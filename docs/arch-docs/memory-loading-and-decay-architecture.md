# Memory Loading and Decay Architecture

## Overview

This document describes the memory loading types, metadata fields, and context-aware decay system implemented in the Heimdall Cognitive Memory System. The system uses deterministic content-type detection and activity-based decay rates to provide intelligent memory management that adapts to project workflows.

## Memory Loading Types

### Core Memory Sources

The system implements **5 distinct memory source types**, each with specific characteristics and decay profiles:

#### 1. Git Commits (`git_commit`)
- **Loader**: `GitHistoryLoader` → `CommitLoader`
- **Source Files**:
  - `cognitive_memory/loaders/git_loader.py`
  - `cognitive_memory/git_analysis/commit_loader.py`
- **Metadata Set**: Line 244 in `commit_loader.py`
- **Hierarchy Level**: Always L2 (Episode)
- **Content**: Natural language descriptions of git commits with file changes
- **Decay Profile**: 1.2 (moderate-fast decay - code becomes outdated)

#### 2. Documentation (`documentation`)
- **Loader**: `MarkdownMemoryLoader`
- **Source Files**:
  - `cognitive_memory/loaders/markdown_loader.py`
  - `cognitive_memory/loaders/markdown/memory_factory.py`
- **Metadata Set**: Line 115 in `memory_factory.py`
- **Hierarchy Level**: L0/L1/L2 based on linguistic analysis
- **Content**: Processed markdown content with hierarchical context
- **Decay Profile**: 0.2 (slow decay - documentation stays relevant)

#### 3. Session Lessons (`session_lesson`)
- **Source**: MCP `session_lessons` tool
- **Source File**: `interfaces/mcp_server.py`
- **Metadata Set**: Line 428 in `mcp_server.py`
- **Hierarchy Level**: Always L1 (Context)
- **Memory Type**: Always semantic
- **Content**: User-provided insights and learnings from sessions
- **Decay Profile**: 0.2 (very slow decay - insights persist long-term)

#### 4. Store Memory (`store_memory`)
- **Source**: MCP `store_memory` tool
- **Source File**: `interfaces/mcp_server.py`
- **Metadata Set**: Line 320 in `mcp_server.py`
- **Hierarchy Level**: User-specified or default L2
- **Memory Type**: User-specified or default episodic
- **Content**: User-provided experiences and context
- **Decay Profile**: 1.0 (normal decay)

#### 5. Manual Entry (`manual_entry`)
- **Source**: Direct API/CLI input (fallback)
- **Source File**: `cognitive_memory/core/cognitive_system.py`
- **Metadata Set**: Line 121 in `cognitive_system.py`
- **Hierarchy Level**: Context-specified or heuristic-determined
- **Content**: Direct text input
- **Decay Profile**: 1.0 (normal decay)

### Memory Loader Interface

All memory loaders implement the `MemoryLoader` interface defined in `cognitive_memory/core/interfaces.py`:

```python
class MemoryLoader:
    def validate_source(self, source_path: str) -> bool
    def load_from_source(self, source_path: str, **kwargs) -> List[CognitiveMemory]
    def get_supported_extensions(self) -> List[str]
    def extract_connections(self, memories: List[CognitiveMemory]) -> List[tuple]
```

**Current Implementations**:
- `MarkdownMemoryLoader` - Processes .md, .markdown, .mdown, .mkd files
- `GitHistoryLoader` - Processes git repositories (any directory with .git)

## Metadata Fields

### Standard Metadata Fields

All cognitive memories include these base metadata fields:

```python
{
    "id": str,                    # Unique memory identifier
    "hierarchy_level": int,       # 0=Concept, 1=Context, 2=Episode
    "strength": float,            # Memory strength (0.0-1.0)
    "source": str,                # Creation source information
    "source_type": str,           # CRITICAL: Deterministic content type
    "created_date": str,          # ISO timestamp of creation
    "last_accessed": str,         # ISO timestamp of last access
    "access_count": int,          # Number of times accessed
    "importance_score": float,    # Importance rating (0.0-1.0)
    "tags": List[str] | None      # Optional categorization tags
}
```

### Source-Specific Metadata

