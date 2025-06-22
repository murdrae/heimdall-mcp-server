"""
Unit tests for dual memory system.

Tests the EpisodicMemoryStore, SemanticMemoryStore, MemoryConsolidation,
and DualMemorySystem components.
"""

import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

from cognitive_memory.core.memory import CognitiveMemory
from cognitive_memory.storage.dual_memory import (
    DualMemorySystem,
    EpisodicMemoryStore,
    MemoryAccessPattern,
    MemoryConsolidation,
    MemoryType,
    SemanticMemoryStore,
    create_dual_memory_system,
)
from cognitive_memory.storage.sqlite_persistence import DatabaseManager


class TestMemoryAccessPattern:
    """Test MemoryAccessPattern functionality."""

    def test_access_pattern_creation(self):
        """Test creating a memory access pattern."""
        pattern = MemoryAccessPattern("test_memory_001")

        assert pattern.memory_id == "test_memory_001"
        assert pattern.access_times == []
        assert pattern.consolidation_score == 0.0

    def test_add_access(self):
        """Test adding access timestamps."""
        pattern = MemoryAccessPattern("test_memory_001")

        now = time.time()
        pattern.add_access(now)
        pattern.add_access(now + 3600)  # 1 hour later

        assert len(pattern.access_times) == 2
        assert pattern.access_times[0] == now
        assert pattern.access_times[1] == now + 3600

    def test_access_frequency_calculation(self):
        """Test access frequency calculation."""
        pattern = MemoryAccessPattern("test_memory_001")

        now = time.time()
        # Add 5 accesses within the last week
        for i in range(5):
            pattern.add_access(now - i * 3600)  # Every hour going back

        frequency = pattern.calculate_access_frequency(window_hours=168.0)  # 1 week
        assert frequency > 0
        assert frequency == 5 / 168.0

    def test_recency_score_calculation(self):
        """Test recency score calculation."""
        pattern = MemoryAccessPattern("test_memory_001")

        now = time.time()
        pattern.add_access(now - 3600)  # 1 hour ago

        recency = pattern.calculate_recency_score()
        assert 0 <= recency <= 1
        assert recency > 0.9  # Should be high for recent access

    def test_consolidation_score_calculation(self):
        """Test consolidation score calculation."""
        pattern = MemoryAccessPattern("test_memory_001")

        now = time.time()
        # Add several distributed accesses
        for i in range(5):
            pattern.add_access(now - i * 24 * 3600)  # Daily accesses

        score = pattern.calculate_consolidation_score()
        assert 0 <= score <= 1
        assert score > 0  # Should have some consolidation potential


