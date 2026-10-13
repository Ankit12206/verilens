"""
VeriLens Database Models
SQLAlchemy ORM table definitions for persisting analysis history and
the 4-layer Self-Learning Memory System (Episodic Facts, Source Reputation,
and Image Fingerprint Memory).
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database.db import Base


class AnalysisRecord(Base):
    """Stores every analysis request and its final trust report for history."""
    __tablename__ = "analysis_history"

    id                   = Column(String, primary_key=True, index=True)
    input_type           = Column(String, nullable=False)          # text | image | multimodal
    input_text           = Column(Text, nullable=True)
    image_url            = Column(String, nullable=True)
    overall_verdict      = Column(String, nullable=False)
    credibility_score    = Column(Integer, nullable=False)
    sensationalism_score = Column(Integer, nullable=False)
    summary_explanation  = Column(Text, nullable=False)
    raw_report_json      = Column(Text, nullable=False)            # full JSON for reconstruction
    created_at           = Column(DateTime(timezone=True), server_default=func.now())


class LearnedFactMemory(Base):
    """
    Episodic Knowledge Memory Bank (Self-Learning RAG).
    Stores verified facts, missing context for half-truths, scientific reasoning,
    and user corrections so future related analyses become progressively more accurate.
    """
    __tablename__ = "learned_fact_memory"

    id                   = Column(Integer, primary_key=True, autoincrement=True, index=True)
    report_id            = Column(String, nullable=True, index=True)
    topic_keywords       = Column(String, nullable=False, index=True)  # space-separated normalized keywords
    claim_summary        = Column(Text, nullable=False)
    learned_verdict      = Column(String, nullable=False)              # AUTHENTIC | HALF_TRUTH | CONTRADICTED | etc.
    confidence           = Column(Float, default=0.85)
    full_truth_context   = Column(Text, nullable=True)                 # Complete story / missing context
    science_fact_notes   = Column(Text, nullable=True)                 # Scientific/factual explanation
    reader_impact        = Column(Text, nullable=True)                 # Impact warning
    user_confirmed       = Column(Boolean, default=False)              # True if human explicitly confirmed/corrected
    times_recalled       = Column(Integer, default=0)
    updated_at           = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SourceReputation(Base):
    """
    Dynamic Source Reputation Learner.
    Tracks domains and YouTube channels encountered during verification and
    maintains a learned trust score (0-100) that evolves after every analysis.
    """
    __tablename__ = "source_reputation"

    domain               = Column(String, primary_key=True, index=True)
    source_type          = Column(String, default="web")               # web | local_news | youtube | fact_checker
    verified_count       = Column(Integer, default=0)
    half_truth_count     = Column(Integer, default=0)
    fake_count           = Column(Integer, default=0)
    learned_trust_score  = Column(Float, default=70.0)                 # 0.0 to 100.0
    updated_at           = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ImageFingerprintMemory(Base):
    """
    Visual Fingerprint Memory Bank.
    Stores 64-bit Perceptual Hashes (pHash), AI vs. Real forensics, and
    Incident + Location details so repeat/cropped uploads are recognized instantly.
    """
    __tablename__ = "image_fingerprint_memory"

    id                   = Column(Integer, primary_key=True, autoincrement=True, index=True)
    phash                = Column(String, nullable=False, index=True)
    authenticity_verdict = Column(String, nullable=False)              # REAL_PHOTO | AI_GENERATED | DIGITALLY_MANIPULATED
    ai_probability       = Column(Integer, default=0)                  # 0 - 100
    related_incident     = Column(String, nullable=True)
    location_taken       = Column(String, nullable=True)
    incident_date        = Column(String, nullable=True)
    incident_details     = Column(Text, nullable=True)
    forensic_json        = Column(Text, nullable=True)
    user_confirmed       = Column(Boolean, default=False)
    times_matched        = Column(Integer, default=1)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
