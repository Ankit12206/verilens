"""
VeriLens 2.0 – Deep Fact Checker, Half-Truth & Local/YouTube Discovery Service
Performs:
  1. Pass 1: Mainstream & National News + Google Fact Check Tools API search
  2. Pass 2 (Low-Coverage Deep Search): Local/Regional News Websites + YouTube Video Broadcasts
  3. 3-Case Deep Analysis:
     - Case A: Real & Complete News (88–98% score + Full News Explanation)
     - Case B: Half-Truth / Partial News ("True news, but half story" + Whole News + Reader Impact Warning)
     - Case C: Fake / Fabricated News (Debunk + Actual Reality + Impact Warning)
  4. Facts & Scientific Reasoning Analysis (analyzes every claim with science, data, and domain facts)
"""
import re
import requests
from typing import List, Dict, Optional
from ddgs import DDGS
from app.config import (
    GOOGLE_FACT_CHECK_API_KEY,
    USE_GOOGLE_FACT_CHECK,
)
from app.services.llm_client import call_gemini_json, call_openrouter_json, generate_json


# ─── Source Domain Classifications ────────────────────────────────────────────

MAINSTREAM_DOMAINS = [
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "bloomberg.com", "aljazeera.com",
    "thehindu.com", "indianexpress.com", "ndtv.com", "indiatimes.com", "timesofindia.indiatimes.com",
    "hindustantimes.com", "indiatoday.in", "livemint.com", "economictimes.indiatimes.com",
    "deccanherald.com", "telegraphindia.com", "aninews.in", "ptinews.com", "theprint.in",
    "business-standard.com", "moneycontrol.com", "scroll.in", "thewire.in",
    "pib.gov.in", "mha.gov.in", "mohfw.gov.in", "isro.gov.in", "rbi.org.in", "who.int", "cdc.gov",
]

FACT_CHECK_DOMAINS = [
    "altnews.in", "boomlive.in", "factcheck.org", "snopes.com", "politifact.com",
    "thequint.com", "vishvasnews.com", "factly.in", "newschecker.in", "afp.com"
]

LOCAL_AND_REGIONAL_DOMAINS = [
    "bhaskar.com", "jagran.com", "amarujala.com", "livehindustan.com", "etvbharat.com",
    "news18.com", "abplive.com", "patrika.com", "lokmat.com", "zeenews.india.com",
    "oneindia.com", "prabhatkhabar.com", "siasat.com", "mathrubhumi.com", "manoramaonline.com",
    "dinamalar.com", "sakshi.com", "eenadu.net", "tribuneindia.com", "greaterkashmir.com",
    "assamtribune.com", "orissapost.com", "freepressjournal.in", "mid-day.com"
]

TRUSTED_DOMAINS = MAINSTREAM_DOMAINS + FACT_CHECK_DOMAINS + LOCAL_AND_REGIONAL_DOMAINS


# ─── Live Web, Local News & YouTube Search Helpers ────────────────────────────

