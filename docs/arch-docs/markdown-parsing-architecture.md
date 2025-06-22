# Memory Loading Architecture for Cognitive Memory System

## Overview

This document describes the architecture for loading external content into the cognitive memory system. The design introduces a formal `MemoryLoader` interface that enables pluggable content ingestion from various sources, with markdown documents as the first implementation.

## Architectural Approach

### Memory Loader Interface Pattern

Following the existing interface-driven design, we introduce a new abstraction layer:

```
External Source → MemoryLoader → CognitiveSystem → Storage Layer
                     ↓               ↓
                Parse Content    Orchestrate     → VectorStorage (Qdrant)
                Extract Relations    Storage     → MemoryStorage (SQLite)
                Validate Input                   → ConnectionGraph
```

### Key Architectural Components

1. **MemoryLoader Interface**: Abstract base for all content loaders
2. **MarkdownMemoryLoader**: Coordinator for markdown processing components
3. **Specialized Markdown Components**: Modular processing pipeline
   - **ContentAnalyzer**: Linguistic analysis and content classification
   - **DocumentParser**: Markdown parsing and tree construction
   - **MemoryFactory**: Memory creation and content assembly
   - **ConnectionExtractor**: Relationship analysis between memories
   - **ChunkProcessor**: Document chunking and grouping logic
4. **CognitiveSystem Integration**: Orchestrates loading process
5. **Content Classification Engine**: Determines L0/L1/L2 hierarchy
6. **Relationship Extraction Engine**: Builds connection graph

## Memory Classification Algorithm

### Feature Extraction (using spaCy en_core_web_md)
- `noun_ratio` = nouns / total_tokens
- `verb_ratio` = verbs / total_tokens
- `code_fraction` = code_tokens / total_tokens
- `imperative_score` = detection of command patterns ("Run...", "Install...")
- `header_level` = markdown header depth (0, 1, 2, 3...)

### Classification Rules
```python
if tokens < 5 and header_level ≤ 2:
    return L0  # Concepts (short headers, key terms)
elif code_fraction ≥ 0.60:
    return L2  # Episodes (code blocks)
elif imperative_score > 0.5:
    return L2  # Episodes (commands, procedures)
else:
    # Scoring model
    score_L0 = 1.2×noun_ratio - 0.8×verb_ratio - 0.8×header_level
    score_L2 = 1.0×verb_ratio + 0.7×imperative_score
    score_L1 = middle_ground
    return argmax(scores)
```

## Connection Strength Computation

```python
connection_strength = base_weight × relevance_score

base_weights = {
    'hierarchical': 0.80,  # Header contains subsection
    'sequential': 0.70,    # Step 1 → Step 2
    'associative': 0.50    # Related concepts
}

relevance_score = (
    0.45 × semantic_similarity +      # Cosine similarity
    0.25 × lexical_jaccard +          # Token overlap
    0.15 × structural_proximity +     # Document distance
    0.15 × explicit_references        # Markdown links
)
```

## Chunking Strategy

1. **Primary Split**: Split on `##` headers
2. **Secondary Split**: If chunk >250 tokens, split on `###` headers
3. **Code Extraction**: Pull out code blocks >8 lines as separate chunks
4. **Result**: ~25-35 chunks per 200-line document

## Example: CLAUDE.md Processing

**Input**: `## Development Commands` section
**Chunks Created**:
- `## Development Commands` → L1 Context (procedures)
- `python3 -m venv venv` → L2 Episode (specific command)
- `pytest` → L0 Concept (tool name)

**Connections**:
- L1(Dev Commands) ──0.42(assoc)──► L0(pytest)
- L2(venv command) ──0.56(seq)──► L2(pip install)

## Configuration Integration

Extend existing `CognitiveConfig` in `config.py`:

