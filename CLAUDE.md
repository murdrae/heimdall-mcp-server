# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Cognitive Memory System** - An MCP server that provides Large Language Models with persistent memory across conversations. The system learns patterns from git history, stores insights from sessions, and enables intelligent knowledge consolidation for project-specific contexts.

**Core Capabilities:**
- Multi-dimensional memory encoding (semantic, emotional, temporal, contextual)
- Hierarchical memory storage (L0: Concepts, L1: Contexts, L2: Episodes)
- Bridge discovery for serendipitous connections between distant concepts
- Git pattern extraction (co-change patterns, maintenance hotspots, solution patterns)
- Session lessons framework for metacognitive learning

## System Architecture

### Memory Hierarchy (3-Level System)
- **L0 (Concepts)**: High-level abstractions, principles, patterns
- **L1 (Contexts)**: Mid-level scenarios, domain knowledge, contextual information
- **L2 (Episodes)**: Specific experiences, interactions, detailed memories

### Core Components
- **Multi-Dimensional Encoder**: Converts experiences to rich vectors (semantic + emotional + temporal + contextual)
- **Dual Memory System**: Episodic (fast decay) + Semantic (slow decay) with consolidation
- **Context-Driven Activation**: Spreads activation through memory networks for retrieval
- **Bridge Discovery**: Finds unexpected connections between distant concepts

### Technology Stack
- **Vector Storage**: Qdrant with project-specific collections
- **Embeddings**: Sentence-BERT (all-MiniLM-L6-v2) + multi-dimensional extraction
- **Persistence**: SQLite for metadata, connections, and usage statistics
- **Integration**: MCP protocol for Claude Code integration

## Key File Structure

```
cognitive_memory/
├── core/                    # Core cognitive system interfaces
│   ├── cognitive_system.py  # Main CognitiveSystem class
│   ├── memory.py            # CognitiveMemory, BridgeMemory data structures
│   ├── interfaces.py        # Abstract interfaces (MemoryLoader, etc.)
│   └── config.py           # System configuration
├── encoding/               # Multi-dimensional encoding
│   ├── cognitive_encoder.py # Main encoder with dimension fusion
│   ├── sentence_bert.py    # SentenceBERT implementation
│   └── dimensions.py       # Rule-based dimension extraction
├── storage/                # Memory persistence
│   ├── qdrant_storage.py   # Vector database operations
│   ├── sqlite_persistence.py # Metadata storage
│   └── dual_memory.py      # Episodic/semantic memory system
├── retrieval/              # Memory retrieval and activation
│   ├── contextual_retrieval.py # Main retrieval coordinator
│   ├── basic_activation.py     # Activation spreading
│   └── bridge_discovery.py     # Serendipitous connections
├── git_analysis/           # Git pattern extraction
│   ├── history_miner.py    # Git history analysis
│   ├── pattern_detector.py # Pattern identification
│   └── pattern_embedder.py # Convert patterns to memories
└── loaders/               # Memory loading interfaces
    ├── git_loader.py      # Git repository integration
    └── markdown_loader.py # Markdown file processing

interfaces/
├── cli.py                 # CognitiveCLI - main CLI interface
├── mcp_server.py         # MCP protocol server
└── mcp_tools/            # Individual MCP tool implementations

memory_system/
├── cli.py                # Service management CLI (memory_system command)
├── service_manager.py    # Docker/Qdrant service management
└── interactive_shell.py  # Interactive memory shell
```

## Development Commands

### Core Development
```bash
# Install dependencies
pip install -e .

# Development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Linting and formatting
ruff check                # Code linting
ruff format              # Code formatting
mypy .                   # Type checking

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only
```

### System Management
```bash
# Service management
memory_system qdrant start    # Start Qdrant vector database
memory_system qdrant stop     # Stop Qdrant
memory_system qdrant status   # Check status

# Health checking
memory_system doctor          # Full system health check

# Interactive shell
memory_system shell          # Interactive memory operations

# MCP server
memory_system serve mcp      # Start MCP server (stdio)
```

### Memory Operations (CLI)
```bash
# Load memories from sources
memory_system load /path/to/docs --loader-type=markdown
memory_system load /path/to/repo --loader-type=git

# Manual memory storage
cognitive-cli store "Important insight about the system"

# Memory retrieval
cognitive-cli recall "authentication patterns"
cognitive-cli bridges "debugging approaches"

# System status
cognitive-cli status
```

## MCP Integration

The system provides 4 MCP tools for Claude Code integration:

### Available MCP Tools
- **`store_memory`**: Store experiences and insights with multi-dimensional context
- **`recall_memories`**: Semantic search with categorized results (core/peripheral/bridge)
- **`session_lessons`**: Record key learnings for future sessions (metacognitive reflection)
- **`memory_status`**: System health and memory statistics

