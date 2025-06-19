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


@dataclass
class CoChangePattern:
    """Represents a co-change pattern with security validation.

    Tracks files that frequently change together with statistical
    confidence scoring and quality assessment.

    Attributes:
        file_a: First file in the co-change relationship (validated path)
        file_b: Second file in the co-change relationship (validated path)
        support_count: Number of times files changed together
        confidence_score: Statistical confidence score (0.0-1.0)
        recency_weight: Temporal relevance weight (0.0-1.0)
        quality_rating: Quality assessment (high/medium/low/very_low)
    """

    file_a: Any
    file_b: Any
    support_count: Any
    confidence_score: Any
    recency_weight: Any
    quality_rating: Any

    def __post_init__(self) -> None:
        """Validate and sanitize all fields after initialization."""
        self._validate_and_sanitize()

    def _validate_and_sanitize(self) -> None:
        """Comprehensive validation and sanitization of all fields."""
        try:
            # Validate and sanitize file paths
            if not isinstance(self.file_a, str):
                self.file_a = str(self.file_a)

            if not validate_file_path(self.file_a, MAX_FILE_PATH_LENGTH):
                logger.warning("Invalid file_a path", file_path=self.file_a)
                raise ValueError(f"Invalid file_a path: {self.file_a}")

            self.file_a = _sanitize_string(self.file_a, MAX_FILE_PATH_LENGTH)

            if not isinstance(self.file_b, str):
                self.file_b = str(self.file_b)

            if not validate_file_path(self.file_b, MAX_FILE_PATH_LENGTH):
                logger.warning("Invalid file_b path", file_path=self.file_b)
                raise ValueError(f"Invalid file_b path: {self.file_b}")

            self.file_b = _sanitize_string(self.file_b, MAX_FILE_PATH_LENGTH)

            # Validate support count
            if not isinstance(self.support_count, int) or self.support_count < 0:
                logger.warning(
                    "Invalid support_count", support_count=self.support_count
                )
                raise ValueError("Support count must be non-negative integer")

            # Validate confidence score
            if not isinstance(self.confidence_score, int | float) or not (
                0.0 <= self.confidence_score <= 1.0
            ):
                logger.warning(
                    "Invalid confidence_score", confidence_score=self.confidence_score
                )
                raise ValueError("Confidence score must be between 0.0 and 1.0")

            self.confidence_score = float(self.confidence_score)

            # Validate recency weight
            if not isinstance(self.recency_weight, int | float) or not (
                0.0 <= self.recency_weight <= 1.0
            ):
                logger.warning(
                    "Invalid recency_weight", recency_weight=self.recency_weight
                )
                raise ValueError("Recency weight must be between 0.0 and 1.0")

            self.recency_weight = float(self.recency_weight)

            # Validate quality rating
            valid_ratings = {"high", "medium", "low", "very_low"}
            if not isinstance(self.quality_rating, str):
                self.quality_rating = str(self.quality_rating)

            self.quality_rating = self.quality_rating.lower().strip()

            if self.quality_rating not in valid_ratings:
                logger.warning(
                    "Invalid quality_rating", quality_rating=self.quality_rating
                )
                raise ValueError(f"Quality rating must be one of: {valid_ratings}")

            logger.debug(
                "CoChangePattern validation completed",
                file_a=self.file_a,
                file_b=self.file_b,
            )

        except Exception as e:
            logger.error(
                "CoChangePattern validation failed",
                file_a=getattr(self, "file_a", "unknown"),
                file_b=getattr(self, "file_b", "unknown"),
                error=str(e),
            )
            raise

    @classmethod
    def from_dict(cls, data: dict) -> "CoChangePattern":
        """Create CoChangePattern from dictionary with validation.

        Args:
            data: Dictionary containing co-change pattern data

        Returns:
            Validated CoChangePattern instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Sanitize input data
            sanitized_data = sanitize_git_data(data)

            # Extract required fields
            file_a = sanitized_data.get("file_a", "")
            file_b = sanitized_data.get("file_b", "")
            support_count = sanitized_data.get("support_count", 0)
            confidence_score = sanitized_data.get("confidence_score", 0.0)
            recency_weight = sanitized_data.get("recency_weight", 0.0)
            quality_rating = sanitized_data.get("quality_rating", "low")

            # Validate required fields
            if not file_a:
                raise ValueError("file_a is required")
            if not file_b:
                raise ValueError("file_b is required")

            return cls(
                file_a=file_a,
                file_b=file_b,
                support_count=support_count,
                confidence_score=confidence_score,
                recency_weight=recency_weight,
                quality_rating=quality_rating,
            )

        except Exception as e:
            logger.error(
                "Failed to create CoChangePattern from dict", data=data, error=str(e)
            )
            raise


@dataclass
class MaintenanceHotspot:
    """Represents a maintenance hotspot with security validation.

    Tracks files with high problem frequency and maintenance risk
    with trend analysis and quality assessment.

    Attributes:
        file_path: Path to the hotspot file (validated)
        problem_frequency: Number of problems encountered
        hotspot_score: Calculated hotspot risk score (0.0-1.0)
        trend_direction: Trend direction (increasing/decreasing/stable)
        recent_problems: List of recent problem types
    """

    file_path: Any
    problem_frequency: Any
    hotspot_score: Any
    trend_direction: Any
    recent_problems: Any

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
                logger.warning("Invalid file_path", file_path=self.file_path)
                raise ValueError(f"Invalid file_path: {self.file_path}")

            self.file_path = _sanitize_string(self.file_path, MAX_FILE_PATH_LENGTH)

            # Validate problem frequency
            if (
                not isinstance(self.problem_frequency, int)
                or self.problem_frequency < 0
            ):
                logger.warning(
                    "Invalid problem_frequency",
                    problem_frequency=self.problem_frequency,
                )
                raise ValueError("Problem frequency must be non-negative integer")

            # Validate hotspot score
            if not isinstance(self.hotspot_score, int | float) or not (
                0.0 <= self.hotspot_score <= 1.0
            ):
                logger.warning(
                    "Invalid hotspot_score", hotspot_score=self.hotspot_score
                )
                raise ValueError("Hotspot score must be between 0.0 and 1.0")

            self.hotspot_score = float(self.hotspot_score)

            # Validate trend direction
            valid_trends = {"increasing", "decreasing", "stable", "unknown"}
            if not isinstance(self.trend_direction, str):
                self.trend_direction = str(self.trend_direction)

            self.trend_direction = self.trend_direction.lower().strip()

            if self.trend_direction not in valid_trends:
                logger.warning(
                    "Invalid trend_direction", trend_direction=self.trend_direction
                )
                raise ValueError(f"Trend direction must be one of: {valid_trends}")

            # Validate and sanitize recent problems list
            if not isinstance(self.recent_problems, list):
                logger.warning(
                    "Recent problems is not a list",
                    problems_type=type(self.recent_problems),
                    file_path=self.file_path,
                )
                self.recent_problems = []

            # Limit number of recent problems
            if len(self.recent_problems) > 20:
                logger.warning(
                    "Too many recent problems, truncating",
                    original_count=len(self.recent_problems),
                    file_path=self.file_path,
                )
                self.recent_problems = self.recent_problems[:20]

            # Validate each problem type
            validated_problems = []
            for problem in self.recent_problems:
                if not isinstance(problem, str):
                    problem = str(problem)

                sanitized_problem = _sanitize_string(problem, 255)
                if sanitized_problem:
                    validated_problems.append(sanitized_problem)

            self.recent_problems = validated_problems

            logger.debug(
                "MaintenanceHotspot validation completed", file_path=self.file_path
            )

        except Exception as e:
            logger.error(
                "MaintenanceHotspot validation failed",
                file_path=getattr(self, "file_path", "unknown"),
                error=str(e),
            )
            raise

    @classmethod
    def from_dict(cls, data: dict) -> "MaintenanceHotspot":
        """Create MaintenanceHotspot from dictionary with validation.

        Args:
            data: Dictionary containing hotspot data

        Returns:
            Validated MaintenanceHotspot instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Sanitize input data
            sanitized_data = sanitize_git_data(data)

            # Extract required fields
            file_path = sanitized_data.get("file_path", "")
            problem_frequency = sanitized_data.get("problem_frequency", 0)
            hotspot_score = sanitized_data.get("hotspot_score", 0.0)
            trend_direction = sanitized_data.get("trend_direction", "unknown")
            recent_problems = sanitized_data.get("recent_problems", [])

            # Validate required fields
            if not file_path:
                raise ValueError("file_path is required")

            return cls(
                file_path=file_path,
                problem_frequency=problem_frequency,
                hotspot_score=hotspot_score,
                trend_direction=trend_direction,
                recent_problems=recent_problems,
            )

        except Exception as e:
            logger.error(
                "Failed to create MaintenanceHotspot from dict", data=data, error=str(e)
            )
            raise