#### Git Commit Metadata
```python
{
    "source_type": "git_commit",
    "commit_hash": str,           # Full git commit hash
    "author_name": str,           # Commit author name
    "author_email": str,          # Commit author email
    "affected_files": List[str],  # List of modified file paths
    "lines_added": int,           # Total lines added
    "lines_deleted": int,         # Total lines deleted
    "commit_message": str         # Original commit message
}
```

#### Documentation Metadata
```python
{
    "source_type": "documentation",
    "title": str,                 # Document/section title
    "source_path": str,           # File path
    "header_level": int,          # Markdown header level (1-6)
    "hierarchical_path": str,     # Document structure path
    "linguistic_features": dict,  # Content analysis results
    "document_name": str          # Source document name
}
```

#### Session Lesson Metadata
```python
{
    "source_type": "session_lesson",
    "lesson_type": str,           # discovery, pattern, solution, warning, context
    "session_context": str,       # What was being worked on
    "importance_level": str,      # low, medium, high, critical
    "stored_at": str             # Creation timestamp
}
```

#### Store Memory Metadata
```python
{
    "source_type": "store_memory",
    "context": dict,              # User-provided context
    "memory_type": str,           # episodic or semantic
    "importance_score": float,    # User-specified importance
    "tags": List[str]            # User-specified tags
}
```

## Context-Aware Memory Decay System

### Decay Rate Calculation Flow

The system implements a sophisticated 3-layer decay calculation:

```
Base Decay Rate × Activity Multiplier × Content-Type Multiplier = Final Decay Rate
```

### Layer 1: Activity-Based Scaling

**Implementation**: `cognitive_memory/storage/project_activity_tracker.py`

**Activity Score Calculation**:
```python
activity_score = 0.6 * commit_score + 0.4 * access_score

# Where:
# commit_score = recent_commits / (max_commits_per_day * window_days)
# access_score = recent_accesses / (max_accesses_per_day * window_days)
```

**Activity Multipliers**:
- **High Activity** (>0.7): 2.0× faster decay (active development)
- **Normal Activity** (0.2-0.7): 1.0× normal decay
- **Low Activity** (<0.2): 0.1× slower decay (dormant project)

### Layer 2: Content-Type Decay Profiles

**Implementation**: `cognitive_memory/core/config.py` (lines 154-167)

**Decay Profile Configuration**:
```python
decay_profiles = {
    # Source-based content types (deterministic)
    "git_commit": 1.2,           # Moderate-fast decay
    "session_lesson": 0.2,       # Very slow decay
    "store_memory": 1.0,         # Normal decay
    "documentation": 0.2,        # Slow decay
    "manual_entry": 1.0,         # Normal decay

    # Hierarchy level fallbacks
    "L0_concept": 0.3,           # Very slow decay
    "L1_context": 0.8,           # Moderate decay
    "L2_episode": 1.0            # Base rate decay
}
```

### Layer 3: Combined Decay Application

**Implementation**: `cognitive_memory/storage/dual_memory.py` (lines 241-289)

**Decay Calculation Process**:
1. **Base Time Calculation**: `hours_elapsed = (now - memory.timestamp) / 3600`
2. **Activity Scaling**: Apply activity-based multiplier if available
3. **Content-Type Scaling**: Apply content-type multiplier using deterministic detection
4. **Exponential Decay**: `strength = initial_strength × exp(-effective_rate × time_in_days)`

### Deterministic Content-Type Detection

**Implementation**: `cognitive_memory/core/config.py` (lines 357-383)

**Detection Strategy**:
1. **Primary**: Use explicit `source_type` from memory metadata
2. **Fallback**: Use hierarchy level if `source_type` missing
3. **Final Fallback**: Default to `"manual_entry"`

This approach ensures 100% reliable content-type identification without pattern matching.

## Memory Store Architecture

### Dual Memory System

The system implements separate episodic and semantic memory stores:

- **EpisodicMemoryStore**: Fast decay rate (default 0.05/day), cleanup implemented but unused
- **SemanticMemoryStore**: Slow decay rate (default 0.01/day), long-term retention

### Consolidation Process

**Access Pattern Tracking**:
- Frequency analysis over configurable time windows
- Recency scoring with exponential decay
- Distribution analysis for repeated access patterns

**Consolidation Criteria**:
- Minimum access frequency thresholds
- Distributed access patterns over time
- Combined consolidation score calculation

