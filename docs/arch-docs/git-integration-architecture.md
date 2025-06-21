# Git Integration Architecture Plan

## Executive Overview

This document specifies the architecture for integrating git repository history analysis into the cognitive memory system. The integration leverages the existing MemoryLoader interface to store git commits directly as cognitive memories, enabling LLMs to automatically understand development history, file relationships, and project evolution.

**Key Features:**
- **Direct Commit Storage**: Stores each git commit as a cognitive memory with full metadata
- **File Change Tracking**: Preserves detailed file change information (additions, deletions, modifications)
- **Memory Integration**: Commits stored as cognitive memories using the existing MemoryLoader interface

## Core Components

### 1. GitHistoryLoader
**Responsibility**: Load git commits as cognitive memories from git repository history
- Implements the existing `MemoryLoader` interface
- Uses CommitLoader to convert git commits to CognitiveMemory objects
- Transforms git commit data into memory objects with deterministic IDs
- Supports both full repository analysis and incremental updates

**Key Dependencies**:
- CommitLoader (commit to memory conversion)
- GitHistoryMiner (data extraction)
- Existing CognitiveConfig

**Memory Architecture**:
- Uses deterministic commit IDs: `git::commit::<commit_hash>`
- Each commit becomes one memory with full metadata
- File changes embedded in memory content as natural language

### 2. GitHistoryMiner
**Responsibility**: Raw data extraction from git repository
- Execute git commands to gather commit history
- Parse commit data, file changes, and timestamps
- Return structured Commit objects with FileChange details

**Output Data Structures**:
- Commit: commit_hash, message, author, timestamp, files_changed list
- FileChange: file_path, change_type, lines_added, lines_deleted

### 3. CommitLoader
**Responsibility**: Transform git commits into cognitive memories
- Convert Commit objects to CognitiveMemory format
- Generate natural language descriptions of commits
- Embed file change information in memory content
- Assign appropriate hierarchy levels and importance scores

**Memory Content Generation**:
- Commit Summary: Natural language description of commit purpose
- File Changes: Detailed list of modified files with change types
- Context Information: Author, timestamp, commit message integration

### 4. Security and Validation
**Responsibility**: Ensure safe processing of git data
- Validate commit hashes, file paths, and metadata
- Sanitize input data to prevent injection attacks
- Limit data sizes to prevent memory exhaustion
- Filter sensitive information from commit content


## Data Flow Architecture

### Complete Data Flow
```
Git Repository (.git/)
        ↓
GitHistoryMiner.extract_commits()
        ↓
List[Commit] with FileChange details
        ↓
CommitLoader.convert_to_memories()
        ↓
Commit Descriptions (natural language text with metadata)
        ↓
GitHistoryLoader.load_from_source()
        ↓
List[CognitiveMemory] with embedded commit data
        ↓
CognitiveSystem.load_memories_from_source()
        ↓
Existing Memory Pipeline:
• Multi-dimensional encoding (Sentence-BERT + dimensions)
• Hierarchical storage (Qdrant L0/L1/L2 collections)
• Connection extraction and storage (SQLite)
• Indexing and retrieval preparation
```

### Integration-Specific Data Flow

**Repository Loading:**
```
CLI Command: ./scripts/load_project_content.sh --git-only
        ↓
GitHistoryLoader instantiation
        ↓
GitHistoryLoader.validate_source() [verify .git exists]
        ↓
GitHistoryLoader.load_from_source() [extract patterns with confidence scoring]
        ↓
CognitiveSystem.load_memories_from_source() [existing]
        ↓
Memories stored with deterministic IDs in Qdrant + SQLite [existing]
        ↓
Available for retrieval via existing interfaces [existing]
```

## Key Methods and Responsibilities

### GitHistoryLoader Methods

**validate_source(source_path: str) -> bool**
- Must verify source_path contains a .git directory
- Must check git repository accessibility
- Must return boolean validation result

**load_from_source(source_path: str, **kwargs) -> List[CognitiveMemory]**
- Must extract all git commits from repository
- Must convert commits to CognitiveMemory objects with deterministic IDs
- Must embed commit metadata in natural language content
- Must assign appropriate hierarchy levels (L1 for significant commits, L2 for routine commits)
- Must return list compatible with existing memory pipeline


