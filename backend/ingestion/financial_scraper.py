"""
Financial data scraper for Tunisian stock exchange and companies.
Extracts ownership structures, stock data, and corporate information.
"""

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from loguru import logger

from backend.config import settings


@dataclass
class ShareholderData:
    """Shareholder ownership information."""

    name: str
    share_count: Optional[int] = None
    percentage: Optional[float] = None
    value_tnd: Optional[float] = None
    shareholder_type: Optional[str] = None  # Individual, Institutional, Family, Public


@dataclass
class CompanyFinancialData:
    """Company financial and stock information."""

    name: str
    ticker: Optional[str] = None
    sector: Optional[str] = None
    legal_form: Optional[str] = None  # SA, SARL, etc.

    # Stock data
    stock_price: Optional[float] = None
    market_cap_tnd: Optional[float] = None
    trading_volume: Optional[int] = None

    # Corporate info
    headquarters: Optional[str] = None
    founded_date: Optional[str] = None
    ipo_date: Optional[str] = None
    ipo_price: Optional[float] = None

    # Ownership
    shareholders: List[ShareholderData] = None

    # Leadership
    ceo: Optional[str] = None
    board_members: List[str] = None

    # Group affiliation
    parent_group: Optional[str] = None
    subsidiaries: List[str] = None

    # Financial performance
    revenue_tnd: Optional[float] = None
    profit_tnd: Optional[float] = None
    assets_tnd: Optional[float] = None

    # Source
    source_url: Optional[str] = None
    scraped_date: Optional[str] = None

    def __post_init__(self):
        if self.shareholders is None:
            self.shareholders = []
        if self.board_members is None:
            self.board_members = []
        if self.subsidiaries is None:
            self.subsidiaries = []
        if self.scraped_date is None:
            self.scraped_date = datetime.now().isoformat()


