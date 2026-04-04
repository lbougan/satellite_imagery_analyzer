from app.agent.tools.search_traffic import format_traffic_summary


class TestFormatTrafficSummary:
    def test_formats_congestion(self) -> None:
        result = format_traffic_summary(
            avg_speed=40.0,
            avg_free_flow=60.0,
            congestion_ratio=0.333,
            segments_sampled=9,
        )
        assert "40" in result
        assert "60" in result
        assert "33" in result
        assert "9" in result

    def test_no_segments(self) -> None:
        result = format_traffic_summary(
            avg_speed=0.0,
            avg_free_flow=0.0,
            congestion_ratio=0.0,
            segments_sampled=0,
        )
        assert "no" in result.lower() or "0" in result

    def test_comparison_format(self) -> None:
        result = format_traffic_summary(
            avg_speed=35.0,
            avg_free_flow=60.0,
            congestion_ratio=0.417,
            segments_sampled=9,
            comparison_avg_speed=50.0,
            comparison_congestion_ratio=0.167,
        )
        assert "slower" in result.lower() or "increase" in result.lower() or "worse" in result.lower()