### Memory Cleanup System

**Implementation Status**: The memory cleanup system is **implemented but not integrated** into the production system.

**Cleanup Logic** (`cognitive_memory/storage/dual_memory.py:291-324`):
- **Location**: `EpisodicMemoryStore.cleanup_expired_memories()`
- **Criteria**: Removes memories that meet ANY of these conditions:
  - Age > `max_retention_days` (default: 30 days)
  - Strength < 0.01 (completely decayed)
  - Importance score < 0.01 (negligible importance)
- **Scope**: Only episodic memories (semantic memories never expire)

**Current Status**:
- ✅ **Implementation**: Cleanup logic is coded and tested
- ❌ **Integration**: No production code calls cleanup methods
- ❌ **Scheduling**: No background process or scheduler exists
- ❌ **CLI Commands**: No manual cleanup commands available
- ⚠️ **Result**: Episodic memories accumulate indefinitely in database

**Configuration**:
- `cleanup_interval_hours: 24` - Defined but unused
- `max_retention_days: 30` - Used by cleanup logic when called
- Strength/importance thresholds: 0.01 (hardcoded)

**Evidence**:
```bash
# Cleanup method only appears in:
# - Unit tests: tests/unit/test_dual_memory.py
# - Integration tests: tests/integration/test_storage_pipeline.py
# - Method definitions: cognitive_memory/storage/dual_memory.py
# - Never in: MCP server, CLI, cognitive system, or any scheduler
```

## Configuration Management

### Environment Variables

**Activity Tracking Configuration**:
```bash
ACTIVITY_WINDOW_DAYS=30
MAX_COMMITS_PER_DAY=3
MAX_ACCESSES_PER_DAY=100
ACTIVITY_COMMIT_WEIGHT=0.6
ACTIVITY_ACCESS_WEIGHT=0.4
HIGH_ACTIVITY_THRESHOLD=0.7
LOW_ACTIVITY_THRESHOLD=0.2
HIGH_ACTIVITY_MULTIPLIER=2.0
NORMAL_ACTIVITY_MULTIPLIER=1.0
LOW_ACTIVITY_MULTIPLIER=0.1
```

**Decay Profile Configuration**:
```bash
DECAY_PROFILE_GIT_COMMIT=1.2
DECAY_PROFILE_SESSION_LESSON=0.2
DECAY_PROFILE_STORE_MEMORY=1.0
DECAY_PROFILE_DOCUMENTATION=0.2
DECAY_PROFILE_MANUAL_ENTRY=1.0
DECAY_PROFILE_L0_CONCEPT=0.3
DECAY_PROFILE_L1_CONTEXT=0.8
DECAY_PROFILE_L2_EPISODE=1.0
```

### Validation

**Configuration Validation** (`cognitive_memory/core/config.py` lines 463-586):
- Activity weights must sum to 1.0
- Activity thresholds must be ordered correctly
- All multipliers must be positive
- Decay profiles must be valid floating-point numbers

## Integration Points

### MCP Protocol Integration

The system provides 4 MCP tools for Claude Code integration:
- `store_memory` - Creates memories with user context
- `recall_memories` - Retrieves memories with decay-adjusted scores
- `session_lessons` - Records metacognitive insights
- `memory_status` - System health and statistics

### CLI and Script Integration

**Memory System CLI**:
- `memory_system load` - Markdown document processing
- `memory_system git-load` - Git repository analysis
- `memory_system shell` - Interactive memory operations

**Project Setup Scripts**:
- `scripts/load_project_content.sh` - Bulk content loading
- `scripts/setup_project_memory.sh` - Docker container setup

## Performance Considerations

### Caching Strategy

**Activity Calculation Caching**:
- 5-minute TTL cache for activity score calculations
- Batch processing for multiple memories
- Efficient git log parsing with limited history depth

### Database Optimization

**SQLite Performance**:
- WAL mode for concurrent access
- Indexed queries on timestamp and strength
- Manual cleanup of expired memories (implemented but not automatically triggered)

### Memory Efficiency

**Vector Storage**:
- Qdrant collections with project isolation
- Optimized embedding dimensions (384 + cognitive dimensions)
- Sparse activation networks for retrieval
