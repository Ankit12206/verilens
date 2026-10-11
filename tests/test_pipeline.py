# encoding: utf-8
"""
VeriLens - Automated Test Suite
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


# ── Test 4: Image verifier returns proper structure ───────────────────────────
def test_image_verifier_returns_structure():
    from app.services.image_verifier import verify_image
    result = verify_image(
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Fronalpstock_big.jpg/800px-Fronalpstock_big.jpg"
    )
    assert "checked" in result, "Result should have 'checked' field"
    assert "is_context_hijacked" in result, "Result should have 'is_context_hijacked' field"
    print(f"  Image checked: {result['checked']}, hijacked: {result['is_context_hijacked']}")


# ── Test 5: Image verifier handles missing input gracefully ───────────────────
def test_image_verifier_no_image():
    from app.services.image_verifier import verify_image
    result = verify_image()
    assert result["checked"] == False, "Should not be checked without input"
    print("  Handles missing image gracefully")


# ── Test 6: Credibility score is high when all claims verified ────────────────
def test_credibility_score_with_verified_claims():
    from app.services.narrative_matrix import calculate_credibility_score
    from app.models.schemas import ClaimItem
    claims = [
        ClaimItem(claim="Test", status="VERIFIED", confidence=0.9, explanation="", citations=[]),
        ClaimItem(claim="Test2", status="VERIFIED", confidence=0.85, explanation="", citations=[]),
    ]
    score = calculate_credibility_score(claims, sensationalism_score=2, media_check=None)
    assert score >= 60, f"All-verified claims should score >=60, got {score}"
    print(f"  Credibility score (all verified, low sens): {score}/100")


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


# ── Test 8: Context hijack always returns CONTEXT_HIJACKED verdict ────────────
def test_credibility_score_context_hijacked():
    from app.services.narrative_matrix import calculate_credibility_score, determine_verdict
    from app.models.schemas import ClaimItem, MediaVerification
    claims = [ClaimItem(claim="Test", status="UNPROVEN", confidence=0.5, explanation="", citations=[])]
    media = MediaVerification(checked=True, is_context_hijacked=True, discrepancy_details="Image from 2019")
    score = calculate_credibility_score(claims, sensationalism_score=5, media_check=media)
    verdict = determine_verdict(score, media)
    assert verdict == "CONTEXT_HIJACKED", f"Should be CONTEXT_HIJACKED, got {verdict}"
    print(f"  Context hijack verdict correctly assigned: {verdict}")


# ── Test 9: DuckDuckGo live search returns results ────────────────────────────
def test_live_search_returns_results():
    from app.services.fact_checker import live_search
    results = live_search("India inflation rate 2024", max_results=3)
    assert isinstance(results, list), "Should return a list"
    print(f"  DuckDuckGo search returned {len(results)} results")


# ── Main Runner ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  VeriLens Automated Test Suite")
    print("="*55)

    tests = [
        test_claim_extractor_returns_structure,
        test_claim_extractor_sensationalism_for_clickbait,
        test_claim_extractor_low_sensationalism_for_factual,
        test_image_verifier_returns_structure,
        test_image_verifier_no_image,
        test_credibility_score_with_verified_claims,
        test_credibility_score_with_contradicted_claims,
        test_credibility_score_context_hijacked,
        test_live_search_returns_results
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

    print(f"\n{'='*55}")
    print(f"  Results: {passed} PASSED | {failed} FAILED out of {len(tests)} tests")
    print("="*55)
    sys.exit(0 if failed == 0 else 1)
