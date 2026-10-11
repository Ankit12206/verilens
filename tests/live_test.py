import requests

print("=" * 55)
print("  VeriLens - Live End-to-End Test")
print("=" * 55)

# Test 1: Health check
r = requests.get("http://127.0.0.1:8000/health")
h = r.json()
print("\n[1] Health Check:")
print("  Status       :", h["status"])
print("  Gemini       :", h["gemini_available"])
print("  DuckDuckGo   :", h["duckduckgo_available"])

# Test 2: Fake viral rumor
print("\n[2] Analyzing Viral Rumor (this may take 20-40 seconds)...")
r2 = requests.post(
    "http://127.0.0.1:8000/api/analyze-text",
    json={
        "text": "BREAKING: Government has secretly banned all private vehicles starting Monday. Police will seize cars from tomorrow!"
    },
    timeout=120
)

if r2.status_code != 200:
    print("  ERROR:", r2.status_code, r2.text[:300])
else:
    d = r2.json()
    print("  Verdict          :", d["overall_verdict"])
    print("  Credibility Score:", d["credibility_score"], "/ 100")
    print("  Sensationalism   :", d["sensationalism_score"], "/ 10")
    print("  Claims extracted :", len(d["claims"]))
    for c in d["claims"]:
        status = c["status"]
        claim  = c["claim"][:70]
        print("    [" + status + "] " + claim)
    print("  Summary:", d["summary_explanation"][:150])

print()
print("=" * 55)
print("  TEST COMPLETE")
print("=" * 55)