**get_supported_extensions() -> List[str]**
- Must return empty list (git repos don't have file extensions)

**extract_connections(memories: List[CognitiveMemory]) -> List[tuple]**
- Must identify relationships between git pattern memories
- Must return connection tuples in existing format

### GitHistoryMiner Methods

**extract_commits(repo_path: str, time_window: str) -> List[Commit]**
- Must execute git log commands to gather commit data
- Must parse commit messages, file changes, and metadata
- Must filter commits by time window and relevance
- Must include detailed file change information (lines added/deleted)

**parse_commit_data(raw_commit: str) -> Commit**
- Must parse git log output into structured Commit objects
- Must extract author, timestamp, hash, and message
- Must parse file changes with change types and line counts

**validate_and_sanitize(commit: Commit) -> Commit**
- Must validate commit hash format and data integrity
- Must sanitize commit messages and file paths
- Must enforce size limits on commit data

### CommitLoader Methods

**convert_to_memories(commits: List[Commit]) -> List[CognitiveMemory]**
- Must convert each commit to a CognitiveMemory object
- Must generate natural language descriptions of commits
- Must embed file change details in memory content
- Must assign hierarchy levels based on commit significance
- Must create deterministic memory IDs from commit hashes

**generate_commit_description(commit: Commit) -> str**
- Must create readable description of commit purpose
- Must include file changes and their types
- Must embed metadata (author, timestamp) naturally
- Must make content searchable through existing retrieval

**assess_commit_importance(commit: Commit) -> float**
- Must calculate importance score based on files changed
- Must consider commit message indicators (fix, feature, refactor)
- Must account for file change volume and scope
- Must assign appropriate hierarchy level (L0/L1/L2)

### Security and Validation Methods

**validate_repository_path(repo_path: str) -> bool**
- Must verify the path contains a valid git repository
- Must check for .git directory existence
- Must validate path safety and accessibility

**sanitize_git_data(data: str) -> str**
- Must remove potentially harmful characters
- Must limit string lengths to prevent memory issues
- Must preserve essential git information while ensuring safety

**validate_commit_hash(hash_str: str) -> bool**
- Must verify commit hash format (40-character hex)
- Must check for valid git hash patterns
- Must reject malformed or suspicious hashes

## System Structure

### File Organization
```
cognitive_memory/
├── loaders/
│   ├── __init__.py                    # Add GitHistoryLoader export
│   ├── markdown_loader.py             # Existing
│   └── git_loader.py                  # GitHistoryLoader implementation
└── git_analysis/                      # Git analysis module
    ├── __init__.py
    ├── commit.py                      # Commit and FileChange data classes
    ├── commit_loader.py               # CommitLoader for memory conversion
    ├── history_miner.py               # GitHistoryMiner for data extraction
    └── security.py                    # Security validation and sanitization
```

### Memory Content Embedding Strategy

Since the system embeds all commit information into memory content text rather than separate metadata fields, git commits must be embedded as natural language:

**Commit Memory Embedding**:
```
"Git commit abc1234 by John Doe on 2024-01-15: 'Fix authentication timeout in Redis connection'. Modified 3 files: auth/middleware.py (15 lines added, 3 deleted), auth/config.py (8 lines added, 2 deleted), tests/test_auth.py (25 lines added). This commit addresses timeout issues by increasing Redis connection pool size and adjusting timeout parameters."
```

**Feature Commit Embedding**:
```
"Git commit def5678 by Jane Smith on 2024-01-16: 'Add user profile caching system'. Created 2 files, modified 4 files: users/cache.py (156 lines added), users/models.py (12 lines added, 4 deleted), users/views.py (23 lines added, 8 deleted), users/serializers.py (18 lines added), settings/base.py (3 lines added), requirements.txt (1 line added). This feature commit introduces Redis-based caching for user profiles to improve API response times."
```

**Bug Fix Commit Embedding**:
```
"Git commit ghi9012 by Bob Wilson on 2024-01-17: 'Fix memory leak in background tasks'. Modified 1 file: tasks/background.py (8 lines added, 15 deleted). This bug fix resolves memory accumulation by properly closing database connections in background task workers."
```

## Integration Benefits

### For LLM Context Enhancement
- Automatic access to complete development history during debugging
- Understanding of file evolution and change patterns over time
- Context about when and why specific changes were made
- Enhanced understanding of codebase architecture through commit history
- Direct access to actual development decisions and rationales

### For Development Workflow
- Zero-configuration commit history access from existing git repository
- Integration with existing memory retrieval mechanisms
- Compatibility with current CLI and MCP interfaces
- Batch loading via project scripts
- Real commit data instead of derived statistical patterns

## Immutable Memory Architecture

### Commit Identity and Storage
Git commits are **immutable historical records** that provide stable memories:

**Deterministic Commit IDs:**
```python
# Commit memories
memory_id = f"git::commit::{commit_hash}"

# File-based grouping for retrieval
file_tag = f"git::file::{file_path}"

# Author-based grouping
author_tag = f"git::author::{author_email}"
```

**Storage Operations:**
- Each commit becomes one memory with stable commit hash ID
- No updates needed - commits are immutable historical facts
- Qdrant stores vectors with commit metadata in payload
- SQLite stores commit relationships and file associations
- New commits simply add new memories without affecting existing ones

**Incremental Loading:**
- Only load new commits since last update
- Use git log with --since parameter for efficiency
- Avoid duplicate storage through commit hash checking
- Maintain chronological order for temporal relationships

### Payload Structure
```python
payload = {
    "commit_hash": "abc1234567890",
    "author": "john.doe@example.com",
    "timestamp": "2024-01-20T10:30:00Z",
    "files_changed": ["auth/middleware.py", "auth/config.py"],
    "change_types": ["M", "M"],
    "lines_added": 23,
    "lines_deleted": 5,
    "is_merge": False,
    "is_fix": True
}
