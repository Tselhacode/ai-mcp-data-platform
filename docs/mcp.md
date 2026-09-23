# MCP Server Design

---

## Overview

The MCP (Model Context Protocol) server exposes a set of read-only tools that
an LLM agent uses to query the energy analytics database.

The server is built with **FastMCP 4.0.5** (backed by the **MCP SDK 2.2.0**)
and runs as a subprocess of the backend API (stdio transport for local
development, SSE transport for network deployment).

**Design principle:** MCP tools are thin adapters. Every tool:
1. Validates input
2. Calls a service function (or executes a validated SQL query)
3. Returns a structured dict

No database access, no business logic, no side effects inside tool handlers.

---

## Package Structure

```
backend/mcp/
    __init__.py        # Resolves mcp/SDK naming conflict (see note below)
    _server.py         # FastMCP server factory: create_mcp_server()
    schemas.py         # Pydantic request/response models
    dependencies.py    # Session factory and EnergyService helpers
    tools/
        schema_tools.py    # list_tables, describe_table
        query_tools.py     # run_readonly_query
        analytics_tools.py # get_building_summary, get_consumption_trend
```

### Naming conflict note

The local `backend/mcp/` directory shares its name with the MCP SDK package
(`mcp` on PyPI). `mcp/__init__.py` resolves this by extending `__path__` to
include the SDK's `mcp/` directory, then re-exporting all SDK top-level symbols.
This makes `from mcp.server.lowlevel...` (used internally by FastMCP) and
`from mcp import MCPError` both work correctly without renaming either package.

---

## Tool Inventory

### `list_tables`

List the analytical tables available for querying.

**Input:** none

**Output:**
```json
{
  "tables": [
    {
      "name": "buildings",
      "description": "Metadata about monitored buildings ...",
      "row_count_estimate": null
    },
    {
      "name": "energy_readings",
      "description": "Hourly energy consumption readings ...",
      "row_count_estimate": null
    }
  ]
}
```

**When to call:** Before writing SQL queries or calling analytics tools, to
discover what data is available.

---

### `describe_table`

Describe the columns, data types, and purpose of a table.

**Input:**
```json
{ "table_name": "energy_readings" }
```
`table_name` must be `"buildings"` or `"energy_readings"`.

**Output:**
```json
{
  "table_name": "energy_readings",
  "description": "...",
  "columns": [
    { "name": "id", "data_type": "INTEGER", "description": "...", "nullable": false },
    ...
  ]
}
```

Returns `{"error": "...", "error_code": "TABLE_NOT_FOUND"}` for unknown tables.

---

### `run_readonly_query`

Execute a read-only SQL SELECT query against the energy database.

**Input:**
```json
{
  "query": "SELECT building_id, SUM(kwh) FROM energy_readings WHERE reading_type = :rtype GROUP BY building_id",
  "params": { "rtype": "electricity" },
  "limit": 1000
}
```

- `query`: A single SQL SELECT statement. Use `:param_name` for bind parameters.
- `params`: Optional dict of bind parameter values.
- `limit`: Maximum rows to return (default 1000, maximum 5000).

**Output:**
```json
{
  "columns": ["building_id", "SUM(kwh)"],
  "rows": [["B001", 4821.7], ["B007", 18200.0]],
  "row_count": 2,
  "truncated": false,
  "execution_time_ms": 3.2
}
```

Returns an error dict if the query is rejected or fails.

**SQL security constraints:**
- Only `SELECT` statements are accepted (validated by sqlglot parser)
- UNION, multi-statement (`;`), INSERT, UPDATE, DELETE, DROP, CREATE, ALTER,
  TRUNCATE are all rejected with `error_code: "INVALID_SQL"`
- Comments (`--` and `/* */`) are handled correctly
- Results truncated to max 5000 rows
- All parameters use SQLAlchemy bound params — no string interpolation

---

### `get_building_summary`

Get an energy consumption summary for a specific building over a date range.

**Input:**
```json
{
  "building_id": "B007",
  "start_date": "2024-07-01",
  "end_date": "2024-07-31",
  "reading_type": "electricity"
}
```
- `reading_type` defaults to `"electricity"`. Allowed: `"electricity"`, `"gas"`, `"solar"`.