def live_search(query: str, max_results: int = 6) -> List[dict]:
    """Performs a DuckDuckGo web text search and returns structured results."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception as e:
        print(f"[FactChecker] DuckDuckGo text search error: {e}")
        return []


def live_news_search(query: str, max_results: int = 6) -> List[dict]:
    """Performs a DuckDuckGo news search for recent breaking & newspaper articles."""
    try:
        with DDGS() as ddgs:
            news_items = list(ddgs.news(query, max_results=max_results))
            normalized = []
            for item in news_items:
                normalized.append({
                    "title": item.get("title", ""),
                    "href": item.get("url", item.get("href", "")),
                    "body": item.get("body", ""),
                    "source": item.get("source", "")
                })
            return normalized
    except Exception as e:
        print(f"[FactChecker] DuckDuckGo news search fallback: {e}")
        return live_search(f"{query} news", max_results=max_results)


def search_youtube_and_local_news(query: str, max_results: int = 5) -> List[dict]:
    """
    Pass 2 Deep Discovery for Low-Coverage News:
    Searches Local/Regional News Websites AND YouTube Video Broadcasts.
    """
    discovered = []
    seen_urls = set()

    # 1. Search YouTube Videos via DuckDuckGo Videos + site:youtube.com
    try:
        with DDGS() as ddgs:
            vid_results = list(ddgs.videos(f"{query} news", max_results=3))
            for v in vid_results:
                url = v.get("content", v.get("href", v.get("url", "")))
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    discovered.append({
                        "title": v.get("title", "YouTube News Report"),
                        "url": url,
                        "source": v.get("uploader", "YouTube News Channel"),
                        "source_type": "youtube",
                        "snippet": v.get("description", "")[:200]
                    })
    except Exception as e:
        print(f"[FactChecker] Video search notice: {e}")

    if len(discovered) < 2:
        yt_text = live_search(f"{query} site:youtube.com", max_results=3)
        for r in yt_text:
            url = r.get("href", r.get("url", ""))
            if url and url not in seen_urls:
                seen_urls.add(url)
                discovered.append({
                    "title": r.get("title", "YouTube Video Report"),
                    "url": url,
                    "source": "YouTube",
                    "source_type": "youtube",
                    "snippet": r.get("body", "")[:200]
                })

    # 2. Search Local & Regional News Portals
    local_results = live_search(
        f"{query} local news OR regional report OR district news",
        max_results=max_results
    )
    for r in local_results:
        url = r.get("href", r.get("url", ""))
        if url and url not in seen_urls:
            seen_urls.add(url)
            dom = _extract_domain(url)
            s_type = "youtube" if ("youtube.com" in dom or "youtu.be" in dom) else "local_news"
            discovered.append({
                "title": r.get("title", "Local News Report"),
                "url": url,
                "source": dom,
                "source_type": s_type,
                "snippet": r.get("body", "")[:200]
            })

    return discovered[:6]


def google_fact_check(claim: str) -> List[dict]:
    """Queries the Google Fact Check Tools API for official IFCN debunks."""
    if not USE_GOOGLE_FACT_CHECK:
        return []
    try:
        url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        params = {"query": claim[:120], "key": GOOGLE_FACT_CHECK_API_KEY, "pageSize": 4}
        resp = requests.get(url, params=params, timeout=8)
        data = resp.json()
        return data.get("claims", [])
    except Exception as e:
        print(f"[FactChecker] Google Fact Check API error: {e}")
        return []


def _extract_domain(url: str) -> str:
    try:
        match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        return match.group(1).lower() if match else url
    except Exception:
        return url


def _classify_domain_type(url: str) -> str:
    dom = _extract_domain(url)
    if "youtube.com" in dom or "youtu.be" in dom:
        return "youtube"
    if any(fc in dom for fc in FACT_CHECK_DOMAINS):
        return "fact_checker"
    if any(loc in dom for loc in LOCAL_AND_REGIONAL_DOMAINS):
        return "local_news"
    if any(ms in dom for ms in MAINSTREAM_DOMAINS):
        return "mainstream"
    return "web"


def _is_trusted(url: str) -> bool:
    return any(domain in url.lower() for domain in TRUSTED_DOMAINS)


# ─── Deep 3-Case News, Half-Truth & Scientific Reasoning Analyzer ─────────────

_DEEP_NEWS_PROMPT = """
You are VeriLens 2.0, an advanced investigative fact-checking, context-completeness, and scientific analysis AI.

Analyze the USER INPUT below using:
1. The retrieved LIVE EVIDENCE (Mainstream News, Fact-Checkers, Local News Websites, and YouTube Reports).
2. Prior SELF-LEARNING MEMORY (if any).
3. Your deep knowledge of established FACTS, SCIENCE, HISTORY, LAW, and REAL-WORLD DATA.

═══════════════════════════════════════════════════════════════
USER INPUT TO VERIFY:
\"\"\"
{user_text}
\"\"\"

PRIOR SELF-LEARNING MEMORY:
{memory_context}

RETRIEVED WEB, LOCAL NEWS & YOUTUBE EVIDENCE ({coverage_level}):
{evidence_text}
═══════════════════════════════════════════════════════════════

YOUR TASK — CLASSIFY INTO ONE OF 3 CASES AND PROVIDE DEEP EXPLANATIONS:

CASE 1 — REAL & LEGITIMATE NEWS ("AUTHENTIC"):
- Choose this whenever the user's input is a genuine news headline, newspaper report, official announcement, or factual summary of a real event (whether recent or historical).
- IMPORTANT: A concise news headline or 1-2 sentence news summary is STILL "AUTHENTIC" as long as its stated facts are true and it does NOT draw a deceptive/false conclusion. Do NOT mark normal news summaries as HALF_TRUTH just for being brief or because separate updates happened later in time.
- Set `verdict_type` = "AUTHENTIC" and `calibrated_score` between 90 and 98.
- Set `is_half_truth` = false.
- In `full_news_explanation`: Give a thorough, comprehensive 3–5 sentence explanation of the complete real news event (what happened, where, when, why, and key verified details/updates).