```python
# Markdown parsing parameters
max_tokens_per_chunk: int = 250
code_block_lines: int = 8
strength_floor: float = 0.15

# Base connection weights
hierarchical_weight: float = 0.80
sequential_weight: float = 0.70
associative_weight: float = 0.50

# Relevance scoring weights (must sum to 1.0)
semantic_alpha: float = 0.45
lexical_beta: float = 0.25
structural_gamma: float = 0.15
explicit_delta: float = 0.15
```

## CLI Interface

New command: `memory_system parse-md <file_path>`

```bash
# Parse single markdown file
memory_system parse-md ./CLAUDE.md

# Parse with custom parameters
memory_system parse-md ./docs/api.md --chunk-size 300 --dry-run

# Batch parse directory
memory_system parse-md ./docs/ --recursive
```

## Implementation Status

### ✅ Completed: Modular Component Architecture
The markdown processing system has been refactored into specialized components:

1. **ContentAnalyzer**: Linguistic analysis, POS tagging, content classification
2. **DocumentParser**: Markdown parsing with hierarchical tree construction
3. **MemoryFactory**: Memory creation, content assembly, and enhancement
4. **ConnectionExtractor**: Semantic similarity, lexical analysis, structural analysis
5. **ChunkProcessor**: Document chunking, grouping, and consolidation
6. **MarkdownMemoryLoader**: Main coordinator delegating to specialized components

### ✅ Completed: Connection Building
1. **Semantic Analysis**: Cosine similarity computation using spaCy
2. **Lexical Analysis**: Jaccard coefficient implementation
3. **Structural Analysis**: Document proximity scoring
4. **Connection Storage**: SQLite memory_connections table integration

### ✅ Completed: Integration & Validation
1. **Memory Ingestion**: Fully integrated with existing storage layer
2. **Configuration**: Extended CognitiveConfig with parsing parameters
3. **Test Coverage**: 53/53 tests passing with comprehensive validation
4. **CLI Enhancement**: Batch processing and dry-run mode available

## Quality Validation

### Test Harness
- **QA Set**: 30-40 natural language queries about markdown content
- **Success Metric**: Top-5 retrieval contains correct answer
- **Activation Metrics**: BFS spread efficiency (10-60 nodes optimal)

### Example Test Queries for CLAUDE.md
- "How do I run tests?" → Should activate L2(pytest command)
- "What is the vector database?" → Should activate L0(Qdrant concept)
- "Development workflow steps?" → Should activate L1(Dev Commands section)

## Dependencies

### Requirements Status

✅ **Already Installed and Configured**:
- spacy (with en_core_web_md model)
- vaderSentiment
- All dependencies integrated in modular architecture

✅ **Component Dependencies**:
- ContentAnalyzer: spacy, vaderSentiment
- DocumentParser: markdown, re
- MemoryFactory: Custom content assembly logic
- ConnectionExtractor: spacy, semantic analysis
- ChunkProcessor: Token counting, content grouping

## System Integration Architecture

### Interface Integration Points

The MemoryLoader architecture integrates cleanly with existing system interfaces:

1. **Interface Layer**: New `MemoryLoader` interface joins existing abstractions (`EmbeddingProvider`, `VectorStorage`, `MemoryStorage`, etc.)

2. **CognitiveSystem Orchestration**: The `CognitiveSystem` interface gains a new method `load_memories_from_source(loader, source_path)` that coordinates the loading process

3. **Storage Layer Reuse**: MemoryLoaders produce `CognitiveMemory` objects that flow through existing storage interfaces without modification

4. **Configuration Integration**: Loading parameters extend the existing `CognitiveConfig` dataclass following current environment variable patterns

### System Flow Integration

```
CLI Command → CognitiveSystem.load_memories_from_source()
                      ↓
            MemoryLoader.load_from_source()
                      ↓
            MemoryLoader.extract_connections()
                      ↓
            Existing Storage Pipeline (VectorStorage + MemoryStorage + ConnectionGraph)
```

### Extensibility Design

