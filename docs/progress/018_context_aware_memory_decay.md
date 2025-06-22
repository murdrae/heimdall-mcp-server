# 018 - Context-Aware Memory Decay Implementation

## Overview
Implement context-aware memory decay system to replace calendar-based decay with project activity and content-type aware decay mechanisms. This addresses the limitation where memories decay during project breaks (vacations) when they're still valid, while enabling faster decay during active development periods when memories become outdated quickly.

## Status
- **Started**: 2025-06-22
- **Current Step**: Step 1 Complete - Project Activity Tracking Implementation
- **Completion**: 20% (1 of 5 steps completed)
- **Expected Completion**: Step 2 ready for implementation

## Objectives
- [x] Add project activity tracking based on git commits and memory accesses
- [ ] Implement content-type aware decay profiles configuration
- [ ] Integrate activity-based and content-type decay into existing dual memory system
- [ ] Test and validate new decay behavior
- [ ] Document configuration options for decay profiles

## Implementation Progress

### Step 1: Project Activity Tracking Implementation
**Status**: ✅ COMPLETED
**Date Range**: 2025-06-22
**Implementation Time**: ~4 hours

#### Tasks Completed
- ✅ Create `ProjectActivityTracker` class to monitor project activity
- ✅ Implement activity score calculation using git commits and memory accesses
- ✅ Add activity-based decay rate scaling (dormant projects = 0.1x decay, active projects = 2.0x decay)
- ✅ Integrate activity tracker into `DualMemorySystem`
- ✅ Add comprehensive configuration parameters to `CognitiveConfig`
- ✅ Create comprehensive unit test suite (20 tests, all passing)
- ✅ Ensure backward compatibility with existing memory system

#### Files Created/Modified
**New Files:**
- `cognitive_memory/storage/project_activity_tracker.py` - Core activity tracking implementation
- `tests/unit/test_project_activity_tracker.py` - Comprehensive test suite (20 tests)

**Modified Files:**
- `cognitive_memory/core/config.py` - Added 9 new configuration parameters with validation
- `cognitive_memory/storage/dual_memory.py` - Integrated activity tracking into memory stores

#### Implementation Results
- **Git Activity Tracking**: Successfully tracks commit patterns over configurable time windows
- **Memory Access Tracking**: Leverages existing `MemoryAccessPattern` for access-based scoring
- **Activity Score Formula**: `activity_score = 0.6 * commit_score + 0.4 * access_score` (implemented)
- **Decay Rate Scaling**: High/Normal/Low activity levels with 2.0x/1.0x/0.1x multipliers (implemented)
- **Caching System**: 5-minute TTL cache for activity calculations to optimize performance
- **Configuration**: 9 new environment variables for complete customization
- **Testing**: 100% backward compatibility maintained, all existing tests pass

#### Validation Results
- ✅ Live demo with real git repository (87 commits, normal activity level)
- ✅ Activity score calculation: Git=0.967, Access=0.000, Overall=0.580
- ✅ Decay rate scaling working correctly (1.0x multiplier for normal activity)
- ✅ Memory storage and retrieval functioning with context-aware decay
- ✅ Performance: Efficient caching and batch calculations implemented

#### Technical Specifications (Implemented)
```python
# Activity calculation formulas (as implemented):
max_score_commits = 3 * days  # 3 commits per day = max score
max_score_activity = 100 * days  # 100 memory accesses per day = max score

activity_score = 0.6 * commit_score + 0.4 * access_score

# Decay scaling based on activity (implemented):
# - High activity (>0.7): 2.0x faster decay
# - Normal activity (0.2-0.7): 1.0x normal decay
# - Low activity (<0.2): 0.1x slower decay

# Configuration parameters added to CognitiveConfig:
activity_window_days: int = 30
max_commits_per_day: int = 3
max_accesses_per_day: int = 100
activity_commit_weight: float = 0.6
activity_access_weight: float = 0.4
high_activity_threshold: float = 0.7
low_activity_threshold: float = 0.2
high_activity_multiplier: float = 2.0
normal_activity_multiplier: float = 1.0
low_activity_multiplier: float = 0.1
```

#### Environment Variables Added
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

### Step 2: Content-Type Decay Profiles Configuration
**Status**: Not Started
**Date Range**: TBD

#### Tasks Planned
- Add decay profiles configuration to `CognitiveConfig` in `cognitive_memory/core/config.py`
- Implement content-type detection from memory tags and metadata
- Create decay multiplier calculation function
- Add environment variable support for decay profile customization

#### Technical Specifications
```python
# Configuration addition to CognitiveConfig:
@dataclass
class CognitiveConfig:
    # ... existing fields ...

    # Content-type decay profiles (multipliers applied to base decay rate)
    decay_profiles: dict[str, float] = field(default_factory=lambda: {
        # Memory tags -> decay multipliers
        "architectural_decision": 0.1,     # 10x slower decay
        "session_lesson": 0.3,             # 3x slower decay
        "git_commit": 0.5,                 # Moderate decay
        "bug_fix": 2.0,                    # 2x faster decay
        "implementation": 1.5,             # 1.5x faster decay
        "documentation": 0.7,              # Slower decay
        "exploration": 1.8,                # Faster decay

        # Hierarchy level defaults
        "L0_concept": 0.2,                 # Concepts decay very slowly
        "L1_context": 0.8,                 # Context moderately
        "L2_episode": 1.0,                 # Episodes at base rate
    })
```

### Step 3: Enhanced Decay Calculation Integration
**Status**: Partially Complete (Activity Integration Done)
**Date Range**: TBD

