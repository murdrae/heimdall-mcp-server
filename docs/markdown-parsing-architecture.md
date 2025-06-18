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
2. **MarkdownMemoryLoader**: Specific implementation for .md files
3. **CognitiveSystem Integration**: Orchestrates loading process
4. **Content Classification Engine**: Determines L0/L1/L2 hierarchy
5. **Relationship Extraction Engine**: Builds connection graph

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

## Implementation Steps

### Phase 1: Core Parser (Week 1)
1. **Chunker Component**: Markdown splitting logic
2. **spaCy Integration**: POS tagging and linguistic features
3. **Classifier**: L0/L1/L2 assignment algorithm
4. **Basic CLI**: Single file parsing command

### Phase 2: Connection Builder (Week 2)
1. **Semantic Analysis**: Cosine similarity computation
2. **Lexical Analysis**: Jaccard coefficient implementation
3. **Structural Analysis**: Document proximity scoring
4. **Connection Storage**: SQLite memory_connections table

### Phase 3: Integration & Validation (Week 3)
1. **Memory Ingestion**: Integration with existing storage layer
2. **Configuration**: Extend CognitiveConfig with parsing parameters
3. **Validation System**: QA harness with test queries
4. **CLI Enhancement**: Batch processing, dry-run mode

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

### New Requirements

- Already installed
- spacy, vaderSentiment
- spacy en_core_web_md
- python -m spacy download en_core_web_md

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
