import os
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.config import get_settings

router = APIRouter(prefix="/imagery", tags=["imagery"])


@router.get("/bounds/{filename}")
async def get_imagery_bounds(filename: str):
    """Return WGS84 bounds [west, south, east, north] for a generated PNG."""
    settings = get_settings()
    bounds_path = os.path.join(settings.imagery_cache_dir, filename + ".bounds.json")
    if not os.path.isfile(bounds_path):
        raise HTTPException(status_code=404, detail="Bounds metadata not found for this file")
    with open(bounds_path) as f:
        return json.load(f)


@router.get("/{filename}")
async def serve_imagery(filename: str):
    settings = get_settings()
    filepath = os.path.join(settings.imagery_cache_dir, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Imagery file not found")
    if filename.endswith(".png"):
        media_type = "image/png"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
        media_type = "image/jpeg"
    else:
        media_type = "image/tiff"
    return FileResponse(filepath, media_type=media_type)
