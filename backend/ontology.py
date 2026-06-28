"""
Ontology definition for the Tunisian economy knowledge graph.
Defines entity types, relationship types, and their properties.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Entity types in the knowledge graph.

    These are the ONLY valid entity types. LLM must not create others.
    Based on Tunisian economy knowledge graph requirements.
    """

    # Core business entities
    PERSON = "Person"
    COMPANY = "Company"
    GROUP = "Group"
    BANK = "Bank"

    # Organizational entities
    ORGANIZATION = "Organization"
    GOVERNMENT_ENTITY = "GovernmentEntity"

    # Contextual entities
    SECTOR = "Sector"
    LOCATION = "Location"

    # Financial/Stock market entities
    STOCK = "Stock"  # Tradable stock/shares on exchange
    STOCK_EXCHANGE = "StockExchange"  # Bourse/stock market

    # Document entities (for traceability)
    DOCUMENT = "Document"
    ARTICLE = "Article"
    CONTRACT = "Contract"
    EVENT = "Event"


class RelationType(str, Enum):
    """Relationship types in the knowledge graph.

    These are the ONLY valid relationship types. LLM must use these exactly.
    Based on the project ontology specification.
    """

    # Ownership relationships
    OWNS = "OWNS"  # Person/entity owns company (generic ownership)
    OWNS_SHARES = "OWNS_SHARES"  # Person/entity owns X% shares (with percentage property)

    # Leadership relationships
    DIRECTOR_OF = "DIRECTOR_OF"  # Board director / CEO / PDG
    MEMBER_OF_BOARD = "MEMBER_OF_BOARD"  # Board member

    # Corporate structure
    SUBSIDIARY_OF = "SUBSIDIARY_OF"  # Company is subsidiary of another
    PART_OF_GROUP = "PART_OF_GROUP"  # Company belongs to business group
    PARTNER_OF = "PARTNER_OF"  # Business partnership

    # Financial relationships
    ACQUIRED = "ACQUIRED"  # Acquisition
    INVESTED_IN = "INVESTED_IN"  # Investment
    FOUNDED = "FOUNDED"  # Founder relationship

    # Stock market relationships
    LISTED_ON = "LISTED_ON"  # Company listed on stock exchange
    TRADES_AS = "TRADES_AS"  # Company trades with ticker symbol

    # Operational relationships
    OPERATES_IN = "OPERATES_IN"  # Operates in sector/location

    # Document relationships (traceability)
    MENTIONED_IN = "MENTIONED_IN"  # Entity mentioned in document
    MENTIONED_WITH = "MENTIONED_WITH"  # Co-mentioned entities

    # Fallback for unclear relationships
    RELATED_TO = "RELATED_TO"  # Generic relationship