**Output:**
```json
{
  "building_id": "B007",
  "building_name": "Central Data Center",
  "start_date": "2024-07-01",
  "end_date": "2024-07-31",
  "reading_type": "electricity",
  "total_kwh": 36456.0,
  "average_daily_kwh": 1176.0,
  "peak_hourly_kwh": 50.0,
  "measurement_count": 744
}
```

Returns an error dict with:
- `error_code: "BUILDING_NOT_FOUND"` if building ID is unknown
- `error_code: "INVALID_DATE"` if dates are not YYYY-MM-DD
- `error_code: "INVALID_DATE_RANGE"` if start >= end
- `error_code: "INVALID_READING_TYPE"` if reading type is not in the allowlist

Returns zeros (not an error) when there are no readings in the requested range
for a valid building.

---

### `get_consumption_trend`

Get energy consumption aggregated by time period (day, week, or month).

**Input:**
```json
{
  "start_date": "2024-07-01",
  "end_date": "2024-08-31",
  "granularity": "month",
  "building_id": "B001",
  "reading_type": "electricity"
}
```
- `building_id` is optional; omit to aggregate across all buildings.
- `granularity` defaults to `"month"`. Allowed: `"day"`, `"week"`, `"month"`.
- `reading_type` defaults to `"electricity"`.

**Output:**
```json
{
  "building_id": "B001",
  "granularity": "month",
  "reading_type": "electricity",
  "data_points": [
    { "period": "2024-07", "total_kwh": 9920.0, "average_kwh": 14.4, "data_points": 744 },
    { "period": "2024-08", "total_kwh": 10416.0, "average_kwh": 14.5, "data_points": 744 }
  ]
}
```

Period label formats:
- `"month"` → `"YYYY-MM"` (e.g. `"2024-07"`)
- `"week"` → ISO week start date `"YYYY-MM-DD"` (Monday)
- `"day"` → `"YYYY-MM-DD"`

Returns an error dict with:
- `error_code: "INVALID_GRANULARITY"` for unknown granularity
- `error_code: "BUILDING_NOT_FOUND"` if building ID is specified but unknown
- `error_code: "INVALID_DATE"` / `"INVALID_DATE_RANGE"` for bad dates

---

## Error Response Format

All tools return errors as plain dicts, not raised exceptions:

```json
{
  "error": "Building 'B999' not found.",
  "error_code": "BUILDING_NOT_FOUND"
}
```

The LLM can read the error and decide how to proceed (e.g. call `list_tables`
to find valid building IDs, then retry).

---

## Tool Design Rules

1. **Docstrings are for the LLM.** Write them as if explaining to an AI assistant,
   not a human developer. Include: purpose, when to call, what it returns.

2. **All outputs are JSON-serializable.** Return Pydantic `.model_dump()` dicts.

3. **No writes.** Every tool is read-only.

4. **Errors are data.** Tool errors are returned as structured error results,
   not raised as exceptions. The LLM can reason about error results.

5. **Tool names are stable.** Renaming a tool is a breaking change for any
   evaluation task that references it.

---

## MCP Transport Configuration

| Environment | Transport | Notes |
|---|---|---|
| Local dev | `stdio` | Backend spawns MCP server as subprocess |
| Docker Compose | `stdio` | Same, within container |
| AWS ECS | `sse` | MCP server runs as separate container, backend connects via HTTP |

Transport is configured via `MCP_TRANSPORT` environment variable.
The server entry point is `mcp._server.run_server()`.

---

## Running the Server

```bash
# From backend/ directory
uv run python -m mcp._server
```

Or via the FastMCP CLI:
```bash
uv run fastmcp run mcp._server:create_mcp_server
```

---

## Adding a New Tool

1. Define input/output Pydantic models in `backend/mcp/schemas.py`
2. Add a service function in `backend/services/energy_service.py`
3. Add the tool handler in the appropriate `backend/mcp/tools/*.py` file
4. Register the tool group in `backend/mcp/_server.py`
5. Write integration tests in `backend/tests/integration/mcp/`
6. Update this document with the new tool specification
