"""Tool: compare satellite imagery from two dates for change detection."""

import os
import glob as globmod
import numpy as np
import rasterio
from PIL import Image
from langchain_core.tools import tool
from app.config import get_settings
from app.services.raster import _save_bounds_metadata


def _find_band(cache_dir: str, scene_id: str, band: str) -> str | None:
    pattern = os.path.join(cache_dir, f"{scene_id}_{band}_*.tif")
    matches = sorted(globmod.glob(pattern), key=os.path.getmtime, reverse=True)
    return matches[0] if matches else None


@tool
def compare_images(
    scene_id_1: str,
    scene_id_2: str,
    index_type: str = "ndvi",
) -> str:
    """Compare two satellite scenes to detect changes over time.

    Args:
        scene_id_1: First (earlier) scene ID. Index must already be computed.
        scene_id_2: Second (later) scene ID. Index must already be computed.
        index_type: Which spectral index to compare. One of 'ndvi', 'ndwi', 'nbr'.

    Returns:
        Change statistics and a difference visualization filename.
    """
    settings = get_settings()
    index_type = index_type.lower().strip()

    def _load_index(scene_id: str) -> np.ndarray | None:
        if index_type == "ndvi":
            nir_p = _find_band(settings.imagery_cache_dir, scene_id, "B08")
            red_p = _find_band(settings.imagery_cache_dir, scene_id, "B04")
            if not nir_p or not red_p:
                return None
            with rasterio.open(nir_p) as s1, rasterio.open(red_p) as s2:
                nir = s1.read(1).astype(np.float32)
                red = s2.read(1).astype(np.float32)
            denom = nir + red
            return np.where(denom > 0, (nir - red) / denom, 0)

        elif index_type == "ndwi":
            green_p = _find_band(settings.imagery_cache_dir, scene_id, "B03")
            nir_p = _find_band(settings.imagery_cache_dir, scene_id, "B08")
            if not green_p or not nir_p:
                return None
            with rasterio.open(green_p) as s1, rasterio.open(nir_p) as s2:
                green = s1.read(1).astype(np.float32)
                nir = s2.read(1).astype(np.float32)
            denom = green + nir
            return np.where(denom > 0, (green - nir) / denom, 0)

        elif index_type == "nbr":
            nir_p = _find_band(settings.imagery_cache_dir, scene_id, "B08")
            swir_p = _find_band(settings.imagery_cache_dir, scene_id, "B12")
            if not nir_p or not swir_p:
                return None
            with rasterio.open(nir_p) as s1, rasterio.open(swir_p) as s2:
                nir = s1.read(1).astype(np.float32)
                swir = s2.read(1).astype(np.float32)
            denom = nir + swir
            return np.where(denom > 0, (nir - swir) / denom, 0)

        return None

    idx1 = _load_index(scene_id_1)
    idx2 = _load_index(scene_id_2)

    if idx1 is None:
        return f"Error: Could not compute {index_type.upper()} for {scene_id_1}. Download the required bands first."
    if idx2 is None:
        return f"Error: Could not compute {index_type.upper()} for {scene_id_2}. Download the required bands first."

    min_h = min(idx1.shape[0], idx2.shape[0])
    min_w = min(idx1.shape[1], idx2.shape[1])
    idx1 = idx1[:min_h, :min_w]
    idx2 = idx2[:min_h, :min_w]

    diff = idx2 - idx1

    stats = {
        "mean_change": float(np.nanmean(diff)),
        "max_increase": float(np.nanmax(diff)),
        "max_decrease": float(np.nanmin(diff)),
        "std_change": float(np.nanstd(diff)),
        "pct_increased": float(np.sum(diff > 0.1) / diff.size * 100),
        "pct_decreased": float(np.sum(diff < -0.1) / diff.size * 100),
    }

    diff_normalized = np.clip((diff + 1) / 2 * 255, 0, 255).astype(np.uint8)
    diff_filename = f"diff_{index_type}_{scene_id_1[:20]}_{scene_id_2[:20]}.png"
    diff_path = os.path.join(settings.imagery_cache_dir, diff_filename)
    Image.fromarray(diff_normalized, mode="L").save(diff_path)

    ref_band = _find_band(settings.imagery_cache_dir, scene_id_1, "B08") or \
               _find_band(settings.imagery_cache_dir, scene_id_1, "B04") or \
               _find_band(settings.imagery_cache_dir, scene_id_1, "B03")
    if ref_band:
        _save_bounds_metadata(diff_path, ref_band)

    return (
        f"{index_type.upper()} change detection: {scene_id_1} → {scene_id_2}\n"
        f"  Mean change: {stats['mean_change']:+.4f}\n"
        f"  Max increase: {stats['max_increase']:+.4f}\n"
        f"  Max decrease: {stats['max_decrease']:+.4f}\n"
        f"  Std dev: {stats['std_change']:.4f}\n"
        f"  Pixels with significant increase (>0.1): {stats['pct_increased']:.1f}%\n"
        f"  Pixels with significant decrease (<-0.1): {stats['pct_decreased']:.1f}%\n"
        f"  Difference visualization: {diff_filename}"
    )
