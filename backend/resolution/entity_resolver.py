"""
Entity resolution for handling duplicates and variants.
Critical for multilingual Tunisian names (Arabic/French/English).
"""

from typing import Dict, List, Optional, Set, Tuple

from loguru import logger
from rapidfuzz import fuzz, process
from sentence_transformers import SentenceTransformer

from backend.ontology import Entity


class EntityResolver:
    """Resolve entity duplicates and variants using fuzzy matching and embeddings."""

    def __init__(
        self,
        fuzzy_threshold: int = 85,
        embedding_threshold: float = 0.85,
        use_embeddings: bool = True,
    ):
        """
        Initialize entity resolver.

        Args:
            fuzzy_threshold: Fuzzy matching threshold (0-100)
            embedding_threshold: Semantic similarity threshold (0-1)
            use_embeddings: Whether to use embedding-based matching
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.embedding_threshold = embedding_threshold
        self.use_embeddings = use_embeddings

        # Load embedding model for semantic similarity
        if use_embeddings:
            try:
                logger.info("Loading sentence transformer model")
                self.embedding_model = SentenceTransformer(
                    "paraphrase-multilingual-MiniLM-L12-v2"
                )
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self.use_embeddings = False

        # Known aliases (to be populated from database)
        self.alias_map: Dict[str, str] = {}

    def resolve_entities(self, entities: List[Entity]) -> List[Entity]:
        """
        Resolve duplicate entities in a list.

        Args:
            entities: List of entities to resolve

        Returns:
            Deduplicated list of entities with merged aliases
        """
        if not entities:
            return []

        logger.info(f"Resolving {len(entities)} entities")

        # Build entity name index
        canonical_entities: Dict[str, Entity] = {}
        name_to_canonical: Dict[str, str] = {}

        for entity in entities:
            canonical_name = self._find_canonical_match(
                entity, canonical_entities, name_to_canonical
            )

            if canonical_name:
                # Merge with existing entity
                canonical = canonical_entities[canonical_name]
                canonical = self._merge_entities(canonical, entity)
                canonical_entities[canonical_name] = canonical
                name_to_canonical[entity.name.lower()] = canonical_name
            else:
                # New canonical entity
                canonical_name = entity.name.lower()
                canonical_entities[canonical_name] = entity
                name_to_canonical[canonical_name] = canonical_name

        resolved = list(canonical_entities.values())
        logger.info(f"Resolved to {len(resolved)} unique entities")

        return resolved

    def _find_canonical_match(
        self,
        entity: Entity,
        canonical_entities: Dict[str, Entity],
        name_to_canonical: Dict[str, str],
    ) -> Optional[str]:
        """
        Find canonical entity that matches this entity.

        Returns canonical entity name if match found, None otherwise.
        """
        entity_name_lower = entity.name.lower()

        # Check exact match
        if entity_name_lower in name_to_canonical:
            return name_to_canonical[entity_name_lower]

        # Check known aliases
        if entity_name_lower in self.alias_map:
            canonical = self.alias_map[entity_name_lower]
            if canonical.lower() in canonical_entities:
                return canonical.lower()

        # Check fuzzy matching
        fuzzy_match = self._fuzzy_match(entity.name, canonical_entities)
        if fuzzy_match:
            return fuzzy_match

        # Check embedding similarity (expensive, use last)
        if self.use_embeddings and len(canonical_entities) > 0:
            embedding_match = self._embedding_match(entity.name, canonical_entities)
            if embedding_match:
                return embedding_match

        return None

    def _fuzzy_match(
        self, name: str, canonical_entities: Dict[str, Entity]
    ) -> Optional[str]:
        """Find fuzzy match using string similarity."""
        if not canonical_entities:
            return None

        # Normalize for comparison
        name_normalized = self._normalize_entity_name(name)

        # Get all names to compare against
        candidate_names = []
        for canonical_name, entity in canonical_entities.items():
            candidate_names.append((canonical_name, entity.name))
            for alias in entity.aliases:
                candidate_names.append((canonical_name, alias))

        # Check for exact match after normalization first
        for canonical_name, candidate_name in candidate_names:
            if self._normalize_entity_name(candidate_name) == name_normalized:
                logger.debug(f"Exact normalized match: '{name}' -> '{candidate_name}'")
                return canonical_name

        # Find best fuzzy match
        if candidate_names:
            matches = process.extract(
                name,
                [cn[1] for cn in candidate_names],
                scorer=fuzz.token_sort_ratio,
                limit=1,
            )

            if matches and matches[0][1] >= self.fuzzy_threshold:
                # Find canonical name for matched name
                matched_name = matches[0][0]
                for canonical_name, candidate_name in candidate_names:
                    if candidate_name == matched_name:
                        logger.debug(
                            f"Fuzzy match: '{name}' -> '{matched_name}' (score: {matches[0][1]})"
                        )
                        return canonical_name

        return None

    def _normalize_entity_name(self, name: str) -> str:
        """
        Normalize entity name for comparison.

        - Lowercase
        - Remove common suffixes (SA, SARL, Holding, Group)
        - Remove extra spaces
        - Remove special characters
        """
        import re

        name = name.lower().strip()

        # Remove legal suffixes
        suffixes = [
            r'\bsa\b', r'\bsarl\b', r'\bsuarl\b', r'\bholding\b',
            r'\bgroupe\b', r'\bgroup\b', r'\bs\.a\.\b', r'\bs\.a\.r\.l\.\b'
        ]
        for suffix in suffixes:
            name = re.sub(suffix, '', name)

        # Remove special characters except spaces
        name = re.sub(r'[^\w\s]', '', name)

        # Normalize spaces
        name = ' '.join(name.split())

        return name

    def _embedding_match(
        self, name: str, canonical_entities: Dict[str, Entity]
    ) -> Optional[str]:
        """Find match using semantic embeddings."""
        if not self.use_embeddings or not canonical_entities:
            return None

        try:
            # Get embedding for input name
            name_embedding = self.embedding_model.encode([name])[0]

            # Get embeddings for all canonical entities
            canonical_names = list(canonical_entities.keys())
            canonical_embeddings = self.embedding_model.encode(
                [canonical_entities[cn].name for cn in canonical_names]
            )

            # Compute cosine similarities
            from numpy import dot
            from numpy.linalg import norm

            similarities = [
                dot(name_embedding, ce) / (norm(name_embedding) * norm(ce))
                for ce in canonical_embeddings
            ]

            # Find best match
            max_sim = max(similarities)
            if max_sim >= self.embedding_threshold:
                best_idx = similarities.index(max_sim)
                canonical_name = canonical_names[best_idx]
                logger.debug(
                    f"Embedding match: '{name}' -> '{canonical_name}' (similarity: {max_sim:.3f})"
                )
                return canonical_name

        except Exception as e:
            logger.warning(f"Embedding match failed: {e}")

        return None

    def _merge_entities(self, canonical: Entity, new: Entity) -> Entity:
        """Merge two entities, combining aliases and properties."""
        # Add new name as alias if different
        if new.name.lower() != canonical.name.lower():
            if new.name not in canonical.aliases:
                canonical.aliases.append(new.name)

        # Merge aliases
        for alias in new.aliases:
            if alias not in canonical.aliases and alias.lower() != canonical.name.lower():
                canonical.aliases.append(alias)

        # Merge properties
        canonical.properties.update(new.properties)

        # Update confidence (take max)
        canonical.confidence = max(canonical.confidence, new.confidence)

        return canonical

    def add_known_aliases(self, alias_map: Dict[str, str]) -> None:
        """
        Add known aliases for entity resolution.

        Args:
            alias_map: Dictionary mapping alias -> canonical name
        """
        self.alias_map.update(alias_map)
        logger.info(f"Added {len(alias_map)} known aliases")


class ValidationQueue:
    """
    Human-in-the-loop validation queue for ambiguous entities.
    Tracks entities that need manual review.
    """

    def __init__(self):
        """Initialize validation queue."""
        self.queue: List[Dict] = []
        self.approved: Set[Tuple[str, str]] = set()  # (name1, name2) pairs
        self.rejected: Set[Tuple[str, str]] = set()

    def add_for_review(
        self,
        entity1: Entity,
        entity2: Entity,
        reason: str,
        similarity_score: float,
    ) -> None:
        """Add entity pair for manual review."""
        self.queue.append(
            {
                "entity1": entity1,
                "entity2": entity2,
                "reason": reason,
                "similarity_score": similarity_score,
            }
        )
        logger.info(f"Added entity pair for review: {entity1.name} vs {entity2.name}")

    def approve_merge(self, entity1_name: str, entity2_name: str) -> None:
        """Mark entity pair as approved for merging."""
        pair = tuple(sorted([entity1_name.lower(), entity2_name.lower()]))
        self.approved.add(pair)
        logger.info(f"Approved merge: {entity1_name} = {entity2_name}")

    def reject_merge(self, entity1_name: str, entity2_name: str) -> None:
        """Mark entity pair as different entities."""
        pair = tuple(sorted([entity1_name.lower(), entity2_name.lower()]))
        self.rejected.add(pair)
        logger.info(f"Rejected merge: {entity1_name} ≠ {entity2_name}")

    def is_approved(self, entity1_name: str, entity2_name: str) -> bool:
        """Check if entity pair is approved for merging."""
        pair = tuple(sorted([entity1_name.lower(), entity2_name.lower()]))
        return pair in self.approved

    def is_rejected(self, entity1_name: str, entity2_name: str) -> bool:
        """Check if entity pair is marked as different."""
        pair = tuple(sorted([entity1_name.lower(), entity2_name.lower()]))
        return pair in self.rejected

    def get_pending(self) -> List[Dict]:
        """Get all pending reviews."""
        return self.queue.copy()

    def clear_queue(self) -> None:
        """Clear the validation queue."""
        self.queue.clear()
        logger.info("Validation queue cleared")
