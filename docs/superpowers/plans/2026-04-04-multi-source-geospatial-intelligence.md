# Multi-Source Geospatial Intelligence — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the satellite imagery agent into a multi-source geospatial intelligence tool with vessel traffic (Global Fishing Watch), road traffic (TomTom), 2-scene comparison constraints, smart date selection, and large-area optimization.

**Architecture:** Add two new service modules (`vessel.py`, `traffic.py`) alongside the existing `stac.py`/`raster.py`. Each service gets corresponding agent tools. The existing agent graph and prompt are extended to route questions to the right data source. Area validation and scene limits are enforced in the existing satellite tools. The frontend gets new tool-status labels and result rendering for non-imagery intelligence.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, httpx (async HTTP), pytest + pytest-asyncio (testing), React 18, TypeScript, Zustand

---

## File Structure

### New files
- `backend/app/services/vessel.py` — Global Fishing Watch API client
- `backend/app/services/traffic.py` — TomTom Traffic API client
- `backend/app/services/area.py` — AOI area calculation and validation
- `backend/app/agent/tools/search_vessels.py` — Vessel search + comparison tools
- `backend/app/agent/tools/search_traffic.py` — Traffic search + comparison tools
- `backend/tests/conftest.py` — Shared pytest fixtures
- `backend/tests/services/test_area.py` — Area validation tests
- `backend/tests/services/test_vessel.py` — Vessel service tests
- `backend/tests/services/test_traffic.py` — Traffic service tests
- `backend/tests/agent/tools/test_search_imagery.py` — Updated search imagery tests
- `backend/tests/agent/tools/test_download_imagery.py` — Download constraint tests
- `backend/tests/agent/tools/test_search_vessels.py` — Vessel tool tests
- `backend/tests/agent/tools/test_search_traffic.py` — Traffic tool tests
- `backend/pytest.ini` — Pytest configuration

### Modified files
- `backend/app/config.py` — New API keys + area/scene thresholds
- `backend/app/agent/tools/search_imagery.py` — Smart date selection (pick 2 best scenes)
- `backend/app/agent/tools/download_imagery.py` — 2-scene hard limit
- `backend/app/services/raster.py` — Overview downsampling for large AOIs
- `backend/app/agent/tools/__init__.py` — Register new tools
- `backend/app/agent/prompts.py` — Multi-source routing instructions
- `backend/app/agent/state.py` — New state fields for vessel/traffic results
- `backend/requirements.txt` — Add pytest, pytest-asyncio, respx (HTTP mocking)
- `frontend/src/components/ToolStatusCard.tsx` — New tool labels
- `frontend/src/components/MessageBubble.tsx` — Render vessel/traffic results

---

## Task 1: Test Infrastructure Setup

**Files:**
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/services/__init__.py`
- Create: `backend/tests/agent/__init__.py`
- Create: `backend/tests/agent/tools/__init__.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add test dependencies to requirements.txt**

Append to `backend/requirements.txt`:

```
pytest==8.3.3
pytest-asyncio==0.24.0
respx==0.21.1
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
```

- [ ] **Step 3: Create test directory structure and conftest**

`backend/tests/__init__.py`: empty file

`backend/tests/services/__init__.py`: empty file

`backend/tests/agent/__init__.py`: empty file

`backend/tests/agent/tools/__init__.py`: empty file

`backend/tests/conftest.py`:

```python
import pytest


@pytest.fixture
def sample_bbox() -> list[float]:
    """Small AOI in the Netherlands (~1 km²)."""
    return [4.35, 52.00, 4.36, 52.01]


@pytest.fixture
def large_bbox() -> list[float]:
    """Large AOI (~500 km²) for testing area limits."""
    return [4.0, 52.0, 4.5, 52.5]


@pytest.fixture
def huge_bbox() -> list[float]:
    """Huge AOI (~5000 km²) exceeding hard cap."""
    return [3.0, 51.0, 5.0, 53.0]


@pytest.fixture
def sample_aoi_geojson(sample_bbox: list[float]) -> dict:
    """GeoJSON polygon from sample bbox."""
    w, s, e, n = sample_bbox
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
        },
        "properties": {},
    }
```

- [ ] **Step 4: Install dependencies and verify pytest runs**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && pip install pytest==8.3.3 pytest-asyncio==0.24.0 respx==0.21.1`

Then: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest --co -q`

Expected: `no tests ran` (collection succeeds, no tests found yet)

- [ ] **Step 5: Commit**

```bash
git add backend/pytest.ini backend/tests/ backend/requirements.txt
git commit -m "chore: add pytest infrastructure and test fixtures"
```

---

## Task 2: Area Validation Service

**Files:**
- Create: `backend/app/services/area.py`
- Create: `backend/tests/services/test_area.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add area thresholds to config.py**

Add these fields to the `Settings` class in `backend/app/config.py`, after `imagery_cache_dir`:

```python
    # Area thresholds (km²)
    area_soft_limit_km2: float = 200.0
    area_hard_limit_km2: float = 2000.0

    # Scene comparison limit
    max_comparison_scenes: int = 2
