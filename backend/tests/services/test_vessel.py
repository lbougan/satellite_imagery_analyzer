import httpx
import pytest
import respx
from app.services.vessel import (
    GFWClient,
    VesselDetection,
    VesselSearchResult,
    search_vessels_in_aoi,
)


GFW_SEARCH_URL = "https://gateway.api.globalfishingwatch.org/v3/vessels/search"

MOCK_GFW_RESPONSE = {
    "entries": [
        {
            "id": "vessel-1",
            "type": "FISHING",
            "lat": 52.01,
            "lon": 4.35,
            "timestamp": "2025-01-15T10:00:00Z",
            "ssvid": "123456789",
        },
        {
            "id": "vessel-2",
            "type": "CARRIER",
            "lat": 52.005,
            "lon": 4.355,
            "timestamp": "2025-01-15T12:00:00Z",
            "ssvid": "987654321",
        },
    ]
}


class TestGFWClient:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, sample_bbox: list[float]) -> None:
        async with respx.mock(using="httpx", assert_all_mocked=True) as mock:
            mock.get(GFW_SEARCH_URL).mock(
                return_value=httpx.Response(200, json=MOCK_GFW_RESPONSE)
            )
            client = GFWClient(api_key="test-key")
            results = await client.search(
                bbox=sample_bbox,
                date_from="2025-01-01",
                date_to="2025-01-31",
            )
        assert len(results) == 2
        assert results[0].vessel_type == "FISHING"

    @pytest.mark.asyncio
    async def test_search_empty_response(self, sample_bbox: list[float]) -> None:
        async with respx.mock(using="httpx", assert_all_mocked=True) as mock:
            mock.get(GFW_SEARCH_URL).mock(
                return_value=httpx.Response(200, json={"entries": []})
            )
            client = GFWClient(api_key="test-key")
            results = await client.search(
                bbox=sample_bbox,
                date_from="2025-01-01",
                date_to="2025-01-31",
            )
        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_api_error(self, sample_bbox: list[float]) -> None:
        async with respx.mock(using="httpx", assert_all_mocked=True) as mock:
            mock.get(GFW_SEARCH_URL).mock(
                return_value=httpx.Response(500, text="Internal Server Error")
            )
            client = GFWClient(api_key="test-key")
            with pytest.raises(httpx.HTTPStatusError):
                await client.search(
                    bbox=sample_bbox,
                    date_from="2025-01-01",
                    date_to="2025-01-31",
                )


class TestSearchVesselsInAoi:
    @pytest.mark.asyncio
    async def test_aggregates_by_type(self, sample_bbox: list[float]) -> None:
        async with respx.mock(using="httpx", assert_all_mocked=True) as mock:
            mock.get(GFW_SEARCH_URL).mock(
                return_value=httpx.Response(200, json=MOCK_GFW_RESPONSE)
            )
            result = await search_vessels_in_aoi(
                bbox=sample_bbox,
                date_from="2025-01-01",
                date_to="2025-01-31",
                api_key="test-key",
            )
        assert result.total_count == 2
        assert result.by_type["FISHING"] == 1
        assert result.by_type["CARRIER"] == 1
