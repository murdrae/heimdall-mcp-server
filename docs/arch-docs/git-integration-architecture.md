# Git Integration Architecture Plan

## Executive Overview

This document specifies the architecture for integrating git repository history analysis into the cognitive memory system. The integration leverages the existing MemoryLoader interface to extract development patterns from git history and store them as cognitive memories, enabling LLMs to automatically understand codebase relationships, maintenance hotspots, and solution patterns.

**Key Features:**
- **Mutable Pattern Memories**: Git patterns are statistical aggregates that update incrementally using stable-ID upserts
- **Live Development Integration**: Post-commit hooks provide real-time pattern updates during development
- **Pattern Confidence Scoring**: Quality metrics embedded in memory content ensure reliable pattern detection

## Core Components

### 1. GitHistoryLoader
**Responsibility**: Extract structured patterns from git repository history
- Implements the existing `MemoryLoader` interface with mutable memory support
- Analyzes git commits, file changes, and commit messages
- Transforms git data into `CognitiveMemory` objects with deterministic IDs
- Supports both full repository analysis and incremental updates

**Key Dependencies**:
- GitHistoryMiner (data extraction)
- PatternExtractor (pattern analysis with confidence scoring)
- GitHookManager (post-commit hook installation)
- Existing CognitiveConfig

**Mutable Memory Architecture**:
- Uses deterministic pattern IDs: `git::cochange::<hash(file_a|file_b)>`
- Supports in-place updates via Qdrant upserts when patterns evolve
- Maintains pattern confidence and quality scores in memory payload

### 2. GitHistoryMiner
**Responsibility**: Raw data extraction from git repository
- Execute git commands to gather commit history
- Parse commit data, file changes, and timestamps
- Filter and preprocess git data for pattern analysis

**Output Data Structures**:
- CommitEvent: commit_hash, files_changed, message, timestamp, author
- FileChangeEvent: file_path, change_type, commit_hash
- ProblemCommit: commit_hash, message, files_changed (for fix/bug commits)

### 3. PatternExtractor
**Responsibility**: Transform raw git data into meaningful patterns
- Analyze co-change relationships between files
- Identify maintenance hotspots from problem commit frequency
- Extract solution patterns from fix commits
- Calculate pattern strength and relevance metrics

**Pattern Types with Confidence Scoring**:
- CoChangePattern: files that frequently change together (support count, confidence score, recency weight)
- MaintenanceHotspot: files with high problem frequency (hotspot score, trend analysis, quality rating)
- SolutionPattern: successful fix approaches for specific problems (success rate, applicability confidence)

### 4. GitPatternEmbedder
**Responsibility**: Convert git patterns into memory content suitable for embedding
- Generate natural language descriptions of patterns with embedded confidence metrics
- Structure pattern data for embedding in memory content text
- Ensure patterns are discoverable through existing retrieval mechanisms
- Embed quality scores and confidence indicators directly in natural language

### 5. GitHookManager (New)
**Responsibility**: Manage git post-commit hooks for live integration
- Install and configure post-commit hooks in target repositories
- Handle incremental pattern updates triggered by new commits
- Provide hook templates and configuration management
- Support multiple repositories with centralized pattern updates

## Data Flow Architecture

### Complete Data Flow
```
Git Repository (.git/)
        ↓
GitHistoryMiner.extract_commit_data()
        ↓
Raw Git Data (commits, file changes, messages)
        ↓
PatternExtractor.extract_patterns()
        ↓
Structured Patterns (cochange, hotspots, solutions)
        ↓
GitPatternEmbedder.embed_patterns()
        ↓
Pattern Descriptions (natural language text)
        ↓
GitHistoryLoader.load_from_source()
        ↓
List[CognitiveMemory] with embedded pattern data
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

**Initial Repository Setup:**
```
CLI Command: memory_system load /repo --loader-type=git
        ↓
CognitiveCLI.load_memories() [existing method]
        ↓
GitHistoryLoader instantiation [new]
        ↓
GitHistoryLoader.validate_source() [verify .git exists]
        ↓
GitHistoryLoader.load_from_source() [extract patterns with confidence scoring]
        ↓
GitHookManager.install_post_commit_hook() [setup live updates]
        ↓
CognitiveSystem.load_memories_from_source() [existing]
        ↓
Memories stored with deterministic IDs in Qdrant + SQLite [existing]
        ↓
Available for retrieval via existing interfaces [existing]
```

**Incremental Update Flow (Post-Commit):**
```
Git Commit → Post-commit hook triggers
        ↓
memory_system git-refresh --since HEAD~1
        ↓
GitHistoryLoader.load_incremental(since_commit)
        ↓
Pattern updates with confidence recalculation
        ↓
Qdrant upsert operations (same deterministic IDs)
        ↓