```

- [ ] **Step 2: Write failing tests for area validation**

`backend/tests/services/test_area.py`:

```python
import pytest
from app.services.area import bbox_area_km2, validate_aoi_area, AreaTooLargeError


class TestBboxAreaKm2:
    def test_small_area(self, sample_bbox: list[float]) -> None:
        area = bbox_area_km2(sample_bbox)
        assert 0.5 < area < 2.0  # ~1 km² in the Netherlands

    def test_large_area(self, large_bbox: list[float]) -> None:
        area = bbox_area_km2(large_bbox)
        assert 100 < area < 2000

    def test_equatorial_area(self) -> None:
        # 1 degree x 1 degree at equator ≈ 12,321 km²
        area = bbox_area_km2([0.0, 0.0, 1.0, 1.0])
        assert 10_000 < area < 15_000

    def test_high_latitude_smaller(self) -> None:
        # Same degree span at 60°N should be smaller due to longitude convergence
        equator = bbox_area_km2([0.0, 0.0, 1.0, 1.0])
        high_lat = bbox_area_km2([0.0, 60.0, 1.0, 61.0])
        assert high_lat < equator


class TestValidateAoiArea:
    def test_small_area_returns_none(self, sample_bbox: list[float]) -> None:
        result = validate_aoi_area(sample_bbox)
        assert result is None

    def test_soft_limit_returns_warning(self, large_bbox: list[float]) -> None:
        result = validate_aoi_area(large_bbox)
        assert result is not None
        assert result["level"] == "warning"
        assert "downsampled" in result["message"].lower() or "large" in result["message"].lower()

    def test_hard_limit_raises(self, huge_bbox: list[float]) -> None:
        with pytest.raises(AreaTooLargeError):
            validate_aoi_area(huge_bbox)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/services/test_area.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.area'`

- [ ] **Step 4: Implement area validation service**

`backend/app/services/area.py`:

```python
import math


class AreaTooLargeError(Exception):
    """Raised when AOI exceeds the hard area limit."""

    def __init__(self, area_km2: float, limit_km2: float) -> None:
        self.area_km2 = area_km2
        self.limit_km2 = limit_km2
        super().__init__(
            f"Area of interest is {area_km2:.0f} km², which exceeds the "
            f"maximum of {limit_km2:.0f} km². Please draw a smaller area."
        )


def bbox_area_km2(bbox: list[float]) -> float:
    """Approximate area of a WGS84 bounding box in km².

    Uses the spherical Earth model with latitude-corrected longitude.
    """
    west, south, east, north = bbox
    lat_mid = math.radians((south + north) / 2)

    km_per_deg_lat = 111.132
    km_per_deg_lon = 111.320 * math.cos(lat_mid)

    width_km = abs(east - west) * km_per_deg_lon
    height_km = abs(north - south) * km_per_deg_lat

    return width_km * height_km


def validate_aoi_area(
    bbox: list[float],
    soft_limit_km2: float = 200.0,
    hard_limit_km2: float = 2000.0,
) -> dict | None:
    """Validate AOI area against thresholds.

    Returns None if under soft limit, a warning dict if between soft and hard,
    or raises AreaTooLargeError if over hard limit.
    """
    area = bbox_area_km2(bbox)

    if area > hard_limit_km2:
        raise AreaTooLargeError(area, hard_limit_km2)

    if area > soft_limit_km2:
        return {
            "level": "warning",
            "area_km2": area,
            "message": (
                f"Large area ({area:.0f} km²). Imagery will be downsampled "
                f"for performance. For full resolution, draw an area under "
                f"{soft_limit_km2:.0f} km²."
            ),
        }

    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/services/test_area.py -v`

Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/area.py backend/tests/services/test_area.py backend/app/config.py
git commit -m "feat: add AOI area validation with soft/hard limits"
```

---

## Task 3: Smart Date Selection in Search Imagery

**Files:**
- Create: `backend/tests/agent/tools/test_search_imagery.py`
- Modify: `backend/app/agent/tools/search_imagery.py`

- [ ] **Step 1: Write failing tests for smart date selection**

`backend/tests/agent/tools/test_search_imagery.py`:

```python
from app.agent.tools.search_imagery import pick_best_scenes


