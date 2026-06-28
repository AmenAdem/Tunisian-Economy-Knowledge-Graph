"""
Web scrapers for Tunisian news sources.
Collects articles from TAP, African Manager, IlBoursa, etc.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger

from backend.config import settings


class BaseScraper:
    """Base class for web scrapers."""

    def __init__(self, base_url: str, name: str):
        """
        Initialize scraper.

        Args:
            base_url: Base URL of the website
            name: Scraper name
        """
        self.base_url = base_url
        self.name = name
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            return soup
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def save_article(self, article: Dict) -> Path:
        """Save article to disk."""
        # Create filename from title and date
        date_str = article.get("date", datetime.now().strftime("%Y%m%d"))
        title_slug = "".join(
            c if c.isalnum() else "_" for c in article["title"][:50]
        ).lower()
        filename = f"{date_str}_{self.name}_{title_slug}.txt"

        filepath = settings.upload_dir / filename

        # Write article content
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Title: {article['title']}\n")
            f.write(f"URL: {article['url']}\n")
            f.write(f"Date: {article.get('date', 'N/A')}\n")
            f.write(f"Source: {self.name}\n")
            f.write(f"\n{'='*80}\n\n")
            f.write(article["content"])

        logger.info(f"Saved article: {filepath}")
        return filepath


class TAPScraper(BaseScraper):
    """
    Scraper for TAP (Tunis Afrique Presse) - Tunisia's national news agency.
    """

    def __init__(self):
        super().__init__("https://www.tap.info.tn", "tap")

    def scrape_business_section(self, limit: int = 10) -> List[Dict]:
        """Scrape business/economy articles."""
        articles = []

        # TAP business section (adjust URL based on actual site structure)
        section_url = f"{self.base_url}/fr/economie"

        soup = self.fetch_page(section_url)
        if not soup:
            return articles

        # Find article links (adjust selectors based on actual HTML structure)
        article_links = soup.select("article a.article-link")[:limit]

        for link in article_links:
            url = urljoin(self.base_url, link.get("href", ""))
            article = self.scrape_article(url)
            if article:
                articles.append(article)
                self.save_article(article)

        logger.info(f"Scraped {len(articles)} articles from TAP")
        return articles

    def scrape_article(self, url: str) -> Optional[Dict]:
        """Scrape a single article."""
        soup = self.fetch_page(url)
        if not soup:
            return None

        try:
            # Extract article details (adjust selectors for actual site)
            title = soup.select_one("h1.article-title")
            content_div = soup.select_one("div.article-content")
            date_elem = soup.select_one("time.article-date")

            if not title or not content_div:
                return None

            return {
                "title": title.get_text(strip=True),
                "url": url,
                "content": content_div.get_text("\n", strip=True),
                "date": date_elem.get("datetime") if date_elem else None,
                "source": self.name,
            }
        except Exception as e:
            logger.warning(f"Failed to parse article {url}: {e}")
            return None


class AfricanManagerScraper(BaseScraper):
    """
    Scraper for African Manager - Tunisian business news.
    """

    def __init__(self):
        super().__init__("https://africanmanager.com", "african_manager")

    def scrape_business_section(self, limit: int = 10) -> List[Dict]:
        """Scrape business articles."""
        articles = []

        section_url = f"{self.base_url}/category/economie/"

        soup = self.fetch_page(section_url)
        if not soup:
            return articles

        # Find article links
        article_links = soup.select("article h2 a")[:limit]

        for link in article_links:
            url = link.get("href", "")
            if url:
                article = self.scrape_article(url)
                if article:
                    articles.append(article)
                    self.save_article(article)

        logger.info(f"Scraped {len(articles)} articles from African Manager")
        return articles

    def scrape_article(self, url: str) -> Optional[Dict]:
        """Scrape a single article."""
        soup = self.fetch_page(url)
        if not soup:
            return None

        try:
            title = soup.select_one("h1.entry-title")
            content_div = soup.select_one("div.entry-content")
            date_elem = soup.select_one("time.entry-date")

            if not title or not content_div:
                return None

            return {
                "title": title.get_text(strip=True),
                "url": url,
                "content": content_div.get_text("\n", strip=True),
                "date": date_elem.get("datetime") if date_elem else None,
                "source": self.name,
            }
        except Exception as e:
            logger.warning(f"Failed to parse article {url}: {e}")
            return None


class IlBoursaScraper(BaseScraper):
    """
    Scraper for IlBoursa - Tunisian stock market and business news.
    """

    def __init__(self):
        super().__init__("https://www.ilboursa.com", "ilboursa")

    def scrape_business_section(self, limit: int = 10) -> List[Dict]:
        """Scrape business articles."""
        articles = []

        section_url = f"{self.base_url}/marches"

        soup = self.fetch_page(section_url)
        if not soup:
            return articles

        # Find article links
        article_links = soup.select("div.article-item a")[:limit]

        for link in article_links:
            url = urljoin(self.base_url, link.get("href", ""))
            article = self.scrape_article(url)
            if article:
                articles.append(article)
                self.save_article(article)

        logger.info(f"Scraped {len(articles)} articles from IlBoursa")
        return articles

    def scrape_article(self, url: str) -> Optional[Dict]:
        """Scrape a single article."""
        soup = self.fetch_page(url)
        if not soup:
            return None

        try:
            title = soup.select_one("h1.article-title")
            content_div = soup.select_one("div.article-body")
            date_elem = soup.select_one("span.article-date")

            if not title or not content_div:
                return None

            return {
                "title": title.get_text(strip=True),
                "url": url,
                "content": content_div.get_text("\n", strip=True),
                "date": date_elem.get_text(strip=True) if date_elem else None,
                "source": self.name,
            }
        except Exception as e:
            logger.warning(f"Failed to parse article {url}: {e}")
            return None


class ScraperManager:
    """Manage multiple scrapers."""

    def __init__(self):
        """Initialize scraper manager."""
        self.scrapers = {
            "tap": TAPScraper(),
            "african_manager": AfricanManagerScraper(),
            "ilboursa": IlBoursaScraper(),
        }

    def scrape_all(self, limit_per_source: int = 10) -> Dict[str, List[Dict]]:
        """
        Scrape from all sources.

        Args:
            limit_per_source: Number of articles per source

        Returns:
            Dictionary of source -> articles
        """
        results = {}

        for name, scraper in self.scrapers.items():
            logger.info(f"Scraping {name}...")
            try:
                articles = scraper.scrape_business_section(limit_per_source)
                results[name] = articles
            except Exception as e:
                logger.error(f"Failed to scrape {name}: {e}")
                results[name] = []

        total_articles = sum(len(articles) for articles in results.values())
        logger.info(f"Scraped {total_articles} total articles")

        return results

    def scrape_source(self, source: str, limit: int = 10) -> List[Dict]:
        """Scrape from a specific source."""
        if source not in self.scrapers:
            logger.error(f"Unknown source: {source}")
            return []

        scraper = self.scrapers[source]
        return scraper.scrape_business_section(limit)
