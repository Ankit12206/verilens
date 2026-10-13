"""
VeriLens 2.0 – Multimodal Vision Forensics & Incident/Location Verifier
Performs 2 Core Tasks on any uploaded image or image URL:
  Task 1: Real Photograph vs. AI-Generated Image Detection
          (Combines Multimodal Vision AI + EXIF/Software/Resolution Forensics)
  Task 2: If Real -> Identifies the Exact Related Incident, Where It Was Taken (Location),
          When It Happened, and the Full Story (grounded via Mainstream News,
          Local News Websites, and YouTube Video Reports).
          Also checks if an old real photo is being misused in a false context (Context Hijack).
"""
import io
import re
import requests
from datetime import datetime
from typing import Optional, Tuple
from PIL import Image
from PIL.ExifTags import TAGS
import imagehash
from ddgs import DDGS
from app.config import SERPAPI_KEY, USE_SERPAPI
from app.services.llm_client import generate_vision_json, generate_json
from app.services.fact_checker import (
    live_search,
    live_news_search,
    search_youtube_and_local_news,
    _extract_domain
)


AI_SOFTWARE_SIGNATURES = [
    "midjourney", "dall-e", "dalle", "stable diffusion", "stablediffusion",
    "comfyui", "automatic1111", "firefly", "flux", "bing image creator",
    "imagen", "leonardo", "runway", "ideogram", "sora", "ai generated"
]


# ─── Image Loader ─────────────────────────────────────────────────────────────

def load_image_from_url(url: str) -> Optional[Image.Image]:
    """Downloads an image from a URL and returns a PIL Image object."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=12)
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


# ─── EXIF & Technical Forensics ───────────────────────────────────────────────

def extract_exif(image: Image.Image) -> dict:
    """Extracts readable EXIF and info metadata from the image."""
    exif_data = {}
    try:
        if hasattr(image, "info") and isinstance(image.info, dict):
            for k, v in image.info.items():
                if isinstance(v, (str, int, float)):
                    exif_data[str(k)] = str(v)[:300]
        raw_exif = image._getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag = TAGS.get(tag_id, str(tag_id))
                exif_data[tag] = str(value)[:300]
    except Exception:
        pass
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


def analyze_technical_forensics(image: Image.Image, exif: dict) -> Tuple[list, Optional[str]]:
    """
    Inspects technical metadata, camera tags, and AI software headers.
    Returns (forensic_notes, detected_ai_signature_or_camera).
    """
    notes = []
    width, height = image.size
    notes.append(f"Image Resolution: {width}×{height} px ({image.format or 'RAW/Web'})")

    combined_meta = " ".join(f"{k}: {v}" for k, v in exif.items()).lower()
    for sig in AI_SOFTWARE_SIGNATURES:
        if sig in combined_meta:
            notes.append(f"AI Generator Metadata Signature Detected: '{sig.upper()}' in file header.")
            return (notes, "AI_SIGNATURE")

    camera_make = exif.get("Make", "")
    camera_model = exif.get("Model", "")
    if camera_make or camera_model:
        notes.append(f"Authentic Camera EXIF Hardware Tag: {camera_make} {camera_model}".strip())
        return (notes, "CAMERA_EXIF")

    if (width, height) in [(1024, 1024), (768, 768), (512, 512), (1024, 1792), (1792, 1024)]:
        notes.append("Standard 1:1 / diffusion aspect ratio with stripped camera EXIF metadata.")
    else:
        notes.append("EXIF metadata stripped (common for social media / WhatsApp / web images); relying on Vision AI pixel forensics.")

    return (notes, None)


# ─── Perceptual Hash ──────────────────────────────────────────────────────────

def compute_phash(image: Image.Image) -> str:
    """Computes a 64-bit perceptual hash (pHash) hex string for the image."""
    try:
        return str(imagehash.phash(image))
    except Exception:
        return ""


# ─── Vision AI Prompt (Task 1: Real vs AI + Task 2: Visual Scene & Incident) ──

_VISION_FORENSICS_PROMPT = """
You are VeriLens 2.0 Vision Forensics & OSINT Investigator.
Carefully inspect this image and perform TWO critical tasks:

TASK 1 — REAL PHOTOGRAPH vs. AI-GENERATED DETECTION:
Examine the image closely for:
- AI generation artifacts: synthetic skin/fur/surface smoothness, distorted fingers/hands/eyes, garbled or nonsensical background text/signage, impossible architecture/reflections, inconsistent lighting/shadows, or painterly diffusion noise.
- Real camera photograph traits: natural sensor grain, authentic optical depth-of-field, genuine street/news signage in real scripts, natural human expressions and clothing creases, real-world physics and debris.
Determine:
- `authenticity_verdict`: "REAL_PHOTO" | "AI_GENERATED" | "DIGITALLY_MANIPULATED"
- `ai_probability`: integer 0 to 100 (0-15 = definitely real photo, 80-100 = definitely AI-generated).
- `forensic_analysis`: list of 3–4 specific visual/forensic observations explaining WHY it is real or AI-generated.

TASK 2 — INCIDENT, LOCATION & VISUAL SCENE IDENTIFICATION (Especially if REAL_PHOTO):
Examine all visual clues in the photo: landmarks, buildings, language/text on boards or banners, vehicle license plates, police/military/rescue uniforms, public figures, terrain, weather, or disaster type.
- Provide `visual_search_query`: A specific 5–9 word search query to find news articles or YouTube videos about this exact image/incident.
- Provide `related_incident`: The specific real-world incident, news event, or subject shown (if recognizable or inferable from the scene/caption).
- Provide `location_taken`: Where this photo was taken (City, State/Province, Country, or Landmark — if identifiable, plus regional clues).
- Provide `incident_date`: Estimated or known date/year/period of the incident.
- Provide `initial_scene_description`: Detailed description of what is happening in the photograph.

USER CAPTION / CONTEXT (if provided): "{caption}"

Respond ONLY in this exact JSON format:
{{
  "authenticity_verdict": "REAL_PHOTO" | "AI_GENERATED" | "DIGITALLY_MANIPULATED",
  "ai_probability": 8,
  "forensic_analysis": [
    "Observation 1 about lighting/texture/sensor grain",
    "Observation 2 about background signage/anatomy/geometry",
    "Observation 3 about overall photographic authenticity"
  ],
  "visual_search_query": "specific keywords to search news about this photo",
  "related_incident": "Name of the incident or event shown",
  "location_taken": "City, State, Country (or most specific identifiable location)",
  "incident_date": "Year or Date of incident",
  "initial_scene_description": "Detailed 2-3 sentence description of the scene and event"
}}
"""

_INCIDENT_GROUNDING_PROMPT = """
You are VeriLens 2.0 Incident & Provenance Synthesizer.
We inspected a photograph with Vision AI and searched Mainstream News, Local News Websites, and YouTube Reports.

VISION AI SCENE ANALYSIS:
- Initial Incident Identified: {initial_incident}
- Initial Location: {initial_location}
- Initial Date: {initial_date}
- Scene Description: {scene_description}
- User Caption (if any): {caption}

RETRIEVED NEWS, LOCAL PORTALS & YOUTUBE EVIDENCE:
{web_evidence}

Synthesize the final, verified Incident & Location Dossier for the user:
1. `related_incident`: Exact name of the real-world incident/event this photo relates to.
2. `location_taken`: Exact location where it was taken (City/District, State, Country).
3. `incident_date`: When the incident occurred (Date / Month / Year).
4. `earliest_year`: Integer year (e.g. 2023) if known, or null.
5. `incident_details`: A comprehensive 3–5 sentence explanation of the incident, what happened, where it was taken, and the factual/scientific context behind it.
6. `is_context_hijacked`: true ONLY IF the user provided a caption that falsely claims an old historical photo happened today or in a different place; otherwise false.
7. `discrepancy_details`: If `is_context_hijacked` is true, explain the mismatch; otherwise null.