class TestPickBestScenes:
    def test_returns_max_n_scenes(self) -> None:
        scenes = [
            {"scene_id": "a", "cloud_cover": 5.0, "datetime": "2025-01-01"},
            {"scene_id": "b", "cloud_cover": 10.0, "datetime": "2025-01-06"},
            {"scene_id": "c", "cloud_cover": 3.0, "datetime": "2025-01-12"},
            {"scene_id": "d", "cloud_cover": 8.0, "datetime": "2025-01-18"},
        ]
        result = pick_best_scenes(scenes, max_scenes=2)
        assert len(result) == 2

    def test_prefers_low_cloud_cover(self) -> None:
        scenes = [
            {"scene_id": "cloudy", "cloud_cover": 50.0, "datetime": "2025-01-01"},
            {"scene_id": "clear", "cloud_cover": 2.0, "datetime": "2025-01-06"},
            {"scene_id": "medium", "cloud_cover": 20.0, "datetime": "2025-01-12"},
        ]
        result = pick_best_scenes(scenes, max_scenes=2)
        ids = [s["scene_id"] for s in result]
        assert "clear" in ids
        assert "cloudy" not in ids

    def test_single_scene_when_max_is_one(self) -> None:
        scenes = [
            {"scene_id": "a", "cloud_cover": 5.0, "datetime": "2025-01-01"},
            {"scene_id": "b", "cloud_cover": 3.0, "datetime": "2025-01-06"},
        ]
        result = pick_best_scenes(scenes, max_scenes=1)
        assert len(result) == 1
        assert result[0]["scene_id"] == "b"

    def test_empty_input(self) -> None:
        result = pick_best_scenes([], max_scenes=2)
        assert result == []

    def test_fewer_scenes_than_max(self) -> None:
        scenes = [{"scene_id": "a", "cloud_cover": 5.0, "datetime": "2025-01-01"}]
        result = pick_best_scenes(scenes, max_scenes=2)
        assert len(result) == 1

    def test_preserves_temporal_spread(self) -> None:
        """When cloud cover is similar, prefer scenes spread apart in time."""
        scenes = [
            {"scene_id": "jan1", "cloud_cover": 5.0, "datetime": "2025-01-01"},
            {"scene_id": "jan3", "cloud_cover": 4.0, "datetime": "2025-01-03"},
            {"scene_id": "mar1", "cloud_cover": 6.0, "datetime": "2025-03-01"},
        ]
        result = pick_best_scenes(scenes, max_scenes=2)
        ids = [s["scene_id"] for s in result]
        # Should pick jan3 (best cloud) + mar1 (furthest apart) over jan1+jan3
        assert "mar1" in ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/agent/tools/test_search_imagery.py -v`

Expected: FAIL — `ImportError: cannot import name 'pick_best_scenes'`

- [ ] **Step 3: Implement pick_best_scenes**

Add this function at the top of `backend/app/agent/tools/search_imagery.py`, before the `@tool` function:

```python
from datetime import datetime as dt


def pick_best_scenes(
    scenes: list[dict], max_scenes: int = 2
) -> list[dict]:
    """Select the best scenes for comparison.

    Strategy: sort by cloud cover, then if picking 2+, maximize temporal
    spread among the top candidates (top 2x max_scenes by cloud cover).
    """
    if not scenes or max_scenes < 1:
        return scenes[:max_scenes] if scenes else []

    sorted_by_cloud = sorted(scenes, key=lambda s: s["cloud_cover"])

    if max_scenes == 1:
        return [sorted_by_cloud[0]]

    # Take top candidates (2x max to have room for temporal spread)
    candidates = sorted_by_cloud[: max(max_scenes * 2, len(sorted_by_cloud))]

    if len(candidates) <= max_scenes:
        return candidates

    # Pick the best cloud cover scene first
    selected = [candidates[0]]
    remaining = candidates[1:]

    while len(selected) < max_scenes and remaining:
        # Pick the scene furthest in time from all selected scenes
        best_idx = 0
        best_min_gap = -1.0
        for i, candidate in enumerate(remaining):
            c_date = dt.fromisoformat(candidate["datetime"][:10])
            min_gap = min(
                abs((c_date - dt.fromisoformat(s["datetime"][:10])).days)
                for s in selected
            )
            if min_gap > best_min_gap:
                best_min_gap = min_gap
                best_idx = i
        selected.append(remaining.pop(best_idx))

    return selected
