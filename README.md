# Cognitive Memory System

A cognitive memory system for Large Language Models that implements true cognitive processing through associative thinking, serendipitous connections, and emergent insights using multi-dimensional memory representation and dynamic activation patterns.

## Overview

This system implements the cognitive memory architecture described in the technical specification, featuring:

- **Multi-dimensional Memory Encoding**: Emotional, temporal, contextual, and social dimensions
- **Hierarchical Storage**: 3-tier memory hierarchy (L0: Concepts, L1: Contexts, L2: Episodes)
- **Activation Spreading**: Context-driven memory activation with BFS traversal
- **Bridge Discovery**: Novel connection identification through distance inversion
- **Dual Memory System**: Episodic and semantic memory with consolidation

## Technology Stack

- **Python 3.13**: Latest features, async support, type hints
- **Vector Database**: Qdrant for production-ready hierarchical collections
- **ML Framework**: PyTorch for research flexibility and transformers ecosystem
- **Base Embeddings**: Sentence-BERT (all-MiniLM-L6-v2) for fast local inference
- **Persistence**: SQLite + JSON for zero-setup ACID transactions
- **Configuration**: .env files with python-dotenv
- **Logging**: Loguru for structured logging

## Project Structure

```
cognitive-memory/
├── cognitive_memory/           # Core system
│   ├── core/                  # Cognitive interfaces and models
│   ├── encoding/              # Multi-dimensional encoding (Phase 1)
│   ├── storage/               # Memory persistence
│   └── retrieval/             # Activation and bridge discovery (Phase 1)
├── interfaces/                # API implementations (Phase 1)
├── data/                      # Local data storage
├── tests/                     # Unit and integration tests
└── docs/                      # Documentation and progress tracking
```

## Quick Start

### Prerequisites

- Python 3.13
- Qdrant server (for vector storage)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd cognitive-memory
```

2. Set up Python environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install development dependencies (optional):
```bash
pip install -r requirements-dev.txt
```

5. Set up configuration:
```bash
cp .env.template .env
# Edit .env with your configuration
```

### Running Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest -m unit

# Run with coverage
pytest --cov=cognitive_memory
```

### Code Quality

```bash
# Lint and format code
ruff check --fix
ruff format

# Type checking
mypy cognitive_memory/

# Run pre-commit hooks
pre-commit run --all-files
```

## Development Status

**Current Phase**: Bootstrap Complete ✅
- [x] Project structure and environment setup
- [x] Core interfaces and data structures
- [x] SQLite and Qdrant storage implementations
- [x] Configuration management
- [x] Testing framework
- [x] Development tools and quality gates

**Next Phase**: Phase 1 Implementation
- [ ] Multi-dimensional encoding with Sentence-BERT
- [ ] Basic activation spreading
- [ ] Simple similarity-based retrieval
- [ ] Rule-based dimension extraction

See `docs/progress/` for detailed progress tracking.

## Configuration

The system uses environment variables for configuration. Key settings:

```bash
# Vector Database
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=optional_key

# Database
SQLITE_PATH=./data/cognitive_memory.db

# Embeddings
SENTENCE_BERT_MODEL=all-MiniLM-L6-v2

# Cognitive Parameters
ACTIVATION_THRESHOLD=0.7
BRIDGE_DISCOVERY_K=5
MAX_ACTIVATIONS=50
```

See `.env.template` for all available configuration options.

## Architecture

The system follows a modular, interface-driven architecture:

- **Core Interfaces**: Abstract base classes for all major components
- **Storage Layer**: SQLite for metadata, Qdrant for vectors
- **Cognitive Layer**: Multi-dimensional encoding and processing
- **API Layer**: CLI, MCP, and HTTP interfaces

## Testing

The project includes comprehensive testing:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **Performance Tests**: Latency and throughput benchmarks
- **Cognitive Tests**: Bridge discovery and activation quality

## Contributing

1. Follow the established code style (enforced by ruff and black)
2. Write tests for new functionality
3. Update documentation as needed
4. Use the pre-commit hooks for quality gates

## License

MIT License - see LICENSE file for details.

## Resources

- [Technical Architecture Specification](architecture-technical-specification.md)
- [Progress Documentation](docs/progress/README.md)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Sentence-BERT Documentation](https://www.sbert.net/)