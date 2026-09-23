# MCP Server Design

---

## Overview

The MCP (Model Context Protocol) server exposes a set of read-only tools that
an LLM agent uses to query the energy analytics database.

The server is built with **FastMCP** and runs as a subprocess of the backend API
(stdio transport for local development, SSE transport for network deployment).

**Design principle:** MCP tools are thin adapters. Every tool:
1. Validates input via a Pydantic model
2. Calls a service function
3. Returns a structured result

No database access, no business logic, no side effects inside tool handlers.

---

## Tool Inventory

### `list_buildings`

Returns all buildings registered in the database.

**Input:** none

**Output:**
```json
{
  "buildings": [
    { "id": "B001", "name": "Main Office", "address": "...", "area_sqft": 24000 }
  ]
}
```

**When to call:** When the user asks about available buildings, or before
querying a specific building when the building name is not yet known.

---

### `get_building_consumption`

Returns energy consumption readings for a building over a time range.

**Input:**
```json
{
  "building_id": "B001",
  "start_date": "2024-11-01",
  "end_date": "2024-11-30",
  "reading_type": "electricity"
}
```

**Output:**
```json
{
  "building_id": "B001",
  "building_name": "Main Office",
  "period": { "start": "2024-11-01", "end": "2024-11-30" },
  "readings": [
    { "timestamp": "2024-11-01T00:00:00Z", "kwh": 142.3 }
  ],
  "total_kwh": 4821.7,
  "reading_count": 720
}
```

**When to call:** When the question concerns a specific building's usage
over a time period.

---

### `compare_buildings`

Compares two buildings over the same time range.

**Input:**
```json
{
  "building_id_a": "B001",
  "building_id_b": "B002",
  "start_date": "2024-11-01",
  "end_date": "2024-11-30",
  "reading_type": "electricity"
}
```

**Output:**
```json
{
  "period": { "start": "2024-11-01", "end": "2024-11-30" },
  "building_a": { "id": "B001", "name": "Main Office", "total_kwh": 4821.7 },
  "building_b": { "id": "B002", "name": "Warehouse", "total_kwh": 8103.2 },
  "difference_kwh": 3281.5,
  "difference_pct": 68.1
}
```

---

### `get_monthly_summary`

Returns total consumption by month, for one building or all buildings.

**Input:**
```json
{
  "building_id": "B001",
  "start_year_month": "2024-01",
  "end_year_month": "2024-12"
}
```
`building_id` is optional; omit to get all buildings.

**Output:**
```json
{
  "summaries": [
    {
      "building_id": "B001",
      "building_name": "Main Office",
      "year_month": "2024-11",
      "total_kwh": 4821.7,
      "mom_change_pct": 3.2
    }
  ]
}
```

---

### `find_anomalies`

Identifies readings that deviate significantly from the building's historical baseline.

**Input:**
```json
{
  "building_id": "B001",
  "threshold_stddev": 2.0
}
```
`building_id` is optional; omit to check all buildings.

**Output:**
```json
{
  "anomalies": [
    {
      "building_id": "B001",
      "building_name": "Main Office",
      "timestamp": "2024-11-15T14:00:00Z",
      "kwh": 892.1,
      "baseline_kwh": 142.3,
      "stddev_from_baseline": 4.7
    }
  ]
}
```

---

### `get_schema`

Returns a description of the database schema available to the agent.

**Input:** none

**Output:**
```json
{
  "tables": [
    {
      "name": "buildings",
      "description": "...",
      "columns": [...]
    }
  ]
}
```

**Note:** This returns a static description, not live schema introspection.
It is safe to call at any time.

---

### `run_safe_query`

Executes a read-only SQL query that has been validated against an allowlist.

**Input:**
```json
{
  "query": "SELECT building_id, SUM(kwh) FROM energy_readings WHERE ...",
  "params": { "building_id": "B001" }
}
```

**Output:**
```json
{
  "rows": [...],
  "row_count": 12
}
```

**Safety constraints:**
- Only `SELECT` statements are accepted
- No subqueries accessing system tables
- Query is validated by `SQLAllowlistValidator` before execution
- Results are truncated to 500 rows
- Execution timeout: 5 seconds

---

## Tool Design Rules

1. **Docstrings are for the LLM.** Write them as if explaining to an AI assistant,
   not a human developer. Include: purpose, when to call, what it returns.

2. **All inputs are Pydantic models.** No `dict`, no `Any`.

3. **All outputs are JSON-serializable.** Return Pydantic models that are
   `.model_dump()`-able.

4. **No writes.** Every tool is read-only. If the LLM requests a write
   operation, it should receive a refusal message from the application layer.

5. **Errors are data.** Tool errors are returned as structured error results
   (`{"error": "building_id B999 not found"}`), not raised as exceptions.
   The LLM can reason about error results.

6. **Tool names are stable.** Renaming a tool is a breaking change for any
   evaluation task that references it.

---

## MCP Transport Configuration

| Environment | Transport | Notes |
|---|---|---|
| Local dev | `stdio` | Backend spawns MCP server as subprocess |
| Docker Compose | `stdio` | Same, within container |
| AWS ECS | `sse` | MCP server runs as separate container, backend connects via HTTP |

Transport is configured via `MCP_TRANSPORT` environment variable.

---

## Adding a New Tool

1. Define input/output Pydantic models in `backend/mcp/models.py`
2. Add a service function in the appropriate service in `backend/services/`
3. Add the tool handler in `backend/mcp/server.py`
4. Write a unit test for the service function
5. Write an integration test for the tool handler
6. Update this document with the new tool specification
7. Add a tool schema contract test in `backend/tests/mcp/`
