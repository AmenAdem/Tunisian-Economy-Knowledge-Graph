"""
Utility to reset and rebuild the knowledge graph.
Clears Neo4j data and optionally reprocesses documents.
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

from backend.config import settings
from backend.graph.neo4j_client import Neo4jClient


def clear_graph():
    """Delete all nodes and relationships from Neo4j."""
    logger.info("Clearing Neo4j graph...")

    neo4j_client = Neo4jClient()

    try:
        # Delete all relationships first
        result = neo4j_client.execute_cypher(
            "MATCH ()-[r]->() DELETE r RETURN count(r) as deleted"
        )
        rel_count = result[0]["deleted"] if result else 0
        logger.info(f"Deleted {rel_count} relationships")

        # Delete all nodes
        result = neo4j_client.execute_cypher(
            "MATCH (n) DELETE n RETURN count(n) as deleted"
        )
        node_count = result[0]["deleted"] if result else 0
        logger.info(f"Deleted {node_count} nodes")

        # Recreate schema
        neo4j_client.initialize_schema()
        logger.info("Schema reinitialized")

        logger.success(f"✅ Graph cleared: {node_count} nodes, {rel_count} relationships deleted")

    except Exception as e:
        logger.error(f"Failed to clear graph: {e}")
        raise
    finally:
        neo4j_client.close()


def get_processed_documents():
    """List all documents that have been processed."""
    raw_dir = Path(settings.raw_dir)
    if not raw_dir.exists():
        return []

    return list(raw_dir.glob("*.pdf"))


def reprocess_documents():
    """Reprocess all documents in raw directory."""
    from backend.extraction.ner_extractor import NERExtractor
    from backend.extraction.relation_extractor import HybridExtractor, RelationExtractor
    from backend.processing.pdf_extractor import PDFExtractor
    from backend.resolution.entity_resolver import EntityResolver

    documents = get_processed_documents()

    if not documents:
        logger.warning("No documents found in raw directory")
        return

    logger.info(f"Found {len(documents)} documents to reprocess")

    # Initialize extractors
    pdf_extractor = PDFExtractor()
    ner_extractor = NERExtractor()
    relation_extractor = RelationExtractor()
    hybrid_extractor = HybridExtractor(ner_extractor, relation_extractor)
    entity_resolver = EntityResolver()
    neo4j_client = Neo4jClient()

    try:
        for doc_path in documents:
            logger.info(f"Processing: {doc_path.name}")

            try:
                # Extract text
                text, metadata = pdf_extractor.extract(str(doc_path))

                # Chunk document
                chunks = pdf_extractor.chunk_document(text, metadata)
                logger.info(f"Created {len(chunks)} chunks")

                # Process each chunk
                all_entities = []
                all_relations = []

                for idx, chunk in enumerate(chunks, 1):
                    if idx % 10 == 0:
                        logger.info(f"Processing chunk {idx}/{len(chunks)}")

                    # Extract entities and relations
                    result = hybrid_extractor.extract(chunk.content, language="fr")

                    all_entities.extend(result.entities)
                    all_relations.extend(result.relations)

                # Resolve entities
                logger.info(f"Resolving {len(all_entities)} entities...")
                resolved_entities = entity_resolver.resolve_entities(all_entities)

                # Create result with resolved entities
                from backend.ontology import ExtractionResult
                final_result = ExtractionResult(
                    entities=resolved_entities,
                    relations=all_relations,
                    source_document=str(doc_path)
                )

                # Add to Neo4j
                counts = neo4j_client.add_extraction_result(
                    final_result,
                    str(doc_path)
                )

                logger.success(
                    f"✅ {doc_path.name}: {counts['entities_added']} entities, "
                    f"{counts['relations_added']} relations"
                )

            except Exception as e:
                logger.error(f"Failed to process {doc_path.name}: {e}")
                continue

        # Show final stats
        stats = neo4j_client.get_graph_stats()
        logger.success(
            f"🎉 Reprocessing complete! Graph has {stats['entities']} entities "
            f"and {stats['relationships']} relationships"
        )

    finally:
        neo4j_client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Reset and rebuild the knowledge graph"
    )
    parser.add_argument(
        "--clear-only",
        action="store_true",
        help="Only clear the graph without reprocessing",
    )
    parser.add_argument(
        "--skip-clear",
        action="store_true",
        help="Skip clearing and only reprocess documents",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    # Confirmation
    if not args.yes:
        if not args.skip_clear:
            print("\n⚠️  WARNING: This will DELETE ALL DATA in Neo4j!")

        if not args.clear_only:
            print("📄 This will reprocess all documents in data/raw/")

        response = input("\nContinue? (yes/no): ")
        if response.lower() not in ["yes", "y"]:
            print("Aborted.")
            return

    try:
        # Clear graph
        if not args.skip_clear:
            clear_graph()

        # Reprocess documents
        if not args.clear_only:
            reprocess_documents()

    except Exception as e:
        logger.error(f"Operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    from backend.utils.logger import setup_logger
    setup_logger()
    main()
