#!/bin/bash
# Initialize Ollama with required model

set -e

echo "Waiting for Ollama service to be ready..."
until curl -s http://ollama:11434/api/tags > /dev/null 2>&1; do
  echo "  Waiting..."
  sleep 2
done

echo "Ollama is ready. Pulling model: ${OLLAMA_MODEL:-llama3.2}"
docker-compose exec ollama ollama pull "${OLLAMA_MODEL:-llama3.2}"

echo "✅ Ollama model ready"
