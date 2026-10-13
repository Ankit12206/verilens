"""
VeriLens 2.0 Pydantic Schemas
Defines all request/response data models for the API, including:
  - Full News Explanation & Half-Truth / Missing Context Breakdown
  - Reader Impact Warning
  - Facts & Scientific Reasoning Analysis
  - Deep Local News & YouTube Video Discovery
  - Image AI-Generation Detection + Incident & Location Dossier
  - Self-Learning Memory & User Feedback Loop
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


# ─── Input Models ─────────────────────────────────────────────────────────────

class TextAnalysisRequest(BaseModel):
    text: str
    headline: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "The Reserve Bank of India maintained its benchmark repo rate at 6.5% citing inflation targets.",
                "headline": "RBI keeps repo rate unchanged at 6.5%"
            }
        }
    }


class ImageURLRequest(BaseModel):
    image_url: str
    caption: Optional[str] = None


class MultimodalRequest(BaseModel):
    text: str
    image_url: Optional[str] = None
    headline: Optional[str] = None


class FeedbackRequest(BaseModel):
    report_id: str
    is_accurate: bool
    correct_verdict: Optional[str] = None
    user_correction: Optional[str] = None


# ─── Output / Report Models ────────────────────────────────────────────────────

class Citation(BaseModel):
    title: str
    url: str
    source: str
    source_type: Optional[str] = "web"      # mainstream | local_news | youtube | fact_checker
    trust_score: Optional[int] = None


class LocalOrVideoSource(BaseModel):
    title: str
    url: str
    source: str
    source_type: Literal["local_news", "youtube", "regional_web"] = "local_news"
    snippet: Optional[str] = None


class ClaimItem(BaseModel):
    claim: str
    status: Literal["VERIFIED", "HALF_TRUE", "CONTRADICTED", "UNPROVEN"]
    confidence: float          # 0.0 – 1.0
    explanation: str
    citations: List[Citation] = Field(default_factory=list)


class MediaVerification(BaseModel):
    checked: bool
    # Task 1: Real vs. AI-Generated Detection
    authenticity_verdict: Literal[
        "REAL_PHOTO", "AI_GENERATED", "DIGITALLY_MANIPULATED", "UNKNOWN"
    ] = "UNKNOWN"
    ai_probability: int = 0                 # 0 – 100% probability of AI generation
    forensic_analysis: List[str] = Field(default_factory=list)

    # Task 2: Incident, Location & Timeline Identification (If Real)
    related_incident: Optional[str] = None
    location_taken: Optional[str] = None
    incident_date: Optional[str] = None
    incident_details: Optional[str] = None

    # Context-Hijack & Provenance Fields
    earliest_found_year: Optional[int] = None
    original_context: Optional[str] = None
    is_context_hijacked: bool = False
    discrepancy_details: Optional[str] = None
    warning_message: Optional[str] = None
    matched_from_memory: bool = False
    discovered_sources: List[Citation] = Field(default_factory=list)


class NarrativePerspective(BaseModel):
    label: str          # e.g. "Viral Social Claim", "Mainstream & Local Press", "Official & Scientific Record"
    summary: str
    source_urls: List[str] = Field(default_factory=list)


class NarrativeMatrix(BaseModel):
    perspectives: List[NarrativePerspective]
    consensus_verdict: str


class LearningMetadata(BaseModel):
    recalled_facts_count: int = 0
    recalled_facts_preview: List[str] = Field(default_factory=list)
    tracked_sources_used: int = 0
    learned_from_this_run: bool = True
    total_learned_facts: int = 0
    total_tracked_sources: int = 0
    total_learned_images: int = 0


class TrustReport(BaseModel):
    id: str
    overall_verdict: Literal[
        "AUTHENTIC", "HALF_TRUTH", "MOSTLY_TRUE", "MISLEADING",
        "CONTRADICTED", "CONTEXT_HIJACKED", "AI_GENERATED_IMAGE",
        "UNVERIFIED", "SATIRE_LIKELY"
    ]
    credibility_score: int          # 0 – 100
    sensationalism_score: int       # 1 – 10

    # Deep News Explanation & Half-Truth / Science Analysis
    coverage_level: Literal[
        "HIGH_MAINSTREAM", "LOW_INTERNET_LOCAL_VERIFIED", "MINIMAL_OR_NONE"
    ] = "HIGH_MAINSTREAM"
    full_news_explanation: Optional[str] = None
    facts_and_science_analysis: Optional[str] = None

    # Half-Truth / Partial Story Specifics
    is_half_truth: bool = False
    what_is_true: Optional[str] = None
    missing_context_full_story: Optional[str] = None
    reader_impact_warning: Optional[str] = None

    # Local News & YouTube Deep Discovery
    local_and_youtube_sources: List[LocalOrVideoSource] = Field(default_factory=list)

    # Atomic Claims, Media, Matrix & Self-Learning
    claims: List[ClaimItem] = Field(default_factory=list)
    media_verification: Optional[MediaVerification] = None
    narrative_matrix: Optional[NarrativeMatrix] = None
    learning_metadata: Optional[LearningMetadata] = None
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
    self_learning_active: bool = True
