"""
VeriLens 2.0 – FastAPI Main Application
Integrates:
  - Self-Learning Memory Recall & Post-Analysis Learning Loop
  - 3-Case Deep News & Half-Truth Analysis (Real vs. Half-Truth vs. Fake)
  - Deep Local News Websites & YouTube Video Discovery
  - Facts & Scientific Reasoning Analysis
  - Multimodal Vision AI Image Forensics (Real vs. AI-Generated + Incident & Location)
"""
import os
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import USE_GEMINI, USE_OPENROUTER, USE_SERPAPI, USE_GOOGLE_FACT_CHECK
from app.database.db import get_db, init_db
from app.database.models import AnalysisRecord
from app.models.schemas import (
    TextAnalysisRequest,
    FeedbackRequest,
    TrustReport,
    HealthResponse,
    ClaimItem,
    Citation,
    MediaVerification
)
from app.services.claim_extractor import extract_claims
from app.services.fact_checker import analyze_news_deeply
from app.services.image_verifier import (
    verify_image,
    load_image_from_bytes,
    load_image_from_url,
    compute_phash
)
from app.services.narrative_matrix import assemble_report
from app.services.learning_engine import (
    recall_relevant_knowledge,
    recall_image_memory,
    get_learned_source_trust,
    learn_from_analysis,
    apply_user_feedback,
    get_learning_stats
)


# ─── App Initialization ───────────────────────────────────────────────────────

