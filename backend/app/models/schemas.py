"""
VeriLens Pydantic Schemas
Defines all request/response data models for the API.
"""
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Literal
from datetime import datetime


# ─── Input Models ─────────────────────────────────────────────────────────────

class TextAnalysisRequest(BaseModel):
    text: str
    headline: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Breaking: Massive floods in Mumbai today, thousands displaced",
                "headline": "Mumbai flooded after record rainfall"
            }
        }
    }


class ImageURLRequest(BaseModel):
    image_url: str
    caption: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "image_url": "https://example.com/image.jpg",
                "caption": "Flood damage seen in Mumbai streets today"
            }
        }
    }


class MultimodalRequest(BaseModel):
    text: str
    image_url: Optional[str] = None
    headline: Optional[str] = None


# ─── Output / Report Models ────────────────────────────────────────────────────

class Citation(BaseModel):
    title: str
    url: str
    source: str


class ClaimItem(BaseModel):
    claim: str
    status: Literal["VERIFIED", "CONTRADICTED", "UNPROVEN"]
    confidence: float          # 0.0 – 1.0
    explanation: str
    citations: List[Citation]


class MediaVerification(BaseModel):
    checked: bool
    earliest_found_year: Optional[int] = None
    original_context: Optional[str] = None
    is_context_hijacked: bool = False
    discrepancy_details: Optional[str] = None
    warning_message: Optional[str] = None


class NarrativePerspective(BaseModel):
    label: str          # e.g. "Viral Social Claim", "Mainstream Outlets", "Official Record"
    summary: str
    source_urls: List[str]


class NarrativeMatrix(BaseModel):
    perspectives: List[NarrativePerspective]
    consensus_verdict: str


class TrustReport(BaseModel):
    id: str
    overall_verdict: Literal[
        "AUTHENTIC", "MOSTLY_TRUE", "MISLEADING", "CONTRADICTED",
        "CONTEXT_HIJACKED", "UNVERIFIED", "SATIRE_LIKELY"
    ]
    credibility_score: int          # 0 – 100
    sensationalism_score: int       # 1 – 10
    claims: List[ClaimItem]
    media_verification: Optional[MediaVerification] = None
    narrative_matrix: Optional[NarrativeMatrix] = None
    summary_explanation: str
    analyzed_at: datetime
    input_type: Literal["text", "image", "multimodal"]


class HealthResponse(BaseModel):
    status: str
    gemini_available: bool
    openrouter_available: bool
    duckduckgo_available: bool
    fact_check_api_available: bool
    serpapi_available: bool
