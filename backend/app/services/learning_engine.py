"""
VeriLens 2.0 – Self-Learning & Continuous Accuracy Engine
Enables VeriLens to learn and improve accuracy after every single analysis:
  1. Episodic Fact & Context Memory (Continuous RAG)
  2. Dynamic Source & YouTube Channel Reputation Learning
  3. Perceptual Hash (pHash) Visual Fingerprint Memory
  4. Human-in-the-Loop Feedback & Correction Learning (RLHF)
"""
import json
import re
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from app.database.models import (
    AnalysisRecord,
    LearnedFactMemory,
    SourceReputation,
    ImageFingerprintMemory
)
from app.models.schemas import TrustReport, LearningMetadata, FeedbackRequest


STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "has", "had",
    "was", "were", "are", "is", "been", "being", "into", "over", "after",
    "before", "about", "between", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "only", "own",
    "same", "than", "too", "very", "can", "will", "just", "should", "now",
    "news", "breaking", "report", "reports", "said", "says", "today", "yesterday"
}


def extract_keywords(text: str) -> List[str]:
    """Extracts normalized, meaningful keywords/entities from text."""
    if not text:
        return []
    words = re.findall(r"[a-zA-Z0-9]{3,}", text.lower())
    seen = set()
    keywords = []
    for w in words:
        if w not in STOPWORDS and w not in seen:
            seen.add(w)
            keywords.append(w)
    return keywords[:25]


# ─── 1. Episodic Fact Memory Recall (RAG) ─────────────────────────────────────

def recall_relevant_knowledge(text: str, db: Optional[Session]) -> Dict:
    """
    Searches the LearnedFactMemory table for previously verified facts,
    half-truth contexts, or user corrections that match the current input.
    """
    if db is None or not text:
        return {"matches": [], "prompt_context": "", "highest_similarity": 0.0}

    query_kws = set(extract_keywords(text))
    if not query_kws:
        return {"matches": [], "prompt_context": "", "highest_similarity": 0.0}

    try:
        all_memories = db.query(LearnedFactMemory).order_by(
            LearnedFactMemory.user_confirmed.desc(),
            LearnedFactMemory.updated_at.desc()
        ).limit(200).all()

        scored_matches = []
        for mem in all_memories:
            mem_kws = set((mem.topic_keywords or "").split())
            if not mem_kws:
                continue
            overlap = query_kws.intersection(mem_kws)
            if not overlap:
                continue

            # Jaccard + coverage score, boosted if human-confirmed
            sim = len(overlap) / max(1, min(len(query_kws), len(mem_kws)))
            if mem.user_confirmed:
                sim = min(1.0, sim * 1.25)

            if len(overlap) >= 2 and sim >= 0.35:
                scored_matches.append((sim, mem))

        scored_matches.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_matches[:3]

        matches_data = []
        prompt_lines = []
        highest_sim = 0.0

        for sim, mem in top_matches:
            highest_sim = max(highest_sim, sim)
            mem.times_recalled = (mem.times_recalled or 0) + 1
            tag = "[HUMAN-VERIFIED CORRECTION]" if mem.user_confirmed else "[LEARNED MEMORY]"
            matches_data.append({
                "id": mem.id,
                "claim_summary": mem.claim_summary,
                "learned_verdict": mem.learned_verdict,
                "confidence": mem.confidence,
                "full_truth_context": mem.full_truth_context,
                "science_fact_notes": mem.science_fact_notes,
                "reader_impact": mem.reader_impact,
                "user_confirmed": mem.user_confirmed,
                "similarity": round(sim, 2)
            })
            prompt_lines.append(
                f"- {tag} (Match {int(sim*100)}%, Verdict: {mem.learned_verdict}): "
                f"Claim='{mem.claim_summary[:180]}' | Full Truth='{mem.full_truth_context or ''}' | "
                f"Science/Facts='{mem.science_fact_notes or ''}'"
            )

        if top_matches:
            db.commit()

        prompt_context = "\n".join(prompt_lines) if prompt_lines else "No prior learned memory for this specific topic."
        return {
            "matches": matches_data,
            "prompt_context": prompt_context,
            "highest_similarity": highest_sim
        }
    except Exception as e:
        print(f"[LearningEngine] Memory recall error: {e}")
        return {"matches": [], "prompt_context": "", "highest_similarity": 0.0}


# ─── 2. Perceptual Image Fingerprint Memory ───────────────────────────────────

def _hamming_distance(hash1: str, hash2: str) -> int:
    """Computes bit-level Hamming distance between two hex pHash strings."""
    try:
        if not hash1 or not hash2 or len(hash1) != len(hash2):
            return 999
        return bin(int(hash1, 16) ^ int(hash2, 16)).count("1")
    except Exception:
        return 999