Updated patterns immediately available for retrieval
```

## Key Methods and Responsibilities

### GitHistoryLoader Methods

**validate_source(source_path: str) -> bool**
- Must verify source_path contains a .git directory
- Must check git repository accessibility
- Must return boolean validation result

**load_from_source(source_path: str, **kwargs) -> List[CognitiveMemory]**
- Must extract all git patterns from repository with confidence scoring
- Must convert patterns to CognitiveMemory objects with deterministic IDs
- Must embed confidence metrics in natural language content
- Must assign appropriate hierarchy levels (L1 for patterns, L2 for solutions)
- Must return list compatible with existing memory pipeline

**load_incremental(source_path: str, since_commit: str) -> List[CognitiveMemory]**
- Must extract only new patterns since specified commit
- Must update existing pattern confidence scores and support counts
- Must use same deterministic IDs for upsert operations
- Must handle pattern evolution (strengthen/weaken existing patterns)

**install_git_hooks(source_path: str) -> bool**
- Must install post-commit hook in repository
- Must configure hook to call git-refresh command
- Must handle existing hooks gracefully (append, don't overwrite)
- Must return success status

**get_supported_extensions() -> List[str]**
- Must return empty list (git repos don't have file extensions)

**extract_connections(memories: List[CognitiveMemory]) -> List[tuple]**
- Must identify relationships between git pattern memories
- Must return connection tuples in existing format

### GitHistoryMiner Methods

**extract_commit_history(repo_path: str, time_window: str) -> List[CommitEvent]**
- Must execute git log commands to gather commit data
- Must parse commit messages, file changes, and metadata
- Must filter commits by time window and relevance

**extract_problem_commits(commits: List[CommitEvent]) -> List[ProblemCommit]**
- Must identify commits containing problem indicators (fix, bug, error)
- Must extract problem context from commit messages
- Must associate problems with affected files

**extract_file_changes(commits: List[CommitEvent]) -> List[FileChangeEvent]**
- Must parse git diff data for each commit
- Must track file modification patterns over time
- Must maintain file path consistency across renames

### PatternExtractor Methods

**extract_cochange_patterns(file_changes: List[FileChangeEvent]) -> List[CoChangePattern]**
- Must build co-occurrence matrix for file changes
- Must identify file pairs with significant co-change frequency
- Must calculate pattern strength, statistical confidence, and recency weighting
- Must assign quality scores based on pattern consistency and reliability
- Must filter patterns below minimum confidence thresholds

**extract_maintenance_hotspots(problem_commits: List[ProblemCommit]) -> List[MaintenanceHotspot]**
- Must count problem frequency per file with trend analysis
- Must calculate hotspot confidence scores based on problem density
- Must identify files exceeding dynamic hotspot thresholds
- Must assign quality ratings based on problem type consistency
- Must collect recent problem examples with confidence indicators

**extract_solution_patterns(problem_commits: List[ProblemCommit]) -> List[SolutionPattern]**
- Must correlate problem types with solution approaches
- Must calculate solution success rates and applicability confidence
- Must identify successful fix patterns with quality scoring
- Must extract actionable solution insights with confidence indicators
- Must rank solutions by effectiveness and reliability metrics

### GitPatternEmbedder Methods

**embed_cochange_pattern(pattern: CoChangePattern) -> str**
- Must generate natural language description of file relationships with confidence indicators
- Must embed pattern confidence score, support count, and quality rating in text
- Must include recency weighting and trend information
- Must create content suitable for Sentence-BERT embedding with quality context

**embed_hotspot_pattern(hotspot: MaintenanceHotspot) -> str**
- Must describe maintenance characteristics and risk factors
- Must include recent problem examples and warning indicators
- Must embed actionable maintenance guidance

**embed_solution_pattern(solution: SolutionPattern) -> str**
- Must describe problem type and successful solution approach
- Must include specific file and change information
- Must create retrievable solution guidance

## System Structure

### File Organization
```
cognitive_memory/
├── loaders/
│   ├── __init__.py                    # Add GitHistoryLoader export
│   ├── markdown_loader.py             # Existing
│   └── git_loader.py                  # New: GitHistoryLoader implementation
├── git/                               # New module
│   ├── __init__.py
│   ├── history_miner.py               # GitHistoryMiner
│   ├── pattern_extractor.py           # PatternExtractor with confidence scoring
│   ├── pattern_embedder.py            # GitPatternEmbedder with quality metrics
│   └── hook_manager.py                # GitHookManager for post-commit integration
└── interfaces/
    ├── cli.py                         # Modified: add git commands and hook management
    └── git_commands.py                # New: git-specific CLI commands
