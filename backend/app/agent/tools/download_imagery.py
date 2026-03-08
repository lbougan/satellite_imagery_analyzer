"""Tool: download specific bands of a satellite scene (single + batch)."""

import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_core.tools import tool
from app.services.stac import get_signed_asset_urls, get_signed_asset_urls_batch
from app.services.raster import download_bands_parallel, make_rgb_preview

logger = logging.getLogger(__name__)


def _download_one_scene(
    scene_id: str,
    band_urls: dict[str, str],
    bbox: list[float] | None,
    max_size: int | None = None,
) -> tuple[str, dict[str, str], list[str]]:
    """Download bands for a single scene and return (scene_id, downloaded, info_lines)."""
    downloaded = download_bands_parallel(
        band_urls, scene_id, bbox=bbox, max_size=max_size
    )

    lines: list[str] = []
    for band, path in downloaded.items():
        size_mb = os.path.getsize(path) / (1024 * 1024)
        lines.append(f"  - {band}: {os.path.basename(path)} ({size_mb:.1f} MB)")

    color_bands = {"B04", "B03", "B02"}
    if color_bands.issubset(downloaded.keys()):
        rgb_path = make_rgb_preview(
            downloaded["B04"], downloaded["B03"], downloaded["B02"], scene_id
        )
        size_mb = os.path.getsize(rgb_path) / (1024 * 1024)
        lines.append(f"  RGB preview: {os.path.basename(rgb_path)} ({size_mb:.1f} MB)")

    return scene_id, downloaded, lines


@tool
def download_imagery(scene_id: str, bands: list[str], bbox: list[float] | None = None) -> str:
    """Download specific spectral bands for a Sentinel-2 scene.

    Args:
        scene_id: The scene ID from a previous search (e.g. 'S2B_MSIL2A_...').
        bands: List of band names to download. Common bands:
            - B02 (blue), B03 (green), B04 (red), B08 (NIR)
            - B11 (SWIR 1.6um), B12 (SWIR 2.2um)
            - visual (true color composite)
        bbox: Optional bounding box [west, south, east, north] in WGS84 degrees
            to clip the download to the area of interest. STRONGLY RECOMMENDED —
            without this, the entire Sentinel-2 tile (~110 km x 110 km) is downloaded.

    Returns:
        Paths to downloaded files and an RGB preview if color bands were included.
    """
    t0 = time.perf_counter()

    band_urls = get_signed_asset_urls(scene_id, bands)
    _, _, lines = _download_one_scene(scene_id, band_urls, bbox)

    elapsed = time.perf_counter() - t0
    logger.info("download_imagery %s: %.1fs total", scene_id, elapsed)

    return f"Downloaded {len(bands)} bands for {scene_id} ({elapsed:.1f}s):\n" + "\n".join(lines)


@tool
def download_imagery_batch(
    scene_ids: list[str], bands: list[str], bbox: list[float] | None = None
) -> str:
    """Download the same spectral bands for multiple scenes at once.

    This is MUCH faster than calling download_imagery multiple times because it
    fetches all STAC metadata in one request and manages download concurrency
    globally. **Always prefer this tool when downloading bands for 2+ scenes.**

    Args:
        scene_ids: List of scene IDs from a previous search.
        bands: List of band names to download for every scene.
        bbox: Optional bounding box [west, south, east, north] in WGS84 degrees.

    Returns:
        Summary of downloaded files and RGB previews for each scene.
    """
    t0 = time.perf_counter()

    all_urls = get_signed_asset_urls_batch(scene_ids, bands)
    t_urls = time.perf_counter()
    logger.info(
        "download_imagery_batch: %d scenes, STAC lookup %.1fs",
        len(scene_ids), t_urls - t0,
    )

    result_lines: list[str] = []

    with ThreadPoolExecutor(max_workers=min(8, len(scene_ids))) as pool:
        futures = {
            pool.submit(_download_one_scene, sid, all_urls[sid], bbox, 2048): sid
            for sid in scene_ids
        }
        for future in as_completed(futures):
            sid = futures[future]
            try:
                scene_id, downloaded, lines = future.result()
                result_lines.append(f"\n{scene_id} ({len(downloaded)} bands):")
                result_lines.extend(lines)
            except Exception as exc:
                logger.error("Failed scene %s: %s", sid, exc)
                result_lines.append(f"\n{sid}: ERROR - {exc}")

    elapsed = time.perf_counter() - t0
    header = f"Batch download complete: {len(scene_ids)} scenes, {len(bands)} bands each ({elapsed:.1f}s)"
    return header + "\n" + "\n".join(result_lines)
