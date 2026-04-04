"""Tool: search satellite imagery catalogs."""

from datetime import datetime as dt

from langchain_core.tools import tool
from app.services.stac import search_scenes


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

    candidates = sorted_by_cloud[: max(max_scenes * 2, len(sorted_by_cloud))]

    if len(candidates) <= max_scenes:
        return candidates

    selected = [candidates[0]]
    remaining = candidates[1:]

    while len(selected) < max_scenes and remaining:
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

    # Recommend best scenes for comparison
    if len(scenes) > 2:
        best = pick_best_scenes(
            [{"scene_id": s.scene_id, "cloud_cover": s.cloud_cover, "datetime": str(s.datetime)} for s in scenes],
            max_scenes=2,
        )
        best_ids = [s["scene_id"] for s in best]
        lines.append(f"\n**Recommended scenes for comparison** (lowest cloud cover, best temporal spread): {', '.join(best_ids)}")

    return "\n".join(lines)
