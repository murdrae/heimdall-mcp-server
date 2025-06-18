"""
Unit tests for git data structures.

Tests validation and sanitization of git data structures including
CommitEvent, FileChangeEvent, and ProblemCommit.
"""

from datetime import datetime

import pytest

from cognitive_memory.git_analysis.data_structures import (
    MAX_AUTHOR_NAME_LENGTH,
    MAX_COMMIT_MESSAGE_LENGTH,
    MAX_FILE_PATH_LENGTH,
    MAX_FILES_PER_COMMIT,
    VALID_CHANGE_TYPES,
    CommitEvent,
    FileChangeEvent,
    ProblemCommit,
)


class TestCommitEvent:
    """Test CommitEvent validation and sanitization."""

    def test_valid_commit_creation(self):
        """Test creation of valid commit event."""
        commit = CommitEvent(
            hash="a" * 40,
            message="Fix security issue",
            author_name="John Doe",
            author_email="john@example.com",
            timestamp=datetime.now(),
            files=["file1.py", "file2.py"],
            parent_hashes=[],
        )

        assert commit.hash == "a" * 40
        assert commit.message == "Fix security issue"
        assert commit.author_name == "John Doe"
        assert commit.author_email == "john@example.com"
        assert len(commit.files) == 2

    def test_invalid_commit_hash_rejected(self):
        """Test that invalid commit hashes are rejected."""
        invalid_hashes = [
            "invalid_hash",
            "a" * 39,  # Too short
            "g" * 40,  # Invalid hex
            "",
            None,
        ]

        for invalid_hash in invalid_hashes:
            with pytest.raises(ValueError, match="Invalid commit hash"):
                CommitEvent(
                    hash=invalid_hash,
                    message="Test message",
                    author_name="John Doe",
                    author_email="john@example.com",
                    timestamp=datetime.now(),
                    files=[],
                    parent_hashes=[],
                )

    def test_commit_message_sanitization(self):
        """Test that commit messages are sanitized."""
        dangerous_message = "<script>alert('xss')</script>Fix bug"

        commit = CommitEvent(
            hash="a" * 40,
            message=dangerous_message,
            author_name="John Doe",
            author_email="john@example.com",
            timestamp=datetime.now(),
            files=[],
            parent_hashes=[],
        )

        assert "script" not in commit.message.lower()
        assert "fix bug" in commit.message.lower()

    def test_commit_message_length_limit(self):
        """Test that commit message length is limited."""
        long_message = "a" * (MAX_COMMIT_MESSAGE_LENGTH + 100)

        commit = CommitEvent(
            hash="a" * 40,
            message=long_message,
            author_name="John Doe",
            author_email="john@example.com",
            timestamp=datetime.now(),
            files=[],
            parent_hashes=[],
        )

        assert len(commit.message) <= MAX_COMMIT_MESSAGE_LENGTH

    def test_author_name_sanitization(self):
        """Test that author names are sanitized."""
        dangerous_name = "John<script>alert('xss')</script>Doe"

        commit = CommitEvent(
            hash="a" * 40,
            message="Test message",
            author_name=dangerous_name,
            author_email="john@example.com",
            timestamp=datetime.now(),
            files=[],
            parent_hashes=[],
        )

        assert "script" not in commit.author_name.lower()
        assert "johndoe" in commit.author_name.lower()

    def test_author_name_length_limit(self):
        """Test that author name length is limited."""
        long_name = "a" * (MAX_AUTHOR_NAME_LENGTH + 10)

        commit = CommitEvent(
            hash="a" * 40,
            message="Test message",
            author_name=long_name,
            author_email="john@example.com",
            timestamp=datetime.now(),
            files=[],
            parent_hashes=[],
        )

        assert len(commit.author_name) <= MAX_AUTHOR_NAME_LENGTH

    def test_author_email_validation(self):
        """Test that author email format is validated."""
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "user@",
            "user@.com",
            "user space@example.com",
            "",
            None,
        ]

        for invalid_email in invalid_emails:
            with pytest.raises(ValueError, match="Invalid author email"):
                CommitEvent(
                    hash="a" * 40,
                    message="Test message",
                    author_name="John Doe",
                    author_email=invalid_email,
                    timestamp=datetime.now(),
                    files=[],
                    parent_hashes=[],
                )

    def test_author_email_sanitization(self):
        """Test that author email is sanitized."""
        email_with_script = "john<script>@example.com"

        commit = CommitEvent(
            hash="a" * 40,
            message="Test message",
            author_name="John Doe",
            author_email=email_with_script,
            timestamp=datetime.now(),
            files=[],
            parent_hashes=[],
        )

        assert "script" not in commit.author_email.lower()
        assert "@example.com" in commit.author_email

    def test_files_validation(self):
        """Test that files changed list is validated."""
        valid_files = ["file1.py", "dir/file2.py", "deep/nested/file3.py"]

        commit = CommitEvent(
            hash="a" * 40,
            message="Test message",
            author_name="John Doe",
            author_email="john@example.com",
            timestamp=datetime.now(),
            files=valid_files,
            parent_hashes=[],
        )

        assert len(commit.files) == 3
        assert all(f in commit.files for f in valid_files)

    def test_files_dangerous_paths_filtered(self):
        """Test that dangerous file paths are filtered out."""
        mixed_files = [
            "safe_file.py",
            "../../../etc/passwd",  # Dangerous
            "normal/file.py",
            "file;rm -rf /.py",  # Dangerous
            "another_safe.py",
        ]

        commit = CommitEvent(
            hash="a" * 40,
            message="Test message",
            author_name="John Doe",
            author_email="john@example.com",
            timestamp=datetime.now(),
            files=mixed_files,
            parent_hashes=[],
        )

        # Only safe files should remain
        assert len(commit.files) == 3
        assert "safe_file.py" in commit.files
        assert "normal/file.py" in commit.files
        assert "another_safe.py" in commit.files
        assert "../../../etc/passwd" not in commit.files

    def test_files_count_limit(self):
        """Test that files changed count is limited."""
        many_files = [f"file{i}.py" for i in range(MAX_FILES_PER_COMMIT + 100)]

        commit = CommitEvent(
            hash="a" * 40,
            message="Test message",
            author_name="John Doe",
            author_email="john@example.com",
            timestamp=datetime.now(),
            files=many_files,
            parent_hashes=[],
        )

        assert len(commit.files) <= MAX_FILES_PER_COMMIT

    def test_timestamp_validation(self):
        """Test that timestamp is properly handled."""
        now = datetime.now()

        commit = CommitEvent(
            hash="a" * 40,
            message="Test message",
            author_name="John Doe",
            author_email="john@example.com",
            timestamp=now,
            files=[],
            parent_hashes=[],
        )

        assert commit.timestamp == now

    def test_unicode_handling(self):
        """Test proper Unicode handling in commit data."""
        commit = CommitEvent(
            hash="a" * 40,
            message="Unicode commit: 🚀 café naïve",
            author_name="José María",
            author_email="jose@example.com",
            timestamp=datetime.now(),
            files=["unicode_файл.py"],
            parent_hashes=[],
        )

        assert "🚀" in commit.message
        assert "café" in commit.message
        assert "José" in commit.author_name
        assert "unicode_файл.py" in commit.files


