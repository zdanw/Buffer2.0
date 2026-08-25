import logging

logger = logging.getLogger(__name__)

import base64
import re
from PIL import Image
import imagehash
import requests
import time
from io import BytesIO

_DOWNLOAD_HEADERS = {
    "User-Agent": "BebcareBuffer/2.0 (+cdn-persist)",
    "Accept": "image/*,*/*;q=0.8",
}


def _retry_request(func, max_retries=3, initial_delay=2.0, backoff_factor=2.0):
    """带指数退避的通用重试函数"""
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            logger.warning(
                "Attempt %s/%s failed: %s...",
                attempt + 1,
                max_retries,
                str(e)[:100],
            )

            if attempt < max_retries - 1:
                logger.info("Retrying in %.2f seconds...", delay)
                time.sleep(delay)
                delay *= backoff_factor

    logger.error(
        "All %s attempts failed. Last error: %s", max_retries, str(last_exception)[:200]
    )
    raise last_exception


def _open_image_bytes(raw: bytes) -> Image.Image:
    image = Image.open(BytesIO(raw))
    image.load()
    return image


def download_image_bytes(url: str) -> bytes:
    """Download raw image bytes from http(s) or data: URL."""
    if isinstance(url, str) and url.startswith("data:"):
        match = re.match(
            r"^data:image/[\w.+-]+;base64,(.*)$", url, flags=re.IGNORECASE | re.DOTALL
        )
        if not match:
            raise ValueError("Unsupported data URL for image")
        return base64.b64decode(match.group(1))

    def download_func():
        response = requests.get(url, timeout=60, headers=_DOWNLOAD_HEADERS)
        response.raise_for_status()
        if not response.content:
            raise ValueError("Empty image response body")
        return response.content

    return _retry_request(download_func, max_retries=3, initial_delay=2.0)


def image_to_jpeg_bytes(image: Image.Image, quality: int = 92) -> bytes:
    """Convert any PIL mode to JPEG bytes (handles RGBA/P/LA)."""
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        rgb = background
    elif image.mode != "RGB":
        rgb = image.convert("RGB")
    else:
        rgb = image

    buffer = BytesIO()
    rgb.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def calculate_phash(image):
    if isinstance(image, str):
        image = download_image(image)

    phash = imagehash.phash(image)
    return str(phash)


def hamming_distance(hash1, hash2):
    if len(hash1) != len(hash2):
        return float("inf")
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))


def get_image_dimensions(image):
    if isinstance(image, str):
        image = download_image(image)

    return image.size


def download_image(url):
    return _open_image_bytes(download_image_bytes(url))


def is_github_cdn_url(image_url) -> bool:
    """Return True if the URL is already on our GitHub/jsDelivr CDN."""
    return bool(image_url and "cdn.jsdelivr.net" in str(image_url))


def any_non_cdn_image(images) -> bool:
    """True when any non-empty image URL is not yet on GitHub CDN."""
    return any(url and not is_github_cdn_url(url) for url in (images or []))


def _source_label(image_url: str) -> str:
    """Short, log-safe description of an image source (never dump full data URLs)."""
    if not image_url:
        return "<empty>"
    if image_url.startswith("data:"):
        header = image_url.split(",", 1)[0]
        return f"data_url({header}; len={len(image_url)})"
    if is_github_cdn_url(image_url):
        return f"cdn({image_url[:120]})"
    return f"http({image_url[:160]})"


def composite_brand_logo_on_image(
    base_image: Image.Image,
    logo_url: str,
    *,
    max_width_ratio: float = 0.18,
    padding_ratio: float = 0.03,
) -> Image.Image:
    """Overlay brand logo on bottom-right; preserves logo aspect ratio and transparency."""
    logo = download_image(logo_url).convert("RGBA")
    base = base_image.convert("RGBA")
    canvas_w, canvas_h = base.size
    max_logo_w = max(1, int(canvas_w * max_width_ratio))
    logo_w, logo_h = logo.size
    scale = min(1.0, max_logo_w / logo_w) if logo_w else 1.0
    new_w = max(1, int(logo_w * scale))
    new_h = max(1, int(logo_h * scale))
    if (new_w, new_h) != logo.size:
        logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)

    pad = max(4, int(min(canvas_w, canvas_h) * padding_ratio))
    x = canvas_w - new_w - pad
    y = canvas_h - new_h - pad
    base.alpha_composite(logo, (x, y))
    return base


def composite_brand_logo_bytes(image_url: str, logo_url: str) -> bytes:
    """Download generated image, overlay logo, return JPEG bytes."""
    base = _open_image_bytes(download_image_bytes(image_url))
    composited = composite_brand_logo_on_image(base, logo_url)
    return image_to_jpeg_bytes(composited)


def persist_image_url_to_cdn(image_url, file_name=None, logo_url: str | None = None):
    """Download a remote image, optionally composite brand logo, upload to GitHub CDN."""
    from bebcare.utils.github_uploader import github_uploader
    from datetime import datetime

    if is_github_cdn_url(image_url) and not logo_url:
        logger.info("[CDN] skip persist, already on CDN: %s", _source_label(image_url))
        return image_url

    if not image_url:
        raise ValueError("image_url is empty")

    if not file_name:
        file_name = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    elif not str(file_name).lower().endswith((".jpg", ".jpeg")):
        stem = str(file_name).rsplit(".", 1)[0]
        file_name = f"{stem}.jpg"

    src = _source_label(image_url)
    logger.info("[CDN] persist start source=%s file_name=%s composite=%s", src, file_name, bool(logo_url))
    try:
        if logo_url:
            jpeg_bytes = composite_brand_logo_bytes(image_url, logo_url)
        else:
            raw = download_image_bytes(image_url)
            image = _open_image_bytes(raw)
            jpeg_bytes = image_to_jpeg_bytes(image)
        cdn_url = github_uploader.upload_file(jpeg_bytes, file_name)
        logger.info("[CDN] persist ok file_name=%s cdn_url=%s", file_name, cdn_url)
        return cdn_url
    except Exception:
        logger.exception("[CDN] persist failed source=%s file_name=%s", src, file_name)
        raise


def calculate_average_color(image):
    if isinstance(image, str):
        image = download_image(image)
    image = image.resize((1, 1)).convert("RGB")
    r, g, b = image.getpixel((0, 0))
    return (r / 255, g / 255, b / 255)


def get_color_temperature(avg_color):
    r, g, b = avg_color
    if r > g and r > b:
        return "warm"
    elif b > g and b > r:
        return "cool"
    else:
        return "neutral"
