"""
VeriLens – Narrative Matrix Service
Builds the 360° Narrative Matrix by:
  1. Searching for how different media tiers cover the story.
  2. Classifying each source's stance (SUPPORT / CONTRADICT / NEUTRAL).
  3. Computing the final composite Credibility Score (0–100).
  4. Assembling the complete TrustReport.
"""
import uuid
import json
import re
from datetime import datetime
from typing import List, Optional

from ddgs import DDGS

from app.config import USE_GEMINI, GEMINI_API_KEY

if USE_GEMINI:
    from google import genai as _genai_lib
    _client = _genai_lib.Client(api_key=GEMINI_API_KEY)
else:
    _client = None
from app.models.schemas import (
    NarrativeMatrix, NarrativePerspective,
    ClaimItem, Citation, TrustReport, MediaVerification
)


# ─── Source Tiers ─────────────────────────────────────────────────────────────
OFFICIAL_DOMAINS = ["pib.gov.in", "mha.gov.in", "who.int", "cdc.gov", "mausam.imd.gov.in", "mohfw.gov.in"]
WIRE_DOMAINS = ["reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "afp.com"]
FACT_CHECK_DOMAINS = ["snopes.com", "politifact.com", "factcheck.org", "altnews.in", "boomlive.in", "factchecker.in"]

# ─── Narrative Search Queries ──────────────────────────────────────────────────
_MATRIX_PROMPT = """
You are a neutral media analyst. Given a news topic and search snippets from different sources, construct a 360° Narrative Matrix.

TOPIC: {topic}

SEARCH RESULTS:
{results}

Respond ONLY in this exact JSON format:
{{
  "perspectives": [
    {{
      "label": "Viral / Social Media Claim",
      "summary": "What viral/social media sources are saying",
      "source_urls": ["url1", "url2"]
    }},
    {{
      "label": "Mainstream Media Coverage",
      "summary": "What established news outlets report",
      "source_urls": ["url1", "url2"]
    }},
    {{
      "label": "Official / Primary Record",
      "summary": "What official government or scientific sources state",
      "source_urls": ["url1"]
    }}
  ],
  "consensus_verdict": "One sentence summarizing the overall consensus across all perspectives"
}}
"""


def build_narrative_matrix(topic: str) -> Optional[NarrativeMatrix]:
    """
    Searches for the topic across media tiers and builds the 360° Narrative Matrix.
    """
    try:
        # Search across multiple tiers
        with DDGS() as ddgs:
            mainstream = list(ddgs.text(f"{topic} news report", max_results=4))
            official = list(ddgs.text(f"{topic} official government statement", max_results=3))
            social = list(ddgs.text(f"{topic} viral social media claim", max_results=3))

        all_results = mainstream + official + social
        results_text = "\n".join(
            f"- [{r.get('title','')}]({r.get('href', r.get('url',''))}) — {r.get('body','')[:200]}"
            for r in all_results[:10]
        )

        if USE_GEMINI and _client:
            return _gemini_matrix(topic, results_text, all_results)
        else:
            return _fallback_matrix(mainstream, official, social)
    except Exception as e:
        print(f"[NarrativeMatrix] Error building matrix: {e}")
        return None


def _gemini_matrix(topic: str, results_text: str, all_results: list) -> Optional[NarrativeMatrix]:
    """Use Gemini to synthesize the narrative matrix."""
    try:
        prompt = _MATRIX_PROMPT.format(topic=topic, results=results_text)
        resp = _client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )
        raw = resp.text.strip()
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)

        perspectives = [
            NarrativePerspective(
                label=p["label"],
                summary=p["summary"],
                source_urls=p.get("source_urls", [])
            )
            for p in data.get("perspectives", [])
        ]
        return NarrativeMatrix(
            perspectives=perspectives,
            consensus_verdict=data.get("consensus_verdict", "")
        )
    except Exception as e:
        print(f"[NarrativeMatrix] Gemini matrix error: {e}")
        return _fallback_matrix(all_results[:4], all_results[4:7], all_results[7:])


