"""
Natural language query endpoints.
Converts questions to Cypher queries.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from backend.graph.neo4j_client import Neo4jClient

router = APIRouter()


class NaturalLanguageQuery(BaseModel):
    """Natural language query request."""

    question: str


class QueryResponse(BaseModel):
    """Query response."""

    question: str
    cypher_query: str
    results: List[Dict[str, Any]]
    interpretation: str


@router.post("/ask", response_model=QueryResponse)
async def ask_question(query: NaturalLanguageQuery):
    """
    Ask a natural language question about the knowledge graph.

    Examples:
    - "Who owns Poulina Group?"
    - "What companies are linked to Abdelwaheb Ben Ayed?"
    - "What groups operate in telecom?"
    """
    question = query.question.lower()

    # Simple pattern matching for MVP
    # In production, use LLM to convert NL -> Cypher
    cypher_query = _convert_to_cypher(question)

    if not cypher_query:
        raise HTTPException(
            status_code=400,
            detail="Could not understand the question. Try rephrasing or use simpler queries.",
        )

    try:
        neo4j_client = Neo4jClient()
        results = neo4j_client.execute_cypher(cypher_query["query"], cypher_query.get("params", {}))
        neo4j_client.close()

        return QueryResponse(
            question=query.question,
            cypher_query=cypher_query["query"],
            results=results,
            interpretation=cypher_query["interpretation"],
        )
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _convert_to_cypher(question: str) -> Dict[str, Any]:
    """
    Convert natural language question to Cypher query.

    This is a simplified pattern-matching approach for MVP.
    Production version should use LLM for robust NL->Cypher conversion.
    """
    question = question.lower().strip()

    # Pattern: "who owns X?"
    if "who owns" in question or "who own" in question:
        # Extract company name
        company = _extract_entity_name(question, ["who owns", "who own"])
        return {
            "query": """
                MATCH (person:Entity)-[r:OWNS]->(company:Entity {name: $company})
                RETURN person.name as owner, r.confidence as confidence
                ORDER BY confidence DESC
            """,
            "params": {"company": company},
            "interpretation": f"Finding who owns {company}",
        }

    # Pattern: "what companies are linked to X?"
    if "what companies" in question and "linked to" in question:
        person = _extract_entity_name(question, ["linked to"])
        return {
            "query": """
                MATCH (person:Entity {name: $person})-[r]-(company:Entity)
                WHERE company.type IN ['Company', 'Group', 'Bank']
                RETURN DISTINCT company.name as company,
                       company.type as type,
                       type(r) as relationship
            """,
            "params": {"person": person},
            "interpretation": f"Finding companies linked to {person}",
        }

    # Pattern: "what groups operate in X?"
    if "what groups" in question and "operate in" in question:
        sector = _extract_entity_name(question, ["operate in", "in sector"])
        return {
            "query": """
                MATCH (group:Entity)-[r:OPERATES_IN]->(sector:Entity)
                WHERE toLower(sector.name) CONTAINS toLower($sector)
                   OR sector.type = 'Sector'
                RETURN group.name as group,
                       sector.name as sector,
                       r.confidence as confidence
            """,
            "params": {"sector": sector},
            "interpretation": f"Finding groups operating in {sector}",
        }

    # Pattern: "which companies share directors?"
    if "share directors" in question or "shared directors" in question:
        return {
            "query": """
                MATCH (company1:Entity)<-[:DIRECTOR_OF]-(person:Entity)-[:DIRECTOR_OF]->(company2:Entity)
                WHERE company1 <> company2
                RETURN DISTINCT company1.name as company1,
                       company2.name as company2,
                       person.name as shared_director
                LIMIT 50
            """,
            "params": {},
            "interpretation": "Finding companies that share directors",
        }

    # Pattern: "show relationships between X and Y"
    if "relationship" in question and " and " in question:
        parts = question.split(" and ")
        if len(parts) == 2:
            entity1 = _extract_entity_name(parts[0], ["between", "relationship"])
            entity2 = parts[1].strip(" ?.")
            return {
                "query": """
                    MATCH path = shortestPath(
                        (e1:Entity {name: $entity1})-[*1..3]-(e2:Entity {name: $entity2})
                    )
                    RETURN [node in nodes(path) | node.name] as entities,
                           [rel in relationships(path) | type(rel)] as relationships
                    LIMIT 5
                """,
                "params": {"entity1": entity1, "entity2": entity2},
                "interpretation": f"Finding relationships between {entity1} and {entity2}",
            }

    # Default: search for entity
    if len(question.split()) <= 5:  # Short query, likely entity search
        return {
            "query": """
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($query)
                RETURN e.name as name, e.type as type
                LIMIT 10
            """,
            "params": {"query": question},
            "interpretation": f"Searching for entities matching '{question}'",
        }

    return None


def _extract_entity_name(text: str, remove_phrases: List[str]) -> str:
    """Extract entity name from question text."""
    for phrase in remove_phrases:
        text = text.replace(phrase, "")

    # Remove common question words
    for word in ["who", "what", "which", "where", "?", "the", "a", "an"]:
        text = text.replace(f" {word} ", " ")

    return text.strip(" ?.")
