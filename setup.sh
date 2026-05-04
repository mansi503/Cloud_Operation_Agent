#!/bin/bash
# Cloud Operation Agent - Setup Script for macOS/Linux

echo ""
echo "============================================"
echo "Cloud Operation Agent - Setup"
echo "============================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+ first."
    exit 1
fi

echo "✅ Python found"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "⚠️  uv not found. Installing uv..."
    pip install uv
    echo "✅ uv installed"
else
    echo "✅ uv found"
fi
echo ""

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    uv venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Install dependencies
echo "📚 Installing dependencies..."
uv sync
echo "✅ Dependencies installed"
echo ""

# Create .env from .env.example
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env created. Please edit it with your credentials."
else
    echo "✅ .env already exists"
fi
echo ""

echo ""
echo "============================================"
echo "✅ Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Edit .env with your credentials"
echo "2. Run: streamlit run ui.py"
echo ""
