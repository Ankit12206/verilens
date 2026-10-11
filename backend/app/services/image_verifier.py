"""
VeriLens – Image Verifier Service
Detects whether an image is being used out-of-context (Context-Hijack detection).
Pipeline:
  1. Download & open image via URL or bytes upload.
  2. Extract EXIF metadata (original date, GPS, camera model).
  3. Compute perceptual hash (pHash) for fingerprinting.
  4. Search the web for the earliest known appearance of the image.
  5. Compare claimed date/location vs. historical provenance.
"""
import io
import re
import requests
from datetime import datetime
from typing import Optional
from PIL import Image
from PIL.ExifTags import TAGS
import imagehash
from ddgs import DDGS
from app.config import SERPAPI_KEY, USE_SERPAPI


# ─── Image Loader ─────────────────────────────────────────────────────────────

def load_image_from_url(url: str) -> Optional[Image.Image]:
    """Downloads an image from a URL and returns a PIL Image object."""
    try:
        headers = {"User-Agent": "VeriLens/1.0 (Fact-Check Tool)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content))
    except Exception as e:
        print(f"[ImageVerifier] Could not load image from URL: {e}")
        return None


def load_image_from_bytes(data: bytes) -> Optional[Image.Image]:
    """Loads a PIL Image from raw bytes (multipart upload)."""
    try:
        return Image.open(io.BytesIO(data))
    except Exception as e:
        print(f"[ImageVerifier] Could not load image from bytes: {e}")
        return None


# ─── EXIF Extraction ──────────────────────────────────────────────────────────

def extract_exif(image: Image.Image) -> dict:
    """
    Extracts readable EXIF metadata from the image.
    Returns a dict with human-readable tag names.
    """
    exif_data = {}
    try:
        raw_exif = image._getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag = TAGS.get(tag_id, str(tag_id))
                exif_data[tag] = str(value)
    except Exception:
        pass  # Image has no EXIF data (common for screenshots or web images)
    return exif_data


def get_exif_date(exif: dict) -> Optional[int]:
    """Parses the original creation year from EXIF DateTimeOriginal or DateTime."""
    for key in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
        if key in exif:
            try:
                year = int(exif[key][:4])
                if 1990 <= year <= datetime.now().year:
                    return year
            except (ValueError, IndexError):
                continue
    return None


# ─── Perceptual Hash ──────────────────────────────────────────────────────────

def compute_phash(image: Image.Image) -> str:
    """Computes a perceptual hash (pHash) string for the image."""
    try:
        return str(imagehash.phash(image))
    except Exception:
        return ""


# ─── Web Reverse Search ───────────────────────────────────────────────────────

def web_reverse_search(image_url: str) -> dict:
    """
    Attempts to find the earliest known context for this image via DuckDuckGo
    image description search or SerpAPI Google Lens (if key is configured).
    Returns dict: { earliest_year, original_context, source_urls }
    """
    if USE_SERPAPI and image_url:
        return _serpapi_reverse(image_url)
    else:
        return _ddg_image_search(image_url)


def _serpapi_reverse(image_url: str) -> dict:
    """Uses SerpAPI Google Lens for accurate reverse image search."""
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_reverse_image",
                "image_url": image_url,
                "api_key": SERPAPI_KEY
            },
            timeout=12
        )
        data = resp.json()
        pages = data.get("image_results", [])
        years = []
        contexts = []
        for p in pages[:5]:
            title = p.get("title", "")
            snippet = p.get("snippet", "")
            combined = title + " " + snippet
            year_match = re.findall(r"\b(20\d{2}|19\d{2})\b", combined)
            if year_match:
                years.extend([int(y) for y in year_match])
            if snippet:
                contexts.append(snippet[:120])

        earliest = min(years) if years else None
        return {
            "earliest_year": earliest,
            "original_context": contexts[0] if contexts else None,
            "source_urls": [p.get("link", "") for p in pages[:3]]
        }
    except Exception as e:
        print(f"[ImageVerifier] SerpAPI error: {e}")
        return {"earliest_year": None, "original_context": None, "source_urls": []}