class BaseFinancialScraper(ABC):
    """Base class for financial data scrapers."""

    def __init__(self, rate_limit: float = 2.0):
        """
        Initialize scraper.

        Args:
            rate_limit: Minimum seconds between requests
        """
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def _rate_limit_wait(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def _fetch_page(self, url: str, timeout: int = 30) -> Optional[BeautifulSoup]:
        """
        Fetch and parse HTML page.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds

        Returns:
            BeautifulSoup object or None if failed
        """
        self._rate_limit_wait()

        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()

            return BeautifulSoup(response.content, 'html.parser')

        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    @staticmethod
    def _parse_percentage(text: str) -> Optional[float]:
        """
        Extract percentage from text.

        Examples:
            "25.5%" -> 25.5
            "12,3 %" -> 12.3
            "3.14" -> 3.14
        """
        if not text:
            return None

        # Remove spaces and normalize comma/dot
        text = text.replace(' ', '').replace(',', '.')

        # Extract number
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _parse_amount_tnd(text: str) -> Optional[float]:
        """
        Extract TND amount from text.

        Examples:
            "1,250,000 TND" -> 1250000.0
            "3.5 MTND" -> 3500000.0 (millions)
            "2,5 MD" -> 2500000.0 (millions de dinars)
        """
        if not text:
            return None

        # Remove currency symbols
        text = text.upper().replace('TND', '').replace('DT', '').replace('DINARS', '')
        text = text.strip()

        # Check for millions/thousands multiplier
        multiplier = 1
        if 'MTND' in text or 'MD' in text or 'MILLION' in text:
            multiplier = 1_000_000
            text = re.sub(r'(MTND|MD|MILLION)', '', text)
        elif 'KTND' in text or 'MILLE' in text:
            multiplier = 1_000
            text = re.sub(r'(KTND|MILLE)', '', text)

        # Normalize number format (remove spaces, convert comma to dot)
        text = text.replace(' ', '').replace(',', '.')

        # Extract number
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            return float(match.group(1)) * multiplier
        return None

    @staticmethod
    def _parse_share_count(text: str) -> Optional[int]:
        """
        Extract share count from text.

        Examples:
            "1,250,000 actions" -> 1250000
            "3 500 000 parts" -> 3500000
        """
        if not text:
            return None

        # Remove text labels
        text = text.lower().replace('actions', '').replace('parts', '').replace('titres', '')

        # Remove spaces and thousand separators
        text = text.replace(' ', '').replace(',', '').replace('.', '')

        # Extract number
        match = re.search(r'(\d+)', text)
        if match:
            return int(match.group(1))
        return None

    @abstractmethod
    def scrape_company(self, company_id: str) -> Optional[CompanyFinancialData]:
        """
        Scrape company data.

        Args:
            company_id: Company identifier (ticker, ID, etc.)

        Returns:
            CompanyFinancialData or None if failed
        """
        pass

    @abstractmethod
    def list_companies(self) -> List[Dict[str, str]]:
        """
        Get list of all companies.

        Returns:
            List of company dicts with at least 'name' and 'id' keys
        """
        pass


class BVMTScraper(BaseFinancialScraper):
    """Scraper for Bourse de Tunis (BVMT) / Tunis Stock Exchange."""

    BASE_URL = "https://tunis-stockexchange.com"

    def list_companies(self) -> List[Dict[str, str]]:
        """Get list of all listed companies."""
        logger.info("Fetching BVMT company list...")

        # Try to find company listing page
        soup = self._fetch_page(self.BASE_URL)
        if not soup:
            return []

        companies = []

        # TODO: Update selectors based on actual site structure
        # This is a placeholder - needs inspection of actual site
        company_links = soup.find_all('a', href=re.compile(r'/company/|/societe/'))

        for link in company_links:
            company_name = link.get_text(strip=True)
            company_url = urljoin(self.BASE_URL, link.get('href'))

            companies.append({
                'name': company_name,
                'id': company_url.split('/')[-1],
                'url': company_url
            })

        logger.info(f"Found {len(companies)} companies on BVMT")
        return companies

    def scrape_company(self, company_id: str) -> Optional[CompanyFinancialData]:
        """Scrape company data from BVMT."""
        url = f"{self.BASE_URL}/company/{company_id}"
        soup = self._fetch_page(url)

        if not soup:
            return None

        # TODO: Implement actual parsing based on BVMT site structure
        # This is a template that needs to be updated after site inspection

        company_data = CompanyFinancialData(
            name=company_id,  # Placeholder
            source_url=url
        )

        logger.warning("BVMT scraper needs site-specific selectors")
        return company_data


class IlBoursaScraper(BaseFinancialScraper):
    """Scraper for IlBoursa.com financial data."""

    BASE_URL = "https://www.ilboursa.com"

    def list_companies(self) -> List[Dict[str, str]]:
        """Get list of companies from IlBoursa."""
        logger.info("Fetching IlBoursa company list...")

        # Companies list page
        url = f"{self.BASE_URL}/marches/entreprises"
        soup = self._fetch_page(url)

        if not soup:
            return []

        companies = []

        # TODO: Update selectors after site inspection
        # Placeholder structure
        company_elements = soup.find_all('a', href=re.compile(r'/marches/entreprise/'))

        for element in company_elements:
            company_name = element.get_text(strip=True)
            company_url = urljoin(self.BASE_URL, element.get('href'))
            company_id = company_url.split('/')[-1]

            companies.append({
                'name': company_name,
                'id': company_id,
                'url': company_url
            })

        logger.info(f"Found {len(companies)} companies on IlBoursa")
        return companies

    def scrape_company(self, company_id: str) -> Optional[CompanyFinancialData]:
        """Scrape company data from IlBoursa."""
        url = f"{self.BASE_URL}/marches/entreprise/{company_id}"
        soup = self._fetch_page(url)

        if not soup:
            return None

        # TODO: Implement actual parsing
        # Placeholder implementation

        company_data = CompanyFinancialData(
            name=company_id,
            source_url=url
        )

        logger.warning("IlBoursa scraper needs site-specific selectors")
        return company_data


class FinancialDataIntegrator:
    """Integrate financial data into knowledge graph."""

    def __init__(self):
        from backend.graph.neo4j_client import Neo4jClient
        from backend.ontology import Entity, EntityType, Relation, RelationType

        self.neo4j_client = Neo4jClient()
        self.Entity = Entity
        self.EntityType = EntityType
        self.Relation = Relation
        self.RelationType = RelationType

    def integrate_company_data(self, company_data: CompanyFinancialData) -> Dict[str, int]:
        """
        Integrate company financial data into knowledge graph.

        Args:
            company_data: Company financial data

        Returns:
            Dictionary with counts of entities and relations added
        """
        entities = []
        relations = []

        # Create company entity
        company_entity = self.Entity(
            name=company_data.name,
            type=self.EntityType.COMPANY,
            properties={
                'ticker': company_data.ticker or '',
                'sector': company_data.sector or '',
                'legal_form': company_data.legal_form or '',
                'headquarters': company_data.headquarters or '',
                'ipo_date': company_data.ipo_date or '',
                'market_cap_tnd': str(company_data.market_cap_tnd or 0),
                'source': company_data.source_url or '',
            },
            confidence=0.95
        )
        entities.append(company_entity)

        # Add shareholders
        for shareholder in company_data.shareholders:
            shareholder_entity = self.Entity(
                name=shareholder.name,
                type=self.EntityType.PERSON,  # TODO: Better type detection
                confidence=0.9
            )
            entities.append(shareholder_entity)

            # Create ownership relation
            relation = self.Relation(
                source=shareholder.name,
                relation=self.RelationType.OWNS_SHARES,
                target=company_data.name,
                properties={
                    'percentage': str(shareholder.percentage or 0),
                    'share_count': str(shareholder.share_count or 0),
                    'value_tnd': str(shareholder.value_tnd or 0),
                    'shareholder_type': shareholder.shareholder_type or '',
                },
                confidence=0.9,
                evidence=f"Shareholder data from {company_data.source_url}"
            )
            relations.append(relation)

        # Add CEO
        if company_data.ceo:
            ceo_entity = self.Entity(
                name=company_data.ceo,
                type=self.EntityType.PERSON,
                confidence=0.9
            )
            entities.append(ceo_entity)

            relation = self.Relation(
                source=company_data.ceo,
                relation=self.RelationType.DIRECTOR_OF,
                target=company_data.name,
                properties={'title': 'CEO'},
                confidence=0.9
            )
            relations.append(relation)

        # Add to Neo4j
        from backend.ontology import ExtractionResult
        result = ExtractionResult(
            entities=entities,
            relations=relations,
            source_document=company_data.source_url or 'financial_scraper'
        )

        counts = self.neo4j_client.add_extraction_result(
            result,
            source_document=company_data.source_url or 'financial_scraper'
        )

        return counts

    def close(self):
        """Close Neo4j connection."""
        self.neo4j_client.close()
