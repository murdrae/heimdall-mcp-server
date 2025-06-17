# 003 - Phase 1: Basic Retrieval and Activation

## Overview
Phase 1 Step 003 implements the foundational retrieval and activation subsystem for the cognitive memory architecture. This phase builds upon the encoding and storage systems by creating basic activation spreading mechanisms and similarity-based retrieval that will serve as the foundation for more sophisticated cognitive processing in later phases.

## Status
- **Started**: TBD
- **Current Phase**: Basic Retrieval Implementation
- **Completion**: 0%
- **Expected Completion**: TBD

## Objectives
- [ ] Implement basic activation spreading engine with BFS traversal
- [ ] Create similarity-based memory retrieval using cosine similarity
- [ ] Build simple bridge discovery mechanism using distance inversion
- [ ] Develop context-driven activation with threshold-based filtering
- [ ] Integrate retrieval with hierarchical memory storage
- [ ] Comprehensive test coverage for retrieval subsystem

## Implementation Progress

### Step 3A: Basic Activation Engine
**Status**: Pending
**Priority**: High

#### Tasks
- [ ] Create `BasicActivationEngine` in `retrieval/basic_activation.py`
- [ ] Implement BFS traversal through memory connections
- [ ] Add threshold-based activation filtering
- [ ] Implement hierarchical activation (L0→L1→L2)
- [ ] Add activation strength computation

### Step 3B: Similarity-Based Search
**Status**: Pending
**Priority**: High

#### Tasks
- [ ] Implement `SimilaritySearch` in `retrieval/similarity_search.py`
- [ ] Add cosine similarity computation for cognitive vectors
- [ ] Implement k-nearest neighbor search across hierarchy levels
- [ ] Add recency bias for recent memory preference
- [ ] Implement search result ranking and filtering

### Step 3C: Simple Bridge Discovery
**Status**: Pending
**Priority**: Medium

#### Tasks
- [ ] Create `SimpleBridgeDiscovery` in `retrieval/bridge_discovery.py`
- [ ] Implement distance inversion algorithm from tech spec
- [ ] Add novelty score computation (inverse similarity)
- [ ] Add connection potential scoring
- [ ] Implement bridge ranking and selection

### Step 3D: Context-Driven Retrieval
**Status**: Pending
**Priority**: Medium

#### Tasks
- [ ] Implement `ContextualRetrieval` coordinator
- [ ] Add context vector generation from current state
- [ ] Integrate activation, similarity search, and bridge discovery
- [ ] Implement memory categorization (core/peripheral/bridge)
- [ ] Add retrieval result aggregation and ranking

## Technical Architecture

### Retrieval Component Structure
```
cognitive_memory/retrieval/
├── __init__.py
├── basic_activation.py      # BFS activation spreading
├── similarity_search.py     # Cosine similarity retrieval
├── bridge_discovery.py      # Simple distance inversion
└── contextual_retrieval.py  # High-level retrieval coordination
```

### Key Algorithms

#### Activation Spreading (BFS)
- Start with high-similarity memories at L0 (concepts)
- Spread activation through connection graph using breadth-first search
- Apply activation threshold to limit computational overhead
- Track activation strength for result ranking

#### Similarity Search
- Compute cosine similarity between query and memory vectors
- Search across all hierarchy levels (L0, L1, L2)
- Apply recency bias to prefer recent memories
- Return ranked results with similarity scores

#### Bridge Discovery
- Identify memories with low direct similarity to query
- Compute connection potential through activated memories
- Calculate bridge score: `(novelty * 0.6) + (connection_potential * 0.4)`
- Return top-k bridge memories for serendipitous connections

### Integration Architecture
```mermaid
graph TB
    subgraph "Retrieval Subsystem"
        CR[Contextual Retrieval]
        BAE[Basic Activation Engine]
        SS[Similarity Search]
        SBD[Simple Bridge Discovery]
    end
    
    subgraph "Storage Layer"
        HMS[Hierarchical Memory Storage]
        CG[Connection Graph]
    end
    
    CR --> BAE
    CR --> SS
    CR --> SBD
    
    BAE --> HMS
    BAE --> CG
    SS --> HMS
    SBD --> HMS
```