class TestFileChangeEvent:
    """Test FileChangeEvent validation and sanitization."""

    def test_valid_file_change_creation(self):
        """Test creation of valid file change event."""
        change = FileChangeEvent(
            file_path="src/main.py",
            change_type="M",
            lines_added=10,
            lines_deleted=5,
            commit_hash="a" * 40,
        )

        assert change.file_path == "src/main.py"
        assert change.change_type == "M"
        assert change.lines_added == 10
        assert change.lines_deleted == 5
        assert change.commit_hash == "a" * 40

    def test_file_path_validation(self):
        """Test that file paths are validated."""
        dangerous_paths = [
            "../../../etc/passwd",
            "file;rm -rf /",
            "file`whoami`.py",
            "file\x00.py",
        ]

        for dangerous_path in dangerous_paths:
            with pytest.raises(ValueError, match="Invalid file path"):
                FileChangeEvent(
                    file_path=dangerous_path,
                    change_type="M",
                    lines_added=1,
                    lines_deleted=0,
                    commit_hash="a" * 40,
                )

    def test_file_path_length_limit(self):
        """Test that file path length is limited."""
        long_path = "a" * (MAX_FILE_PATH_LENGTH + 10)

        with pytest.raises(ValueError, match="Invalid file path"):
            FileChangeEvent(
                file_path=long_path,
                change_type="M",
                lines_added=1,
                lines_deleted=0,
                commit_hash="a" * 40,
            )

    def test_change_type_validation(self):
        """Test that change type is validated."""
        valid_types = list(VALID_CHANGE_TYPES)
        invalid_types = ["X", "Y", "Z", "", None, 123]

        # Valid types should work
        for change_type in valid_types:
            change = FileChangeEvent(
                file_path="test.py",
                change_type=change_type,
                lines_added=1,
                lines_deleted=0,
                commit_hash="a" * 40,
            )
            assert change.change_type == change_type

        # Invalid types should be rejected
        for invalid_type in invalid_types:
            if invalid_type not in VALID_CHANGE_TYPES:
                with pytest.raises(ValueError, match="Invalid change type"):
                    FileChangeEvent(
                        file_path="test.py",
                        change_type=invalid_type,
                        lines_added=1,
                        lines_deleted=0,
                        commit_hash="a" * 40,
                    )

    def test_lines_validation(self):
        """Test that line counts are validated."""
        # Negative values should be rejected
        with pytest.raises(ValueError, match="Lines added must be non-negative"):
            FileChangeEvent(
                file_path="test.py",
                change_type="M",
                lines_added=-1,
                lines_deleted=0,
                commit_hash="a" * 40,
            )

        with pytest.raises(ValueError, match="Lines deleted must be non-negative"):
            FileChangeEvent(
                file_path="test.py",
                change_type="M",
                lines_added=0,
                lines_deleted=-1,
                commit_hash="a" * 40,
            )

    def test_commit_hash_validation(self):
        """Test that commit hash is validated."""
        invalid_hashes = ["invalid", "a" * 39, "g" * 40, "", None]

        for invalid_hash in invalid_hashes:
            with pytest.raises(ValueError, match="Invalid commit hash"):
                FileChangeEvent(
                    file_path="test.py",
                    change_type="M",
                    lines_added=1,
                    lines_deleted=0,
                    commit_hash=invalid_hash,
                )


