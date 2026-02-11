"""
Insurance Document Intelligence Assistant
Ingestion Module - PDF Parser

Parses PDF files to extract:
- Text content with page/section references
- Tables with structural preservation
- Section headings
- Metadata
"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import pdfplumber

from ..security import get_folder_guard, get_audit_logger


@dataclass
class TableInfo:
    """Information about an extracted table."""
    page: int
    table_index: int
    headers: list
    row_count: int
    data: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "table_index": self.table_index,
            "headers": self.headers,
            "row_count": self.row_count,
            "data": self.data[:10]  # Limit data for summary
        }


@dataclass
class PageInfo:
    """Information about a PDF page."""
    page_number: int
    text: str
    word_count: int
    tables: list[TableInfo] = field(default_factory=list)
    sections: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "word_count": self.word_count,
            "table_count": len(self.tables),
            "sections": self.sections,
            "text_preview": self.text[:500] if self.text else ""
        }


@dataclass
class PDFInfo:
    """Information about a PDF document."""
    filename: str
    filepath: str
    page_count: int
    total_words: int = 0
    total_tables: int = 0
    pages: list[PageInfo] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "filepath": self.filepath,
            "page_count": self.page_count,
            "total_words": self.total_words,
            "total_tables": self.total_tables,
            "metadata": self.metadata,
            "pages": [p.to_dict() for p in self.pages]
        }
    
    def get_full_text(self) -> str:
        """Get all text from the PDF."""
        return "\n\n".join(
            f"[Page {p.page_number}]\n{p.text}"
            for p in self.pages
            if p.text
        )


class PDFParser:
    """
    Parses PDF files for insurance document analysis.
    
    Features:
    - Text extraction with page references
    - Table extraction with structure
    - Section heading detection
    - Metadata extraction
    """
    
    def __init__(self):
        self.guard = get_folder_guard()
        self.logger = get_audit_logger()
        
        # Common insurance document section patterns
        self.section_patterns = [
            "executive summary",
            "introduction",
            "background",
            "methodology",
            "assumptions",
            "results",
            "conclusions",
            "appendix",
            "exhibit",
            "schedule",
            "actuarial opinion",
            "certification",
            "reserves",
            "liabilities",
            "claims",
            "premiums",
            "reinsurance"
        ]
    
    def parse(self, filepath: str | Path) -> PDFInfo:
        """
        Parse a PDF file and extract all relevant information.
        
        Args:
            filepath: Path to the PDF file
            
        Returns:
            PDFInfo containing all extracted data
        """
        safe_path = self.guard.validate_path(filepath)
        
        self.logger.log_document_access(
            str(safe_path),
            "pdf_parse"
        )
        
        with pdfplumber.open(safe_path) as pdf:
            pdf_info = PDFInfo(
                filename=safe_path.name,
                filepath=str(safe_path),
                page_count=len(pdf.pages),
                metadata=pdf.metadata or {}
            )
            
            for i, page in enumerate(pdf.pages):
                page_info = self._parse_page(page, i + 1)
                pdf_info.pages.append(page_info)
                pdf_info.total_words += page_info.word_count
                pdf_info.total_tables += len(page_info.tables)
        
        self.logger.log_ingestion(
            safe_path.name,
            "pdf",
            True,
            {
                "pages": pdf_info.page_count,
                "words": pdf_info.total_words,
                "tables": pdf_info.total_tables
            }
        )
        
        return pdf_info
    
    def _parse_page(self, page, page_number: int) -> PageInfo:
        """Parse a single PDF page."""
        # Extract text
        text = page.extract_text() or ""
        
        page_info = PageInfo(
            page_number=page_number,
            text=text,
            word_count=len(text.split())
        )
        
        # Extract tables
        tables = page.extract_tables()
        for i, table_data in enumerate(tables or []):
            if table_data and len(table_data) > 0:
                table_info = TableInfo(
                    page=page_number,
                    table_index=i,
                    headers=table_data[0] if table_data else [],
                    row_count=len(table_data) - 1,  # Exclude header
                    data=table_data[1:] if len(table_data) > 1 else []
                )
                page_info.tables.append(table_info)
        
        # Detect sections
        page_info.sections = self._detect_sections(text)
        
        return page_info
    
    def _detect_sections(self, text: str) -> list:
        """Detect section headings in text."""
        sections = []
        text_lower = text.lower()
        
        for pattern in self.section_patterns:
            if pattern in text_lower:
                # Find the line containing the section
                for line in text.split("\n"):
                    if pattern in line.lower():
                        section = line.strip()
                        if section and len(section) < 100:
                            sections.append(section)
                        break
        
        return sections
    
    def extract_text(
        self,
        filepath: str | Path,
        page_numbers: list[int] = None
    ) -> str:
        """
        Extract text from specific pages.
        
        Args:
            filepath: Path to the PDF file
            page_numbers: Optional list of page numbers (1-indexed)
            
        Returns:
            Extracted text
        """
        pdf_info = self.parse(filepath)
        
        if page_numbers:
            pages = [p for p in pdf_info.pages if p.page_number in page_numbers]
        else:
            pages = pdf_info.pages
        
        return "\n\n".join(
            f"[Page {p.page_number}]\n{p.text}"
            for p in pages
            if p.text
        )
    
    def extract_tables(
        self,
        filepath: str | Path,
        page_number: int = None
    ) -> list[dict]:
        """
        Extract tables from the PDF.
        
        Args:
            filepath: Path to the PDF file
            page_number: Optional specific page
            
        Returns:
            List of table dictionaries
        """
        pdf_info = self.parse(filepath)
        
        tables = []
        for page in pdf_info.pages:
            if page_number and page.page_number != page_number:
                continue
            for table in page.tables:
                tables.append(table.to_dict())
        
        return tables
    
    def get_page_summary(
        self,
        filepath: str | Path,
        page_number: int
    ) -> dict:
        """Get a summary of a specific page."""
        pdf_info = self.parse(filepath)
        
        for page in pdf_info.pages:
            if page.page_number == page_number:
                return page.to_dict()
        
        return {"error": f"Page {page_number} not found"}
    
    def search_text(
        self,
        filepath: str | Path,
        query: str
    ) -> list[dict]:
        """
        Search for text in the PDF.
        
        Args:
            filepath: Path to the PDF file
            query: Text to search for
            
        Returns:
            List of matches with page numbers and context
        """
        pdf_info = self.parse(filepath)
        query_lower = query.lower()
        
        matches = []
        for page in pdf_info.pages:
            if query_lower in page.text.lower():
                # Find context around match
                lines = page.text.split("\n")
                for line in lines:
                    if query_lower in line.lower():
                        matches.append({
                            "page": page.page_number,
                            "context": line.strip()[:200]
                        })
        
        return matches
    
    def to_chunks(
        self,
        filepath: str | Path,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> list[dict]:
        """
        Convert PDF to chunks suitable for vector embedding.
        
        Creates structured chunks with metadata:
        - Document summary chunk
        - Page-based text chunks
        - Section chunks when detected
        - Table description chunks
        
        Args:
            filepath: Path to the PDF file
            chunk_size: Target words per chunk
            overlap: Word overlap between chunks
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        pdf_info = self.parse(filepath)
        chunks = []
        
        # 1. Document summary chunk
        doc_summary = f"""PDF Document: {pdf_info.filename}
Pages: {pdf_info.page_count}
Total words: {pdf_info.total_words}
Tables found: {pdf_info.total_tables}"""
        
        chunks.append({
            "text": doc_summary,
            "metadata": {
                "source": pdf_info.filename,
                "type": "pdf",
                "chunk_type": "document_summary",
                "page_count": pdf_info.page_count
            }
        })
        
        # 2. Page-based chunks with smart splitting
        for page in pdf_info.pages:
            if not page.text:
                continue
            
            # Split page into smaller chunks if needed
            words = page.text.split()
            
            if len(words) <= chunk_size:
                # Page fits in one chunk
                page_chunk = f"""[Page {page.page_number} of {pdf_info.filename}]
{page.text}"""
                
                chunks.append({
                    "text": page_chunk,
                    "metadata": {
                        "source": pdf_info.filename,
                        "type": "pdf",
                        "chunk_type": "page_content",
                        "page": page.page_number,
                        "sections": page.sections
                    }
                })
            else:
                # Split into multiple chunks
                for i in range(0, len(words), chunk_size - overlap):
                    chunk_words = words[i:i + chunk_size]
                    chunk_text = " ".join(chunk_words)
                    
                    page_chunk = f"""[Page {page.page_number} of {pdf_info.filename}, Part {i // (chunk_size - overlap) + 1}]
{chunk_text}"""
                    
                    chunks.append({
                        "text": page_chunk,
                        "metadata": {
                            "source": pdf_info.filename,
                            "type": "pdf",
                            "chunk_type": "page_content",
                            "page": page.page_number,
                            "chunk_part": i // (chunk_size - overlap) + 1
                        }
                    })
            
            # 3. Table description chunks
            for table in page.tables:
                headers_str = ", ".join(str(h) for h in table.headers if h)
                table_chunk = f"""Table on Page {page.page_number} of {pdf_info.filename}
Headers: {headers_str}
Rows: {table.row_count}
This table contains structured data related to insurance analysis."""
                
                chunks.append({
                    "text": table_chunk,
                    "metadata": {
                        "source": pdf_info.filename,
                        "type": "pdf",
                        "chunk_type": "table",
                        "page": page.page_number,
                        "table_index": table.table_index
                    }
                })
        
        self.logger.log(
            "pdf_chunked",
            "ingestion",
            {
                "filename": pdf_info.filename,
                "chunks": len(chunks)
            }
        )
        
        return chunks


# Global instance
_parser = None

def get_pdf_parser() -> PDFParser:
    """Get the global PDFParser instance."""
    global _parser
    if _parser is None:
        _parser = PDFParser()
    return _parser

