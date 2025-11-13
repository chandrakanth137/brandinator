#!/bin/bash
# Installation script for Brand Extraction Agent

set -e  # Exit on error

echo "=========================================="
echo "Brand Extraction Agent - Installation"
echo "=========================================="
echo ""

# Check if Python 3.11+ is installed
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python 3.11+ is required. Found: Python $PYTHON_VERSION"
    exit 1
fi

echo "✓ Python $PYTHON_VERSION found"
echo ""

# Check if uv is installed
echo "Checking uv package manager..."
if ! command -v uv &> /dev/null; then
    echo "⚠ uv is not installed. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    if ! command -v uv &> /dev/null; then
        echo "❌ Failed to install uv. Please install manually: https://github.com/astral-sh/uv"
        exit 1
    fi
    echo "✓ uv installed successfully"
else
    echo "✓ uv is already installed"
fi
echo ""

# Install project dependencies
echo "Installing project dependencies..."
uv sync
echo "✓ Dependencies installed"
echo ""

# Install Playwright browsers
echo "Installing Playwright browsers..."
uv run playwright install chromium
echo "✓ Playwright browsers installed"
echo ""

# Check for .env file
echo "Checking environment variables..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "⚠ .env file not found. Creating from .env.example..."
        cp .env.example .env
        echo "✓ .env file created from .env.example"
        echo ""
        echo "⚠ IMPORTANT: Please edit .env and add your API key:"
        echo "   - GEMINI_API_KEY"
        echo ""
        echo "   Get your API key from: https://aistudio.google.com/app/apikey"
    else
        echo "⚠ .env.example not found. Please create .env file manually with:"
        echo "   GEMINI_API_KEY=your_key_here"
    fi
else
    echo "✓ .env file exists"
fi
echo ""

# Make run scripts executable
echo "Making run scripts executable..."
chmod +x run_backend.sh
chmod +x run_frontend.sh
chmod +x install.sh
echo "✓ Run scripts are executable"
echo ""

echo "=========================================="
echo "✓ Installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your API key (GEMINI_API_KEY)"
echo "2. Run the backend: ./run_backend.sh"
echo "3. Run the frontend: ./run_frontend.sh (in another terminal)"
echo ""

