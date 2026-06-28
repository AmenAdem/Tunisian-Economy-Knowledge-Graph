"""
FastAPI application for the knowledge graph MVP.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.config import settings
from backend.utils.logger import setup_logger

# Import routers
from backend.api.routes import documents, entities, graph, graph_explorer, query, scraping


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logger()
    settings.ensure_directories()
    logger.info("Starting Tunisian Economy Knowledge Graph API")

    yield

    # Shutdown
    logger.info("Shutting down API")


# Create FastAPI app
app = FastAPI(
    title="Tunisian Economy Knowledge Graph",
    description="Extract and explore relationships in the Tunisian economy",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(entities.router, prefix="/api/entities", tags=["entities"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(graph_explorer.router, prefix="/api/graph/explore", tags=["graph-explorer"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(scraping.router, prefix="/api/scraping", tags=["scraping"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Tunisian Economy Knowledge Graph API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
