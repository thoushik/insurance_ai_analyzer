"""
Insurance Document Intelligence Assistant
Ingestion Module

Provides document parsing for Excel and PDF files.
"""

from .excel_parser import ExcelParser, WorkbookInfo, SheetInfo, get_excel_parser
from .pdf_parser import PDFParser, PDFInfo, PageInfo, get_pdf_parser
from .document_registry import DocumentRegistry, DocumentEntry, get_document_registry

__all__ = [
    "ExcelParser",
    "WorkbookInfo",
    "SheetInfo",
    "get_excel_parser",
    "PDFParser",
    "PDFInfo",
    "PageInfo",
    "get_pdf_parser",
    "DocumentRegistry",
    "DocumentEntry",
    "get_document_registry",
]