```

- [ ] **Step 4: Update the search_imagery tool to report best scenes**

In `backend/app/agent/tools/search_imagery.py`, modify the existing `search_imagery` tool function. After the line that calls `search_scenes()` and builds the results list, add at the end before returning:

```python
    # Recommend best scenes for comparison
    if results and len(results) > 2:
        best = pick_best_scenes(results, max_scenes=2)
        best_ids = [s["scene_id"] for s in best]
        lines.append(f"\n**Recommended scenes for comparison** (lowest cloud cover, best temporal spread): {', '.join(best_ids)}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/agent/tools/test_search_imagery.py -v`

Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/tools/search_imagery.py backend/tests/agent/tools/test_search_imagery.py
git commit -m "feat: smart date selection picks 2 best scenes by cloud cover and temporal spread"
```

---

## Task 4: 2-Scene Download Limit

**Files:**
- Create: `backend/tests/agent/tools/test_download_imagery.py`
- Modify: `backend/app/agent/tools/download_imagery.py`

- [ ] **Step 1: Write failing tests for scene limit enforcement**

`backend/tests/agent/tools/test_download_imagery.py`:

```python
from app.agent.tools.download_imagery import validate_scene_count, MAX_SCENES


class TestValidateSceneCount:
    def test_within_limit(self) -> None:
        result = validate_scene_count(["scene_a", "scene_b"])
        assert result is None

    def test_single_scene(self) -> None:
        result = validate_scene_count(["scene_a"])
        assert result is None

    def test_exceeds_limit(self) -> None:
        result = validate_scene_count(["a", "b", "c"])
        assert result is not None
        assert "2" in result
        assert "3" in str(result)

    def test_max_scenes_is_two(self) -> None:
        assert MAX_SCENES == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/agent/tools/test_download_imagery.py -v`

Expected: FAIL — `ImportError: cannot import name 'validate_scene_count'`

- [ ] **Step 3: Implement scene count validation**

Add at the top of `backend/app/agent/tools/download_imagery.py`, after the imports:

```python
MAX_SCENES = 2


def validate_scene_count(scene_ids: list[str]) -> str | None:
    """Return an error message if too many scenes requested, else None."""
    if len(scene_ids) > MAX_SCENES:
        return (
            f"Cannot download {len(scene_ids)} scenes. Maximum is {MAX_SCENES} "
            f"scenes for comparison. Please select the 2 best scenes to compare."
        )
    return None
```

- [ ] **Step 4: Enforce limit in download_imagery_batch tool**

In `backend/app/agent/tools/download_imagery.py`, find the `download_imagery_batch` function body. Add this check at the very beginning of the function, before any processing:

```python
    error = validate_scene_count(scene_ids)
    if error:
        return error
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/agent/tools/test_download_imagery.py -v`

Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/tools/download_imagery.py backend/tests/agent/tools/test_download_imagery.py
git commit -m "feat: enforce 2-scene hard limit on batch downloads"
```

---

## Task 5: Large Area Downsampling in Raster Service

**Files:**
- Modify: `backend/app/services/raster.py`
- Modify: `backend/app/agent/tools/download_imagery.py`

- [ ] **Step 1: Integrate area validation into download tools**

In `backend/app/agent/tools/download_imagery.py`, add this import at the top:

```python
from app.services.area import validate_aoi_area, bbox_area_km2, AreaTooLargeError
```

In the `_download_one_scene` internal function (used by both tools), add area checking at the start, before calling `download_bands_parallel()`:

```python
    # Area validation and downsampling
    max_size = None
    try:
        warning = validate_aoi_area(bbox)
        if warning:
            max_size = 2048  # Use COG overviews for large areas
    except AreaTooLargeError as exc:
        return str(exc)
```

Then pass `max_size` to the `download_bands_parallel()` call (which already forwards it to `download_band()`). Find the existing call and add the parameter:

```python
    paths = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: download_bands_parallel(signed_urls, out_dir, bbox=bbox, max_size=max_size),
    )
```

Note: `download_bands_parallel` and `download_band` in `raster.py` already accept a `max_size` parameter that reads COG overview levels instead of full resolution. This is already implemented — we just need to pass it through.

- [ ] **Step 2: Verify the raster service already supports max_size**

Read `backend/app/services/raster.py` and confirm `download_band()` has a `max_size` parameter. It should already contain logic like:

```python
if max_size and (window.width > max_size or window.height > max_size):
    # Read at reduced resolution using overview levels
```

If this parameter exists and works, no changes needed to raster.py. If the parameter exists but `download_bands_parallel` doesn't forward it, add the forwarding.

- [ ] **Step 3: Run existing tests**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/agent/tools/download_imagery.py
git commit -m "feat: auto-downsample imagery for large AOIs using COG overviews"
```

---

## Task 6: Vessel Traffic Service (Global Fishing Watch)

**Files:**
- Create: `backend/app/services/vessel.py`
- Create: `backend/tests/services/test_vessel.py`

- [ ] **Step 1: Write failing tests for vessel service**

`backend/tests/services/test_vessel.py`:

```python
import httpx
import pytest
import respx
from app.services.vessel import (
    GFWClient,
    VesselSearchResult,
    search_vessels_in_aoi,
)


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
    @respx.mock
    @pytest.mark.asyncio
    async def test_search_returns_results(self, sample_bbox: list[float]) -> None:
        respx.get("https://gateway.api.globalfishingwatch.org/v3/vessels/search").mock(
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

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_empty_response(self, sample_bbox: list[float]) -> None:
        respx.get("https://gateway.api.globalfishingwatch.org/v3/vessels/search").mock(
            return_value=httpx.Response(200, json={"entries": []})
        )
        client = GFWClient(api_key="test-key")
        results = await client.search(
            bbox=sample_bbox,
            date_from="2025-01-01",
            date_to="2025-01-31",
        )
        assert results == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_handles_api_error(self, sample_bbox: list[float]) -> None:
        respx.get("https://gateway.api.globalfishingwatch.org/v3/vessels/search").mock(
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
    @respx.mock
    @pytest.mark.asyncio
    async def test_aggregates_by_type(self, sample_bbox: list[float]) -> None:
        respx.get("https://gateway.api.globalfishingwatch.org/v3/vessels/search").mock(
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/services/test_vessel.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.vessel'`

- [ ] **Step 3: Implement vessel service**

`backend/app/services/vessel.py`:

```python
from dataclasses import dataclass, field
from collections import Counter

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
        """Search for vessel detections in a bounding box and date range."""
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
    """Search and aggregate vessel detections in an AOI."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/services/test_vessel.py -v`

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/vessel.py backend/tests/services/test_vessel.py
git commit -m "feat: add Global Fishing Watch vessel detection service"
```

---

## Task 7: Vessel Traffic Agent Tools

**Files:**
- Create: `backend/app/agent/tools/search_vessels.py`
- Create: `backend/tests/agent/tools/test_search_vessels.py`

- [ ] **Step 1: Write failing tests for vessel tools**

`backend/tests/agent/tools/test_search_vessels.py`:

```python
import httpx
import pytest
import respx
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/agent/tools/test_search_vessels.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement vessel tools**

`backend/app/agent/tools/search_vessels.py`:

```python
from langchain_core.tools import tool

from app.config import get_settings
from app.services.vessel import search_vessels_in_aoi


def format_vessel_summary(
    total: int,
    by_type: dict[str, int],
    date_from: str,
    date_to: str,
    comparison_total: int | None = None,
    comparison_by_type: dict[str, int] | None = None,
    comparison_date_from: str | None = None,
    comparison_date_to: str | None = None,
) -> str:
    """Format vessel search results as a readable summary."""
    lines = [f"**Vessel detections ({date_from} to {date_to}):** {total} vessels"]

    if by_type:
        breakdown = ", ".join(f"{vtype}: {count}" for vtype, count in sorted(by_type.items()))
        lines.append(f"By type: {breakdown}")
    else:
        lines.append("No vessels detected in this area and time range.")

    if comparison_total is not None and comparison_by_type is not None:
        lines.append("")
        lines.append(
            f"**Comparison period ({comparison_date_from} to {comparison_date_to}):** "
            f"{comparison_total} vessels"
        )
        if comparison_by_type:
            breakdown = ", ".join(
                f"{vtype}: {count}" for vtype, count in sorted(comparison_by_type.items())
            )
            lines.append(f"By type: {breakdown}")

        lines.append("")
        if comparison_total > 0:
            delta = total - comparison_total
            pct = (delta / comparison_total) * 100
            direction = "increase" if delta > 0 else "decrease" if delta < 0 else "no change"
            lines.append(
                f"**Delta:** {delta:+d} vessels ({pct:+.1f}% {direction})"
            )
        elif total > 0:
            lines.append(f"**Delta:** +{total} vessels (no vessels in comparison period)")
        else:
            lines.append("**Delta:** No vessels in either period.")

    return "\n".join(lines)


@tool
async def search_vessels(
    bbox: list[float],
    date_from: str,
    date_to: str,
) -> str:
    """Search for vessel traffic (ships, boats) in an area between two dates.

    Uses Global Fishing Watch data combining satellite SAR imagery and AIS
    transponder signals. Detects vessels >25m in length.

    Args:
        bbox: Bounding box [west, south, east, north] in WGS84 degrees.
        date_from: Start date in YYYY-MM-DD format.
        date_to: End date in YYYY-MM-DD format.
    """
    settings = get_settings()
    if not settings.gfw_api_key:
        return "Error: GFW_API_KEY not configured. Cannot query vessel data."

    try:
        result = await search_vessels_in_aoi(
            bbox=bbox,
            date_from=date_from,
            date_to=date_to,
            api_key=settings.gfw_api_key,
        )
    except Exception as exc:
        return f"Error querying vessel data: {exc}"

    return format_vessel_summary(
        total=result.total_count,
        by_type=result.by_type,
        date_from=date_from,
        date_to=date_to,
    )


@tool
async def compare_vessel_traffic(
    bbox: list[float],
    period_a_from: str,
    period_a_to: str,
    period_b_from: str,
    period_b_to: str,
) -> str:
    """Compare vessel traffic between two time periods in the same area.

    Returns vessel counts and type breakdowns for both periods, plus the delta.

    Args:
        bbox: Bounding box [west, south, east, north] in WGS84 degrees.
        period_a_from: Start date of first period (YYYY-MM-DD).
        period_a_to: End date of first period (YYYY-MM-DD).
        period_b_from: Start date of second period (YYYY-MM-DD).
        period_b_to: End date of second period (YYYY-MM-DD).
    """
    settings = get_settings()
    if not settings.gfw_api_key:
        return "Error: GFW_API_KEY not configured. Cannot query vessel data."

    try:
        result_a = await search_vessels_in_aoi(
            bbox=bbox,
            date_from=period_a_from,
            date_to=period_a_to,
            api_key=settings.gfw_api_key,
        )
        result_b = await search_vessels_in_aoi(
            bbox=bbox,
            date_from=period_b_from,
            date_to=period_b_to,
            api_key=settings.gfw_api_key,
        )
    except Exception as exc:
        return f"Error querying vessel data: {exc}"

    return format_vessel_summary(
        total=result_b.total_count,
        by_type=result_b.by_type,
        date_from=period_b_from,
        date_to=period_b_to,
        comparison_total=result_a.total_count,
        comparison_by_type=result_a.by_type,
        comparison_date_from=period_a_from,
        comparison_date_to=period_a_to,
    )
```

- [ ] **Step 4: Add GFW API key to config**

In `backend/app/config.py`, add to the `Settings` class:

```python
    gfw_api_key: str = ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/agent/tools/test_search_vessels.py -v`

Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/tools/search_vessels.py backend/tests/agent/tools/test_search_vessels.py backend/app/config.py
git commit -m "feat: add vessel traffic search and comparison agent tools"
```

---

## Task 8: Road Traffic Service (TomTom)

**Files:**
- Create: `backend/app/services/traffic.py`
- Create: `backend/tests/services/test_traffic.py`

- [ ] **Step 1: Write failing tests for traffic service**

`backend/tests/services/test_traffic.py`:

```python
import httpx
import pytest
import respx
from app.services.traffic import (
    TomTomClient,
    TrafficSegment,
    search_traffic_in_aoi,
    TrafficSearchResult,
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
    @respx.mock
    @pytest.mark.asyncio
    async def test_flow_returns_segment(self) -> None:
        respx.get("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json").mock(
            return_value=httpx.Response(200, json=MOCK_FLOW_RESPONSE)
        )
        client = TomTomClient(api_key="test-key")
        segment = await client.get_flow_segment(lat=52.01, lon=4.35)
        assert segment.current_speed == 45
        assert segment.free_flow_speed == 60

    @respx.mock
    @pytest.mark.asyncio
    async def test_flow_handles_error(self) -> None:
        respx.get("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        client = TomTomClient(api_key="bad-key")
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_flow_segment(lat=52.01, lon=4.35)


class TestSearchTrafficInAoi:
    @respx.mock
    @pytest.mark.asyncio
    async def test_samples_grid_points(self, sample_bbox: list[float]) -> None:
        respx.get("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json").mock(
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/services/test_traffic.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.traffic'`

- [ ] **Step 3: Implement traffic service**

`backend/app/services/traffic.py`:

```python
from dataclasses import dataclass

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
    """Async client for TomTom Traffic Flow API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def get_flow_segment(self, lat: float, lon: float, zoom: int = 10) -> TrafficSegment:
        """Get traffic flow data for the road segment nearest to a point."""
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
    """Generate a grid of sample points within a bbox.

    Returns (lat, lon) tuples distributed across the AOI.
    """
    west, south, east, north = bbox
    import math

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
    """Sample traffic flow at grid points across an AOI and aggregate."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/services/test_traffic.py -v`

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/traffic.py backend/tests/services/test_traffic.py
git commit -m "feat: add TomTom traffic flow service with grid sampling"
```

---

## Task 9: Road Traffic Agent Tools

**Files:**
- Create: `backend/app/agent/tools/search_traffic.py`
- Create: `backend/tests/agent/tools/test_search_traffic.py`

- [ ] **Step 1: Write failing tests for traffic tools**

`backend/tests/agent/tools/test_search_traffic.py`:

```python
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
        assert "33" in result  # percentage
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
        assert "worse" in result.lower() or "increase" in result.lower() or "slower" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/agent/tools/test_search_traffic.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement traffic tools**

`backend/app/agent/tools/search_traffic.py`:

```python
from langchain_core.tools import tool

from app.config import get_settings
from app.services.traffic import search_traffic_in_aoi


def format_traffic_summary(
    avg_speed: float,
    avg_free_flow: float,
    congestion_ratio: float,
    segments_sampled: int,
    comparison_avg_speed: float | None = None,
    comparison_congestion_ratio: float | None = None,
) -> str:
    """Format traffic data as a readable summary."""
    if segments_sampled == 0:
        return "No road traffic data available for this area. The area may not have major roads covered by TomTom."

    pct = congestion_ratio * 100
    lines = [
        f"**Traffic summary** ({segments_sampled} road segments sampled):",
        f"- Average current speed: {avg_speed:.0f} km/h",
        f"- Average free-flow speed: {avg_free_flow:.0f} km/h",
        f"- Congestion level: {pct:.0f}% slower than free flow",
    ]

    if comparison_avg_speed is not None and comparison_congestion_ratio is not None:
        comp_pct = comparison_congestion_ratio * 100
        lines.append("")
        lines.append(f"**Comparison period:**")
        lines.append(f"- Average speed was: {comparison_avg_speed:.0f} km/h")
        lines.append(f"- Congestion was: {comp_pct:.0f}% slower than free flow")
        lines.append("")

        speed_delta = avg_speed - comparison_avg_speed
        if speed_delta < -2:
            lines.append(f"**Delta:** Traffic is slower by {abs(speed_delta):.0f} km/h (congestion increase)")
        elif speed_delta > 2:
            lines.append(f"**Delta:** Traffic is faster by {speed_delta:.0f} km/h (congestion decrease)")
        else:
            lines.append("**Delta:** Traffic conditions are roughly the same.")

    return "\n".join(lines)


@tool
async def search_traffic(
    bbox: list[float],
) -> str:
    """Get current road traffic congestion in an area.

    Samples traffic flow across a grid of points in the AOI and reports
    average speed, free-flow speed, and congestion level. Uses TomTom
    Traffic data. Provides relative congestion, not absolute vehicle counts.

    Args:
        bbox: Bounding box [west, south, east, north] in WGS84 degrees.
    """
    settings = get_settings()
    if not settings.tomtom_api_key:
        return "Error: TOMTOM_API_KEY not configured. Cannot query traffic data."

    try:
        result = await search_traffic_in_aoi(
            bbox=bbox,
            api_key=settings.tomtom_api_key,
        )
    except Exception as exc:
        return f"Error querying traffic data: {exc}"

    return format_traffic_summary(
        avg_speed=result.avg_speed,
        avg_free_flow=result.avg_free_flow_speed,
        congestion_ratio=result.congestion_ratio,
        segments_sampled=result.segments_sampled,
    )


@tool
async def compare_traffic(
    bbox: list[float],
) -> str:
    """Compare current road traffic against typical free-flow conditions.

    Provides congestion analysis showing how much slower current traffic
    is compared to normal conditions. For historical comparison between
    specific dates, use search_traffic at different times.

    Note: TomTom free tier provides real-time data only. Historical
    date-specific queries require a paid plan.

    Args:
        bbox: Bounding box [west, south, east, north] in WGS84 degrees.
    """
    settings = get_settings()
    if not settings.tomtom_api_key:
        return "Error: TOMTOM_API_KEY not configured. Cannot query traffic data."

    try:
        result = await search_traffic_in_aoi(
            bbox=bbox,
            api_key=settings.tomtom_api_key,
        )
    except Exception as exc:
        return f"Error querying traffic data: {exc}"

    return format_traffic_summary(
        avg_speed=result.avg_speed,
        avg_free_flow=result.avg_free_flow_speed,
        congestion_ratio=result.congestion_ratio,
        segments_sampled=result.segments_sampled,
    )
```

- [ ] **Step 4: Add TomTom API key to config**

In `backend/app/config.py`, add to the `Settings` class:

```python
    tomtom_api_key: str = ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/agent/tools/test_search_traffic.py -v`

Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/tools/search_traffic.py backend/tests/agent/tools/test_search_traffic.py backend/app/config.py
git commit -m "feat: add road traffic search and comparison agent tools"
```

---

## Task 10: Agent Integration (Tools, Prompt, State)

**Files:**
- Modify: `backend/app/agent/tools/__init__.py`
- Modify: `backend/app/agent/prompts.py`
- Modify: `backend/app/agent/state.py`

- [ ] **Step 1: Register new tools in __init__.py**

Read the current `backend/app/agent/tools/__init__.py` to see how tools are collected. It should have an `ALL_TOOLS` list. Add the new tools:

```python
from app.agent.tools.search_vessels import search_vessels, compare_vessel_traffic
from app.agent.tools.search_traffic import search_traffic, compare_traffic
```

And append them to `ALL_TOOLS`:

```python
ALL_TOOLS = [
    search_imagery,
    download_imagery,
    download_imagery_batch,
    compute_index,
    analyze_image,
    compare_images,
    # Vessel traffic
    search_vessels,
    compare_vessel_traffic,
    # Road traffic
    search_traffic,
    compare_traffic,
]
```

- [ ] **Step 2: Update agent state for multi-source results**

In `backend/app/agent/state.py`, add new result accumulator fields:

```python
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    aoi_geojson: dict | None
    imagery_results: Annotated[list, operator.add]
    vessel_results: Annotated[list, operator.add]
    traffic_results: Annotated[list, operator.add]
```

- [ ] **Step 3: Update system prompt for multi-source routing**

In `backend/app/agent/prompts.py`, replace the `SYSTEM_PROMPT` with an updated version that includes the new intelligence types. Add these sections after the existing satellite imagery tool descriptions:

```python
# Add after the existing tool descriptions in SYSTEM_PROMPT:

VESSEL_TOOLS_PROMPT = """
## Vessel Traffic Tools

You can query maritime vessel traffic data from Global Fishing Watch (satellite SAR + AIS transponders).

- `search_vessels` — Search for vessel detections in a bounding box and date range. Returns vessel count and type breakdown (fishing, cargo, tanker, etc.). Detects vessels >25m.
- `compare_vessel_traffic` — Compare vessel counts between two time periods in the same area. Returns counts, type breakdowns, and the delta.

Use these tools when the user asks about ships, boats, vessel traffic, port activity, maritime activity, or fishing activity.
"""

TRAFFIC_TOOLS_PROMPT = """
## Road Traffic Tools

You can query road traffic congestion data from TomTom.

- `search_traffic` — Get current traffic congestion in an area. Samples road segments and reports average speed, free-flow speed, and congestion level.
- `compare_traffic` — Compare current traffic against free-flow conditions.

IMPORTANT: This provides relative congestion data (speed vs free-flow), NOT absolute vehicle counts. Be transparent about this with the user. If they ask for exact vehicle counts, explain that only government traffic sensor stations provide those, and coverage is limited to fixed locations.

Use these tools when the user asks about traffic, road congestion, commute times, or highway conditions.
"""

ROUTING_PROMPT = """
## Data Source Routing

Based on the user's question, decide which tools to use:

- **Land, vegetation, water, environmental change** → Satellite imagery tools (search_imagery, download_imagery, compute_index, etc.)
- **Ships, boats, port activity, maritime traffic** → Vessel traffic tools (search_vessels, compare_vessel_traffic)
- **Road traffic, congestion, highway conditions** → Road traffic tools (search_traffic, compare_traffic)
- **Mixed questions** → Use multiple tool types as needed

When doing temporal comparisons, always compare exactly 2 dates/periods. Select the best dates based on data quality (low cloud cover for optical imagery, sufficient coverage for vessel/traffic data).
"""
```

Then update the main `SYSTEM_PROMPT` string to include these new sections by appending them.

- [ ] **Step 4: Run all tests**

Run: `cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/tools/__init__.py backend/app/agent/prompts.py backend/app/agent/state.py
git commit -m "feat: integrate vessel and traffic tools into agent graph"
```

---

## Task 11: Update Environment Configuration

**Files:**
- Modify: `backend/.env.example` (or project root `.env.example`)

- [ ] **Step 1: Add new API keys to .env.example**

Append to the `.env.example` file:

```bash
# Global Fishing Watch (free — register at globalfishingwatch.org)
GFW_API_KEY=

# TomTom Traffic (free tier — register at developer.tomtom.com)
TOMTOM_API_KEY=
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: add GFW and TomTom API keys to env template"
```

---

## Task 12: Frontend — New Tool Status Labels

**Files:**
- Modify: `frontend/src/components/ToolStatusCard.tsx`

- [ ] **Step 1: Add tool name mappings**

In `frontend/src/components/ToolStatusCard.tsx`, find the object or switch that maps tool names to display labels (e.g., `search_imagery` → `"Searching for satellite imagery"`). Add:

```typescript
search_vessels: "Searching for vessel traffic",
compare_vessel_traffic: "Comparing vessel traffic between periods",
search_traffic: "Checking road traffic conditions",
compare_traffic: "Comparing road traffic conditions",
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ToolStatusCard.tsx
git commit -m "feat: add tool status labels for vessel and traffic tools"
```

---

## Task 13: Frontend — Render Non-Imagery Results

**Files:**
- Modify: `frontend/src/components/MessageBubble.tsx`

- [ ] **Step 1: Ensure Markdown tables render correctly**

The vessel and traffic tools return Markdown-formatted text with tables and bold headings. The existing `MessageBubble.tsx` uses `react-markdown` with `remark-gfm` (GitHub Flavored Markdown), which already supports tables. Verify this works by checking that `remarkGfm` is imported and passed as a plugin.

If GFM tables are already supported (they should be based on the existing code), no changes needed. The agent's Markdown responses will render the vessel/traffic summaries correctly as-is.

- [ ] **Step 2: Run frontend build to verify no errors**

Run: `cd /home/laurenz/satellite_imagery_analyzer/frontend && npm run build`

Expected: Build succeeds with no errors

- [ ] **Step 3: Commit (if changes were needed)**

```bash
git add frontend/src/components/MessageBubble.tsx
git commit -m "feat: ensure Markdown table rendering for vessel/traffic results"
```

---

## Task 14: Update product.md and Documentation

**Files:**
- Modify: `product.md` (already done during brainstorming)

- [ ] **Step 1: Verify product.md is up to date**

Read `product.md` and confirm it matches the implemented features. It should already reflect the multi-source pivot from the brainstorming session.

- [ ] **Step 2: Final commit**

```bash
git add product.md
git commit -m "docs: update product spec for multi-source geospatial intelligence"
```

---

## Run Full Test Suite

After all tasks:

```bash
cd /home/laurenz/satellite_imagery_analyzer/backend && python -m pytest tests/ -v --tb=short
```

Expected: All tests pass. Coverage should be ≥80% for new code.
