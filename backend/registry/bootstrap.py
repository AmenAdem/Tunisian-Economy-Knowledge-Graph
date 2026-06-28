"""
Bootstrap entity registry from existing Neo4j graph.

Extracts all entities and their aliases from Neo4j and populates
the entity registry for future lookups.
"""

from loguru import logger

from backend.graph.neo4j_client import Neo4jClient
from backend.ontology import EntityType
from backend.registry.entity_registry import EntityRegistry


def bootstrap_from_neo4j(registry_path: str = "data/entity_registry.db") -> None:
    """
    Bootstrap entity registry from existing Neo4j graph.

    Args:
        registry_path: Path to registry database
    """
    logger.info("Starting bootstrap from Neo4j...")

    neo4j_client = Neo4jClient()
    registry = EntityRegistry(db_path=registry_path)

    try:
        # Get all entities from Neo4j
        query = """
        MATCH (n:Entity)
        RETURN n.name as name,
               n.type as type,
               n.confidence as confidence,
               n.aliases as aliases,
               COUNT{(n)--() } as relation_count
        ORDER BY n.name
        """

        results = neo4j_client.execute_cypher(query)
        logger.info(f"Found {len(results)} entities in Neo4j")

        entities_added = 0
        aliases_added = 0

        for row in results:
            name = row["name"]
            entity_type_str = row["type"]
            confidence = row["confidence"] or 0.5
            aliases = row["aliases"] or []
            relation_count = row["relation_count"]

            # Convert type string to EntityType
            try:
                entity_type = EntityType(entity_type_str)
            except ValueError:
                logger.warning(f"Unknown entity type '{entity_type_str}' for '{name}', skipping")
                continue

            # Register entity in registry
            entity = registry.register(
                name=name,
                entity_type=entity_type,
                confidence=confidence,
                source_doc="neo4j_bootstrap",
                metadata={
                    "bootstrapped": True,
                    "neo4j_relation_count": relation_count
                }
            )

            # Update relation count
            if relation_count > 0:
                registry.conn.execute(
                    "UPDATE entities SET relation_count = ? WHERE id = ?",
                    (relation_count, entity.id)
                )

            entities_added += 1

            # Add aliases
            for alias in aliases:
                if alias and alias.strip() and alias != name:
                    registry.add_alias(
                        canonical_name=name,
                        entity_type=entity_type,
                        alias=alias.strip(),
                        alias_type="variant",
                        source="neo4j",
                    )
                    aliases_added += 1

        registry.conn.commit()

        logger.success(f"Bootstrap complete:")
        logger.success(f"  - Entities added: {entities_added}")
        logger.success(f"  - Aliases added: {aliases_added}")

        # Print stats
        stats = registry.get_stats()
        logger.info(f"Registry stats: {stats}")

    finally:
        neo4j_client.close()
        registry.close()


