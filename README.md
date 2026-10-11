# VeriLens 🛡️
### *AI-Powered Multimodal Disinformation & Context-Hijack Detector*

---

## What It Does

VeriLens detects fake news and disinformation through three unique modes:

| Mode | What It Checks |
|------|---------------|
| **Text / Headline** | Extracts atomic claims, live fact-checks them, scores sensationalism |
| **Image Check** | Detects if an authentic image is recycled/out-of-context (context hijack) |
| **Multimodal** | Combined text + image analysis in one unified trust report |

---

## Quick Start (One Click)

### Option A: Double-click to Launch
```
double-click start.bat
```
This auto-installs all dependencies and starts the server.

### Option B: Manual Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open: **http://127.0.0.1:8000**

---

## Getting Your Free Gemini API Key

1. Go to **https://aistudio.google.com/**
2. Sign in with Gmail → Click **"Get API Key"**
3. Copy the key into `backend/.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```

> **Without a key:** The app still works in fallback/rule-based mode.

---

## Project Structure

```
verilens/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI routes
│   │   ├── config.py               # API key management
│   │   ├── models/schemas.py       # Data models
│   │   ├── services/
│   │   │   ├── claim_extractor.py  # NLP claim decomposition (Gemini)
│   │   │   ├── fact_checker.py     # Live fact-check (DuckDuckGo + Gemini)
│   │   │   ├── image_verifier.py   # Context-hijack detection (EXIF + hash)
│   │   │   └── narrative_matrix.py # 360° perspective + scoring
│   │   └── database/               # SQLite history
│   └── requirements.txt
├── frontend/
│   ├── index.html                  # Dashboard UI
│   ├── app.js                      # Frontend logic
│   └── styles.css                  # Custom styles
├── tests/test_pipeline.py          # Unit tests
└── start.bat                       # One-click launcher
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze-text` | Analyze news text/headline |
| `POST` | `/api/analyze-image` | Verify image context |
| `POST` | `/api/analyze-multimodal` | Text + image combined |
| `GET`  | `/api/history` | Recent analyses |
| `GET`  | `/health` | API status |
| `GET`  | `/api/docs` | Interactive Swagger UI |

---

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy (SQLite)
- **AI / NLP:** Google Gemini 1.5 Flash (free tier)
- **Search:** DuckDuckGo Search (zero API keys)
- **Vision:** Pillow, imagehash (EXIF + perceptual hashing)
- **Frontend:** HTML5, Tailwind CSS, Vanilla JS

> **Total cost: $0** – 100% free stack.

---

## Running Tests

```bash
cd backend
venv\Scripts\activate
pytest ../tests/test_pipeline.py -v
```

---

*Minor Project — Built with Python & Google Gemini · VeriLens*