#### Tasks Status
- ✅ Modify `_calculate_decayed_strength()` in `EpisodicMemoryStore` and `SemanticMemoryStore`
- [ ] Implement combined decay rate calculation using activity and content-type multipliers (activity part done)
- ✅ Update memory retrieval to use new decay calculations
- ✅ Ensure backward compatibility with existing memories

#### Implementation Notes
Activity-based decay calculation has been implemented in Step 1. Content-type multipliers will be added in Step 2.

#### Technical Specifications (Partially Implemented)
```python
def _calculate_decayed_strength(
    self, memory: CognitiveMemory, access_patterns: dict = None
) -> float:
    """Calculate current strength with context-aware decay (IMPLEMENTED)"""

    # Get base decay components
    now = time.time()
    timestamp_val = memory.timestamp.timestamp()
    time_elapsed = (now - timestamp_val) / 3600  # hours

    # Get activity-based multiplier (IMPLEMENTED)
    effective_decay_rate = self.decay_rate
    if self.activity_tracker and access_patterns is not None:
        effective_decay_rate = self.activity_tracker.get_dynamic_decay_rate(
            self.decay_rate, access_patterns
        )

    # TODO: Add content-type multiplier (Step 2)
    # content_multiplier = get_content_decay_multiplier(memory)
    # effective_decay_rate *= content_multiplier

    # Apply exponential decay
    decayed_strength = memory.strength * math.exp(
        -effective_decay_rate * time_elapsed / 24
    )

    return max(0.0, min(1.0, decayed_strength))
```

### Step 4: Testing and Validation
**Status**: Partially Complete (Activity Tracking Tests Done)
**Date Range**: TBD

#### Tasks Status
- ✅ Create unit tests for activity tracking calculations (20 tests, all passing)
- [ ] Test decay behavior with different content types (pending Step 2)
- ✅ Validate decay scaling under various project activity scenarios
- ✅ Performance testing to ensure minimal overhead (caching implemented)
- ✅ Integration tests with existing memory retrieval system (backward compatibility confirmed)

#### Testing Results (Step 1)
- **Unit Tests**: 20/20 tests passing for `ProjectActivityTracker`
- **Integration Tests**: 24/24 existing tests still passing for `DualMemorySystem`
- **Live Demo**: Successfully tested with real git repository
- **Performance**: Efficient caching system implemented with 5-minute TTL
- **Backward Compatibility**: 100% maintained - existing code works unchanged

### Step 5: Documentation and Configuration
**Status**: Not Started
**Date Range**: TBD

#### Tasks Planned
- Update CLAUDE.md with new decay system documentation
- Document environment variables for decay profile configuration
- Create examples of decay profile customization
- Update architecture documentation

## Technical Notes

### Key Design Decisions
1. **Activity-Based Scaling**: Use git commit frequency and memory access patterns rather than calendar time
2. **Content-Type Awareness**: Different memory types (architectural decisions vs bug fixes) should have different decay rates
3. **Configuration-Driven**: Decay profiles should be configurable via environment variables
4. **Backward Compatibility**: Existing memories should work with new decay system without migration

### Integration Points
- `cognitive_memory/storage/dual_memory.py`: Core decay calculation logic
- `cognitive_memory/core/config.py`: Configuration for decay profiles
- `cognitive_memory/storage/sqlite_persistence.py`: Access tracking for activity calculation
- Git memory loading: Commit frequency tracking for activity score

## Dependencies
- Existing dual memory system (`DualMemorySystem`, `EpisodicMemoryStore`, `SemanticMemoryStore`)
- Configuration system (`CognitiveConfig`)
- Git memory integration for commit tracking
- SQLite persistence for access pattern tracking

## Risks & Mitigation

### Risks Addressed in Step 1
- **Performance Impact**: Activity tracking could add overhead to memory operations
  - ✅ *Mitigation Implemented*: Efficient caching (5-minute TTL) and batch activity calculations
- **Configuration Complexity**: Too many decay parameters could be confusing
  - ✅ *Mitigation Implemented*: Sensible defaults provided, 9 environment variables with validation
- **Backward Compatibility**: Changes to decay calculation could affect existing memories
  - ✅ *Mitigation Implemented*: 100% backward compatibility maintained, gradual opt-in system

### Remaining Risks for Future Steps
- **Content-Type Configuration**: Too many content-type profiles could be overwhelming
  - *Planned Mitigation*: Start with essential profiles, allow gradual customization
- **Performance with Complex Profiles**: Multiple content-type multipliers could impact speed
  - *Planned Mitigation*: Profile performance testing and optimization

## Resources

### Implemented (Step 1)
- **Activity tracking**: `cognitive_memory/storage/project_activity_tracker.py` - Core implementation
- **Configuration**: `cognitive_memory/core/config.py` - Extended with activity tracking parameters
- **Memory stores**: `cognitive_memory/storage/dual_memory.py` - Updated with activity-aware decay
- **Tests**: `tests/unit/test_project_activity_tracker.py` - Comprehensive test suite

### Existing (Leveraged)
- **Memory access tracking**: `MemoryAccessPattern` class in `dual_memory.py`
- **Git integration**: `cognitive_memory/git_analysis/history_miner.py`
- **Database persistence**: `cognitive_memory/storage/sqlite_persistence.py`

## Change Log
- **2025-06-22**: Initial document creation and design specification
- **2025-06-22**: Step 1 implementation completed - Project Activity Tracking
  - Created `ProjectActivityTracker` class with full git and memory access integration
  - Added 9 new configuration parameters with environment variable support
  - Implemented activity-based decay rate scaling (2.0x/1.0x/0.1x multipliers)
  - Created comprehensive test suite (20 tests, all passing)
  - Maintained 100% backward compatibility
  - Validated with live demo using real git repository
  - Step 1 completion: 20% of overall project complete
