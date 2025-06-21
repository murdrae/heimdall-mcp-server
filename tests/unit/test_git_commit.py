"""
Unit tests for git commit data structures.

Tests the Commit and FileChange data classes including validation,
sanitization, and natural language conversion.
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from cognitive_memory.git_analysis.commit import (
    MAX_AUTHOR_EMAIL_LENGTH,
    MAX_AUTHOR_NAME_LENGTH,
    MAX_COMMIT_MESSAGE_LENGTH,
    MAX_FILE_PATH_LENGTH,
    MAX_FILES_PER_COMMIT,
    Commit,
    FileChange,
)


class TestFileChange:
    """Test suite for FileChange data class."""

    def test_valid_file_change_creation(self):
        """Test creating a valid FileChange."""
        file_change = FileChange(
            file_path="src/main.py",
            change_type="M",
            lines_added=10,
            lines_deleted=5,
        )

        assert file_change.file_path == "src/main.py"
        assert file_change.change_type == "M"
        assert file_change.lines_added == 10
        assert file_change.lines_deleted == 5

    def test_all_valid_change_types(self):
        """Test all valid change types."""
        valid_types = ["A", "M", "D", "R", "C", "T", "U", "X", "B"]

        for change_type in valid_types:
            file_change = FileChange(
                file_path="test.py",
                change_type=change_type,
                lines_added=1,
                lines_deleted=0,
            )
            assert file_change.change_type == change_type

    def test_invalid_change_type(self):
        """Test FileChange with invalid change type."""
        with pytest.raises(ValueError, match="Invalid change type"):
            FileChange(
                file_path="test.py",
                change_type="INVALID",
                lines_added=1,
                lines_deleted=0,
            )

    def test_negative_line_counts(self):
        """Test FileChange with negative line counts."""
        with pytest.raises(ValueError, match="Line counts must be non-negative"):
            FileChange(
                file_path="test.py",
                change_type="M",
                lines_added=-1,
                lines_deleted=0,
            )

        with pytest.raises(ValueError, match="Line counts must be non-negative"):
            FileChange(
                file_path="test.py",
                change_type="M",
                lines_added=0,
                lines_deleted=-1,
            )

    def test_file_path_validation(self):
        """Test file path validation."""
        # Test with mock validation that fails
        with patch(
            "cognitive_memory.git_analysis.commit.validate_file_path",
            return_value=False,
        ):
            with pytest.raises(ValueError, match="Invalid file path"):
                FileChange(
                    file_path="invalid/path",
                    change_type="M",
                    lines_added=1,
                    lines_deleted=0,
                )

    def test_file_path_sanitization(self):
        """Test file path sanitization."""
        with patch(
            "cognitive_memory.git_analysis.commit._sanitize_string"
        ) as mock_sanitize:
            mock_sanitize.return_value = "sanitized/path.py"

            file_change = FileChange(
                file_path="original/path.py",
                change_type="M",
                lines_added=1,
                lines_deleted=0,
            )

            mock_sanitize.assert_called_once_with(
                "original/path.py", MAX_FILE_PATH_LENGTH
            )
            assert file_change.file_path == "sanitized/path.py"

    def test_default_line_counts(self):
        """Test default line count values."""
        file_change = FileChange(
            file_path="test.py",
            change_type="A",
        )

        assert file_change.lines_added == 0
        assert file_change.lines_deleted == 0


class TestCommit:
    """Test suite for Commit data class."""

    @pytest.fixture
    def valid_commit_data(self):
        """Create valid commit test data."""
        return {
            "hash": "a1b2c3d4e5f6789012345678901234567890abcd",
            "message": "Fix bug in user authentication",
            "author_name": "John Doe",
            "author_email": "john.doe@example.com",
            "timestamp": datetime(2023, 12, 1, 10, 30),
            "file_changes": [
                FileChange("src/auth.py", "M", 15, 5),
                FileChange("tests/test_auth.py", "M", 20, 0),
            ],
            "parent_hashes": ["1234567890123456789012345678901234567890"],
        }

    def test_valid_commit_creation(self, valid_commit_data):
        """Test creating a valid Commit."""
        commit = Commit(**valid_commit_data)

        assert commit.hash == valid_commit_data["hash"]
        assert commit.message == valid_commit_data["message"]
        assert commit.author_name == valid_commit_data["author_name"]
        assert commit.author_email == valid_commit_data["author_email"]
        assert commit.timestamp == valid_commit_data["timestamp"]
        assert len(commit.file_changes) == 2
        assert len(commit.parent_hashes) == 1

    def test_invalid_commit_hash(self, valid_commit_data):
        """Test Commit with invalid hash."""
        valid_commit_data["hash"] = "invalid_hash"

        with patch(
            "cognitive_memory.git_analysis.commit.validate_commit_hash",
            return_value=False,
        ):
            with pytest.raises(ValueError, match="Invalid commit hash"):
                Commit(**valid_commit_data)

    def test_long_commit_message_truncation(self, valid_commit_data):
        """Test commit message truncation for long messages."""
        long_message = "x" * (MAX_COMMIT_MESSAGE_LENGTH + 100)
        valid_commit_data["message"] = long_message

        with patch(
            "cognitive_memory.git_analysis.commit._sanitize_string"
        ) as mock_sanitize:
            mock_sanitize.return_value = "sanitized_message"

            commit = Commit(**valid_commit_data)

            # Should truncate and add ellipsis
            assert len(commit.message) <= MAX_COMMIT_MESSAGE_LENGTH + 3  # +3 for "..."

    def test_author_name_truncation(self, valid_commit_data):
        """Test author name truncation."""
        long_name = "x" * (MAX_AUTHOR_NAME_LENGTH + 50)
        valid_commit_data["author_name"] = long_name

        commit = Commit(**valid_commit_data)
        assert len(commit.author_name) <= MAX_AUTHOR_NAME_LENGTH

    def test_author_email_truncation(self, valid_commit_data):
        """Test author email truncation."""
        long_email = "x" * (MAX_AUTHOR_EMAIL_LENGTH + 50) + "@example.com"
        valid_commit_data["author_email"] = long_email

        commit = Commit(**valid_commit_data)
        assert len(commit.author_email) <= MAX_AUTHOR_EMAIL_LENGTH

    def test_invalid_timestamp(self, valid_commit_data):
        """Test Commit with invalid timestamp."""
        valid_commit_data["timestamp"] = "not_a_datetime"

        with pytest.raises(ValueError, match="Timestamp must be a datetime object"):
            Commit(**valid_commit_data)

    def test_too_many_file_changes(self, valid_commit_data):
        """Test commit with too many file changes."""
        # Create more file changes than the limit
        excessive_changes = [
            FileChange(f"file_{i}.py", "M", 1, 0)
            for i in range(MAX_FILES_PER_COMMIT + 100)
        ]
        valid_commit_data["file_changes"] = excessive_changes

        commit = Commit(**valid_commit_data)
        assert len(commit.file_changes) == MAX_FILES_PER_COMMIT

    def test_invalid_parent_hash(self, valid_commit_data):
        """Test Commit with invalid parent hash."""
        valid_commit_data["parent_hashes"] = ["invalid_hash"]

        with patch(
            "cognitive_memory.git_analysis.commit.validate_commit_hash",
            side_effect=[True, False],
        ):
            with pytest.raises(ValueError, match="Invalid parent hash"):
                Commit(**valid_commit_data)

    def test_from_dict_valid_data(self):
        """Test Commit.from_dict with valid data."""
        data = {
            "hash": "a1b2c3d4e5f6789012345678901234567890abcd",
            "message": "Test commit",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "timestamp": "2023-12-01T10:30:00",
            "file_changes": [
                {
                    "file_path": "test.py",
                    "change_type": "M",
                    "lines_added": 5,
                    "lines_deleted": 2,
                }
            ],
            "parent_hashes": ["1234567890123456789012345678901234567890"],
        }

        with patch(
            "cognitive_memory.git_analysis.commit.sanitize_git_data", return_value=data
        ):
            commit = Commit.from_dict(data)

            assert commit.hash == data["hash"]
            assert commit.message == data["message"]
            assert isinstance(commit.timestamp, datetime)
            assert len(commit.file_changes) == 1

    def test_from_dict_missing_hash(self):
        """Test Commit.from_dict with missing hash."""
        data = {
            "message": "Test commit",
            "author_name": "Test Author",
            "author_email": "test@example.com",
        }

        with patch(
            "cognitive_memory.git_analysis.commit.sanitize_git_data", return_value=data
        ):
            with pytest.raises(ValueError, match="Commit hash is required"):
                Commit.from_dict(data)

    def test_from_dict_string_timestamp_conversion(self):
        """Test timestamp conversion from ISO string."""
        data = {
            "hash": "a1b2c3d4e5f6789012345678901234567890abcd",
            "message": "Test commit",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "timestamp": "2023-12-01T10:30:00Z",
            "file_changes": [],
            "parent_hashes": [],
        }

        with patch(
            "cognitive_memory.git_analysis.commit.sanitize_git_data", return_value=data
        ):
            commit = Commit.from_dict(data)
            assert isinstance(commit.timestamp, datetime)

    def test_from_dict_invalid_timestamp_fallback(self):
        """Test fallback to current time for invalid timestamp."""
        data = {
            "hash": "a1b2c3d4e5f6789012345678901234567890abcd",
            "message": "Test commit",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "timestamp": "invalid_timestamp",
            "file_changes": [],
            "parent_hashes": [],
        }

        with patch(
            "cognitive_memory.git_analysis.commit.sanitize_git_data", return_value=data
        ):
            commit = Commit.from_dict(data)
            assert isinstance(commit.timestamp, datetime)

    def test_get_affected_files(self, valid_commit_data):
        """Test getting list of affected files."""
        commit = Commit(**valid_commit_data)
        affected_files = commit.get_affected_files()

        assert len(affected_files) == 2
        assert "src/auth.py" in affected_files
        assert "tests/test_auth.py" in affected_files

    def test_get_total_line_changes(self, valid_commit_data):
        """Test getting total line changes."""
        commit = Commit(**valid_commit_data)
        total_added, total_deleted = commit.get_total_line_changes()

        assert total_added == 35  # 15 + 20
        assert total_deleted == 5  # 5 + 0

    def test_to_natural_language_single_file(self, valid_commit_data):
        """Test natural language conversion with single file."""
        # Modify to have only one file change
        valid_commit_data["file_changes"] = [FileChange("src/auth.py", "M", 15, 5)]

        commit = Commit(**valid_commit_data)
        description = commit.to_natural_language()

        assert "Git commit a1b2c3d4" in description
        assert "John Doe" in description
        assert "Fix bug in user authentication" in description
        assert "1 file: src/auth.py" in description
        assert "+15/-5 lines" in description

    def test_to_natural_language_multiple_files(self, valid_commit_data):
        """Test natural language conversion with multiple files."""
        commit = Commit(**valid_commit_data)
        description = commit.to_natural_language()

        assert "Git commit a1b2c3d4" in description
        assert "2 files: src/auth.py, tests/test_auth.py" in description
        assert "+35/-5 lines" in description

    def test_to_natural_language_many_files(self, valid_commit_data):
        """Test natural language conversion with many files."""
        # Add more file changes
        valid_commit_data["file_changes"].extend(
            [
                FileChange("src/config.py", "M", 5, 1),
                FileChange("src/utils.py", "A", 20, 0),
                FileChange("README.md", "M", 3, 2),
            ]
        )

        commit = Commit(**valid_commit_data)
        description = commit.to_natural_language()

        assert (
            "5 files including: src/auth.py, tests/test_auth.py, src/config.py..."
            in description
        )

    def test_to_natural_language_no_files(self, valid_commit_data):
        """Test natural language conversion with no files."""
        valid_commit_data["file_changes"] = []

        commit = Commit(**valid_commit_data)
        description = commit.to_natural_language()

        assert "no files" in description
        assert "+0/-0 lines" in description

    def test_from_dict_exception_handling(self):
        """Test exception handling in from_dict."""
        # Test with data that will cause an exception during creation
        invalid_data = {"invalid": "data"}

        with patch(
            "cognitive_memory.git_analysis.commit.sanitize_git_data",
            return_value=invalid_data,
        ):
            with pytest.raises(ValueError):  # Should re-raise the exception
                Commit.from_dict(invalid_data)

    def test_sanitization_calls(self, valid_commit_data):
        """Test that sanitization functions are called appropriately."""
        with patch(
            "cognitive_memory.git_analysis.commit._sanitize_string"
        ) as mock_sanitize:
            mock_sanitize.side_effect = lambda x, max_len: x  # Return input unchanged

            Commit(**valid_commit_data)

            # Should sanitize message, author_name, and author_email
            assert mock_sanitize.call_count >= 3

    def test_empty_file_changes_list(self, valid_commit_data):
        """Test commit with empty file changes list."""
        valid_commit_data["file_changes"] = []

        commit = Commit(**valid_commit_data)
        assert len(commit.file_changes) == 0
        assert commit.get_affected_files() == []
        assert commit.get_total_line_changes() == (0, 0)
