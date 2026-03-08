"""Tool: search satellite imagery catalogs."""

from langchain_core.tools import tool
from app.services.stac import search_scenes


@tool
def search_imagery(
    bbox: list[float],
    date_from: str,
    date_to: str,
    max_cloud_cover: float = 20.0,
    max_items: int = 10,
) -> str:
    """Search for Sentinel-2 satellite imagery scenes.

    Args:
        bbox: Bounding box as [west, south, east, north] in WGS84 degrees.
        date_from: Start date in YYYY-MM-DD format.
        date_to: End date in YYYY-MM-DD format.
        max_cloud_cover: Maximum cloud cover percentage (0-100). Default 20.
        max_items: Maximum number of scenes to return. Default 10.

    Returns:
        A summary of matching scenes with IDs, dates, cloud cover, and available bands.
    """
    scenes = search_scenes(
        bbox=bbox,
        date_from=date_from,
        date_to=date_to,
        max_cloud_cover=max_cloud_cover,
        max_items=max_items,
    )
    if not scenes:
        return (
            f"No scenes found for bbox={bbox}, dates={date_from} to {date_to}, "
            f"max_cloud_cover={max_cloud_cover}%. "
            "Try widening the date range or increasing the cloud cover threshold."
        )

    lines = [f"Found {len(scenes)} Sentinel-2 scenes:\n"]
    for s in scenes:
        lines.append(
            f"- **{s.scene_id}** | Date: {s.datetime} | Cloud: {s.cloud_cover:.1f}% | "
            f"Bands: {len(s.asset_keys)} assets"
        )
    return "\n".join(lines)