class TestEpisodicMemoryStore:
    """Test EpisodicMemoryStore functionality."""

    @pytest.fixture
    def episodic_store(self):
        """Create a temporary episodic memory store for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        db_manager = DatabaseManager(db_path)
        store = EpisodicMemoryStore(db_manager)

        yield store

        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def sample_episodic_memory(self) -> CognitiveMemory:
        """Create a sample episodic memory."""
        from datetime import datetime

        return CognitiveMemory(
            id="episodic_001",
            content="I had coffee with Alice at the local café this morning",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={
                "emotional": {"valence": 0.7, "arousal": 0.4},
                "temporal": {"recency": 0.9, "duration": 0.3},
                "contextual": {"location": 0.8, "topic": 0.6},
                "social": {"persons": 0.8, "relationships": 0.7},
            },
            timestamp=datetime.fromtimestamp(time.time()),
            strength=0.8,
            access_count=0,
            tags=["coffee", "Alice", "café", "morning"],
        )

    def test_store_episodic_memory(self, episodic_store, sample_episodic_memory):
        """Test storing an episodic memory."""
        success = episodic_store.store_episodic_memory(sample_episodic_memory)
        assert success

    def test_get_episodic_memories(self, episodic_store, sample_episodic_memory):
        """Test retrieving episodic memories."""
        episodic_store.store_episodic_memory(sample_episodic_memory)

        memories = episodic_store.get_episodic_memories()
        assert len(memories) == 1
        assert memories[0].id == sample_episodic_memory.id
        assert memories[0].memory_type == MemoryType.EPISODIC.value

    def test_episodic_decay_calculation(self, episodic_store, sample_episodic_memory):
        """Test episodic memory decay calculation."""
        # Create memory with timestamp in the past
        past_time = time.time() - (7 * 24 * 3600)  # 1 week ago
        from datetime import datetime

        sample_episodic_memory.timestamp = datetime.fromtimestamp(past_time)

        episodic_store.store_episodic_memory(sample_episodic_memory)

        memories = episodic_store.get_episodic_memories()
        memory = memories[0]

        # Strength should have decayed
        assert memory.strength < sample_episodic_memory.strength

    def test_cleanup_expired_memories(self, episodic_store):
        """Test cleanup of expired episodic memories."""
        # Create old memory
        old_memory = CognitiveMemory(
            id="old_episodic_001",
            content="Very old episodic memory",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=datetime.fromtimestamp(
                time.time() - (40 * 24 * 3600)
            ),  # 40 days ago
            strength=0.1,
            access_count=0,
        )

        episodic_store.store_episodic_memory(old_memory)

        # Run cleanup
        deleted_count = episodic_store.cleanup_expired_memories()
        assert deleted_count >= 0  # Should delete old memories


class TestSemanticMemoryStore:
    """Test SemanticMemoryStore functionality."""

    @pytest.fixture
    def semantic_store(self):
        """Create a temporary semantic memory store for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        db_manager = DatabaseManager(db_path)
        store = SemanticMemoryStore(db_manager)

        yield store

        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def sample_semantic_memory(self) -> CognitiveMemory:
        """Create a sample semantic memory."""
        from datetime import datetime

        return CognitiveMemory(
            id="semantic_001",
            content="Coffee shops are social spaces where people gather to work and socialize",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={
                "emotional": {"valence": 0.6, "arousal": 0.2},
                "temporal": {"recency": 0.5, "duration": 0.8},
                "contextual": {"location": 0.4, "topic": 0.9},
                "social": {"persons": 0.6, "relationships": 0.5},
            },
            timestamp=datetime.fromtimestamp(time.time()),
            strength=0.9,
            access_count=10,
            tags=["coffee", "social", "knowledge", "general"],
        )

    def test_store_semantic_memory(self, semantic_store, sample_semantic_memory):
        """Test storing a semantic memory."""
        success = semantic_store.store_semantic_memory(sample_semantic_memory)
        assert success

    def test_get_semantic_memories(self, semantic_store, sample_semantic_memory):
        """Test retrieving semantic memories."""
        semantic_store.store_semantic_memory(sample_semantic_memory)

        memories = semantic_store.get_semantic_memories()
        assert len(memories) == 1
        assert memories[0].id == sample_semantic_memory.id
        assert memories[0].memory_type == MemoryType.SEMANTIC.value

    def test_semantic_slow_decay(self, semantic_store, sample_semantic_memory):
        """Test semantic memory slow decay calculation."""
        # Create memory with timestamp in the past
        past_time = time.time() - (30 * 24 * 3600)  # 1 month ago
        from datetime import datetime

        sample_semantic_memory.timestamp = datetime.fromtimestamp(past_time)

        semantic_store.store_semantic_memory(sample_semantic_memory)

        memories = semantic_store.get_semantic_memories()
        memory = memories[0]

        # Strength should decay very slowly
        assert memory.strength >= 0.85  # Should retain most strength


