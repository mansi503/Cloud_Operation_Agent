@echo off
REM Cloud Operation Agent - Setup Script for Windows

echo.
echo ============================================
echo Cloud Operation Agent - Setup
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.10+ first.
    pause
    exit /b 1
)

echo ✅ Python found
echo.

REM Check if uv is installed
uv --version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  uv not found. Installing uv...
    python -m pip install uv
    echo ✅ uv installed
) else (
    echo ✅ uv found
)
echo.

REM Create virtual environment
if not exist ".venv" (
    echo 📦 Creating virtual environment...
    uv venv .venv
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)
echo.

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call .\.venv\Scripts\activate.bat
echo ✅ Virtual environment activated
echo.

REM Install dependencies
echo 📚 Installing dependencies...
uv sync
echo ✅ Dependencies installed
echo.

REM Create .env from .env.example
if not exist ".env" (
    echo 📝 Creating .env file from template...
    copy .env.example .env
    echo ✅ .env created. Please edit it with your credentials.
) else (
    echo ✅ .env already exists
)
echo.

echo.
echo ============================================
echo ✅ Setup Complete!
echo ============================================
echo.
echo Next steps:
echo 1. Edit .env with your credentials
echo 2. Run: streamlit run ui.py
echo.
pause
