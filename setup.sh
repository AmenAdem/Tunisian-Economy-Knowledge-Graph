#!/bin/bash
set -e

echo "🚀 Setting up Tunisian Economy Knowledge Graph MVP"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.11+ required. Found: $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📥 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Download spaCy models
echo "🔤 Downloading spaCy models..."
python -m spacy download fr_core_news_lg
python -m spacy download en_core_web_lg

# Set up environment file
if [ ! -f .env ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your Neo4j credentials"
fi

# Create directories
echo "📁 Creating directories..."
python -c "from backend.config import settings; settings.ensure_directories()"

# Check if Neo4j is running
echo "🔍 Checking Neo4j..."
if ! curl -s http://localhost:7474 > /dev/null; then
    echo "⚠️  Neo4j not detected. Start it with:"
    echo "   docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5.16"
else
    echo "✅ Neo4j is running"
fi

# Check if Ollama is running
echo "🔍 Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "⚠️  Ollama not detected. Install and start it:"
    echo "   ollama serve"
    echo "   ollama pull llama3.1"
else
    echo "✅ Ollama is running"
fi

# Frontend setup
echo "🎨 Setting up frontend..."
cd frontend
if command -v npm &> /dev/null; then
    npm install
    echo "✅ Frontend dependencies installed"
else
    echo "⚠️  npm not found. Install Node.js to set up frontend."
fi
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  1. Backend:  uvicorn backend.api.main:app --reload"
echo "  2. Frontend: cd frontend && npm run dev"
echo ""
echo "📚 API docs will be at: http://localhost:8000/docs"
echo "🌐 Frontend will be at: http://localhost:3000"
