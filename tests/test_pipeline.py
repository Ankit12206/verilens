# encoding: utf-8
"""
VeriLens 2.0 - Automated Test Suite
Run with: python tests/test_pipeline.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


# ── Test 1: Claim Extractor returns correct structure ─────────────────────────
def test_claim_extractor_returns_structure():
    from app.services.claim_extractor import extract_claims
    result = extract_claims("BREAKING: A massive earthquake hit Tokyo today killing 500 people.")
    assert "claims" in result, "Should return claims list"
    assert "sensationalism_score" in result, "Should return sensationalism score"
    assert isinstance(result["claims"], list), "claims should be a list"
    assert len(result["claims"]) >= 1, "Should extract at least 1 claim"
    print(f"  Claims: {[c['claim'][:60] for c in result['claims']]}")
    print(f"  Sensationalism score: {result['sensationalism_score']}/10")


# ── Test 2: Clickbait scores high on sensationalism ──────────────────────────
def test_claim_extractor_sensationalism_for_clickbait():
    from app.services.claim_extractor import extract_claims
    clickbait = "SHOCKING BOMBSHELL! Doctors HORRIFIED by this deadly secret they don't want you to know!!!"
    result = extract_claims(clickbait)
    score = result["sensationalism_score"]
    assert score >= 6, f"Clickbait should score >=6 but got {score}"
    print(f"  Clickbait sensationalism score: {score}/10")


# ── Test 3: Factual news scores low on sensationalism ─────────────────────────
def test_claim_extractor_low_sensationalism_for_factual():
    from app.services.claim_extractor import extract_claims
    factual = "The central bank maintained the interest rate at 6.5% following its quarterly review."
    result = extract_claims(factual)
    score = result["sensationalism_score"]
    assert score <= 5, f"Factual news should score <=5 but got {score}"
    print(f"  Factual sensationalism score: {score}/10")


# ── Test 4: Image verifier returns proper VeriLens 2.0 structure ─────────────
def test_image_verifier_returns_structure():
    from PIL import Image
    import io
    from app.services.image_verifier import verify_image

    # Create a valid in-memory test image so network thumbnails never 400
    img = Image.new("RGB", (320, 240), color=(40, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    result = verify_image(image_bytes=buf.getvalue(), caption="Test blue sky photo")

    assert result["checked"] is True, "Result should be checked"
    assert "is_context_hijacked" in result, "Result should have 'is_context_hijacked' field"
    assert "authenticity_verdict" in result, "Result should have 'authenticity_verdict' (REAL_PHOTO vs AI_GENERATED)"
    assert "related_incident" in result, "Result should have 'related_incident'"
    assert "location_taken" in result, "Result should have 'location_taken'"
    print(f"  Image checked: {result['checked']}, verdict: {result['authenticity_verdict']}, incident: {result['related_incident']}")


# ── Test 5: Image verifier handles missing input gracefully ───────────────────
def test_image_verifier_no_image():
    from app.services.image_verifier import verify_image
    result = verify_image()
    assert result["checked"] is False, "Should not be checked without input"
    print("  Handles missing image gracefully")


# ── Test 6: Real verified news scores high (85-98, no more 61-62 bug!) ───────
def test_credibility_score_with_verified_claims():
    from app.services.narrative_matrix import calculate_credibility_score, determine_verdict
    from app.models.schemas import ClaimItem
    claims = [
        ClaimItem(claim="Test", status="VERIFIED", confidence=0.92, explanation="", citations=[]),
        ClaimItem(claim="Test2", status="VERIFIED", confidence=0.88, explanation="", citations=[]),
    ]
    score = calculate_credibility_score(claims, sensationalism_score=2, media_check=None)
    verdict = determine_verdict(score, None)
    assert score >= 85, f"Real verified claims should score >=85 (fixed 61-62 bug), got {score}"
    assert verdict == "AUTHENTIC", f"Should be AUTHENTIC, got {verdict}"
    print(f"  Credibility score (real verified news): {score}/100 ({verdict})")


# ── Test 7: Credibility score is low when all claims contradicted ─────────────
def test_credibility_score_with_contradicted_claims():
    from app.services.narrative_matrix import calculate_credibility_score
    from app.models.schemas import ClaimItem
    claims = [
        ClaimItem(claim="Test", status="CONTRADICTED", confidence=0.1, explanation="", citations=[]),
        ClaimItem(claim="Test2", status="CONTRADICTED", confidence=0.1, explanation="", citations=[]),
    ]
    score = calculate_credibility_score(claims, sensationalism_score=9, media_check=None)
    assert score <= 30, f"All-contradicted + high sensationalism should score <=30, got {score}"
    print(f"  Credibility score (all contradicted, high sens): {score}/100")


# ── Test 8: Half-Truth ("True News, But Half") scores 46-68 & HALF_TRUTH ─────
def test_half_truth_scoring_and_verdict():
    from app.services.narrative_matrix import calculate_credibility_score, determine_verdict
    from app.models.schemas import ClaimItem
    claims = [
        ClaimItem(claim="Partial truth claim", status="HALF_TRUE", confidence=0.6, explanation="", citations=[]),
    ]
    score = calculate_credibility_score(
        claims,
        sensationalism_score=5,
        media_check=None,
        calibrated_ai_score=56
    )
    verdict = determine_verdict(
        score,
        media_check=None,
        is_half_truth=True,
        deep_verdict_type="HALF_TRUTH"
    )
    assert 46 <= score <= 68, f"Half-truth should score 46-68, got {score}"
    assert verdict == "HALF_TRUTH", f"Verdict should be HALF_TRUTH, got {verdict}"
    print(f"  Half-truth score: {score}/100, verdict: {verdict}")


# ── Test 9: Context hijack always returns CONTEXT_HIJACKED verdict ────────────
def test_credibility_score_context_hijacked():
    from app.services.narrative_matrix import calculate_credibility_score, determine_verdict
    from app.models.schemas import ClaimItem, MediaVerification
    claims = [ClaimItem(claim="Test", status="UNPROVEN", confidence=0.5, explanation="", citations=[])]
    media = MediaVerification(checked=True, is_context_hijacked=True, discrepancy_details="Image from 2019")
    score = calculate_credibility_score(claims, sensationalism_score=5, media_check=media)
    verdict = determine_verdict(score, media)
    assert verdict == "CONTEXT_HIJACKED", f"Should be CONTEXT_HIJACKED, got {verdict}"
    print(f"  Context hijack verdict correctly assigned: {verdict}")


# ── Test 10: DuckDuckGo & Local/YouTube search returns results ────────────────
def test_live_and_local_youtube_search():
    from app.services.fact_checker import live_search, search_youtube_and_local_news
    results = live_search("Reserve Bank of India interest rate", max_results=3)
    assert isinstance(results, list), "Should return a list"
    local_yt = search_youtube_and_local_news("Reserve Bank of India repo rate", max_results=4)
    assert isinstance(local_yt, list), "Local/YouTube search should return a list"
    print(f"  Web search returned {len(results)} results; Local/YouTube returned {len(local_yt)} results")


# ── Test 11: Self-Learning Engine stores & recalls facts ─────────────────────
def test_self_learning_engine():
    from datetime import datetime, timezone
    from app.database.db import init_db, SessionLocal
    from app.models.schemas import TrustReport, ClaimItem, Citation
    from app.services.learning_engine import learn_from_analysis, recall_relevant_knowledge, get_learning_stats

    init_db()
    db = SessionLocal()
    try:
        sample_text = "The Reserve Bank of India maintained its benchmark repo interest rate at 6.5% in its policy review."
        dummy_report = TrustReport(
            id="test-self-learn-001",
            overall_verdict="AUTHENTIC",
            credibility_score=94,
            sensationalism_score=1,
            coverage_level="HIGH_MAINSTREAM",
            full_news_explanation="The RBI Monetary Policy Committee kept the policy repo rate unchanged at 6.5%.",
            facts_and_science_analysis="Central banks use repo rates to control inflation and liquidity.",
            is_half_truth=False,
            claims=[
                ClaimItem(
                    claim=sample_text,
                    status="VERIFIED",
                    confidence=0.95,
                    explanation="Verified by RBI official press release.",
                    citations=[Citation(title="RBI MPC Statement", url="https://www.rbi.org.in", source="rbi.org.in")]
                )
            ],
            summary_explanation="Verified RBI news.",
            analyzed_at=datetime.now(timezone.utc),
            input_type="text"
        )
        meta = learn_from_analysis(dummy_report, sample_text, None, None, db)
        assert meta.learned_from_this_run is True, "Should record learning"

        recalled = recall_relevant_knowledge(sample_text, db)
        assert len(recalled["matches"]) >= 1, "Should recall learned fact on second check"
        assert recalled["matches"][0]["learned_verdict"] == "AUTHENTIC", "Recalled verdict should match"

        stats = get_learning_stats(db)
        assert stats["total_learned_facts"] >= 1, "Should have at least 1 learned fact in DB"
        print(f"  Self-Learning Engine verified: {stats['total_learned_facts']} facts, top similarity={recalled['highest_similarity']}")
    finally:
        db.close()


# ── Main Runner ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  VeriLens 2.0 Automated Test Suite")
    print("="*60)

    tests = [
        test_claim_extractor_returns_structure,
        test_claim_extractor_sensationalism_for_clickbait,
        test_claim_extractor_low_sensationalism_for_factual,
        test_image_verifier_returns_structure,
        test_image_verifier_no_image,
        test_credibility_score_with_verified_claims,
        test_credibility_score_with_contradicted_claims,
        test_half_truth_scoring_and_verdict,
        test_credibility_score_context_hijacked,
        test_live_and_local_youtube_search,
        test_self_learning_engine
    ]

    passed = failed = 0
    for test in tests:
        print(f"\n[TEST] {test.__name__}")
        try:
            test()
            print("  --> PASSED")
            passed += 1
        except Exception as e:
            print(f"  --> FAILED: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed} PASSED | {failed} FAILED out of {len(tests)} tests")
    print("="*60)
    sys.exit(0 if failed == 0 else 1)
