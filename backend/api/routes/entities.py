"""
Entity search and exploration endpoints.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from backend.graph.neo4j_client import Neo4jClient

router = APIRouter()


class EntitySearchResult(BaseModel):
    """Entity search result."""

    name: str
    type: str
    confidence: float


class EntityDetail(BaseModel):
    """Detailed entity information."""

    name: str
    type: str
    aliases: List[str]
    confidence: float
    documents: List[str]


class RelationshipInfo(BaseModel):
    """Relationship information."""

    relation_type: str
    target_name: Optional[str] = None
    source_name: Optional[str] = None
    target_type: Optional[str] = None
    source_type: Optional[str] = None
    confidence: float
    evidence: Optional[str] = None


@router.get("/search", response_model=List[EntitySearchResult])
async def search_entities(
    q: str = Query(..., min_length=2, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
):
    """
    Search for entities by name.

    Performs case-insensitive substring matching.
    """
    try:
        neo4j_client = Neo4jClient()
        results = neo4j_client.search_entities(q, type, limit)
        neo4j_client.close()

        return [
            EntitySearchResult(
                name=r["name"], type=r["type"], confidence=r["confidence"]
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Entity search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}", response_model=EntityDetail)
async def get_entity(name: str):
    """
    Get detailed information about an entity.

    Includes aliases and source documents.
    """
    try:
        neo4j_client = Neo4jClient()
        entity = neo4j_client.get_entity(name)
        neo4j_client.close()

        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        return EntityDetail(**entity)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/relationships", response_model=List[RelationshipInfo])
async def get_entity_relationships(name: str):
    """
    Get all relationships for an entity.

    Returns both incoming and outgoing relationships.
    """
    try:
        neo4j_client = Neo4jClient()
        relationships = neo4j_client.get_entity_relationships(name)
        neo4j_client.close()

        return [RelationshipInfo(**r) for r in relationships]
    except Exception as e:
        logger.error(f"Failed to get relationships: {e}")
        raise HTTPException(status_code=500, detail=str(e))
