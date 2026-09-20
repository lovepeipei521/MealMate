# app/utils/image_storage.py
"""
Image Storage Utility

Provides utilities for uploading images to external storage services (imgbb).
Extracted from image_generator.py for reuse across the application.
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def upload_to_imgbb(
    image_data: str,
    mime_type: str = "image/jpeg",
) -> Optional[dict]:
    """
    Upload base64 image to imgbb for persistent storage.

    Args:
        image_data: Base64 encoded image data or image URL
        mime_type: MIME type of the image (default: image/jpeg)

    Returns:
        Dict containing {url, display_url, delete_url, thumb_url} on success,
        None on failure
    """
    storage_config = settings.image_storage
    if not storage_config.enabled:
        logger.info("Image storage is disabled, skipping upload")
        return None

    if not storage_config.api_key:
        logger.warning("imgbb API key is not configured, skipping upload")
        return None

    try:
        params = {
            "key": storage_config.api_key,
            "image": image_data,
        }
        if storage_config.expiration:
            params["expiration"] = str(storage_config.expiration)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                storage_config.upload_url,
                data=params,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                return {
                    "url": result["data"]["url"],
                    "display_url": result["data"]["display_url"],
                    "delete_url": result["data"]["delete_url"],
                    "thumb_url": result["data"].get("thumb", {}).get("url"),
                }
            else:
                logger.error(f"imgbb upload failed: {result}")
                return None

    except Exception as e:
        logger.exception(f"Failed to upload image to imgbb: {e}")
        return None


__all__ = ["upload_to_imgbb"]
