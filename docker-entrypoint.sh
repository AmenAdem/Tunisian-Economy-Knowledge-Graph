#!/bin/bash
set -e

echo "🚀 Starting Tunisian Economy Knowledge Graph Backend..."

# Check if spaCy models are installed
echo "📦 Checking spaCy models..."

if ! python -c "import spacy; spacy.load('fr_core_news_lg')" 2>/dev/null; then
    echo "⬇️  Downloading French spaCy model (fr_core_news_lg)..."
    pip install fr-core-news-lg@https://github.com/explosion/spacy-models/releases/download/fr_core_news_lg-3.7.0/fr_core_news_lg-3.7.0-py3-none-any.whl
fi

if ! python -c "import spacy; spacy.load('en_core_web_lg')" 2>/dev/null; then
    echo "⬇️  Downloading English spaCy model (en_core_web_lg)..."
    pip install en-core-web-lg@https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl
fi

echo "✅ spaCy models ready!"

# Execute the main command
exec "$@"
