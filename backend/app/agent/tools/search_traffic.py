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
        lines.append("**Comparison period:**")
        lines.append(f"- Average speed was: {comparison_avg_speed:.0f} km/h")
        lines.append(f"- Congestion was: {comp_pct:.0f}% slower than free flow")
        lines.append("")
        speed_delta = avg_speed - comparison_avg_speed
        if speed_delta < -2:
            lines.append(
                f"**Delta:** Traffic is slower by {abs(speed_delta):.0f} km/h (congestion increase)"
            )
        elif speed_delta > 2:
            lines.append(
                f"**Delta:** Traffic is faster by {speed_delta:.0f} km/h (congestion decrease)"
            )
        else:
            lines.append("**Delta:** Traffic conditions are roughly the same.")
    return "\n".join(lines)


@tool
async def search_traffic(bbox: list[float]) -> str:
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
        result = await search_traffic_in_aoi(bbox=bbox, api_key=settings.tomtom_api_key)
    except Exception as exc:
        return f"Error querying traffic data: {exc}"
    return format_traffic_summary(
        avg_speed=result.avg_speed,
        avg_free_flow=result.avg_free_flow_speed,
        congestion_ratio=result.congestion_ratio,
        segments_sampled=result.segments_sampled,
    )


@tool
async def compare_traffic(bbox: list[float]) -> str:
    """Compare current road traffic against typical free-flow conditions.

    Note: TomTom free tier provides real-time data only. Historical
    date-specific queries require a paid plan.

    Args:
        bbox: Bounding box [west, south, east, north] in WGS84 degrees.
    """
    settings = get_settings()
    if not settings.tomtom_api_key:
        return "Error: TOMTOM_API_KEY not configured. Cannot query traffic data."
    try:
        result = await search_traffic_in_aoi(bbox=bbox, api_key=settings.tomtom_api_key)
    except Exception as exc:
        return f"Error querying traffic data: {exc}"
    return format_traffic_summary(
        avg_speed=result.avg_speed,
        avg_free_flow=result.avg_free_flow_speed,
        congestion_ratio=result.congestion_ratio,
        segments_sampled=result.segments_sampled,
    )
