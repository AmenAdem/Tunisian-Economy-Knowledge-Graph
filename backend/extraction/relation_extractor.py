"""
Relationship extraction using LLM (OpenRouter or Ollama).
Extracts structured relationships between entities.
"""

import json
from typing import List, Optional

from loguru import logger

from backend.config import settings
from backend.llm import OpenRouterClient, OllamaClient, BaseLLMClient
from backend.ontology import (
    ENTITY_DESCRIPTIONS,
    RELATION_DESCRIPTIONS,
    RELATION_TYPE_ALIASES,
    Entity,
    EntityType,
    ExtractionResult,
    Relation,
    RelationType,
)


class RelationExtractor:
    """Extract relationships between entities using LLM."""

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """
        Initialize relation extractor with LLM client.

        Args:
            llm_client: LLM client (defaults to configured provider)
        """
        if llm_client:
            self.llm_client = llm_client
            self.fallback_client = None
        else:
            # Auto-select based on config
            if settings.llm_provider == "openrouter":
                if not settings.openrouter_api_key:
                    logger.warning("OpenRouter API key not set, falling back to Ollama")
                    self.llm_client = OllamaClient(
                        host=settings.ollama_host,
                        model=settings.ollama_model
                    )
                    self.fallback_client = None
                else:
                    self.llm_client = OpenRouterClient(
                        api_key=settings.openrouter_api_key,
                        model=settings.openrouter_model,
                        base_url=settings.openrouter_base_url,
                        timeout=settings.openrouter_timeout,
                        max_retries=settings.openrouter_max_retries,
                    )
                    # Set up Ollama as fallback
                    try:
                        self.fallback_client = OllamaClient(
                            host=settings.ollama_host,
                            model=settings.ollama_model
                        )
                        if not self.fallback_client.is_available():
                            self.fallback_client = None
                    except Exception:
                        self.fallback_client = None
            else:
                self.llm_client = OllamaClient(
                    host=settings.ollama_host,
                    model=settings.ollama_model
                )
                self.fallback_client = None

        logger.info(
            f"Relation extractor initialized with {type(self.llm_client).__name__}"
            + (f" (fallback: {type(self.fallback_client).__name__})" if self.fallback_client else "")
        )

    def extract_relations(
        self,
        text: str,
        entities: Optional[List[Entity]] = None,
        context_before: str = "",
        context_after: str = ""
    ) -> ExtractionResult:
        """
        Extract entities and relationships from text.

        Args:
            text: Input text
            entities: Optional pre-extracted entities from NER
            context_before: Optional context from previous chunk
            context_after: Optional context from next chunk

        Returns:
            ExtractionResult with entities and relations
        """
        import time
        start_time = time.time()

        logger.debug(f"Extracting relations from text of length {len(text)}")
        logger.trace(f"🔍 Starting relation extraction:")
        logger.trace(f"  Text length: {len(text)} chars")
        logger.trace(f"  Pre-extracted entities: {len(entities) if entities else 0}")

        # Quality check: skip low-value chunks
        if self._is_low_quality_chunk(text):
            logger.info(f"⏭️  Skipping low-quality chunk (TOC, headers, or page numbers)")
            return ExtractionResult(entities=entities or [], relations=[])

        if entities:
            logger.trace(f"  Entity names: {', '.join([e.name for e in entities[:10]])}{'...' if len(entities) > 10 else ''}")

        prompt = self._build_prompt(text, entities, context_before, context_after)
        system_prompt = self._get_system_prompt()

        logger.trace(f"  Built prompt length: {len(prompt)} chars")
        logger.trace(f"  System prompt length: {len(system_prompt)} chars")

        # Try primary LLM
        try:
            llm_start = time.time()
            result_json = self.llm_client.complete_json(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=2000,
            )
            llm_elapsed = time.time() - llm_start

            logger.trace(f"  LLM call completed in {llm_elapsed:.2f}s")
            logger.trace(f"  Raw JSON keys: {list(result_json.keys())}")
            logger.trace(f"  Entities in response: {len(result_json.get('entities', []))}")
            logger.trace(f"  Relations in response: {len(result_json.get('relations', []))}")

            parse_start = time.time()
            result = self._parse_response(json.dumps(result_json), entities)
            parse_elapsed = time.time() - parse_start

            total_elapsed = time.time() - start_time

            logger.info(
                f"✅ Extracted {len(result.entities)} entities and {len(result.relations)} relations "
                f"in {total_elapsed:.2f}s (LLM: {llm_elapsed:.2f}s, Parse: {parse_elapsed:.2f}s)"
            )
            logger.trace(f"  Final entities: {', '.join([e.name for e in result.entities[:10]])}{'...' if len(result.entities) > 10 else ''}")
            logger.trace(f"  Final relations: {len(result.relations)}")

            return result

        except Exception as e:
            primary_elapsed = time.time() - start_time
            logger.error(f"❌ Primary LLM extraction failed after {primary_elapsed:.2f}s: {e}")
            logger.trace(f"  Error type: {type(e).__name__}")
            logger.trace(f"  Error details: {str(e)[:200]}")

            # Try fallback if available
            if self.fallback_client:
                logger.warning("🔄 Attempting fallback to Ollama...")
                try:
                    fallback_start = time.time()
                    result_json = self.fallback_client.complete_json(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=0.1,
                        max_tokens=2000,
                    )
                    fallback_elapsed = time.time() - fallback_start

                    result = self._parse_response(json.dumps(result_json), entities)

                    total_elapsed = time.time() - start_time
                    logger.info(
                        f"✅ Fallback extraction succeeded: {len(result.entities)} entities, "
                        f"{len(result.relations)} relations in {total_elapsed:.2f}s "
                        f"(Fallback: {fallback_elapsed:.2f}s)"
                    )
                    return result

                except Exception as fallback_error:
                    fallback_elapsed = time.time() - fallback_start
                    logger.error(f"❌ Fallback extraction also failed after {fallback_elapsed:.2f}s: {fallback_error}")

            # Return NER entities if both fail
            total_elapsed = time.time() - start_time
            logger.warning(f"⚠️  Returning NER entities only (no relations) - Total time: {total_elapsed:.2f}s")
            return ExtractionResult(entities=entities or [], relations=[])

    def _get_system_prompt(self) -> str:
        """Get system prompt for LLM (simplified and focused)."""
        entity_types = "\n".join(
            f"- {et.value}: {desc}" for et, desc in ENTITY_DESCRIPTIONS.items()
        )

        relation_types = "\n".join(
            f"- {rt.value}: {desc}" for rt, desc in RELATION_DESCRIPTIONS.items()
        )

        return f"""Extract business entities and relationships from Tunisian economic text.

ENTITY TYPES (use ONLY these):
{entity_types}

RELATIONSHIP TYPES (use ONLY these):
{relation_types}

RULES:
1. Extract ONLY named entities (proper nouns): people, companies, banks, organizations
2. Extract ONLY explicit relationships stated in the text
3. Skip: job titles alone, dates, page numbers, table of contents entries
4. Use exact relation types above (e.g., "DIRECTOR_OF", not "CEO_OF" or "is_director_of")
5. If no clear relationships exist, return empty arrays

EXAMPLE 1:
Input: "Aziz Miled est PDG de Poulina Group Holding depuis 1990."
Output:
{{
  "entities": [
    {{"name": "Aziz Miled", "type": "Person", "confidence": 0.95}},
    {{"name": "Poulina Group Holding", "type": "Group", "confidence": 0.95}}
  ],
  "relations": [
    {{
      "source": "Aziz Miled",
      "relation": "DIRECTOR_OF",
      "target": "Poulina Group Holding",
      "confidence": 0.95,
      "evidence": "Aziz Miled est PDG de Poulina Group Holding"
    }}
  ]
}}

EXAMPLE 2:
Input: "TABLE OF CONTENTS: Activity Report 11, Financial Situation 28, Appendix 75"
Output:
{{
  "entities": [],
  "relations": []
}}

Return ONLY valid JSON. No explanatory text."""

    def _is_low_quality_chunk(self, text: str) -> bool:
        """
        Check if chunk is low quality (TOC, headers, page numbers).

        Returns True if chunk should be skipped.
        """
        text_lower = text.lower()

        # Skip if too short
        if len(text) < 100:
            return True

        # Skip table of contents indicators
        toc_patterns = [
            "table of contents",
            "sommaire",
            "appendix",
            "annexe",
            "page ",
            "   •",  # Bullet points with page numbers
            "........",  # Dotted lines to page numbers
        ]
        if any(pattern in text_lower for pattern in toc_patterns):
            return True

        # Skip if mostly page numbers and punctuation
        # Count alphanumeric vs non-alphanumeric chars
        alphanum_count = sum(c.isalnum() for c in text)
        if alphanum_count < len(text) * 0.5:  # Less than 50% actual content
            return True

        # Skip if contains many section numbers (1., 2., 3., etc.)
        section_count = sum(1 for i in range(10) if f"{i}." in text or f" {i} " in text)
        if section_count > 5:
            return True

        return False

    def _build_prompt(
        self,
        text: str,
        entities: Optional[List[Entity]] = None,
        context_before: str = "",
        context_after: str = ""
    ) -> str:
        """Build extraction prompt with optional context window."""
        prompt = "Extract entities and relationships from this Tunisian business text:\n\n"

        # Add context from previous chunk if available
        if context_before:
            prompt += f"""[CONTEXT FROM PREVIOUS SECTION]:
...{context_before}

"""

        # Main text
        prompt += f"""[MAIN TEXT TO ANALYZE]:
{text[:2000]}  # Limit text length for LLM context

"""

        # Add context from next chunk if available
        if context_after:
            prompt += f"""[CONTEXT FROM NEXT SECTION]:
{context_after}...

"""

        if entities:
            entity_names = [e.name for e in entities[:20]]  # Limit to 20 entities
            prompt += f"""
KNOWN ENTITIES (from NER):
{', '.join(entity_names)}

Focus on finding relationships between these entities and any additional entities you discover.
"""

        prompt += """
Extract all entities and their relationships from the [MAIN TEXT TO ANALYZE] section.
Use the context sections to better understand relationships that span across sections.
Return your response as valid JSON only, no other text."""

        return prompt

    def _parse_response(
        self, response_text: str, ner_entities: Optional[List[Entity]] = None
    ) -> ExtractionResult:
        """Parse LLM JSON response into ExtractionResult."""
        try:
            data = json.loads(response_text)

            # Parse entities
            entities = []
            for ent_data in data.get("entities", []):
                try:
                    entity_name = ent_data["name"].strip()
                    raw_type = ent_data["type"]

                    # Quality validation
                    if not self._is_valid_entity_name(entity_name):
                        logger.warning(f"❌ Rejected entity '{entity_name}' - failed quality checks")
                        continue

                    # Strict validation: only accept valid EntityType values
                    try:
                        entity_type = EntityType(raw_type)
                    except ValueError:
                        logger.warning(f"❌ Rejected entity '{entity_name}' - invalid type: '{raw_type}'")
                        continue

                    entity = Entity(
                        name=entity_name,
                        type=entity_type,
                        aliases=ent_data.get("aliases", []),
                        confidence=ent_data.get("confidence", 0.8),
                    )
                    entities.append(entity)
                except (KeyError, ValueError) as e:
                    logger.warning(f"❌ Failed to parse entity: {e}")
                    continue

            # Merge with NER entities if provided
            if ner_entities:
                entities = self._merge_entities(entities, ner_entities)

            # Parse relations with strict validation
            relations = []
            for rel_data in data.get("relations", []):
                try:
                    raw_relation = rel_data["relation"]

                    # Validation 1: Reject sentences (contains spaces or lowercase)
                    if " " in raw_relation or not raw_relation.isupper():
                        logger.warning(
                            f"❌ Rejected relation '{raw_relation}' - must be UPPERCASE_WITH_UNDERSCORES"
                        )
                        continue

                    # Validation 2: Reject overly long strings (likely sentences)
                    if len(raw_relation) > 50:
                        logger.warning(
                            f"❌ Rejected relation '{raw_relation[:30]}...' - too long (max 50 chars)"
                        )
                        continue

                    # Try direct match first
                    try:
                        relation_type = RelationType(raw_relation)
                        logger.debug(f"✓ Accepted relation: {raw_relation}")
                    except ValueError:
                        # Try alias mapping for common variations
                        if raw_relation in RELATION_TYPE_ALIASES:
                            relation_type = RelationType(RELATION_TYPE_ALIASES[raw_relation])
                            logger.info(
                                f"✓ Mapped relation {raw_relation} → {relation_type.value}"
                            )
                        else:
                            logger.warning(
                                f"❌ Rejected unknown relation '{raw_relation}' - not in allowed types"
                            )
                            continue

                    relation = Relation(
                        source=rel_data["source"],
                        relation=relation_type,
                        target=rel_data["target"],
                        confidence=rel_data.get("confidence", 0.8),
                        evidence=rel_data.get("evidence", ""),
                    )
                    relations.append(relation)
                except (KeyError, ValueError) as e:
                    logger.warning(f"❌ Failed to parse relation: {e}")
                    continue

            # Filter low-confidence results
            entities = [e for e in entities if e.confidence >= settings.min_confidence]
            relations = [
                r for r in relations if r.confidence >= settings.min_confidence
            ]

            return ExtractionResult(entities=entities, relations=relations)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            return ExtractionResult(entities=ner_entities or [], relations=[])

    def _is_valid_entity_name(self, name: str) -> bool:
        """
        Validate entity name quality.

        Rejects:
        - Very short (< 2 chars) or very long (> 100 chars)
        - Full sentences with many spaces
        - Job titles alone
        - Citations (Author YYYY)
        - Generic numbered terms
        """
        import re

        name = name.strip()
        name_lower = name.lower()

        # Length checks
        if len(name) < 2 or len(name) > 100:
            return False

        # Job titles alone (should NOT be entities)
        job_titles = {
            "ceo", "pdg", "dg", "director", "directeur", "président", "president",
            "manager", "chairman", "vice-president", "vp", "cfo", "cto", "board member"
        }
        if name_lower in job_titles:
            return False

        # Full sentences (many spaces + common words)
        if name.count(' ') >= 5:
            return False

        # Citations: "Author YYYY" or "Author YYYYa"
        if re.match(r'^[\w\s]+ \d{4}[a-z]?$', name):
            return False

        # Generic numbered: "company 2", "investor11"
        if re.match(r'^(company|investor|shareholder|entity)\s*\d+$', name_lower):
            return False

        # Publication references: contains date patterns
        if re.search(r'\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b', name_lower):
            return False

        return True

    def _merge_entities(
        self, llm_entities: List[Entity], ner_entities: List[Entity]
    ) -> List[Entity]:
        """Merge entities from LLM and NER, avoiding duplicates."""
        merged = {e.name.lower(): e for e in ner_entities}

        for entity in llm_entities:
            name_lower = entity.name.lower()
            if name_lower not in merged:
                merged[name_lower] = entity
            else:
                # Update confidence if LLM found it too
                existing = merged[name_lower]
                existing.confidence = max(existing.confidence, entity.confidence)
                # Merge aliases
                existing.aliases.extend(
                    [a for a in entity.aliases if a not in existing.aliases]
                )

        return list(merged.values())


class HybridExtractor:
    """Hybrid extraction pipeline combining NER and LLM."""

    def __init__(self, ner_extractor, relation_extractor):
        """
        Initialize hybrid extractor.

        Args:
            ner_extractor: NERExtractor instance
            relation_extractor: RelationExtractor instance
        """
        self.ner = ner_extractor
        self.llm = relation_extractor

    def extract(
        self,
        text: str,
        language: str = "fr",
        context_before: str = "",
        context_after: str = ""
    ) -> ExtractionResult:
        """
        Extract entities and relations using hybrid approach.

        Args:
            text: Input text
            language: Language code
            context_before: Optional context from previous chunk
            context_after: Optional context from next chunk

        Returns:
            ExtractionResult with entities and relations
        """
        # Step 1: Extract entities with NER (fast, high recall)
        ner_entities = self.ner.extract_entities(text, language)

        logger.info(f"NER found {len(ner_entities)} entities")

        # Step 2: Extract relations with LLM (slow, high precision)
        result = self.llm.extract_relations(
            text,
            ner_entities,
            context_before=context_before,
            context_after=context_after
        )

        logger.info(
            f"Hybrid extraction: {len(result.entities)} entities, {len(result.relations)} relations"
        )

        return result
