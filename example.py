#!/usr/bin/env python3
"""
Example script demonstrating the extraction pipeline.
Run this after setup to verify everything works.
"""

from backend.ontology import Entity, EntityType, ExtractionResult, Relation, RelationType


def example_extraction():
    """Example of creating entities and relations manually."""
    print("🔍 Example: Tunisian Economy Knowledge Graph\n")

    # Create entities
    person = Entity(
        name="Abdelwaheb Ben Ayed",
        type=EntityType.PERSON,
        aliases=["Ben Ayed"],
        confidence=0.95,
    )

    group = Entity(
        name="Poulina Group",
        type=EntityType.GROUP,
        aliases=["PGH", "Poulina Group Holding"],
        confidence=0.98,
    )

    company = Entity(
        name="Tunisie Telecom",
        type=EntityType.COMPANY,
        confidence=0.92,
    )

    sector = Entity(
        name="Telecommunications",
        type=EntityType.SECTOR,
        confidence=1.0,
    )

    # Create relationships
    founded_relation = Relation(
        source="Abdelwaheb Ben Ayed",
        relation=RelationType.FOUNDED,
        target="Poulina Group",
        confidence=0.95,
        evidence="Abdelwaheb Ben Ayed founded Poulina Group in 1967",
    )

    operates_relation = Relation(
        source="Tunisie Telecom",
        relation=RelationType.OPERATES_IN,
        target="Telecommunications",
        confidence=0.99,
    )

    # Create extraction result
    result = ExtractionResult(
        entities=[person, group, company, sector],
        relations=[founded_relation, operates_relation],
    )

    # Display results
    print(f"✅ Extracted {len(result.entities)} entities:")
    for entity in result.entities:
        print(f"  - {entity.name} ({entity.type.value})")
        if entity.aliases:
            print(f"    Aliases: {', '.join(entity.aliases)}")

    print(f"\n✅ Extracted {len(result.relations)} relationships:")
    for relation in result.relations:
        print(f"  - {relation.source} → {relation.relation.value} → {relation.target}")
        if relation.evidence:
            print(f"    Evidence: {relation.evidence[:80]}...")

    print("\n📊 This data would be stored in Neo4j with full traceability.\n")

    return result


def example_cypher_queries():
    """Example Cypher queries for Neo4j."""
    print("📝 Example Cypher Queries:\n")

    queries = [
        {
            "description": "Find who owns a company",
            "cypher": """
MATCH (person:Entity)-[:OWNS]->(company:Entity {name: 'Poulina Group'})
RETURN person.name as owner, person.type as type
            """,
        },
        {
            "description": "Find companies in a sector",
            "cypher": """
MATCH (company:Entity)-[:OPERATES_IN]->(sector:Entity {type: 'Sector'})
WHERE toLower(sector.name) CONTAINS 'telecom'
RETURN company.name, company.type
            """,
        },
        {
            "description": "Find shared directors",
            "cypher": """
MATCH (c1:Entity)<-[:DIRECTOR_OF]-(person:Entity)-[:DIRECTOR_OF]->(c2:Entity)
WHERE c1 <> c2
RETURN c1.name, c2.name, person.name as shared_director
LIMIT 10
            """,
        },
        {
            "description": "Find path between two entities",
            "cypher": """
MATCH path = shortestPath(
  (e1:Entity {name: 'Poulina Group'})-[*1..3]-(e2:Entity {name: 'Tunisie Telecom'})
)
RETURN path
            """,
        },
    ]

    for i, query in enumerate(queries, 1):
        print(f"{i}. {query['description']}:")
        print(query["cypher"])
        print()


if __name__ == "__main__":
    print("=" * 70)
    print("Tunisian Economy Knowledge Graph - Example")
    print("=" * 70)
    print()

    # Run examples
    result = example_extraction()
    print()
    example_cypher_queries()

    print("💡 To use the full pipeline:")
    print("  1. Start the API: uvicorn backend.api.main:app --reload")
    print("  2. Upload a PDF at http://localhost:8000/docs")
    print("  3. View extracted entities in Neo4j Browser")
    print()
    print("=" * 70)
