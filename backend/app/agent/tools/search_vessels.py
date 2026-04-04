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
    """Format vessel detection results as a Markdown summary."""
    lines = [f"**Vessel detections ({date_from} to {date_to}):** {total} vessels"]
    if by_type:
        breakdown = ", ".join(
            f"{vtype}: {count}" for vtype, count in sorted(by_type.items())
        )
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
                f"{vtype}: {count}"
                for vtype, count in sorted(comparison_by_type.items())
            )
            lines.append(f"By type: {breakdown}")
        lines.append("")
        if comparison_total > 0:
            delta = total - comparison_total
            pct = (delta / comparison_total) * 100
            direction = (
                "increase" if delta > 0 else "decrease" if delta < 0 else "no change"
            )
            lines.append(f"**Delta:** {delta:+d} vessels ({pct:+.1f}% {direction})")
        elif total > 0:
            lines.append(
                f"**Delta:** +{total} vessels (no vessels in comparison period)"
            )
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