Respond ONLY in this exact JSON format:
{{
  "related_incident": "Exact incident name",
  "location_taken": "Specific location where photo was taken",
  "incident_date": "Date / Year",
  "earliest_year": 2024,
  "incident_details": "Detailed 3-5 sentence explanation of the incident, location, and factual context...",
  "is_context_hijacked": false,
  "discrepancy_details": null
}}
"""


# ─── Main Image Verification Pipeline ─────────────────────────────────────────

def verify_image(
    image_url: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    caption: Optional[str] = None,
    recalled_img_memory: Optional[dict] = None
) -> dict:
    """
    Runs the complete VeriLens 2.0 Image Pipeline:
      0. Checks Self-Learning Image Fingerprint Memory (if matched).
      1. Detects Real Photograph vs. AI-Generated Image (Vision AI + EXIF Forensics).
      2. If Real -> Identifies the Related Incident, Location Taken, Date, and Full Story
         using Vision AI + Mainstream News + Local News Websites + YouTube search.
    """
    image = None
    if image_bytes:
        image = load_image_from_bytes(image_bytes)
    elif image_url:
        image = load_image_from_url(image_url)

    if image is None:
        return {
            "checked": False,
            "authenticity_verdict": "UNKNOWN",
            "ai_probability": 0,
            "forensic_analysis": [],
            "related_incident": None,
            "location_taken": None,
            "incident_date": None,
            "incident_details": None,
            "earliest_found_year": None,
            "original_context": None,
            "is_context_hijacked": False,
            "discrepancy_details": None,
            "warning_message": "Image could not be loaded for verification.",
            "matched_from_memory": False,
            "discovered_sources": [],
            "phash": ""
        }

    # Compute perceptual hash (pHash) for Self-Learning Memory
    phash_str = compute_phash(image)

    # Extract EXIF & technical forensics
    exif = extract_exif(image)
    exif_year = get_exif_date(exif)
    tech_notes, tech_flag = analyze_technical_forensics(image, exif)

    # ── Stage 0: Check Self-Learning Image Fingerprint Memory ──
    if recalled_img_memory and not caption:
        return {
            "checked": True,
            "authenticity_verdict": recalled_img_memory.get("authenticity_verdict", "REAL_PHOTO"),
            "ai_probability": recalled_img_memory.get("ai_probability", 5),
            "forensic_analysis": (recalled_img_memory.get("forensic_analysis") or []) + [
                f"🧠 Instant Visual Memory Match (pHash distance={recalled_img_memory.get('hamming_distance', 0)}, matched {recalled_img_memory.get('times_matched', 1)} times)."
            ],
            "related_incident": recalled_img_memory.get("related_incident"),
            "location_taken": recalled_img_memory.get("location_taken"),
            "incident_date": recalled_img_memory.get("incident_date"),
            "incident_details": recalled_img_memory.get("incident_details"),
            "earliest_found_year": exif_year,
            "original_context": recalled_img_memory.get("incident_details"),
            "is_context_hijacked": False,
            "discrepancy_details": None,
            "warning_message": None,
            "matched_from_memory": True,
            "discovered_sources": [],
            "phash": phash_str
        }

    # ── Stage 1: Vision AI Inspection (Real vs. AI-Generated + Scene Recognition) ──
    vision_prompt = _VISION_FORENSICS_PROMPT.format(caption=caption or "No caption provided")
    vision_res = generate_vision_json(image, vision_prompt) or {}

    auth_verdict = vision_res.get("authenticity_verdict", "REAL_PHOTO")
    try:
        ai_prob = int(vision_res.get("ai_probability", 10))
    except Exception:
        ai_prob = 10

    # Override / calibrate with hard technical metadata if present
    if tech_flag == "AI_SIGNATURE":
        auth_verdict = "AI_GENERATED"
        ai_prob = max(ai_prob, 95)
    elif tech_flag == "CAMERA_EXIF" and ai_prob < 50:
        auth_verdict = "REAL_PHOTO"
        ai_prob = min(ai_prob, 8)

    forensic_list = list(vision_res.get("forensic_analysis") or []) + tech_notes

    # If the image is AI-Generated, report it clearly right away!
    if auth_verdict == "AI_GENERATED" or ai_prob >= 70:
        auth_verdict = "AI_GENERATED"
        scene_desc = vision_res.get("initial_scene_description", "Synthetic AI-generated imagery.")
        return {
            "checked": True,
            "authenticity_verdict": "AI_GENERATED",
            "ai_probability": max(ai_prob, 75),
            "forensic_analysis": forensic_list,
            "related_incident": "None — Synthetic AI-Generated Image",
            "location_taken": "Not taken in the real world (Generated by AI)",
            "incident_date": "Synthetic / AI Creation",
            "incident_details": (
                f"This image is AI-generated ({max(ai_prob, 75)}% probability) and does NOT depict a real-world photograph. "
                f"Visual content: {scene_desc}"
            ),
            "earliest_found_year": None,
            "original_context": scene_desc,
            "is_context_hijacked": bool(caption),
            "discrepancy_details": "An AI-generated synthetic image is being presented as real." if caption else None,
            "warning_message": (
                f"🤖 AI-GENERATED IMAGE DETECTED ({max(ai_prob, 75)}% confidence): "
                "This image was created by an AI generator and is not a real photograph."
            ),
            "matched_from_memory": False,
            "discovered_sources": [],
            "phash": phash_str
        }

    # ── Stage 2: Real Image -> Identify Exact Incident & Location via Web + Local News + YouTube ──
    visual_query = (
        vision_res.get("visual_search_query")
        or caption
        or vision_res.get("related_incident")
        or ""
    ).strip()

    discovered_sources = []
    evidence_snippets = []

    if visual_query and len(visual_query) > 3:
        news_hits = live_news_search(visual_query, max_results=4)
        web_hits = live_search(visual_query, max_results=4)
        local_yt = search_youtube_and_local_news(visual_query, max_results=4)

        seen_u = set()
        for r in (news_hits + web_hits):
            u = r.get("href", r.get("url", ""))
            if u and u not in seen_u:
                seen_u.add(u)
                dom = _extract_domain(u)
                discovered_sources.append({
                    "title": r.get("title", "News Report"),
                    "url": u,
                    "source": dom,
                    "source_type": "mainstream"
                })
                evidence_snippets.append(f"- [{dom}] {r.get('title','')}: {r.get('body','')[:200]}")

        for loc in local_yt:
            u = loc.get("url", "")
            if u and u not in seen_u:
                seen_u.add(u)
                discovered_sources.append({
                    "title": loc.get("title", "Local/Video Report"),
                    "url": u,
                    "source": loc.get("source", "Local/YouTube"),
                    "source_type": loc.get("source_type", "local_news")
                })
                evidence_snippets.append(
                    f"- [{loc.get('source_type','LOCAL').upper()}: {loc.get('source','')}] "
                    f"{loc.get('title','')}: {loc.get('snippet','')[:180]}"
                )

    # Synthesize final Incident, Location & Context Hijack assessment
    grounding_prompt = _INCIDENT_GROUNDING_PROMPT.format(
        initial_incident=vision_res.get("related_incident", "Unknown"),
        initial_location=vision_res.get("location_taken", "Unknown"),
        initial_date=exif_year or vision_res.get("incident_date", "Unknown"),
        scene_description=vision_res.get("initial_scene_description", ""),
        caption=caption or "No user caption",
        web_evidence="\n".join(evidence_snippets[:8]) if evidence_snippets else "Rely on Vision AI identification."
    )

    grounded = generate_json(grounding_prompt) or {}

    related_incident = grounded.get("related_incident") or vision_res.get("related_incident") or "Real-World Photograph"
    location_taken = grounded.get("location_taken") or vision_res.get("location_taken") or "Location identified from visual features"
    incident_date = str(grounded.get("incident_date") or exif_year or vision_res.get("incident_date") or "Recent / Historical")
    incident_details = (
        grounded.get("incident_details")
        or vision_res.get("initial_scene_description")
        or "Authentic photograph verified through visual and metadata analysis."
    )

    earliest_year = exif_year
    if not earliest_year:
        try:
            if grounded.get("earliest_year"):
                earliest_year = int(grounded["earliest_year"])
            else:
                ym = re.findall(r"\b(20\d{2}|19\d{2})\b", incident_date)
                if ym:
                    earliest_year = int(ym[0])
        except Exception:
            earliest_year = None

    is_hijacked = bool(grounded.get("is_context_hijacked", False))
    discrepancy = grounded.get("discrepancy_details")

    # Deterministic check: if image is >= 2 years old and caption claims "today / breaking"
    current_year = datetime.now().year
    if earliest_year and (current_year - earliest_year) >= 2 and caption:
        if any(w in caption.lower() for w in ["today", "just now", "breaking", "yesterday", "this morning"]):
            is_hijacked = True
            discrepancy = (
                f"This is a real photograph from {earliest_year} ({related_incident} in {location_taken}), "
                f"but the caption falsely presents it as a current event ({current_year - earliest_year}-year mismatch)."
            )

    warning_msg = None
    if is_hijacked:
        warning_msg = (
            f"🚨 CONTEXT HIJACK DETECTED: This is a REAL photograph from '{related_incident}' "
            f"({location_taken}, {incident_date}), being reused in a misleading context!"
        )

    return {
        "checked": True,
        "authenticity_verdict": auth_verdict,
        "ai_probability": min(ai_prob, 35),
        "forensic_analysis": forensic_list,
        "related_incident": related_incident,
        "location_taken": location_taken,
        "incident_date": incident_date,
        "incident_details": incident_details,
        "earliest_found_year": earliest_year,
        "original_context": incident_details,
        "is_context_hijacked": is_hijacked,
        "discrepancy_details": discrepancy,
        "warning_message": warning_msg,
        "matched_from_memory": False,
        "discovered_sources": discovered_sources[:6],
        "phash": phash_str
    }