def recall_image_memory(phash_str: str, db: Optional[Session]) -> Optional[Dict]:
    """
    Checks if an image (or a cropped/compressed version of it, Hamming distance <= 6)
    has already been analyzed and learned in ImageFingerprintMemory.
    """
    if db is None or not phash_str:
        return None
    try:
        memories = db.query(ImageFingerprintMemory).order_by(
            ImageFingerprintMemory.user_confirmed.desc(),
            ImageFingerprintMemory.created_at.desc()
        ).limit(300).all()

        for mem in memories:
            dist = _hamming_distance(phash_str, mem.phash)
            if dist <= 6:
                mem.times_matched = (mem.times_matched or 1) + 1
                db.commit()
                forensic_list = []
                if mem.forensic_json:
                    try:
                        forensic_list = json.loads(mem.forensic_json)
                    except Exception:
                        forensic_list = []
                return {
                    "authenticity_verdict": mem.authenticity_verdict,
                    "ai_probability": mem.ai_probability,
                    "related_incident": mem.related_incident,
                    "location_taken": mem.location_taken,
                    "incident_date": mem.incident_date,
                    "incident_details": mem.incident_details,
                    "forensic_analysis": forensic_list,
                    "hamming_distance": dist,
                    "times_matched": mem.times_matched
                }
    except Exception as e:
        print(f"[LearningEngine] Image memory recall error: {e}")
    return None


# ─── 3. Dynamic Source Reputation Learning ────────────────────────────────────

def get_learned_source_trust(domain: str, db: Optional[Session]) -> Tuple[int, bool]:
    """
    Returns (trust_score_0_to_100, is_tracked_in_db) for a given domain.
    """
    if not domain or db is None:
        return (70, False)
    try:
        clean_dom = domain.lower().strip()
        rec = db.query(SourceReputation).filter(SourceReputation.domain == clean_dom).first()
        if rec:
            return (int(round(rec.learned_trust_score)), True)
    except Exception:
        pass
    return (70, False)


def _update_source_reputation(
    domain: str,
    source_type: str,
    overall_verdict: str,
    db: Session
):
    """Updates a domain's reputation based on the analysis outcome."""
    if not domain:
        return
    clean_dom = domain.lower().strip()
    rec = db.query(SourceReputation).filter(SourceReputation.domain == clean_dom).first()
    if not rec:
        rec = SourceReputation(
            domain=clean_dom,
            source_type=source_type or "web",
            verified_count=0,
            half_truth_count=0,
            fake_count=0,
            learned_trust_score=75.0
        )
        db.add(rec)

    if overall_verdict in ("AUTHENTIC", "MOSTLY_TRUE"):
        rec.verified_count = (rec.verified_count or 0) + 1
        rec.learned_trust_score = min(99.0, (rec.learned_trust_score or 75.0) + 2.0)
    elif overall_verdict in ("HALF_TRUTH", "MISLEADING"):
        rec.half_truth_count = (rec.half_truth_count or 0) + 1
        # Sources used to expose a half-truth are still helpful corroborators
        rec.learned_trust_score = min(98.0, (rec.learned_trust_score or 75.0) + 1.0)
    elif overall_verdict in ("CONTRADICTED", "CONTEXT_HIJACKED", "AI_GENERATED_IMAGE"):
        # Fact-checker/news sources that helped debunk fake news gain trust
        rec.verified_count = (rec.verified_count or 0) + 1
        rec.learned_trust_score = min(98.0, (rec.learned_trust_score or 75.0) + 1.5)


# ─── 4. Post-Analysis Self-Learning Writeback ─────────────────────────────────