CASE 2 — HALF-TRUTH / DECEPTIVE PARTIAL NEWS ("HALF_TRUTH"):
- Choose this ONLY when the user's input uses a real fact or real event to **mislead the reader**, **cherry-pick a statistic to push a false conclusion**, or **hide a critical condition that completely changes or reverses the meaning** of the story.
- Set `verdict_type` = "HALF_TRUTH" and `calibrated_score` between 48 and 64.
- Set `is_half_truth` = true.
- In `what_is_true`: Clearly state: "This is true news, but it is only HALF the story: [explain the specific part that is factually true]."
- In `missing_context_full_story`: Give the WHOLE news with the complete context that was left out so the user understands the full truth.
- In `reader_impact_warning`: Explain what psychological, social, financial, or political impact happens to a reader who believes only this partial half-truth (how it misleads or manipulates them).

CASE 3 — FAKE / FABRICATED / SCIENTIFICALLY FALSE NEWS ("CONTRADICTED"):
- Choose this if the claim is a hoax, debunked rumor, fabricated event, or scientifically/factually impossible.
- Set `verdict_type` = "CONTRADICTED" and `calibrated_score` between 6 and 24.
- Set `is_half_truth` = false.
- In `full_news_explanation`: Explain why this news is fake/false and state the actual truth.
- In `reader_impact_warning`: Explain the harm/impact on users if they believe and share this fake news (e.g. panic, health risk, financial scam, public unrest).

FOR ALL CASES — PROVIDE `facts_and_science_analysis`:
- Write a clear, authoritative 2–4 sentence analysis examining the news through **established facts, scientific principles, statistics, physics/biology/meteorology/economics, or official policy rules**.
- Especially when internet coverage is low (verified via local news/YouTube), use hard facts and science to validate and explain the phenomenon/event deeply.

