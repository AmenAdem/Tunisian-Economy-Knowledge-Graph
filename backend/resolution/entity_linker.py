"""
Entity linking - connects extracted entities to existing graph nodes.

Critical for preventing duplicate nodes and linking to canonical entities.
"""

import re
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger
from rapidfuzz import fuzz, process

from backend.graph.neo4j_client import Neo4jClient
from backend.ontology import Entity, EntityType


class EntityLinker:
    """
    Link extracted entities to existing nodes in Neo4j.

    Prevents duplicate node creation by:
    1. Checking if entity already exists (exact match, aliases)
    2. Fuzzy matching against existing entities
    3. Splitting compound entities ("X and Y")
    4. Acronym expansion (STB → Société Tunisienne de Banque)
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """Initialize entity linker."""
        self.neo4j_client = neo4j_client or Neo4jClient()

        # Cache of existing entities from Neo4j
        self.entity_cache: Dict[str, Dict] = {}
        self.acronym_map: Dict[str, str] = {}

        # Known Tunisian business acronyms
        self.known_acronyms = {
            "STB": "Société Tunisienne de Banque",
            "BNA": "Banque Nationale Agricole",
            "BIAT": "Banque Internationale Arabe de Tunisie",
            "BH": "Banque de l'Habitat",
            "ATB": "Arab Tunisian Bank",
            "UIB": "Union Internationale de Banques",
            "BT": "Banque de Tunisie",
            "PGH": "Poulina Group Holding",
            "SFBT": "Société de Fabrication des Boissons de Tunisie",
            "STIL": "Société Tunisienne des Industries de Lait",
        }

        self._refresh_cache()

    def _refresh_cache(self):
        """Load existing entities from Neo4j into cache."""
        logger.info("Refreshing entity cache from Neo4j...")

        query = """
        MATCH (n:Entity)
        RETURN n.name as name, n.type as type,
               n.aliases as aliases, elementId(n) as id
        """

        result = self.neo4j_client.execute_cypher(query)

        self.entity_cache.clear()
        self.acronym_map.clear()

        for record in result:
            name = record["name"]
            name_lower = name.lower()
            entity_type = record["type"]
            aliases = record.get("aliases", []) or []
            entity_id = record["id"]

            # Store in cache
            entity_data = {
                "name": name,
                "type": entity_type,
                "aliases": aliases,
                "id": entity_id,
            }

            self.entity_cache[name_lower] = entity_data

            # Also cache by aliases
            for alias in aliases:
                self.entity_cache[alias.lower()] = entity_data

            # Build acronym map
            if len(name) <= 5 and name.isupper():
                self.acronym_map[name] = name

        logger.info(f"Cached {len(self.entity_cache)} entities from Neo4j")

    def link_entities(self, entities: List[Entity]) -> List[Entity]:
        """
        Link extracted entities to existing graph nodes.

        Returns:
            List of entities with canonical names and IDs where matched
        """
        linked_entities = []

        for entity in entities:
            # Split compound entities first
            split_entities = self._split_compound_entity(entity)

            for ent in split_entities:
                # Try to link to existing node
                linked = self._link_entity(ent)
                linked_entities.append(linked)

        return linked_entities

    def _split_compound_entity(self, entity: Entity) -> List[Entity]:
        """
        Split compound entities like "STB and BNA" into separate entities.

        Returns list of entities (original if no split needed).
        """
        name = entity.name

        # Patterns for compound entities
        patterns = [
            r'\band\b',      # "STB and BNA"
            r'\bet\b',       # "Poulina et Ben Yedder"
            r'\bor\b',       # "Company A or Company B"
            r'\bou\b',       # "Banque A ou Banque B"
            r'[/,]',         # "STB/BNA" or "STB, BNA"
        ]

        for pattern in patterns:
            if re.search(pattern, name, re.IGNORECASE):
                # Split by the pattern
                parts = re.split(pattern, name, flags=re.IGNORECASE)
                parts = [p.strip() for p in parts if p.strip()]

                if len(parts) >= 2:
                    logger.info(f"Split compound entity '{name}' → {parts}")

                    # Create separate entities
                    entities = []
                    for part in parts:
                        # Skip very short parts unless they're known acronyms
                        if len(part) < 2 and part.upper() not in self.known_acronyms:
                            continue

                        entities.append(Entity(
                            name=part,
                            type=entity.type,
                            aliases=entity.aliases,
                            confidence=entity.confidence * 0.9,  # Slight confidence penalty
                            properties=entity.properties.copy(),
                        ))

                    return entities if entities else [entity]

        # No split needed
        return [entity]

    def _link_entity(self, entity: Entity) -> Entity:
        """
        Link entity to existing node if found.

        Returns entity with updated name (canonical) and graph_id if matched.
        """
        name = entity.name
        name_lower = name.lower()

        # 1. Exact match (case-insensitive)
        if name_lower in self.entity_cache:
            match = self.entity_cache[name_lower]
            logger.debug(f"Exact match: '{name}' → '{match['name']}'")
            return self._update_entity_with_match(entity, match)

        # 2. Acronym expansion
        if name.isupper() and len(name) <= 5 and name in self.known_acronyms:
            expanded = self.known_acronyms[name]
            if expanded.lower() in self.entity_cache:
                match = self.entity_cache[expanded.lower()]
                logger.debug(f"Acronym match: '{name}' → '{match['name']}'")
                return self._update_entity_with_match(entity, match)

        # 3. Normalized match (remove suffixes)
        normalized = self._normalize_name(name)
        for cached_name, cached_entity in self.entity_cache.items():
            if self._normalize_name(cached_name) == normalized:
                logger.debug(f"Normalized match: '{name}' → '{cached_entity['name']}'")
                return self._update_entity_with_match(entity, cached_entity)

        # 4. Fuzzy match (for typos, variations)
        fuzzy_match = self._fuzzy_match(name)
        if fuzzy_match:
            logger.debug(f"Fuzzy match: '{name}' → '{fuzzy_match['name']}'")
            return self._update_entity_with_match(entity, fuzzy_match)

        # No match found - this is a new entity
        logger.debug(f"New entity (no match): '{name}'")
        return entity

    def _normalize_name(self, name: str) -> str:
        """
        Normalize name for comparison.

        Removes:
        - Legal suffixes (SA, SARL, Holding, Group)
        - Special characters
        - Extra spaces
        """
        name = name.lower().strip()

        # Remove legal suffixes
        suffixes = [
            r'\bsa\b', r'\bsarl\b', r'\bsuarl\b', r'\bs\.a\.\b', r'\bs\.a\.r\.l\.\b',
            r'\bholding\b', r'\bgroupe\b', r'\bgroup\b',
            r'\bbank\b', r'\bbanque\b',
            r'\bcompany\b', r'\bcompanie\b', r'\bsociété\b', r'\bsociete\b',
        ]

        for suffix in suffixes:
            name = re.sub(suffix, '', name, flags=re.IGNORECASE)

        # Remove special characters
        name = re.sub(r'[^\w\s]', '', name)

        # Normalize whitespace
        name = ' '.join(name.split())

        return name

    def _fuzzy_match(self, name: str, threshold: int = 85) -> Optional[Dict]:
        """
        Find fuzzy match in cache.

        Returns matched entity data or None.
        """
        if not self.entity_cache:
            return None

        # Get all cached names
        cached_names = list(self.entity_cache.keys())

        # Find best match
        matches = process.extract(
            name.lower(),
            cached_names,
            scorer=fuzz.token_sort_ratio,
            limit=1,
        )

        if matches and matches[0][1] >= threshold:
            matched_name = matches[0][0]
            return self.entity_cache[matched_name]

        return None

    def _update_entity_with_match(self, entity: Entity, match: Dict) -> Entity:
        """Update entity with canonical name and graph ID from match."""
        # Use canonical name from graph
        canonical_name = match["name"]

        # Add original name as alias if different
        if entity.name.lower() != canonical_name.lower():
            if entity.name not in entity.aliases:
                entity.aliases.append(entity.name)

        # Update to canonical name
        entity.name = canonical_name

        # Store graph ID for later use
        entity.properties["graph_id"] = match["id"]
        entity.properties["matched"] = "true"

        return entity

    def close(self):
        """Close Neo4j connection."""
        if self.neo4j_client:
            self.neo4j_client.close()


class DuplicateMerger:
    """
    Find and merge duplicate nodes that already exist in the graph.

    Post-processing tool to clean up existing duplicates.
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """Initialize duplicate merger."""
        self.neo4j_client = neo4j_client or Neo4jClient()

    def find_duplicates(self, threshold: int = 85) -> List[Dict]:
        """
        Find potential duplicate entities in the graph.

        Returns list of duplicate groups.
        """
        logger.info("Finding duplicate entities...")

        # Get all entities
        query = """
        MATCH (n:Entity)
        RETURN elementId(n) as id, n.name as name, n.type as type,
               n.aliases as aliases, COUNT{(n)--() } as connections
        ORDER BY connections DESC
        """

        result = self.neo4j_client.execute_cypher(query)
        entities = list(result)

        # Find duplicates using fuzzy matching
        duplicates = []
        processed = set()

        for i, entity1 in enumerate(entities):
            if entity1["id"] in processed:
                continue

            name1 = entity1["name"]
            normalized1 = self._normalize_name(name1)

            # Find similar entities
            group = [entity1]

            for j, entity2 in enumerate(entities[i+1:], i+1):
                if entity2["id"] in processed:
                    continue

                name2 = entity2["name"]
                normalized2 = self._normalize_name(name2)

                # Check if they're similar
                if self._are_duplicates(normalized1, normalized2, name1, name2, threshold):
                    group.append(entity2)
                    processed.add(entity2["id"])

            if len(group) > 1:
                duplicates.append({
                    "canonical": group[0],  # Keep entity with most connections
                    "duplicates": group[1:],
                    "total_connections": sum(e["connections"] for e in group),
                })
                for e in group:
                    processed.add(e["id"])

        logger.info(f"Found {len(duplicates)} duplicate groups")
        return duplicates

    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison."""
        name = name.lower().strip()

        # Remove legal suffixes
        suffixes = [
            r'\bsa\b', r'\bsarl\b', r'\bholding\b', r'\bgroup\b', r'\bgroupe\b',
            r'\bbank\b', r'\bbanque\b', r'\bcompany\b', r'\bsociété\b',
        ]

        for suffix in suffixes:
            name = re.sub(suffix, '', name, flags=re.IGNORECASE)

        name = re.sub(r'[^\w\s]', '', name)
        return ' '.join(name.split())

    def _are_duplicates(self, norm1: str, norm2: str, name1: str, name2: str, threshold: int) -> bool:
        """Check if two entities are duplicates."""
        # Exact normalized match
        if norm1 == norm2:
            return True

        # Fuzzy match
        score = fuzz.token_sort_ratio(norm1, norm2)
        if score >= threshold:
            return True

        # One is acronym of the other
        if len(name1) <= 5 and name1.isupper():
            if name1.lower() in norm2.split():
                return True
        if len(name2) <= 5 and name2.isupper():
            if name2.lower() in norm1.split():
                return True

        return False

    def merge_duplicates(self, duplicate_group: Dict, dry_run: bool = True) -> Dict:
        """
        Merge duplicate nodes into canonical node.

        Args:
            duplicate_group: Group from find_duplicates()
            dry_run: If True, only show what would be merged

        Returns:
            Statistics about merge
        """
        canonical = duplicate_group["canonical"]
        duplicates = duplicate_group["duplicates"]

        canonical_id = canonical["id"]
        duplicate_ids = [d["id"] for d in duplicates]
        duplicate_names = [d["name"] for d in duplicates]

        logger.info(f"Merging {len(duplicates)} duplicates into '{canonical['name']}'")

        if dry_run:
            return {
                "canonical": canonical["name"],
                "merged": duplicate_names,
                "dry_run": True,
            }

        # Merge in Neo4j
        merge_query = """
        // Get canonical node
        MATCH (canonical:Entity)
        WHERE elementId(canonical) = $canonical_id

        // Get duplicate nodes
        MATCH (dup:Entity)
        WHERE elementId(dup) IN $duplicate_ids

        // Merge aliases
        WITH canonical, COLLECT(dup) as duplicates
        UNWIND duplicates as dup
        SET canonical.aliases = coalesce(canonical.aliases, []) +
                                coalesce([a IN dup.aliases WHERE NOT a IN canonical.aliases], []) +
                                CASE WHEN NOT dup.name IN canonical.aliases THEN [dup.name] ELSE [] END

        // Redirect all relationships to canonical
        WITH canonical, duplicates
        UNWIND duplicates as dup
        OPTIONAL MATCH (dup)-[r]->(other)
        WHERE other <> canonical
        WITH canonical, dup, r, other
        CALL {
            WITH canonical, r, other
            WITH canonical, type(r) as relType, properties(r) as props, other
            CALL apoc.create.relationship(canonical, relType, props, other) YIELD rel
            RETURN rel
        }
        WITH canonical, dup, r
        DELETE r

        WITH canonical, COLLECT(dup) as duplicates
        UNWIND duplicates as dup
        OPTIONAL MATCH (other)-[r]->(dup)
        WHERE other <> canonical
        WITH canonical, dup, r, other
        CALL {
            WITH canonical, r, other
            WITH other, type(r) as relType, properties(r) as props, canonical
            CALL apoc.create.relationship(other, relType, props, canonical) YIELD rel
            RETURN rel
        }
        WITH canonical, dup, r
        DELETE r

        // Delete duplicate nodes
        WITH canonical, COLLECT(DISTINCT dup) as duplicates
        UNWIND duplicates as dup
        DETACH DELETE dup

        RETURN canonical.name as canonical_name, size(duplicates) as merged_count
        """

        result = self.neo4j_client.execute_cypher(
            merge_query,
            {
                "canonical_id": canonical_id,
                "duplicate_ids": duplicate_ids,
            }
        )

        return {
            "canonical": canonical["name"],
            "merged": duplicate_names,
            "dry_run": False,
        }

    def close(self):
        """Close Neo4j connection."""
        if self.neo4j_client:
            self.neo4j_client.close()