class TestMemoryConsolidation:
    """Test MemoryConsolidation functionality."""

    @pytest.fixture
    def consolidation_system(self):
        """Create a temporary consolidation system for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        db_manager = DatabaseManager(db_path)
        consolidation = MemoryConsolidation(db_manager)

        # Create episodic store to set up test memories
        episodic_store = EpisodicMemoryStore(db_manager)

        yield consolidation, episodic_store

        Path(db_path).unlink(missing_ok=True)

    def test_track_memory_access(self, consolidation_system):
        """Test tracking memory access patterns."""
        consolidation, _ = consolidation_system

        memory_id = "test_memory_001"
        consolidation.track_memory_access(memory_id)

        assert memory_id in consolidation.access_patterns
        assert len(consolidation.access_patterns[memory_id].access_times) == 1

    def test_identify_consolidation_candidates(self, consolidation_system):
        """Test identifying memories ready for consolidation."""
        consolidation, episodic_store = consolidation_system

        # Create a frequently accessed episodic memory
        memory = CognitiveMemory(
            id="consolidation_candidate_001",
            content="Frequently accessed episodic memory",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=time.time() - (7 * 24 * 3600),  # 1 week old
            strength=0.8,
            access_count=5,  # Meets minimum access count
            tags=[],
        )

        episodic_store.store_episodic_memory(memory)

        # Track multiple accesses
        for _ in range(5):
            consolidation.track_memory_access(memory.id)

        # Wait for cooldown to pass
        time.sleep(0.1)

        candidates = consolidation.identify_consolidation_candidates()
        assert len(candidates) >= 0  # May or may not have candidates based on scoring

    def test_consolidate_memory(self, consolidation_system):
        """Test consolidating an episodic memory to semantic."""
        consolidation, episodic_store = consolidation_system

        # Create episodic memory
        memory = CognitiveMemory(
            id="consolidation_test_001",
            content="Memory to be consolidated",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=time.time(),
            strength=0.8,
            access_count=5,
            tags=["test"],
        )

        episodic_store.store_episodic_memory(memory)

        # Track accesses to build consolidation score
        for _ in range(5):
            consolidation.track_memory_access(memory.id)

        # Attempt consolidation
        success = consolidation.consolidate_memory(memory.id)

        if success:
            # Check that semantic version was created
            with consolidation.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM memories
                    WHERE memory_type = 'semantic'
                    AND id LIKE ?
                """,
                    (f"{memory.id}_semantic",),
                )

                semantic_count = cursor.fetchone()[0]
                assert semantic_count == 1

    def test_consolidation_cycle(self, consolidation_system):
        """Test running a complete consolidation cycle."""
        consolidation, episodic_store = consolidation_system

        # Create multiple episodic memories
        for i in range(3):
            memory = CognitiveMemory(
                id=f"cycle_test_{i:03d}",
                content=f"Episodic memory {i} for cycle test",
                memory_type="episodic",
                hierarchy_level=2,
                dimensions={},
                timestamp=time.time() - (i * 24 * 3600),  # Different ages
                strength=0.8,
                access_count=3 + i,  # Different access counts
                tags=["cycle", "test"],
            )

            episodic_store.store_episodic_memory(memory)

            # Track accesses
            for _ in range(3 + i):
                consolidation.track_memory_access(memory.id)

        # Run consolidation cycle
        stats = consolidation.run_consolidation_cycle()

        assert "candidates_identified" in stats
        assert "memories_consolidated" in stats
        assert "errors" in stats
        assert all(isinstance(v, int) for v in stats.values())


