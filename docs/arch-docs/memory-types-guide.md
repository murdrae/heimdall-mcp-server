# Memory Types in Cognitive Memory System

## Overview

The Cognitive Memory System categorizes retrieved memories into two distinct types that mirror how human memory and cognition work. This dual classification enables both focused recall and contextual discovery, creating a truly cognitive approach to information retrieval.

## The Two Memory Types

### 🎯 Core Memories

**Definition**: The most directly relevant memories to your query, representing the central concepts and experiences most closely related to what you're asking about.

**Characteristics**:
- **Activation Threshold**: ≥ 0.7 (highest relevance score)
- **Purpose**: Direct, focused responses to your query
- **Visual Style**: Blue border in interactive shell
- **Cognitive Role**: Primary working memory content

**How They're Determined**:
Core memories are selected based on the highest activation strength, calculated from:
- Direct semantic similarity to your query
- Frequency of access (memories you retrieve often get boosted)
- Importance scores (manually assigned or inferred)
- Temporal relevance (recent memories get slight preference)

**Examples**:
- **Query**: "machine learning algorithms"
- **Core Memories**:
  - Your notes on neural networks
  - A document about gradient descent
  - Your experience implementing a classifier

### 🌐 Peripheral Memories

**Definition**: Moderately relevant memories that provide broader context, related concepts, and supporting associations that enrich understanding.

**Characteristics**:
- **Activation Threshold**: ≥ 0.5 but < 0.7 (moderate relevance score)
- **Purpose**: Contextual support and related associations
- **Visual Style**: Dim border in interactive shell
- **Cognitive Role**: Extended context and background knowledge

**How They're Determined**:
Peripheral memories have moderate activation strength and often include:
- Related but not directly matching concepts
- Background knowledge that supports understanding
- Memories connected through associative links
- Contextual information from similar domains

**Examples**:
- **Query**: "machine learning algorithms"
- **Peripheral Memories**:
  - General programming best practices
  - Statistics and probability concepts
  - Data preprocessing techniques
  - Your experience with Python libraries


## Technical Implementation

### Activation Strength Calculation

Each memory's activation strength is computed using multiple factors:

```python
activation_strength = (
    base_similarity_score +
    frequency_boost +      # Access count × 0.1 (max 0.5)
    importance_boost +     # Importance score × 0.3
    temporal_decay_factor  # Recency adjustment
)
```

### Classification Thresholds

```python
if activation_strength >= 0.7:
    → Core Memory
elif activation_strength >= 0.5:
    → Peripheral Memory
```

### Configuration

Default thresholds can be configured via environment variables:

```bash
# Core/Peripheral thresholds
ACTIVATION_THRESHOLD=0.7        # Core threshold
PERIPHERAL_THRESHOLD=0.5        # Peripheral threshold
```

## Usage in Different Interfaces

### Interactive Shell

```bash
# Get all memory types
cognitive> retrieve "neural networks"
🎯 CORE MEMORIES (3)
🌐 PERIPHERAL MEMORIES (5)
```

### Command Line Interface

```bash
# All memory types (default)
memory_system load retrieve "neural networks"

# Specific types only
memory_system retrieve "neural networks" --types core
memory_system retrieve "neural networks" --types peripheral
```

### Programmatic API

```python
# Retrieve all types
results = cognitive_system.retrieve_memories(
    query="neural networks",
    types=["core", "peripheral"],
    max_results=10
)

# Access by type
core_memories = results["core"]
peripheral_memories = results["peripheral"]
```

## Cognitive Psychology Background

This two-tier system is inspired by research in cognitive psychology and memory science:

### Spreading Activation Theory
- **Core memories**: Direct activation from query concepts
- **Peripheral memories**: Secondary activation through associative links

### Dual-Process Theory
- **System 1 (Fast)**: Core memories for quick, direct responses
- **System 2 (Slow)**: Peripheral memories for contextual understanding and broader connections

