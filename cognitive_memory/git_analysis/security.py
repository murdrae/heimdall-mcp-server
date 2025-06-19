"""
Security module for git repository analysis.

This module provides comprehensive security controls for git repository access,
including path validation, sanitization, and attack prevention.
"""

import hashlib
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from loguru import logger


class GitPatternIDGenerator:
    """
    Generates canonical, deterministic IDs for git patterns.

    Ensures consistent ID generation across platforms and repository analyses
    using path canonicalization and SHA-256 hashing.
    """

    @staticmethod
    def generate_cochange_id(file_a: str, file_b: str) -> str:
        """
        Generate deterministic ID for co-change pattern.

        Args:
            file_a: First file path
            file_b: Second file path

        Returns:
            Canonical pattern ID
        """
        # Canonicalize and sort for consistency
        canonical_a = canonicalize_path(file_a)
        canonical_b = canonicalize_path(file_b)

        # Ensure lexicographic ordering for deterministic results
        file_1, file_2 = sorted([canonical_a, canonical_b])

        # Create pattern key
        pattern_key = f"{file_1}|{file_2}"

        # Generate SHA-256 hash
        pattern_hash = hashlib.sha256(pattern_key.encode("utf-8")).hexdigest()

        return f"git::cochange::{pattern_hash}"

    @staticmethod
    def generate_hotspot_id(file_path: str) -> str:
        """
        Generate deterministic ID for maintenance hotspot.

        Args:
            file_path: File path for hotspot

        Returns:
            Canonical pattern ID
        """
        # Canonicalize path
        canonical_path = canonicalize_path(file_path)

        # Generate SHA-256 hash
        pattern_hash = hashlib.sha256(canonical_path.encode("utf-8")).hexdigest()

        return f"git::hotspot::{pattern_hash}"

    @staticmethod
    def generate_solution_id(problem_type: str, solution_approach: str) -> str:
        """
        Generate deterministic ID for solution pattern.

        Args:
            problem_type: Type of problem
            solution_approach: Solution approach used

        Returns:
            Canonical pattern ID
        """
        # Normalize and canonicalize
        canonical_problem = problem_type.lower().strip()
        canonical_solution = solution_approach.lower().strip()

        # Create pattern key
        pattern_key = f"{canonical_problem}|{canonical_solution}"

        # Generate SHA-256 hash
        pattern_hash = hashlib.sha256(pattern_key.encode("utf-8")).hexdigest()

        return f"git::solution::{pattern_hash}"


def validate_repository_path(path: str) -> bool:
    """
    Validate repository path against security threats.

    Performs comprehensive validation including:
    - Directory traversal attack prevention
    - Repository structure verification
    - Access permission checking
    - Path canonicalization

    Args:
        path: Repository path to validate

    Returns:
        True if path is a valid, safe git repository

    Raises:
        ValueError: If path contains security threats
    """
    try:
        # Basic path validation
        if not path or not isinstance(path, str):
            logger.warning("Invalid path type or empty path provided")
            return False

        # Strip whitespace and normalize
        path = path.strip()
        if not path:
            logger.warning("Empty path after normalization")
            return False

        # Check for directory traversal patterns
        dangerous_patterns = [
            "..",  # Parent directory traversal
            "~",  # Home directory reference
            "\\\\",  # UNC paths on Windows
            "\x00",  # Null byte injection
            "|",  # Command injection
            ";",  # Command chaining
            "&",  # Command chaining
            "`",  # Command substitution
            "$(",  # Command substitution
            "${",  # Variable expansion
        ]

        for pattern in dangerous_patterns:
            if pattern in path:
                logger.warning(
                    f"Dangerous pattern '{pattern}' detected in path: {path}"
                )
                return False

        # Additional regex checks for sophisticated attacks
        dangerous_regex_patterns = [
            r"\.\.[\\/]",  # Directory traversal
            r"[\\/]\.\.[\\/]",  # Nested traversal
            r"[\x00-\x1f\x7f-\x9f]",  # Control characters
            r'[<>:"|?*]',  # Windows forbidden characters
        ]

        for pattern in dangerous_regex_patterns:
            if re.search(pattern, path):
                logger.warning(f"Path contains dangerous pattern: {path}")
                return False

        # Convert to Path object for safe handling
        try:
            repo_path = Path(path).resolve()
        except (OSError, ValueError) as e:
            logger.warning(f"Path resolution failed: {e}")
            return False

        # Check if path exists
        if not repo_path.exists():
            logger.warning(f"Repository path does not exist: {repo_path}")
            return False

        # Check if it's a directory
        if not repo_path.is_dir():
            logger.warning(f"Repository path is not a directory: {repo_path}")
            return False

        # Check for .git directory (indicates git repository)
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            logger.warning(f"No .git directory found in: {repo_path}")
            return False

        # Check read permissions
        if not os.access(repo_path, os.R_OK):
            logger.warning(f"No read permission for repository: {repo_path}")
            return False

        # Additional security: ensure it's not in system directories
        system_dirs = [
            "/bin",
            "/sbin",
            "/usr/bin",
            "/usr/sbin",
            "/etc",
            "/proc",
            "/sys",
            "/dev",
            "C:\\Windows",
            "C:\\System32",
            "C:\\Program Files",
        ]

        repo_str = str(repo_path).lower()
        for sys_dir in system_dirs:
            if repo_str.startswith(sys_dir.lower()):
                logger.warning(
                    f"Repository in system directory not allowed: {repo_path}"
                )
                return False

        logger.info(f"Repository path validation successful: {repo_path}")
        return True

    except Exception as e:
        logger.error(f"Repository path validation failed with exception: {e}")
        return False