class Entity(BaseModel):
    """An entity extracted from documents."""

    name: str = Field(..., description="Entity name")
    type: EntityType = Field(..., description="Entity type")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    properties: Dict[str, str] = Field(
        default_factory=dict, description="Additional properties"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Relation(BaseModel):
    """A relationship between two entities."""

    source: str = Field(..., description="Source entity name")
    relation: RelationType = Field(..., description="Relationship type")
    target: str = Field(..., description="Target entity name")
    properties: Dict[str, str] = Field(
        default_factory=dict, description="Relationship properties"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: Optional[str] = Field(None, description="Evidence text")


class ExtractionResult(BaseModel):
    """Result of entity and relation extraction."""

    entities: List[Entity] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)
    source_document: Optional[str] = None


# Entity type descriptions for LLM prompts
ENTITY_DESCRIPTIONS = {
    EntityType.PERSON: "Individual person (executive, director, business owner, politician)",
    EntityType.COMPANY: "Business entity, corporation, or enterprise (SA, SARL, etc.)",
    EntityType.GROUP: "Business group or holding company (e.g., Poulina Group Holding)",
    EntityType.BANK: "Financial institution or bank",
    EntityType.ORGANIZATION: "Non-profit organization, association, or union",
    EntityType.GOVERNMENT_ENTITY: "Government body, ministry, or public institution",
    EntityType.SECTOR: "Industry sector (telecom, banking, manufacturing, tourism, etc.)",
    EntityType.LOCATION: "Geographic location (Tunis, Sfax, Tunisia, France, etc.)",
    EntityType.STOCK: "Tradable stock/shares on stock exchange",
    EntityType.STOCK_EXCHANGE: "Stock exchange / Bourse (BVMT, etc.)",
    EntityType.DOCUMENT: "Document (report, contract, article)",
    EntityType.ARTICLE: "News article or publication",
    EntityType.CONTRACT: "Business contract or agreement",
    EntityType.EVENT: "Business event (merger, acquisition, appointment)",
}

# Relationship type descriptions for LLM prompts
RELATION_DESCRIPTIONS = {
    RelationType.OWNS: "Person/entity owns or controls a company (generic ownership, actionnaire)",
    RelationType.OWNS_SHARES: "Person/entity owns X% of shares (use properties: percentage, share_count, value_tnd)",
    RelationType.DIRECTOR_OF: "Person is director/PDG/CEO/DG of organization (Directeur, PDG, DG)",
    RelationType.MEMBER_OF_BOARD: "Person is board member (conseil d'administration)",
    RelationType.SUBSIDIARY_OF: "Company is subsidiary/filiale of another company",
    RelationType.PART_OF_GROUP: "Company belongs to business group (e.g., part of Poulina Group)",
    RelationType.PARTNER_OF: "Business partnership or collaboration between entities",
    RelationType.ACQUIRED: "Entity acquired another entity (acquisition, rachat)",
    RelationType.INVESTED_IN: "Entity invested capital in another entity",
    RelationType.FOUNDED: "Person/entity founded or created a company (fondateur)",
    RelationType.LISTED_ON: "Company is listed/traded on stock exchange",
    RelationType.TRADES_AS: "Company trades with ticker symbol",
    RelationType.OPERATES_IN: "Company operates in a sector or geographic location",
    RelationType.MENTIONED_IN: "Entity mentioned in document (for traceability)",
    RelationType.MENTIONED_WITH: "Entities co-mentioned in same document",
    RelationType.RELATED_TO: "Generic relationship when specific type unclear",
}

# Mapping of common LLM mistakes to valid relation types
# Only allow variations that are semantically equivalent
RELATION_TYPE_ALIASES = {
    # Ownership variations
    "OWNED_BY": "OWNS",  # Reverse direction
    "SHAREHOLDER_OF": "OWNS_SHARES",
    "HOLDS_SHARES_IN": "OWNS_SHARES",
    "HAS_STAKE_IN": "OWNS_SHARES",

    # Leadership variations
    "IS_DIRECTOR_OF": "DIRECTOR_OF",
    "HAS_DIRECTOR": "DIRECTOR_OF",
    "IS_MEMBER_OF_BOARD": "MEMBER_OF_BOARD",
    "HAS_BOARD_MEMBER": "MEMBER_OF_BOARD",
    "HAS_MEMBER_OF_BOARD": "MEMBER_OF_BOARD",

    # Subsidiary variations
    "IS_SUBSIDIARY_OF": "SUBSIDIARY_OF",
    "HAS_SUBSIDIARY": "SUBSIDIARY_OF",

    # Partnership variations
    "IS_PARTNER_OF": "PARTNER_OF",
    "PARTNERS_WITH": "PARTNER_OF",

    # Acquisition variations
    "ACQUIRING": "ACQUIRED",
    "ACQUIRED_BY": "ACQUIRED",

    # Founding variations
    "FOUNDED_BY": "FOUNDED",
    "IS_FOUNDED_BY": "FOUNDED",
    "FOUNDERS_OF": "FOUNDED",
    "IS_FOUNDER_OF": "FOUNDED",

    # Investment variations
    "INVESTS_IN": "INVESTED_IN",
    "IS_INVESTOR_IN": "INVESTED_IN",

    # Operation variations
    "OPERATES_IN_SECTOR": "OPERATES_IN",
    "WORKS_IN": "OPERATES_IN",

    # Mention variations
    "MENTIONED_BY": "MENTIONED_IN",
    "MENTIONS": "MENTIONED_IN",
    "IS_MENTIONED_IN": "MENTIONED_IN",
    "APPEARS_IN": "MENTIONED_IN",

    # Group/structure variations
    "MEMBER_OF_GROUP": "PART_OF_GROUP",
    "BELONGS_TO_GROUP": "PART_OF_GROUP",
    "PART_OF": "PART_OF_GROUP",

    # Stock market variations
    "LISTED_IN": "LISTED_ON",
    "TRADED_ON": "LISTED_ON",
    "TICKER_SYMBOL": "TRADES_AS",

    # Generic fallbacks (map unclear relationships to RELATED_TO)
    "ASSOCIATED_WITH": "RELATED_TO",
    "CONNECTED_TO": "RELATED_TO",
    "LINKED_TO": "RELATED_TO",
}

