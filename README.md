# Tunisian Economy Knowledge Graph

A knowledge graph system that extracts and visualizes relationships between companies, people, and organizations in the Tunisian economy using natural language processing and graph databases.

## Overview

This project automatically processes documents (PDFs, web articles) about Tunisian businesses and creates a queryable knowledge graph showing ownership structures, board memberships, and business relationships. It handles multilingual content (French, Arabic, English) and provides an interactive visualization interface.

## Features

- **📄 Document Processing**: Upload PDFs or scrape Tunisian news sources (TAP, African Manager, IlBoursa)
- **🔍 Entity Extraction**: Hybrid NLP pipeline using spaCy and local LLM (Ollama) to identify companies, people, and organizations
- **🧠 Multilingual Support**: Handles Arabic, French, and English business names with fuzzy matching and entity resolution
- **📊 Knowledge Graph**: Neo4j graph database with full traceability to source documents
- **🔎 Natural Language Queries**: Ask questions like "Who owns Poulina Group?" and get graph-based answers
- **🌐 Interactive Visualization**: React-based graph explorer using Cytoscape.js

## Architecture

### Tech Stack

- **Backend**: Python 3.11+, FastAPI, spaCy, PyMuPDF
- **Graph Database**: Neo4j 5.x
- **Frontend**: React 18, Vite, Cytoscape.js
- **NLP**: spaCy (French/English models), Ollama (local LLM for relationship extraction)

### 5-Layer Pipeline

```
┌─────────────────┐
│  1. Ingestion   │  PDF upload, web scraping
└────────┬────────┘
         │
┌────────▼────────┐
│  2. Processing  │  Text extraction, OCR, chunking
└────────┬────────┘
         │
┌────────▼────────┐
│  3. Extraction  │  NER (entities) + LLM (relationships)
└────────┬────────┘
         │
┌────────▼────────┐
│  4. Resolution  │  Entity deduplication, multilingual matching
└────────┬────────┘
         │
┌────────▼────────┐
│  5. Storage     │  Neo4j graph with traceability
└─────────────────┘
```

## Quick Start

### Option 1: Docker (Recommended)

**Prerequisites:**
- Docker Desktop (Mac/Windows) or Docker Engine (Linux)
- 8GB RAM available
- 20GB disk space

**Steps:**

```bash
# Clone the repository
git clone https://github.com/yourusername/tun-economy-graph-MVP.git
cd tun-economy-graph-MVP

# Create environment file
cp .env.example .env

# Start all services (Neo4j, Ollama, Backend, Frontend)
docker-compose up -d

# Wait 2-3 minutes for services to initialize
docker-compose logs -f

# Access the application
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
# Neo4j Browser: http://localhost:7474
```

**Docker Commands:**

```bash
docker-compose up -d      # Start services
docker-compose down       # Stop services
docker-compose logs -f    # View logs
docker-compose ps         # Check status
docker-compose restart    # Restart all services
```

### Option 2: Manual Installation

**Prerequisites:**
- Python 3.11+
- Neo4j 5.x
- Ollama
- Node.js 18+
- Tesseract OCR

**Installation:**

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Download spaCy language models
python -m spacy download fr_core_news_lg
python -m spacy download en_core_web_lg

# 4. Set up environment
cp .env.example .env
# Edit .env with your Neo4j credentials

# 5. Create directories
python -c "from backend.config import settings; settings.ensure_directories()"

# 6. Start Neo4j (using Docker)
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:5.16

# 7. Start Ollama and download model
ollama serve
ollama pull llama3.1

# 8. Start backend
cd backend
uvicorn api.main:app --reload --port 8000