def canonicalize_path(path: str) -> str:
    """
    Canonicalize path for consistent ID generation.

    Provides deterministic path normalization to ensure consistent
    pattern IDs across different systems and invocations.

    Args:
        path: File or directory path to canonicalize

    Returns:
        Canonicalized path string suitable for ID generation
    """
    try:
        # Handle empty or invalid input
        if not path or not isinstance(path, str):
            return ""

        # Unicode normalization (NFC form)
        normalized = unicodedata.normalize("NFC", path)

        # Convert to lowercase for case-insensitive comparison
        normalized = normalized.lower()

        # Normalize path separators to forward slashes
        normalized = normalized.replace("\\", "/")

        # Remove duplicate slashes
        normalized = re.sub(r"/+", "/", normalized)

        # Remove leading/trailing slashes for consistency
        normalized = normalized.strip("/")

        # Handle relative path markers consistently
        normalized = re.sub(r"/\./", "/", normalized)
        normalized = re.sub(r"^\./", "", normalized)

        return normalized

    except Exception as e:
        logger.warning(f"Path canonicalization failed: {e}, returning empty string")
        return ""


def sanitize_git_data(data: dict[str, Any], max_length: int = 10000) -> dict[str, Any]:
    """
    Sanitize git data for safe processing.

    Cleans commit messages, file paths, author information, and other
    git data to prevent injection attacks and ensure safe processing.

    Args:
        data: Dictionary containing git data to sanitize
        max_length: Maximum length for text fields

    Returns:
        Sanitized data dictionary
    """
    try:
        sanitized: dict[str, Any] = {}

        for key, value in data.items():
            if value is None:
                sanitized[key] = None
                continue

            if isinstance(value, str):
                sanitized[key] = _sanitize_string(value, max_length)
            elif isinstance(value, list):
                sanitized[key] = [
                    _sanitize_string(item, max_length)
                    if isinstance(item, str)
                    else item
                    for item in value[:100]  # Limit list size
                ]
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = sanitize_git_data(value, max_length)
            else:
                # Keep non-string values as-is (numbers, booleans, etc.)
                sanitized[key] = value

        return sanitized

    except Exception as e:
        logger.error(f"Git data sanitization failed: {e}")
        return {}


def _sanitize_string(text: Any, max_length: int) -> str:
    """
    Sanitize individual string values.

    Args:
        text: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(text, str):
        return str(text)[:max_length]

    # Unicode normalization
    normalized = unicodedata.normalize("NFC", text)

    # Remove control characters (except newlines and tabs)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", normalized)

    # Remove potential script injection patterns
    dangerous_patterns = [
        r"<script[^>]*>.*?</script>",
        r"<script[^>]*>",
        r"</script>",
        r"<[^>]*script[^>]*>",
        r"javascript:",
        r"vbscript:",
        r"data:text/html",
        r"<!--.*?-->",
    ]

    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE | re.DOTALL)

    # Limit length and ensure valid UTF-8
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        # Ensure we don't cut off in the middle of a multi-byte character
        try:
            sanitized.encode("utf-8")
        except UnicodeEncodeError:
            # If encoding fails, truncate more conservatively
            sanitized = sanitized[: max_length - 10]

    return sanitized


def generate_secure_id(data: Any) -> str:
    """
    Generate a secure, deterministic ID from input data.

    Args:
        data: Input data for ID generation

    Returns:
        SHA-256 hash as hexadecimal string
    """
    try:
        # Ensure consistent encoding
        if isinstance(data, str):
            data_bytes = data.encode("utf-8")
        else:
            data_bytes = str(data).encode("utf-8")

        # Generate SHA-256 hash
        hash_obj = hashlib.sha256(data_bytes)
        return hash_obj.hexdigest()

    except Exception as e:
        logger.error(f"Secure ID generation failed: {e}")
        # Use a deterministic fallback that's the right length (64 chars for SHA-256)
        return "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def validate_commit_hash(commit_hash: str) -> bool:
    """
    Validate git commit hash format.

    Args:
        commit_hash: Git commit hash to validate

    Returns:
        True if hash format is valid
    """
    if not commit_hash or not isinstance(commit_hash, str):
        return False

    # Git commit hashes are 40-character SHA-1 hashes (or 64-character SHA-256)
    if len(commit_hash) not in [40, 64]:
        return False

    # Check if it's a valid hexadecimal string
    try:
        int(commit_hash, 16)
        return True
    except ValueError:
        return False


def validate_file_path(file_path: str, max_length: int = 4096) -> bool:
    """
    Validate file path for security and length constraints.

    Args:
        file_path: File path to validate
        max_length: Maximum allowed path length

    Returns:
        True if path is valid and safe
    """
    if not file_path or not isinstance(file_path, str):
        return False

    if len(file_path) > max_length:
        return False

    # Check for dangerous patterns
    dangerous_patterns = ["..", "\x00", "|", ";", "&", "`", "$(", "${"]
    for pattern in dangerous_patterns:
        if pattern in file_path:
            return False

    return True
