"""
Graph exploration and statistics endpoints.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from backend.graph.neo4j_client import Neo4jClient

router = APIRouter()


class GraphStats(BaseModel):
    """Graph statistics."""

    entities: int
    relationships: int


class CypherQuery(BaseModel):
    """Cypher query request."""

    query: str
    parameters: Optional[Dict[str, Any]] = None


@router.get("/stats", response_model=GraphStats)
async def get_graph_stats():
    """Get overall graph statistics."""
    try:
        neo4j_client = Neo4jClient()
        stats = neo4j_client.get_graph_stats()
        neo4j_client.close()

        return GraphStats(**stats)
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cypher")
async def execute_cypher(query: CypherQuery):
    """
    Execute a raw Cypher query.

    Use with caution - for advanced users only.
    """
    try:
        neo4j_client = Neo4jClient()
        results = neo4j_client.execute_cypher(query.query, query.parameters)
        neo4j_client.close()

        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Cypher query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/neighbors/{name}")
async def get_neighbors(name: str, max_depth: int = 1):
    """
    Get neighboring entities up to a certain depth.

    Returns entities directly or indirectly connected to the given entity.
    """
    try:
        neo4j_client = Neo4jClient()

        query = """
        MATCH path = (e:Entity {name: $name})-[*1..""" + str(max_depth) + """]->(neighbor:Entity)
        RETURN DISTINCT neighbor.name as name,
               neighbor.type as type,
               length(path) as distance
        ORDER BY distance, name
        """

        results = neo4j_client.execute_cypher(query, {"name": name})
        neo4j_client.close()

        return {"entity": name, "neighbors": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Failed to get neighbors: {e}")
        raise HTTPException(status_code=500, detail=str(e))
