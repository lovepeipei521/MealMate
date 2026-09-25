"""Proxy generated and uploaded images through the application origin.

Only image URLs hosted by ImgBB are accepted. This avoids browser-side
third-party image blocking while keeping the proxy narrowly scoped.
"""

import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_IMAGE_HOSTS = frozenset({"i.ibb.co", "ibb.co"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def _is_allowed_image_url(raw_url: str) -> bool:
    """Return whether the URL is an HTTPS ImgBB image URL."""
    try:
        parsed = urlparse(raw_url)
    except ValueError:
        return False

    return parsed.scheme == "https" and parsed.hostname in ALLOWED_IMAGE_HOSTS


@router.get("/image-proxy")
async def proxy_image(
    url: str = Query(..., min_length=12, max_length=2048),
):
    """Fetch an allowed remote image and return it from the API origin."""
    if not _is_allowed_image_url(url):
        raise HTTPException(status_code=400, detail="不支持的图片来源")

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=False,
        ) as client:
            async with client.stream(
                "GET",
                url,
                headers={
                    "User-Agent": "MealMate/1.0",
                    "Referer": "https://i.ibb.co/",
                },
            ) as upstream:
                upstream.raise_for_status()

                content_type = (
                    upstream.headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if not content_type.startswith("image/"):
                    raise HTTPException(status_code=502, detail="远端资源不是图片")

                chunks: list[bytes] = []
                total = 0
                async for chunk in upstream.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_IMAGE_BYTES:
                        raise HTTPException(status_code=413, detail="图片过大")
                    chunks.append(chunk)

                return Response(
                    content=b"".join(chunks),
                    media_type=content_type,
                    headers={
                        "Cache-Control": "public, max-age=86400",
                        "X-Content-Type-Options": "nosniff",
                    },
                )
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        logger.warning("Image proxy upstream error: %s", exc)
        raise HTTPException(status_code=502, detail="图片源返回错误")
    except httpx.RequestError as exc:
        logger.warning("Image proxy request failed: %s", exc)
        raise HTTPException(status_code=502, detail="无法获取图片")


__all__ = ["router"]