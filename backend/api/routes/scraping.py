"""
Web scraping endpoints for collecting documents.
"""

from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from backend.ingestion.scrapers import ScraperManager

router = APIRouter()


class ScrapeRequest(BaseModel):
    """Scraping request."""

    sources: List[str] = ["tap", "african_manager", "ilboursa"]
    limit_per_source: int = 10


class ScrapeResult(BaseModel):
    """Scraping result."""

    total_articles: int
    articles_by_source: Dict[str, int]
    sources: List[str]


@router.post("/scrape", response_model=ScrapeResult)
async def scrape_sources(request: ScrapeRequest):
    """
    Scrape articles from Tunisian news sources.

    Saves articles as text files in the data directory.
    """
    try:
        scraper_manager = ScraperManager()

        # Validate sources
        valid_sources = ["tap", "african_manager", "ilboursa"]
        for source in request.sources:
            if source not in valid_sources:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid source: {source}. Valid sources: {valid_sources}",
                )

        # Scrape from selected sources
        results = {}
        for source in request.sources:
            logger.info(f"Scraping {source}...")
            articles = scraper_manager.scrape_source(source, request.limit_per_source)
            results[source] = len(articles)

        total_articles = sum(results.values())

        return ScrapeResult(
            total_articles=total_articles,
            articles_by_source=results,
            sources=request.sources,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def list_sources():
    """List available scraping sources."""
    return {
        "sources": [
            {
                "id": "tap",
                "name": "TAP (Tunis Afrique Presse)",
                "description": "Tunisia's national news agency",
            },
            {
                "id": "african_manager",
                "name": "African Manager",
                "description": "Tunisian business news",
            },
            {
                "id": "ilboursa",
                "name": "IlBoursa",
                "description": "Tunisian stock market and business news",
            },
        ]
    }
