"""
Insurance Document Intelligence Assistant
Ingestion Module - Excel Parser

Parses Excel files to extract:
- Workbook structure (sheets, names)
- Sheet purposes (input/calculation/output)
- Cell formulas and calculated values
- Cell dependencies for formula tracing
"""

import re
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

import openpyxl
from openpyxl.utils import get_column_letter

from ..security import get_folder_guard, get_audit_logger


@dataclass
class CellInfo:
    """Information about a single cell."""
    address: str
    value: Any
    formula: Optional[str] = None
    data_type: str = "unknown"
    
    def has_formula(self) -> bool:
        return self.formula is not None and self.formula.startswith("=")


@dataclass
class SheetInfo:
    """Information about an Excel sheet."""
    name: str
    row_count: int
    col_count: int
    purpose: str = "unknown"  # input, calculation, output, mixed
    cells_with_formulas: int = 0
    cells_with_values: int = 0
    sample_formulas: list = field(default_factory=list)
    headers: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "row_count": self.row_count,
            "col_count": self.col_count,
            "purpose": self.purpose,
            "cells_with_formulas": self.cells_with_formulas,
            "cells_with_values": self.cells_with_values,
            "sample_formulas": self.sample_formulas[:5],
            "headers": self.headers
        }


@dataclass
class WorkbookInfo:
    """Information about an Excel workbook."""
    filename: str
    filepath: str
    sheet_count: int
    sheets: list[SheetInfo] = field(default_factory=list)
    named_ranges: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "filepath": self.filepath,
            "sheet_count": self.sheet_count,
            "sheets": [s.to_dict() for s in self.sheets],
            "named_ranges": self.named_ranges
        }


class ExcelParser:
    """
    Parses Excel files for insurance document analysis.
    
    Features:
    - Workbook structure extraction
    - Formula extraction and analysis
    - Sheet purpose classification
    - Dependency mapping
    """
    
    def __init__(self):
        self.guard = get_folder_guard()
        self.logger = get_audit_logger()
        
        # Insurance-related keywords for classification
        self.input_keywords = [
            "input", "assumption", "parameter", "scenario", "data",
            "policy", "premium", "claim", "exposure"
        ]
        self.output_keywords = [
            "output", "result", "summary", "report", "dashboard",
            "reserve", "liability", "projection"
        ]
        self.calc_keywords = [
            "calc", "calculation", "formula", "model", "analysis",
            "actuarial", "factor", "rate"
        ]
    
    def parse(self, filepath: str | Path) -> WorkbookInfo:
        """
        Parse an Excel file and extract all relevant information.
        
        Args:
            filepath: Path to the Excel file
            
        Returns:
            WorkbookInfo containing all extracted data
        """
        # Validate path is safe
        safe_path = self.guard.validate_path(filepath)
        
        self.logger.log_document_access(
            str(safe_path),
            "excel_parse"
        )
        
        # Load workbook with data_only=False to get formulas
        wb = openpyxl.load_workbook(safe_path, data_only=False)
        
        # Also load with data_only=True for calculated values
        wb_values = openpyxl.load_workbook(safe_path, data_only=True)
        
        workbook_info = WorkbookInfo(
            filename=safe_path.name,
            filepath=str(safe_path),
            sheet_count=len(wb.sheetnames)
        )
        
        # Extract named ranges
        workbook_info.named_ranges = list(wb.defined_names.keys())
        
        # Process each sheet
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            sheet_values = wb_values[sheet_name]
            
            sheet_info = self._parse_sheet(sheet, sheet_values)
            workbook_info.sheets.append(sheet_info)
        
        wb.close()
        wb_values.close()
        
        self.logger.log_ingestion(
            safe_path.name,
            "excel",
            True,
            {"sheets": len(workbook_info.sheets)}
        )
        
        return workbook_info
    
    def _parse_sheet(
        self,
        sheet,
        sheet_values
    ) -> SheetInfo:
        """Parse a single sheet."""
        sheet_info = SheetInfo(
            name=sheet.title,
            row_count=sheet.max_row or 0,
            col_count=sheet.max_column or 0
        )
        
        # Extract headers (first row)
        if sheet.max_row and sheet.max_row > 0:
            for col in range(1, min(sheet.max_column or 0, 20) + 1):
                cell = sheet.cell(row=1, column=col)
                if cell.value:
                    sheet_info.headers.append(str(cell.value))
        
        # Count formulas and values
        formulas = []
        # Scan more rows and columns for comprehensive formula coverage
        for row in range(1, min(sheet.max_row or 0, 500) + 1):
            for col in range(1, min(sheet.max_column or 0, 100) + 1):
                cell = sheet.cell(row=row, column=col)
                
                if cell.value is not None:
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        sheet_info.cells_with_formulas += 1
                        addr = f"{get_column_letter(col)}{row}"
                        formulas.append({
                            "cell": addr,
                            "formula": cell.value
                        })
                    else:
                        sheet_info.cells_with_values += 1
        
        # Store more formulas for better RAG retrieval (200 per sheet max)
        sheet_info.sample_formulas = formulas[:200]
        
        # Classify sheet purpose
        sheet_info.purpose = self._classify_sheet(sheet_info)
        
        return sheet_info
    
    def _classify_sheet(self, sheet_info: SheetInfo) -> str:
        """
        Classify sheet as input, calculation, output, or mixed.
        """
        name_lower = sheet_info.name.lower()
        headers_lower = " ".join(sheet_info.headers).lower()
        
        # Check keywords
        input_score = sum(1 for kw in self.input_keywords if kw in name_lower or kw in headers_lower)
        output_score = sum(1 for kw in self.output_keywords if kw in name_lower or kw in headers_lower)
        calc_score = sum(1 for kw in self.calc_keywords if kw in name_lower or kw in headers_lower)
        
        # Also consider formula ratio
        total_cells = sheet_info.cells_with_formulas + sheet_info.cells_with_values
        if total_cells > 0:
            formula_ratio = sheet_info.cells_with_formulas / total_cells
        else:
            formula_ratio = 0
        
        # Classification logic
        if formula_ratio > 0.5 or calc_score > 0:
            return "calculation"
        elif output_score > input_score:
            return "output"
        elif input_score > 0:
            return "input"
        elif formula_ratio > 0.2:
            return "calculation"
        else:
            return "mixed"
    
    def extract_formulas(
        self,
        filepath: str | Path,
        sheet_name: str = None
    ) -> list[dict]:
        """
        Extract all formulas from an Excel file.
        
        Args:
            filepath: Path to the Excel file
            sheet_name: Optional specific sheet to extract from
            
        Returns:
            List of formula dictionaries with cell, formula, and context
        """
        safe_path = self.guard.validate_path(filepath)
        
        wb = openpyxl.load_workbook(safe_path, data_only=False)
        wb_values = openpyxl.load_workbook(safe_path, data_only=True)
        
        formulas = []
        
        sheets_to_process = [sheet_name] if sheet_name else wb.sheetnames
        
        for sname in sheets_to_process:
            if sname not in wb.sheetnames:
                continue
                
            sheet = wb[sname]
            sheet_values = wb_values[sname]
            
            for row in range(1, (sheet.max_row or 0) + 1):
                for col in range(1, (sheet.max_column or 0) + 1):
                    cell = sheet.cell(row=row, column=col)
                    
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        addr = f"{get_column_letter(col)}{row}"
                        
                        # Get calculated value
                        calc_cell = sheet_values.cell(row=row, column=col)
                        
                        formulas.append({
                            "sheet": sname,
                            "cell": addr,
                            "formula": cell.value,
                            "calculated_value": calc_cell.value,
                            "row": row,
                            "column": col
                        })
        
        wb.close()
        wb_values.close()
        
        return formulas
    
    def get_sheet_summary(
        self,
        filepath: str | Path,
        sheet_name: str
    ) -> dict:
        """
        Get a detailed summary of a specific sheet.
        """
        workbook_info = self.parse(filepath)
        
        for sheet in workbook_info.sheets:
            if sheet.name == sheet_name:
                return sheet.to_dict()
        
        return {"error": f"Sheet '{sheet_name}' not found"}
    
    def to_chunks(self, filepath: str | Path) -> list[dict]:
        """
        Convert Excel file to chunks suitable for vector embedding.
        
        Creates structured chunks with rich metadata for RAG:
        - Workbook summary chunk
        - Sheet purpose chunks  
        - Formula explanation chunks
        
        Args:
            filepath: Path to the Excel file
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        workbook_info = self.parse(filepath)
        chunks = []
        
        # 1. Workbook summary chunk
        sheet_names = [s.name for s in workbook_info.sheets]
        workbook_summary = f"""Workbook: {workbook_info.filename}
