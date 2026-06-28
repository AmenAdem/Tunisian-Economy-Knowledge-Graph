#!/bin/bash
# Clear the Neo4j graph database

set -e

echo "⚠️  This will DELETE ALL DATA from Neo4j!"
read -p "Are you sure? (yes/no): " response

if [[ "$response" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi

echo "Clearing graph..."

docker exec tun-economy-backend python3 -c "
from backend.graph.neo4j_client import Neo4jClient
from loguru import logger

client = Neo4jClient()

# Delete all relationships
result = client.execute_cypher('MATCH ()-[r]->() DELETE r RETURN count(r) as deleted')
rel_count = result[0]['deleted'] if result else 0
print(f'Deleted {rel_count} relationships')

# Delete all nodes
result = client.execute_cypher('MATCH (n) DELETE n RETURN count(n) as deleted')
node_count = result[0]['deleted'] if result else 0
print(f'Deleted {node_count} nodes')

# Reinitialize schema
client.initialize_schema()
print('Schema reinitialized')

client.close()

print(f'✅ Graph cleared: {node_count} nodes, {rel_count} relationships deleted')
"

echo "✅ Done!"
