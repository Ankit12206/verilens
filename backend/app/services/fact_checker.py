"""
VeriLens – Fact Checker Service
Performs live web searches using DuckDuckGo (zero API key required) and
optionally queries the Google Fact Check Tools API for official debunks.
Uses Gemini to synthesize retrieved evidence into a final claim verdict.
"""
import json
import re
import requests
from typing import List, Optional
from ddgs import DDGS
from app.config import (
    USE_GEMINI, GOOGLE_FACT_CHECK_API_KEY,
    USE_GOOGLE_FACT_CHECK, GEMINI_API_KEY
)

if USE_GEMINI:
    from google import genai as _genai_lib
    _client = _genai_lib.Client(api_key=GEMINI_API_KEY)
else:
    _client = None


# ─── Trusted / High-Priority Source Domains ──────────────────────────────────
TRUSTED_DOMAINS = [
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "ndtv.com", "thehindu.com", "indianexpress.com",
    "altnews.in", "boomlive.in", "factcheck.org",
    "snopes.com", "politifact.com",
    "pib.gov.in", "mha.gov.in", "mohfw.gov.in",
    "who.int", "cdc.gov",
]


def live_search(query: str, max_results: int = 6) -> List[dict]:
    """
    Performs a DuckDuckGo text search and returns structured results.
    Each result has: title, url, body (snippet).
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception as e:
        print(f"[FactChecker] DuckDuckGo search error: {e}")
        return []


def google_fact_check(claim: str) -> List[dict]:
    """
    Queries the Google Fact Check Tools API for an existing debunk of the claim.
    Returns a list of fact check articles if found.
    Requires GOOGLE_FACT_CHECK_API_KEY in .env (free, no billing needed).
    """
    if not USE_GOOGLE_FACT_CHECK:
        return []
    try:
        url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        params = {"query": claim, "key": GOOGLE_FACT_CHECK_API_KEY, "pageSize": 3}
        resp = requests.get(url, params=params, timeout=8)
        data = resp.json()
        return data.get("claims", [])
    except Exception as e:
        print(f"[FactChecker] Google Fact Check API error: {e}")
        return []


def _is_trusted(url: str) -> bool:
    return any(domain in url for domain in TRUSTED_DOMAINS)


_VERDICT_PROMPT = """
You are a professional fact-checker. Based only on the search results below, determine if the following claim is VERIFIED, CONTRADICTED, or UNPROVEN.

CLAIM: {claim}

SEARCH RESULTS:
{results}

Respond ONLY in this exact JSON format:
{{
  "status": "VERIFIED" | "CONTRADICTED" | "UNPROVEN",
  "confidence": 0.0 to 1.0,
  "explanation": "1-2 sentence explanation citing specific results",
  "key_source": "Most relevant URL from the results, or empty string"
}}
"""


def verify_claim(claim: str) -> dict:
    """
    Main function: searches the web for evidence on a claim and returns a verdict.

    Returns dict with: status, confidence, explanation, citations
    """
    # 1. Live web search for the claim
    search_results = live_search(f'"{claim}" fact check site:reuters.com OR site:apnews.com OR site:snopes.com OR site:altnews.in', max_results=4)
    if not search_results:
        # Broader fallback search
        search_results = live_search(claim, max_results=5)

    # 2. Optional Google Fact Check API
    fact_check_hits = google_fact_check(claim)

    # 3. Build citation objects
    citations = []
    for r in search_results[:5]:
        citations.append({
            "title": r.get("title", "No title"),
            "url": r.get("href", r.get("url", "")),
            "source": _extract_domain(r.get("href", r.get("url", "")))
        })

    # Add fact check hits as top-priority citations
    for fc in fact_check_hits[:2]:
        review = fc.get("claimReview", [{}])[0]
        citations.insert(0, {
            "title": review.get("title", "Fact Check Result"),
            "url": review.get("url", ""),
            "source": review.get("publisher", {}).get("name", "Fact Checker")
        })

    # 4. Synthesize verdict using Gemini or rule-based fallback
    results_text = "\n".join(
        f"- [{r.get('title','')}]({r.get('href', r.get('url', ''))}) — {r.get('body', '')[:200]}"
        for r in search_results[:5]
    )

    if USE_GEMINI and _client and search_results:
        verdict = _gemini_verdict(claim, results_text)
    else:
        verdict = _fallback_verdict(claim, search_results, fact_check_hits)

    verdict["citations"] = citations
    return verdict


def _gemini_verdict(claim: str, results_text: str) -> dict:
    """Use Gemini to synthesize a verdict from search results."""
    try:
        prompt = _VERDICT_PROMPT.format(claim=claim, results=results_text)
        resp = _client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )
        raw = resp.text.strip()
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
    except Exception as e:
        print(f"[FactChecker] Gemini verdict error: {e}")
        return _fallback_verdict(claim, [], [])


def _fallback_verdict(claim: str, results: list, fact_checks: list) -> dict:
    """Simple keyword-based verdict when Gemini is unavailable."""
    debunk_keywords = ["false", "misleading", "debunked", "misinformation", "fake", "not true", "no evidence"]
    confirm_keywords = ["confirmed", "true", "verified", "official", "government", "report confirms"]

    combined_text = " ".join(
        (r.get("body", "") + r.get("title", "")).lower()
        for r in results
    )

    debunk_hits = sum(1 for kw in debunk_keywords if kw in combined_text)
    confirm_hits = sum(1 for kw in confirm_keywords if kw in combined_text)

    if fact_checks:
        status = "CONTRADICTED"
        confidence = 0.8
        explanation = "This claim appears in official fact-check registries as previously debunked."
    elif debunk_hits > confirm_hits:
        status = "CONTRADICTED"
        confidence = min(0.75, 0.3 + debunk_hits * 0.1)
        explanation = f"Found {debunk_hits} search results suggesting the claim is false or misleading."
    elif confirm_hits > debunk_hits:
        status = "VERIFIED"
        confidence = min(0.75, 0.3 + confirm_hits * 0.1)
        explanation = f"Found {confirm_hits} search results from credible sources confirming this claim."
    else:
        status = "UNPROVEN"
        confidence = 0.4
        explanation = "No strong evidence found either confirming or contradicting this claim."

    return {"status": status, "confidence": confidence, "explanation": explanation}


def _extract_domain(url: str) -> str:
    """Extract the domain name from a URL for display purposes."""
    try:
        match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        return match.group(1) if match else url
    except Exception:
        return url
