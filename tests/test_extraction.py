"""
Tests for entity and relation extraction.
"""

import pytest

from backend.ontology import Entity, EntityType, Relation, RelationType


def test_entity_creation():
    """Test creating an entity."""
    entity = Entity(
        name="Poulina Group",
        type=EntityType.GROUP,
        aliases=["PGH", "Poulina Group Holding"],
        confidence=0.95,
    )

    assert entity.name == "Poulina Group"
    assert entity.type == EntityType.GROUP
    assert len(entity.aliases) == 2
    assert entity.confidence == 0.95


def test_relation_creation():
    """Test creating a relation."""
    relation = Relation(
        source="Abdelwaheb Ben Ayed",
        relation=RelationType.FOUNDED,
        target="Poulina Group",
        confidence=0.9,
        evidence="Abdelwaheb Ben Ayed founded Poulina Group in 1967",
    )

    assert relation.source == "Abdelwaheb Ben Ayed"
    assert relation.relation == RelationType.FOUNDED
    assert relation.target == "Poulina Group"
    assert "1967" in relation.evidence


def test_entity_type_enum():
    """Test entity type enum values."""
    assert EntityType.PERSON.value == "Person"
    assert EntityType.COMPANY.value == "Company"
    assert EntityType.GROUP.value == "Group"


def test_relation_type_enum():
    """Test relation type enum values."""
    assert RelationType.OWNS.value == "OWNS"
    assert RelationType.DIRECTOR_OF.value == "DIRECTOR_OF"
    assert RelationType.FOUNDED.value == "FOUNDED"