The MemoryLoader interface enables future content types:
- `PDFMemoryLoader` for research papers
- `CodeMemoryLoader` for source code repositories
- `ChatMemoryLoader` for conversation logs
- `WebMemoryLoader` for web content

Each loader implements the same interface contract, ensuring consistent integration with the cognitive system.

### CLI Integration

New command integrates with existing `memory_system` CLI:
```bash
memory_system load <source_path> [--loader-type=markdown] [--dry-run]
```

The command delegates to `CognitiveSystem.load_memories_from_source()` with appropriate loader instance, maintaining architectural consistency.

## Architectural Benefits

1. **Interface Consistency**: Follows established patterns from existing 9 interfaces
2. **Component Isolation**: MemoryLoaders are independently testable and swappable
3. **Storage Reuse**: Leverages existing vector and metadata storage without duplication
4. **Configuration Consistency**: Extends current environment-based configuration approach
5. **Future Extensibility**: Clean foundation for additional content types

This architecture maintains the system's interface-driven design principles while adding structured content ingestion capabilities that integrate seamlessly with existing cognitive processing and storage layers.

## Automatic File Change Monitoring

### Overview

The system includes comprehensive automatic markdown file change monitoring that synchronizes markdown files with cognitive memory in real-time. The monitoring system detects markdown file additions, modifications, and deletions, automatically updating the memory system to reflect file system changes.

### Architecture Components

#### Markdown File Monitoring
- **MarkdownFileMonitor**: Polling-based detection specifically for markdown files (`.md`, `.markdown`, `.mdown`, `.mkd`)
- **FileState Tracking**: Monitors file mtime, size, and existence with change detection logic
- **FileChangeEvent System**: Observer pattern with ChangeType enum (ADDED, MODIFIED, DELETED)
- **Cross-platform Compatibility**: Reliable polling approach that works on all operating systems

#### Generic Synchronization Layer
- **FileSyncHandler**: Generic file change synchronization using MemoryLoader interface pattern
- **LoaderRegistry**: Manages and discovers MemoryLoader implementations for different file types
- **Atomic Operations**: Delete+reload pattern with transaction-like error handling for consistency
- **File Type Detection**: Automatic loader selection via `get_supported_extensions()` and `validate_source()`

#### Production Service Integration
- **Container Integration**: Monitoring runs as built-in service within existing `heimdall-mcp` containers
- **Process Management**: Python multiprocessing with PID file tracking and signal handling
- **Health Monitoring**: Service status included in container health check system
- **Resource Management**: Memory/CPU monitoring with configurable thresholds

### Configuration Options

`CognitiveConfig` provides monitoring parameters:

```python
# File monitoring configuration
monitoring_enabled: bool = True
monitoring_interval_seconds: float = 5.0
monitoring_batch_size: int = 10
monitoring_ignore_patterns: Set[str] = {'.git', 'node_modules', '__pycache__'}

# File synchronization configuration
sync_enabled: bool = True
sync_atomic_operations: bool = True
sync_continue_on_error: bool = True
sync_max_retry_attempts: int = 3
sync_retry_delay_seconds: float = 1.0
```

### Memory Source Path Querying

SQLite persistence provides source path querying capabilities:

- **`get_memories_by_source_path()`**: Efficiently query memories by source file path
- **`delete_memories_by_source_path()`**: Atomic deletion of all memories from a specific file
- **JSON Indexing**: Performance-optimized indexes on `context_metadata.source_path` field
- **Partial Indexing**: Only indexes rows where source_path exists for efficiency

### CLI Integration

```bash
# Monitoring service management
memory_system monitor start        # Start monitoring service
memory_system monitor stop         # Stop monitoring service
memory_system monitor restart      # Restart monitoring service
memory_system monitor status       # Check service status
memory_system monitor health       # Detailed health check

# Health check integration
memory_system doctor               # Includes monitoring service validation
```

### Data Flow

