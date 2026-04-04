import httpx
import pytest
import respx
from app.services.traffic import (
    TomTomClient,
    TrafficSegment,
    search_traffic_in_aoi,
    TrafficSearchResult,
)


TOMTOM_FLOW_URL = (
    "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
)

MOCK_FLOW_RESPONSE = {
    "flowSegmentData": {
        "frc": "FRC0",
        "currentSpeed": 45,
        "freeFlowSpeed": 60,
        "currentTravelTime": 120,
        "freeFlowTravelTime": 90,
        "confidence": 0.95,
        "coordinates": {
            "coordinate": [
                {"latitude": 52.01, "longitude": 4.35},
                {"latitude": 52.02, "longitude": 4.36},
            ]
        },
    }
}


class TestTomTomClient:
    @pytest.mark.asyncio
    async def test_flow_returns_segment(self) -> None:
        async with respx.mock(using="httpx", assert_all_mocked=True) as mock:
            mock.get(TOMTOM_FLOW_URL).mock(
                return_value=httpx.Response(200, json=MOCK_FLOW_RESPONSE)
            )
            client = TomTomClient(api_key="test-key")
            segment = await client.get_flow_segment(lat=52.01, lon=4.35)
        assert segment.current_speed == 45
        assert segment.free_flow_speed == 60

    @pytest.mark.asyncio
    async def test_flow_handles_error(self) -> None:
        async with respx.mock(using="httpx", assert_all_mocked=True) as mock:
            mock.get(TOMTOM_FLOW_URL).mock(
                return_value=httpx.Response(403, text="Forbidden")
            )
            client = TomTomClient(api_key="bad-key")
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_flow_segment(lat=52.01, lon=4.35)


class TestSearchTrafficInAoi:
    @pytest.mark.asyncio
    async def test_samples_grid_points(self, sample_bbox: list[float]) -> None:
        async with respx.mock(using="httpx", assert_all_mocked=True) as mock:
            mock.get(TOMTOM_FLOW_URL).mock(
                return_value=httpx.Response(200, json=MOCK_FLOW_RESPONSE)
            )
            result = await search_traffic_in_aoi(
                bbox=sample_bbox,
                api_key="test-key",
            )
        assert isinstance(result, TrafficSearchResult)
        assert result.avg_speed > 0
        assert result.avg_free_flow_speed > 0
        assert 0 <= result.congestion_ratio <= 1.0