def learn_from_analysis(
    report: TrustReport,
    input_text: Optional[str],
    phash_str: Optional[str],
    recalled_info: Optional[Dict],
    db: Optional[Session]
) -> LearningMetadata:
    """
    Stores the newly discovered truth, context, source reputations, and image
    fingerprint into SQLite so VeriLens becomes smarter for the next query.
    """
    if db is None:
        return LearningMetadata()

    try:
        # A. Learn Fact & Context Memory (if text or multimodal)
        seed_text = input_text or report.full_news_explanation or report.summary_explanation or ""
        kws = extract_keywords(seed_text)
        if kws and report.overall_verdict != "UNVERIFIED":
            kw_str = " ".join(kws)
            mem = LearnedFactMemory(
                report_id=report.id,
                topic_keywords=kw_str,
                claim_summary=(input_text or report.summary_explanation)[:500],
                learned_verdict=report.overall_verdict,
                confidence=report.credibility_score / 100.0,
                full_truth_context=(
                    report.missing_context_full_story
                    or report.full_news_explanation
                    or report.summary_explanation
                )[:1200],
                science_fact_notes=(report.facts_and_science_analysis or "")[:1000],
                reader_impact=(report.reader_impact_warning or "")[:800],
                user_confirmed=False
            )
            db.add(mem)

        # B. Update Source Reputations for all cited domains & YouTube channels
        tracked_used = 0
        seen_domains = set()
        for claim in report.claims:
            for cit in claim.citations:
                if cit.source and cit.source not in seen_domains:
                    seen_domains.add(cit.source)
                    _update_source_reputation(cit.source, cit.source_type or "web", report.overall_verdict, db)
                    tracked_used += 1

        for loc_src in report.local_and_youtube_sources:
            if loc_src.source and loc_src.source not in seen_domains:
                seen_domains.add(loc_src.source)
                _update_source_reputation(loc_src.source, loc_src.source_type, report.overall_verdict, db)
                tracked_used += 1

        # C. Learn Image Fingerprint Memory (if image was analyzed)
        if phash_str and report.media_verification and report.media_verification.checked:
            mv = report.media_verification
            existing_img = db.query(ImageFingerprintMemory).filter(
                ImageFingerprintMemory.phash == phash_str
            ).first()
            if not existing_img and mv.authenticity_verdict != "UNKNOWN":
                img_mem = ImageFingerprintMemory(
                    phash=phash_str,
                    authenticity_verdict=mv.authenticity_verdict,
                    ai_probability=mv.ai_probability,
                    related_incident=mv.related_incident,
                    location_taken=mv.location_taken,
                    incident_date=mv.incident_date,
                    incident_details=mv.incident_details,
                    forensic_json=json.dumps(mv.forensic_analysis or []),
                    user_confirmed=False
                )
                db.add(img_mem)

        db.commit()

        # Gather updated totals
        total_facts = db.query(LearnedFactMemory).count()
        total_sources = db.query(SourceReputation).count()
        total_images = db.query(ImageFingerprintMemory).count()

        recalled_matches = (recalled_info or {}).get("matches", [])
        recalled_preview = [
            f"{m['learned_verdict']}: {m['claim_summary'][:90]}..."
            for m in recalled_matches
        ]

        return LearningMetadata(
            recalled_facts_count=len(recalled_matches),
            recalled_facts_preview=recalled_preview,
            tracked_sources_used=tracked_used,
            learned_from_this_run=True,
            total_learned_facts=total_facts,
            total_tracked_sources=total_sources,
            total_learned_images=total_images
        )
    except Exception as e:
        print(f"[LearningEngine] Writeback error: {e}")
        return LearningMetadata()


# ─── 5. Human-in-the-Loop Feedback & Correction (RLHF) ────────────────────────

def apply_user_feedback(req: FeedbackRequest, db: Session) -> Dict:
    """
    Applies explicit user confirmation or correction to the Self-Learning Memory Bank.
    When a user corrects a verdict or adds missing facts, VeriLens permanently prioritizes
    that human lesson on future queries.
    """
    mem = db.query(LearnedFactMemory).filter(LearnedFactMemory.report_id == req.report_id).first()
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == req.report_id).first()

    if mem:
        mem.user_confirmed = True
        if req.is_accurate:
            mem.confidence = 0.98
        else:
            if req.correct_verdict:
                mem.learned_verdict = req.correct_verdict
            if req.user_correction:
                mem.full_truth_context = f"[User Verified Correction]: {req.user_correction} | {mem.full_truth_context or ''}"
            mem.confidence = 0.99
    elif record:
        kws = extract_keywords(record.input_text or record.summary_explanation or "")
        new_mem = LearnedFactMemory(
            report_id=req.report_id,
            topic_keywords=" ".join(kws),
            claim_summary=(record.input_text or record.summary_explanation)[:500],
            learned_verdict=req.correct_verdict or record.overall_verdict,
            confidence=0.99,
            full_truth_context=req.user_correction or record.summary_explanation,
            user_confirmed=True
        )
        db.add(new_mem)

    db.commit()
    stats = get_learning_stats(db)
    return {
        "status": "learned",
        "message": "Thank you! VeriLens has permanently added this lesson to its Self-Learning Memory Bank.",
        "stats": stats
    }


def get_learning_stats(db: Session) -> Dict:
    """Returns current statistics of the Self-Learning Memory Bank."""
    try:
        return {
            "total_learned_facts": db.query(LearnedFactMemory).count(),
            "human_verified_facts": db.query(LearnedFactMemory).filter(LearnedFactMemory.user_confirmed == True).count(),
            "total_tracked_sources": db.query(SourceReputation).count(),
            "total_learned_images": db.query(ImageFingerprintMemory).count(),
            "total_analyses_run": db.query(AnalysisRecord).count()
        }
    except Exception:
        return {
            "total_learned_facts": 0,
            "human_verified_facts": 0,
            "total_tracked_sources": 0,
            "total_learned_images": 0,
            "total_analyses_run": 0
        }
