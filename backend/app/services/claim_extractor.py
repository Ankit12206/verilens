"""
VeriLens 2.0 – Claim Extractor Service
Decomposes raw news text or headlines into atomic verifiable claims,
computes a calibrated sensationalism score (1–10), and generates search queries.
Uses the Multi-Model AI Client (rotating across 4 Gemini models + OpenRouter)
with deterministic rule-based fallback.
"""
from typing import Optional
from app.services.llm_client import generate_json

_CLAIM_PROMPT = """
You are a professional fact-checking assistant. Analyze the following news article or headline:

1. Extract 1–3 core ATOMIC FACTUAL CLAIMS (specific, verifiable statements).
2. Score SENSATIONALISM from 1–10:
   - 1–3: Neutral, factual, objective journalism (e.g., RBI policy, official announcements, standard news).
   - 4–6: Moderate urgency or dramatic phrasing.
   - 7–10: Extreme clickbait, all-caps panic, fear-mongering ("SHOCKING", "SECRETLY BANNED", "SHARE BEFORE DELETED").
3. Generate a concise SEARCH QUERY (5–8 keywords) to find mainstream and local news about this event.

Respond ONLY in this exact JSON format:
{{
  "claims": [
    {{
      "claim": "Specific verifiable statement",
      "entities": ["entity1", "entity2"],
      "is_opinion": false
    }}
  ],
  "sensationalism_score": 2,
  "sensationalism_reason": "Brief explanation of the tone",
  "primary_topic": "5-8 word search query for this news event"
}}

NEWS TEXT TO ANALYZE:
\"\"\"
{text}
\"\"\"
"""


def extract_claims(text: str, headline: Optional[str] = None) -> dict:
    """
    Extracts atomic factual claims, sensationalism score, and primary topic from text.
    """
    full_text = f"HEADLINE: {headline}\n\nBODY: {text}" if headline else text

    prompt = _CLAIM_PROMPT.format(text=full_text[:4000])
    llm_result = generate_json(prompt)

    if llm_result and isinstance(llm_result.get("claims"), list) and len(llm_result["claims"]) > 0:
        # Ensure sensationalism_score is an integer 1..10
        try:
            sens = int(llm_result.get("sensationalism_score", 3))
            llm_result["sensationalism_score"] = max(1, min(10, sens))
        except Exception:
            llm_result["sensationalism_score"] = 3
        if not llm_result.get("primary_topic"):
            llm_result["primary_topic"] = (headline or text[:80]).strip()
        return llm_result

    return _fallback_extract(full_text)


def _fallback_extract(text: str) -> dict:
    """Rule-based fallback when all external AI models are unreachable."""
    alarm_words = [
        "breaking", "massive", "shocking", "disaster", "urgent",
        "deadly", "crisis", "catastrophic", "exclusive", "bombshell",
        "destroyed", "killed", "collapse", "banned", "attack", "secretly", "horrified"
    ]
    text_lower = text.lower()
    hits = sum(1 for w in alarm_words if w in text_lower)
    excl = text.count("!")
    caps_words = sum(1 for w in text.split() if len(w) > 3 and w.isupper())
    sensationalism = min(10, max(1, 1 + hits * 2 + min(3, excl) + min(2, caps_words)))

    sentences = [
        s.strip() for s in text.replace("!", ".").replace("?", ".").split(".")
        if len(s.strip()) > 15
    ][:3]

    claims = [
        {"claim": s, "entities": [], "is_opinion": False}
        for s in (sentences or [text[:200]])
    ]

    return {
        "claims": claims,
        "sensationalism_score": sensationalism,
        "sensationalism_reason": f"Detected {hits} sensational keyword(s).",
        "primary_topic": sentences[0][:80] if sentences else text[:80]
    }
