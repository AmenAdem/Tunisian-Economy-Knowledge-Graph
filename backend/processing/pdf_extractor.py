"""
PDF text extraction with OCR support.
Uses PyMuPDF for digital PDFs and Tesseract for scanned documents.
"""

from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
import pytesseract
from loguru import logger
from PIL import Image


class PDFExtractor:
    """Extract text from PDF documents with OCR fallback."""

    def __init__(self, ocr_enabled: bool = True, language: str = "fra+ara+eng"):
        """
        Initialize PDF extractor.

        Args:
            ocr_enabled: Whether to use OCR for scanned PDFs
            language: Tesseract language codes (fra=French, ara=Arabic, eng=English)
        """
        self.ocr_enabled = ocr_enabled
        self.language = language

    def extract(self, pdf_path: Path) -> Dict[str, any]:
        """
        Extract text from PDF with page-level structure.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with extracted text, pages, and metadata
        """
        logger.info(f"Extracting text from {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            pages = []
            total_chars = 0

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")

                # If text extraction yields little content, try OCR
                if len(text.strip()) < 50 and self.ocr_enabled:
                    logger.debug(f"Page {page_num + 1} has minimal text, using OCR")
                    text = self._ocr_page(page)

                pages.append(
                    {
                        "page_number": page_num + 1,
                        "text": text,
                        "char_count": len(text),
                    }
                )
                total_chars += len(text)

            doc.close()

            result = {
                "file_path": str(pdf_path),
                "page_count": len(pages),
                "pages": pages,
                "total_chars": total_chars,
                "metadata": self._extract_metadata(pdf_path),
            }

            logger.info(
                f"Extracted {total_chars} characters from {len(pages)} pages"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to extract from {pdf_path}: {e}")
            raise

    def _ocr_page(self, page: fitz.Page) -> str:
        """
        Perform OCR on a page.

        Args:
            page: PyMuPDF page object

        Returns:
            Extracted text
        """
        try:
            # Render page to image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Perform OCR
            text = pytesseract.image_to_string(img, lang=self.language)
            return text

        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return ""

    def _extract_metadata(self, pdf_path: Path) -> Dict[str, str]:
        """Extract PDF metadata."""
        try:
            doc = fitz.open(pdf_path)
            metadata = doc.metadata or {}
            doc.close()
            return {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
            }
        except Exception as e:
            logger.warning(f"Failed to extract metadata: {e}")
            return {}


class StructureAwareChunker:
    """
    Structure-aware document chunking.
    Preserves paragraph, section, and heading boundaries.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        """
        Initialize chunker.

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            min_chunk_size: Minimum chunk size to keep
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_document(self, pages: List[Dict]) -> List[Dict[str, any]]:
        """
        Chunk document while preserving structure.

        Args:
            pages: List of page dictionaries from PDFExtractor

        Returns:
            List of chunks with metadata
        """
        chunks = []

        for page in pages:
            page_chunks = self._chunk_page(page["text"], page["page_number"])
            chunks.extend(page_chunks)

        logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages")
        return chunks

    def _chunk_page(self, text: str, page_number: int) -> List[Dict[str, any]]:
        """Chunk a single page preserving structure."""
        # Split into paragraphs (double newline or significant whitespace)
        paragraphs = self._split_paragraphs(text)

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            # If single paragraph exceeds chunk size, split it
            if para_size > self.chunk_size:
                # Save current chunk if any
                if current_chunk:
                    chunks.append(self._create_chunk(current_chunk, page_number))
                    current_chunk = []
                    current_size = 0

                # Split large paragraph
                chunks.extend(self._split_large_paragraph(para, page_number))
                continue

            # If adding paragraph exceeds chunk size, start new chunk
            if current_size + para_size > self.chunk_size and current_chunk:
                chunks.append(self._create_chunk(current_chunk, page_number))
                # Keep last paragraph for overlap
                if self.chunk_overlap > 0 and current_chunk:
                    current_chunk = [current_chunk[-1]]
                    current_size = len(current_chunk[-1])
                else:
                    current_chunk = []
                    current_size = 0

            current_chunk.append(para)
            current_size += para_size

        # Add remaining chunk
        if current_chunk and current_size >= self.min_chunk_size:
            chunks.append(self._create_chunk(current_chunk, page_number))

        return chunks

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs preserving structure."""
        # Split on double newlines or significant breaks
        paragraphs = []
        current_para = []

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                if current_para:
                    paragraphs.append(" ".join(current_para))
                    current_para = []
            else:
                current_para.append(line)

        if current_para:
            paragraphs.append(" ".join(current_para))

        return [p for p in paragraphs if p]

    def _split_large_paragraph(
        self, paragraph: str, page_number: int
    ) -> List[Dict[str, any]]:
        """Split a large paragraph into sentence-based chunks."""
        # Simple sentence split (can be improved with spaCy)
        sentences = [s.strip() + "." for s in paragraph.split(".") if s.strip()]

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sent_size = len(sentence)

            if current_size + sent_size > self.chunk_size and current_chunk:
                chunks.append(
                    self._create_chunk([" ".join(current_chunk)], page_number)
                )
                current_chunk = []
                current_size = 0

            current_chunk.append(sentence)
            current_size += sent_size

        if current_chunk:
            chunks.append(self._create_chunk([" ".join(current_chunk)], page_number))

        return chunks

    def _create_chunk(self, paragraphs: List[str], page_number: int) -> Dict[str, any]:
        """Create chunk dictionary."""
        text = "\n\n".join(paragraphs)
        return {
            "text": text,
            "page_number": page_number,
            "char_count": len(text),
            "paragraph_count": len(paragraphs),
        }
