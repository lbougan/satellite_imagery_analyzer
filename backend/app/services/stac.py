"""STAC catalog search via Microsoft Planetary Computer."""

import threading
from dataclasses import dataclass
from pystac_client import Client
import planetary_computer as pc


PLANETARY_COMPUTER_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

SENTINEL2_BANDS = {
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B08": "nir",
    "B11": "swir16",
    "B12": "swir22",
    "visual": "true_color",
}

_catalog_lock = threading.Lock()
_catalog_instance: Client | None = None


def _get_catalog() -> Client:
    """Return a cached, thread-safe STAC catalog client."""
    global _catalog_instance
    if _catalog_instance is None:
        with _catalog_lock:
            if _catalog_instance is None:
                _catalog_instance = Client.open(
                    PLANETARY_COMPUTER_URL, modifier=pc.sign_inplace
                )
    return _catalog_instance


@dataclass
class SceneMetadata:
    scene_id: str
    datetime: str
    cloud_cover: float
    bbox: list[float]
    thumbnail_url: str | None
    asset_keys: list[str]


def search_scenes(
    bbox: list[float],
    date_from: str,
    date_to: str,
    max_cloud_cover: float = 20.0,
    max_items: int = 10,
    collection: str = "sentinel-2-l2a",
) -> list[SceneMetadata]:
    """Search Planetary Computer STAC for Sentinel-2 scenes matching criteria."""
    catalog = _get_catalog()

    search = catalog.search(
        collections=[collection],
        bbox=bbox,
        datetime=f"{date_from}/{date_to}",
        query={"eo:cloud_cover": {"lt": max_cloud_cover}},
        max_items=max_items,
        sortby=["-properties.datetime"],
    )

    results = []
    for item in search.items():
        thumb = item.assets.get("rendered_preview") or item.assets.get("thumbnail")
        results.append(
            SceneMetadata(
                scene_id=item.id,
                datetime=item.datetime.isoformat() if item.datetime else "",
                cloud_cover=item.properties.get("eo:cloud_cover", -1),
                bbox=list(item.bbox) if item.bbox else [],
                thumbnail_url=thumb.href if thumb else None,
                asset_keys=list(item.assets.keys()),
            )
        )
    return results


def get_signed_asset_url(scene_id: str, band: str, collection: str = "sentinel-2-l2a") -> str:
    """Get a signed download URL for a specific band of a scene."""
    urls = get_signed_asset_urls(scene_id, [band], collection)
    return urls[band]


def get_signed_asset_urls(
    scene_id: str, bands: list[str], collection: str = "sentinel-2-l2a"
) -> dict[str, str]:
    """Get signed download URLs for multiple bands in a single STAC lookup."""
    catalog = _get_catalog()
    search = catalog.search(
        collections=[collection],
        ids=[scene_id],
    )
    items = list(search.items())
    if not items:
        raise ValueError(f"Scene {scene_id} not found")

    item = items[0]
    urls: dict[str, str] = {}
    available = list(item.assets.keys())
    for band in bands:
        if band not in item.assets:
            raise ValueError(f"Band {band} not found. Available: {available}")
        urls[band] = item.assets[band].href
    return urls


def get_signed_asset_urls_batch(
    scene_ids: list[str],
    bands: list[str],
    collection: str = "sentinel-2-l2a",
) -> dict[str, dict[str, str]]:
    """Get signed URLs for multiple scenes + bands in a single STAC search.

    Returns:
        {scene_id: {band: url, ...}, ...}
    """
    catalog = _get_catalog()
    search = catalog.search(
        collections=[collection],
        ids=scene_ids,
    )
    items_by_id = {item.id: item for item in search.items()}

    missing = set(scene_ids) - items_by_id.keys()
    if missing:
        raise ValueError(f"Scene(s) not found: {', '.join(missing)}")

    result: dict[str, dict[str, str]] = {}
    for scene_id in scene_ids:
        item = items_by_id[scene_id]
        available = list(item.assets.keys())
        urls: dict[str, str] = {}
        for band in bands:
            if band not in item.assets:
                raise ValueError(
                    f"Band {band} not found in {scene_id}. Available: {available}"
                )
            urls[band] = item.assets[band].href
        result[scene_id] = urls
    return result
