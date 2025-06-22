# 020 - Incremental Git Loading System

## Overview
Implement an incremental git commit loading system that tracks processed commits and only loads new commits, replacing the current batch-only approach. This enhancement will enable real-time git integration with on-commit memory creation while maintaining all existing security and validation features.

## Status
- **Started**: 2025-06-22
- **Current Step**: Phase 1 Complete, Moving to Phase 2
- **Completion**: 25%
- **Expected Completion**: 2025-06-24

## Objectives
- [x] Implement memory-based state tracking for processed commits
- [ ] Add incremental loading mode to GitHistoryMiner
- [ ] Update GitHistoryLoader to default to incremental behavior
- [ ] Create git hook integration for real-time commit processing
- [ ] Maintain all existing security and validation features
- [ ] Ensure idempotent batch loading (skip existing commits)

## Implementation Progress

### Step 1: Memory-Based State Tracking
**Status**: ✅ Completed
**Date Range**: 2025-06-22 - 2025-06-22

#### Tasks Completed ✅
- ✅ Implement `get_latest_processed_commit()` method in GitHistoryLoader
- ✅ Query existing SQLite memories with pattern `git::commit::%`
- ✅ Extract commit hash from deterministic memory IDs
- ✅ Handle edge cases (no existing memories, corrupted state)

#### Technical Approach
```python
def get_latest_processed_commit(self, repo_path: str) -> tuple[str, datetime] | None:
    """Query SQLite to find most recent git commit memory for this repository."""
    # Query: SELECT id, created_date FROM memories
    # WHERE id LIKE 'git::commit::%'
    # ORDER BY created_date DESC LIMIT 1

    # Extract commit hash from memory ID format: git::commit::<hash>
    # Return (commit_hash, timestamp) for git history traversal
```

#### Implementation Notes
- **File Modified**: `cognitive_memory/loaders/git_loader.py`
- **Methods Added**:
  - `get_latest_processed_commit(repo_path: str) -> tuple[str, datetime] | None`
  - `_extract_commit_hash_from_memory_id(memory_id: str) -> str | None`
- **Key Features**:
  - Repository path validation for state isolation
  - Graceful error handling for edge cases
  - Support for both SHA-1 (40 char) and SHA-256 (64 char) commit hashes
  - Comprehensive test coverage (14 new tests)
- **Test Coverage**: Added `TestGitHistoryLoaderPhase1` class with 14 comprehensive tests

### Step 2: Incremental GitHistoryMiner
**Status**: Not Started
**Date Range**: 2025-06-22 - 2025-06-23

#### Tasks Planned
- Add `since_commit` parameter to `extract_commit_history()`
- Implement git log traversal from specific commit hash
- Update security validation for incremental mode
- Maintain existing max_commits safety limits

#### Technical Approach
```python
def extract_commit_history(
    self,
    since_commit: str | None = None,  # New parameter
    max_commits: int = 1000,          # Existing safety limit
    # Remove complex date filtering - use git's natural ordering
) -> Iterator[Commit]:
    """Extract commits since specified commit hash."""

    # Build git log parameters
    if since_commit:
        # Use git's native since-commit traversal
        kwargs["rev"] = f"{since_commit}..HEAD"

    # Rest of existing logic unchanged
```

#### Next Tasks
- Handle edge cases (invalid since_commit, branch switches)
- Test with various git repository states
- Ensure security limits still apply in incremental mode

### Step 3: Default Incremental Behavior
**Status**: Not Started
**Date Range**: 2025-06-23 - 2025-06-23

#### Tasks Planned
- Update GitHistoryLoader.load_from_source() to check existing state
- Make incremental loading the default behavior
- Add fallback to full history for fresh repositories
- Implement duplicate detection and skipping

#### Technical Approach
```python
def load_from_source(self, source_path: str, **kwargs) -> list[CognitiveMemory]:
    """Load git commits with automatic incremental behavior."""

    # Always check what we already have
    last_processed = self.get_latest_processed_commit(source_path)

    if last_processed:
        # Incremental mode: only new commits
        since_commit, last_timestamp = last_processed
        new_commits = self._extract_since_commit(since_commit)
    else:
        # Fresh repository: full history (with limits)
        new_commits = self._extract_full_history()

    return self._process_commits(new_commits)
```

