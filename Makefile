.PHONY: help build up down restart logs clean test

help:
	@echo "Tunisian Economy Knowledge Graph - Docker Commands"
	@echo ""
	@echo "Development:"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs (all services)"
	@echo "  make logs-api    - View backend API logs"
	@echo "  make logs-ollama - View Ollama logs"
	@echo "  make build       - Build containers"
	@echo ""
	@echo "Graph Management:"
	@echo "  make graph-stats        - Show graph statistics"
	@echo "  make analyze-graph      - Analyze graph quality (dry-run)"
	@echo "  make clean-bad-entities - Remove bad entities (citations, job titles)"
	@echo "  make merge-duplicates   - Merge duplicate entities (case variants)"
	@echo "  make clean-and-merge    - Full cleanup (remove bad + merge duplicates)"
	@echo "  make fix-misclassified  - Fix misclassified entities (STAR, BIAT, etc.)"
	@echo "  make clear-graph        - Delete all graph data"
	@echo "  make reset-graph        - Clear graph + reprocess all documents"
	@echo "  make reprocess-docs     - Reprocess documents (keep existing data)"
	@echo ""
	@echo "Entity Registry:"
	@echo "  make bootstrap-registry - Create entity registry from Neo4j graph"
	@echo "  make registry-stats     - Show entity registry statistics"
	@echo "  make seed-entities      - Seed registry with known Tunisian entities"
	@echo ""
	@echo "Production:"
	@echo "  make up-prod     - Start production services"
	@echo "  make down-prod   - Stop production services"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean       - Stop and remove all containers/volumes"
	@echo "  make backup      - Backup Neo4j data"
	@echo "  make status      - Show service status"
	@echo "  make shell-api   - Open shell in backend container"
	@echo "  make test        - Run tests"

# Development commands
up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f backend

logs-ollama:
	docker-compose logs -f ollama

logs-neo4j:
	docker-compose logs -f neo4j

build:
	docker-compose build

rebuild:
	docker-compose up -d --build

# Production commands
up-prod:
	docker-compose -f docker-compose.prod.yml up -d

down-prod:
	docker-compose -f docker-compose.prod.yml down

logs-prod:
	docker-compose -f docker-compose.prod.yml logs -f

# Status and maintenance
status:
	docker-compose ps

shell-api:
	docker-compose exec backend /bin/bash

shell-neo4j:
	docker-compose exec neo4j /bin/bash

clean:
	docker-compose down -v
	@echo "⚠️  All data has been deleted!"

backup:
	@mkdir -p backups
	docker-compose exec neo4j neo4j-admin database dump neo4j --to=/data/backup-$$(date +%Y%m%d-%H%M%S).dump
	docker cp tun-economy-neo4j:/data/backup-*.dump ./backups/
	@echo "✅ Backup saved to ./backups/"

# Testing
test:
	docker-compose exec backend pytest

test-coverage:
	docker-compose exec backend pytest --cov=backend --cov-report=html

# Model management
pull-model:
	docker-compose exec ollama ollama pull llama3.2

list-models:
	docker-compose exec ollama ollama list

shell-ollama:
	docker-compose exec ollama /bin/bash

# Health checks
health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health && echo "✅ Backend API healthy"
	@curl -s http://localhost:11434/api/tags > /dev/null && echo "✅ Ollama healthy"
	@curl -s http://localhost:7474 > /dev/null && echo "✅ Neo4j healthy"

# Graph management
clear-graph:
	@echo "⚠️  This will DELETE ALL DATA from Neo4j!"
	@read -p "Continue? (yes/no): " response; \
	if [ "$$response" = "yes" ]; then \
		docker-compose exec -T backend python3 -m backend.utils.reset_graph --clear-only --yes; \
	else \
		echo "Aborted."; \
	fi

reset-graph:
	@echo "⚠️  This will DELETE ALL DATA and REPROCESS all documents!"
	@read -p "Continue? (yes/no): " response; \
	if [ "$$response" = "yes" ]; then \
		docker-compose exec -T backend python3 -m backend.utils.reset_graph --yes; \
	else \
		echo "Aborted."; \
	fi

reprocess-docs:
	@echo "📄 Reprocessing all documents (keeping existing graph data)..."
	docker-compose exec backend python3 -m backend.utils.reset_graph --skip-clear

graph-stats:
	@docker-compose exec -T backend python3 -c "from backend.graph.neo4j_client import Neo4jClient; \
	c = Neo4jClient(); \
	stats = c.get_graph_stats(); \
	c.close(); \
	print(f\"📊 Entities: {stats['entities']}, Relationships: {stats['relationships']}\")"

analyze-graph:
	@echo "🔍 Analyzing graph quality..."
	docker-compose exec backend python3 -m backend.utils.clean_graph

clean-bad-entities:
	@echo "🧹 Cleaning bad entities from graph..."
	docker-compose exec backend python3 -m backend.utils.clean_graph --clean --yes

merge-duplicates:
	@echo "🔄 Merging duplicate entities..."
	docker-compose exec backend python3 -m backend.utils.clean_graph --merge --yes

clean-and-merge:
	@echo "🧹 Full cleanup: removing bad entities + merging duplicates..."
	docker-compose exec backend python3 -m backend.utils.clean_graph --all --yes

fix-misclassified:
	@echo "🔧 Fixing misclassified entities (STAR, BIAT, Shareholders)..."
	docker-compose exec backend python3 -m backend.utils.manual_merge

# Entity Registry
bootstrap-registry:
	@echo "🔄 Bootstrapping entity registry from Neo4j graph..."
	docker-compose exec backend python3 -m backend.registry.bootstrap

seed-entities:
	@echo "🌱 Seeding registry with known entities..."
	docker-compose exec backend python3 -m backend.registry.bootstrap --seed-only

registry-stats:
	@echo "📊 Entity Registry Statistics:"
	@docker-compose exec backend python3 -c "from backend.registry import EntityRegistry; r = EntityRegistry(); import json; print(json.dumps(r.get_stats(), indent=2)); r.close()"

# Initialize
init:
	cp .env.docker .env
	@echo "✅ Created .env file"
	@echo "Edit .env with your settings, then run: make up"
