#!/bin/bash

# THINK eLearn CI/CD Setup Script
# Sets up the complete development and testing environment

set -e

echo "🚀 Setting up THINK eLearn CI/CD environment..."

# Check for required tools
echo "📋 Checking dependencies..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required"
    exit 1
fi

# Check uv
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required for CSS builds"
    exit 1
fi

echo "✅ All dependencies available"

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
uv sync --all-extras

# Install Node.js dependencies  
echo "📦 Installing Node.js dependencies..."
npm ci

# Build CSS
echo "🎨 Building CSS..."
npm run build-css-prod

# Run tests to verify setup
echo "🧪 Running test suite..."
uv run pytest --tb=short -q

# Run linting
echo "🔍 Running code quality checks..."
uv run ruff check .
uv run ruff format --check .

echo ""
echo "🎉 CI/CD setup complete!"
echo ""
echo "Available commands:"
echo "  pytest                    # Run test suite"
echo "  pytest --cov              # Run tests with coverage"
echo "  uv run ruff check .       # Lint code"
echo "  uv run ruff format .      # Format code"
echo "  uv run mypy .             # Type checking"
echo "  uv run safety scan        # Security check"
echo "  uv run bandit -r .        # Security linting"
echo ""
echo "🔧 Next steps:"
echo "1. Set up GitHub repository and push code"
echo "2. Enable GitHub Actions (automatic)"
echo "3. Connect Railway to GitHub repository"
echo "4. Configure environment variables in Railway"
echo "5. Deploy! 🚀"
