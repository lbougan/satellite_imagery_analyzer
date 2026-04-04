from dataclasses import dataclass
import math

import httpx

TOMTOM_BASE_URL = "https://api.tomtom.com/traffic/services/4"


@dataclass(frozen=True)
class TrafficSegment:
    current_speed: float
    free_flow_speed: float
    current_travel_time: float
    free_flow_travel_time: float
    confidence: float
    road_class: str


@dataclass(frozen=True)
class TrafficSearchResult:
    avg_speed: float
    avg_free_flow_speed: float
    congestion_ratio: float
    segments_sampled: int
    segments: list[TrafficSegment]


class TomTomClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def get_flow_segment(self, lat: float, lon: float, zoom: int = 10) -> TrafficSegment:
        params = {
            "key": self._api_key,
            "point": f"{lat},{lon}",
            "unit": "KMPH",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{TOMTOM_BASE_URL}/flowSegmentData/absolute/{zoom}/json",
                params=params,
            )
            resp.raise_for_status()
        data = resp.json()["flowSegmentData"]
        return TrafficSegment(
            current_speed=data["currentSpeed"],
            free_flow_speed=data["freeFlowSpeed"],
            current_travel_time=data["currentTravelTime"],
            free_flow_travel_time=data["freeFlowTravelTime"],
            confidence=data.get("confidence", 0.0),
            road_class=data.get("frc", "UNKNOWN"),
        )


def _grid_sample_points(bbox: list[float], max_points: int = 9) -> list[tuple[float, float]]:
    west, south, east, north = bbox
    n = min(max_points, 9)
    side = max(int(math.sqrt(n)), 1)
    points = []
    for i in range(side):
        for j in range(side):
            lat = south + (north - south) * (i + 0.5) / side
            lon = west + (east - west) * (j + 0.5) / side
            points.append((lat, lon))
    return points[:max_points]


async def search_traffic_in_aoi(
    bbox: list[float],
    api_key: str,
    max_sample_points: int = 9,
) -> TrafficSearchResult:
    client = TomTomClient(api_key=api_key)
    points = _grid_sample_points(bbox, max_sample_points)
    segments: list[TrafficSegment] = []
    for lat, lon in points:
        try:
            segment = await client.get_flow_segment(lat=lat, lon=lon)
            segments.append(segment)
        except (httpx.HTTPStatusError, httpx.RequestError, KeyError):
            continue
    if not segments:
        return TrafficSearchResult(
            avg_speed=0.0,
            avg_free_flow_speed=0.0,
            congestion_ratio=0.0,
            segments_sampled=0,
            segments=[],
        )
    avg_speed = sum(s.current_speed for s in segments) / len(segments)
    avg_free = sum(s.free_flow_speed for s in segments) / len(segments)
    congestion = 1 - (avg_speed / avg_free) if avg_free > 0 else 0.0
    return TrafficSearchResult(
        avg_speed=round(avg_speed, 1),
        avg_free_flow_speed=round(avg_free, 1),
        congestion_ratio=round(max(0, congestion), 3),
        segments_sampled=len(segments),
        segments=segments,
    )
