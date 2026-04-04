import math


class AreaTooLargeError(Exception):
    def __init__(self, area_km2: float, limit_km2: float) -> None:
        self.area_km2 = area_km2
        self.limit_km2 = limit_km2
        super().__init__(
            f"Area of interest is {area_km2:.0f} km², which exceeds the "
            f"maximum of {limit_km2:.0f} km². Please draw a smaller area."
        )


def bbox_area_km2(bbox: list[float]) -> float:
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
