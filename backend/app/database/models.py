"""
VeriLens Database Models
SQLAlchemy ORM table definitions for persisting analysis history.
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database.db import Base


class AnalysisRecord(Base):
    """Stores every analysis request and its final trust report for history."""
    __tablename__ = "analysis_history"

    id              = Column(String, primary_key=True, index=True)
    input_type      = Column(String, nullable=False)          # text | image | multimodal
    input_text      = Column(Text, nullable=True)
    image_url       = Column(String, nullable=True)
    overall_verdict = Column(String, nullable=False)
    credibility_score    = Column(Integer, nullable=False)
    sensationalism_score = Column(Integer, nullable=False)
    summary_explanation  = Column(Text, nullable=False)
    raw_report_json      = Column(Text, nullable=False)       # full JSON for reconstruction
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