```
Container Startup → MonitoringService (daemon) → MarkdownFileMonitor (polling) → FileSyncHandler → CognitiveSystem
                                ↓                                                      ↓
File System Changes → FileChangeEvent → FileSyncHandler → LoaderRegistry → MemoryLoader → Memory Operations
                                ↓
Container Health Check ← Service Status ← Error Recovery ← Statistics Tracking
```

### Component Interaction

The monitoring system uses a three-layer architecture:

1. **Detection Layer**: MarkdownFileMonitor watches for markdown file changes using polling
2. **Coordination Layer**: FileSyncHandler receives change events and orchestrates sync operations
3. **Loading Layer**: LoaderRegistry auto-selects appropriate MemoryLoader for file-to-memory conversion

This separation allows markdown-specific file monitoring while maintaining generic, extensible memory loading capabilities for future file types.

## Modular Component Architecture

### Component Responsibilities

The refactored markdown processing system follows the single responsibility principle with these specialized components:

#### 1. ContentAnalyzer (`content_analyzer.py`)
- **Purpose**: Linguistic analysis and content classification
- **Responsibilities**:
  - Token counting and content validation
  - Code section detection and analysis
  - Memory type classification (conceptual, procedural, contextual)
  - Content meaningfulness assessment
  - spaCy-based linguistic feature extraction

#### 2. DocumentParser (`document_parser.py`)
- **Purpose**: Markdown parsing and hierarchical tree construction
- **Responsibilities**:
  - Markdown header parsing and hierarchy building
  - Document tree construction with proper nesting
  - Position tracking for structural analysis
  - Content extraction and organization

#### 3. MemoryFactory (`memory_factory.py`)
- **Purpose**: Memory creation and content assembly
- **Responsibilities**:
  - Contextual content assembly with hierarchical paths
  - Code context enhancement and merging
  - Memory chunk creation with proper metadata
  - Content truncation and optimization

#### 4. ConnectionExtractor (`connection_extractor.py`)
- **Purpose**: Relationship analysis between memories
- **Responsibilities**:
  - Hierarchical connection detection (parent-child relationships)
  - Sequential connection analysis (step-by-step procedures)
  - Associative connection scoring (semantic similarity)
  - Relevance score calculation using multiple factors

#### 5. ChunkProcessor (`chunk_processor.py`)
- **Purpose**: Document chunking and intelligent grouping
- **Responsibilities**:
  - Tree-to-memory conversion with contextual awareness
  - Intelligent grouping of small sections
  - Memory consolidation and optimization
  - Token threshold management

#### 6. MarkdownMemoryLoader (`markdown_loader.py`)
- **Purpose**: Main coordinator orchestrating all components
- **Responsibilities**:
  - Component initialization and dependency injection
  - High-level processing workflow coordination
  - Interface compliance with MemoryLoader abstract base
  - Error handling and logging coordination

### Component Interaction Flow

```
MarkdownMemoryLoader (Coordinator)
    ↓
DocumentParser → Hierarchical Tree
    ↓
ContentAnalyzer → Content Classification
    ↓
ChunkProcessor → Memory Chunks
    ↓
MemoryFactory → Enhanced Memories
    ↓
ConnectionExtractor → Memory Relationships
    ↓
Return: (memories, connections)
```

### Benefits of Modular Architecture

1. **Single Responsibility**: Each component has a clear, focused purpose
2. **Testability**: Components can be tested independently with mocks
3. **Maintainability**: Changes to one component don't affect others
4. **Reusability**: Components can be reused in different contexts
5. **Extensibility**: New components can be added without affecting existing ones
6. **Code Quality**: Eliminates duplication and reduces complexity

### Backward Compatibility

The refactoring maintains full backward compatibility:
- Public API of MarkdownMemoryLoader remains unchanged
- All existing tests continue to pass (53/53)
- Integration points with CognitiveSystem unchanged
- Configuration parameters remain the same
