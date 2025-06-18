"""Data structures for git analysis with comprehensive validation.

This module defines validated data structures for git repository analysis,
ensuring all commit data is properly sanitized and validated before processing.
All structures include security controls and input validation to prevent
malicious data injection.

Data Structures:
- CommitEvent: Represents a git commit with validation
- FileChangeEvent: Represents file changes with path validation
- ProblemCommit: Represents commits that fix issues with validation
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger

from .security import (
    _sanitize_string,
    sanitize_git_data,
    validate_commit_hash,
    validate_file_path,
)

# Data validation constants
MAX_COMMIT_MESSAGE_LENGTH = 10000
MAX_AUTHOR_NAME_LENGTH = 255
MAX_AUTHOR_EMAIL_LENGTH = 320
MAX_FILE_PATH_LENGTH = 4096
MAX_FILES_PER_COMMIT = 1000
VALID_CHANGE_TYPES = {"A", "M", "D", "R", "C", "T", "U", "X", "B"}
VALID_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class CommitEvent:
    """Represents a git commit event with security validation.

    All fields are validated and sanitized upon creation to ensure
    safe processing and prevent injection attacks.

    Attributes:
        hash: Git commit hash (validated SHA-1/SHA-256)
        message: Commit message (sanitized, length-limited)
        author_name: Author name (sanitized, length-limited)
        author_email: Author email (validated format, sanitized)
        timestamp: Commit timestamp (validated datetime)
        files: List of changed files (validated paths)
        parent_hashes: List of parent commit hashes (validated)
    """

    hash: Any
    message: Any
    author_name: Any
    author_email: Any
    timestamp: Any
    files: Any
    parent_hashes: Any

    def __post_init__(self) -> None:
        """Validate and sanitize all fields after initialization."""
        self._validate_and_sanitize()

    def _validate_and_sanitize(self) -> None:
        """Comprehensive validation and sanitization of all fields."""
        try:
            # Validate and sanitize commit hash
            if not validate_commit_hash(self.hash):
                logger.warning("Invalid commit hash", hash=self.hash)
                raise ValueError(f"Invalid commit hash: {self.hash}")

            # Sanitize commit message
            if not isinstance(self.message, str):
                self.message = str(self.message)

            if len(self.message) > MAX_COMMIT_MESSAGE_LENGTH:
                logger.warning(
                    "Commit message truncated",
                    original_length=len(self.message),
                    commit_hash=self.hash,
                )
                self.message = self.message[:MAX_COMMIT_MESSAGE_LENGTH] + "..."

            self.message = _sanitize_string(self.message, MAX_COMMIT_MESSAGE_LENGTH)

            # Validate and sanitize author name
            if not isinstance(self.author_name, str):
                self.author_name = str(self.author_name)

            if len(self.author_name) > MAX_AUTHOR_NAME_LENGTH:
                self.author_name = self.author_name[:MAX_AUTHOR_NAME_LENGTH]

            self.author_name = _sanitize_string(
                self.author_name, MAX_AUTHOR_NAME_LENGTH
            )

            # Validate and sanitize author email
            if not isinstance(self.author_email, str):
                self.author_email = str(self.author_email)

            if len(self.author_email) > MAX_AUTHOR_EMAIL_LENGTH:
                self.author_email = self.author_email[:MAX_AUTHOR_EMAIL_LENGTH]

            self.author_email = _sanitize_string(
                self.author_email, MAX_AUTHOR_EMAIL_LENGTH
            )

            # Basic email format validation
            if self.author_email is None:
                raise ValueError(f"Invalid author email: {self.author_email}")
            elif not self.author_email.strip():
                raise ValueError(f"Invalid author email: {self.author_email}")
            elif not VALID_EMAIL_PATTERN.match(self.author_email):
                logger.debug(
                    "Invalid email format",
                    email=self.author_email,
                    commit_hash=self.hash,
                )
                raise ValueError(f"Invalid author email: {self.author_email}")

            # Validate timestamp
            if not isinstance(self.timestamp, datetime):
                logger.warning(
                    "Invalid timestamp type",
                    timestamp=self.timestamp,
                    commit_hash=self.hash,
                )
                self.timestamp = datetime.now()

            # Validate and sanitize file paths
            if not isinstance(self.files, list):
                logger.warning(
                    "Files is not a list",
                    files_type=type(self.files),
                    commit_hash=self.hash,
                )
                self.files = []

            # Limit number of files to prevent memory issues
            if len(self.files) > MAX_FILES_PER_COMMIT:
                logger.warning(
                    "Too many files in commit, truncating",
                    original_count=len(self.files),
                    commit_hash=self.hash,
                )
                self.files = self.files[:MAX_FILES_PER_COMMIT]

            # Validate each file path
            validated_files = []
            for file_path in self.files:
                if not isinstance(file_path, str):
                    file_path = str(file_path)

                if validate_file_path(file_path, MAX_FILE_PATH_LENGTH):
                    sanitized_path = _sanitize_string(file_path, MAX_FILE_PATH_LENGTH)
                    validated_files.append(sanitized_path)
                else:
                    logger.debug(
                        "Invalid file path excluded",
                        file_path=file_path,
                        commit_hash=self.hash,
                    )

            self.files = validated_files

            # Validate parent hashes
            if not isinstance(self.parent_hashes, list):
                logger.warning(
                    "Parent hashes is not a list",
                    parent_hashes_type=type(self.parent_hashes),
                    commit_hash=self.hash,
                )
                self.parent_hashes = []

            validated_parents = []
            for parent_hash in self.parent_hashes:
                if isinstance(parent_hash, str) and validate_commit_hash(parent_hash):
                    validated_parents.append(parent_hash)
                else:
                    logger.debug(
                        "Invalid parent hash excluded",
                        parent_hash=parent_hash,
                        commit_hash=self.hash,
                    )

            self.parent_hashes = validated_parents

            logger.debug("CommitEvent validation completed", commit_hash=self.hash)

        except Exception as e:
            logger.error(
                "CommitEvent validation failed",
                commit_hash=getattr(self, "hash", "unknown"),
                error=str(e),
            )
            raise

    @classmethod
    def from_dict(cls, data: dict) -> "CommitEvent":
        """Create CommitEvent from dictionary with validation.

        Args:
            data: Dictionary containing commit data

        Returns:
            Validated CommitEvent instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Sanitize input data
            sanitized_data = sanitize_git_data(data)

            # Extract required fields
            commit_hash = sanitized_data.get("hash", "")
            message = sanitized_data.get("message", "")
            author_name = sanitized_data.get("author_name", "")
            author_email = sanitized_data.get("author_email", "")
            timestamp = sanitized_data.get("timestamp")
            files = sanitized_data.get("files", [])
            parent_hashes = sanitized_data.get("parent_hashes", [])

            # Validate required fields
            if not commit_hash:
                raise ValueError("Commit hash is required")

            # Handle timestamp conversion
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            elif not isinstance(timestamp, datetime):
                timestamp = datetime.now()

            return cls(
                hash=commit_hash,
                message=message,
                author_name=author_name,
                author_email=author_email,
                timestamp=timestamp,
                files=files,
                parent_hashes=parent_hashes,
            )

        except Exception as e:
            logger.error(
                "Failed to create CommitEvent from dict", data=data, error=str(e)
            )
            raise