## Best Practices

### For Query Formulation
- **Specific queries** tend to produce more core memories
- **Broad queries** generate more peripheral connections
- **Abstract concepts** often yield more peripheral associations

### For Memory Storage
- **Rich metadata** improves classification accuracy
- **Diverse content** increases peripheral connection potential
- **Regular use** strengthens memory activation patterns

### For System Configuration
- **Lower thresholds** (0.6/0.4) for more inclusive results
- **Higher thresholds** (0.8/0.6) for more focused results

## Troubleshooting


### Too Many Peripheral Memories
- Increase peripheral threshold in configuration
- Use more specific queries
- Focus on core memories only with `--types core`

### Missing Expected Core Memories
- Check activation threshold configuration
- Verify memory importance scores
- Consider if memories need more frequent access to boost relevance

## Memory Decay and Lifecycle

### Dual Memory System with Decay

The system implements biologically-inspired memory decay with two distinct storage types:

#### Episodic Memory (Fast Decay)
- **Purpose**: Recent, specific experiences and interactions
- **Decay Rate**: Fast exponential decay (configurable in `cognitive_memory/storage/dual_memory.py`)
- **Retention**: Maximum 30 days absolute limit
- **Removal Criteria**:
  - Age exceeds retention period
  - Strength falls below minimum threshold
  - Importance score becomes negligible

#### Semantic Memory (Slow Decay)
- **Purpose**: Generalized patterns and consolidated knowledge
- **Decay Rate**: Very slow exponential decay (10x slower than episodic)
- **Retention**: Months to years, no automatic expiration
- **Consolidation**: Frequently accessed episodic memories get promoted to semantic

### Data Flow for Memory Lifecycle

```
New Experience → Episodic Storage → Access Tracking → Consolidation Decision
                      ↓                                        ↓
                 Decay Calculation                    Semantic Storage
                      ↓                                        ↓
              Cleanup if Expired                      Long-term Retention
```

### Configuration Sources

Memory decay parameters are defined in:

- **Decay Rates**: `cognitive_memory/storage/dual_memory.py` (DualMemorySystem class)
- **Cleanup Intervals**: `cognitive_memory/core/config.py` (CognitiveConfig.cleanup_interval_hours)
- **Consolidation Criteria**: `cognitive_memory/core/cognitive_system.py` (CognitiveSystem.consolidate_memories)
- **Retention Limits**: `cognitive_memory/storage/dual_memory.py` (episodic/semantic retention policies)

### Consolidation Process

**Automatic Promotion Criteria** (episodic → semantic):
- Access frequency threshold (defined in consolidation logic)
- Minimum strength requirement
- Age requirement for stability
- Connection strength to other memories

**Manual Cleanup** via:
```bash
# Trigger consolidation cycle
memory_system shell
cognitive> consolidate

# Clean expired memories
cognitive> cleanup
```

### Key Implementation Files

- `cognitive_memory/storage/dual_memory.py` - DualMemorySystem with episodic/semantic storage
- `cognitive_memory/core/cognitive_system.py` - Main CognitiveSystem orchestrator
- `cognitive_memory/core/config.py` - CognitiveConfig with system parameters
- `memory_system/cli.py` - Service management CLI with cleanup commands
- `memory_system/interactive_shell.py` - Interactive shell for manual operations

**Note**: Cleanup is currently manual rather than automated. The system tracks when cleanup should occur but requires explicit triggering through CLI or API calls.

## Related Documentation

- [Architecture Technical Specification](./architecture-technical-specification.md) - Deep technical details
- [Configuration Guide](../cognitive_memory/core/config.py) - All configuration options
- [API Reference](../interfaces/) - Programming interfaces
- [Interactive Shell Guide](../memory_system/interactive_shell.py) - Shell commands and features

---

*The Cognitive Memory System implements these memory types to create human-like information retrieval that balances precision and context - enabling both focused research and contextual discovery.*
