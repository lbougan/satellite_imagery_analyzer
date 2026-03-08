"""Raster processing: download COGs, compute spectral indices, generate PNGs."""

import os
import json
import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)

_download_semaphore = threading.Semaphore(16)

GDAL_COG_ENV = {
    "GDAL_HTTP_MULTIPLEX": "YES",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "50000000",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "1",
    "GDAL_HTTP_VERSION": "2",
}


def _cache_path(name: str) -> str:
    settings = get_settings()
    os.makedirs(settings.imagery_cache_dir, exist_ok=True)
    return os.path.join(settings.imagery_cache_dir, name)


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _bbox_suffix(bbox: list[float] | None) -> str:
    """Short hash of bbox for cache-busting when AOI changes."""
    if not bbox:
        return "full"
    return hashlib.md5(str(bbox).encode()).hexdigest()[:8]


def download_band(
    url: str,
    scene_id: str,
    band: str,
    bbox: list[float] | None = None,
    max_size: int | None = None,
) -> str:
    """Download a single band from a COG URL, optionally clipped to a WGS84 bbox.

    When a bbox [west, south, east, north] is provided, only the pixels within
    that extent are fetched from the remote COG — dramatically reducing download
    size and time compared to reading the full Sentinel-2 tile.

    When max_size is set, the longest pixel dimension is capped to that value,
    reading from COG overviews for a massive speed-up.

    Acquires a global semaphore to prevent too many concurrent COG reads
    (protects against parallel tool calls from the LLM agent).
    """
    suffix = _bbox_suffix(bbox)
    res_tag = f"_{max_size}px" if max_size else ""
    filename = f"{scene_id}_{band}_{suffix}{res_tag}.tif"
    local_path = _cache_path(filename)
    if os.path.exists(local_path):
        return local_path

    _download_semaphore.acquire()
    try:
        if os.path.exists(local_path):
            return local_path

        with rasterio.Env(**GDAL_COG_ENV):
            with rasterio.open(url) as src:
                if bbox:
                    src_bounds = transform_bounds("EPSG:4326", src.crs, *bbox)
                    window = from_bounds(*src_bounds, transform=src.transform)
                    window = window.intersection(
                        rasterio.windows.Window(0, 0, src.width, src.height)
                    )
                    win_h, win_w = int(window.height), int(window.width)

                    out_shape = None
                    if max_size and max(win_h, win_w) > max_size:
                        scale = max_size / max(win_h, win_w)
                        out_shape = (src.count, max(1, int(win_h * scale)), max(1, int(win_w * scale)))

                    data = src.read(
                        window=window,
                        out_shape=out_shape,
                        resampling=Resampling.bilinear,
                    )
                    win_transform = rasterio.windows.transform(window, src.transform)
                    if out_shape:
                        win_transform = win_transform * win_transform.scale(
                            win_w / out_shape[2], win_h / out_shape[1]
                        )
                    profile = src.profile.copy()
                    profile.update(
                        driver="GTiff",
                        compress="zstd",
                        zstd_level=3,
                        height=data.shape[1],
                        width=data.shape[2],
                        transform=win_transform,
                    )
                else:
                    out_shape = None
                    if max_size and max(src.height, src.width) > max_size:
                        scale = max_size / max(src.height, src.width)
                        out_shape = (src.count, max(1, int(src.height * scale)), max(1, int(src.width * scale)))

                    data = src.read(
                        out_shape=out_shape,
                        resampling=Resampling.bilinear,
                    )
                    profile = src.profile.copy()
                    profile.update(driver="GTiff", compress="zstd", zstd_level=3)
                    if out_shape:
                        profile.update(
                            height=data.shape[1],
                            width=data.shape[2],
                            transform=src.transform * src.transform.scale(
                                src.width / out_shape[2], src.height / out_shape[1]
                            ),
                        )

                with rasterio.open(local_path, "w", **profile) as dst:
                    dst.write(data)
    finally:
        _download_semaphore.release()

    return local_path


def download_bands_parallel(
    band_urls: dict[str, str],
    scene_id: str,
    bbox: list[float] | None = None,
    max_workers: int = 6,
    max_size: int | None = None,
) -> dict[str, str]:
    """Download multiple bands concurrently using a thread pool.

    Args:
        band_urls: Mapping of band name to signed COG URL.
        scene_id: Scene identifier for cache filenames.
        bbox: Optional WGS84 bounding box to clip downloads.
        max_workers: Max parallel download threads.
        max_size: Optional pixel cap on longest dimension (uses COG overviews).

    Returns:
        Mapping of band name to local file path.
    """
    downloaded: dict[str, str] = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=min(max_workers, len(band_urls))) as pool:
        futures = {
            pool.submit(download_band, url, scene_id, band, bbox, max_size): band
            for band, url in band_urls.items()
        }
        for future in as_completed(futures):
            band = futures[future]
            try:
                downloaded[band] = future.result()
            except Exception as exc:
                logger.error("Failed to download band %s: %s", band, exc)
                errors.append(f"{band}: {exc}")

    if errors:
        raise RuntimeError(
            f"Failed to download {len(errors)} band(s): " + "; ".join(errors)
        )

    return downloaded


def _save_bounds_metadata(png_path: str, reference_tiff_path: str) -> None:
    """Save WGS84 bounds as a sidecar JSON alongside a generated PNG."""
    with rasterio.open(reference_tiff_path) as src:
        bounds = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
    bounds_path = png_path + ".bounds.json"
    with open(bounds_path, "w") as f:
        json.dump({"bounds": list(bounds)}, f)