class TestProblemCommit:
    """Test ProblemCommit validation and sanitization."""

    def test_valid_problem_commit_creation(self):
        """Test creation of valid problem commit."""
        problem = ProblemCommit(
            commit_hash="a" * 40,
            problem_type="bug_fix",
            affected_files=["src/bug.py"],
            fix_description="Fixed null pointer exception",
            confidence_score=0.85,
        )

        assert problem.commit_hash == "a" * 40
        assert problem.problem_type == "bug_fix"
        assert problem.affected_files == ["src/bug.py"]
        assert problem.fix_description == "Fixed null pointer exception"
        assert problem.confidence_score == 0.85

    def test_commit_hash_validation(self):
        """Test that commit hash is validated."""
        invalid_hashes = ["invalid", "a" * 39, "g" * 40, "", None]

        for invalid_hash in invalid_hashes:
            with pytest.raises(ValueError, match="Invalid commit hash"):
                ProblemCommit(
                    commit_hash=invalid_hash,
                    problem_type="bug_fix",
                    affected_files=["test.py"],
                    fix_description="Test fix",
                    confidence_score=0.5,
                )

    def test_problem_type_validation(self):
        """Test that problem type is validated."""
        valid_types = [
            "bug_fix",
            "security_fix",
            "performance_fix",
            "refactor",
            "feature",
        ]

        for problem_type in valid_types:
            problem = ProblemCommit(
                commit_hash="a" * 40,
                problem_type=problem_type,
                affected_files=["test.py"],
                fix_description="Test fix",
                confidence_score=0.5,
            )
            assert problem.problem_type == problem_type

    def test_affected_files_validation(self):
        """Test that affected files are validated."""
        valid_files = ["file1.py", "dir/file2.py"]
        dangerous_files = ["../../../etc/passwd", "file;rm -rf /"]

        # Valid files should work
        problem = ProblemCommit(
            commit_hash="a" * 40,
            problem_type="bug_fix",
            affected_files=valid_files,
            fix_description="Test fix",
            confidence_score=0.5,
        )
        assert len(problem.affected_files) == 2

        # Dangerous files should be filtered
        problem = ProblemCommit(
            commit_hash="a" * 40,
            problem_type="bug_fix",
            affected_files=valid_files + dangerous_files,
            fix_description="Test fix",
            confidence_score=0.5,
        )
        assert len(problem.affected_files) == 2  # Only valid files remain

    def test_fix_description_sanitization(self):
        """Test that fix description is sanitized."""
        dangerous_description = "<script>alert('xss')</script>Fixed the bug"

        problem = ProblemCommit(
            commit_hash="a" * 40,
            problem_type="bug_fix",
            affected_files=["test.py"],
            fix_description=dangerous_description,
            confidence_score=0.5,
        )

        assert "script" not in problem.fix_description.lower()
        assert "fixed the bug" in problem.fix_description.lower()

    def test_confidence_score_validation(self):
        """Test that confidence score is validated."""
        # Valid scores (0.0 to 1.0)
        valid_scores = [0.0, 0.5, 1.0, 0.123, 0.999]

        for score in valid_scores:
            problem = ProblemCommit(
                commit_hash="a" * 40,
                problem_type="bug_fix",
                affected_files=["test.py"],
                fix_description="Test fix",
                confidence_score=score,
            )
            assert problem.confidence_score == score

        # Invalid scores should be rejected
        invalid_scores = [-0.1, 1.1, 2.0, -1.0, None, "invalid"]

        for score in invalid_scores:
            with pytest.raises(
                ValueError, match="Confidence score must be between 0.0 and 1.0"
            ):
                ProblemCommit(
                    commit_hash="a" * 40,
                    problem_type="bug_fix",
                    affected_files=["test.py"],
                    fix_description="Test fix",
                    confidence_score=score,
                )

    def test_unicode_handling(self):
        """Test proper Unicode handling in problem commit data."""
        problem = ProblemCommit(
            commit_hash="a" * 40,
            problem_type="bug_fix",
            affected_files=["файл.py"],
            fix_description="Fixed Unicode issue: 🐛 → ✅",
            confidence_score=0.9,
        )

        assert "файл.py" in problem.affected_files
        assert "🐛" in problem.fix_description
        assert "✅" in problem.fix_description


