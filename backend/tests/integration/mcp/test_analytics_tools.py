"""MCP integration tests for analytics tools.

Tests: get_building_summary and get_consumption_trend with
valid inputs, invalid inputs, and edge cases.
"""

from __future__ import annotations


class TestGetBuildingSummary:
    async def test_valid_building_returns_summary(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_building_summary",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
                "reading_type": "electricity",
            },
        )
        data = result.data
        assert "error" not in data
        assert data["building_id"] == "B001"
        assert data["building_name"] == "City Hall Annex"
        assert data["total_kwh"] > 0
        assert data["measurement_count"] > 0

    async def test_summary_includes_all_required_fields(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_building_summary",
            {
                "building_id": "B007",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
            },
        )
        data = result.data
        required_fields = {
            "building_id",
            "building_name",
            "start_date",
            "end_date",
            "reading_type",
            "total_kwh",
            "average_daily_kwh",
            "peak_hourly_kwh",
            "measurement_count",
        }
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    async def test_default_reading_type_is_electricity(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_building_summary",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
            },
        )
        data = result.data
        assert data.get("reading_type") == "electricity"

    async def test_unknown_building_returns_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_building_summary",
            {
                "building_id": "B999",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "BUILDING_NOT_FOUND"

    async def test_invalid_start_date_returns_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_building_summary",
            {
                "building_id": "B001",
                "start_date": "not-a-date",
                "end_date": "2024-07-31",
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_DATE"

    async def test_invalid_end_date_returns_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_building_summary",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024/07/31",
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_DATE"

    async def test_start_after_end_returns_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_building_summary",
            {
                "building_id": "B001",
                "start_date": "2024-08-01",
                "end_date": "2024-07-01",
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_DATE_RANGE"

    async def test_invalid_reading_type_returns_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_building_summary",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
                "reading_type": "nuclear",
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_READING_TYPE"

    async def test_no_data_period_returns_zero_values(self, mcp_client):
        """A valid building with no readings in range returns zeros, not an error."""
        result = await mcp_client.call_tool(
            "get_building_summary",
            {
                "building_id": "B001",
                "start_date": "2020-01-01",
                "end_date": "2020-01-31",
            },
        )
        data = result.data
        assert "error" not in data
        assert data["total_kwh"] == 0
        assert data["measurement_count"] == 0


class TestGetConsumptionTrend:
    async def test_valid_request_returns_data_points(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024-08-31",
                "granularity": "month",
            },
        )
        data = result.data
        assert "error" not in data
        assert "data_points" in data
        assert len(data["data_points"]) > 0

    async def test_monthly_granularity_returns_correct_periods(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024-08-31",
                "granularity": "month",
            },
        )
        data = result.data
        periods = [p["period"] for p in data["data_points"]]
        assert "2024-07" in periods
        assert "2024-08" in periods

    async def test_data_point_has_required_fields(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "building_id": "B007",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
                "granularity": "day",
            },
        )
        data = result.data
        assert len(data["data_points"]) > 0
        point = data["data_points"][0]
        assert "period" in point
        assert "total_kwh" in point
        assert "average_kwh" in point
        assert "data_points" in point

    async def test_day_granularity_works(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024-07-07",
                "granularity": "day",
            },
        )
        data = result.data
        assert "error" not in data
        assert len(data["data_points"]) > 0

    async def test_week_granularity_works(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
                "granularity": "week",
            },
        )
        data = result.data
        assert "error" not in data
        assert len(data["data_points"]) > 0

    async def test_all_buildings_when_no_building_id(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
                "granularity": "month",
            },
        )
        data = result.data
        assert "error" not in data
        assert data["building_id"] is None
        assert len(data["data_points"]) > 0

    async def test_invalid_granularity_returns_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
                "granularity": "quarter",
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_GRANULARITY"

    async def test_invalid_dates_return_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "start_date": "bad-date",
                "end_date": "2024-07-31",
                "granularity": "month",
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "INVALID_DATE"

    async def test_unknown_building_returns_error(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "building_id": "B999",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
                "granularity": "month",
            },
        )
        data = result.data
        assert "error" in data
        assert data.get("error_code") == "BUILDING_NOT_FOUND"

    async def test_result_contains_metadata_fields(self, mcp_client):
        result = await mcp_client.call_tool(
            "get_consumption_trend",
            {
                "building_id": "B001",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
                "granularity": "month",
                "reading_type": "electricity",
            },
        )
        data = result.data
        assert "building_id" in data
        assert "granularity" in data
        assert "reading_type" in data
        assert data["granularity"] == "month"
        assert data["reading_type"] == "electricity"
