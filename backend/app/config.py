"""
VeriLens Configuration Module
Loads environment variables from .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── AI & Search ──────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
GOOGLE_FACT_CHECK_API_KEY: str = os.getenv("GOOGLE_FACT_CHECK_API_KEY", "")

# ─── Feature Flags ────────────────────────────────────────────────────────────
USE_GEMINI: bool = bool(GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here")
USE_SERPAPI: bool = bool(SERPAPI_KEY)
USE_GOOGLE_FACT_CHECK: bool = bool(GOOGLE_FACT_CHECK_API_KEY)

# ─── Server ────────────────────────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
