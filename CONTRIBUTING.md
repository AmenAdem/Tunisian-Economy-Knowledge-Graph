# Contributing to Tunisian Economy Knowledge Graph

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/tun-economy-graph-MVP.git
   cd tun-economy-graph-MVP
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### Using Docker (Recommended)

```bash
docker-compose up -d
docker-compose logs -f
```

### Manual Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy models
python -m spacy download fr_core_news_lg
python -m spacy download en_core_web_lg

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Run tests
pytest
```

## Code Style

We follow Python best practices and use automated tools:

### Python

```bash
# Format code (required before committing)
black backend/

# Lint
ruff backend/

# Type checking
mypy backend/
```

### JavaScript/React

```bash
cd frontend
npm run lint
npm run format
```

## Testing

All new features should include tests:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_extraction.py

# Run with coverage
pytest --cov=backend tests/
```

### Test Guidelines

- Write unit tests for new functions/classes
- Write integration tests for API endpoints
- Ensure tests are deterministic (no random failures)
- Mock external services (Neo4j, Ollama) when appropriate
- Aim for >80% code coverage

## Making Changes

### Commit Messages

Follow conventional commit format:

```
type(scope): brief description

More detailed explanation if needed.

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(extraction): add support for Arabic NER
fix(api): handle empty query parameters
docs(readme): update installation instructions
```

### Pull Request Process

1. **Update documentation** if needed
2. **Add tests** for new functionality
3. **Run code quality checks**:
   ```bash
   black backend/
   ruff backend/
   mypy backend/
   pytest
   ```
4. **Update CHANGELOG** (if applicable)
5. **Create Pull Request** with clear description
6. **Link related issues** using "Fixes #123"
7. **Wait for review** and address feedback

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] No new warnings or errors
- [ ] Commits are well-formatted
- [ ] PR description explains changes

## Project Structure

```
backend/
├── api/              # FastAPI routes
├── ingestion/        # Document collection
├── processing/       # Text extraction
├── extraction/       # NLP pipeline
├── resolution/       # Entity deduplication
├── graph/            # Neo4j operations
└── utils/            # Shared utilities

frontend/
├── src/
│   ├── components/   # React components
│   ├── hooks/        # Custom hooks
│   └── utils/        # Frontend utilities

tests/                # Unit and integration tests
```

## Adding New Features

### Add a New Entity Type

1. Update `EntityType` in `backend/ontology.py`
2. Add classification logic in `backend/extraction/ner_extractor.py`
3. Update frontend visualization in `frontend/src/components/GraphVisualization.jsx`
4. Add tests in `tests/test_extraction.py`
5. Update documentation

### Add a New Relationship Type

1. Update `RelationType` in `backend/ontology.py`
2. Update LLM prompts in `backend/extraction/relation_extractor.py`
3. Add tests
4. Update documentation

### Add a New Web Scraper

1. Create scraper class in `backend/ingestion/scrapers.py`
2. Extend `BaseScraper` class
3. Implement required methods
4. Register in `ScraperManager`
5. Add tests for scraper
6. Update API documentation

## Code Review Guidelines

When reviewing PRs, consider:

- **Correctness**: Does it work as intended?
- **Tests**: Are there adequate tests?
- **Performance**: Any performance concerns?
- **Security**: Any security vulnerabilities?
- **Maintainability**: Is the code readable and maintainable?
- **Documentation**: Is it well-documented?

## Community Guidelines

- Be respectful and constructive
- Help others learn and grow
- Focus on the code, not the person
- Assume good intentions
- Ask questions when unclear

## Getting Help

- **Issues**: Check existing issues or create a new one
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check README.md and inline code comments

## Recognition

Contributors will be:
- Listed in the project README
- Credited in release notes
- Acknowledged in commit history

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to open an issue with the "question" label if you need help!
