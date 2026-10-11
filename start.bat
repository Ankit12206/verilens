@echo off
echo.
echo  ===========================================
echo   VeriLens - AI Disinformation Detector
echo  ===========================================
echo.

cd /d "%~dp0backend"

:: Check if venv exists, create it if not
if not exist "venv" (
    echo [1/3] Creating Python virtual environment...
    python -m venv venv
)

:: Activate virtual environment
echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

:: Check if packages are installed
python -c "import fastapi" 2>nul
if %errorlevel% neq 0 (
    echo [3/3] Installing dependencies (first time only, please wait)...
    pip install -r requirements.txt
) else (
    echo [3/3] Dependencies already installed.
)

:: Check for .env file
if not exist ".env" (
    echo.
    echo [!] WARNING: .env file not found!
    echo     Copy .env.example to .env and add your GEMINI_API_KEY
    echo     The app will still work in fallback mode without it.
    echo.
    copy .env.example .env
)

echo.
echo  Starting VeriLens API server...
echo  Dashboard: http://127.0.0.1:8000
echo  API Docs:  http://127.0.0.1:8000/api/docs
echo.
echo  Press Ctrl+C to stop the server.
echo.

:: Start the FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