# 9. Start frontend (in new terminal)
cd frontend
npm install
npm run dev
```

Visit **http://localhost:5173** to use the application.

## Usage

### Upload Documents

1. Navigate to the upload section in the web interface
2. Upload a PDF containing business information (annual reports, news articles, etc.)
3. The system will automatically:
   - Extract text (with OCR fallback for scanned docs)
   - Identify entities (companies, people, organizations)
   - Extract relationships (ownership, board membership, etc.)
   - Add to the knowledge graph

### Search and Query

**Search entities:**
```bash
curl "http://localhost:8000/api/entities/search?q=poulina"
```

**Ask natural language questions:**
```bash
curl -X POST http://localhost:8000/api/query/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Who owns Poulina Group?"}'
```

**Example questions:**
- "Who owns Poulina Group?"
- "What companies are linked to Abdelwaheb Ben Ayed?"
- "Which companies share directors?"
- "What groups operate in telecom?"

### Web Scraping

Automatically collect articles from Tunisian news sources:

```bash
curl -X POST http://localhost:8000/api/scraping/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "sources": ["tap", "african_manager", "ilboursa"],
    "limit_per_source": 10
  }'
```

### Graph Visualization

The web interface provides an interactive graph where:
- **Nodes** represent entities (companies, people, organizations)
- **Edges** represent relationships (OWNS, DIRECTOR_OF, SUBSIDIARY_OF, etc.)
- **Colors** indicate entity types
- **Click nodes** to explore connections
- **Hover** for details and source documents

## API Endpoints

### Documents
- `POST /api/documents/upload` - Upload PDF document
- `GET /api/documents/list` - List all uploaded documents
- `GET /api/documents/{id}` - Get document details

### Entities
- `GET /api/entities/search?q={query}` - Search entities
- `GET /api/entities/{name}` - Get entity details
- `GET /api/entities/{name}/relationships` - Get relationships

### Query
- `POST /api/query/ask` - Natural language question answering

### Graph
- `GET /api/graph/stats` - Get graph statistics (node/edge counts)
- `GET /api/graph/neighbors/{name}` - Get connected entities
- `POST /api/graph/cypher` - Execute raw Cypher queries

### Scraping
- `POST /api/scraping/scrape` - Scrape news sources
- `GET /api/scraping/sources` - List available sources

## Project Structure

```
tun-economy-graph-MVP/
├── backend/
│   ├── api/              # FastAPI routes and endpoints
│   ├── ingestion/        # PDF upload and web scraping
│   ├── processing/       # Text extraction and chunking
│   ├── extraction/       # NER and relationship extraction
│   ├── resolution/       # Entity deduplication and matching
│   ├── graph/            # Neo4j client and queries
│   ├── utils/            # Shared utilities
│   ├── config.py         # Configuration management
│   └── ontology.py       # Entity and relationship types
├── frontend/             # React visualization application
├── data/
│   ├── raw/              # Uploaded documents
│   └── processed/        # Processed text chunks
├── models/               # spaCy models and embeddings
├── logs/                 # Application logs
├── tests/                # Unit and integration tests
├── docker-compose.yml    # Docker services configuration
└── requirements.txt      # Python dependencies
```

## Configuration

All configuration is managed through the `.env` file:

```bash
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1

# Extraction Settings
CHUNK_SIZE=1000
MIN_CONFIDENCE=0.7
SUPPORTED_LANGUAGES=fr,ar,en

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
```

## Data Model

### Entity Types

- **Person**: Individual executives, directors, shareholders
- **Company**: Individual companies and businesses
- **Group**: Holding companies and business groups
- **Bank**: Financial institutions
- **Organization**: Government entities, NGOs, associations
- **Sector**: Industry sectors (telecom, finance, etc.)
- **Location**: Cities, regions, countries

### Relationship Types

- **OWNS**: Ownership relationships
- **DIRECTOR_OF**: Board membership
- **MEMBER_OF_BOARD**: Board participation
- **SUBSIDIARY_OF**: Corporate structure
- **PARTNER_OF**: Business partnerships
- **ACQUIRED**: Acquisition events
- **FOUNDED**: Company founding
- **INVESTED_IN**: Investment relationships
- **OPERATES_IN**: Sector/location operations

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_extraction.py

# Run with coverage
pytest --cov=backend tests/
```

