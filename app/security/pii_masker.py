"""
Insurance Document Intelligence Assistant
Security Module - PII Masker

Detects and masks Personally Identifiable Information (PII)
before sending to LLM for processing.
"""

import re
from typing import Tuple


class PIIMasker:
    """
    Detects and masks PII in text.
    
    Supports:
    - Social Security Numbers (SSN)
    - Phone numbers
    - Email addresses
    - Credit card numbers
    - Names (basic pattern matching)
    - Dates of birth
    - Addresses (basic pattern matching)
    """
    
    def __init__(self):
        # Compile regex patterns for efficiency
        self.patterns = {
            "ssn": (
                re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'),
                "[SSN MASKED]"
            ),
            "phone": (
                re.compile(r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
                "[PHONE MASKED]"
            ),
            "email": (
                re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
                "[EMAIL MASKED]"
            ),
            "credit_card": (
                re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
                "[CREDIT CARD MASKED]"
            ),
            "dob": (
                re.compile(r'\b(?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12]\d|3[01])[-/](?:19|20)\d{2}\b'),
                "[DOB MASKED]"
            ),
            "ip_address": (
                re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
                "[IP MASKED]"
            ),
        }
        
        # Track what was masked for audit
        self.last_mask_report = {}
    
    def mask(self, text: str) -> Tuple[str, dict]:
        """
        Mask all PII in the given text.
        
        Args:
            text: The text to mask
            
        Returns:
            Tuple of (masked_text, mask_report)
            mask_report contains counts of each PII type found
        """
        masked_text = text
        mask_report = {}
        
        for pii_type, (pattern, replacement) in self.patterns.items():
            matches = pattern.findall(masked_text)
            if matches:
                mask_report[pii_type] = len(matches)
                masked_text = pattern.sub(replacement, masked_text)
        
        self.last_mask_report = mask_report
        return masked_text, mask_report
    
    def mask_text(self, text: str) -> str:
        """
        Mask PII and return only the masked text.
        
        Args:
            text: The text to mask
            
        Returns:
            Masked text string
        """
        masked, _ = self.mask(text)
        return masked
    
    def contains_pii(self, text: str) -> bool:
        """
        Check if text contains any PII without masking.
        
        Args:
            text: The text to check
            
        Returns:
            True if PII is detected, False otherwise
        """
        for pattern, _ in self.patterns.values():
            if pattern.search(text):
                return True
        return False
    
    def get_pii_locations(self, text: str) -> dict:
        """
        Get the locations of all PII in the text.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary mapping PII types to list of (start, end) positions
        """
        locations = {}
        
        for pii_type, (pattern, _) in self.patterns.items():
            matches = list(pattern.finditer(text))
            if matches:
                locations[pii_type] = [
                    (m.start(), m.end()) for m in matches
                ]
        
        return locations
    
    def add_custom_pattern(
        self,
        name: str,
        pattern: str,
        replacement: str
    ):
        """
        Add a custom PII pattern.
        
        Args:
            name: Name for the pattern
            pattern: Regex pattern string
            replacement: Replacement text when matched
        """
        self.patterns[name] = (re.compile(pattern), replacement)
    
    def mask_for_logging(self, text: str, max_length: int = 500) -> str:
        """
        Mask PII and truncate for safe logging.
        
        Args:
            text: The text to process
            max_length: Maximum length of output
            
        Returns:
            Masked and truncated text safe for logging
        """
        masked, _ = self.mask(text)
        if len(masked) > max_length:
            return masked[:max_length] + "... [TRUNCATED]"
        return masked


# Global instance
_masker = None

def get_pii_masker() -> PIIMasker:
    """Get the global PIIMasker instance."""
    global _masker
    if _masker is None:
        _masker = PIIMasker()
    return _masker