def _fallback_matrix(mainstream: list, official: list, social: list) -> NarrativeMatrix:
    """Rule-based narrative matrix when Gemini is unavailable."""
    def summarize(results: list) -> str:
        snippets = [r.get("body", r.get("title", ""))[:120] for r in results[:2]]
        return " | ".join(snippets) if snippets else "No data found from this source tier."

    def urls(results: list) -> List[str]:
        return [r.get("href", r.get("url", "")) for r in results[:2]]

    perspectives = [
        NarrativePerspective(label="Viral / Social Media Claim", summary=summarize(social), source_urls=urls(social)),
        NarrativePerspective(label="Mainstream Media Coverage", summary=summarize(mainstream), source_urls=urls(mainstream)),
        NarrativePerspective(label="Official / Primary Record", summary=summarize(official), source_urls=urls(official)),
    ]
    return NarrativeMatrix(
        perspectives=perspectives,
        consensus_verdict="Automated analysis complete. Review individual perspectives for a full picture."
    )


# ─── Credibility Score Calculator ─────────────────────────────────────────────

def calculate_credibility_score(
    claims: List[ClaimItem],
    sensationalism_score: int,
    media_check: Optional[MediaVerification]
) -> int:
    """
    Computes a composite credibility score from 0–100.

    Weightings:
      - Claim verdicts:     60%
      - Sensationalism:     25%
      - Context-Hijack:     15%
    """
    # ── Claim Score (60%) ──
    claim_points = 0
    for claim in claims:
        if claim.status == "VERIFIED":
            claim_points += claim.confidence
        elif claim.status == "UNPROVEN":
            claim_points += 0.35
        else:  # CONTRADICTED
            claim_points += 0.0

    claim_score = (claim_points / len(claims)) * 60 if claims else 30

    # ── Sensationalism Score (25%) ──
    # Lower sensationalism = higher credibility
    sens_score = ((10 - sensationalism_score) / 9) * 25

    # ── Context-Hijack Penalty (15%) ──
    if media_check and media_check.is_context_hijacked:
        context_score = 0
    elif media_check and media_check.checked:
        context_score = 15
    else:
        context_score = 8  # Neutral when not checked

    total = int(round(claim_score + sens_score + context_score))
    return max(0, min(100, total))


def determine_verdict(score: int, media_check: Optional[MediaVerification]) -> str:
    """Maps a credibility score and media check to the final verdict label."""
    if media_check and media_check.is_context_hijacked:
        return "CONTEXT_HIJACKED"
    if score >= 80:
        return "AUTHENTIC"
    if score >= 60:
        return "MOSTLY_TRUE"
    if score >= 40:
        return "MISLEADING"
    if score >= 20:
        return "CONTRADICTED"
    return "UNVERIFIED"


# ─── Report Assembler ──────────────────────────────────────────────────────────

def assemble_report(
    claims: List[ClaimItem],
    sensationalism_score: int,
    media_check: Optional[MediaVerification],
    topic: str,
    input_type: str
) -> TrustReport:
    """
    Assembles the complete TrustReport from all pipeline outputs.
    """
    # Build narrative matrix
    narrative = build_narrative_matrix(topic)

    # Calculate scores and verdict
    credibility_score = calculate_credibility_score(claims, sensationalism_score, media_check)
    verdict = determine_verdict(credibility_score, media_check)

    # Generate summary explanation
    summary = _generate_summary(verdict, credibility_score, claims, media_check)

    return TrustReport(
        id=str(uuid.uuid4()),
        overall_verdict=verdict,
        credibility_score=credibility_score,
        sensationalism_score=sensationalism_score,
        claims=claims,
        media_verification=media_check,
        narrative_matrix=narrative,
        summary_explanation=summary,
        analyzed_at=datetime.utcnow(),
        input_type=input_type
    )


def _generate_summary(verdict: str, score: int, claims: List[ClaimItem], media_check: Optional[MediaVerification]) -> str:
    """Generates a human-readable summary sentence for the trust report."""
    contradicted = sum(1 for c in claims if c.status == "CONTRADICTED")
    verified = sum(1 for c in claims if c.status == "VERIFIED")

    if verdict == "CONTEXT_HIJACKED":
        return (
            f"This content has been flagged as a CONTEXT HIJACK. "
            f"An authentic image is being reused in a false or misleading context. "
            f"Credibility score: {score}/100."
        )
    elif verdict == "AUTHENTIC":
        return f"{verified} out of {len(claims)} claim(s) verified by credible sources. Credibility score: {score}/100."
    elif verdict == "CONTRADICTED":
        return f"{contradicted} out of {len(claims)} claim(s) directly contradicted by credible sources. Credibility score: {score}/100."
    elif verdict == "MISLEADING":
        return f"Content shows signs of exaggeration or selective omission. {contradicted} claim(s) flagged. Credibility score: {score}/100."
    else:
        return f"Insufficient evidence to confirm or deny these claims. Credibility score: {score}/100. Manual verification recommended."