### Key Design Decisions
- **Simple algorithms**: Focus on correctness over sophistication for Phase 1
- **Threshold-based activation**: Computationally efficient activation spreading
- **Hierarchical search**: Leverage L0→L1→L2 structure for efficient retrieval
- **Interface compliance**: All retrievers implement abstract interfaces
- **Modular design**: Each retrieval method can be tested independently

## Dependencies
- torch (tensor operations for similarity computation)
- collections.deque (BFS queue implementation)
- numpy (numerical operations for scoring)
- typing (type hints for interfaces)
- Core storage and memory components from previous steps

## Integration Points
- **With Storage**: Retrieval accesses memories through storage interfaces
- **With Encoding**: Uses cognitive vectors from encoding system
- **With Core**: Implements retrieval interfaces defined in `core/interfaces.py`
- **Future Phases**: Foundation for advanced activation and bridge discovery

## Algorithm Specifications

### Basic Activation Spreading
```python
def activate_memories(context_vector, threshold=0.7, max_activations=50):
    # Phase 1: Find high-similarity L0 concepts
    l0_matches = storage.search_level(0, context_vector, threshold)
    
    # Phase 2: BFS through connection graph
    activated = set()
    queue = deque(l0_matches)
    
    while queue and len(activated) < max_activations:
        current = queue.popleft()
        if current.id not in activated:
            activated.add(current.id)
            connected = connection_graph.get_connections(current.id, threshold)
            queue.extend(connected)
    
    return ActivationResult(activated, strengths)
```

### Simple Bridge Discovery
```python
def discover_bridges(query_context, activated_memories, k=5):
    candidates = get_non_activated_memories(activated_memories)
    bridge_scores = []
    
    for candidate in candidates:
        # Novelty = inverse similarity to query
        novelty = 1.0 - cosine_similarity(query_context, candidate.vector)
        
        # Connection potential to activated memories
        connection_potential = max(
            cosine_similarity(candidate.vector, activated.vector)
            for activated in activated_memories
        )
        
        bridge_score = (novelty * 0.6) + (connection_potential * 0.4)
        bridge_scores.append((candidate, bridge_score))
    
    return sorted(bridge_scores, key=lambda x: x[1], reverse=True)[:k]
```

## Testing Strategy
- Unit tests for each retrieval algorithm
- Integration tests with storage and encoding systems
- Performance tests for activation spreading efficiency
- Accuracy tests for similarity search results
- Bridge quality evaluation with synthetic data

## Success Criteria
- [ ] All retrieval interfaces implemented and tested
- [ ] BFS activation spreading functional and efficient
- [ ] Similarity search returns relevant results with proper ranking
- [ ] Bridge discovery identifies meaningful connections
- [ ] Integration with storage layer complete and tested
- [ ] 85%+ test coverage for retrieval components
- [ ] All quality gates pass (ruff, mypy, pytest)

## Risks & Mitigation
- **Risk**: BFS may be too slow for large memory graphs
  - **Mitigation**: Implement strict activation limits and early termination
- **Risk**: Simple bridge discovery may produce low-quality connections
  - **Mitigation**: Focus on correctness, plan enhancement for Phase 2
- **Risk**: Threshold tuning may be challenging
  - **Mitigation**: Start with conservative values, make configurable

## Future Enhancements (Phase 2+)
- Advanced activation spreading with learned weights
- Attention-based bridge discovery mechanisms
- Dynamic threshold adjustment based on context
- Multi-modal retrieval combining different similarity metrics

## Resources
- Technical specification: `architecture-technical-specification.md`
- High-level architecture: `architecture-highlevel.md`
- Previous phases: `001_phase1_foundation.md`, `002_phase1_storage.md`
- BFS algorithm reference: Graph traversal algorithms
- Cosine similarity: Vector similarity metrics

## Change Log
- **2025-06-17**: Step 003 progress document created
- **2025-06-17**: Basic retrieval and activation scope defined
- **2025-06-17**: Algorithm specifications and architecture planned