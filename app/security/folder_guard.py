"""
Insurance Document Intelligence Assistant
Security Module - Folder Guard

Enforces all file operations stay within the project folder.
This is a critical security component for SR 11-7 compliance.
"""

import os
from pathlib import Path
from functools import wraps


class SecurityViolationError(Exception):
    """Raised when an operation attempts to access files outside the allowed folder."""
    pass


class FolderGuard:
    """
    Enforces folder-safety rules:
    - All operations must stay within the project folder
    - No modification, deletion, or access to external files
    - Read-only mode for uploaded documents
    """
    
    def __init__(self, base_path: str = None):
        """
        Initialize the folder guard with a base path.
        
        Args:
            base_path: The root folder for all operations. Defaults to project root.
        """
        if base_path is None:
            # Default to the project root (parent of app/)
            self.base_path = Path(__file__).parent.parent.parent.resolve()
        else:
            self.base_path = Path(base_path).resolve()
        
        # Define allowed subdirectories
        self.upload_dir = self.base_path / "data" / "uploads"
        self.logs_dir = self.base_path / "logs"
        self.cache_dir = self.base_path / "cache"
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories if they don't exist."""
        for directory in [self.upload_dir, self.logs_dir, self.cache_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            # Create .gitkeep files
            gitkeep = directory / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()
    
    def validate_path(self, path: str | Path) -> Path:
        """
        Validate that a path is within the allowed project folder.
        
        Args:
            path: The path to validate
            
        Returns:
            Resolved Path object if valid
            
        Raises:
            SecurityViolationError: If path is outside allowed folder
        """
        resolved = Path(path).resolve()
        
        try:
            # Check if the path is relative to base_path
            resolved.relative_to(self.base_path)
            return resolved
        except ValueError:
            raise SecurityViolationError(
                f"Access denied: Path '{path}' is outside the allowed folder. "
                f"All operations must stay within '{self.base_path}'"
            )
    
    def validate_upload_path(self, path: str | Path) -> Path:
        """
        Validate that a path is within the uploads directory.
        
        Args:
            path: The path to validate
            
        Returns:
            Resolved Path object if valid
            
        Raises:
            SecurityViolationError: If path is outside uploads folder
        """
        resolved = Path(path).resolve()
        
        try:
            resolved.relative_to(self.upload_dir)
            return resolved
        except ValueError:
            raise SecurityViolationError(
                f"Access denied: Path '{path}' is outside the uploads folder. "
                f"Uploaded documents must be in '{self.upload_dir}'"
            )
    
    def is_safe_path(self, path: str | Path) -> bool:
        """
        Check if a path is safe (within project folder) without raising an exception.
        
        Args:
            path: The path to check
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            self.validate_path(path)
            return True
        except SecurityViolationError:
            return False
    
    def safe_read(self, path: str | Path, mode: str = 'r') -> str | bytes:
        """
        Safely read a file, ensuring it's within the allowed folder.
        
        Args:
            path: Path to the file to read
            mode: Read mode ('r' for text, 'rb' for binary)
            
        Returns:
            File contents
            
        Raises:
            SecurityViolationError: If path is outside allowed folder
        """
        kwargs = {}
        if 'b' not in mode:
            kwargs['encoding'] = 'utf-8'
            
        with open(validated_path, mode, **kwargs) as f:
            return f.read()
    
    def safe_write(self, path: str | Path, content: str | bytes, mode: str = 'w'):
        """
        Safely write to a file, ensuring it's within the allowed folder
        and NOT in the uploads directory (which is read-only).
        
        Args:
            path: Path to write to
            content: Content to write
            mode: Write mode ('w' for text, 'wb' for binary)
            
        Raises:
            SecurityViolationError: If path is outside allowed folder or in uploads
        """
        validated_path = self.validate_path(path)
        
        # Check that we're not writing to uploads (read-only)
        try:
            validated_path.relative_to(self.upload_dir)
            raise SecurityViolationError(
                f"Write denied: The uploads folder is read-only. "
                f"Cannot write to '{path}'"
            )
        except ValueError:
            # Good - path is not in uploads, we can write
            pass
        
        # Ensure parent directory exists
        validated_path.parent.mkdir(parents=True, exist_ok=True)
        
        kwargs = {}
        if 'b' not in mode:
            kwargs['encoding'] = 'utf-8'
        
        with open(validated_path, mode, **kwargs) as f:
            f.write(content)
    
    def list_uploads(self) -> list[Path]:
        """
        List all files in the uploads directory.
        
        Returns:
            List of Path objects for uploaded files
        """
        return list(self.upload_dir.rglob("*"))
    
    def get_upload_path(self, filename: str) -> Path:
        """
        Get the full path for an upload, validating the filename.
        
        Args:
            filename: The filename to get path for
            
        Returns:
            Full Path to the upload location
        """
        # Sanitize filename to prevent directory traversal
        safe_filename = Path(filename).name  # Strip any directory components
        return self.upload_dir / safe_filename


# Decorator for functions that access files
def require_safe_path(func):
    """Decorator to ensure file operations use safe paths."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        guard = FolderGuard()
        
        # Check all string/Path arguments
        for arg in args:
            if isinstance(arg, (str, Path)):
                if os.path.sep in str(arg) or '/' in str(arg):
                    guard.validate_path(arg)
        
        for key, value in kwargs.items():
            if isinstance(value, (str, Path)):
                if os.path.sep in str(value) or '/' in str(value):
                    guard.validate_path(value)
        
        return func(*args, **kwargs)
    
    return wrapper


# Global instance
_guard = None

def get_folder_guard() -> FolderGuard:
    """Get the global FolderGuard instance."""
    global _guard
    if _guard is None:
        _guard = FolderGuard()
    return _guard