### Code Quality

```bash
# Format code
black backend/

# Lint
ruff backend/

# Type checking
mypy backend/
```

### Adding New Features

**Add a new entity type:**
1. Update `EntityType` enum in `backend/ontology.py`
2. Add classification logic in extraction pipeline
3. Update frontend visualization styles

**Add a new relationship type:**
1. Update `RelationType` enum in `backend/ontology.py`
2. Update LLM extraction prompts
3. Update graph queries if needed

**Add a new web scraper:**
1. Create scraper class in `backend/ingestion/scrapers.py`
2. Implement `scrape_business_section()` method
3. Register in `ScraperManager`

## Multilingual Entity Resolution

The system handles Tunisian business names that appear in multiple forms:

- **Arabic**: حمزة الشركة
- **French**: Groupe Poulina, PGH
- **English/Transliterated**: Hamza Group, Hamzah

**Resolution approach:**
1. Exact string matching
2. Alias lookup (known variants)
3. Fuzzy string matching (Levenshtein distance)
4. Semantic embeddings (multilingual-MiniLM)
5. Human validation queue for ambiguous cases

## Known Limitations (MVP)

This is an MVP (Minimum Viable Product) with some limitations:

1. **No authentication**: API endpoints are currently open
2. **Arabic NLP**: Limited Arabic language model support
3. **Scraper maintenance**: Web scrapers may need updates if source sites change
4. **Manual validation**: Entity resolution queue requires human review
5. **Performance**: LLM-based extraction can be slow (5-10 seconds per relationship)

## Troubleshooting

**"Model not found" error:**
```bash
python -m spacy download fr_core_news_lg
```

**Neo4j connection fails:**
```bash
# Check if Neo4j is running
docker ps | grep neo4j

# View Neo4j logs
docker logs neo4j

# Test connection
curl http://localhost:7474
```

**Ollama not responding:**
```bash
# Check if Ollama is running
ollama list

# Restart Ollama
ollama serve
```

**Frontend can't reach API:**
- Ensure backend is running on port 8000
- Check browser console for CORS errors
- Verify Vite proxy configuration in `frontend/vite.config.js`

**Out of memory:**
- Increase Docker Desktop memory allocation (8GB minimum)
- Reduce `CHUNK_SIZE` in `.env`
- Use a smaller Ollama model (`llama3.2` instead of `llama3.1`)

## Performance Optimization

**For faster extraction:**
- Reduce `CHUNK_SIZE` to process smaller text segments
- Use smaller LLM models (llama3.2 3B vs llama3.1 8B)
- Increase `MIN_CONFIDENCE` to filter low-quality extractions

**For better accuracy:**
- Increase `CHUNK_SIZE` to provide more context
- Use larger LLM models
- Decrease `MIN_CONFIDENCE` to capture more relationships

## Data Sources

The system can ingest data from:

- **PDFs**: Annual reports, financial documents, news articles
- **Web sources**: TAP (Tunis Afrique Presse), African Manager, IlBoursa
- **Structured data**: Company registries, stock exchange filings
- **Social media**: LinkedIn profiles (for executive information)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run code quality checks (`black`, `ruff`, `mypy`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [spaCy](https://spacy.io/) for NLP
- [Neo4j](https://neo4j.com/) for graph database
- [Ollama](https://ollama.ai/) for local LLM inference
- [FastAPI](https://fastapi.tiangolo.com/) for the backend API
- [React](https://react.dev/) and [Cytoscape.js](https://js.cytoscape.org/) for visualization

## Contact

For questions or feedback, please open an issue on GitHub.

---

**Note**: This is an MVP (Minimum Viable Product) designed for research and development purposes. For production deployment, additional security, authentication, and performance optimizations are recommended.
