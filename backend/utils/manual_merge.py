"""
Manual entity merging and type correction utility.

For cases where automatic merge skips entities due to type conflicts,
but domain knowledge says they should be merged.
"""

from loguru import logger
from backend.graph.neo4j_client import Neo4jClient


def merge_and_fix_type(
    canonical_name: str,
    canonical_type: str,
    merge_names: list[str],
) -> None:
    """
    Manually merge entities and set correct type.

    Args:
        canonical_name: The name to keep
        canonical_type: The correct entity type (Company, Bank, etc.)
        merge_names: List of duplicate names to merge into canonical
    """
    client = Neo4jClient()

    try:
        # Find canonical entity
        find_canonical = """
        MATCH (n:Entity)
        WHERE n.name = $name
        RETURN elementId(n) as id, n.type as type, COUNT{(n)--()} as connections
        """
        results = client.execute_cypher(find_canonical, {"name": canonical_name})

        if not results:
            logger.error(f"Canonical entity '{canonical_name}' not found")
            return

        canonical_id = results[0]["id"]
        logger.info(f"Found canonical: {canonical_name} ({results[0]['type']}, {results[0]['connections']} connections)")

        # Find duplicates
        find_dupes = """
        MATCH (n:Entity)
        WHERE n.name IN $names
        RETURN elementId(n) as id, n.name as name, n.type as type, COUNT{(n)--()} as connections
        ORDER BY n.name
        """
        dupes = client.execute_cypher(find_dupes, {"names": merge_names})

        if not dupes:
            logger.warning(f"No duplicate entities found for: {merge_names}")
            return

        logger.info(f"Found {len(dupes)} duplicates to merge:")
        for d in dupes:
            logger.info(f"  - {d['name']} ({d['type']}, {d['connections']} connections)")

        # Merge each duplicate
        for dupe in dupes:
            dupe_id = dupe["id"]
            dupe_name = dupe["name"]

            # Add alias
            alias_query = """
            MATCH (canonical:Entity)
            WHERE elementId(canonical) = $canonical_id
            SET canonical.aliases = coalesce(canonical.aliases, []) + [$alias_name]
            """
            client.execute_cypher(alias_query, {
                "canonical_id": canonical_id,
                "alias_name": dupe_name,
            })

            # Transfer outgoing relationships
            transfer_out = """
            MATCH (dup:Entity)-[r:RELATED_TO]->(other:Entity)
            WHERE elementId(dup) = $dup_id
            MATCH (canonical:Entity)
            WHERE elementId(canonical) = $canonical_id
            WITH canonical, other, r
            WHERE other <> canonical AND NOT (canonical)-[:RELATED_TO]->(other)
            MERGE (canonical)-[new_r:RELATED_TO]->(other)
            SET new_r = properties(r)
            """
            client.execute_cypher(transfer_out, {
                "dup_id": dupe_id,
                "canonical_id": canonical_id,
            })

            # Transfer incoming relationships
            transfer_in = """
            MATCH (other:Entity)-[r:RELATED_TO]->(dup:Entity)
            WHERE elementId(dup) = $dup_id
            MATCH (canonical:Entity)
            WHERE elementId(canonical) = $canonical_id
            WITH canonical, other, r
            WHERE other <> canonical AND NOT (other)-[:RELATED_TO]->(canonical)
            MERGE (other)-[new_r:RELATED_TO]->(canonical)
            SET new_r = properties(r)
            """
            client.execute_cypher(transfer_in, {
                "dup_id": dupe_id,
                "canonical_id": canonical_id,
            })

            # Delete duplicate
            delete_query = """
            MATCH (dup:Entity)
            WHERE elementId(dup) = $dup_id
            DETACH DELETE dup
            """
            client.execute_cypher(delete_query, {"dup_id": dupe_id})

            logger.info(f"✅ Merged '{dupe_name}' into '{canonical_name}'")

        # Fix type on canonical
        fix_type_query = """
        MATCH (n:Entity)
        WHERE elementId(n) = $id
        SET n.type = $type
        RETURN n.name as name, n.type as type
        """
        result = client.execute_cypher(fix_type_query, {
            "id": canonical_id,
            "type": canonical_type,
        })

        logger.info(f"✅ Set type to '{canonical_type}' for '{canonical_name}'")
        logger.success(f"Merge complete: {canonical_name} ({canonical_type})")

    finally:
        client.close()


def main():
    """Run manual merges for known misclassified entities."""
    import argparse

    parser = argparse.ArgumentParser(description="Manually merge and fix entity types")
    parser.add_argument(
        "--entity",
        choices=["star", "biat", "shareholders", "all"],
        default="all",
        help="Which entity to fix",
    )
    args = parser.parse_args()

    logger.info("Starting manual entity merges...")

    if args.entity in ["star", "all"]:
        logger.info("\n=== Fixing STAR ===")
        merge_and_fix_type(
            canonical_name="STAR",
            canonical_type="Company",
            merge_names=["Star"],
        )

    if args.entity in ["biat", "all"]:
        logger.info("\n=== Fixing BIAT ===")
        merge_and_fix_type(
            canonical_name="BIAT",
            canonical_type="Bank",  # BIAT is Banque Internationale Arabe de Tunisie
            merge_names=["Biat"],
        )

    if args.entity in ["shareholders", "all"]:
        logger.info("\n=== Fixing Shareholders ===")
        merge_and_fix_type(
            canonical_name="Shareholders",
            canonical_type="Group",
            merge_names=["shareholders"],
        )

    logger.success("✅ All manual merges complete!")


if __name__ == "__main__":
    main()
