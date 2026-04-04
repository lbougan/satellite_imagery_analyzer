from app.agent.tools.search_vessels import format_vessel_summary


class TestFormatVesselSummary:
    def test_formats_count_and_types(self) -> None:
        result = format_vessel_summary(
            total=5,
            by_type={"FISHING": 3, "CARRIER": 2},
            date_from="2025-01-01",
            date_to="2025-01-31",
        )
        assert "5" in result
        assert "FISHING" in result
        assert "CARRIER" in result
        assert "2025-01-01" in result

    def test_zero_vessels(self) -> None:
        result = format_vessel_summary(
            total=0,
            by_type={},
            date_from="2025-01-01",
            date_to="2025-01-31",
        )
        assert "0" in result or "no" in result.lower()

    def test_delta_format(self) -> None:
        result = format_vessel_summary(
            total=10,
            by_type={"FISHING": 10},
            date_from="2025-01-01",
            date_to="2025-01-31",
            comparison_total=5,
            comparison_by_type={"FISHING": 5},
            comparison_date_from="2024-01-01",
            comparison_date_to="2024-01-31",
        )
        assert "increase" in result.lower() or "+" in result or "100%" in result
