"""
Clean bad quality entities from the knowledge graph.

Removes:
- Job titles extracted as entities (CEO, PDG, etc.)
- Citations (Author YYYY)
- Publication references
- Very short names (< 3 chars) except known acronyms
- Very long names (> 100 chars = sentences)
- Generic numbered terms
"""

import re
from typing import List

from loguru import logger

from backend.graph.neo4j_client import Neo4jClient


class GraphCleaner:
    """Clean low-quality entities from the graph."""

    def __init__(self):
        self.neo4j_client = Neo4jClient()

        # Known valid acronyms to keep
        self.valid_acronyms = {
            "BNA", "STB", "UIB", "BH", "BIAT", "ATB", "BT",  # Banks
            "PGH", "SFBT", "STIL",  # Companies
            "RCD", "PDG", "DG",  # Acronyms used in context
        }

    def analyze_quality(self) -> dict:
        """Analyze graph quality and identify problematic entities."""
        logger.info("Analyzing graph quality...")

        stats = {
            "total_entities": 0,
            "job_titles": [],
            "citations": [],
            "references": [],
            "too_short": [],
            "too_long": [],
            "generic_numbered": [],
            "sentence_like": [],
            "duplicates": [],
            "total_to_remove": 0,
        }

        # Get all entities
        query = """
        MATCH (n:Entity)
        RETURN elementId(n) as id, n.name as name, n.type as type,
               n.spacy_label as label, COUNT{(n)--() } as connections
        """
        result = self.neo4j_client.execute_cypher(query)

        for record in result:
            entity_id = record["id"]
            name = record["name"]
            entity_type = record["type"]
            connections = record["connections"]

            stats["total_entities"] += 1

            # Check if it's a bad entity
            issue = self._identify_issue(name)
            if issue:
                entry = {
                    "id": entity_id,
                    "name": name,
                    "type": entity_type,
                    "connections": connections,
                }
                stats[issue].append(entry)
                stats["total_to_remove"] += 1

        # Find potential duplicates (case-insensitive)
        duplicate_query = """
        MATCH (n:Entity)
        WITH toLower(n.name) as name_lower, COLLECT(n) as nodes
        WHERE size(nodes) > 1
        RETURN name_lower, [node in nodes | {name: node.name, type: node.type, id: elementId(node)}] as variants
        ORDER BY size(variants) DESC
        LIMIT 30
        """
        dup_result = self.neo4j_client.execute_cypher(duplicate_query)
        for record in dup_result:
            stats["duplicates"].append({
                "name_lower": record["name_lower"],
                "variants": record["variants"],
            })

        return stats

    def _identify_issue(self, name: str) -> str | None:
        """Identify what's wrong with an entity name. Returns issue type or None."""
        name = name.strip()
        name_lower = name.lower()

        # Job titles
        job_titles = {
            "ceo", "pdg", "dg", "director", "directeur", "président", "president",
            "manager", "chairman", "vice-president", "vp", "cfo", "cto"
        }
        if name_lower in job_titles:
            return "job_titles"

        # Too short (unless valid acronym)
        if len(name) <= 2 and name.upper() not in self.valid_acronyms:
            return "too_short"

        # Too long (sentences)
        if len(name) > 100:
            return "too_long"

        # Citations: "Author YYYY" or "Author YYYYa"
        if re.match(r'^[\w\s]+ \d{4}[a-z]?$', name):
            return "citations"

        # Publication references with dates
        if re.search(r'\b(in|on|from)\s+\d+\s+(january|february|march|april|may|june|july|august|september|october|november|december)', name_lower):
            return "references"

        # Sentence-like (many spaces + common words)
        if name.count(' ') >= 5:
            return "sentence_like"

        # Generic numbered: "investor 1", "company 2"
        if re.match(r'^(company|investor|shareholders?|entity)\s*\d+$', name_lower):
            return "generic_numbered"

        return None

    def merge_duplicates(self, dry_run: bool = True) -> dict:
        """
        Merge duplicate entities (case/capitalization variants).

        Strategy:
        - Keep the variant with most relationships
        - Transfer all relationships to canonical entity
        - Add other variants as aliases
        - Only merge if types are compatible

        Args:
            dry_run: If True, only report what would be merged without merging

        Returns:
            Statistics about merges
        """
        logger.info("Finding duplicates to merge...")

        # Find duplicates with type info and connection counts
        duplicate_query = """
        MATCH (n:Entity)
        WITH toLower(n.name) as name_lower, COLLECT(n) as nodes
        WHERE size(nodes) > 1
        UNWIND nodes as node
        WITH name_lower, node, COUNT{(node)--()} as connections
        WITH name_lower, COLLECT({
            name: node.name,
            type: node.type,
            id: elementId(node),
            connections: connections
        }) as variants
        RETURN name_lower, variants
        ORDER BY size(variants) DESC
        """
        dup_result = self.neo4j_client.execute_cypher(duplicate_query)

        merge_groups = []
        merge_count = 0

        for record in dup_result:
            variants = record["variants"]
            name_lower = record["name_lower"]

            # Check if types are compatible
            types = {v["type"] for v in variants}
            if len(types) > 1:
                # Check for compatible type pairs
                compatible_pairs = [
                    {"Company", "Sector"},
                    {"Bank", "Company"},
                    {"Organization", "Company"},
                    {"Group", "Company"},
                ]
                compatible = any(types <= pair for pair in compatible_pairs)
                if not compatible:
                    logger.debug(f"Skipping '{name_lower}' - incompatible types: {types}")
                    continue

            # Sort by: most connections, then title case preferred
            sorted_variants = sorted(
                variants,
                key=lambda v: (v["connections"], v["name"].istitle()),
                reverse=True
            )

            canonical = sorted_variants[0]
            to_merge = sorted_variants[1:]

            merge_groups.append({
                "name_lower": name_lower,
                "canonical": canonical,
                "to_merge": to_merge,
            })
            merge_count += len(to_merge)

        stats = {
            "merge_groups": len(merge_groups),
            "entities_to_merge": merge_count,
            "groups": merge_groups,
        }

        if dry_run:
            logger.info("DRY RUN - No entities will be merged")
            self._print_merge_stats(stats)
            return stats

        logger.warning(f"Merging {merge_count} duplicate entities into {len(merge_groups)} canonical entities...")

        # Perform merges - one entity at a time for reliability
        for group in merge_groups:
            canonical_id = group["canonical"]["id"]

            for variant in group["to_merge"]:
                variant_id = variant["id"]
                variant_name = variant["name"]

                try:
                    # Step 1: Add alias to canonical
                    alias_query = """
                    MATCH (canonical:Entity)
                    WHERE elementId(canonical) = $canonical_id
                    SET canonical.aliases = coalesce(canonical.aliases, []) + [$alias_name]
                    """
                    self.neo4j_client.execute_cypher(alias_query, {
                        "canonical_id": canonical_id,
                        "alias_name": variant_name,
                    })

                    # Step 2: Get all relationships of the duplicate
                    get_rels_query = """
                    MATCH (dup:Entity)
                    WHERE elementId(dup) = $dup_id
                    OPTIONAL MATCH (dup)-[r:RELATED_TO]->(other:Entity)
                    RETURN collect({
                        other_id: elementId(other),
                        props: properties(r)
                    }) as outgoing
                    """
                    rels = self.neo4j_client.execute_cypher(get_rels_query, {"dup_id": variant_id})

                    # Step 3: Recreate relationships on canonical
                    for rel_data in rels[0]["outgoing"]:
                        if rel_data["other_id"] != canonical_id:  # Don't create self-loops
                            create_rel_query = """
                            MATCH (canonical:Entity), (other:Entity)
                            WHERE elementId(canonical) = $canonical_id
                              AND elementId(other) = $other_id
                            MERGE (canonical)-[r:RELATED_TO]->(other)
                            SET r = $props
                            """
                            self.neo4j_client.execute_cypher(create_rel_query, {
                                "canonical_id": canonical_id,
                                "other_id": rel_data["other_id"],
                                "props": rel_data["props"],
                            })

                    # Step 4: Get incoming relationships
                    get_incoming_query = """
                    MATCH (dup:Entity)
                    WHERE elementId(dup) = $dup_id
                    OPTIONAL MATCH (other:Entity)-[r:RELATED_TO]->(dup)
                    RETURN collect({
                        other_id: elementId(other),
                        props: properties(r)
                    }) as incoming
                    """
                    incoming = self.neo4j_client.execute_cypher(get_incoming_query, {"dup_id": variant_id})

                    # Step 5: Recreate incoming relationships
                    for rel_data in incoming[0]["incoming"]:
                        if rel_data["other_id"] != canonical_id:
                            create_incoming_query = """
                            MATCH (canonical:Entity), (other:Entity)
                            WHERE elementId(canonical) = $canonical_id
                              AND elementId(other) = $other_id
                            MERGE (other)-[r:RELATED_TO]->(canonical)
                            SET r = $props
                            """
                            self.neo4j_client.execute_cypher(create_incoming_query, {
                                "canonical_id": canonical_id,
                                "other_id": rel_data["other_id"],
                                "props": rel_data["props"],
                            })

                    # Step 6: Delete duplicate
                    delete_query = """
                    MATCH (dup:Entity)
                    WHERE elementId(dup) = $dup_id
                    DETACH DELETE dup
                    """
                    self.neo4j_client.execute_cypher(delete_query, {"dup_id": variant_id})

                    logger.debug(f"Merged '{variant_name}' into '{group['canonical']['name']}'")

                except Exception as e:
                    logger.error(f"Failed to merge '{variant_name}': {e}")

            logger.info(f"✅ Merged '{group['canonical']['name']}' ({len(group['to_merge'])} variants)")

        logger.info(f"✅ Merged {merge_count} duplicate entities")
        return stats

    def clean_bad_entities(self, dry_run: bool = True) -> dict:
        """
        Remove bad quality entities from the graph.

        Args:
            dry_run: If True, only report what would be deleted without deleting

        Returns:
            Statistics about deletion
        """
        stats = self.analyze_quality()

        if dry_run:
            logger.info("DRY RUN - No entities will be deleted")
            self._print_stats(stats)
            return stats

        logger.warning(f"Deleting {stats['total_to_remove']} bad entities...")

        # Collect all IDs to delete
        ids_to_delete = []
        for issue_type in ["job_titles", "citations", "references", "too_short",
                          "too_long", "generic_numbered", "sentence_like"]:
            for entry in stats[issue_type]:
                ids_to_delete.append(entry["id"])

        if ids_to_delete:
            # Delete entities and their relationships
            delete_query = """
            MATCH (n:Entity)
            WHERE elementId(n) IN $ids
            DETACH DELETE n
            """
            self.neo4j_client.execute_cypher(delete_query, {"ids": ids_to_delete})
            logger.info(f"✅ Deleted {len(ids_to_delete)} bad entities")
        else:
            logger.info("No bad entities found")

        return stats

    def _print_stats(self, stats: dict):
        """Print statistics in readable format."""
        print("\n" + "="*70)
        print("GRAPH QUALITY ANALYSIS")
        print("="*70)
        print(f"Total entities: {stats['total_entities']}")
        print(f"Entities to remove: {stats['total_to_remove']}")
        print()

        if stats['job_titles']:
            print(f"🚫 Job titles as entities ({len(stats['job_titles'])}):")
            for e in stats['job_titles'][:10]:
                print(f"   - {e['name']:<30} ({e['type']}, {e['connections']} connections)")
            if len(stats['job_titles']) > 10:
                print(f"   ... and {len(stats['job_titles']) - 10} more")
            print()

        if stats['citations']:
            print(f"📚 Citations as entities ({len(stats['citations'])}):")
            for e in stats['citations'][:10]:
                print(f"   - {e['name']:<30} ({e['type']}, {e['connections']} connections)")
            if len(stats['citations']) > 10:
                print(f"   ... and {len(stats['citations']) - 10} more")
            print()

        if stats['sentence_like']:
            print(f"💬 Sentences as entities ({len(stats['sentence_like'])}):")
            for e in stats['sentence_like'][:5]:
                print(f"   - {e['name'][:60]:<60}...")
            if len(stats['sentence_like']) > 5:
                print(f"   ... and {len(stats['sentence_like']) - 5} more")
            print()

        if stats['too_short']:
            print(f"⚠️  Very short names ({len(stats['too_short'])}):")
            for e in stats['too_short'][:15]:
                print(f"   - '{e['name']}'")
            if len(stats['too_short']) > 15:
                print(f"   ... and {len(stats['too_short']) - 15} more")
            print()

        if stats['duplicates']:
            print(f"🔄 Potential duplicates ({len(stats['duplicates'])} groups):")
            for dup in stats['duplicates'][:10]:
                variants = dup['variants']
                print(f"   '{dup['name_lower']}' has {len(variants)} variants:")
                for v in variants[:5]:
                    print(f"      - {v['name']} ({v['type']})")
                if len(variants) > 5:
                    print(f"      ... and {len(variants) - 5} more")
            if len(stats['duplicates']) > 10:
                print(f"   ... and {len(stats['duplicates']) - 10} more groups")
            print()

        print("="*70)

    def _print_merge_stats(self, stats: dict):
        """Print merge statistics in readable format."""
        print("\n" + "="*70)
        print("DUPLICATE MERGE ANALYSIS")
        print("="*70)
        print(f"Merge groups: {stats['merge_groups']}")
        print(f"Entities to merge: {stats['entities_to_merge']}")
        print()

        if stats['groups']:
            print(f"🔀 Merges to perform:")
            for group in stats['groups'][:15]:
                canonical = group['canonical']
                to_merge = group['to_merge']
                print(f"\n   Keep: {canonical['name']} ({canonical['type']}, {canonical['connections']} connections)")
                print(f"   Merge into it:")
                for v in to_merge:
                    print(f"      ← {v['name']} ({v['type']}, {v['connections']} connections)")
            if len(stats['groups']) > 15:
                print(f"\n   ... and {len(stats['groups']) - 15} more groups")

        print("\n" + "="*70)

    def close(self):
        """Close Neo4j connection."""
        self.neo4j_client.close()


