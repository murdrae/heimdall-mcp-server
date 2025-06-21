"""
Git commit data structures for the cognitive memory system.

This module defines git commit representation for direct storage as memories.
Each commit becomes a memory with metadata and file changes, providing
a straightforward approach to git history analysis.
"""

from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from .security import (
    _sanitize_string,
    sanitize_git_data,
    validate_commit_hash,
    validate_file_path,
)

# Constants for validation
MAX_COMMIT_MESSAGE_LENGTH = 10000
MAX_AUTHOR_NAME_LENGTH = 255
MAX_AUTHOR_EMAIL_LENGTH = 320
MAX_FILE_PATH_LENGTH = 4096
MAX_FILES_PER_COMMIT = 1000


@dataclass
class FileChange:
    """Represents a single file change within a commit."""

    file_path: str
    change_type: str  # A, M, D, R, C, T, U, X, B
    lines_added: int = 0
    lines_deleted: int = 0

    def __post_init__(self) -> None:
        """Validate and sanitize fields after initialization."""
        # Validate file path
        if not validate_file_path(self.file_path, MAX_FILE_PATH_LENGTH):
            raise ValueError(f"Invalid file path: {self.file_path}")

        self.file_path = _sanitize_string(self.file_path, MAX_FILE_PATH_LENGTH)

        # Validate change type
        valid_types = {"A", "M", "D", "R", "C", "T", "U", "X", "B"}
        if self.change_type not in valid_types:
            raise ValueError(f"Invalid change type: {self.change_type}")

        # Validate line counts
        if self.lines_added < 0 or self.lines_deleted < 0:
            raise ValueError("Line counts must be non-negative")


@dataclass
class Commit:
    """Represents a git commit with validation."""

    hash: str
    message: str
    author_name: str
    author_email: str
    timestamp: datetime
    file_changes: list[FileChange]
    parent_hashes: list[str]

    def __post_init__(self) -> None:
        """Validate and sanitize all fields after initialization."""
        # Validate commit hash
        if not validate_commit_hash(self.hash):
            raise ValueError(f"Invalid commit hash: {self.hash}")

        # Sanitize and validate message
        if len(self.message) > MAX_COMMIT_MESSAGE_LENGTH:
            logger.warning(
                "Commit message truncated",
                original_length=len(self.message),
                commit_hash=self.hash,
            )
            self.message = self.message[:MAX_COMMIT_MESSAGE_LENGTH] + "..."

        self.message = _sanitize_string(self.message, MAX_COMMIT_MESSAGE_LENGTH)

        # Validate author info
        if len(self.author_name) > MAX_AUTHOR_NAME_LENGTH:
            self.author_name = self.author_name[:MAX_AUTHOR_NAME_LENGTH]
        self.author_name = _sanitize_string(self.author_name, MAX_AUTHOR_NAME_LENGTH)

        if len(self.author_email) > MAX_AUTHOR_EMAIL_LENGTH:
            self.author_email = self.author_email[:MAX_AUTHOR_EMAIL_LENGTH]
        self.author_email = _sanitize_string(self.author_email, MAX_AUTHOR_EMAIL_LENGTH)

        # Validate timestamp
        if not isinstance(self.timestamp, datetime):
            raise ValueError("Timestamp must be a datetime object")

        # Validate file changes
        if len(self.file_changes) > MAX_FILES_PER_COMMIT:
            logger.warning(
                "Too many file changes, truncating",
                original_count=len(self.file_changes),
                commit_hash=self.hash,
            )
            self.file_changes = self.file_changes[:MAX_FILES_PER_COMMIT]

        # Validate parent hashes
        for parent_hash in self.parent_hashes:
            if not validate_commit_hash(parent_hash):
                raise ValueError(f"Invalid parent hash: {parent_hash}")

    @classmethod
    def from_dict(cls, data: dict) -> "Commit":
        """Create Commit from dictionary with validation."""
        try:
            # Sanitize input data
            sanitized_data = sanitize_git_data(data)

            # Extract required fields
            commit_hash = sanitized_data.get("hash", "")
            message = sanitized_data.get("message", "")
            author_name = sanitized_data.get("author_name", "")
            author_email = sanitized_data.get("author_email", "")
            timestamp = sanitized_data.get("timestamp")
            file_changes_data = sanitized_data.get("file_changes", [])
            parent_hashes = sanitized_data.get("parent_hashes", [])

            # Validate required fields
            if not commit_hash:
                raise ValueError("Commit hash is required")

            # Handle timestamp conversion
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            elif not isinstance(timestamp, datetime):
                timestamp = datetime.now()

            # Convert file changes
            file_changes = []
            for fc_data in file_changes_data:
                if isinstance(fc_data, dict):
                    file_change = FileChange(
                        file_path=fc_data.get("file_path", ""),
                        change_type=fc_data.get("change_type", "M"),
                        lines_added=fc_data.get("lines_added", 0),
                        lines_deleted=fc_data.get("lines_deleted", 0),
                    )
                    file_changes.append(file_change)

            return cls(
                hash=commit_hash,
                message=message,
                author_name=author_name,
                author_email=author_email,
                timestamp=timestamp,
                file_changes=file_changes,
                parent_hashes=parent_hashes,
            )

        except Exception as e:
            logger.error("Failed to create Commit from dict", data=data, error=str(e))
            raise

    def get_affected_files(self) -> list[str]:
        """Get list of all file paths affected by this commit."""
        return [fc.file_path for fc in self.file_changes]

    def get_total_line_changes(self) -> tuple[int, int]:
        """Get total lines added and deleted across all files."""
        total_added = sum(fc.lines_added for fc in self.file_changes)
        total_deleted = sum(fc.lines_deleted for fc in self.file_changes)
        return total_added, total_deleted

    def to_natural_language(self) -> str:
        """Convert commit to natural language description for memory storage."""
        # Format timestamp
        time_str = self.timestamp.strftime("%Y-%m-%d %H:%M")

        # Get file summary
        affected_files = self.get_affected_files()
        file_count = len(affected_files)

        if file_count == 0:
            file_summary = "no files"
        elif file_count == 1:
            file_summary = f"1 file: {affected_files[0]}"
        elif file_count <= 3:
            file_summary = f"{file_count} files: {', '.join(affected_files)}"
        else:
            file_summary = (
                f"{file_count} files including: {', '.join(affected_files[:3])}..."
            )

        # Get line change summary
        total_added, total_deleted = self.get_total_line_changes()
        change_summary = f"+{total_added}/-{total_deleted} lines"

        # Generate description
        description = (
            f"Git commit {self.hash[:8]} by {self.author_name} on {time_str}: "
            f'"{self.message.strip()}" - Modified {file_summary} ({change_summary})'
        )

        return description
