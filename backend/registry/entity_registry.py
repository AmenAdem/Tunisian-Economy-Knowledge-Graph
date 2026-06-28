"""
Entity Registry - Canonical entity lookup system.

Provides persistent storage and intelligent matching for entity deduplication.
"""

import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger
from rapidfuzz import fuzz, process

from backend.ontology import EntityType


@dataclass
class CanonicalEntity:
    """Canonical entity from registry."""

    id: int
    canonical_name: str
    entity_type: EntityType
    confidence: float
    mention_count: int = 1
    relation_count: int = 0
    aliases: List[str] = field(default_factory=list)
    first_seen_doc: Optional[str] = None
    validated: bool = False
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type.value if isinstance(self.entity_type, EntityType) else self.entity_type,
            "confidence": self.confidence,
            "mention_count": self.mention_count,
            "relation_count": self.relation_count,
            "aliases": self.aliases,
            "first_seen_doc": self.first_seen_doc,
            "validated": self.validated,
            "metadata": self.metadata,
        }


class EntityRegistry:
    """
    Canonical entity registry with intelligent matching.

    Provides:
    - Entity lookup by name/alias
    - Fuzzy matching for variants
    - Confidence scoring based on mentions
    - Alias learning
    - Human validation tracking
    """

    def __init__(self, db_path: str = "data/entity_registry.db", fuzzy_threshold: int = 85):
        """
        Initialize entity registry.

        Args:
            db_path: Path to SQLite database
            fuzzy_threshold: Minimum fuzzy match score (0-100)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.fuzzy_threshold = fuzzy_threshold

        # In-memory cache for fast lookups
        self._cache: Dict[str, CanonicalEntity] = {}
        self._alias_cache: Dict[str, str] = {}  # alias -> canonical_name

        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._load_cache()

        logger.info(f"Entity registry initialized at {self.db_path}")

    def _init_schema(self) -> None:
        """Initialize database schema."""
        schema_file = Path(__file__).parent / "schema.sql"
        with open(schema_file) as f:
            schema = f.read()
        self.conn.executescript(schema)
        self.conn.commit()

    def _load_cache(self) -> None:
        """Load frequently used entities into memory cache."""
        # Load top 1000 most mentioned entities
        cursor = self.conn.execute("""
            SELECT id, canonical_name, entity_type, confidence, mention_count,
                   relation_count, first_seen_doc, validated, metadata
            FROM entities
            ORDER BY mention_count DESC, confidence DESC
            LIMIT 1000
        """)

        for row in cursor:
            entity = self._row_to_entity(row)
            cache_key = self._cache_key(entity.canonical_name, entity.entity_type)
            self._cache[cache_key] = entity

        # Load aliases
        cursor = self.conn.execute("""
            SELECT ea.alias_name, e.canonical_name, e.entity_type
            FROM entity_aliases ea
            JOIN entities e ON ea.entity_id = e.id
        """)

        for row in cursor:
            alias_key = self._cache_key(row["alias_name"], row["entity_type"])
            self._alias_cache[alias_key] = row["canonical_name"]

        logger.info(f"Loaded {len(self._cache)} entities and {len(self._alias_cache)} aliases into cache")

    def _cache_key(self, name: str, entity_type: str) -> str:
        """Generate cache key."""
        return f"{name.lower()}:{entity_type}"

    def _row_to_entity(self, row) -> CanonicalEntity:
        """Convert database row to CanonicalEntity."""
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        # Get aliases
        cursor = self.conn.execute(
            "SELECT alias_name FROM entity_aliases WHERE entity_id = ?",
            (row["id"],)
        )
        aliases = [r["alias_name"] for r in cursor]

        return CanonicalEntity(
            id=row["id"],
            canonical_name=row["canonical_name"],
            entity_type=EntityType(row["entity_type"]) if isinstance(row["entity_type"], str) else row["entity_type"],
            confidence=row["confidence"],
            mention_count=row["mention_count"],
            relation_count=row["relation_count"],
            aliases=aliases,
            first_seen_doc=row["first_seen_doc"],
            validated=bool(row["validated"]),
            metadata=metadata,
        )

    def lookup(
        self,
        name: str,
        entity_type: EntityType,
        use_fuzzy: bool = True,
        create_if_missing: bool = False,
        source_doc: Optional[str] = None,
    ) -> Optional[CanonicalEntity]:
        """
        Lookup entity in registry.

        Args:
            name: Entity name to look up
            entity_type: Entity type
            use_fuzzy: Whether to use fuzzy matching
            create_if_missing: Create new entry if not found
            source_doc: Source document (if creating)

        Returns:
            CanonicalEntity if found, None otherwise
        """
        name = name.strip()
        type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type

        # 1. Check cache (exact match)
        cache_key = self._cache_key(name, type_str)
        if cache_key in self._cache:
            logger.debug(f"Cache hit: '{name}' ({type_str})")
            return self._cache[cache_key]

        # 2. Check alias cache
        if cache_key in self._alias_cache:
            canonical_name = self._alias_cache[cache_key]
            canonical_key = self._cache_key(canonical_name, type_str)
            if canonical_key in self._cache:
                logger.debug(f"Alias cache hit: '{name}' -> '{canonical_name}'")
                return self._cache[canonical_key]

        # 3. Database lookup (exact match)
        cursor = self.conn.execute(
            "SELECT * FROM entities WHERE LOWER(canonical_name) = LOWER(?) AND entity_type = ?",
            (name, type_str)
        )
        row = cursor.fetchone()
        if row:
            entity = self._row_to_entity(row)
            self._cache[cache_key] = entity
            logger.debug(f"DB exact match: '{name}'")
            return entity

        # 4. Check aliases in database
        cursor = self.conn.execute("""
            SELECT e.* FROM entities e
            JOIN entity_aliases ea ON e.id = ea.entity_id
            WHERE LOWER(ea.alias_name) = LOWER(?) AND e.entity_type = ?
        """, (name, type_str))
        row = cursor.fetchone()
        if row:
            entity = self._row_to_entity(row)
            self._alias_cache[cache_key] = entity.canonical_name
            logger.debug(f"DB alias match: '{name}' -> '{entity.canonical_name}'")
            return entity

        # 5. Fuzzy matching (expensive, use last)
        if use_fuzzy:
            fuzzy_match = self._fuzzy_match(name, type_str)
            if fuzzy_match:
                logger.debug(f"Fuzzy match: '{name}' -> '{fuzzy_match.canonical_name}'")
                return fuzzy_match

        # 6. Create if requested
        if create_if_missing:
            logger.info(f"Creating new entity: '{name}' ({type_str})")
            return self.register(
                name=name,
                entity_type=entity_type,
                confidence=0.5,
                source_doc=source_doc
            )

        return None

    def _fuzzy_match(self, name: str, entity_type: str) -> Optional[CanonicalEntity]:
        """Find fuzzy match using string similarity."""
        # Get all entities of this type
        cursor = self.conn.execute(
            "SELECT canonical_name FROM entities WHERE entity_type = ?",
            (entity_type,)
        )
        candidates = [row["canonical_name"] for row in cursor]

        if not candidates:
            return None

        # Add aliases
        cursor = self.conn.execute("""
            SELECT ea.alias_name
            FROM entity_aliases ea
            JOIN entities e ON ea.entity_id = e.id
            WHERE e.entity_type = ?
        """, (entity_type,))
        candidates.extend([row["alias_name"] for row in cursor])

        # Normalize for comparison
        name_normalized = self._normalize_name(name)
        candidates_normalized = [(c, self._normalize_name(c)) for c in candidates]

        # Check exact normalized match first
        for candidate, candidate_norm in candidates_normalized:
            if candidate_norm == name_normalized:
                return self.lookup(candidate, EntityType(entity_type), use_fuzzy=False)

        # Fuzzy match
        matches = process.extract(
            name,
            candidates,
            scorer=fuzz.token_sort_ratio,
            limit=1
        )

        if matches and matches[0][1] >= self.fuzzy_threshold:
            matched_name = matches[0][0]
            logger.debug(f"Fuzzy match score {matches[0][1]}: '{name}' -> '{matched_name}'")
            return self.lookup(matched_name, EntityType(entity_type), use_fuzzy=False)

        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for comparison."""
        import re

        name = name.lower().strip()

        # Remove legal suffixes
        suffixes = [
            r'\bsa\b', r'\bsarl\b', r'\bsuarl\b', r'\bholding\b',
            r'\bgroupe\b', r'\bgroup\b', r'\bs\.a\.\b', r'\bs\.a\.r\.l\.\b',
            r'\bltd\b', r'\bllc\b', r'\binc\b', r'\bcorp\b'
        ]
        for suffix in suffixes:
            name = re.sub(suffix, '', name)

        # Remove special characters except spaces
        name = re.sub(r'[^\w\s]', '', name)

        # Normalize spaces
        name = ' '.join(name.split())

        return name

    def register(
        self,
        name: str,
        entity_type: EntityType,
        confidence: float = 0.5,
        source_doc: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> CanonicalEntity:
        """
        Register new entity or update existing.

        Args:
            name: Entity name
            entity_type: Entity type
            confidence: Initial confidence score
            source_doc: Source document ID
            metadata: Additional metadata

        Returns:
            CanonicalEntity (created or updated)
        """
        name = name.strip()
        type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type

        # Check if exists (case-insensitive)
        existing = self.lookup(name, entity_type, use_fuzzy=False)
        if existing:
            # Update mention count and confidence
            return self.increment_mention(existing.canonical_name, entity_type, source_doc)

        # Create new entity
        metadata_json = json.dumps(metadata) if metadata else None

        cursor = self.conn.execute("""
            INSERT INTO entities (
                canonical_name, entity_type, confidence, mention_count,
                first_seen_doc, last_seen_doc, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, type_str, confidence, 1, source_doc, source_doc, metadata_json))

        self.conn.commit()

        entity = CanonicalEntity(
            id=cursor.lastrowid,
            canonical_name=name,
            entity_type=entity_type,
            confidence=confidence,
            mention_count=1,
            first_seen_doc=source_doc,
            metadata=metadata or {},
        )

        # Update cache
        cache_key = self._cache_key(name, type_str)
        self._cache[cache_key] = entity

        logger.info(f"Registered new entity: '{name}' ({type_str}) with confidence {confidence:.2f}")
        return entity

    def increment_mention(
        self,
        canonical_name: str,
        entity_type: EntityType,
        source_doc: Optional[str] = None
    ) -> CanonicalEntity:
        """
        Increment mention count and update confidence.

        Args:
            canonical_name: Canonical entity name
            entity_type: Entity type
            source_doc: Source document

        Returns:
            Updated CanonicalEntity
        """
        type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type

        # Get current entity
        cursor = self.conn.execute(
            "SELECT * FROM entities WHERE canonical_name = ? AND entity_type = ?",
            (canonical_name, type_str)
        )
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Entity not found for increment: '{canonical_name}'")
            return None

        new_mention_count = row["mention_count"] + 1
        new_confidence = self._calculate_confidence(
            base_confidence=row["confidence"],
            mention_count=new_mention_count,
            relation_count=row["relation_count"],
            validated=row["validated"]
        )

        # Update database
        self.conn.execute("""
            UPDATE entities
            SET mention_count = ?,
                confidence = ?,
                last_seen_doc = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_mention_count, new_confidence, source_doc, row["id"]))
        self.conn.commit()

        # Update cache
        entity = self._row_to_entity(row)
        entity.mention_count = new_mention_count
        entity.confidence = new_confidence

        cache_key = self._cache_key(canonical_name, type_str)
        self._cache[cache_key] = entity

        logger.debug(f"Incremented mention for '{canonical_name}': {new_mention_count} mentions, confidence {new_confidence:.2f}")
        return entity

    def _calculate_confidence(
        self,
        base_confidence: float,
        mention_count: int,
        relation_count: int = 0,
        validated: bool = False
    ) -> float:
        """
        Calculate confidence score based on entity statistics.

        Args:
            base_confidence: Initial confidence
            mention_count: Number of mentions
            relation_count: Number of relationships
            validated: Whether human-validated

        Returns:
            Updated confidence score (0.0 to 1.0)
        """
        confidence = base_confidence

        # Mention frequency boost (logarithmic to prevent over-confidence)
        mention_boost = min(0.25, 0.05 * math.log(mention_count + 1))
        confidence += mention_boost

        # Relation boost (entities with relationships more likely real)
        if relation_count > 0:
            relation_boost = min(0.15, 0.03 * math.log(relation_count + 1))
            confidence += relation_boost

        # Human validation gives high confidence
        if validated:
            confidence = max(confidence, 0.95)

        return min(1.0, confidence)

    def add_alias(
        self,
        canonical_name: str,
        entity_type: EntityType,
        alias: str,
        alias_type: str = "variant",
        confidence: float = 0.7,
        source: str = "learned",
        language: Optional[str] = None,
    ) -> None:
        """
        Add alias to entity.

        Args:
            canonical_name: Canonical entity name
            entity_type: Entity type
            alias: Alias name
            alias_type: Type of alias (variant, abbreviation, translation, etc.)
            confidence: Alias confidence
            source: Source of alias (learned, manual, seed)
            language: Language code (fr, ar, en)
        """
        alias = alias.strip()
        if alias.lower() == canonical_name.lower():
            return  # Don't add canonical name as alias

        type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type

        # Get entity ID
        cursor = self.conn.execute(
            "SELECT id FROM entities WHERE canonical_name = ? AND entity_type = ?",
            (canonical_name, type_str)
        )
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Entity not found for alias add: '{canonical_name}'")
            return

        entity_id = row["id"]

        # Check if alias already exists
        cursor = self.conn.execute(
            "SELECT id FROM entity_aliases WHERE entity_id = ? AND LOWER(alias_name) = LOWER(?)",
            (entity_id, alias)
        )
        if cursor.fetchone():
            logger.debug(f"Alias already exists: '{alias}' for '{canonical_name}'")
            return

        # Insert alias
        try:
            self.conn.execute("""
                INSERT INTO entity_aliases (
                    entity_id, alias_name, alias_type, confidence, source, language
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (entity_id, alias, alias_type, confidence, source, language))
            self.conn.commit()

            # Update cache
            alias_key = self._cache_key(alias, type_str)
            self._alias_cache[alias_key] = canonical_name

            logger.info(f"Added alias '{alias}' -> '{canonical_name}' ({alias_type})")
        except sqlite3.IntegrityError:
            logger.debug(f"Alias already exists (race condition): '{alias}'")

    def get_entity(self, canonical_name: str, entity_type: EntityType) -> Optional[CanonicalEntity]:
        """Get entity by canonical name."""
        return self.lookup(canonical_name, entity_type, use_fuzzy=False)

    def get_all_entities(
        self,
        entity_type: Optional[EntityType] = None,
        min_confidence: float = 0.0,
        limit: int = 1000
    ) -> List[CanonicalEntity]:
        """
        Get all entities from registry.

        Args:
            entity_type: Filter by entity type
            min_confidence: Minimum confidence threshold
            limit: Maximum number of entities

        Returns:
            List of entities
        """
        query = "SELECT * FROM entities WHERE confidence >= ?"
        params = [min_confidence]

        if entity_type:
            type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
            query += " AND entity_type = ?"
            params.append(type_str)

        query += " ORDER BY mention_count DESC, confidence DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        return [self._row_to_entity(row) for row in cursor]

    def get_stats(self) -> Dict:
        """Get registry statistics."""
        cursor = self.conn.execute("SELECT entity_type, COUNT(*) as count FROM entities GROUP BY entity_type")
        by_type = {row["entity_type"]: row["count"] for row in cursor}

        cursor = self.conn.execute("SELECT COUNT(*) as total FROM entities")
        total = cursor.fetchone()["total"]

        cursor = self.conn.execute("SELECT COUNT(*) as total FROM entity_aliases")
        alias_count = cursor.fetchone()["total"]

        cursor = self.conn.execute("SELECT AVG(confidence) as avg_conf FROM entities")
        avg_confidence = cursor.fetchone()["avg_conf"]

        return {
            "total_entities": total,
            "total_aliases": alias_count,
            "entities_by_type": by_type,
            "average_confidence": round(avg_confidence, 3) if avg_confidence else 0.0,
        }

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Entity registry closed")
