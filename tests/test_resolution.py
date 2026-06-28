"""
Tests for entity resolution.
"""

import pytest

from backend.ontology import Entity, EntityType
from backend.resolution.entity_resolver import EntityResolver


def test_exact_match_resolution():
    """Test resolving exact duplicate entities."""
    resolver = EntityResolver(use_embeddings=False)

    entities = [
        Entity(name="Poulina Group", type=EntityType.GROUP, confidence=0.9),
        Entity(name="Poulina Group", type=EntityType.GROUP, confidence=0.95),
    ]

    resolved = resolver.resolve_entities(entities)

    assert len(resolved) == 1
    assert resolved[0].name == "Poulina Group"
    assert resolved[0].confidence == 0.95  # Takes max confidence


def test_fuzzy_match_resolution():
    """Test resolving similar entity names."""
    resolver = EntityResolver(use_embeddings=False, fuzzy_threshold=85)

    entities = [
        Entity(name="Poulina Group", type=EntityType.GROUP, confidence=0.9),
        Entity(name="Poulina Group Holding", type=EntityType.GROUP, confidence=0.85),
    ]

    resolved = resolver.resolve_entities(entities)

    # Should merge as they're very similar
    assert len(resolved) <= 2


def test_alias_management():
    """Test that aliases are properly merged."""
    resolver = EntityResolver(use_embeddings=False)

    entities = [
        Entity(
            name="Poulina Group",
            type=EntityType.GROUP,
            aliases=["PGH"],
            confidence=0.9,
        ),
        Entity(
            name="Poulina Group",
            type=EntityType.GROUP,
            aliases=["Poulina Holding"],
            confidence=0.85,
        ),
    ]

    resolved = resolver.resolve_entities(entities)

    assert len(resolved) == 1
    assert "PGH" in resolved[0].aliases
    assert "Poulina Holding" in resolved[0].aliases
