from collections import Counter
from dataclasses import dataclass

import httpx

GFW_BASE_URL = "https://gateway.api.globalfishingwatch.org/v3"


@dataclass(frozen=True)
class VesselDetection:
    vessel_id: str
    vessel_type: str
    lat: float
    lon: float
    timestamp: str
    ssvid: str


@dataclass(frozen=True)
class VesselSearchResult:
    total_count: int
    by_type: dict[str, int]
    detections: list[VesselDetection]
    date_from: str
    date_to: str


class GFWClient:
    """Async client for the Global Fishing Watch API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(
        self,
        bbox: list[float],
        date_from: str,
        date_to: str,
    ) -> list[VesselDetection]:
        west, south, east, north = bbox
        params = {
            "datasets": "public-global-fishing-events:latest",
            "start-date": date_from,
            "end-date": date_to,
            "geometry": f"{west},{south},{east},{north}",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{GFW_BASE_URL}/vessels/search",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()

        entries = resp.json().get("entries", [])
        return [
            VesselDetection(
                vessel_id=e["id"],
                vessel_type=e.get("type", "UNKNOWN"),
                lat=e["lat"],
                lon=e["lon"],
                timestamp=e["timestamp"],
                ssvid=e.get("ssvid", ""),
            )
            for e in entries
        ]


async def search_vessels_in_aoi(
    bbox: list[float],
    date_from: str,
    date_to: str,
    api_key: str,
) -> VesselSearchResult:
    client = GFWClient(api_key=api_key)
    detections = await client.search(bbox, date_from, date_to)
    type_counts = dict(Counter(d.vessel_type for d in detections))
    return VesselSearchResult(
        total_count=len(detections),
        by_type=type_counts,
        detections=detections,
        date_from=date_from,
        date_to=date_to,
    )