def main():
    """CLI for graph cleaning."""
    import argparse

    parser = argparse.ArgumentParser(description="Clean bad entities from knowledge graph")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete bad entities (citations, job titles, etc.)",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge duplicate entities (case variants)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Both clean and merge (full cleanup)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    cleaner = GraphCleaner()

    try:
        # Default: dry-run analysis
        if not (args.clean or args.merge or args.all):
            logger.info("Running analysis (dry-run mode)...")
            stats = cleaner.analyze_quality()
            cleaner._print_stats(stats)
            print("\n💡 To delete bad entities: --clean")
            print("💡 To merge duplicates: --merge")
            print("💡 To do both: --all")
            return

        # Full cleanup
        if args.all:
            args.clean = True
            args.merge = True

        # Clean bad entities
        if args.clean:
            stats = cleaner.analyze_quality()
            cleaner._print_stats(stats)

            if stats["total_to_remove"] == 0:
                print("✅ No bad entities found.")
            else:
                if not args.yes:
                    print(f"\n⚠️  About to DELETE {stats['total_to_remove']} entities")
                    response = input("Continue? (yes/no): ")
                    if response.lower() != "yes":
                        print("Aborted.")
                        return

                cleaner.clean_bad_entities(dry_run=False)
                print("✅ Bad entities deleted!")

        # Merge duplicates
        if args.merge:
            stats = cleaner.merge_duplicates(dry_run=True)

            if stats["entities_to_merge"] == 0:
                print("✅ No duplicates found.")
            else:
                if not args.yes:
                    print(f"\n⚠️  About to MERGE {stats['entities_to_merge']} duplicate entities")
                    response = input("Continue? (yes/no): ")
                    if response.lower() != "yes":
                        print("Aborted.")
                        return

                cleaner.merge_duplicates(dry_run=False)
                print("✅ Duplicates merged!")

        print("\n✅ Graph cleanup complete!")

    finally:
        cleaner.close()


if __name__ == "__main__":
    main()
