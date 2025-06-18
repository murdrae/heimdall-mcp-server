"""Secure git history mining with GitPython integration.

This module provides secure git repository analysis using GitPython library
exclusively. All operations are performed without shell command execution,
implementing comprehensive security controls and error handling.

Security Features:
- No shell command execution (GitPython API only)
- Repository path validation before access
- Comprehensive error handling and logging
- Resource cleanup and connection management
- Input validation for all git data
"""

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from git import GitCommandError, InvalidGitRepositoryError, Repo
    from git.objects import Commit

    GITPYTHON_AVAILABLE = True
except ImportError:
    GITPYTHON_AVAILABLE = False
    Repo = type(None)
    Commit = type(None)
    InvalidGitRepositoryError = Exception
    GitCommandError = Exception

from loguru import logger

from .data_structures import CommitEvent, FileChangeEvent, ProblemCommit
from .security import (
    validate_repository_path,
)


class GitHistoryMiner:
    """Secure git history mining with comprehensive security controls.

    This class provides safe git repository analysis using GitPython
    exclusively, with no shell command execution and comprehensive
    security validation.

    Security Features:
    - Repository path validation before access
    - GitPython API only (no subprocess/shell)
    - Comprehensive error handling
    - Resource cleanup and connection management
    - Input sanitization for all git data
    """

    def __init__(self, repository_path: str):
        """Initialize git history miner with security validation.

        Args:
            repository_path: Path to git repository

        Raises:
            ImportError: If GitPython is not available
            ValueError: If repository path is invalid or insecure
            InvalidGitRepositoryError: If path is not a valid git repository
        """
        if not GITPYTHON_AVAILABLE:
            logger.error("GitPython library not available")
            raise ImportError("GitPython library is required but not installed")

        # Validate repository path for security
        if not validate_repository_path(repository_path):
            logger.error("Repository path validation failed", path=repository_path)
            raise ValueError(f"Invalid or insecure repository path: {repository_path}")

        self.repository_path = Path(repository_path).resolve()
        self.repo: Repo | None = None

        # Initialize repository connection
        try:
            self.repo = Repo(str(self.repository_path))
            logger.info(
                "Git repository initialized successfully",
                path=str(self.repository_path),
            )
        except InvalidGitRepositoryError as e:
            logger.error(
                "Invalid git repository", path=str(self.repository_path), error=str(e)
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to initialize git repository",
                path=str(self.repository_path),
                error=str(e),
            )
            raise

    def __enter__(self) -> "GitHistoryMiner":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit with cleanup."""
        self.close()

    def close(self) -> None:
        """Clean up resources."""
        if self.repo:
            try:
                self.repo.close()
                logger.debug("Git repository connection closed")
            except Exception as e:
                logger.warning("Error closing git repository", error=str(e))
            finally:
                self.repo = None

    def validate_repository(self) -> bool:
        """Validate repository access and structure.

        Returns:
            True if repository is valid and accessible
        """
        try:
            if not self.repo:
                logger.warning("Repository not initialized")
                return False

            # Check if repository has commits
            try:
                if self.repo is None:
                    return False
                list(self.repo.iter_commits(max_count=1))
            except Exception:
                logger.warning("Repository has no commits or is corrupted")
                return False

            # Check if we can access the HEAD
            try:
                if self.repo is None:
                    return False
                _ = self.repo.head.commit
            except Exception:
                logger.warning("Cannot access repository HEAD")
                return False

            logger.debug("Repository validation successful")
            return True

        except Exception as e:
            logger.error("Repository validation failed", error=str(e))
            return False

    def extract_commit_history(
        self,
        max_commits: int = 1000,
        since_date: datetime | None = None,
        until_date: datetime | None = None,
        branch: str | None = None,
    ) -> Iterator[CommitEvent]:
        """Extract commit history with security controls.

        Args:
            max_commits: Maximum number of commits to extract (security limit)
            since_date: Extract commits since this date
            until_date: Extract commits until this date
            branch: Branch to extract from (defaults to current branch)

        Yields:
            CommitEvent: Validated commit events

        Raises:
            ValueError: If repository is not valid
            GitCommandError: If git operations fail
        """
        if not self.validate_repository():
            raise ValueError("Repository validation failed")

        try:
            # Security: limit max_commits to prevent memory exhaustion
            if max_commits > 10000:
                logger.warning(
                    "Max commits limited to 10000 for security", requested=max_commits
                )
                max_commits = 10000

            # Build commit iteration parameters
            kwargs: dict[str, Any] = {"max_count": max_commits}

            if since_date:
                kwargs["since"] = since_date

            if until_date:
                kwargs["until"] = until_date

            if branch:
                kwargs["rev"] = branch

            logger.info(
                "Starting commit history extraction",
                max_commits=max_commits,
                since_date=since_date,
                until_date=until_date,
                branch=branch,
            )

            commit_count = 0

            # Extract commits using GitPython API
            if self.repo is None:
                raise ValueError("Repository not initialized")
            for commit in self.repo.iter_commits(**kwargs):
                try:
                    commit_event = self._convert_commit_to_event(commit)
                    if commit_event:
                        yield commit_event
                        commit_count += 1

                        # Log progress periodically
                        if commit_count % 100 == 0:
                            logger.debug("Processed commits", count=commit_count)

                except Exception as e:
                    logger.warning(
                        "Failed to process commit",
                        commit_hash=commit.hexsha,
                        error=str(e),
                    )
                    continue

            logger.info(
                "Commit history extraction completed", total_commits=commit_count
            )

        except GitCommandError as e:
            logger.error("Git command failed during history extraction", error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during history extraction", error=str(e))
            raise

    def _convert_commit_to_event(self, commit: Commit) -> CommitEvent | None:
        """Convert GitPython commit to CommitEvent with validation.

        Args:
            commit: GitPython commit object

        Returns:
            Validated CommitEvent or None if conversion fails
        """
        try:
            # Extract basic commit information
            commit_hash = commit.hexsha
            message = commit.message.strip()
            author_name = commit.author.name
            author_email = commit.author.email
            timestamp = datetime.fromtimestamp(commit.committed_date)

            # Extract parent hashes
            parent_hashes = [parent.hexsha for parent in commit.parents]

            # Extract changed files
            files = []
            try:
                # Get changed files from commit
                if commit.parents:
                    # Compare with first parent for changed files
                    diffs = commit.parents[0].diff(commit)
                    for diff in diffs:
                        if diff.a_path:
                            files.append(diff.a_path)
                        if diff.b_path and diff.b_path != diff.a_path:
                            files.append(diff.b_path)
                else:
                    # Initial commit - get all files
                    for item in commit.tree.traverse():
                        if item.type == "blob":  # Only include files, not directories
                            files.append(item.path)
            except Exception as e:
                logger.debug(
                    "Failed to extract changed files",
                    commit_hash=commit_hash,
                    error=str(e),
                )
                files = []

            # Create and validate commit event
            commit_data = {
                "hash": commit_hash,
                "message": message,
                "author_name": author_name,
                "author_email": author_email,
                "timestamp": timestamp,
                "files": files,
                "parent_hashes": parent_hashes,
            }

            return CommitEvent.from_dict(commit_data)

        except Exception as e:
            logger.warning(
                "Failed to convert commit to event",
                commit_hash=getattr(commit, "hexsha", "unknown"),
                error=str(e),
            )
            return None

    def extract_file_changes(
        self, max_commits: int = 1000, since_date: datetime | None = None
    ) -> Iterator[FileChangeEvent]:
        """Extract file change events with security controls.

        Args:
            max_commits: Maximum number of commits to analyze
            since_date: Extract changes since this date

        Yields:
            FileChangeEvent: Validated file change events
        """
        if not self.validate_repository():
            raise ValueError("Repository validation failed")

        try:
            # Security: limit max_commits
            if max_commits > 10000:
                logger.warning(
                    "Max commits limited to 10000 for security", requested=max_commits
                )
                max_commits = 10000

            kwargs: dict[str, Any] = {"max_count": max_commits}
            if since_date:
                kwargs["since"] = since_date

            logger.info(
                "Starting file change extraction",
                max_commits=max_commits,
                since_date=since_date,
            )

            change_count = 0

            if self.repo is None:
                raise ValueError("Repository not initialized")
            for commit in self.repo.iter_commits(**kwargs):
                try:
                    # Extract file changes from commit
                    for file_change in self._extract_file_changes_from_commit(commit):
                        yield file_change
                        change_count += 1

                        # Log progress periodically
                        if change_count % 500 == 0:
                            logger.debug("Processed file changes", count=change_count)

                except Exception as e:
                    logger.warning(
                        "Failed to extract file changes from commit",
                        commit_hash=commit.hexsha,
                        error=str(e),
                    )
                    continue

            logger.info("File change extraction completed", total_changes=change_count)

        except Exception as e:
            logger.error("Unexpected error during file change extraction", error=str(e))
            raise

    def _extract_file_changes_from_commit(
        self, commit: Commit
    ) -> list[FileChangeEvent]:
        """Extract file changes from a single commit.

        Args:
            commit: GitPython commit object

        Returns:
            List of validated FileChangeEvent objects
        """
        file_changes = []

        try:
            commit_hash = commit.hexsha

            if commit.parents:
                # Compare with first parent
                diffs = commit.parents[0].diff(commit)

                for diff in diffs:
                    try:
                        # Determine change type and file path
                        if diff.new_file:
                            change_type = "A"  # Added
                            file_path = diff.b_path
                        elif diff.deleted_file:
                            change_type = "D"  # Deleted
                            file_path = diff.a_path
                        elif diff.renamed_file:
                            change_type = "R"  # Renamed
                            file_path = diff.b_path
                        else:
                            change_type = "M"  # Modified
                            file_path = diff.a_path or diff.b_path

                        if not file_path:
                            continue

                        # Calculate line changes
                        lines_added = 0
                        lines_deleted = 0

                        try:
                            if hasattr(diff, "diff") and diff.diff:
                                diff_text = diff.diff.decode("utf-8", errors="ignore")
                                for line in diff_text.split("\n"):
                                    if line.startswith("+") and not line.startswith(
                                        "+++"
                                    ):
                                        lines_added += 1
                                    elif line.startswith("-") and not line.startswith(
                                        "---"
                                    ):
                                        lines_deleted += 1
                        except Exception:
                            # If diff parsing fails, use safe defaults
                            pass

                        # Create file change event
                        change_data = {
                            "file_path": file_path,
                            "change_type": change_type,
                            "commit_hash": commit_hash,
                            "lines_added": lines_added,
                            "lines_deleted": lines_deleted,
                        }

                        file_change = FileChangeEvent.from_dict(change_data)
                        file_changes.append(file_change)

                    except Exception as e:
                        logger.debug(
                            "Failed to process diff",
                            commit_hash=commit_hash,
                            error=str(e),
                        )
                        continue
            else:
                # Initial commit - all files are added
                for item in commit.tree.traverse():
                    if item.type == "blob":  # Only files
                        try:
                            change_data = {
                                "file_path": item.path,
                                "change_type": "A",
                                "commit_hash": commit_hash,
                                "lines_added": 0,
                                "lines_deleted": 0,
                            }

                            file_change = FileChangeEvent.from_dict(change_data)
                            file_changes.append(file_change)

                        except Exception as e:
                            logger.debug(
                                "Failed to process initial commit file",
                                file_path=item.path,
                                commit_hash=commit_hash,
                                error=str(e),
                            )
                            continue

        except Exception as e:
            logger.warning(
                "Failed to extract file changes from commit",
                commit_hash=getattr(commit, "hexsha", "unknown"),
                error=str(e),
            )

        return file_changes

    def find_problem_commits(
        self, max_commits: int = 1000, problem_keywords: list[str] | None = None
    ) -> Iterator[ProblemCommit]:
        """Find commits that fix problems with security controls.

        Args:
            max_commits: Maximum number of commits to analyze
            problem_keywords: Keywords to search for in commit messages

        Yields:
            ProblemCommit: Validated problem commit events
        """
        if not self.validate_repository():
            raise ValueError("Repository validation failed")

        # Default problem keywords
        if problem_keywords is None:
            problem_keywords = [
                "fix",
                "bug",
                "error",
                "issue",
                "problem",
                "resolve",
                "patch",
                "correct",
                "repair",
                "hotfix",
                "bugfix",
            ]

        try:
            # Security: limit max_commits
            if max_commits > 10000:
                logger.warning(
                    "Max commits limited to 10000 for security", requested=max_commits
                )
                max_commits = 10000

            logger.info(
                "Starting problem commit search",
                max_commits=max_commits,
                keywords_count=len(problem_keywords),
            )

            problem_count = 0

            if self.repo is None:
                raise ValueError("Repository not initialized")
            for commit in self.repo.iter_commits(max_count=max_commits):
                try:
                    problem_commit = self._analyze_commit_for_problems(
                        commit, problem_keywords
                    )
                    if problem_commit:
                        yield problem_commit
                        problem_count += 1

                        # Log progress periodically
                        if problem_count % 50 == 0:
                            logger.debug("Found problem commits", count=problem_count)

                except Exception as e:
                    logger.warning(
                        "Failed to analyze commit for problems",
                        commit_hash=commit.hexsha,
                        error=str(e),
                    )
                    continue

            logger.info("Problem commit search completed", total_found=problem_count)

        except Exception as e:
            logger.error("Unexpected error during problem commit search", error=str(e))
            raise

    def _analyze_commit_for_problems(
        self, commit: Commit, problem_keywords: list[str]
    ) -> ProblemCommit | None:
        """Analyze commit for problem-solving indicators.

        Args:
            commit: GitPython commit object
            problem_keywords: Keywords to search for

        Returns:
            ProblemCommit if commit appears to fix problems, None otherwise
        """
        try:
            commit_hash = commit.hexsha
            message = commit.message.strip().lower()

            # Search for problem keywords in commit message
            found_keywords = []
            for keyword in problem_keywords:
                if keyword.lower() in message:
                    found_keywords.append(keyword)

            # If no keywords found, not a problem commit
            if not found_keywords:
                return None

            # Calculate confidence score based on keyword matches and message patterns
            confidence_score = self._calculate_problem_confidence(
                message, found_keywords
            )

            # Extract changed files
            files = []
            try:
                if commit.parents:
                    diffs = commit.parents[0].diff(commit)
                    for diff in diffs:
                        if diff.a_path:
                            files.append(diff.a_path)
                        if diff.b_path and diff.b_path != diff.a_path:
                            files.append(diff.b_path)
            except Exception as e:
                logger.debug(
                    "Failed to extract changed files for problem commit",
                    commit_hash=commit_hash,
                    error=str(e),
                )

            # Create problem commit
            problem_data = {
                "hash": commit_hash,
                "message": commit.message.strip(),
                "files": files,
                "problem_keywords": found_keywords,
                "confidence_score": confidence_score,
            }

            return ProblemCommit.from_dict(problem_data)

        except Exception as e:
            logger.warning(
                "Failed to analyze commit for problems",
                commit_hash=getattr(commit, "hexsha", "unknown"),
                error=str(e),
            )
            return None

    def _calculate_problem_confidence(
        self, message: str, found_keywords: list[str]
    ) -> float:
        """Calculate confidence that commit fixes a problem.

        Args:
            message: Commit message (lowercase)
            found_keywords: Keywords found in message

        Returns:
            Confidence score between 0.0 and 1.0
        """
        try:
            # Base confidence from keyword matches
            base_confidence = min(len(found_keywords) * 0.2, 0.8)

            # Bonus for specific patterns
            high_confidence_patterns = [
                "fixes #",
                "closes #",
                "resolves #",
                "fix #",
                "critical fix",
                "urgent fix",
                "hotfix",
                "security fix",
                "vulnerability",
            ]

            medium_confidence_patterns = [
                "bug fix",
                "issue fix",
                "error fix",
                "fix for",
                "fixing",
                "resolved",
            ]

            # Check for high confidence patterns
            for pattern in high_confidence_patterns:
                if pattern in message:
                    base_confidence = min(base_confidence + 0.3, 1.0)
                    break

            # Check for medium confidence patterns
            for pattern in medium_confidence_patterns:
                if pattern in message:
                    base_confidence = min(base_confidence + 0.15, 1.0)
                    break

            return base_confidence

        except Exception:
            return 0.5  # Default confidence if calculation fails

    def get_repository_stats(self) -> dict[str, Any]:
        """Get basic repository statistics with security controls.

        Returns:
            Dictionary containing repository statistics
        """
        if not self.validate_repository():
            return {}

        try:
            stats = {
                "repository_path": str(self.repository_path),
                "total_commits": 0,
                "total_branches": 0,
                "total_tags": 0,
                "active_branch": None,
                "last_commit_date": None,
                "first_commit_date": None,
            }

            # Count commits (limited for security)
            try:
                if self.repo is None:
                    raise ValueError("Repository not initialized")
                commits = list(self.repo.iter_commits(max_count=10000))
                stats["total_commits"] = len(commits)

                if commits:
                    stats["last_commit_date"] = datetime.fromtimestamp(
                        commits[0].committed_date
                    )
                    stats["first_commit_date"] = datetime.fromtimestamp(
                        commits[-1].committed_date
                    )
            except Exception as e:
                logger.debug("Failed to count commits", error=str(e))

            # Count branches
            try:
                if self.repo is None:
                    raise ValueError("Repository not initialized")
                stats["total_branches"] = len(list(self.repo.branches))
            except Exception as e:
                logger.debug("Failed to count branches", error=str(e))

            # Count tags
            try:
                if self.repo is None:
                    raise ValueError("Repository not initialized")
                stats["total_tags"] = len(list(self.repo.tags))
            except Exception as e:
                logger.debug("Failed to count tags", error=str(e))

            # Get active branch
            try:
                if self.repo is None:
                    raise ValueError("Repository not initialized")
                stats["active_branch"] = self.repo.active_branch.name
            except Exception as e:
                logger.debug("Failed to get active branch", error=str(e))

            logger.debug("Repository statistics collected", stats=stats)
            return stats

        except Exception as e:
            logger.error("Failed to collect repository statistics", error=str(e))
            return {}


# Utility functions for external use


def create_git_history_miner(repository_path: str) -> GitHistoryMiner:
    """Create a GitHistoryMiner instance with error handling.

    Args:
        repository_path: Path to git repository

    Returns:
        GitHistoryMiner instance

    Raises:
        ImportError: If GitPython is not available
        ValueError: If repository path is invalid
    """
    try:
        return GitHistoryMiner(repository_path)
    except Exception as e:
        logger.error(
            "Failed to create GitHistoryMiner", path=repository_path, error=str(e)
        )
        raise


def validate_git_repository(repository_path: str) -> bool:
    """Validate if path contains a valid git repository.

    Args:
        repository_path: Path to validate

    Returns:
        True if valid git repository, False otherwise
    """
    try:
        with create_git_history_miner(repository_path) as miner:
            return miner.validate_repository()
    except Exception:
        return False
