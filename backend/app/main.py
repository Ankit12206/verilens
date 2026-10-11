"""
VeriLens – FastAPI Main Application
All API routes, startup events, and static file serving are defined here.
Run with: uvicorn app.main:app --reload
"""
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import USE_GEMINI, USE_OPENROUTER, USE_SERPAPI, USE_GOOGLE_FACT_CHECK
from app.database.db import get_db, init_db
from app.database.models import AnalysisRecord
from app.models.schemas import (
    TextAnalysisRequest, ImageURLRequest, MultimodalRequest,
    TrustReport, HealthResponse, ClaimItem, Citation, MediaVerification
)
from app.services.claim_extractor import extract_claims
from app.services.fact_checker import verify_claim
from app.services.image_verifier import verify_image, load_image_from_url
from app.services.narrative_matrix import assemble_report

import os

# ─── App Initialization ───────────────────────────────────────────────────────

app = FastAPI(
    title="VeriLens API",
    description="Multimodal Disinformation Detection & Context-Hijack Engine",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Allow all origins for local development (Chrome Extension / Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    init_db()
    print("[OK] VeriLens API started. Visit http://127.0.0.1:8000/api/docs for interactive API docs.")




# ─── Helper: Build ClaimItems from extracted + verified data ──────────────────

def _build_claim_items(extracted_claims: list) -> list[ClaimItem]:
    """Runs fact-checking for each extracted claim and returns ClaimItem objects."""
    claim_items = []
    for c in extracted_claims:
        claim_text = c.get("claim", "")
        if not claim_text:
            continue
        verdict = verify_claim(claim_text)
        claim_items.append(ClaimItem(
            claim=claim_text,
            status=verdict.get("status", "UNPROVEN"),
            confidence=float(verdict.get("confidence", 0.4)),
            explanation=verdict.get("explanation", ""),
            citations=[
                Citation(
                    title=cit.get("title", ""),
                    url=cit.get("url", ""),
                    source=cit.get("source", "")
                )
                for cit in verdict.get("citations", [])
            ]
        ))
    return claim_items


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
    """Returns the API status and which optional services are available."""
    return HealthResponse(
        status="ok",
        gemini_available=USE_GEMINI,
        openrouter_available=USE_OPENROUTER,
        duckduckgo_available=True,
        fact_check_api_available=USE_GOOGLE_FACT_CHECK,
        serpapi_available=USE_SERPAPI
    )


@app.post("/api/analyze-text", response_model=TrustReport, tags=["Analysis"])
def analyze_text(payload: TextAnalysisRequest, db: Session = Depends(get_db)):
    """
    Analyze a news headline or article body text for misinformation.
    - Extracts atomic claims
    - Live fact-checks each claim via DuckDuckGo + optional Gemini
    - Builds 360° Narrative Matrix
    - Returns a full TrustReport
    """
    if len(payload.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Text is too short to analyze.")

    # 1. Extract claims
    extracted = extract_claims(payload.text, payload.headline)
    claim_list = extracted.get("claims", [])
    sensationalism = extracted.get("sensationalism_score", 5)
    topic = extracted.get("primary_topic", payload.text[:100])

    # 2. Verify each claim
    claim_items = _build_claim_items(claim_list)

    # 3. Assemble final report
    report = assemble_report(
        claims=claim_items,
        sensationalism_score=sensationalism,
        media_check=None,
        topic=topic,
        input_type="text"
    )

    _save_to_db(db, report, payload.text, None)
    return report


@app.post("/api/analyze-image", response_model=TrustReport, tags=["Analysis"])
async def analyze_image(
    image_url: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Verify whether an uploaded image or image URL is being used out of context.
    Supports:
    - Direct image URL
    - Uploaded image file (JPEG, PNG, WebP)
    """
    if not image_url and not file:
        raise HTTPException(status_code=400, detail="Provide either image_url or upload a file.")

    image_bytes = None
    if file:
        image_bytes = await file.read()

    # Run image verification pipeline
    media_result_dict = verify_image(
        image_url=image_url,
        image_bytes=image_bytes,
        caption=caption
    )

    media_check = MediaVerification(**media_result_dict)

    # Create a synthetic claim from the caption for text analysis
    claim_items = []
    if caption:
        extracted = extract_claims(caption)
        claim_list = extracted.get("claims", [])
        sensationalism = extracted.get("sensationalism_score", 5)
        topic = extracted.get("primary_topic", caption[:80])
        claim_items = _build_claim_items(claim_list)
    else:
        sensationalism = 5
        topic = "Image verification"

    report = assemble_report(
        claims=claim_items,
        sensationalism_score=sensationalism,
        media_check=media_check,
        topic=topic,
        input_type="image"
    )

    _save_to_db(db, report, caption, image_url)
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
    Perform a combined text + image analysis:
    - Extracts and verifies textual claims
    - Runs context-hijack detection on the accompanying image
    - Builds a unified TrustReport covering both modalities
    """
    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Text is too short to analyze.")

    # ── Text Pipeline ──
    extracted = extract_claims(text, headline)
    claim_list = extracted.get("claims", [])
    sensationalism = extracted.get("sensationalism_score", 5)
    topic = extracted.get("primary_topic", text[:100])
    claim_items = _build_claim_items(claim_list)

    # ── Image Pipeline ──
    media_check = None
    if image_url or file:
        image_bytes = None
        if file:
            image_bytes = await file.read()
        media_result_dict = verify_image(
            image_url=image_url,
            image_bytes=image_bytes,
            caption=text
        )
        media_check = MediaVerification(**media_result_dict)

    report = assemble_report(
        claims=claim_items,
        sensationalism_score=sensationalism,
        media_check=media_check,
        topic=topic,
        input_type="multimodal"
    )

    _save_to_db(db, report, text, image_url)
    return report


@app.get("/api/history", tags=["History"])
def get_history(limit: int = 10, db: Session = Depends(get_db)):
    """Returns the most recent analysis records from the SQLite database."""
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