@dataclass
class FileChangeEvent:
    """Represents a file change event with security validation.

    Tracks individual file changes within commits, ensuring all
    paths and metadata are properly validated.

    Attributes:
        file_path: Path to the changed file (validated)
        change_type: Type of change (A/M/D/R/C/T/U/X/B)
        commit_hash: Associated commit hash (validated)
        lines_added: Number of lines added (non-negative)
        lines_deleted: Number of lines deleted (non-negative)
    """

    file_path: Any
    change_type: Any
    commit_hash: Any
    lines_added: Any = 0
    lines_deleted: Any = 0

    def __post_init__(self) -> None:
        """Validate and sanitize all fields after initialization."""
        self._validate_and_sanitize()

    def _validate_and_sanitize(self) -> None:
        """Comprehensive validation and sanitization of all fields."""
        try:
            # Validate and sanitize file path
            if not isinstance(self.file_path, str):
                self.file_path = str(self.file_path)

            if not validate_file_path(self.file_path, MAX_FILE_PATH_LENGTH):
                logger.warning("Invalid file path", file_path=self.file_path)
                raise ValueError(f"Invalid file path: {self.file_path}")

            self.file_path = _sanitize_string(self.file_path, MAX_FILE_PATH_LENGTH)

            # Validate change type
            if not isinstance(self.change_type, str):
                self.change_type = str(self.change_type)

            self.change_type = self.change_type.upper().strip()

            if self.change_type not in VALID_CHANGE_TYPES:
                logger.warning("Invalid change type", change_type=self.change_type)
                raise ValueError(f"Invalid change type: {self.change_type}")

            # Validate commit hash
            if not validate_commit_hash(self.commit_hash):
                logger.warning(
                    "Invalid commit hash in FileChangeEvent", hash=self.commit_hash
                )
                raise ValueError(f"Invalid commit hash: {self.commit_hash}")

            # Validate line counts
            if not isinstance(self.lines_added, int) or self.lines_added < 0:
                logger.debug("Invalid lines_added", lines_added=self.lines_added)
                raise ValueError("Lines added must be non-negative")

            if not isinstance(self.lines_deleted, int) or self.lines_deleted < 0:
                logger.debug(
                    "Invalid lines_deleted",
                    lines_deleted=self.lines_deleted,
                )
                raise ValueError("Lines deleted must be non-negative")

            # Sanity check: prevent extremely large values
            if self.lines_added > 1000000:
                logger.warning(
                    "Extremely large lines_added value", lines_added=self.lines_added
                )
                self.lines_added = 1000000

            if self.lines_deleted > 1000000:
                logger.warning(
                    "Extremely large lines_deleted value",
                    lines_deleted=self.lines_deleted,
                )
                self.lines_deleted = 1000000

            logger.debug(
                "FileChangeEvent validation completed", file_path=self.file_path
            )

        except Exception as e:
            logger.error(
                "FileChangeEvent validation failed",
                file_path=getattr(self, "file_path", "unknown"),
                error=str(e),
            )
            raise

    @classmethod
    def from_dict(cls, data: dict) -> "FileChangeEvent":
        """Create FileChangeEvent from dictionary with validation.

        Args:
            data: Dictionary containing file change data

        Returns:
            Validated FileChangeEvent instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Sanitize input data
            sanitized_data = sanitize_git_data(data)

            # Extract required fields
            file_path = sanitized_data.get("file_path", "")
            change_type = sanitized_data.get("change_type", "M")
            commit_hash = sanitized_data.get("commit_hash", "")
            lines_added = sanitized_data.get("lines_added", 0)
            lines_deleted = sanitized_data.get("lines_deleted", 0)

            # Validate required fields
            if not file_path:
                raise ValueError("File path is required")

            if not commit_hash:
                raise ValueError("Commit hash is required")

            return cls(
                file_path=file_path,
                change_type=change_type,
                commit_hash=commit_hash,
                lines_added=lines_added,
                lines_deleted=lines_deleted,
            )

        except Exception as e:
            logger.error(
                "Failed to create FileChangeEvent from dict", data=data, error=str(e)
            )
            raise


@dataclass
class ProblemCommit:
    """Represents a commit that fixes a problem with security validation.

    Tracks commits that solve issues, with validation to ensure all
    data is safe for analysis and storage.

    Attributes:
        commit_hash: Git commit hash (validated)
        problem_type: Type of problem being fixed
        affected_files: List of files modified in the fix (validated paths)
        fix_description: Description of the fix (sanitized)
        confidence_score: Confidence that this is a problem fix (0.0-1.0)
    """

    commit_hash: Any
    problem_type: Any
    affected_files: Any
    fix_description: Any
    confidence_score: Any = 0.0

    def __post_init__(self) -> None:
        """Validate and sanitize all fields after initialization."""
        self._validate_and_sanitize()

    def _validate_and_sanitize(self) -> None:
        """Comprehensive validation and sanitization of all fields."""
        try:
            # Validate commit hash
            if not validate_commit_hash(self.commit_hash):
                logger.warning(
                    "Invalid commit hash in ProblemCommit", hash=self.commit_hash
                )
                raise ValueError(f"Invalid commit hash: {self.commit_hash}")

            # Validate and sanitize problem type
            if not isinstance(self.problem_type, str):
                self.problem_type = str(self.problem_type)

            self.problem_type = _sanitize_string(self.problem_type, 255)

            if not self.problem_type:
                raise ValueError("Problem type cannot be empty")

            # Sanitize fix description
            if not isinstance(self.fix_description, str):
                self.fix_description = str(self.fix_description)

            if len(self.fix_description) > MAX_COMMIT_MESSAGE_LENGTH:
                logger.warning(
                    "Fix description truncated in ProblemCommit",
                    original_length=len(self.fix_description),
                    commit_hash=self.commit_hash,
                )
                self.fix_description = (
                    self.fix_description[:MAX_COMMIT_MESSAGE_LENGTH] + "..."
                )

            self.fix_description = _sanitize_string(
                self.fix_description, MAX_COMMIT_MESSAGE_LENGTH
            )

            # Validate and sanitize file paths
            if not isinstance(self.affected_files, list):
                logger.warning(
                    "Affected files is not a list in ProblemCommit",
                    files_type=type(self.affected_files),
                    commit_hash=self.commit_hash,
                )
                self.affected_files = []

            # Limit number of files
            if len(self.affected_files) > MAX_FILES_PER_COMMIT:
                logger.warning(
                    "Too many files in ProblemCommit, truncating",
                    original_count=len(self.affected_files),
                    commit_hash=self.commit_hash,
                )
                self.affected_files = self.affected_files[:MAX_FILES_PER_COMMIT]

            # Validate each file path
            validated_files = []
            for file_path in self.affected_files:
                if not isinstance(file_path, str):
                    file_path = str(file_path)

                if validate_file_path(file_path, MAX_FILE_PATH_LENGTH):
                    sanitized_path = _sanitize_string(file_path, MAX_FILE_PATH_LENGTH)
                    validated_files.append(sanitized_path)
                else:
                    logger.debug(
                        "Invalid file path excluded from ProblemCommit",
                        file_path=file_path,
                        commit_hash=self.commit_hash,
                    )

            self.affected_files = validated_files

            # Validate confidence score
            if (
                not isinstance(self.confidence_score, int | float)
                or self.confidence_score is None
            ):
                logger.debug(
                    "Invalid confidence score type",
                    score_type=type(self.confidence_score),
                    commit_hash=self.commit_hash,
                )
                raise ValueError("Confidence score must be between 0.0 and 1.0")
            else:
                # Ensure confidence is between 0.0 and 1.0
                if not (0.0 <= self.confidence_score <= 1.0):
                    raise ValueError("Confidence score must be between 0.0 and 1.0")
                self.confidence_score = float(self.confidence_score)

            logger.debug(
                "ProblemCommit validation completed", commit_hash=self.commit_hash
            )

        except Exception as e:
            logger.error(
                "ProblemCommit validation failed",
                commit_hash=getattr(self, "commit_hash", "unknown"),
                error=str(e),
            )
            raise

    @classmethod
    def from_dict(cls, data: dict) -> "ProblemCommit":
        """Create ProblemCommit from dictionary with validation.

        Args:
            data: Dictionary containing problem commit data

        Returns:
            Validated ProblemCommit instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Sanitize input data
            sanitized_data = sanitize_git_data(data)

            # Extract required fields
            commit_hash = sanitized_data.get(
                "commit_hash", sanitized_data.get("hash", "")
            )
            problem_type = sanitized_data.get("problem_type", "unknown")
            affected_files = sanitized_data.get(
                "affected_files", sanitized_data.get("files", [])
            )
            fix_description = sanitized_data.get(
                "fix_description", sanitized_data.get("message", "")
            )
            confidence_score = sanitized_data.get("confidence_score", 0.0)

            # Validate required fields
            if not commit_hash:
                raise ValueError("Commit hash is required")

            return cls(
                commit_hash=commit_hash,
                problem_type=problem_type,
                affected_files=affected_files,
                fix_description=fix_description,
                confidence_score=confidence_score,
            )

        except Exception as e:
            logger.error(
                "Failed to create ProblemCommit from dict", data=data, error=str(e)
            )
            raise


def validate_git_data_structure(data: Any, structure_type: str) -> bool:
    """Validate git data structure before creating objects.

    Args:
        data: Dictionary containing git data
        structure_type: Type of structure ('commit', 'file_change', 'problem_commit')

    Returns:
        True if data structure is valid for the specified type
    """
    try:
        if not isinstance(data, dict):
            logger.warning("Data is not a dictionary", data_type=type(data))
            return False

        # Check for required fields based on structure type
        if structure_type == "commit":
            required_fields = ["hash", "message", "author_name", "timestamp"]
        elif structure_type == "file_change":
            required_fields = ["file_path", "change_type", "commit_hash"]
        elif structure_type == "problem_commit":
            required_fields = ["hash", "message", "files"]
        else:
            logger.warning("Unknown structure type", structure_type=structure_type)
            return False

        # Check if all required fields are present
        for field in required_fields:
            if field not in data:
                logger.debug(
                    "Missing required field", field=field, structure_type=structure_type
                )
                return False

        return True

    except Exception as e:
        logger.error(
            "Git data structure validation failed",
            structure_type=structure_type,
            error=str(e),
        )
        return False