```

### Memory Content Embedding Strategy

Since the system embeds all pattern information into memory content text rather than separate metadata fields, git patterns must be embedded as natural language:

**Co-change Pattern Embedding with Confidence**:
```
"Development pattern (confidence: 92%, quality: high): Files auth/middleware.py and auth/jwt.py frequently change together (12 co-commits over 6 months, trend: increasing). Strong coupling indicates shared authentication logic. When debugging authentication issues, examine both files together. Pattern strength: 0.85, last updated: commit abc123."
```

**Maintenance Hotspot Embedding with Quality Scoring**:
```
"Maintenance hotspot (hotspot score: 8.5/10, trend: worsening): File payment/gateway.py has high change frequency (23 bug fixes in 6 months, confidence: 94%). Recent issues include timeout handling (commit def456), validation errors (commit ghi789), and connection failures (commit jkl012). Exercise extreme caution when modifying this component - quality rating: requires immediate attention."
```

**Solution Pattern Embedding with Success Metrics**:
```
"Solution pattern (success rate: 89%, applicability: high): Authentication timeout errors typically resolved by adjusting Redis connection settings in auth/config.py and increasing timeout values in auth/middleware.py. Pattern verified across 8 successful fixes (commits abc123, def456, ghi789). Confidence: 91%, effectiveness rating: proven approach."
```

## Integration Benefits

### For LLM Context Enhancement
- Automatic file relationship awareness with confidence indicators during debugging
- Proactive warnings about high-maintenance areas with quality ratings
- Solution pattern suggestions with success rates and reliability metrics
- Enhanced understanding of codebase architecture with trend analysis
- Quality-filtered pattern retrieval prevents noise from low-confidence patterns

### For Development Workflow
- Zero-configuration pattern discovery from existing git history
- **Live development integration** via post-commit hooks for real-time updates
- Continuous learning from development activity with incremental pattern evolution
- Integration with existing memory retrieval mechanisms
- Compatibility with current CLI and MCP interfaces
- Automated git hook installation and management

## Mutable Memory Architecture

### Pattern Identity and Updates
Git patterns are **mutable statistical aggregates** that require special handling:

**Deterministic Pattern IDs:**
```python
# Co-change patterns
pattern_id = f"git::cochange::{hashlib.sha256(f'{file_a}|{file_b}'.encode()).hexdigest()}"

# Hotspot patterns
pattern_id = f"git::hotspot::{hashlib.sha256(file_path.encode()).hexdigest()}"

# Solution patterns
pattern_id = f"git::solution::{hashlib.sha256(f'{problem_type}|{solution_approach}'.encode()).hexdigest()}"
```

**Upsert Operations:**
- When patterns evolve (e.g., co-change count increases), use same ID to update existing memory
- Qdrant supports native upsert operations: `client.upsert(collection, [PointStruct(id, vector, payload)])`
- SQLite handles updates via `ON CONFLICT DO UPDATE` clauses
- Pattern confidence and quality scores recalculated on each update

**Update Debouncing:**
- Prevent excessive updates: only upsert when significant changes occur
- Configurable thresholds: minimum confidence delta, minimum time interval
- Batch updates from multiple commits to reduce churn

### Payload Structure with Confidence
```python
payload = {
    "pattern_type": "cochange",
    "support": 13,
    "confidence": 0.92,
    "quality_score": 0.85,
    "recency_weight": 0.8,
    "updated_at": "2024-01-20T10:30:00Z",
    "trend": "increasing",
    "primary_file": "auth/jwt.py",
    "secondary_file": "auth/middleware.py"
}
```

## Implementation Phases

### Phase 1: Core Pattern Extraction with Confidence
- Implement GitHistoryMiner for data extraction with quality filtering
- Implement PatternExtractor with confidence scoring and quality metrics
- Create GitPatternEmbedder with embedded confidence indicators
- Implement deterministic ID generation for pattern identity

### Phase 2: Mutable Memory Integration
- Implement GitHistoryLoader with upsert support for pattern updates
- Add GitHookManager for post-commit hook installation and management
- Integrate incremental update commands with existing CLI
- Test mutable pattern storage and retrieval through existing pipeline

### Phase 3: Live Development Integration
- Implement post-commit hook templates and auto-installation
- Add git-specific CLI commands (git-refresh, install-hooks)
- Implement update debouncing and batch processing
- Add pattern quality monitoring and alerting

## Success Metrics

### Technical Success
- Git patterns successfully stored as mutable cognitive memories with stable IDs
- Patterns discoverable through existing retrieval mechanisms with confidence filtering
- Incremental updates working seamlessly via post-commit hooks
- No performance degradation in existing memory operations
- Pattern confidence and quality metrics embedded in retrievable content
- Seamless integration with current CLI and MCP interfaces

### Functional Success
- LLM receives relevant file relationship context with confidence indicators during debugging
- Maintenance hotspots appropriately flagged with quality ratings during code analysis
- Solution patterns surface during problem-solving sessions with success rate information
- Real-time pattern updates during active development sessions
- Development efficiency improvements measurable through usage patterns
- High-quality pattern filtering prevents noise in retrieval results

This architecture leverages the existing cognitive memory infrastructure while adding powerful git-based pattern recognition that enhances LLM understanding of codebases through historical development data.