def _ddg_image_search(image_url: str) -> dict:
    """
    Lightweight reverse context search using DuckDuckGo text search on the image URL.
    This works by searching the URL itself to find pages that have embedded it.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f'"{image_url}" OR image site:reuters.com OR site:apnews.com', max_results=5))
        if not results:
            return {"earliest_year": None, "original_context": None, "source_urls": []}

        years = []
        contexts = []
        for r in results:
            combined = r.get("title", "") + " " + r.get("body", "")
            year_match = re.findall(r"\b(20\d{2}|19\d{2})\b", combined)
            if year_match:
                years.extend([int(y) for y in year_match])
            if r.get("body"):
                contexts.append(r["body"][:120])

        return {
            "earliest_year": min(years) if years else None,
            "original_context": contexts[0] if contexts else None,
            "source_urls": [r.get("href", r.get("url", "")) for r in results[:3]]
        }
    except Exception as e:
        print(f"[ImageVerifier] DDG image search error: {e}")
        return {"earliest_year": None, "original_context": None, "source_urls": []}


# ─── Main Verification Orchestrator ───────────────────────────────────────────

def verify_image(image_url: Optional[str] = None, image_bytes: Optional[bytes] = None, caption: Optional[str] = None) -> dict:
    """
    Full image context-hijack verification pipeline.

    Returns a dict matching the MediaVerification schema:
    {
        checked, earliest_found_year, original_context,
        is_context_hijacked, discrepancy_details, warning_message
    }
    """
    result = {
        "checked": False,
        "earliest_found_year": None,
        "original_context": None,
        "is_context_hijacked": False,
        "discrepancy_details": None,
        "warning_message": None
    }

    # 1. Load image
    image = None
    if image_bytes:
        image = load_image_from_bytes(image_bytes)
    elif image_url:
        image = load_image_from_url(image_url)

    if not image:
        result["warning_message"] = "Could not load image for analysis."
        return result

    result["checked"] = True

    # 2. Extract EXIF metadata
    exif = extract_exif(image)
    exif_year = get_exif_date(exif)

    # 3. Compute perceptual hash
    phash = compute_phash(image)

    # 4. Web reverse search (only works well with image URLs)
    reverse_data = {"earliest_year": None, "original_context": None, "source_urls": []}
    if image_url:
        reverse_data = web_reverse_search(image_url)

    # 5. Determine earliest known year
    years = [y for y in [exif_year, reverse_data.get("earliest_year")] if y]
    earliest_year = min(years) if years else None
    current_year = datetime.now().year

    result["earliest_found_year"] = earliest_year
    result["original_context"] = reverse_data.get("original_context")

    # 6. Context-Hijack Detection Logic
    if earliest_year and (current_year - earliest_year) >= 2:
        # Check if caption claims this is recent/breaking
        if caption:
            breaking_keywords = [
                "today", "breaking", "now", "just", "this morning",
                "yesterday", "latest", "hours ago", "minutes ago",
                str(current_year), str(current_year - 1)
            ]
            caption_lower = caption.lower()
            is_claimed_recent = any(kw in caption_lower for kw in breaking_keywords)

            if is_claimed_recent:
                result["is_context_hijacked"] = True
                result["discrepancy_details"] = (
                    f"Image appears to date from {earliest_year}, but the caption "
                    f"implies it is from {current_year} or very recently."
                )
                result["warning_message"] = (
                    f"⚠️ CONTEXT HIJACK DETECTED: This image was first found online "
                    f"around {earliest_year} but is being presented as breaking/recent news."
                )
            else:
                # Old image, not claiming to be new — low risk
                result["discrepancy_details"] = (
                    f"Image dates from approximately {earliest_year}. "
                    f"No explicit recency claims detected in caption."
                )
        else:
            # No caption — flag as potentially suspicious if image is old
            if (current_year - earliest_year) >= 3:
                result["warning_message"] = (
                    f"ℹ️ NOTE: This image appears to originate from around {earliest_year}. "
                    f"Verify whether it is being used in the correct context."
                )

    elif earliest_year is None and not exif_year:
        result["warning_message"] = "Could not determine image origin date. Manual verification recommended."

    return result
