"""
Unit tests for git security module.

Comprehensive security testing for path validation, input sanitization,
and attack prevention in git repository analysis.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from cognitive_memory.git_analysis.security import (
    canonicalize_path,
    generate_secure_id,
    sanitize_git_data,
    validate_commit_hash,
    validate_file_path,
    validate_repository_path,
)


class TestValidateRepositoryPath:
    """Test repository path validation against security threats."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()
            git_dir = repo_path / ".git"
            git_dir.mkdir()
            yield str(repo_path)

    def test_valid_repository_path(self, temp_git_repo):
        """Test validation of a valid git repository path."""
        assert validate_repository_path(temp_git_repo) is True

    def test_empty_path_rejected(self):
        """Test that empty paths are rejected."""
        assert validate_repository_path("") is False
        assert validate_repository_path("   ") is False

    def test_none_path_rejected(self):
        """Test that None path is rejected."""
        assert validate_repository_path(None) is False

    def test_non_string_path_rejected(self):
        """Test that non-string paths are rejected."""
        assert validate_repository_path(123) is False
        assert validate_repository_path(["path"]) is False

    def test_directory_traversal_attacks_blocked(self):
        """Test that directory traversal patterns are blocked."""
        dangerous_paths = [
            "../../../etc/passwd",
            "repo/../../../secret",
            "valid/path/../../etc/passwd",
            "/valid/path/../../../etc",
            "C:\\valid\\..\\..\\Windows\\System32",
        ]

        for path in dangerous_paths:
            assert validate_repository_path(path) is False

    def test_command_injection_patterns_blocked(self):
        """Test that command injection patterns are blocked."""
        dangerous_paths = [
            "repo; rm -rf /",
            "repo & del C:\\*",
            "repo | cat /etc/passwd",
            "repo `whoami`",
            "repo $(ls -la)",
            "repo ${PWD}",
            "repo\x00injection",
        ]

        for path in dangerous_paths:
            assert validate_repository_path(path) is False

    def test_system_directory_access_blocked(self):
        """Test that system directories are blocked."""
        system_paths = [
            "/bin/bash",
            "/etc/passwd",
            "/usr/bin/git",
            "/proc/version",
            "/sys/devices",
            "/dev/null",
            "C:\\Windows\\System32",
            "C:\\Program Files\\Git",
        ]

        for path in system_paths:
            assert validate_repository_path(path) is False

    def test_nonexistent_path_rejected(self):
        """Test that non-existent paths are rejected."""
        assert validate_repository_path("/this/path/does/not/exist") is False

    def test_non_directory_path_rejected(self, temp_git_repo):
        """Test that file paths (not directories) are rejected."""
        file_path = Path(temp_git_repo) / "file.txt"
        file_path.write_text("test")
        assert validate_repository_path(str(file_path)) is False

    def test_directory_without_git_rejected(self):
        """Test that directories without .git are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            assert validate_repository_path(temp_dir) is False

    def test_windows_forbidden_characters_blocked(self):
        """Test that Windows forbidden characters are blocked."""
        forbidden_chars = ["<", ">", ":", '"', "|", "?", "*"]

        for char in forbidden_chars:
            path = f"repo{char}name"
            assert validate_repository_path(path) is False

    def test_control_characters_blocked(self):
        """Test that control characters are blocked."""
        for i in range(32):  # Control characters 0-31
            if i not in [9, 10, 13]:  # Exclude tab, newline, carriage return
                path = f"repo{chr(i)}name"
                assert validate_repository_path(path) is False

    def test_unicode_normalization_attacks_blocked(self):
        """Test that Unicode normalization attacks are blocked."""
        # Test various Unicode attack vectors
        unicode_attacks = [
            "repo\u202e",  # Right-to-left override
            "repo\u2029",  # Paragraph separator
            "repo\ufeff",  # Zero width no-break space
        ]

        for path in unicode_attacks:
            assert validate_repository_path(path) is False

    @patch("os.access")
    def test_permission_check(self, mock_access, temp_git_repo):
        """Test that read permission is checked."""
        mock_access.return_value = False
        assert validate_repository_path(temp_git_repo) is False

        mock_access.return_value = True
        assert validate_repository_path(temp_git_repo) is True


class TestCanonicalizePath:
    """Test path canonicalization for consistent ID generation."""

    def test_empty_path_handling(self):
        """Test handling of empty or invalid paths."""
        assert canonicalize_path("") == ""
        assert canonicalize_path(None) == ""
        assert canonicalize_path(123) == ""

    def test_case_normalization(self):
        """Test that paths are normalized to lowercase."""
        assert canonicalize_path("FILE.TXT") == "file.txt"
        assert canonicalize_path("Dir/FILE.TXT") == "dir/file.txt"

    def test_separator_normalization(self):
        """Test that path separators are normalized."""
        assert canonicalize_path("dir\\file.txt") == "dir/file.txt"
        assert canonicalize_path("dir/subdir\\file.txt") == "dir/subdir/file.txt"

    def test_duplicate_separator_removal(self):
        """Test that duplicate separators are removed."""
        assert canonicalize_path("dir//file.txt") == "dir/file.txt"
        assert canonicalize_path("dir///subdir//file.txt") == "dir/subdir/file.txt"

    def test_leading_trailing_separator_removal(self):
        """Test that leading/trailing separators are removed."""
        assert canonicalize_path("/dir/file.txt/") == "dir/file.txt"
        assert canonicalize_path("///dir/file.txt///") == "dir/file.txt"

    def test_relative_path_normalization(self):
        """Test that relative path markers are handled."""
        assert canonicalize_path("./file.txt") == "file.txt"
        assert canonicalize_path("dir/./file.txt") == "dir/file.txt"

    def test_unicode_normalization(self):
        """Test Unicode normalization (NFC form)."""
        # Test composed vs decomposed Unicode
        composed = "café"  # NFC form
        decomposed = "cafe\u0301"  # NFD form (e + combining acute accent)

        assert canonicalize_path(composed) == canonicalize_path(decomposed)

    def test_complex_path_normalization(self):
        """Test complex path with multiple normalization needs."""
        complex_path = "\\\\Dir\\SubDir//File.TXT///"
        expected = "dir/subdir/file.txt"
        assert canonicalize_path(complex_path) == expected

    def test_exception_handling(self):
        """Test that exceptions during normalization are handled."""
        with patch("unicodedata.normalize", side_effect=Exception("test error")):
            assert canonicalize_path("test") == ""


class TestSanitizeGitData:
    """Test git data sanitization for safe processing."""

    def test_empty_data_handling(self):
        """Test handling of empty or None data."""
        assert sanitize_git_data({}) == {}
        assert sanitize_git_data({"key": None}) == {"key": None}

    def test_string_sanitization(self):
        """Test string value sanitization."""
        data = {"message": "Test commit message"}
        result = sanitize_git_data(data)
        assert result["message"] == "Test commit message"

    def test_control_character_removal(self):
        """Test that control characters are removed."""
        data = {"message": "Test\x00\x01\x02message"}
        result = sanitize_git_data(data)
        assert "\x00" not in result["message"]
        assert "\x01" not in result["message"]
        assert "\x02" not in result["message"]

    def test_script_injection_removal(self):
        """Test that script injection patterns are removed."""
        dangerous_strings = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "vbscript:msgbox('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "<!-- comment -->",
        ]

        for dangerous in dangerous_strings:
            data = {"message": dangerous}
            result = sanitize_git_data(data)
            assert "script" not in result["message"].lower()
            assert "javascript" not in result["message"].lower()

    def test_length_limiting(self):
        """Test that string length is limited."""
        long_string = "a" * 20000
        data = {"message": long_string}
        result = sanitize_git_data(data, max_length=1000)
        assert len(result["message"]) <= 1000

    def test_list_sanitization(self):
        """Test that lists are sanitized."""
        data = {"files": ["file1.txt", "file2<script>", "file3.txt"]}
        result = sanitize_git_data(data)
        assert len(result["files"]) == 3
        assert "script" not in result["files"][1].lower()

    def test_list_size_limiting(self):
        """Test that list size is limited."""
        large_list = [f"file{i}.txt" for i in range(200)]
        data = {"files": large_list}
        result = sanitize_git_data(data)
        assert len(result["files"]) <= 100

    def test_nested_dict_sanitization(self):
        """Test that nested dictionaries are sanitized."""
        data = {
            "commit": {
                "message": "<script>alert('xss')</script>",
                "author": "test@example.com",
            }
        }
        result = sanitize_git_data(data)
        assert "script" not in result["commit"]["message"].lower()
        assert result["commit"]["author"] == "test@example.com"

    def test_non_string_preservation(self):
        """Test that non-string values are preserved."""
        data = {
            "timestamp": 1234567890,
            "is_merge": True,
            "files_changed": 42,
            "score": 3.14,
        }
        result = sanitize_git_data(data)
        assert result["timestamp"] == 1234567890
        assert result["is_merge"] is True
        assert result["files_changed"] == 42
        assert result["score"] == 3.14

    def test_unicode_handling(self):
        """Test proper Unicode handling in sanitization."""
        data = {"message": "Unicode test: 🚀 café naïve"}
        result = sanitize_git_data(data)
        assert "🚀" in result["message"]
        assert "café" in result["message"]

    def test_utf8_encoding_safety(self):
        """Test that UTF-8 encoding is safe after truncation."""
        # Create a string that might be truncated in the middle of a multi-byte character
        data = {"message": "a" * 9995 + "🚀🚀🚀"}  # Multi-byte characters at the end
        result = sanitize_git_data(data, max_length=10000)

        # Result should be valid UTF-8
        result["message"].encode("utf-8")  # Should not raise exception

    def test_exception_handling(self):
        """Test that exceptions during sanitization are handled."""
        with patch("unicodedata.normalize", side_effect=Exception("test error")):
            data = {"message": "test"}
            result = sanitize_git_data(data)
            assert result == {}


class TestGenerateSecureId:
    """Test secure ID generation."""

    def test_string_input(self):
        """Test ID generation from string input."""
        result = generate_secure_id("test_data")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex length

    def test_deterministic_output(self):
        """Test that output is deterministic."""
        data = "test_data"
        result1 = generate_secure_id(data)
        result2 = generate_secure_id(data)
        assert result1 == result2

    def test_different_inputs_different_outputs(self):
        """Test that different inputs produce different outputs."""
        result1 = generate_secure_id("data1")
        result2 = generate_secure_id("data2")
        assert result1 != result2

    def test_non_string_input(self):
        """Test ID generation from non-string input."""
        result = generate_secure_id(123)
        assert isinstance(result, str)
        assert len(result) == 64

    def test_unicode_input(self):
        """Test ID generation with Unicode input."""
        result = generate_secure_id("Unicode: 🚀 café")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_exception_handling(self):
        """Test that exceptions return fallback ID."""
        with patch("hashlib.sha256", side_effect=Exception("test error")):
            result = generate_secure_id("test")
            # Should return fallback hash
            assert isinstance(result, str)
            assert len(result) == 64


class TestValidateCommitHash:
    """Test git commit hash validation."""

    def test_valid_sha1_hash(self):
        """Test validation of valid SHA-1 commit hashes."""
        valid_hashes = [
            "a" * 40,  # All 'a's
            "1234567890abcdef1234567890abcdef12345678",
            "0" * 40,  # All zeros
            "f" * 40,  # All 'f's
        ]

        for hash_val in valid_hashes:
            assert validate_commit_hash(hash_val) is True

    def test_valid_sha256_hash(self):
        """Test validation of valid SHA-256 commit hashes."""
        valid_hashes = [
            "a" * 64,  # All 'a's
            "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "0" * 64,  # All zeros
        ]

        for hash_val in valid_hashes:
            assert validate_commit_hash(hash_val) is True

    def test_invalid_length_rejected(self):
        """Test that invalid length hashes are rejected."""
        invalid_hashes = [
            "a" * 39,  # Too short for SHA-1
            "a" * 41,  # Too long for SHA-1
            "a" * 63,  # Too short for SHA-256
            "a" * 65,  # Too long for SHA-256
            "a" * 20,  # Way too short
            "",  # Empty
        ]

        for hash_val in invalid_hashes:
            assert validate_commit_hash(hash_val) is False

    def test_non_hex_characters_rejected(self):
        """Test that non-hexadecimal characters are rejected."""
        invalid_hashes = [
            "g" * 40,  # 'g' is not hex
            "z" * 40,  # 'z' is not hex
            "123456789abcdefg123456789abcdefg12345678",  # Contains 'g'
            "!" * 40,  # Special characters
        ]

        for hash_val in invalid_hashes:
            assert validate_commit_hash(hash_val) is False

    def test_none_and_empty_rejected(self):
        """Test that None and empty values are rejected."""
        assert validate_commit_hash(None) is False
        assert validate_commit_hash("") is False

    def test_non_string_rejected(self):
        """Test that non-string values are rejected."""
        assert validate_commit_hash(123) is False
        assert validate_commit_hash(["hash"]) is False

    def test_case_insensitive(self):
        """Test that both uppercase and lowercase hex are valid."""
        hash_lower = "abcdef1234567890abcdef1234567890abcdef12"
        hash_upper = "ABCDEF1234567890ABCDEF1234567890ABCDEF12"

        assert validate_commit_hash(hash_lower) is True
        assert validate_commit_hash(hash_upper) is True


class TestValidateFilePath:
    """Test file path validation."""

    def test_valid_file_paths(self):
        """Test validation of valid file paths."""
        valid_paths = [
            "file.txt",
            "dir/file.txt",
            "deep/nested/path/file.py",
            "file-with-dashes.txt",
            "file_with_underscores.py",
            "file.with.dots.txt",
        ]

        for path in valid_paths:
            assert validate_file_path(path) is True

    def test_empty_and_none_rejected(self):
        """Test that empty and None paths are rejected."""
        assert validate_file_path("") is False
        assert validate_file_path(None) is False

    def test_non_string_rejected(self):
        """Test that non-string paths are rejected."""
        assert validate_file_path(123) is False
        assert validate_file_path(["path"]) is False

    def test_length_limit_enforced(self):
        """Test that path length limit is enforced."""
        long_path = "a" * 5000
        assert validate_file_path(long_path, max_length=4096) is False

        acceptable_path = "a" * 100
        assert validate_file_path(acceptable_path, max_length=4096) is True

    def test_dangerous_patterns_blocked(self):
        """Test that dangerous patterns are blocked."""
        dangerous_paths = [
            "../file.txt",
            "dir/../file.txt",
            "file\x00.txt",
            "file|cmd.txt",
            "file;cmd.txt",
            "file&cmd.txt",
            "file`cmd.txt",
            "file$(cmd).txt",
            "file${var}.txt",
        ]

        for path in dangerous_paths:
            assert validate_file_path(path) is False

    def test_unicode_file_paths(self):
        """Test that Unicode file paths are handled correctly."""
        unicode_paths = [
            "café.txt",
            "файл.txt",
            "文件.txt",
            "🚀rocket.txt",
        ]

        for path in unicode_paths:
            assert validate_file_path(path) is True


class TestSecurityIntegration:
    """Integration tests for security functions working together."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()
            git_dir = repo_path / ".git"
            git_dir.mkdir()
            yield str(repo_path)

    def test_path_validation_and_canonicalization(self, temp_git_repo):
        """Test that path validation and canonicalization work together."""
        # First validate the path
        assert validate_repository_path(temp_git_repo) is True

        # Then canonicalize it
        canonical = canonicalize_path(temp_git_repo)
        assert canonical is not None
        assert len(canonical) > 0

    def test_data_sanitization_and_id_generation(self):
        """Test that data sanitization and ID generation work together."""
        dangerous_data = {
            "message": "<script>alert('xss')</script>Normal message",
            "author": "test@example.com",
            "files": ["file1.txt", "file2<script>.txt"],
        }

        # Sanitize the data
        clean_data = sanitize_git_data(dangerous_data)

        # Generate secure ID from clean data
        data_id = generate_secure_id(str(clean_data))

        assert "script" not in str(clean_data).lower()
        assert len(data_id) == 64

    def test_complete_security_pipeline(self, temp_git_repo):
        """Test complete security validation pipeline."""
        # 1. Validate repository path
        assert validate_repository_path(temp_git_repo) is True

        # 2. Create mock git data
        git_data = {
            "message": "Fix security issue\n\nRemove <script> tags",
            "hash": "a" * 40,
            "files": ["security.py", "../../../etc/passwd"],
        }

        # 3. Sanitize git data
        clean_data = sanitize_git_data(git_data)

        # 4. Validate commit hash
        assert validate_commit_hash(clean_data["hash"]) is True

        # 5. Validate file paths
        valid_files = [f for f in clean_data["files"] if validate_file_path(f)]
        assert len(valid_files) == 1  # Only security.py should be valid
        assert "security.py" in valid_files

        # 6. Generate secure ID
        secure_id = generate_secure_id(str(clean_data))
        assert len(secure_id) == 64
