"""
VeriLens 2.0 – Unified Multi-Model AI & Vision Client
Provides automatic rotation across multiple Gemini models and OpenRouter models
so VeriLens never hits a single-model rate limit and supports both:
  1. Deep Text / News / Scientific Reasoning (JSON output)
  2. Multimodal Vision Image Forensics & Incident Recognition (PIL Image + Prompt)
"""
import base64
import io
import json
import re
import requests
from typing import Optional, Tuple
from PIL import Image
from app.config import (
    GEMINI_API_KEY, USE_GEMINI,
    OPENROUTER_API_KEY, USE_OPENROUTER
)

if USE_GEMINI:
    from google import genai as _genai_lib
    _gemini_client = _genai_lib.Client(api_key=GEMINI_API_KEY)
else:
    _gemini_client = None

# Ordered rotation of active Gemini models (each has its own independent quota bucket)
GEMINI_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]

OPENROUTER_TEXT_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "openrouter/free",
]

OPENROUTER_VISION_MODELS = [
    "google/gemma-3-27b-it:free",
    "qwen/qwen2.5-vl-32b-instruct:free",
    "openrouter/free",
]


def _extract_json_dict(raw_text: str) -> Optional[dict]:
    """Robustly extracts a JSON object from LLM text output."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # Try finding outermost {...}
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None


def call_gemini_json(prompt: str) -> Tuple[Optional[dict], Optional[str]]:
    """Tries Gemini models in rotation until one succeeds and returns parsed JSON."""
    if not (USE_GEMINI and _gemini_client):
        return (None, None)

    for model_name in GEMINI_MODELS:
        try:
            resp = _gemini_client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            parsed = _extract_json_dict(resp.text)
            if parsed is not None:
                return (parsed, model_name)
        except Exception as e:
            err_str = str(e)
            print(f"[LLMClient] Gemini ({model_name}) notice: {err_str[:110]}")
            continue
    return (None, None)


def call_openrouter_json(prompt: str) -> Tuple[Optional[dict], Optional[str]]:
    """Tries OpenRouter models in rotation and returns parsed JSON."""
    if not USE_OPENROUTER:
        return (None, None)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://verilens.onrender.com",
        "X-Title": "VeriLens 2.0",
        "Content-Type": "application/json"
    }

    for model_name in OPENROUTER_TEXT_MODELS:
        try:
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are VeriLens, an elite investigative fact-checker and scientific analyst. Respond ONLY with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.15
            }
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=18
            )
            if resp.status_code == 200:
                data = resp.json()
                raw = data["choices"][0]["message"]["content"]
                parsed = _extract_json_dict(raw)
                if parsed is not None:
                    return (parsed, model_name)
        except Exception as e:
            print(f"[LLMClient] OpenRouter ({model_name}) notice: {str(e)[:100]}")
            continue
    return (None, None)


def generate_json(prompt: str) -> Optional[dict]:
    """
    Primary entry point for structured JSON generation.
    Uses Gemini model rotation first, then seamlessly fails over to OpenRouter.
    """
    res, _ = call_gemini_json(prompt)
    if res is not None:
        return res

    res, _ = call_openrouter_json(prompt)
    if res is not None:
        return res

    return None


def generate_vision_json(image: Image.Image, prompt: str) -> Optional[dict]:
    """
    Multimodal Vision entry point: analyzes an actual PIL Image + prompt.
    Uses Gemini Vision rotation first, then OpenRouter Vision models.
    """
    # Normalize image size & RGB mode so upload is fast and compatible
    img_rgb = image.convert("RGB")
    img_rgb.thumbnail((1024, 1024))

    # 1. Try Gemini Vision models in rotation
    if USE_GEMINI and _gemini_client:
        for model_name in GEMINI_MODELS:
            try:
                resp = _gemini_client.models.generate_content(
                    model=model_name,
                    contents=[img_rgb, prompt]
                )
                parsed = _extract_json_dict(resp.text)
                if parsed is not None:
                    return parsed
            except Exception as e:
                print(f"[LLMClient] Gemini Vision ({model_name}) notice: {str(e)[:110]}")
                continue

    # 2. Failover to OpenRouter Vision models (base64 data URI)
    if USE_OPENROUTER:
        buf = io.BytesIO()
        img_rgb.save(buf, format="JPEG", quality=85)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{b64_str}"

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://verilens.onrender.com",
            "X-Title": "VeriLens 2.0 Vision",
            "Content-Type": "application/json"
        }

        for model_name in OPENROUTER_VISION_MODELS:
            try:
                payload = {
                    "model": model_name,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": data_uri}}
                            ]
                        }
                    ],
                    "temperature": 0.15
                }
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=22
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw = data["choices"][0]["message"]["content"]
                    parsed = _extract_json_dict(raw)
                    if parsed is not None:
                        return parsed
            except Exception as e:
                print(f"[LLMClient] OpenRouter Vision ({model_name}) notice: {str(e)[:100]}")
                continue

    return None