def compute_ndvi(nir_path: str, red_path: str, scene_id: str) -> tuple[str, dict]:
    """Compute NDVI from NIR (B08) and Red (B04) bands. Returns (png_path, stats)."""
    with rasterio.open(nir_path) as nir_src, rasterio.open(red_path) as red_src:
        nir = nir_src.read(1).astype(np.float32)
        red = red_src.read(1).astype(np.float32)

    denominator = nir + red
    ndvi = np.where(denominator > 0, (nir - red) / denominator, 0)
    ndvi = np.clip(ndvi, -1, 1)

    stats = {
        "min": float(np.nanmin(ndvi)),
        "max": float(np.nanmax(ndvi)),
        "mean": float(np.nanmean(ndvi)),
        "std": float(np.nanstd(ndvi)),
    }

    png_path = _cache_path(f"{scene_id}_ndvi.png")
    _ndvi_to_png(ndvi, png_path)
    _save_bounds_metadata(png_path, nir_path)
    return png_path, stats


def compute_ndwi(green_path: str, nir_path: str, scene_id: str) -> tuple[str, dict]:
    """Compute NDWI from Green (B03) and NIR (B08) bands."""
    with rasterio.open(green_path) as green_src, rasterio.open(nir_path) as nir_src:
        green = green_src.read(1).astype(np.float32)
        nir = nir_src.read(1).astype(np.float32)

    denominator = green + nir
    ndwi = np.where(denominator > 0, (green - nir) / denominator, 0)
    ndwi = np.clip(ndwi, -1, 1)

    stats = {
        "min": float(np.nanmin(ndwi)),
        "max": float(np.nanmax(ndwi)),
        "mean": float(np.nanmean(ndwi)),
        "std": float(np.nanstd(ndwi)),
    }

    png_path = _cache_path(f"{scene_id}_ndwi.png")
    _index_to_png(ndwi, png_path, cmap_name="RdYlBu")
    _save_bounds_metadata(png_path, green_path)
    return png_path, stats


def compute_nbr(nir_path: str, swir_path: str, scene_id: str) -> tuple[str, dict]:
    """Compute NBR from NIR (B08) and SWIR (B12) bands."""
    with rasterio.open(nir_path) as nir_src, rasterio.open(swir_path) as swir_src:
        nir = nir_src.read(1).astype(np.float32)
        swir = swir_src.read(1).astype(np.float32)

    denominator = nir + swir
    nbr = np.where(denominator > 0, (nir - swir) / denominator, 0)
    nbr = np.clip(nbr, -1, 1)

    stats = {
        "min": float(np.nanmin(nbr)),
        "max": float(np.nanmax(nbr)),
        "mean": float(np.nanmean(nbr)),
        "std": float(np.nanstd(nbr)),
    }

    png_path = _cache_path(f"{scene_id}_nbr.png")
    _index_to_png(nbr, png_path, cmap_name="RdYlGn")
    _save_bounds_metadata(png_path, nir_path)
    return png_path, stats


def make_rgb_preview(red_path: str, green_path: str, blue_path: str, scene_id: str) -> str:
    """Create a true-color RGB JPEG preview from B04, B03, B02 bands."""
    with rasterio.open(red_path) as r, rasterio.open(green_path) as g, rasterio.open(blue_path) as b:
        red = r.read(1).astype(np.float32)
        green = g.read(1).astype(np.float32)
        blue = b.read(1).astype(np.float32)

    def _normalize(band: np.ndarray) -> np.ndarray:
        p2, p98 = np.percentile(band[band > 0], (2, 98)) if np.any(band > 0) else (0, 1)
        if p98 <= p2:
            return np.zeros_like(band, dtype=np.uint8)
        return np.clip((band - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)

    rgb = np.stack([_normalize(red), _normalize(green), _normalize(blue)], axis=-1)
    img = Image.fromarray(rgb)

    max_dim = 2048
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

    jpg_path = _cache_path(f"{scene_id}_rgb.jpg")
    img.save(jpg_path, "JPEG", quality=85, optimize=True)
    _save_bounds_metadata(jpg_path, red_path)
    return jpg_path


def _ndvi_to_png(ndvi: np.ndarray, path: str) -> None:
    """NDVI colormap using a proper RdYlGn-style diverging palette with RGBA transparency."""
    _STOPS = np.array([
        [-1.0, 165,   0,  38],
        [-0.5, 215,  48,  39],
        [-0.2, 244, 109,  67],
        [ 0.0, 255, 255, 191],
        [ 0.1, 217, 239, 139],
        [ 0.2, 166, 217, 106],
        [ 0.4,  26, 152,  80],
        [ 0.6,   0, 104,  55],
        [ 1.0,   0,  69,  41],
    ], dtype=np.float64)

    vals = _STOPS[:, 0]
    r_lut = np.interp(np.linspace(-1, 1, 256), vals, _STOPS[:, 1]).astype(np.uint8)
    g_lut = np.interp(np.linspace(-1, 1, 256), vals, _STOPS[:, 2]).astype(np.uint8)
    b_lut = np.interp(np.linspace(-1, 1, 256), vals, _STOPS[:, 3]).astype(np.uint8)

    idx = np.clip(((ndvi + 1) / 2 * 255), 0, 255).astype(np.uint8)
    alpha = np.full_like(idx, 140, dtype=np.uint8)
    rgba = np.stack([r_lut[idx], g_lut[idx], b_lut[idx], alpha], axis=-1)
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True, compress_level=6)


def _index_to_png(data: np.ndarray, path: str, cmap_name: str = "RdYlBu") -> None:
    """Generic index to PNG with a simple diverging colormap."""
    normalized = ((data + 1) / 2 * 255).astype(np.uint8)
    Image.fromarray(normalized, mode="L").save(path, optimize=True, compress_level=6)