app = FastAPI(
    title="VeriLens 2.0 API",
    description="Self-Learning Multimodal Disinformation, Half-Truth & Vision Forensics Engine",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    print("[OK] VeriLens 2.0 API started with Self-Learning Memory Engine.")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_claim_items_from_deep(deep_data: dict, fallback_claims: list, db: Session) -> list[ClaimItem]:
    """Builds ClaimItem objects enriched with learned source trust scores."""
    raw_citations = deep_data.get("citations", [])
    citation_objs = []
    for cit in raw_citations[:6]:
        src_dom = cit.get("source", "")
        trust_val, _ = get_learned_source_trust(src_dom, db)
        citation_objs.append(
            Citation(
                title=cit.get("title", "News Report"),
                url=cit.get("url", ""),
                source=src_dom,
                source_type=cit.get("source_type", "web"),
                trust_score=trust_val
            )
        )

    claim_verdicts = deep_data.get("claim_verdicts", [])
    items = []
    if claim_verdicts:
        for cv in claim_verdicts[:4]:
            status = cv.get("status", "VERIFIED")
            if status not in ("VERIFIED", "HALF_TRUE", "CONTRADICTED", "UNPROVEN"):
                status = "VERIFIED"
            try:
                conf = float(cv.get("confidence", 0.9))
            except Exception:
                conf = 0.9
            items.append(
                ClaimItem(
                    claim=cv.get("claim", ""),
                    status=status,
                    confidence=max(0.0, min(1.0, conf)),
                    explanation=cv.get("explanation", deep_data.get("full_news_explanation", "")),
                    citations=citation_objs
                )
            )
    else:
        for fc in fallback_claims[:3]:
            items.append(
                ClaimItem(
                    claim=fc.get("claim", ""),
                    status="VERIFIED" if deep_data.get("verdict_type") == "AUTHENTIC" else "UNPROVEN",
                    confidence=0.88,
                    explanation=deep_data.get("full_news_explanation", ""),
                    citations=citation_objs
                )
            )
    return items


def _save_to_db(db: Session, report: TrustReport, input_text: Optional[str], image_url: Optional[str]):
    """Persists the analysis result to SQLite for history retrieval."""
    record = AnalysisRecord(
        id=report.id,
        input_type=report.input_type,
        input_text=input_text,
        image_url=image_url,
        overall_verdict=report.overall_verdict,
        credibility_score=report.credibility_score,
        sensationalism_score=report.sensationalism_score,
        summary_explanation=report.summary_explanation,
        raw_report_json=report.model_dump_json()
    )
    db.add(record)
    db.commit()


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Returns API status and active engines."""
    return HealthResponse(
        status="ok",
        gemini_available=USE_GEMINI,
        openrouter_available=USE_OPENROUTER,
        duckduckgo_available=True,
        fact_check_api_available=USE_GOOGLE_FACT_CHECK,
        serpapi_available=USE_SERPAPI,
        self_learning_active=True
    )


@app.get("/api/learning-stats", tags=["Self-Learning"])
def learning_stats(db: Session = Depends(get_db)):
    """Returns live statistics from the Self-Learning Memory Bank."""
    return get_learning_stats(db)


@app.post("/api/feedback", tags=["Self-Learning"])
def submit_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    """
    Human-in-the-loop learning endpoint.
    Allows users to confirm accuracy or teach/correct the AI on any analysis.
    """
    return apply_user_feedback(payload, db)


@app.post("/api/analyze-text", response_model=TrustReport, tags=["Analysis"])
def analyze_text(payload: TextAnalysisRequest, db: Session = Depends(get_db)):
    """
    VeriLens 2.0 Deep News & Half-Truth Analyzer:
    0. Recalls prior knowledge from Self-Learning Memory
    1. Extracts atomic claims & sensationalism
    2. Searches Mainstream News + Fact-Checkers + Local News Websites + YouTube Videos
    3. Evaluates Complete Real News vs. Half-Truth (Missing Context) vs. Fake News + Science Analysis
    4. Stores new findings into the Self-Learning Memory Bank
    """
    if len(payload.text.strip()) < 6:
        raise HTTPException(status_code=400, detail="Text is too short to analyze.")

    full_input = f"{payload.headline}. {payload.text}" if payload.headline else payload.text

    # Step 0: Self-Learning Memory Recall
    recalled_memory = recall_relevant_knowledge(full_input, db)

    # Step 1: Claim & Topic Extraction
    extracted = extract_claims(payload.text, payload.headline)
    claim_list = extracted.get("claims", [])
    sensationalism = extracted.get("sensationalism_score", 3)
    topic = extracted.get("primary_topic", payload.text[:100])

    # Step 2 & 3: 2-Pass Search (Mainstream + Local/YouTube) & 3-Case Deep Analysis
    deep_analysis = analyze_news_deeply(
        user_text=full_input,
        extracted_claims=claim_list,
        primary_topic=topic,
        recalled_memory=recalled_memory
    )

    claim_items = _build_claim_items_from_deep(deep_analysis, claim_list, db)

    # Step 4: Assemble Report
    report = assemble_report(
        claims=claim_items,
        sensationalism_score=sensationalism,
        media_check=None,
        topic=topic,
        input_type="text",
        deep_analysis=deep_analysis,
        recalled_memory=recalled_memory
    )

    # Step 5: Self-Learning Writeback & DB History
    report.learning_metadata = learn_from_analysis(report, full_input, None, recalled_memory, db)
    _save_to_db(db, report, full_input, None)
    return report


@app.post("/api/analyze-image", response_model=TrustReport, tags=["Analysis"])
async def analyze_image(
    image_url: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    VeriLens 2.0 Image Forensics & Incident Identifier:
    Task 1: Identifies if the image is a Real Photograph or AI-Generated.
    Task 2: If Real -> Identifies the Related Incident, Location Taken, Date, and Full Story.
    """
    if not image_url and not file:
        raise HTTPException(status_code=400, detail="Provide either image_url or upload a file.")

    image_bytes = None
    if file:
        image_bytes = await file.read()

    # Check Self-Learning Image Fingerprint Memory first
    pil_img = load_image_from_bytes(image_bytes) if image_bytes else (load_image_from_url(image_url) if image_url else None)
    phash_str = compute_phash(pil_img) if pil_img else ""
    recalled_img = recall_image_memory(phash_str, db) if phash_str else None

    # Run 2-Stage Vision AI + Web/Local/YouTube Image Pipeline
    media_result_dict = verify_image(
        image_url=image_url,
        image_bytes=image_bytes,
        caption=caption,
        recalled_img_memory=recalled_img
    )
    phash_str = media_result_dict.pop("phash", phash_str)
    media_check = MediaVerification(**media_result_dict)

    # If user also supplied a caption, run deep news analysis on the caption
    claim_items = []
    deep_analysis = None
    recalled_memory = None
    sensationalism = 2
    topic = media_check.related_incident or caption or "Image verification"

    if caption and len(caption.strip()) >= 8:
        recalled_memory = recall_relevant_knowledge(caption, db)
        extracted = extract_claims(caption)
        claim_list = extracted.get("claims", [])
        sensationalism = extracted.get("sensationalism_score", 3)
        topic = extracted.get("primary_topic", caption[:80])
        deep_analysis = analyze_news_deeply(caption, claim_list, topic, recalled_memory)
        claim_items = _build_claim_items_from_deep(deep_analysis, claim_list, db)

    report = assemble_report(
        claims=claim_items,
        sensationalism_score=sensationalism,
        media_check=media_check,
        topic=topic,
        input_type="image",
        deep_analysis=deep_analysis,
        recalled_memory=recalled_memory
    )

    report.learning_metadata = learn_from_analysis(report, caption or topic, phash_str, recalled_memory, db)
    _save_to_db(db, report, caption or topic, image_url)
    return report


@app.post("/api/analyze-multimodal", response_model=TrustReport, tags=["Analysis"])
async def analyze_multimodal(
    text: str = Form(...),
    headline: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Combined Text + Image Analysis (Half-Truth + Science + Vision AI + Incident Lookup).
    """
    if len(text.strip()) < 6:
        raise HTTPException(status_code=400, detail="Text is too short to analyze.")

    full_input = f"{headline}. {text}" if headline else text
    recalled_memory = recall_relevant_knowledge(full_input, db)

    extracted = extract_claims(text, headline)
    claim_list = extracted.get("claims", [])
    sensationalism = extracted.get("sensationalism_score", 3)
    topic = extracted.get("primary_topic", text[:100])

    deep_analysis = analyze_news_deeply(full_input, claim_list, topic, recalled_memory)
    claim_items = _build_claim_items_from_deep(deep_analysis, claim_list, db)

    media_check = None
    phash_str = None
    if image_url or file:
        image_bytes = None
        if file:
            image_bytes = await file.read()
        pil_img = load_image_from_bytes(image_bytes) if image_bytes else (load_image_from_url(image_url) if image_url else None)
        phash_str = compute_phash(pil_img) if pil_img else ""
        recalled_img = recall_image_memory(phash_str, db) if phash_str else None

        media_result_dict = verify_image(
            image_url=image_url,
            image_bytes=image_bytes,
            caption=full_input,
            recalled_img_memory=recalled_img
        )
        phash_str = media_result_dict.pop("phash", phash_str)
        media_check = MediaVerification(**media_result_dict)

    report = assemble_report(
        claims=claim_items,
        sensationalism_score=sensationalism,
        media_check=media_check,
        topic=topic,
        input_type="multimodal",
        deep_analysis=deep_analysis,
        recalled_memory=recalled_memory
    )

    report.learning_metadata = learn_from_analysis(report, full_input, phash_str, recalled_memory, db)
    _save_to_db(db, report, full_input, image_url)
    return report


@app.get("/api/history", tags=["History"])
def get_history(limit: int = 10, db: Session = Depends(get_db)):
    """Returns the most recent analysis records from SQLite."""
    records = db.query(AnalysisRecord).order_by(
        AnalysisRecord.created_at.desc()
    ).limit(limit).all()

    return [
        {
            "id": r.id,
            "input_type": r.input_type,
            "overall_verdict": r.overall_verdict,
            "credibility_score": r.credibility_score,
            "summary": r.summary_explanation,
            "analyzed_at": r.created_at
        }
        for r in records
    ]


# ─── Serve Frontend Static Files ──────────────────────────────────────────────
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