### Setup for Claude Code
```bash
# From any project directory
/path/to/cognitive-memory/setup_claude_code_mcp.sh

# This creates project-specific memory isolation
# Each project gets its own Docker containers and memory space
```

## Git Integration Features

### Pattern Types Extracted
- **Co-change Patterns**: Files that frequently change together with confidence scores
- **Maintenance Hotspots**: Files with high problem frequency and quality ratings
- **Solution Patterns**: Successful fix approaches with success rate metrics

### Loading Git Patterns
```bash
# Load git history patterns into memory
./scripts/load_project_content.sh --git-only

# Preview what would be loaded
./scripts/load_project_content.sh --dry-run
```

## Docker Architecture

### Project Isolation Strategy
Each project directory gets isolated Docker containers:
- Deterministic naming: `cognitive-memory-{project-hash}`
- Unique ports: `6333 + hash % 1000`
- Isolated data volumes and networks
- Project-specific Qdrant collections

### Container Management
```bash
# Setup project memory (from project directory)
/path/to/cognitive-memory/scripts/setup_project_memory.sh

# Cleanup project containers
/path/to/cognitive-memory/scripts/setup_project_memory.sh --cleanup

# Rebuild containers
/path/to/cognitive-memory/scripts/setup_project_memory.sh --rebuild
```

## Testing Strategy

### Test Categories
- **Unit Tests**: Individual component testing (`tests/unit/`)
- **Integration Tests**: End-to-end workflows (`tests/integration/`)
- **E2E Tests**: Complete system scenarios (`tests/e2e/`)

### Key Test Patterns
```bash
# Test specific components
pytest tests/unit/test_cognitive_system.py
pytest tests/integration/test_memory_loader_integration.py

# Test git integration
pytest tests/unit/test_git_pattern_detector.py
pytest tests/integration/test_end_to_end_system.py

# Test MCP server
pytest tests/test_mcp_server.py
```

## Configuration Management

### Environment Variables
```bash
# Core system
QDRANT_URL=http://localhost:6333
SENTENCE_BERT_MODEL=all-MiniLM-L6-v2
COGNITIVE_MEMORY_DB_PATH=./data/cognitive_memory.db

# MCP specific
MCP_MAX_MEMORIES_PER_QUERY=10
MCP_SESSION_LESSON_BOOST=1.5

# Git integration
GIT_PATTERN_MIN_CONFIDENCE=0.7
GIT_HOTSPOT_THRESHOLD=5
```

### Configuration Files
- `.env` files for environment-specific settings
- `cognitive_memory/core/config.py` for system defaults
- Project-specific config in `.cognitive-memory/` directories

## Memory Content Strategy

All pattern information is embedded in natural language content rather than separate metadata, enabling rich semantic search:

**Example Git Pattern Content:**
```
"Development pattern (confidence: 92%, quality: high): Files auth/middleware.py and auth/jwt.py frequently change together (12 co-commits over 6 months, trend: increasing). Strong coupling indicates shared authentication logic."
```

## Development Workflow

### Adding New Memory Loaders
1. Implement `MemoryLoader` interface in `cognitive_memory/loaders/`
2. Add loader registration in `cognitive_memory/factory.py`
3. Add CLI integration in `interfaces/cli.py`
4. Write comprehensive tests in `tests/unit/` and `tests/integration/`

### Adding New MCP Tools
1. Implement tool in `interfaces/mcp_tools/`
2. Register in `interfaces/mcp_server.py`
3. Add comprehensive input validation and error handling
4. Write integration tests in `tests/test_mcp_server.py`

### Modifying Memory Schema
1. Update `CognitiveMemory` dataclass in `cognitive_memory/core/memory.py`
2. Create database migration in `cognitive_memory/storage/migrations/`
3. Update serialization/deserialization in storage components
4. Ensure backward compatibility for existing memories

## Performance Considerations

### Scalability Targets
- **Phase 1**: 10K memories, single-user, local deployment
- **Phase 2**: 100K memories, multi-user, containerized
- **Phase 3**: 1M+ memories, distributed deployment

### Optimization Guidelines
- Use batch operations for bulk memory loading
- Implement connection caching in retrieval components
- Monitor Qdrant collection sizes and optimize vectors
- Use SQLite indices for metadata queries
- Implement memory consolidation for episodic→semantic promotion

## Quality Standards

### Code Quality Requirements
- **Linting**: `ruff check` must pass
- **Type Checking**: `mypy` must pass with no errors
- **Test Coverage**: Minimum 85% for core cognitive components
- **Complexity**: Maximum cyclomatic complexity of 10

### Git Commit Standards
All commits must pass pre-commit hooks:
- Code linting and formatting
- Type checking
- Test suite execution
- Architecture validation

This system represents a sophisticated approach to persistent AI memory that grows more valuable over time through continuous learning and pattern recognition.
