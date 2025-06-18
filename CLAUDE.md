# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ESSENTIAL READING REQUIREMENT

**CRITICAL**: Before starting ANY development task, you MUST read the progress documentation at `docs/progress/README.md` and the current progress file (e.g. `docs/progress/000_bootstrapping.md`) to understand:
- Current project status and completion percentage
- Recent changes and updates
- Technical decisions made
- Dependencies and blockers
- Next planned steps

This ensures continuity and prevents duplicate work or architectural conflicts.

## Project Overview

This is a **cognitive memory system for Large Language Models** implementing true cognitive processing through associative thinking, serendipitous connections, and emergent insights. The system uses multi-dimensional memory representation and dynamic activation patterns to enable human-like memory retrieval.

## Architecture Summary

### Technology Stack
- **Vector Database**: Qdrant (hierarchical collections, production-ready)
- **ML Framework**: PyTorch + Sentence-BERT (all-MiniLM-L6-v2, 384D)
- **Memory Persistence**: SQLite + JSON (metadata, connections, statistics)
- **Language**: Python 3.13 (latest features, async support)

### Cognitive Architecture
- **Multi-dimensional Encoding**: 4 dimensions (emotional, temporal, contextual, social) + Sentence-BERT (384D vectors)
- **Hierarchical Storage**: 3-tier Qdrant collections (L0: Concepts, L1: Contexts, L2: Episodes)
- **Activation Spreading**: BFS traversal through memory connections with threshold-based activation
- **Bridge Discovery**: Distance inversion algorithm for serendipitous connections between distant concepts
- **Dual Memory System**: Episodic (fast decay) and semantic (slow decay) with automatic consolidation

### Data Flow & Interface Connections
```
Experience Input → DimensionExtractor → EmbeddingProvider → CognitiveSystem
                                                               ↓
                                          VectorStorage ← MemoryStorage → SQLite
                                               ↓
Query → ActivationEngine → ConnectionGraph → BridgeDiscovery → SearchResults
```

### Interface-Driven Design
**Core Interfaces**: `EmbeddingProvider`, `VectorStorage`, `ActivationEngine`, `BridgeDiscovery`, `MemoryStorage`, `ConnectionGraph`, `CognitiveSystem`, `DimensionExtractor`

- Component swapping (vector stores, embedding models, algorithms)
- Easy unit testing with mock implementations
- Research iteration and algorithm comparison

Refer to `./docs/architecture-technical-specification.md` for detailed technical implementation.

## Development Commands

### Environment Setup

- **ALWAYS USE VENV AT ROOT OF REPOSITORY**
```bash
# Python 3.13 virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development tools

# Install package in development mode
pip install -e .
```

### CLI Usage

Essential commands after `pip install -e .`:

```bash
# Quick start - automated setup
memory_system doctor          # Check system health
memory_system qdrant start    # Start vector database
memory_system shell           # Interactive memory operations

# When done
memory_system qdrant stop     # Stop services
```

### Testing Strategy
```bash
# Run all tests
pytest

# Coverage reporting
pytest --cov=cognitive_memory --cov-report=html
```

### Code Quality (Pre-commit Requirements)

- **NEVER BYPASS COMMIT HOOKS**

```bash
# Run all quality gates - this already wraps everything
pre-commit run --all-files
```

## Configuration Management

Environment variables in `.env` (see `.env.template`):
```bash
# Vector Database
QDRANT_URL=http://localhost:6333

# ML Models
SENTENCE_BERT_MODEL=all-MiniLM-L6-v2

# Cognitive Parameters
```

## Project Structure

```
cognitive-memory/
├── cognitive_memory/        # Core cognitive system
│   ├── core/               # Interfaces and data structures
│   │   ├── interfaces.py   # Abstract base classes (9 interfaces)
│   │   ├── memory.py      # CognitiveMemory, SearchResult, ActivationResult
│   │   ├── config.py      # Configuration management with validation
│   │   └── logging_setup.py # Structured cognitive event logging
│   ├── encoding/          # Multi-dimensional encoding
│   │   ├── sentence_bert.py   # SentenceBERT implementation
│   │   ├── dimensions.py      # Rule-based dimension extraction
│   │   └── cognitive_encoder.py # Multi-dimensional encoding
│   ├── storage/           # Memory persistence
│   │   ├── qdrant_storage.py    # Qdrant vector storage
│   │   ├── sqlite_persistence.py # SQLite metadata storage
│   │   └── dual_memory.py       # Episodic/semantic system
│   └── retrieval/         # Activation spreading and bridge discovery
│       ├── basic_activation.py  # Simple activation spreading
│       └── similarity_search.py # Cosine similarity retrieval
├── interfaces/            # API implementations
│   ├── cli.py            # Command-line interface (memory_system)
│   ├── mcp_server.py     # MCP protocol server
│   └── http_api.py       # HTTP REST API
├── data/                 # Local storage
│   ├── cognitive_memory.db # SQLite database
│   └── models/           # Downloaded ML models
├── tests/               # Comprehensive test suite
│   ├── unit/           # Component isolation tests
│   └── integration/    # End-to-end cognitive workflows
└── docs/               # Documentation
    ├── progress/       # Progress tracking (REQUIRED READING)
    └── architecture-technical-specification.md
```

## Development Phase Status

**Current Phase**: Bootstrap Complete ✅ (100%)
- All foundational components implemented
- 19 tests passing, full quality gates operational
- Ready for Phase 1 implementation

**Next Phase**: Phase 1 - Foundation
- Multi-dimensional encoding with rule-based dimension extraction
- Basic activation spreading through memory levels
- Simple similarity-based retrieval
- Qdrant collections setup for hierarchical storage

**Implementation Phases**:
1. **Foundation**: Basic encoding, storage, retrieval
2. **Cognitive Enhancement**: Full activation spreading, bridge discovery
3. **Emergent Intelligence**: Meta-learning, advanced algorithms

## Code Quality Requirements

### Type Safety
- **Strict mypy compliance**: All functions must have complete type annotations
- **Interface compliance**: Core components must implement abstract base classes
- **Generic types**: Use proper generic typing for collections and tensors

### Testing Standards
- **85% coverage minimum** for cognitive components
- **Unit tests**: All interfaces must have comprehensive test coverage
- **Integration tests**: End-to-end cognitive workflows

### Architecture Compliance
- **Interface-first design**: Always implement abstract interfaces
- **Dependency injection**: Components receive dependencies via constructor
- **DRY**: Obsess with DRY principles
- **SOLID**: Obsess with SOLID principles
- **Separation of concerns**: Storage, encoding, retrieval, and interfaces are distinct
- **Configuration externalization**: All parameters configurable via environment

### Cognitive Event Logging
Use structured logging for all cognitive operations:
```python
logger.info("Memory formation", experience_id=uuid, dimensions=extracted_dims)
logger.debug("Activation spreading", activated_count=42, threshold=0.7)
logger.warning("Bridge discovery yielded no results", query_context=context_summary)
```

## Development Workflow

1. **Read Progress Documentation**: Always check `docs/progress/` before starting.
2. **READ and FOLLOW** `./docs/progress/README.md` on any development tasks
3. **Update Progress**: Document significant changes in appropriate progress file
4. **ALWAYS** commit at milestones. Never git add all files, manually list the files you worked on.

## Testing Methodology

1. Work on 1 test file at a time.
2. Make sure tests are meaningful, cover edge cases, aim for high coverage happy and bad paths
3. Make sure tests PASS or capture bugs before moving to next test files.
4 After you finish working in a test file, update progress and move to the next test file
