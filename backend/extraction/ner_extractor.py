"""
Named Entity Recognition using spaCy.
Customized for Tunisian business context (French/Arabic/English).
"""

from typing import Dict, List, Set

import spacy
from loguru import logger

from backend.config import settings
from backend.ontology import Entity, EntityType


class NERExtractor:
    """Extract named entities using spaCy models."""

    def __init__(self):
        """Initialize NER extractor with configured spaCy models."""
        self.models = {}
        self._load_models()

        # Entity type mapping from spaCy to our ontology
        self.entity_type_map = {
            "PER": EntityType.PERSON,
            "PERSON": EntityType.PERSON,
            "ORG": EntityType.COMPANY,  # Default organizations to companies
            "ORGANIZATION": EntityType.COMPANY,
            "LOC": EntityType.LOCATION,
            "GPE": EntityType.LOCATION,
        }

        # Tunisian business keywords for entity classification
        self.company_keywords = {
            "group",
            "groupe",
            "holding",
            "sa",
            "sarl",
            "suarl",
            "bank",
            "banque",
            "telecom",
            "industries",
        }

        self.person_titles = {
            "mr",
            "m.",
            "mrs",
            "mme",
            "dr",
            "prof",
            "président",
            "directeur",
            "pdg",
            "ceo",
            "dg",
        }

    def _load_models(self) -> None:
        """Load configured spaCy models."""
        for model_name in settings.spacy_models_list:
            try:
                logger.info(f"Loading spaCy model: {model_name}")
                self.models[model_name] = spacy.load(model_name)
            except OSError:
                logger.warning(
                    f"Model {model_name} not found. Install with: python -m spacy download {model_name}"
                )

        if not self.models:
            logger.error("No spaCy models loaded! NER extraction will fail.")

    def extract_entities(self, text: str, language: str = "fr") -> List[Entity]:
        """
        Extract entities from text.

        Args:
            text: Input text
            language: Language code (fr, en, ar)

        Returns:
            List of extracted entities
        """
        # Select appropriate model
        model = self._select_model(language)
        if not model:
            logger.warning(f"No model available for language {language}")
            return []

        doc = model(text)
        entities = []
        seen_names: Set[str] = set()

        for ent in doc.ents:
            # Skip duplicates
            if ent.text in seen_names:
                continue

            # Quality filters
            if not self._is_valid_entity(ent.text, ent.label_):
                logger.debug(f"Filtered out invalid entity: '{ent.text}' ({ent.label_})")
                continue

            # Map to our entity types
            entity_type = self._classify_entity(ent.text, ent.label_)

            if entity_type:
                entity = Entity(
                    name=ent.text.strip(),
                    type=entity_type,
                    confidence=0.8,  # spaCy baseline confidence
                    properties={
                        "spacy_label": ent.label_,
                        "language": language,
                    },
                )
                entities.append(entity)
                seen_names.add(ent.text)

        logger.debug(f"Extracted {len(entities)} entities from text")
        return entities

    def _select_model(self, language: str):
        """Select appropriate spaCy model for language."""
        # Map language codes to model prefixes
        lang_map = {
            "fr": "fr_core",
            "en": "en_core",
            "ar": "ar_core",  # If Arabic model available
        }

        prefix = lang_map.get(language, "fr_core")

        # Find matching model
        for model_name, model in self.models.items():
            if model_name.startswith(prefix):
                return model

        # Fallback to any available model
        return next(iter(self.models.values())) if self.models else None

    def _is_valid_entity(self, text: str, spacy_label: str) -> bool:
        """
        Quality filters for entity extraction.

        Returns False for:
        - Job titles alone (CEO, PDG, Director)
        - Citations (Author YYYY, Author et al YYYY)
        - Very short names (< 2 chars)
        - Very long names (> 100 chars = likely sentences)
        - Names with dates/numbers in suspicious patterns
        - Publication references
        - Generic terms
        """
        text = text.strip()
        text_lower = text.lower()

        # Length filters
        if len(text) < 2:
            return False
        if len(text) > 100:
            return False

        # Job titles that should NOT be entities
        job_titles_alone = {
            "ceo", "pdg", "dg", "director", "directeur", "président", "president",
            "manager", "chairman", "vice-president", "vp", "cfo", "cto"
        }
        if text_lower in job_titles_alone:
            return False

        # Citation patterns: "Author YYYY" or "Author YYYYa/b"
        import re
        if re.match(r'^[\w\s]+ \d{4}[a-z]?$', text):
            return False
        if re.match(r'^[\w\s]+ and [\w\s]+ \d{4}$', text):
            return False

        # Full sentences (contains multiple spaces and common sentence words)
        if text.count(' ') >= 5:
            sentence_indicators = ['the', 'in', 'of', 'and', 'bought', 'sold', 'dans', 'pour', 'avec']
            if any(word in text_lower for word in sentence_indicators):
                return False

        # Publication references: "Source in DATE"
        if re.search(r'\b(in|on|from)\s+\d+\s+(january|february|march|april|may|june|july|august|september|october|november|december)', text_lower):
            return False

        # Generic numbered terms: "company 2", "investor11"
        if re.match(r'^(company|investor|shareholders?|entity)\s*\d+$', text_lower):
            return False

        # Single letter + numbers: "Z13"
        if re.match(r'^[a-z]\d+$', text_lower):
            return False

        # Domain extensions
        if text_lower in ['com', 'tn', 'org', 'net', 'fr']:
            return False

        return True

    def _classify_entity(self, text: str, spacy_label: str) -> EntityType:
        """
        Classify entity into our ontology types.

        Uses heuristics for Tunisian business context.
        """
        text_lower = text.lower()

        # Check if it's a company based on keywords
        if any(keyword in text_lower for keyword in self.company_keywords):
            # Check for specific types
            if "bank" in text_lower or "banque" in text_lower:
                return EntityType.BANK
            if "group" in text_lower or "groupe" in text_lower:
                return EntityType.GROUP
            return EntityType.COMPANY

        # Check if it's a person based on titles
        words = text_lower.split()
        if any(title in words for title in self.person_titles):
            return EntityType.PERSON

        # Use spaCy label as fallback
        return self.entity_type_map.get(spacy_label, None)

    def extract_with_context(
        self, text: str, window: int = 100
    ) -> List[Dict[str, any]]:
        """
        Extract entities with surrounding context.

        Args:
            text: Input text
            window: Character window around entity

        Returns:
            List of entities with context
        """
        entities = self.extract_entities(text)
        entities_with_context = []

        for entity in entities:
            # Find entity position in text
            start_idx = text.find(entity.name)
            if start_idx == -1:
                continue

            # Extract context
            context_start = max(0, start_idx - window)
            context_end = min(len(text), start_idx + len(entity.name) + window)
            context = text[context_start:context_end]

            entities_with_context.append(
                {
                    "entity": entity,
                    "context": context,
                    "position": start_idx,
                }
            )

        return entities_with_context
