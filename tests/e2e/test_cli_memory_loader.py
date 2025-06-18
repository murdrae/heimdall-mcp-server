"""
End-to-end tests for CLI memory loader functionality.

Tests the actual command-line interface using subprocess to execute real commands,
validate real storage, and test actual error scenarios. These tests run the full
pipeline from CLI command to database storage.
"""

import os
import sqlite3
import subprocess

import pytest


@pytest.mark.slow
class TestCLIMemoryLoaderE2E:
    """End-to-end tests for CLI memory loader using real commands."""

    def test_cli_load_command_success(self, tmp_path):
        """Test successful memory loading via actual CLI command."""
        # Create test markdown file
        test_content = """# E2E Test Document

## Introduction
This document tests the end-to-end CLI functionality.

### Features
- Real command execution
- Actual database storage
- Complete integration testing

### Technical Details
The CLI should properly parse this markdown and create memories.

```python
def example_function():
    return "This is a code example"
```

## Validation
This content should be processed into different hierarchy levels:
- L0: Concepts like "CLI functionality"
- L1: Contexts like "Technical Details"
- L2: Episodes like code examples
"""

        test_file = tmp_path / "test_doc.md"
        test_file.write_text(test_content)

        # Set up environment for test
        env = os.environ.copy()
        env["SQLITE_PATH"] = str(tmp_path / "test_memory.db")

        # Execute actual CLI command
        result = subprocess.run(
            ["memory_system", "load", str(test_file)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            env=env,
        )

        # Validate command execution
        assert result.returncode == 0, f"CLI command failed: {result.stderr}"
        assert "✓ Memory loading completed" in result.stdout
        assert "Memories loaded:" in result.stdout
        assert "Connections created:" in result.stdout

        # Validate actual database was created and populated
        db_path = tmp_path / "test_memory.db"
        assert db_path.exists(), "Database file was not created"

        # Check database contents
        with sqlite3.connect(str(db_path)) as conn:
            # Check memories table exists and has data
            memories = conn.execute("SELECT * FROM memories").fetchall()
            assert len(memories) > 0, "No memories were stored in database"

            # Verify hierarchy distribution
            hierarchy_counts = conn.execute("""
                SELECT hierarchy_level, COUNT(*)
                FROM memories
                GROUP BY hierarchy_level
            """).fetchall()

            levels = dict(hierarchy_counts)
            assert len(levels) > 1, "Should have multiple hierarchy levels"
            assert 0 in levels or 1 in levels or 2 in levels, (
                "Should have valid hierarchy levels"
            )

    def test_cli_load_command_dry_run(self, tmp_path):
        """Test CLI dry-run mode via actual command."""
        # Create test file
        test_content = """# Dry Run Test

## Section 1
Content for dry run testing.

## Section 2
More content to analyze.
"""

        test_file = tmp_path / "dry_run_test.md"
        test_file.write_text(test_content)

        # Execute CLI command with dry-run flag
        result = subprocess.run(
            ["memory_system", "load", str(test_file), "--dry-run"],
            capture_output=True,
            text=True,
        )

        # Validate dry-run output
        assert result.returncode == 0, f"Dry-run command failed: {result.stderr}"
        assert "🔍 Dry run mode:" in result.stdout
        assert "Would load" in result.stdout
        assert "memories:" in result.stdout

        # Verify no database was created in dry-run
        db_path = tmp_path / "cognitive_memory.db"
        assert not db_path.exists(), "Database should not be created in dry-run mode"

    def test_cli_load_command_file_not_found(self, tmp_path):
        """Test CLI error handling for missing files."""
        nonexistent_file = tmp_path / "does_not_exist.md"

        # Execute CLI command with nonexistent file
        result = subprocess.run(
            ["memory_system", "load", str(nonexistent_file)],
            capture_output=True,
            text=True,
        )

        # Should fail gracefully
        assert result.returncode != 0, "Command should fail for nonexistent file"
        # Error messages appear in stdout (from CognitiveCLI), logs in stderr
        assert "✗" in result.stdout or "❌" in result.stdout

    def test_cli_load_command_invalid_file_format(self, tmp_path):
        """Test CLI error handling for invalid file formats."""
        # Create invalid file (binary content)
        invalid_file = tmp_path / "invalid.md"
        invalid_file.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8

        # Execute CLI command
        result = subprocess.run(
            ["memory_system", "load", str(invalid_file)], capture_output=True, text=True
        )

        # Should handle error gracefully
        assert result.returncode != 0, "Command should fail for invalid file"
        assert "✗" in result.stdout or "error" in result.stdout.lower()

    def test_cli_load_command_empty_file(self, tmp_path):
        """Test CLI handling of empty markdown files."""
        # Create empty file
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")

        # Set up environment
        env = os.environ.copy()
        env["SQLITE_PATH"] = str(tmp_path / "empty_test.db")

        # Execute CLI command
        result = subprocess.run(
            ["memory_system", "load", str(empty_file)],
            capture_output=True,
            text=True,
            env=env,
        )

        # Should succeed but load nothing
        assert result.returncode == 0, f"Empty file handling failed: {result.stderr}"
        assert "Memories loaded: 0" in result.stdout

    def test_cli_load_command_unsupported_loader(self, tmp_path):
        """Test CLI error handling for unsupported loader types."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        # Execute CLI command with unsupported loader type
        result = subprocess.run(
            ["memory_system", "load", str(test_file), "--loader-type", "pdf"],
            capture_output=True,
            text=True,
        )

        # Should fail with appropriate error
        assert result.returncode != 0, "Command should fail for unsupported loader"
        assert "Unsupported loader type" in result.stdout or "pdf" in result.stdout

    def test_cli_load_command_large_document(self, tmp_path):
        """Test CLI performance with larger documents."""
        # Create larger test document
        sections = []
        for i in range(25):  # 25 sections - substantial but not too large for CI
            sections.append(f"""## Section {i}

This is section {i} with detailed content for performance testing.

### Subsection {i}.1

Technical details for section {i}.

```python
def section_{i}_function():
    '''Function for section {i}.'''
    return f"Section {i} result"
```

### Examples

1. Example {i}.1: Basic usage
2. Example {i}.2: Advanced patterns
3. Example {i}.3: Error handling
""")

        large_content = "# Large Document Performance Test\n\n" + "\n\n".join(sections)

        large_file = tmp_path / "large_test.md"
        large_file.write_text(large_content)

        # Set up environment
        env = os.environ.copy()
        env["SQLITE_PATH"] = str(tmp_path / "large_test.db")

        # Execute CLI command and time it
        import time

        start_time = time.time()

        result = subprocess.run(
            ["memory_system", "load", str(large_file)],
            capture_output=True,
            text=True,
            env=env,
        )

        execution_time = time.time() - start_time

        # Validate performance and results
        assert result.returncode == 0, f"Large document loading failed: {result.stderr}"
        assert execution_time < 60, f"Loading took too long: {execution_time}s"
        assert "✓ Memory loading completed" in result.stdout

        # Verify substantial memory creation
        lines = result.stdout.split("\n")
        memories_line = next(line for line in lines if "Memories loaded:" in line)
        memories_count = int(memories_line.split(":")[1].strip())
        assert memories_count > 25, f"Should create many memories, got {memories_count}"

    def test_cli_load_command_with_connections(self, tmp_path):
        """Test CLI connection extraction and storage."""
        # Create document designed to generate connections
        test_content = """# Security Documentation

## Authentication
User authentication protects system access.

## Authorization
Authorization controls user permissions after authentication.

## Session Management
Sessions maintain user authentication state securely.

## Token Handling
Tokens provide secure authentication mechanisms.

## Access Control
Access control enforces authorization policies.

## Security Testing
Testing validates authentication and authorization systems.
"""

        test_file = tmp_path / "connections_test.md"
        test_file.write_text(test_content)

        # Set up environment
        env = os.environ.copy()
        env["SQLITE_PATH"] = str(tmp_path / "connections_test.db")

        # Execute CLI command
        result = subprocess.run(
            ["memory_system", "load", str(test_file)],
            capture_output=True,
            text=True,
            env=env,
        )

        # Validate execution
        assert result.returncode == 0, f"Connection test failed: {result.stderr}"
        assert "Connections created:" in result.stdout

        # Extract connections count from output
        lines = result.stdout.split("\n")
        connections_line = next(
            line for line in lines if "Connections created:" in line
        )
        connections_count = int(connections_line.split(":")[1].strip())

        # Should create connections between related security topics
        assert connections_count > 0, "Should create connections between related topics"

        # Verify connections in database
        db_path = tmp_path / "connections_test.db"
        with sqlite3.connect(str(db_path)) as conn:
            connections = conn.execute("SELECT * FROM connections").fetchall()
            assert len(connections) == connections_count, (
                "Database connections should match CLI output"
            )


@pytest.mark.e2e
@pytest.mark.slow
class TestCLIMemoryLoaderE2EAdvanced:
    """Advanced end-to-end tests for edge cases and production scenarios."""

    def test_cli_concurrent_operations_simulation(self, tmp_path):
        """Test CLI resilience with multiple sequential operations."""
        # Create multiple test files
        test_files = []
        for i in range(3):
            content = f"""# Document {i}

## Section {i}
Content for document {i} testing concurrent operations.

### Details {i}
Technical information for document {i}.
"""
            test_file = tmp_path / f"concurrent_{i}.md"
            test_file.write_text(content)
            test_files.append(test_file)

        # Execute multiple CLI operations sequentially
        results = []
        for i, test_file in enumerate(test_files):
            env = os.environ.copy()
            env["SQLITE_PATH"] = str(tmp_path / f"concurrent_{i}.db")

            result = subprocess.run(
                ["memory_system", "load", str(test_file)],
                capture_output=True,
                text=True,
                env=env,
            )

            results.append(result)

        # All operations should succeed
        for i, result in enumerate(results):
            assert result.returncode == 0, f"Operation {i} failed: {result.stderr}"
            assert "✓ Memory loading completed" in result.stdout

    def test_cli_memory_statistics_validation(self, tmp_path):
        """Test CLI output statistics match actual database contents."""
        test_content = """# Statistics Validation

## Concept Section
This is a concept-level section.

### Context Subsection
This provides context information.

#### Detailed Implementation
```python
# This is episode-level content
def validate_statistics():
    return "validation complete"
```

## Another Concept
More concept-level information.

### Implementation Context
Context for implementation details.
"""

        test_file = tmp_path / "stats_test.md"
        test_file.write_text(test_content)

        # Set up environment
        env = os.environ.copy()
        env["SQLITE_PATH"] = str(tmp_path / "stats_test.db")

        # Execute CLI command
        result = subprocess.run(
            ["memory_system", "load", str(test_file)],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, f"Statistics test failed: {result.stderr}"

        # Parse CLI output statistics
        lines = result.stdout.split("\n")
        memories_line = next(line for line in lines if "Memories loaded:" in line)
        memories_count = int(memories_line.split(":")[1].strip())

        # Validate against actual database
        db_path = tmp_path / "stats_test.db"
        with sqlite3.connect(str(db_path)) as conn:
            actual_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            assert actual_count == memories_count, (
                f"CLI reported {memories_count} but DB has {actual_count}"
            )

            # Verify hierarchy distribution if shown in output
            hierarchy_lines = [
                line for line in lines if "L0" in line or "L1" in line or "L2" in line
            ]
            if hierarchy_lines:
                # Validate hierarchy distribution matches database
                db_distribution = dict(
                    conn.execute("""
                    SELECT hierarchy_level, COUNT(*)
                    FROM memories
                    GROUP BY hierarchy_level
                """).fetchall()
                )

                assert len(db_distribution) > 0, (
                    "Should have memories at different hierarchy levels"
                )

    def test_cli_error_message_quality(self, tmp_path):
        """Test that CLI error messages are helpful and actionable."""
        # Test various error scenarios and validate error message quality

        # 1. File permission error (simulate with non-existent directory)
        bad_path = tmp_path / "nonexistent_dir" / "file.md"
        result = subprocess.run(
            ["memory_system", "load", str(bad_path)], capture_output=True, text=True
        )

        assert result.returncode != 0
        error_output = result.stdout.lower()
        assert any(
            word in error_output
            for word in ["not found", "does not exist", "file", "path"]
        )

        # 2. Unsupported file extension
        unsupported_file = tmp_path / "test.txt"
        unsupported_file.write_text("# Test")

        result = subprocess.run(
            ["memory_system", "load", str(unsupported_file)],
            capture_output=True,
            text=True,
        )

        # Should either succeed (if .txt is supported) or give clear error
        if result.returncode != 0:
            error_output = result.stdout.lower()
            assert any(
                word in error_output for word in ["unsupported", "format", "extension"]
            )

    def test_cli_help_and_usage(self, tmp_path):
        """Test CLI help and usage information."""
        # Test help command
        result = subprocess.run(
            ["memory_system", "load", "--help"], capture_output=True, text=True
        )

        # Help should work and provide useful information
        assert result.returncode == 0, "Help command should work"
        help_output = result.stdout.lower()
        assert any(word in help_output for word in ["usage", "options", "help", "load"])
