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

### Cognitive Architecture (from Technical Specification)
- **Multi-dimensional Encoding**: 4 dimensions (emotional, temporal, contextual, social) + Sentence-BERT semantic embeddings fused via learned weights
- **Hierarchical Memory Storage**: 3-tier hierarchy using Qdrant collections:
  - L0: Concepts Collection (abstract ideas)
  - L1: Contexts Collection (situational memories)
  - L2: Episodes Collection (specific experiences)
- **Activation Spreading**: Context-driven activation using BFS traversal through memory connections
- **Bridge Discovery**: Distance inversion algorithm to find serendipitous connections between distant concepts
- **Dual Memory System**: Episodic (fast decay) and semantic (slow decay) with automatic consolidation
- Refer `./docs/architecture-technical-specification.md`

### Interface-Driven Design
All components implement abstract interfaces for:
- Component swapping (vector stores, embedding models, algorithms)
- Easy unit testing with mock implementations
- Scaling from local to distributed deployment
- Research iteration and algorithm comparison

**Core Interfaces**: `EmbeddingProvider`, `VectorStorage`, `ActivationEngine`, `BridgeDiscovery`, `MemoryStorage`, `ConnectionGraph`, `CognitiveSystem`, `DimensionExtractor`

## Development Commands

### Environment Setup

- **ALWAY USE VENV AT ROOT OF REPOSITORY**
```bash
# Python 3.13 virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development tools
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

## Project Structure (Technical Specification)

```
cognitive-memory/
├── cognitive_memory/        # Core cognitive system
│   ├── core/               # Interfaces and data structures
│   │   ├── interfaces.py   # Abstract base classes (9 interfaces)
│   │   ├── memory.py      # CognitiveMemory, SearchResult, ActivationResult
│   │   ├── config.py      # Configuration management with validation
│   │   └── logging_setup.py # Structured cognitive event logging
│   ├── encoding/          # Multi-dimensional encoding (Phase 1)
│   ├── storage/           # Memory persistence implementations
│   └── retrieval/         # Activation spreading and bridge discovery
├── interfaces/            # API implementations
│   ├── cli.py            # Command-line interface (cognitive-cli)
│   ├── mcp_server.py     # MCP protocol server
│   └── http_api.py       # HTTP REST API
├── data/                 # Local storage
│   ├── cognitive_memory.db # SQLite database
│   └── models/           # Downloaded ML models
├── tests/               # Comprehensive test suite
│   ├── unit/           # Component isolation tests
│   └── integration/    # End-to-end cognitive workflows
└── docs/progress/      # Progress tracking (REQUIRED READING)
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