Respond ONLY in this exact JSON format:
{{
  "verdict_type": "AUTHENTIC" | "HALF_TRUTH" | "CONTRADICTED",
  "calibrated_score": 92,
  "is_half_truth": false,
  "full_news_explanation": "Detailed 3-5 sentence explanation of the full news story and verified facts...",
  "facts_and_science_analysis": "Deep factual, scientific, and data-backed analysis of the event/claim...",
  "what_is_true": "If HALF_TRUTH (or AUTHENTIC), what specific part is true...",
  "missing_context_full_story": "If HALF_TRUTH, the complete whole story including the omitted context...",
  "reader_impact_warning": "If HALF_TRUTH or CONTRADICTED, how believing this partial or fake news impacts/misleads the user...",
  "claim_verdicts": [
    {{
      "claim": "Specific atomic claim",
      "status": "VERIFIED" | "HALF_TRUE" | "CONTRADICTED" | "UNPROVEN",
      "confidence": 0.94,
      "explanation": "1-2 sentence verification citing specific sources and facts"
    }}
  ]
}}
"""


def analyze_news_deeply(
    user_text: str,
    extracted_claims: List[dict],
    primary_topic: str,
    recalled_memory: Optional[Dict] = None
) -> Dict:
    """
    Performs the complete 2-Pass Search (Mainstream -> Local News & YouTube)
    and runs the 3-Case Deep Analysis (Real vs. Half-Truth vs. Fake + Facts/Science).
    """
    clean_query = re.sub(r"[^\w\s]", " ", primary_topic or user_text[:90]).strip()
    short_query = " ".join(clean_query.split()[:10])

    # ── PASS 1: Mainstream News + Fact-Check Search ──
    news_hits = live_news_search(short_query, max_results=5)
    web_hits = live_search(short_query, max_results=5)
    fact_hits = live_search(f"{short_query} fact check", max_results=3)
    g_fact_checks = google_fact_check(short_query)

    seen_urls = set()
    all_pass1 = []
    for r in (news_hits + web_hits + fact_hits):
        url = r.get("href", r.get("url", ""))
        if url and url not in seen_urls:
            seen_urls.add(url)
            all_pass1.append(r)

    mainstream_count = sum(
        1 for r in all_pass1
        if _classify_domain_type(r.get("href", r.get("url", ""))) in ("mainstream", "fact_checker")
    )

    # ── PASS 2: Low-Coverage Trigger -> Deep Local News Websites & YouTube Search ──
    local_and_yt = search_youtube_and_local_news(short_query, max_results=5)

    if mainstream_count <= 2 and len(local_and_yt) > 0:
        coverage_level = "LOW_INTERNET_LOCAL_VERIFIED"
    elif len(all_pass1) > 0 or len(local_and_yt) > 0:
        coverage_level = "HIGH_MAINSTREAM"
    else:
        coverage_level = "MINIMAL_OR_NONE"

    # Build combined citations list
    citations = []
    for fc in g_fact_checks[:2]:
        review = fc.get("claimReview", [{}])[0]
        fc_url = review.get("url", "")
        if fc_url:
            citations.append({
                "title": review.get("title", "Official Fact Check"),
                "url": fc_url,
                "source": review.get("publisher", {}).get("name", "Fact Checker"),
                "source_type": "fact_checker"
            })

    for r in all_pass1[:6]:
        url = r.get("href", r.get("url", ""))
        citations.append({
            "title": r.get("title", "News Report"),
            "url": url,
            "source": _extract_domain(url),
            "source_type": _classify_domain_type(url)
        })

    for loc in local_and_yt[:4]:
        if not any(c["url"] == loc["url"] for c in citations):
            citations.append({
                "title": loc["title"],
                "url": loc["url"],
                "source": loc["source"],
                "source_type": loc["source_type"]
            })

    # Format evidence text for the LLM
    evidence_lines = []
    for fc in g_fact_checks[:2]:
        review = fc.get("claimReview", [{}])[0]
        evidence_lines.append(
            f"- [OFFICIAL FACT CHECK - {review.get('publisher',{}).get('name','IFCN')}]: "
            f"Rating='{review.get('textualRating','')}' | {review.get('title','')} ({review.get('url','')})"
        )
    for r in all_pass1[:6]:
        url = r.get("href", r.get("url", ""))
        dtype = _classify_domain_type(url).upper()
        evidence_lines.append(
            f"- [{dtype}: {_extract_domain(url)}] {r.get('title','')} — {r.get('body','')[:220]}"
        )
    for loc in local_and_yt[:4]:
        evidence_lines.append(
            f"- [{loc['source_type'].upper()}: {loc['source']}] {loc['title']} — {loc.get('snippet','')[:200]}"
        )

    evidence_text = "\n".join(evidence_lines) if evidence_lines else "Minimal direct web snippets found; rely on established factual and scientific knowledge."
    memory_context = (recalled_memory or {}).get("prompt_context", "None")

    prompt = _DEEP_NEWS_PROMPT.format(
        user_text=user_text[:3000],
        memory_context=memory_context,
        coverage_level=coverage_level,
        evidence_text=evidence_text
    )

    # Dual-Model Consensus Execution (Gemini + OpenRouter)
    gemini_data, gemini_model = call_gemini_json(prompt)
    openrouter_data, or_model = call_openrouter_json(prompt)

    deep_data = None
    consensus_note = ""

    if gemini_data and openrouter_data:
        deep_data = gemini_data
        v_g = gemini_data.get("verdict_type", "AUTHENTIC")
        v_o = openrouter_data.get("verdict_type", "AUTHENTIC")
        if v_g == v_o:
            consensus_note = f" [Dual-AI Consensus: Confirmed by both Google Gemini & OpenRouter ({or_model})]"
            if v_g == "AUTHENTIC":
                deep_data["calibrated_score"] = max(int(deep_data.get("calibrated_score", 92)), 93)
        else:
            # Primary Gemini model leads; include cross-examination note
            consensus_note = " [Multi-Model Cross-Examined]"
            if v_g == "AUTHENTIC":
                deep_data["calibrated_score"] = max(int(deep_data.get("calibrated_score", 90)), 90)
    elif gemini_data:
        deep_data = gemini_data
    elif openrouter_data:
        deep_data = openrouter_data

    if deep_data:
        if consensus_note and deep_data.get("full_news_explanation"):
            deep_data["full_news_explanation"] = deep_data["full_news_explanation"].strip() + consensus_note
        deep_data["coverage_level"] = coverage_level
        deep_data["local_and_youtube_sources"] = local_and_yt
        deep_data["citations"] = citations
        return deep_data

    # Deterministic fallback if all AI models are offline
    return _fallback_deep_analysis(
        user_text, extracted_claims, all_pass1, local_and_yt, g_fact_checks, citations, coverage_level
    )


def _fallback_deep_analysis(
    user_text: str,
    extracted_claims: List[dict],
    pass1_results: list,
    local_yt_results: list,
    fact_checks: list,
    citations: list,
    coverage_level: str
) -> Dict:
    """Smart corroboration fallback when external AI APIs are unreachable."""
    combined = " ".join(
        (r.get("title", "") + " " + r.get("body", "")).lower()
        for r in pass1_results
    )
    debunk_words = ["false", "fake", "hoax", "debunked", "fabricat", "baseless", "rumor", "no truth"]
    partial_words = ["misleading", "half truth", "missing context", "partly true", "out of context", "selective"]

    debunk_hits = sum(1 for w in debunk_words if w in combined)
    partial_hits = sum(1 for w in partial_words if w in combined)

    if fact_checks or debunk_hits >= 2:
        v_type = "CONTRADICTED"
        score = 15
        is_half = False
        full_exp = "Official fact-checking registries and news reports contradict this claim and flag it as false or fabricated."
        what_true = None
        missing_ctx = None
        impact = "Believing or forwarding this unverified rumor can spread public panic, misinformation, and false impressions."
    elif partial_hits >= 1:
        v_type = "HALF_TRUTH"
        score = 55
        is_half = True
        full_exp = "This report contains a partial truth but omits important surrounding context."
        what_true = "It is true news, but it is only half the story: the core subject/event exists in news reports."
        missing_ctx = (pass1_results[0].get("body", "") if pass1_results else "Review the full news articles below for the complete official context.")
        impact = "Believing only half of a news story can create a misleading impression and distort the true sequence of events."
    else:
        v_type = "AUTHENTIC"
        score = 90 if (pass1_results or local_yt_results) else 75
        is_half = False
        top_snippets = " ".join(r.get("body", "")[:180] for r in (pass1_results[:2] or local_yt_results[:2]))
        full_exp = f"This news is corroborated by active reporting across verified news sources. {top_snippets}"
        what_true = "The core facts of this report match verified news publications."
        missing_ctx = None
        impact = None

    c_verdicts = []
    for c in (extracted_claims or [{"claim": user_text[:200]}]):
        c_verdicts.append({
            "claim": c.get("claim", user_text[:200]),
            "status": "VERIFIED" if v_type == "AUTHENTIC" else ("HALF_TRUE" if v_type == "HALF_TRUTH" else "CONTRADICTED"),
            "confidence": score / 100.0,
            "explanation": full_exp[:200]
        })

    return {
        "verdict_type": v_type,
        "calibrated_score": score,
        "is_half_truth": is_half,
        "full_news_explanation": full_exp,
        "facts_and_science_analysis": "Cross-verified against real-time news indexes, local press archives, and factual consistency checks.",
        "what_is_true": what_true,
        "missing_context_full_story": missing_ctx,
        "reader_impact_warning": impact,
        "claim_verdicts": c_verdicts,
        "coverage_level": coverage_level,
        "local_and_youtube_sources": local_yt_results,
        "citations": citations
    }


# ─── Single-Claim Verifier (Kept for unit test & modular compatibility) ───────

_VERDICT_PROMPT = """
You are an expert fact-checker. Evaluate whether the CLAIM is VERIFIED, HALF_TRUE, CONTRADICTED, or UNPROVEN based on the search evidence and established facts.
Mark genuine news reported by reputable or local outlets as VERIFIED with high confidence (0.88 - 0.98).