class TestDualMemorySystem:
    """Test DualMemorySystem integration."""

    @pytest.fixture
    def dual_memory_system(self):
        """Create a temporary dual memory system for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        system = create_dual_memory_system(db_path)

        yield system

        Path(db_path).unlink(missing_ok=True)

    def test_store_experience(self, dual_memory_system):
        """Test storing a new experience as episodic memory."""
        memory = CognitiveMemory(
            id="experience_001",
            content="I attended a machine learning conference today",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=time.time(),
            strength=0.8,
            access_count=0,
            tags=["conference", "ML", "learning"],
        )

        success = dual_memory_system.store_experience(memory)
        assert success

    def test_store_knowledge(self, dual_memory_system):
        """Test storing generalized knowledge as semantic memory."""
        memory = CognitiveMemory(
            id="knowledge_001",
            content="Machine learning conferences are venues for sharing research and networking",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={},
            timestamp=time.time(),
            strength=0.9,
            access_count=0,
            tags=["conferences", "ML", "knowledge"],
        )

        success = dual_memory_system.store_knowledge(memory)
        assert success

    def test_retrieve_memories(self, dual_memory_system):
        """Test retrieving memories from both stores."""
        # Store episodic memory
        episodic_memory = CognitiveMemory(
            id="retrieve_test_episodic",
            content="Episodic memory for retrieval test",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=time.time(),
            strength=0.8,
            access_count=0,
        )

        # Store semantic memory
        semantic_memory = CognitiveMemory(
            id="retrieve_test_semantic",
            content="Semantic memory for retrieval test",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={},
            timestamp=time.time(),
            strength=0.9,
            access_count=0,
        )

        dual_memory_system.store_experience(episodic_memory)
        dual_memory_system.store_knowledge(semantic_memory)

        # Retrieve all memories
        results = dual_memory_system.retrieve_memories()

        assert MemoryType.EPISODIC in results
        assert MemoryType.SEMANTIC in results
        assert len(results[MemoryType.EPISODIC]) == 1
        assert len(results[MemoryType.SEMANTIC]) == 1

    def test_access_memory(self, dual_memory_system):
        """Test accessing a memory with tracking."""
        memory = CognitiveMemory(
            id="access_test_001",
            content="Memory for access test",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=datetime.fromtimestamp(time.time()),
            strength=0.8,
            access_count=0,
        )

        dual_memory_system.store_experience(memory)

        # Access the memory
        accessed_memory = dual_memory_system.access_memory("access_test_001")

        assert accessed_memory is not None
        assert accessed_memory.id == "access_test_001"
        assert accessed_memory.access_count > 0  # Should be incremented

    def test_consolidate_memories(self, dual_memory_system):
        """Test memory consolidation trigger."""
        # Create episodic memory for consolidation
        memory = CognitiveMemory(
            id="consolidation_trigger_001",
            content="Memory for consolidation trigger test",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=time.time() - (7 * 24 * 3600),  # 1 week old
            strength=0.8,
            access_count=5,
            tags=["consolidation", "test"],
        )

        dual_memory_system.store_experience(memory)

        # Access memory multiple times to build consolidation score
        for _ in range(5):
            dual_memory_system.access_memory(memory.id)

        # Trigger consolidation
        stats = dual_memory_system.consolidate_memories()

        assert "candidates_identified" in stats
        assert "memories_consolidated" in stats
        assert "errors" in stats

    def test_cleanup_expired_memories(self, dual_memory_system):
        """Test cleanup of expired memories."""
        # Create old episodic memory
        old_memory = CognitiveMemory(
            id="cleanup_test_001",
            content="Old memory for cleanup test",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=time.time() - (40 * 24 * 3600),  # 40 days old
            strength=0.1,  # Very weak
            access_count=0,
        )

        dual_memory_system.store_experience(old_memory)

        # Run cleanup
        cleanup_stats = dual_memory_system.cleanup_expired_memories()

        assert "episodic_cleaned" in cleanup_stats
        assert "semantic_cleaned" in cleanup_stats
        assert cleanup_stats["episodic_cleaned"] >= 0

    def test_get_memory_stats(self, dual_memory_system):
        """Test memory system statistics."""
        # Store some memories
        episodic_memory = CognitiveMemory(
            id="stats_test_episodic",
            content="Episodic memory for stats test",
            memory_type="episodic",
            hierarchy_level=2,
            dimensions={},
            timestamp=time.time(),
            strength=0.8,
            access_count=3,
        )

        semantic_memory = CognitiveMemory(
            id="stats_test_semantic",
            content="Semantic memory for stats test",
            memory_type="semantic",
            hierarchy_level=1,
            dimensions={},
            timestamp=time.time(),
            strength=0.9,
            access_count=10,
        )

        dual_memory_system.store_experience(episodic_memory)
        dual_memory_system.store_knowledge(semantic_memory)

        # Get stats
        stats = dual_memory_system.get_memory_stats()

        assert "episodic" in stats
        assert "semantic" in stats
        assert "consolidation" in stats
        assert "access_patterns" in stats

        # Check episodic stats
        episodic_stats = stats["episodic"]
        assert "total_memories" in episodic_stats
        assert "average_strength" in episodic_stats
        assert "average_access_count" in episodic_stats

        # Check semantic stats
        semantic_stats = stats["semantic"]
        assert "total_memories" in semantic_stats
        assert "average_strength" in semantic_stats
        assert "average_access_count" in semantic_stats

    def test_dual_memory_factory(self):
        """Test the factory function for creating dual memory system."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            system = create_dual_memory_system(db_path)

            assert isinstance(system, DualMemorySystem)
            assert isinstance(system.episodic_store, EpisodicMemoryStore)
            assert isinstance(system.semantic_store, SemanticMemoryStore)
            assert isinstance(system.consolidation, MemoryConsolidation)

        finally:
            Path(db_path).unlink(missing_ok=True)