def seed_known_entities(registry_path: str = "data/entity_registry.db") -> None:
    """
    Seed registry with well-known Tunisian entities.

    This provides high-confidence anchors for matching.
    """
    logger.info("Seeding known entities...")

    registry = EntityRegistry(db_path=registry_path)

    # Well-known Tunisian entities with aliases
    SEED_ENTITIES = [
        {
            "name": "Poulina Group Holding",
            "type": EntityType.GROUP,
            "aliases": ["PGH", "Poulina", "Groupe Poulina", "بولينا"],
            "confidence": 1.0,
        },
        {
            "name": "BIAT",
            "type": EntityType.BANK,
            "aliases": [
                "Banque Internationale Arabe de Tunisie",
                "البنك العربي الدولي لتونس",
                "Arab International Bank of Tunisia",
                "International Arab Bank of Tunisia"
            ],
            "confidence": 1.0,
        },
        {
            "name": "Banque de Tunisie",
            "type": EntityType.BANK,
            "aliases": ["BT", "Bank of Tunisia", "بنك تونس"],
            "confidence": 1.0,
        },
        {
            "name": "Banque Nationale Agricole",
            "type": EntityType.BANK,
            "aliases": ["BNA", "National Agricultural Bank", "البنك الوطني الفلاحي"],
            "confidence": 1.0,
        },
        {
            "name": "Société Tunisienne de Banque",
            "type": EntityType.BANK,
            "aliases": ["STB", "Tunisian Banking Company", "الشركة التونسية للبنك"],
            "confidence": 1.0,
        },
        {
            "name": "Union Internationale de Banques",
            "type": EntityType.BANK,
            "aliases": ["UIB", "International Union of Banks", "الاتحاد الدولي للبنوك"],
            "confidence": 1.0,
        },
        {
            "name": "Banque de l'Habitat",
            "type": EntityType.BANK,
            "aliases": ["BH", "Housing Bank", "بنك الإسكان"],
            "confidence": 1.0,
        },
        {
            "name": "Amen Bank",
            "type": EntityType.BANK,
            "aliases": ["Amen", "أمين بنك"],
            "confidence": 1.0,
        },
        {
            "name": "Attijari Bank",
            "type": EntityType.BANK,
            "aliases": ["Attijari", "التجاري بنك", "Attijariwafa Bank Tunisia"],
            "confidence": 1.0,
        },
        {
            "name": "Central Bank of Tunisia",
            "type": EntityType.BANK,
            "aliases": [
                "Banque Centrale de Tunisie",
                "BCT",
                "البنك المركزي التونسي",
                "The Central Bank"
            ],
            "confidence": 1.0,
        },
        {
            "name": "Tunisie Telecom",
            "type": EntityType.COMPANY,
            "aliases": ["TT", "اتصالات تونس"],
            "confidence": 1.0,
        },
        {
            "name": "Ooredoo Tunisia",
            "type": EntityType.COMPANY,
            "aliases": ["Ooredoo", "Tunisiana", "أوريدو تونس"],
            "confidence": 1.0,
        },
        {
            "name": "Orange Tunisia",
            "type": EntityType.COMPANY,
            "aliases": ["Orange", "أورانج تونس"],
            "confidence": 1.0,
        },
    ]

    added_count = 0
    alias_count = 0

    for seed in SEED_ENTITIES:
        # Check if already exists
        existing = registry.lookup(seed["name"], seed["type"], use_fuzzy=False)
        if existing:
            logger.debug(f"Seed entity already exists: {seed['name']}")
            continue

        # Register entity
        entity = registry.register(
            name=seed["name"],
            entity_type=seed["type"],
            confidence=seed["confidence"],
            source_doc="seed",
            metadata={"seeded": True, "validated": True}
        )

        # Mark as validated
        registry.conn.execute(
            "UPDATE entities SET validated = 1 WHERE id = ?",
            (entity.id,)
        )

        added_count += 1

        # Add aliases
        for alias in seed["aliases"]:
            registry.add_alias(
                canonical_name=seed["name"],
                entity_type=seed["type"],
                alias=alias,
                alias_type="translation" if any('؀' <= c <= 'ۿ' for c in alias) else "variant",
                confidence=1.0,
                source="seed",
            )
            alias_count += 1

    registry.conn.commit()
    registry.close()

    logger.success(f"Seeding complete: {added_count} entities, {alias_count} aliases")


def main():
    """Run bootstrap process."""
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap entity registry")
    parser.add_argument(
        "--registry",
        default="data/entity_registry.db",
        help="Path to registry database",
    )
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Only seed known entities (skip Neo4j bootstrap)",
    )
    parser.add_argument(
        "--neo4j-only",
        action="store_true",
        help="Only bootstrap from Neo4j (skip seeding)",
    )

    args = parser.parse_args()

    try:
        if not args.neo4j_only:
            logger.info("=== Seeding known entities ===")
            seed_known_entities(args.registry)

        if not args.seed_only:
            logger.info("\n=== Bootstrapping from Neo4j ===")
            bootstrap_from_neo4j(args.registry)

        logger.success("\n✅ Bootstrap process complete!")
        logger.info(f"Registry created at: {args.registry}")

    except Exception as e:
        logger.error(f"Bootstrap failed: {e}")
        raise


if __name__ == "__main__":
    main()