#### Next Tasks
- Test with various repository states
- Ensure proper error handling for git failures
- Validate memory creation pipeline remains unchanged

### Step 4: Git Hook Integration
**Status**: Not Started
**Date Range**: 2025-06-23 - 2025-06-24

#### Tasks Planned
- Create simple post-commit hook script
- Add CLI command for manual incremental updates
- Document git hook setup process
- ENSURE THIS DOES NOT BREAK OTHER GIT HOOKS FROM THE USER!
- Test real-time commit processing

#### Technical Approach
```bash
#!/bin/bash
# .git/hooks/post-commit
# Process only the latest commit incrementally
cd "$(git rev-parse --show-toplevel)"
memory_system load-git --incremental --max-commits=1
```

#### Next Tasks
- Add hook installation automation
- Create documentation for manual setup
- Test hook behavior with various commit scenarios
- Handle hook failures gracefully

## Technical Notes

### Architecture Decisions
1. **Memory-Based State**: Use existing SQLite memory storage as source of truth for processed commits
2. **Deterministic IDs**: Leverage existing `git::commit::<hash>` format for state tracking
3. **Incremental-First**: Make incremental the default behavior, not an opt-in feature
4. **Security Preservation**: Maintain all existing validation and safety limits
5. **Idempotent Operations**: Ensure duplicate commits are safely skipped

### Key Implementation Details
- Query pattern: `SELECT id, created_date FROM memories WHERE id LIKE 'git::commit::%'`
- Git traversal: Use `git log --reverse since_hash..HEAD` for natural ordering
- State isolation: Include repository path validation for multi-project support
- Error handling: Graceful fallback to full history if incremental state is corrupted

### Performance Considerations
- SQLite queries for latest commit are O(log n) with proper indexing
- Git log since-commit is efficient for incremental updates
- Memory creation pipeline unchanged (no performance regression)
- Hook processing handles single commits efficiently

## Dependencies

### Internal Dependencies
- Existing GitHistoryMiner architecture
- SQLite persistence layer
- Memory deterministic ID system
- Existing security validation framework

### External Dependencies
- GitPython library (already in use)
- Git repository access
- SQLite database availability

### Blocking/Blocked By
- **Depends on**: Current git loading architecture (already implemented)
- **Blocks**: Real-time git integration features
- **Enables**: On-commit memory creation workflows

## Risks & Mitigation

### Identified Risks
1. **State Corruption**: SQLite state inconsistent with git repository
   - **Mitigation**: Validate git history against memory state, fallback to full reload

2. **Git History Rewrites**: Force pushes, rebases invalidate incremental state
   - **Mitigation**: Detect history changes, trigger full reload when necessary

3. **Performance Regression**: Additional queries slow down batch operations
   - **Mitigation**: Optimize SQLite queries, maintain existing performance benchmarks

4. **Repository Branch Switching**: Different branches have different commit histories
   - **Mitigation**: Include branch context in state tracking or document limitations

### Mitigation Strategies
- Comprehensive error handling with fallback to full history
- State validation before incremental operations
- Performance testing to ensure no regression
- Clear documentation of limitations and edge cases

## Resources

### Code References
- `cognitive_memory/git_analysis/history_miner.py` - Current git extraction logic
- `cognitive_memory/loaders/git_loader.py` - Git memory loader interface
- `cognitive_memory/storage/sqlite_persistence.py` - SQLite operations
- `cognitive_memory/git_analysis/commit_loader.py` - Commit to memory conversion

### Architecture Documentation
- `docs/arch-docs/git-integration-architecture.md` - Current git integration design
- `docs/arch-docs/memory-loading-and-decay-architecture.md` - Memory loading patterns

### External Resources
- GitPython documentation for incremental commit traversal
- Git log documentation for since-commit operations
- SQLite query optimization best practices

## Change Log
- **2025-06-22**: Initial progress document created with comprehensive implementation plan