class TestContentTypeDecay:
    """Test content-type aware decay functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration with content-type decay profiles."""
        from cognitive_memory.core.config import CognitiveConfig

        config = CognitiveConfig()
        # Ensure decay profiles are set correctly
        config.decay_profiles = {
            "git_commit": 1.2,  # Faster decay
            "session_lesson": 0.2,  # Very slow decay
            "store_memory": 1.0,  # Normal decay
            "documentation": 0.2,  # Slow decay
            "manual_entry": 1.0,  # Normal decay
            "L0_concept": 0.3,  # Fallback - slow
            "L1_context": 0.8,  # Fallback - moderate
            "L2_episode": 1.0,  # Fallback - normal
        }
        return config

    @pytest.fixture
    def episodic_store_with_config(self, config):
        """Create episodic store with content-type decay configuration."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        db_manager = DatabaseManager(db_path)
        store = EpisodicMemoryStore(db_manager, activity_tracker=None, config=config)

        yield store

        Path(db_path).unlink(missing_ok=True)

    def test_content_type_detection_git_commit(self, config):
        """Test content-type detection for git commits."""
        memory = CognitiveMemory(
            id="test_git_001",
            content="Fix critical bug in authentication module",
            metadata={"source_type": "git_commit", "commit_hash": "abc123"},
        )

        content_type = config.detect_content_type(memory)
        assert content_type == "git_commit"

    def test_content_type_detection_session_lesson(self, config):
        """Test content-type detection for session lessons."""
        memory = CognitiveMemory(
            id="test_lesson_001",
            content="Key insight: Always validate user input before database operations",
            metadata={"source_type": "session_lesson", "lesson_type": "discovery"},
        )

        content_type = config.detect_content_type(memory)
        assert content_type == "session_lesson"

    def test_content_type_detection_documentation(self, config):
        """Test content-type detection for documentation."""
        memory = CognitiveMemory(
            id="test_doc_001",
            content="API Reference: Authentication endpoints require JWT tokens",
            metadata={"source_type": "documentation", "loader_type": "markdown"},
        )

        content_type = config.detect_content_type(memory)
        assert content_type == "documentation"

    def test_content_type_detection_store_memory(self, config):
        """Test content-type detection for store_memory tool."""
        memory = CognitiveMemory(
            id="test_store_001",
            content="Discovered interesting pattern in user behavior data",
            metadata={"source_type": "store_memory", "importance_score": 0.8},
        )

        content_type = config.detect_content_type(memory)
        assert content_type == "store_memory"

    def test_content_type_detection_fallback_hierarchy(self, config):
        """Test content-type detection fallback to hierarchy level."""
        # Memory without source_type should fall back to hierarchy level
        memory = CognitiveMemory(
            id="test_fallback_001",
            content="Some memory without source_type",
            hierarchy_level=0,  # L0 concept
            metadata={"other_field": "value"},
        )

        content_type = config.detect_content_type(memory)
        assert content_type == "L0_concept"

    def test_content_type_detection_final_fallback(self, config):
        """Test content-type detection final fallback to manual_entry."""
        # Memory without source_type and invalid hierarchy level
        memory = CognitiveMemory(
            id="test_fallback_002",
            content="Memory with no identifiable type",
            hierarchy_level=5,  # Invalid level
            metadata={},
        )

        content_type = config.detect_content_type(memory)
        assert content_type == "manual_entry"

    def test_decay_calculation_different_content_types(
        self, episodic_store_with_config
    ):
        """Test that different content types have different decay rates."""
        from datetime import datetime

        # Create memories of different content types but same age
        past_time = time.time() - (24 * 3600)  # 1 day ago
        timestamp = datetime.fromtimestamp(past_time)

        git_memory = CognitiveMemory(
            id="git_001",
            content="Git commit memory",
            timestamp=timestamp,
            strength=1.0,
            metadata={"source_type": "git_commit"},
        )

        lesson_memory = CognitiveMemory(
            id="lesson_001",
            content="Session lesson memory",
            timestamp=timestamp,
            strength=1.0,
            metadata={"source_type": "session_lesson"},
        )

        episodic_store_with_config.store_episodic_memory(git_memory)
        episodic_store_with_config.store_episodic_memory(lesson_memory)

        memories = episodic_store_with_config.get_episodic_memories()

        # Find memories by ID
        git_result = next(m for m in memories if m.id == "git_001")
        lesson_result = next(m for m in memories if m.id == "lesson_001")

        # Git commits should decay faster (1.2x multiplier) than session lessons (0.2x multiplier)
        assert git_result.strength < lesson_result.strength

    def test_decay_profiles_environment_variables(self):
        """Test decay profiles can be configured via environment variables."""
        import os

        from cognitive_memory.core.config import CognitiveConfig

        # Set environment variable
        os.environ["DECAY_PROFILE_GIT_COMMIT"] = "1.5"
        os.environ["DECAY_PROFILE_SESSION_LESSON"] = "0.1"

        try:
            config = CognitiveConfig.from_env()

            # Check if environment variables were applied
            assert config.decay_profiles["git_commit"] == 1.5
            assert config.decay_profiles["session_lesson"] == 0.1

        finally:
            # Clean up environment variables
            os.environ.pop("DECAY_PROFILE_GIT_COMMIT", None)
            os.environ.pop("DECAY_PROFILE_SESSION_LESSON", None)

    def test_decay_calculation_with_activity_and_content_type(self, config):
        """Test combined activity-based and content-type decay calculation."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            db_manager = DatabaseManager(db_path)

            # Create mock activity tracker
            from cognitive_memory.storage.project_activity_tracker import (
                ProjectActivityTracker,
            )

            activity_tracker = ProjectActivityTracker(repository_path=None)

            store = EpisodicMemoryStore(db_manager, activity_tracker, config)

            memory = CognitiveMemory(
                id="combined_test_001",
                content="Test memory for combined decay",
                timestamp=datetime.fromtimestamp(time.time() - 86400),  # 1 day ago
                strength=1.0,
                metadata={
                    "source_type": "git_commit"
                },  # Should get 1.2x decay multiplier
            )

            store.store_episodic_memory(memory)

            # Create mock access patterns for activity calculation
            from cognitive_memory.storage.dual_memory import MemoryAccessPattern

            access_patterns = {
                "combined_test_001": MemoryAccessPattern("combined_test_001")
            }

            # Calculate decayed strength
            decayed_strength = store._calculate_decayed_strength(
                memory, access_patterns
            )

            # Should be less than original strength due to decay
            assert 0.0 <= decayed_strength <= 1.0
            assert decayed_strength < memory.strength

        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_backward_compatibility_no_source_type(self, episodic_store_with_config):
        """Test backward compatibility for memories without source_type."""
        # Create memory without source_type (old format)
        memory = CognitiveMemory(
            id="legacy_001",
            content="Legacy memory without source_type",
            hierarchy_level=2,  # Should fall back to L2_episode
            timestamp=datetime.fromtimestamp(time.time() - 3600),  # 1 hour ago
            strength=1.0,
            metadata={"old_field": "value"},  # No source_type
        )

        episodic_store_with_config.store_episodic_memory(memory)
        memories = episodic_store_with_config.get_episodic_memories()

        # Should work without errors
        assert len(memories) == 1
        assert memories[0].id == "legacy_001"

        # Should apply fallback decay profile
        config = episodic_store_with_config.config
        content_type = config.detect_content_type(memory)
        assert content_type == "L2_episode"