class TestDataStructureIntegration:
    """Integration tests for data structures working together."""

    def test_commit_with_file_changes(self):
        """Test commit event with associated file changes."""
        commit = CommitEvent(
            hash="a" * 40,
            message="Fix multiple files",
            author_name="John Doe",
            author_email="john@example.com",
            timestamp=datetime.now(),
            files=["file1.py", "file2.py", "file3.py"],
            parent_hashes=[],
        )

        file_changes = []
        for file_path in commit.files:
            change = FileChangeEvent(
                file_path=file_path,
                change_type="M",
                lines_added=5,
                lines_deleted=2,
                commit_hash=commit.hash,
            )
            file_changes.append(change)

        assert len(file_changes) == 3
        assert all(change.commit_hash == commit.hash for change in file_changes)

    def test_problem_commit_from_commit_event(self):
        """Test creating problem commit from commit event."""
        commit = CommitEvent(
            hash="a" * 40,
            message="Fix critical security vulnerability",
            author_name="Security Team",
            author_email="security@example.com",
            timestamp=datetime.now(),
            files=["auth.py", "security.py"],
            parent_hashes=[],
        )

        problem = ProblemCommit(
            commit_hash=commit.hash,
            problem_type="security_fix",
            affected_files=commit.files,
            fix_description=commit.message,
            confidence_score=0.95,
        )

        assert problem.commit_hash == commit.hash
        assert problem.affected_files == commit.files
        assert "security vulnerability" in problem.fix_description.lower()

    def test_complete_validation_pipeline(self):
        """Test complete data validation pipeline."""
        # Start with potentially dangerous data
        raw_data = {
            "hash": "a" * 40,
            "message": "<script>alert('xss')</script>Fix bug in auth.py",
            "author_name": "John<script>Doe",
            "author_email": "john@example.com",
            "files": ["auth.py", "../../../etc/passwd", "utils.py"],
        }

        # Create validated commit
        commit = CommitEvent(
            hash=raw_data["hash"],
            message=raw_data["message"],
            author_name=raw_data["author_name"],
            author_email=raw_data["author_email"],
            timestamp=datetime.now(),
            files=raw_data["files"],
            parent_hashes=[],
        )

        # Verify sanitization occurred
        assert "script" not in commit.message.lower()
        assert "script" not in commit.author_name.lower()
        assert len(commit.files) == 2  # Dangerous file filtered out
        assert "auth.py" in commit.files
        assert "utils.py" in commit.files
        assert "../../../etc/passwd" not in commit.files

        # Create file changes for valid files
        file_changes = []
        for file_path in commit.files:
            change = FileChangeEvent(
                file_path=file_path,
                change_type="M",
                lines_added=10,
                lines_deleted=5,
                commit_hash=commit.hash,
            )
            file_changes.append(change)

        assert len(file_changes) == 2

        # Create problem commit if it looks like a fix
        if "fix" in commit.message.lower():
            problem = ProblemCommit(
                commit_hash=commit.hash,
                problem_type="bug_fix",
                affected_files=commit.files,
                fix_description=commit.message,
                confidence_score=0.8,
            )

            assert problem.commit_hash == commit.hash
            assert len(problem.affected_files) == 2