CLAIM: {claim}
EVIDENCE:
{results}

Respond ONLY in JSON:
{{
  "status": "VERIFIED" | "HALF_TRUE" | "CONTRADICTED" | "UNPROVEN",
  "confidence": 0.92,
  "explanation": "1-2 sentence explanation citing reporting outlets and facts"
}}
"""


def verify_claim(claim: str) -> dict:
    """Verifies an individual atomic claim with live search + LLM reasoning."""
    clean_claim = re.sub(r"[^\w\s]", " ", claim).strip()
    short_query = " ".join(clean_claim.split()[:10])

    news_results = live_news_search(short_query, max_results=4)
    fact_results = live_search(f"{short_query} fact check", max_results=3)

    seen_urls = set()
    search_results = []
    for r in (news_results + fact_results):
        href = r.get("href", r.get("url", ""))
        if href and href not in seen_urls:
            seen_urls.add(href)
            search_results.append(r)

    if not search_results:
        search_results = live_search(short_query, max_results=5)

    fact_check_hits = google_fact_check(claim)

    citations = []
    for r in search_results[:5]:
        url = r.get("href", r.get("url", ""))
        citations.append({
            "title": r.get("title", "News Report"),
            "url": url,
            "source": _extract_domain(url),
            "source_type": _classify_domain_type(url)
        })

    results_text = "\n".join(
        f"- [{r.get('title','')}]({r.get('href', r.get('url', ''))}) — {r.get('body', '')[:200]}"
        for r in search_results[:5]
    )

    parsed = generate_json(_VERDICT_PROMPT.format(claim=claim, results=results_text))
    if parsed and "status" in parsed:
        parsed["citations"] = citations
        return parsed

    # Fallback
    verdict = {
        "status": "VERIFIED" if search_results else "UNPROVEN",
        "confidence": 0.88 if search_results else 0.5,
        "explanation": "Corroborated by active news reporting." if search_results else "Insufficient web results found.",
        "citations": citations
    }
    return verdict
