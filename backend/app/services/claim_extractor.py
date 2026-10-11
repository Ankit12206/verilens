"""
VeriLens – Claim Extractor Service
Uses Google Gemini to decompose raw news text into atomic verifiable claims
and compute a sensationalism score. Falls back to a rule-based approach
when no API key is configured.
"""
import json
import re
import requests
from typing import Optional
from app.config import GEMINI_API_KEY, USE_GEMINI, OPENROUTER_API_KEY, USE_OPENROUTER

# ─── Gemini Setup (new google-genai SDK) ─────────────────────────────────────
if USE_GEMINI:
    from google import genai as _genai_lib
    _client = _genai_lib.Client(api_key=GEMINI_API_KEY)
else:
    _client = None

# ─── Extraction Prompt ────────────────────────────────────────────────────────
_CLAIM_PROMPT = """
You are a professional fact-checking assistant. Analyze the following news article/headline and:

1. Extract 2–4 ATOMIC FACTUAL CLAIMS (specific, verifiable statements — not opinions).
2. Score SENSATIONALISM from 1–10 (1 = neutral/factual, 10 = extreme fear/outrage clickbait).
3. Identify key ENTITIES (people, places, organizations, dates) for verification.

Respond ONLY with valid JSON in this exact format:
{{
  "claims": [
    {{
      "claim": "The specific factual assertion",
      "entities": ["entity1", "entity2"],
      "is_opinion": false
    }}
  ],
  "sensationalism_score": 7,
  "sensationalism_reason": "Uses alarmist language like BREAKING and MASSIVE without evidence.",
  "primary_topic": "Brief topic description for search queries"
}}

News Text:
{text}
"""


def extract_claims(text: str, headline: Optional[str] = None) -> dict:
    """
    Extracts atomic factual claims, sensationalism score, and entities from text.

    Args:
        text: The full article body or headline to analyze.
        headline: Optional separate headline to prepend for context.

    Returns:
        dict with keys: claims, sensationalism_score, sensationalism_reason, primary_topic
    """
    full_text = f"HEADLINE: {headline}\n\nBODY: {text}" if headline else text

    # 1. Try Gemini
    if USE_GEMINI and _client:
        gemini_result = _gemini_extract(full_text)
        if gemini_result:
            return gemini_result

    # 2. Failover to OpenRouter if Gemini is rate-limited or unavailable
    if USE_OPENROUTER:
        openrouter_result = _openrouter_extract(full_text)
        if openrouter_result:
            return openrouter_result

    # 3. Deterministic rule-based fallback
    return _fallback_extract(full_text)


def _gemini_extract(text: str) -> Optional[dict]:
    """Use Gemini API to extract structured claims."""
    try:
        prompt = _CLAIM_PROMPT.format(text=text[:4000])  # Limit input size
        response = _client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[ClaimExtractor] Gemini error/quota: {e}")
        return None


def _openrouter_extract(text: str) -> Optional[dict]:
    """Use OpenRouter (Meta Llama 3) to extract structured claims."""
    try:
        prompt = _CLAIM_PROMPT.format(text=text[:4000])
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://verilens.onrender.com",
            "X-Title": "VeriLens AI",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": [
                {"role": "system", "content": "You are a professional fact-checking assistant. Respond ONLY in valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            raw = data["choices"][0]["message"]["content"].strip()
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            return json.loads(raw)
    except Exception as e:
        print(f"[ClaimExtractor] OpenRouter error: {e}")
    return None


def _fallback_extract(text: str) -> dict:
    """
    Rule-based fallback when no Gemini key is set.
    Splits sentences and scores by keywords.
    """
    # Sensationalism keyword scoring
    alarm_words = [
        "breaking", "massive", "shocking", "disaster", "urgent",
        "deadly", "crisis", "catastrophic", "exclusive", "bombshell",
        "destroyed", "killed", "collapse", "banned", "attack"
    ]
    text_lower = text.lower()
    hits = sum(1 for w in alarm_words if w in text_lower)
    sensationalism = min(10, max(1, hits * 2 + (2 if "!" in text else 0)))

    # Extract crude sentences as "claims"
    sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 20]
    claims = [
        {
            "claim": s[:200],
            "entities": [],
            "is_opinion": False
        }
        for s in sentences[:3]
    ]

    if not claims:
        claims = [{"claim": text[:200], "entities": [], "is_opinion": False}]

    return {
        "claims": claims,
        "sensationalism_score": sensationalism,
        "sensationalism_reason": f"Detected {hits} sensationalist keyword(s) in the text.",
        "primary_topic": text[:80]
    }
