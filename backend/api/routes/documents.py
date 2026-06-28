"""
Document upload and management endpoints.
"""

from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel

from backend.config import settings
from backend.extraction.ner_extractor import NERExtractor
from backend.extraction.relation_extractor import HybridExtractor, RelationExtractor
from backend.graph.neo4j_client import Neo4jClient
from backend.processing.pdf_extractor import PDFExtractor, StructureAwareChunker
from backend.resolution.entity_resolver import EntityResolver

router = APIRouter()


class DocumentInfo(BaseModel):
    """Document information."""

    filename: str
    size: int
    path: str


class ProcessingResult(BaseModel):
    """Document processing result."""

    document: DocumentInfo
    pages: int
    chunks: int
    entities_extracted: int
    relations_extracted: int


@router.post("/upload", response_model=ProcessingResult)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and process a PDF document.

    Extracts text, chunks it, extracts entities and relationships,
    and adds them to the knowledge graph.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Save uploaded file
        file_path = settings.upload_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"Uploaded file: {file_path}")

        # Extract text from PDF
        pdf_extractor = PDFExtractor()
        extraction_result = pdf_extractor.extract(file_path)

        # Chunk document
        chunker = StructureAwareChunker(
            chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        chunks = chunker.chunk_document(extraction_result["pages"])

        logger.info(f"Created {len(chunks)} chunks from document")

        # Initialize extractors
        ner_extractor = NERExtractor()
        relation_extractor = RelationExtractor()
        hybrid_extractor = HybridExtractor(ner_extractor, relation_extractor)
        resolver = EntityResolver()

        # Initialize graph client and entity linker
        neo4j_client = Neo4jClient()
        neo4j_client.initialize_schema()

        from backend.resolution.entity_linker import EntityLinker
        entity_linker = EntityLinker(neo4j_client)

        total_entities = 0
        total_relations = 0

        # Process each chunk with context window
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")

            # Build context: include snippets from previous and next chunks
            context_before = ""
            context_after = ""

            if i > 0:
                # Add last 200 chars from previous chunk as context
                prev_text = chunks[i-1]["text"]
                context_before = prev_text[-200:] if len(prev_text) > 200 else prev_text

            if i < len(chunks) - 1:
                # Add first 200 chars from next chunk as context
                next_text = chunks[i+1]["text"]
                context_after = next_text[:200] if len(next_text) > 200 else next_text

            # Extract entities and relations with context
            result = hybrid_extractor.extract(
                chunk["text"],
                context_before=context_before,
                context_after=context_after
            )

            # Resolve duplicate entities within this chunk
            result.entities = resolver.resolve_entities(result.entities)

            # Link entities to existing graph nodes (CRITICAL!)
            result.entities = entity_linker.link_entities(result.entities)

            # Add to graph
            stats = neo4j_client.add_extraction_result(
                result, str(file_path), chunk_id=f"chunk_{i}"
            )

            total_entities += stats["entities_added"]
            total_relations += stats["relations_added"]

        entity_linker.close()
        neo4j_client.close()

        return ProcessingResult(
            document=DocumentInfo(
                filename=file.filename, size=len(content), path=str(file_path)
            ),
            pages=extraction_result["page_count"],
            chunks=len(chunks),
            entities_extracted=total_entities,
            relations_extracted=total_relations,
        )

    except Exception as e:
        logger.error(f"Failed to process document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=List[DocumentInfo])
async def list_documents():
    """List all uploaded documents."""
    try:
        documents = []
        for file_path in settings.upload_dir.glob("*.pdf"):
            documents.append(
                DocumentInfo(
                    filename=file_path.name,
                    size=file_path.stat().st_size,
                    path=str(file_path),
                )
            )
        return documents
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))
