"""
Advanced graph exploration and visualization endpoints.
Provides better queries and data for frontend visualization.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from backend.graph.neo4j_client import Neo4jClient

router = APIRouter()


class GraphNode(BaseModel):
    """Node in graph visualization."""

    id: str
    label: str
    type: str
    confidence: float
    properties: dict = {}


class GraphEdge(BaseModel):
    """Edge in graph visualization."""

    source: str
    target: str
    relation: str
    confidence: float
    evidence: Optional[str] = None


class GraphData(BaseModel):
    """Complete graph data for visualization."""

    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: dict


@router.get("/overview", response_model=GraphData)
async def get_graph_overview(
    limit: int = Query(100, ge=10, le=1000, description="Max nodes to return"),
    min_confidence: float = Query(
        0.6, ge=0.0, le=1.0, description="Minimum confidence"
    ),
):
    """
    Get overview of the graph with most connected entities.

    Returns the most important nodes and their relationships.
    """
    try:
        neo4j_client = Neo4jClient()

        # Get most connected entities with their relationships
        query = """
        MATCH (n:Entity)
        WHERE n.confidence >= $min_confidence
          AND size(n.name) > 2
          AND size(n.name) < 100
          AND NOT n.name =~ '.*\\n.*'
        WITH n, COUNT { (n)--() } as degree
        WHERE degree > 0
        WITH n, degree
        ORDER BY degree DESC, n.confidence DESC
        LIMIT $limit
        MATCH (n)-[r]->(m:Entity)
        WHERE m.confidence >= $min_confidence
        RETURN n.name as source_name,
               n.type as source_type,
               n.confidence as source_conf,
               type(r) as relation,
               r.confidence as rel_conf,
               r.evidence as evidence,
               m.name as target_name,
               m.type as target_type,
               m.confidence as target_conf
        """

        results = neo4j_client.execute_cypher(
            query, {"limit": limit, "min_confidence": min_confidence}
        )

        # Build nodes and edges
        nodes_dict = {}
        edges = []

        for row in results:
            # Add source node
            if row["source_name"] not in nodes_dict:
                nodes_dict[row["source_name"]] = GraphNode(
                    id=row["source_name"],
                    label=row["source_name"],
                    type=row["source_type"],
                    confidence=row["source_conf"],
                )

            # Add target node
            if row["target_name"] not in nodes_dict:
                nodes_dict[row["target_name"]] = GraphNode(
                    id=row["target_name"],
                    label=row["target_name"],
                    type=row["target_type"],
                    confidence=row["target_conf"],
                )

            # Add edge
            edges.append(
                GraphEdge(
                    source=row["source_name"],
                    target=row["target_name"],
                    relation=row["relation"],
                    confidence=row["rel_conf"] or 0.8,
                    evidence=row.get("evidence"),
                )
            )

        neo4j_client.close()

        # Get stats
        stats = {
            "total_nodes": len(nodes_dict),
            "total_edges": len(edges),
            "min_confidence": min_confidence,
        }

        return GraphData(nodes=list(nodes_dict.values()), edges=edges, stats=stats)

    except Exception as e:
        logger.error(f"Failed to get graph overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_name}/neighborhood", response_model=GraphData)
async def get_entity_neighborhood(
    entity_name: str,
    depth: int = Query(2, ge=1, le=3, description="Relationship depth"),
    limit: int = Query(100, ge=10, le=1000, description="Max nodes"),
):
    """
    Get entity and its neighborhood up to specified depth.

    Shows entities connected to the target entity.
    """
    try:
        neo4j_client = Neo4jClient()

        # Get entity neighborhood with variable depth
        query = f"""
        MATCH path = (start:Entity {{name: $entity_name}})-[*1..{depth}]-(connected:Entity)
        WHERE connected.confidence >= 0.6
          AND size(connected.name) > 2
          AND size(connected.name) < 100
        WITH start, connected, relationships(path) as rels
        LIMIT $limit
        UNWIND rels as r
        WITH start, startNode(r) as source, r, endNode(r) as target
        WHERE source.confidence >= 0.6 AND target.confidence >= 0.6
        RETURN DISTINCT
               source.name as source_name,
               source.type as source_type,
               source.confidence as source_conf,
               type(r) as relation,
               r.confidence as rel_conf,
               r.evidence as evidence,
               target.name as target_name,
               target.type as target_type,
               target.confidence as target_conf
        """

        results = neo4j_client.execute_cypher(
            query, {"entity_name": entity_name, "limit": limit}
        )

        if not results:
            raise HTTPException(status_code=404, detail="Entity not found or has no connections")

        # Build graph
        nodes_dict = {}
        edges = []

        for row in results:
            # Add nodes
            if row["source_name"] not in nodes_dict:
                nodes_dict[row["source_name"]] = GraphNode(
                    id=row["source_name"],
                    label=row["source_name"],
                    type=row["source_type"],
                    confidence=row["source_conf"],
                )

            if row["target_name"] not in nodes_dict:
                nodes_dict[row["target_name"]] = GraphNode(
                    id=row["target_name"],
                    label=row["target_name"],
                    type=row["target_type"],
                    confidence=row["target_conf"],
                )

            # Add edge
            edges.append(
                GraphEdge(
                    source=row["source_name"],
                    target=row["target_name"],
                    relation=row["relation"],
                    confidence=row["rel_conf"] or 0.8,
                    evidence=row.get("evidence"),
                )
            )

        neo4j_client.close()

        stats = {
            "center_entity": entity_name,
            "depth": depth,
            "total_nodes": len(nodes_dict),
            "total_edges": len(edges),
        }

        return GraphData(nodes=list(nodes_dict.values()), edges=edges, stats=stats)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get entity neighborhood: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-type/{entity_type}", response_model=GraphData)
async def get_graph_by_type(
    entity_type: str,
    limit: int = Query(100, ge=10, le=1000),
):
    """
    Get subgraph containing only specific entity type.

    Useful for exploring all companies, people, or groups.
    """
    try:
        neo4j_client = Neo4jClient()

        query = """
        MATCH (n:Entity {type: $entity_type})
        WHERE n.confidence >= 0.7
          AND size(n.name) > 2
          AND size(n.name) < 100
        WITH n
        ORDER BY n.confidence DESC
        LIMIT $limit
        OPTIONAL MATCH (n)-[r]-(m:Entity)
        WHERE m.confidence >= 0.7
        RETURN n.name as source_name,
               n.type as source_type,
               n.confidence as source_conf,
               type(r) as relation,
               r.confidence as rel_conf,
               r.evidence as evidence,
               m.name as target_name,
               m.type as target_type,
               m.confidence as target_conf
        """

        results = neo4j_client.execute_cypher(
            query, {"entity_type": entity_type, "limit": limit}
        )

        nodes_dict = {}
        edges = []

        for row in results:
            # Add source
            if row["source_name"] not in nodes_dict:
                nodes_dict[row["source_name"]] = GraphNode(
                    id=row["source_name"],
                    label=row["source_name"],
                    type=row["source_type"],
                    confidence=row["source_conf"],
                )

            # Add target if exists
            if row["target_name"] and row["target_name"] not in nodes_dict:
                nodes_dict[row["target_name"]] = GraphNode(
                    id=row["target_name"],
                    label=row["target_name"],
                    type=row["target_type"],
                    confidence=row["target_conf"],
                )

            # Add edge if exists
            if row["relation"]:
                edges.append(
                    GraphEdge(
                        source=row["source_name"],
                        target=row["target_name"],
                        relation=row["relation"],
                        confidence=row["rel_conf"] or 0.8,
                        evidence=row.get("evidence"),
                    )
                )

        neo4j_client.close()

        stats = {
            "entity_type": entity_type,
            "total_nodes": len(nodes_dict),
            "total_edges": len(edges),
        }

        return GraphData(nodes=list(nodes_dict.values()), edges=edges, stats=stats)

    except Exception as e:
        logger.error(f"Failed to get graph by type: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-path")
async def search_path(
    source: str = Query(..., description="Source entity name"),
    target: str = Query(..., description="Target entity name"),
    max_depth: int = Query(5, ge=1, le=10),
):
    """
    Find shortest path between two entities.

    Useful for discovering hidden connections.
    """
    try:
        neo4j_client = Neo4jClient()

        query = """
        MATCH path = shortestPath(
            (source:Entity {name: $source})-[*..%d]-(target:Entity {name: $target})
        )

        WITH path, relationships(path) as rels, nodes(path) as nodes

        UNWIND range(0, size(rels)-1) as idx
        WITH rels[idx] as r, nodes[idx] as source, nodes[idx+1] as target

        RETURN source.name as source_name,
               source.type as source_type,
               source.confidence as source_conf,
               type(r) as relation,
               r.confidence as rel_conf,
               r.evidence as evidence,
               target.name as target_name,
               target.type as target_type,
               target.confidence as target_conf
        """ % max_depth

        results = neo4j_client.execute_cypher(
            query, {"source": source, "target": target}
        )

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No path found between {source} and {target}",
            )

        nodes_dict = {}
        edges = []

        for row in results:
            if row["source_name"] not in nodes_dict:
                nodes_dict[row["source_name"]] = GraphNode(
                    id=row["source_name"],
                    label=row["source_name"],
                    type=row["source_type"],
                    confidence=row["source_conf"],
                )

            if row["target_name"] not in nodes_dict:
                nodes_dict[row["target_name"]] = GraphNode(
                    id=row["target_name"],
                    label=row["target_name"],
                    type=row["target_type"],
                    confidence=row["target_conf"],
                )

            edges.append(
                GraphEdge(
                    source=row["source_name"],
                    target=row["target_name"],
                    relation=row["relation"],
                    confidence=row["rel_conf"] or 0.8,
                    evidence=row.get("evidence"),
                )
            )

        neo4j_client.close()

        stats = {
            "source": source,
            "target": target,
            "path_length": len(edges),
            "total_nodes": len(nodes_dict),
        }

        return GraphData(nodes=list(nodes_dict.values()), edges=edges, stats=stats)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find path: {e}")
        raise HTTPException(status_code=500, detail=str(e))
