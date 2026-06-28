"""
Find and merge duplicate entities that already exist in the graph.

Usage:
    python -m backend.utils.merge_duplicates              # Find duplicates (dry-run)
    python -m backend.utils.merge_duplicates --merge      # Actually merge them
    python -m backend.utils.merge_duplicates --threshold 90  # Adjust sensitivity
"""

import argparse

from loguru import logger

from backend.resolution.entity_linker import DuplicateMerger


def main():
    """CLI for duplicate merging."""
    parser = argparse.ArgumentParser(
        description="Find and merge duplicate entities in knowledge graph"
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Actually merge duplicates (default is dry-run)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=85,
        help="Fuzzy matching threshold (0-100, default 85)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    merger = DuplicateMerger()

    try:
        # Find duplicates
        logger.info(f"Finding duplicates (threshold: {args.threshold})...")
        duplicate_groups = merger.find_duplicates(threshold=args.threshold)

        if not duplicate_groups:
            print("✅ No duplicates found! Graph is clean.")
            return

        # Print report
        print("\n" + "="*70)
        print(f"DUPLICATE ENTITIES REPORT (threshold: {args.threshold})")
        print("="*70)
        print(f"Found {len(duplicate_groups)} groups of duplicates\n")

        total_to_merge = 0
        for i, group in enumerate(duplicate_groups, 1):
            canonical = group["canonical"]
            duplicates = group["duplicates"]
            total_connections = group["total_connections"]

            print(f"{i}. Canonical: '{canonical['name']}' ({canonical['type']})")
            print(f"   Connections: {canonical['connections']}")
            print(f"   Will merge {len(duplicates)} duplicates:")

            for dup in duplicates:
                print(f"      - '{dup['name']}' ({dup['type']}, {dup['connections']} connections)")

            total_to_merge += len(duplicates)
            print()

        print("="*70)
        print(f"Total entities to merge: {total_to_merge}")
        print(f"Total groups: {len(duplicate_groups)}")
        print("="*70)

        if not args.merge:
            print("\n💡 This is a DRY RUN. To actually merge, use --merge flag")
            print("   Example: python -m backend.utils.merge_duplicates --merge")
            return

        # Confirm merge
        if not args.yes:
            print(f"\n⚠️  About to MERGE {total_to_merge} duplicate entities into {len(duplicate_groups)} canonical nodes")
            print("⚠️  This will DELETE duplicate nodes and redirect their relationships")
            response = input("Continue? (yes/no): ")
            if response.lower() != "yes":
                print("Aborted.")
                return

        # Actually merge
        print("\n🔄 Merging duplicates...")
        merged_count = 0

        for i, group in enumerate(duplicate_groups, 1):
            canonical_name = group["canonical"]["name"]
            dup_count = len(group["duplicates"])

            print(f"[{i}/{len(duplicate_groups)}] Merging {dup_count} into '{canonical_name}'...")

            result = merger.merge_duplicates(group, dry_run=False)
            merged_count += dup_count

        print(f"\n✅ Successfully merged {merged_count} duplicate entities!")
        print(f"✅ Graph now has {len(duplicate_groups)} canonical nodes")

    finally:
        merger.close()


if __name__ == "__main__":
    main()
