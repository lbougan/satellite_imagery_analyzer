"""Tool: compute spectral indices from downloaded bands."""

import os
import glob as globmod
from langchain_core.tools import tool
from app.services.raster import compute_ndvi, compute_ndwi, compute_nbr
from app.config import get_settings


def _band_path(scene_id: str, band: str) -> str | None:
    settings = get_settings()
    pattern = os.path.join(settings.imagery_cache_dir, f"{scene_id}_{band}_*.tif")
    matches = sorted(globmod.glob(pattern), key=os.path.getmtime, reverse=True)
    return matches[0] if matches else None


@tool
def compute_index(scene_id: str, index_type: str) -> str:
    """Compute a spectral index from previously downloaded bands.

    Args:
        scene_id: The scene ID (bands must already be downloaded).
        index_type: One of 'ndvi', 'ndwi', or 'nbr'.
            - NDVI (vegetation): requires B04 (red) and B08 (NIR)
            - NDWI (water): requires B03 (green) and B08 (NIR)
            - NBR (burn severity): requires B08 (NIR) and B12 (SWIR)

    Returns:
        Statistics (min, max, mean, std) and the filename of the generated visualization.
    """
    index_type = index_type.lower().strip()

    if index_type == "ndvi":
        nir_path = _band_path(scene_id, "B08")
        red_path = _band_path(scene_id, "B04")
        if not nir_path or not red_path:
            return "Error: B08 (NIR) and B04 (Red) must be downloaded first. Use download_imagery."
        png_path, stats = compute_ndvi(nir_path, red_path, scene_id)

    elif index_type == "ndwi":
        green_path = _band_path(scene_id, "B03")
        nir_path = _band_path(scene_id, "B08")
        if not green_path or not nir_path:
            return "Error: B03 (Green) and B08 (NIR) must be downloaded first. Use download_imagery."
        png_path, stats = compute_ndwi(green_path, nir_path, scene_id)

    elif index_type == "nbr":
        nir_path = _band_path(scene_id, "B08")
        swir_path = _band_path(scene_id, "B12")
        if not nir_path or not swir_path:
            return "Error: B08 (NIR) and B12 (SWIR) must be downloaded first. Use download_imagery."
        png_path, stats = compute_nbr(nir_path, swir_path, scene_id)

    else:
        return f"Unknown index type '{index_type}'. Supported: ndvi, ndwi, nbr."

    filename = os.path.basename(png_path)
    return (
        f"{index_type.upper()} computed for {scene_id}:\n"
        f"  Min: {stats['min']:.4f}\n"
        f"  Max: {stats['max']:.4f}\n"
        f"  Mean: {stats['mean']:.4f}\n"
        f"  Std Dev: {stats['std']:.4f}\n"
        f"  Visualization: {filename}"
    )