This Excel workbook contains {workbook_info.sheet_count} sheets: {', '.join(sheet_names)}.
Named ranges defined: {', '.join(workbook_info.named_ranges) if workbook_info.named_ranges else 'None'}"""
        
        chunks.append({
            "text": workbook_summary,
            "metadata": {
                "source": workbook_info.filename,
                "type": "excel",
                "chunk_type": "workbook_summary",
                "sheet_count": workbook_info.sheet_count
            }
        })
        
        # 2. Sheet-level chunks
        for sheet in workbook_info.sheets:
            sheet_text = f"""Sheet: {sheet.name} in {workbook_info.filename}
Purpose: {sheet.purpose}
Size: {sheet.row_count} rows x {sheet.col_count} columns
Contains {sheet.cells_with_formulas} formulas and {sheet.cells_with_values} values.
Headers: {', '.join(sheet.headers) if sheet.headers else 'None detected'}"""
            
            chunks.append({
                "text": sheet_text,
                "metadata": {
                    "source": workbook_info.filename,
                    "type": "excel",
                    "chunk_type": "sheet_summary",
                    "sheet": sheet.name,
                    "purpose": sheet.purpose
                }
            })
            
            # 3. Formula chunks (one per formula for granular retrieval)
            for formula_info in sheet.sample_formulas:
                cell = formula_info.get("cell", "")
                formula = formula_info.get("formula", "")
                
                formula_text = f"""Formula in {workbook_info.filename}, Sheet: {sheet.name}, Cell: {cell}
Formula: {formula}
This is a {sheet.purpose} calculation."""
                
                chunks.append({
                    "text": formula_text,
                    "metadata": {
                        "source": workbook_info.filename,
                        "type": "excel",
                        "chunk_type": "formula",
                        "sheet": sheet.name,
                        "cell": cell,
                        "formula": formula
                    }
                })
        
        self.logger.log(
            "excel_chunked",
            "ingestion",
            {
                "filename": workbook_info.filename,
                "chunks": len(chunks)
            }
        )
        
        return chunks


# Global instance
_parser = None

def get_excel_parser() -> ExcelParser:
    """Get the global ExcelParser instance."""
    global _parser
    if _parser is None:
        _parser = ExcelParser()
    return _parser

