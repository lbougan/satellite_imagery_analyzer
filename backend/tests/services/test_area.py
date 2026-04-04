import pytest
from app.services.area import bbox_area_km2, validate_aoi_area, AreaTooLargeError


class TestBboxAreaKm2:
    def test_small_area(self, sample_bbox: list[float]) -> None:
        area = bbox_area_km2(sample_bbox)
        assert 0.5 < area < 2.0

    def test_large_area(self, large_bbox: list[float]) -> None:
        area = bbox_area_km2(large_bbox)
        assert 100 < area < 2000

    def test_equatorial_area(self) -> None:
        area = bbox_area_km2([0.0, 0.0, 1.0, 1.0])
        assert 10_000 < area < 15_000

    def test_high_latitude_smaller(self) -> None:
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