@dataclass
class SolutionPattern:
    """Represents a solution pattern with security validation.

    Tracks successful problem-solving approaches with statistical
    success rate calculation and applicability confidence.

    Attributes:
        problem_type: Type of problem being solved (validated)
        solution_approach: Approach used for solving (validated)
        success_rate: Success rate of this approach (0.0-1.0)
        applicability_confidence: Confidence in pattern applicability (0.0-1.0)
        example_fixes: List of example commit hashes (validated)
    """

    problem_type: Any
    solution_approach: Any
    success_rate: Any
    applicability_confidence: Any
    example_fixes: Any

    def __post_init__(self) -> None:
        """Validate and sanitize all fields after initialization."""
        self._validate_and_sanitize()

    def _validate_and_sanitize(self) -> None:
        """Comprehensive validation and sanitization of all fields."""
        try:
            # Validate and sanitize problem type
            if not isinstance(self.problem_type, str):
                self.problem_type = str(self.problem_type)

            self.problem_type = _sanitize_string(self.problem_type, 255)

            if not self.problem_type:
                raise ValueError("Problem type cannot be empty")

            # Validate and sanitize solution approach
            if not isinstance(self.solution_approach, str):
                self.solution_approach = str(self.solution_approach)

            self.solution_approach = _sanitize_string(self.solution_approach, 255)

            if not self.solution_approach:
                raise ValueError("Solution approach cannot be empty")

            # Validate success rate
            if not isinstance(self.success_rate, int | float) or not (
                0.0 <= self.success_rate <= 1.0
            ):
                logger.warning("Invalid success_rate", success_rate=self.success_rate)
                raise ValueError("Success rate must be between 0.0 and 1.0")

            self.success_rate = float(self.success_rate)

            # Validate applicability confidence
            if not isinstance(self.applicability_confidence, int | float) or not (
                0.0 <= self.applicability_confidence <= 1.0
            ):
                logger.warning(
                    "Invalid applicability_confidence",
                    confidence=self.applicability_confidence,
                )
                raise ValueError("Applicability confidence must be between 0.0 and 1.0")

            self.applicability_confidence = float(self.applicability_confidence)

            # Validate and sanitize example fixes
            if not isinstance(self.example_fixes, list):
                logger.warning(
                    "Example fixes is not a list",
                    fixes_type=type(self.example_fixes),
                    problem_type=self.problem_type,
                )
                self.example_fixes = []

            # Limit number of examples
            if len(self.example_fixes) > 50:
                logger.warning(
                    "Too many example fixes, truncating",
                    original_count=len(self.example_fixes),
                    problem_type=self.problem_type,
                )
                self.example_fixes = self.example_fixes[:50]

            # Validate each commit hash
            validated_fixes = []
            for fix_hash in self.example_fixes:
                if isinstance(fix_hash, str) and validate_commit_hash(fix_hash):
                    validated_fixes.append(fix_hash)
                else:
                    logger.debug(
                        "Invalid commit hash excluded from example fixes",
                        commit_hash=fix_hash,
                        problem_type=self.problem_type,
                    )

            self.example_fixes = validated_fixes

            logger.debug(
                "SolutionPattern validation completed", problem_type=self.problem_type
            )

        except Exception as e:
            logger.error(
                "SolutionPattern validation failed",
                problem_type=getattr(self, "problem_type", "unknown"),
                error=str(e),
            )
            raise

    @classmethod
    def from_dict(cls, data: dict) -> "SolutionPattern":
        """Create SolutionPattern from dictionary with validation.

        Args:
            data: Dictionary containing solution pattern data

        Returns:
            Validated SolutionPattern instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            # Sanitize input data
            sanitized_data = sanitize_git_data(data)

            # Extract required fields
            problem_type = sanitized_data.get("problem_type", "")
            solution_approach = sanitized_data.get("solution_approach", "")
            success_rate = sanitized_data.get("success_rate", 0.0)
            applicability_confidence = sanitized_data.get(
                "applicability_confidence", 0.0
            )
            example_fixes = sanitized_data.get("example_fixes", [])

            # Validate required fields
            if not problem_type:
                raise ValueError("problem_type is required")
            if not solution_approach:
                raise ValueError("solution_approach is required")

            return cls(
                problem_type=problem_type,
                solution_approach=solution_approach,
                success_rate=success_rate,
                applicability_confidence=applicability_confidence,
                example_fixes=example_fixes,
            )

        except Exception as e:
            logger.error(
                "Failed to create SolutionPattern from dict", data=data, error=str(e)
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
        elif structure_type == "cochange_pattern":
            required_fields = ["file_a", "file_b", "support_count", "confidence_score"]
        elif structure_type == "maintenance_hotspot":
            required_fields = ["file_path", "problem_frequency", "hotspot_score"]
        elif structure_type == "solution_pattern":
            required_fields = ["problem_type", "solution_approach", "success_rate"]
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
