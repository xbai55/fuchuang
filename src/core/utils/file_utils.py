"""
File handling utilities for temporary files.
Eliminates duplicate temp file logic across the codebase.
"""
import os
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional
import shutil


def create_temp_file(content: bytes, suffix: str = ".tmp") -> str:
    """
    Create a temporary file with given content.

    Args:
        content: Binary content to write
        suffix: File suffix (e.g., '.mp4', '.wav')

    Returns:
        Path to the temporary file
    """
    temp_dir = tempfile.gettempdir()
    filename = f"{uuid.uuid4().hex}{suffix}"
    temp_path = os.path.join(temp_dir, filename)

    with open(temp_path, "wb") as f:
        f.write(content)

    return temp_path


def create_temp_file_from_upload(file_obj, suffix: Optional[str] = None) -> str:
    """
    Create a temporary file from an uploaded file object.

    Args:
        file_obj: File object with .read() method (e.g., FastAPI UploadFile)
        suffix: Optional file suffix override

    Returns:
        Path to the temporary file
    """
    content = file_obj.read()

    if suffix is None and hasattr(file_obj, 'filename'):
        # Extract suffix from original filename
        suffix = Path(file_obj.filename).suffix

    return create_temp_file(content, suffix or ".tmp")


def cleanup_temp_files(file_paths: List[str]) -> None:
    """
    Safely remove multiple temporary files.

    Args:
        file_paths: List of file paths to remove
    """
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"[警告] 清理临时文件失败 {path}: {e}")


def cleanup_temp_file(path: Optional[str]) -> None:
    """
    Safely remove a single temporary file.

    Args:
        path: File path to remove
    """
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"[警告] 清理临时文件失败 {path}: {e}")


def is_url(path: str) -> bool:
    """
    Check if a path is a URL (http:// or https://).

    Args:
        path: Path or URL string

    Returns:
        True if it's a URL, False otherwise
    """
    if not path:
        return False
    return path.startswith("http://") or path.startswith("https://")


def copy_to_temp(source_path: str, suffix: Optional[str] = None) -> str:
    """
    Copy a file to a temporary location.

    Args:
        source_path: Original file path
        suffix: Optional file suffix

    Returns:
        Path to the temporary copy
    """
    if suffix is None:
        suffix = Path(source_path).suffix

    temp_dir = tempfile.gettempdir()
    filename = f"{uuid.uuid4().hex}{suffix}"
    temp_path = os.path.join(temp_dir, filename)

    shutil.copy2(source_path, temp_path)
    return temp_path


def ensure_dir(path: str) -> str:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        The directory path
    """
    Path(path).mkdir(parents=True, exist_ok=True)
    return path
