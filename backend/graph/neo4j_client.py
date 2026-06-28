"""
Neo4j client for knowledge graph operations.
Implements property graph with full traceability to source documents.
"""

from typing import Dict, List, Optional

from loguru import logger
from neo4j import GraphDatabase, Result

from backend.config import settings
from backend.ontology import Entity, ExtractionResult, Relation


class Neo4jClient:
    """Client for Neo4j graph database operations."""

    def __init__(self):
        """Initialize Neo4j client."""
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        logger.info(f"Connected to Neo4j at {settings.neo4j_uri}")

    def close(self) -> None:
        """Close database connection."""
        self.driver.close()
        logger.info("Neo4j connection closed")

    def verify_connection(self) -> bool:
        """Verify database connection."""
        try:
            self.driver.verify_connectivity()
            logger.info("Neo4j connection verified")
            return True
        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}")
            return False

    def initialize_schema(self) -> None:
        """Create indexes and constraints for the graph."""
        with self.driver.session() as session:
            # Create uniqueness constraints on entity names
            constraints = [
                "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
                "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
                "CREATE INDEX document_path IF NOT EXISTS FOR (d:Document) ON (d.path)",
            ]

            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.debug(f"Created constraint/index: {constraint}")
                except Exception as e:
                    logger.warning(f"Failed to create constraint: {e}")

        logger.info("Schema initialized")

    def add_extraction_result(
        self,
        result: ExtractionResult,
        source_document: str,
        chunk_id: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Add extraction result to graph with traceability.

        Args:
            result: ExtractionResult with entities and relations
            source_document: Path to source document
            chunk_id: Optional chunk identifier

        Returns:
            Dictionary with counts of added nodes and relationships
        """
        with self.driver.session() as session:
            # Create or get document node
            doc_id = session.execute_write(
                self._create_document_node, source_document, chunk_id
            )

            # Add entities
            entity_count = 0
            for entity in result.entities:
                session.execute_write(self._create_entity_node, entity, doc_id)
                entity_count += 1

            # Add relations
            relation_count = 0
            for relation in result.relations:
                session.execute_write(self._create_relation, relation, doc_id)
                relation_count += 1

            logger.info(
                f"Added {entity_count} entities and {relation_count} relations from {source_document}"
            )

            return {
                "entities_added": entity_count,
                "relations_added": relation_count,
            }

    @staticmethod
    def _create_document_node(tx, source_path: str, chunk_id: Optional[str]) -> str:
        """Create or get document node."""
        query = """
        MERGE (d:Document {path: $path})
        ON CREATE SET d.created = timestamp(),
                      d.chunk_id = $chunk_id
        RETURN elementId(d) as doc_id
        """
        result = tx.run(query, path=source_path, chunk_id=chunk_id)
        return result.single()["doc_id"]

    @staticmethod
    def _create_entity_node(tx, entity: Entity, doc_id: str) -> None:
        """Create or update entity node."""
        query = """
        MERGE (e:Entity {name: $name})
        ON CREATE SET e.type = $type,
                      e.aliases = $aliases,
                      e.confidence = $confidence,
                      e.created = timestamp()
        ON MATCH SET e.aliases = e.aliases + [x IN $aliases WHERE NOT x IN e.aliases],
                     e.confidence = CASE WHEN $confidence > e.confidence
                                    THEN $confidence ELSE e.confidence END
        SET e += $properties
        WITH e
        MATCH (d:Document) WHERE elementId(d) = $doc_id
        MERGE (e)-[:MENTIONED_IN]->(d)
        """
        tx.run(
            query,
            name=entity.name,
            type=entity.type.value,
            aliases=entity.aliases,
            confidence=entity.confidence,
            properties=entity.properties,
            doc_id=doc_id,
        )

    @staticmethod
    def _create_relation(tx, relation: Relation, doc_id: str) -> None:
        """Create relationship between entities with traceability."""
        # Create relationship with dynamic type
        query = f"""
        MATCH (source:Entity {{name: $source_name}})
        MATCH (target:Entity {{name: $target_name}})
        MATCH (d:Document) WHERE elementId(d) = $doc_id
        MERGE (source)-[r:{relation.relation.value}]->(target)
        ON CREATE SET r.confidence = $confidence,
                      r.created = timestamp()
        ON MATCH SET r.confidence = CASE WHEN $confidence > r.confidence
                                    THEN $confidence ELSE r.confidence END
        SET r += $properties
        MERGE (r)-[:EXTRACTED_FROM]->(d)
        """
        try:
            # Note: This creates a relationship between the relationship and document
            # which requires Neo4j to support relationship-to-node relationships
            # For simplicity, we'll store evidence as properties
            query = f"""
            MATCH (source:Entity {{name: $source_name}})
            MATCH (target:Entity {{name: $target_name}})
            MERGE (source)-[r:{relation.relation.value}]->(target)
            ON CREATE SET r.confidence = $confidence,
                          r.evidence = $evidence,
                          r.source_document = $doc_path,
                          r.created = timestamp()
            ON MATCH SET r.confidence = CASE WHEN $confidence > r.confidence
                                        THEN $confidence ELSE r.confidence END,
                         r.evidence = r.evidence + '\\n---\\n' + $evidence
            SET r += $properties
            """
            tx.run(
                query,
                source_name=relation.source,
                target_name=relation.target,
                confidence=relation.confidence,
                evidence=relation.evidence or "",
                doc_path=doc_id,
                properties=relation.properties,
            )
        except Exception as e:
            logger.warning(
                f"Failed to create relation {relation.source} -> {relation.target}: {e}"
            )

    def get_entity(self, name: str) -> Optional[Dict]:
        """Get entity by name."""
        with self.driver.session() as session:
            query = """
            MATCH (e:Entity {name: $name})
            OPTIONAL MATCH (e)-[:MENTIONED_IN]->(d:Document)
            RETURN e, collect(d.path) as documents
            """
            result = session.run(query, name=name)
            record = result.single()

            if record:
                entity_node = record["e"]
                return {
                    "name": entity_node["name"],
                    "type": entity_node["type"],
                    "aliases": entity_node.get("aliases", []),
                    "confidence": entity_node.get("confidence", 1.0),
                    "documents": record["documents"],
                }
            return None

    def get_entity_relationships(self, name: str) -> List[Dict]:
        """Get all relationships for an entity."""
        with self.driver.session() as session:
            query = """
            MATCH (e:Entity {name: $name})-[r]->(target:Entity)
            RETURN type(r) as relation_type,
                   target.name as target_name,
                   target.type as target_type,
                   r.confidence as confidence,
                   r.evidence as evidence
            UNION
            MATCH (source:Entity)-[r]->(e:Entity {name: $name})
            RETURN type(r) as relation_type,
                   source.name as source_name,
                   source.type as source_type,
                   r.confidence as confidence,
                   r.evidence as evidence
            """
            result = session.run(query, name=name)
            return [dict(record) for record in result]

    def search_entities(
        self, query: str, entity_type: Optional[str] = None, limit: int = 10
    ) -> List[Dict]:
        """Search entities by name."""
        with self.driver.session() as session:
            cypher_query = """
            MATCH (e:Entity)
            WHERE toLower(e.name) CONTAINS toLower($search_query)
            """
            if entity_type:
                cypher_query += " AND e.type = $type"

            cypher_query += """
            RETURN e.name as name, e.type as type, e.confidence as confidence
            ORDER BY e.confidence DESC
            LIMIT $limit
            """

            result = session.run(
                cypher_query, search_query=query, type=entity_type, limit=limit
            )
            return [dict(record) for record in result]

    def execute_cypher(self, query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """Execute raw Cypher query."""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    def get_graph_stats(self) -> Dict[str, int]:
        """Get graph statistics."""
        with self.driver.session() as session:
            query = """
            MATCH (e:Entity)
            WITH count(e) as entity_count
            MATCH ()-[r]->()
            RETURN entity_count, count(r) as relation_count
            """
            result = session.run(query)
            record = result.single()
            return {
                "entities": record["entity_count"],
                "relationships": record["relation_count"],
            }
