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
