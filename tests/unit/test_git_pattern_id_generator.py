"""
Unit tests for GitPatternIDGenerator.

Tests the deterministic ID generation functionality for cross-platform consistency
and proper canonicalization of git patterns.
"""

from cognitive_memory.git_analysis.security import GitPatternIDGenerator


class TestGitPatternIDGenerator:
    """Test suite for GitPatternIDGenerator."""

    def test_generate_cochange_id_basic(self):
        """Test basic co-change ID generation."""
        file_a = "src/utils.py"
        file_b = "src/main.py"

        result = GitPatternIDGenerator.generate_cochange_id(file_a, file_b)

        assert result.startswith("git::cochange::")
        assert len(result) == len("git::cochange::") + 64  # SHA-256 hex length

    def test_generate_cochange_id_deterministic(self):
        """Test that co-change ID generation is deterministic."""
        file_a = "src/utils.py"
        file_b = "src/main.py"

        id1 = GitPatternIDGenerator.generate_cochange_id(file_a, file_b)
        id2 = GitPatternIDGenerator.generate_cochange_id(file_a, file_b)

        assert id1 == id2

    def test_generate_cochange_id_order_independence(self):
        """Test that co-change ID is independent of file order."""
        file_a = "src/utils.py"
        file_b = "src/main.py"

        id1 = GitPatternIDGenerator.generate_cochange_id(file_a, file_b)
        id2 = GitPatternIDGenerator.generate_cochange_id(file_b, file_a)

        assert id1 == id2

    def test_generate_cochange_id_path_canonicalization(self):
        """Test that co-change ID handles path canonicalization."""
        # Different path representations should produce same ID
        id1 = GitPatternIDGenerator.generate_cochange_id("src/utils.py", "src/main.py")
        id2 = GitPatternIDGenerator.generate_cochange_id(
            "src\\utils.py", "src\\main.py"
        )
        id3 = GitPatternIDGenerator.generate_cochange_id(
            "./src/utils.py", "./src/main.py"
        )

        assert id1 == id2 == id3

    def test_generate_cochange_id_case_normalization(self):
        """Test that co-change ID handles case normalization."""
        id1 = GitPatternIDGenerator.generate_cochange_id("src/Utils.py", "src/Main.py")
        id2 = GitPatternIDGenerator.generate_cochange_id("src/utils.py", "src/main.py")

        assert id1 == id2

    def test_generate_cochange_id_different_files(self):
        """Test that different file pairs produce different IDs."""
        id1 = GitPatternIDGenerator.generate_cochange_id("src/utils.py", "src/main.py")
        id2 = GitPatternIDGenerator.generate_cochange_id("src/config.py", "src/main.py")
        id3 = GitPatternIDGenerator.generate_cochange_id(
            "src/utils.py", "src/config.py"
        )

        assert id1 != id2 != id3
        assert id1 != id3

    def test_generate_hotspot_id_basic(self):
        """Test basic hotspot ID generation."""
        file_path = "src/buggy_module.py"

        result = GitPatternIDGenerator.generate_hotspot_id(file_path)

        assert result.startswith("git::hotspot::")
        assert len(result) == len("git::hotspot::") + 64  # SHA-256 hex length

    def test_generate_hotspot_id_deterministic(self):
        """Test that hotspot ID generation is deterministic."""
        file_path = "src/buggy_module.py"

        id1 = GitPatternIDGenerator.generate_hotspot_id(file_path)
        id2 = GitPatternIDGenerator.generate_hotspot_id(file_path)

        assert id1 == id2

    def test_generate_hotspot_id_path_canonicalization(self):
        """Test that hotspot ID handles path canonicalization."""
        # Different path representations should produce same ID
        id1 = GitPatternIDGenerator.generate_hotspot_id("src/buggy_module.py")
        id2 = GitPatternIDGenerator.generate_hotspot_id("src\\buggy_module.py")
        id3 = GitPatternIDGenerator.generate_hotspot_id("./src/buggy_module.py")

        assert id1 == id2 == id3

    def test_generate_hotspot_id_case_normalization(self):
        """Test that hotspot ID handles case normalization."""
        id1 = GitPatternIDGenerator.generate_hotspot_id("src/BuggyModule.py")
        id2 = GitPatternIDGenerator.generate_hotspot_id("src/buggymodule.py")

        assert id1 == id2

    def test_generate_hotspot_id_different_files(self):
        """Test that different files produce different hotspot IDs."""
        id1 = GitPatternIDGenerator.generate_hotspot_id("src/buggy_module.py")
        id2 = GitPatternIDGenerator.generate_hotspot_id("src/stable_module.py")
        id3 = GitPatternIDGenerator.generate_hotspot_id("tests/test_module.py")

        assert id1 != id2 != id3
        assert id1 != id3

    def test_generate_solution_id_basic(self):
        """Test basic solution ID generation."""
        problem_type = "validation_error"
        solution_approach = "input_sanitization"

        result = GitPatternIDGenerator.generate_solution_id(
            problem_type, solution_approach
        )

        assert result.startswith("git::solution::")
        assert len(result) == len("git::solution::") + 64  # SHA-256 hex length

    def test_generate_solution_id_deterministic(self):
        """Test that solution ID generation is deterministic."""
        problem_type = "validation_error"
        solution_approach = "input_sanitization"

        id1 = GitPatternIDGenerator.generate_solution_id(
            problem_type, solution_approach
        )
        id2 = GitPatternIDGenerator.generate_solution_id(
            problem_type, solution_approach
        )

        assert id1 == id2

    def test_generate_solution_id_case_normalization(self):
        """Test that solution ID handles case normalization."""
        id1 = GitPatternIDGenerator.generate_solution_id(
            "Validation_Error", "Input_Sanitization"
        )
        id2 = GitPatternIDGenerator.generate_solution_id(
            "validation_error", "input_sanitization"
        )
        id3 = GitPatternIDGenerator.generate_solution_id(
            "VALIDATION_ERROR", "INPUT_SANITIZATION"
        )

        assert id1 == id2 == id3

    def test_generate_solution_id_whitespace_normalization(self):
        """Test that solution ID handles whitespace normalization."""
        id1 = GitPatternIDGenerator.generate_solution_id(
            "  validation_error  ", "  input_sanitization  "
        )
        id2 = GitPatternIDGenerator.generate_solution_id(
            "validation_error", "input_sanitization"
        )

        assert id1 == id2

    def test_generate_solution_id_different_patterns(self):
        """Test that different solution patterns produce different IDs."""
        id1 = GitPatternIDGenerator.generate_solution_id(
            "validation_error", "input_sanitization"
        )
        id2 = GitPatternIDGenerator.generate_solution_id("performance_issue", "caching")
        id3 = GitPatternIDGenerator.generate_solution_id(
            "validation_error", "error_handling"
        )

        assert id1 != id2 != id3
        assert id1 != id3

    def test_generate_solution_id_order_matters(self):
        """Test that solution ID is affected by problem/solution order (unlike co-change)."""
        # Problem and solution are semantically different, so order should matter
        id1 = GitPatternIDGenerator.generate_solution_id(
            "validation_error", "input_sanitization"
        )
        id2 = GitPatternIDGenerator.generate_solution_id(
            "input_sanitization", "validation_error"
        )

        assert id1 != id2

    def test_all_id_types_different_formats(self):
        """Test that different ID types have different prefixes."""
        cochange_id = GitPatternIDGenerator.generate_cochange_id("file1.py", "file2.py")
        hotspot_id = GitPatternIDGenerator.generate_hotspot_id("file1.py")
        solution_id = GitPatternIDGenerator.generate_solution_id("problem", "solution")

        assert cochange_id.startswith("git::cochange::")
        assert hotspot_id.startswith("git::hotspot::")
        assert solution_id.startswith("git::solution::")

        # Ensure they're all different
        assert cochange_id != hotspot_id != solution_id

    def test_id_format_validation(self):
        """Test that generated IDs have valid format."""
        cochange_id = GitPatternIDGenerator.generate_cochange_id("file1.py", "file2.py")
        hotspot_id = GitPatternIDGenerator.generate_hotspot_id("file1.py")
        solution_id = GitPatternIDGenerator.generate_solution_id("problem", "solution")

        # Check format: git::<type>::<64-char-hex>
        import re

        pattern = r"^git::(cochange|hotspot|solution)::[a-f0-9]{64}$"

        assert re.match(pattern, cochange_id)
        assert re.match(pattern, hotspot_id)
        assert re.match(pattern, solution_id)

    def test_hash_collision_resistance(self):
        """Test that similar inputs produce different hashes."""
        # Similar but different file pairs
        id1 = GitPatternIDGenerator.generate_cochange_id("src/utils.py", "src/main.py")
        id2 = GitPatternIDGenerator.generate_cochange_id("src/utils.py", "src/main.js")
        id3 = GitPatternIDGenerator.generate_cochange_id("src/util.py", "src/main.py")

        assert id1 != id2
        assert id1 != id3
        assert id2 != id3

    def test_unicode_handling(self):
        """Test that IDs handle Unicode characters properly."""
        # Test with Unicode file names
        cochange_id = GitPatternIDGenerator.generate_cochange_id(
            "src/测试.py", "src/файл.py"
        )
        hotspot_id = GitPatternIDGenerator.generate_hotspot_id("src/ファイル.py")

        # Should generate valid IDs without errors
        assert cochange_id.startswith("git::cochange::")
        assert hotspot_id.startswith("git::hotspot::")

        # Should be deterministic
        cochange_id2 = GitPatternIDGenerator.generate_cochange_id(
            "src/测试.py", "src/файл.py"
        )
        assert cochange_id == cochange_id2

    def test_empty_string_handling(self):
        """Test handling of empty strings."""
        # Should handle empty strings gracefully
        cochange_id = GitPatternIDGenerator.generate_cochange_id("", "file.py")
        hotspot_id = GitPatternIDGenerator.generate_hotspot_id("")
        solution_id = GitPatternIDGenerator.generate_solution_id("", "")

        # Should generate valid IDs
        assert cochange_id.startswith("git::cochange::")
        assert hotspot_id.startswith("git::hotspot::")
        assert solution_id.startswith("git::solution::")

    def test_long_path_handling(self):
        """Test handling of very long file paths."""
        long_path = "very/long/path/that/goes/deep/into/nested/directories/with/many/levels/file.py"

        hotspot_id = GitPatternIDGenerator.generate_hotspot_id(long_path)

        # Should generate valid ID regardless of path length
        assert hotspot_id.startswith("git::hotspot::")
        assert len(hotspot_id) == len("git::hotspot::") + 64

    def test_special_characters_in_paths(self):
        """Test handling of special characters in file paths."""
        special_path = "src/file-with_special.chars@#$.py"

        hotspot_id = GitPatternIDGenerator.generate_hotspot_id(special_path)
        cochange_id = GitPatternIDGenerator.generate_cochange_id(
            special_path, "normal.py"
        )

        # Should handle special characters properly
        assert hotspot_id.startswith("git::hotspot::")
        assert cochange_id.startswith("git::cochange::")

    def test_cross_platform_consistency(self):
        """Test that IDs are consistent across platform path separators."""
        # Test with mixed separators (simulating cross-platform scenarios)
        unix_paths = ("src/module.py", "tests/test_module.py")
        windows_paths = ("src\\module.py", "tests\\test_module.py")
        mixed_paths = ("src/module.py", "tests\\test_module.py")

        id1 = GitPatternIDGenerator.generate_cochange_id(*unix_paths)
        id2 = GitPatternIDGenerator.generate_cochange_id(*windows_paths)
        id3 = GitPatternIDGenerator.generate_cochange_id(*mixed_paths)

        # All should produce the same ID due to canonicalization
        assert id1 == id2 == id3
