"""
Entity Registry module.

Canonical entity lookup system for deduplication and normalization.
"""

from .entity_registry import EntityRegistry, CanonicalEntity

__all__ = ["EntityRegistry", "CanonicalEntity"]
