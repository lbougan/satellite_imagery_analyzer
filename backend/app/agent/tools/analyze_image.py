"""Tool: visual analysis of satellite imagery using Claude Vision."""

import io
import os
import base64
import logging
from langchain_core.tools import tool
from anthropic import Anthropic
from PIL import Image
from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_VISION_DIM = 2048
JPEG_QUALITY = 70


def _compress_for_vision(filepath: str) -> tuple[str, str]:
    """Load an image and return (base64_data, media_type) compressed for API use.

    Resizes to MAX_VISION_DIM on the longest side and re-encodes as JPEG,
    typically shrinking file size by 80-95%.
    """
    img = Image.open(filepath)
    if img.mode != "RGB":
        img = img.convert("RGB")

    if max(img.size) > MAX_VISION_DIM:
        ratio = MAX_VISION_DIM / max(img.size)
        img = img.resize(
            (int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS
        )

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    raw_kb = os.path.getsize(filepath) / 1024
    compressed_kb = buf.tell() / 1024
    logger.info(
        "Vision compress %s: %.0f KB -> %.0f KB (%.0f%% reduction)",
        os.path.basename(filepath), raw_kb, compressed_kb,
        (1 - compressed_kb / raw_kb) * 100 if raw_kb else 0,
    )
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"


@tool
def analyze_image(image_filename: str, question: str) -> str:
    """Analyze a satellite image visually using AI vision capabilities.

    Args:
        image_filename: Filename of a previously generated image (e.g. 'scene_id_rgb.jpg').
        question: The analysis question (e.g. 'How many ships are visible?',
                  'What land cover types are present?', 'Is there flood damage?').

    Returns:
        A detailed visual analysis answering the question.
    """
    settings = get_settings()
    filepath = os.path.join(settings.imagery_cache_dir, image_filename)

    if not os.path.exists(filepath):
        return f"Error: Image file '{image_filename}' not found. Generate it first using download_imagery or compute_index."

    image_data, media_type = _compress_for_vision(filepath)

    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"You are analyzing a satellite image (Sentinel-2). {question}\n\n"
                            "Write your analysis as flowing prose in short paragraphs, not as a bulleted list. "
                            "Start by directly addressing the question, then describe the key features you observe "
                            "and what they tell us. Use complete sentences and a conversational, expert tone. "
                            "Avoid bold-label-colon patterns like '**Feature**: description' — instead weave "
                            "details naturally into your narrative."
                        ),
                    },
                ],
            }
        ],
    )
    return response.content[0].text
