"""
Comprehensive test suite for enhanced Heimdall architecture.

This module tests the enhanced memory system, query engine, and migration tools
to ensure proper functionality and data integrity.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch

# Import enhanced architecture components
from cognitive_memory.core.enhanced_memory import (
    EnhancedCognitiveMemory,
    TemporalWindow,
    MemoryDomain,
    SemanticCluster,
    MemoryRelationship
)
from cognitive_memory.storage.enhanced_storage import EnhancedQdrantStorage
from cognitive_memory.retrieval.enhanced_query_engine import (
    EnhancedQueryEngine,
    QueryContext,
    QueryType,
    RelevanceScore,
    create_query_context
)
from cognitive_memory.retrieval.temporal_semantic_coordinator import (
    TemporalSemanticCoordinator,
    QueryStrategy
)
from cognitive_memory.migration.enhanced_migration_tools import (
    LegacyMemory,
    EnhancedMigrationEngine,
    MigrationReport
)


class TestEnhancedCognitiveMemory:
    """Test the enhanced cognitive memory data structures."""
    
    def test_memory_creation(self):
        """Test basic memory creation and initialization."""
        memory = EnhancedCognitiveMemory(
            content="Test memory content",
            temporal_window=TemporalWindow.ACTIVE,
            semantic_domain=MemoryDomain.PROJECT_CONTEXT
        )
        
        assert memory.content == "Test memory content"
        assert memory.temporal_window == TemporalWindow.ACTIVE
        assert memory.semantic_domain == MemoryDomain.PROJECT_CONTEXT
        assert memory.access_count == 0
        assert isinstance(memory.created_date, datetime)
        assert memory.id is not None
    
    def test_access_tracking(self):
        """Test access count and timestamp tracking."""
        memory = EnhancedCognitiveMemory(content="Test")
        original_access_time = memory.last_accessed
        original_count = memory.access_count
        
        # Simulate access
        memory.update_access()
        
        assert memory.access_count == original_count + 1
        assert memory.last_accessed > original_access_time
    
    def test_age_calculation(self):
        """Test age calculation functionality."""
        past_date = datetime.now() - timedelta(days=5)
        memory = EnhancedCognitiveMemory(content="Test")
        memory.created_date = past_date
        
        age_days = memory.calculate_age_days()
        assert 4.9 < age_days < 5.1  # Allow for small timing variations
    
    def test_temporal_window_transitions(self):
        """Test temporal window transition logic."""
        # Test ACTIVE to WORKING transition
        memory = EnhancedCognitiveMemory(
            content="Test",
            temporal_window=TemporalWindow.ACTIVE
        )
        memory.created_date = datetime.now() - timedelta(days=10)
        memory.access_count = 1
        
        next_window = memory.should_transition_window()
        assert next_window == TemporalWindow.WORKING
        
        # Test WORKING to REFERENCE transition
        memory.temporal_window = TemporalWindow.WORKING
        memory.access_count = 15
        memory.importance_score = 0.9
        
        next_window = memory.should_transition_window()
        assert next_window == TemporalWindow.REFERENCE
    
    def test_contextual_keywords(self):
        """Test contextual keyword extraction."""
        memory = EnhancedCognitiveMemory(
            content="Test",
            temporal_window=TemporalWindow.ACTIVE,
            semantic_domain=MemoryDomain.PROJECT_CONTEXT
        )
        memory.user_defined_tags = {"test", "example"}
        memory.outgoing_relationships = {"rel1", "rel2"}
        
        keywords = memory.get_contextual_keywords()
        
        assert "active" in keywords
        assert "project_context" in keywords
        assert "test" in keywords
        assert "example" in keywords
        assert "has_connections" in keywords


class TestEnhancedQueryEngine:
    """Test the enhanced query engine functionality."""
    
    @pytest.fixture
    def query_engine(self):
        """Create a query engine instance for testing."""
        return EnhancedQueryEngine()
    
    @pytest.fixture
    def sample_memories(self):
        """Create sample memories for testing."""
        return [
            EnhancedCognitiveMemory(
                id="mem1",
                content="Python programming patterns and best practices",
                temporal_window=TemporalWindow.ACTIVE,
                semantic_domain=MemoryDomain.TECHNICAL_PATTERNS,
                access_count=5,
                importance_score=0.8
            ),
            EnhancedCognitiveMemory(
                id="mem2", 
                content="Project status update for trading system",
                temporal_window=TemporalWindow.WORKING,
                semantic_domain=MemoryDomain.PROJECT_CONTEXT,
                access_count=3,
                importance_score=0.6
            ),
            EnhancedCognitiveMemory(
                id="mem3",
                content="Old documentation about legacy systems",
                temporal_window=TemporalWindow.ARCHIVE,
                semantic_domain=MemoryDomain.TECHNICAL_PATTERNS,
                access_count=1,
                importance_score=0.2
            )
        ]
    
    def test_query_context_creation(self):
        """Test query context creation and configuration."""
        context = create_query_context(
            query_text="test query",
            query_type="project_status",
            max_results=5
        )
        
        assert context.query_text == "test query"
        assert context.query_type == QueryType.PROJECT_STATUS
        assert context.max_results == 5
        assert context.temporal_weight == 0.5  # Project status should prioritize temporal
    
    def test_basic_filtering(self, query_engine, sample_memories):
        """Test basic memory filtering functionality."""
        context = QueryContext(
            query_text="test",
            temporal_focus=TemporalWindow.ACTIVE
        )
        
        # Only ACTIVE memories should pass
        passing_memories = [
            memory for memory in sample_memories
            if query_engine._passes_filters(memory, context)
        ]
        
        assert len(passing_memories) == 1
        assert passing_memories[0].id == "mem1"
    
    def test_semantic_similarity_calculation(self, query_engine, sample_memories):
        """Test semantic similarity scoring."""
        context = QueryContext(query_text="Python programming")
        memory = sample_memories[0]  # Contains "Python programming"
        
        similarity = query_engine._calculate_semantic_similarity(memory, context)
        
        assert similarity > 0.0
        assert similarity <= 1.0
    
    def test_temporal_relevance_calculation(self, query_engine, sample_memories):
        """Test temporal relevance scoring."""
        context = QueryContext(query_text="test")
        
        # ACTIVE memory should have higher temporal score
        active_memory = sample_memories[0]
        archive_memory = sample_memories[2]
        
        active_score = query_engine._calculate_temporal_relevance(active_memory, context)
        archive_score = query_engine._calculate_temporal_relevance(archive_memory, context)
        
        assert active_score > archive_score
    
    def test_frequency_relevance_calculation(self, query_engine, sample_memories):
        """Test access frequency relevance scoring."""
        context = QueryContext(query_text="test")
        
        # Higher access count should result in higher frequency score
        high_access_memory = sample_memories[0]  # access_count=5
        low_access_memory = sample_memories[2]   # access_count=1
        
        high_score = query_engine._calculate_frequency_relevance(high_access_memory, context)
        low_score = query_engine._calculate_frequency_relevance(low_access_memory, context)
        
        assert high_score > low_score
    
    def test_query_processing(self, query_engine, sample_memories):
        """Test complete query processing pipeline."""
        context = QueryContext(
            query_text="programming patterns",
            max_results=3,
            min_relevance_threshold=0.0
        )
        
        results = query_engine.process_query(
            query_context=context,
            candidate_memories=sample_memories,
            relationships={},
            semantic_clusters={}
        )
        
        assert len(results) <= 3
        assert all(isinstance(r.relevance, RelevanceScore) for r in results)
        assert all(r.relevance.total_score >= 0.0 for r in results)
        
        # Results should be sorted by relevance (descending)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].relevance.total_score >= results[i + 1].relevance.total_score


class TestTemporalSemanticCoordinator:
    """Test the temporal-semantic query coordinator."""
    
    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage instance."""
        storage = Mock(spec=EnhancedQdrantStorage)
        storage.search_memories_by_window = AsyncMock(return_value=[])
        storage.get_memory_relationships = AsyncMock(return_value={})
        storage.get_semantic_clusters = AsyncMock(return_value={})
        return storage
    
    @pytest.fixture
    def coordinator(self, mock_storage):
        """Create a coordinator instance for testing."""
        query_engine = EnhancedQueryEngine()
        return TemporalSemanticCoordinator(mock_storage, query_engine)
    
    @pytest.mark.asyncio
    async def test_basic_query_execution(self, coordinator, mock_storage):
        """Test basic query execution flow."""
        # Setup mock to return sample memories
        sample_memory = EnhancedCognitiveMemory(
            content="Test memory",
            temporal_window=TemporalWindow.ACTIVE
        )
        mock_storage.search_memories_by_window.return_value = [sample_memory]
        
        results, metrics = await coordinator.query_memories(
            query_text="test query",
            max_results=5
        )
        
        assert isinstance(results, list)
        assert isinstance(metrics.total_query_time, float)
        assert metrics.total_query_time > 0
        assert mock_storage.search_memories_by_window.called
    
    @pytest.mark.asyncio
    async def test_query_strategy_adaptation(self, coordinator):
        """Test query strategy adaptation based on query type."""
        # Test PROJECT_STATUS strategy
        project_context = create_query_context(
            query_text="project status",
            query_type="project_status"
        )
        project_strategy = coordinator._create_adaptive_strategy(project_context)
        
        assert TemporalWindow.ACTIVE in project_strategy.temporal_priorities
        assert project_strategy.early_termination is True
        
        # Test TECHNICAL_PATTERN strategy
        technical_context = create_query_context(
            query_text="code pattern",
            query_type="technical_pattern"
        )
        technical_strategy = coordinator._create_adaptive_strategy(technical_context)
        
        assert TemporalWindow.REFERENCE in technical_strategy.temporal_priorities
        assert technical_strategy.early_termination is False
    
    def test_performance_tracking(self, coordinator):
        """Test performance metrics tracking."""
        # Add some mock metrics
        from cognitive_memory.retrieval.temporal_semantic_coordinator import QueryPerformanceMetrics
        
        metrics = QueryPerformanceMetrics()
        metrics.total_query_time = 0.5
        metrics.results_returned = 8
        metrics.early_termination_triggered = True
        
        coordinator.query_metrics = [metrics] * 10
        
        summary = coordinator.get_performance_summary()
        
        assert summary["total_queries"] == 10
        assert summary["recent_avg_query_time"] == 0.5
        assert summary["recent_avg_results"] == 8
        assert summary["early_termination_rate"] == 1.0


class TestEnhancedMigrationTools:
    """Test the migration tools for legacy data."""
    
    @pytest.fixture
    def sample_legacy_memories(self):
        """Create sample legacy memories for testing."""
        return [
            LegacyMemory(
                id="legacy1",
                content="L0 concept about patterns",
                hierarchy_level=0,
                memory_type="semantic",
                strength=0.8,
                created_date=datetime.now() - timedelta(days=30),
                last_accessed=datetime.now() - timedelta(days=5),
                access_count=10,
                importance_score=0.9,
                tags={"pattern", "architecture"}
            ),
            LegacyMemory(
                id="legacy2",
                content="L2 episode about debugging session",
                hierarchy_level=2,
                memory_type="episodic",
                strength=0.6,
                created_date=datetime.now() - timedelta(days=2),
                last_accessed=datetime.now() - timedelta(hours=6),
                access_count=3,
                importance_score=0.4,
                tags={"debugging", "session"}
            )
        ]
    
    @pytest.fixture
    def mock_enhanced_storage(self):
        """Create a mock enhanced storage for migration testing."""
        storage = Mock(spec=EnhancedQdrantStorage)
        storage.store_memories_batch = AsyncMock()
        return storage
    
    @pytest.fixture
    def migration_engine(self, mock_enhanced_storage):
        """Create a migration engine for testing."""
        return EnhancedMigrationEngine(mock_enhanced_storage)
    
    def test_temporal_window_determination(self, migration_engine, sample_legacy_memories):
        """Test temporal window assignment logic."""
        # L0 concept with high access should become REFERENCE
        l0_memory = sample_legacy_memories[0]
        temporal_window = migration_engine._determine_temporal_window(l0_memory)
        assert temporal_window == TemporalWindow.REFERENCE
        
        # Recent L2 episode should become ACTIVE
        l2_memory = sample_legacy_memories[1] 
        temporal_window = migration_engine._determine_temporal_window(l2_memory)
        assert temporal_window == TemporalWindow.ACTIVE
    
    def test_semantic_domain_inference(self, migration_engine, sample_legacy_memories):
        """Test semantic domain inference from content and tags."""
        # Memory with "pattern" and "architecture" should be TECHNICAL_PATTERNS
        l0_memory = sample_legacy_memories[0]
        domain = migration_engine._infer_semantic_domain(l0_memory)
        assert domain == MemoryDomain.TECHNICAL_PATTERNS
        
        # Memory with "debugging" and "session" should be SESSION_CONTINUITY
        l2_memory = sample_legacy_memories[1]
        domain = migration_engine._infer_semantic_domain(l2_memory)
        assert domain == MemoryDomain.SESSION_CONTINUITY
    
    def test_legacy_to_enhanced_conversion(self, migration_engine, sample_legacy_memories):
        """Test conversion from legacy to enhanced memory format."""
        legacy_memory = sample_legacy_memories[0]
        enhanced_memory = migration_engine._convert_legacy_to_enhanced(legacy_memory)
        
        # Verify core data preservation
        assert enhanced_memory.id == legacy_memory.id
        assert enhanced_memory.content == legacy_memory.content
        assert enhanced_memory.access_count == legacy_memory.access_count
        assert enhanced_memory.importance_score == legacy_memory.importance_score
        
        # Verify new architecture fields
        assert isinstance(enhanced_memory.temporal_window, TemporalWindow)
        assert isinstance(enhanced_memory.semantic_domain, MemoryDomain)
        assert enhanced_memory.user_defined_tags == legacy_memory.tags
        
        # Verify migration metadata
        assert "migration_info" in enhanced_memory.metadata
        assert enhanced_memory.metadata["migration_info"]["source_hierarchy_level"] == 0
    
    @pytest.mark.asyncio
    async def test_migration_batch_processing(self, migration_engine, sample_legacy_memories):
        """Test batch migration processing."""
        report = MigrationReport()
        
        await migration_engine._process_migration_batch(sample_legacy_memories, report)
        
        assert report.successfully_migrated == 2
        assert report.l0_migrated == 1
        assert report.l2_migrated == 1
        assert migration_engine.enhanced_storage.store_memories_batch.called
    
    @pytest.mark.asyncio
    async def test_full_migration_workflow(self, migration_engine, sample_legacy_memories):
        """Test complete migration workflow.""" 
        report = await migration_engine.migrate_memories(sample_legacy_memories)
        
        assert isinstance(report, MigrationReport)
        assert report.total_legacy_memories == 2
        assert report.successfully_migrated >= 0
        assert report.migration_duration > 0


class TestIntegrationScenarios:
    """Integration tests for complete system workflows."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_query_workflow(self):
        """Test complete query workflow from storage to results."""
        # This would require actual Qdrant instance for full integration
        # For now, we'll test the coordination between components
        
        # Create mock storage that returns realistic data
        mock_storage = Mock(spec=EnhancedQdrantStorage)
        
        sample_memories = [
            EnhancedCognitiveMemory(
                content="Sierra Chart trading patterns analysis",
                temporal_window=TemporalWindow.WORKING,
                semantic_domain=MemoryDomain.TECHNICAL_PATTERNS
            ),
            EnhancedCognitiveMemory(
                content="Project status for NQ futures study",
                temporal_window=TemporalWindow.ACTIVE,
                semantic_domain=MemoryDomain.PROJECT_CONTEXT
            )
        ]
        
        mock_storage.search_memories_by_window = AsyncMock(return_value=sample_memories)
        mock_storage.get_memory_relationships = AsyncMock(return_value={})
        mock_storage.get_semantic_clusters = AsyncMock(return_value={})
        
        # Create coordinator and execute query
        query_engine = EnhancedQueryEngine()
        coordinator = TemporalSemanticCoordinator(mock_storage, query_engine)
        
        results, metrics = await coordinator.query_memories(
            query_text="Sierra Chart trading analysis",
            query_type="technical_pattern",
            max_results=10
        )
        
        # Verify results
        assert len(results) > 0
        assert all(hasattr(r, 'memory') for r in results)
        assert all(hasattr(r, 'relevance') for r in results)
        assert metrics.total_query_time > 0
    
    def test_memory_lifecycle_simulation(self):
        """Test complete memory lifecycle from creation to archival."""
        # Create new memory
        memory = EnhancedCognitiveMemory(
            content="New project insight",
            temporal_window=TemporalWindow.ACTIVE,
            semantic_domain=MemoryDomain.PROJECT_CONTEXT
        )
        
        # Simulate aging and access patterns
        memory.created_date = datetime.now() - timedelta(days=8)
        memory.access_count = 1
        
        # Should transition from ACTIVE to WORKING
        next_window = memory.should_transition_window()
        assert next_window == TemporalWindow.WORKING
        
        # Apply transition
        memory.temporal_window = next_window
        memory.created_date = datetime.now() - timedelta(days=35)
        memory.access_count = 2
        
        # Should transition from WORKING to ARCHIVE
        next_window = memory.should_transition_window()
        assert next_window == TemporalWindow.ARCHIVE
        
        # High importance memories should become REFERENCE instead
        memory.access_count = 15
        memory.importance_score = 0.9
        
        next_window = memory.should_transition_window()
        assert next_window == TemporalWindow.REFERENCE


# Helper functions for test data generation
def create_test_memories(count: int = 10) -> List[EnhancedCognitiveMemory]:
    """Create a list of test memories with varied characteristics."""
    memories = []
    domains = list(MemoryDomain)
    windows = list(TemporalWindow)
    
    for i in range(count):
        memory = EnhancedCognitiveMemory(
            content=f"Test memory content {i}",
            temporal_window=windows[i % len(windows)],
            semantic_domain=domains[i % len(domains)],
            access_count=i % 10,
            importance_score=(i % 10) / 10.0
        )
        
        # Vary creation dates
        memory.created_date = datetime.now() - timedelta(days=i * 5)
        memory.last_accessed = datetime.now() - timedelta(days=i % 7)
        
        memories.append(memory)
    
    return memories


def create_test_relationships(
    memory_ids: List[str]
) -> Dict[str, List[MemoryRelationship]]:
    """Create test relationships between memories."""
    relationships = {}
    
    for i, source_id in enumerate(memory_ids[:-1]):
        target_id = memory_ids[i + 1]
        
        relationship = MemoryRelationship(
            source_memory_id=source_id,
            target_memory_id=target_id,
            relationship_type="sequential",
            strength=0.7
        )
        
        if source_id not in relationships:
            relationships[source_id] = []
        relationships[source_id].append(relationship)
    
    return relationships


if __name__ == "__main__":
    # Run specific test categories
    import subprocess
    
    print("Running enhanced Heimdall architecture tests...")
    
    # Run tests with detailed output
    result = subprocess.run([
        "python", "-m", "pytest", 
        __file__,
        "-v",
        "--tb=short"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("Errors:")
        print(result.stderr)
    
    print(f"Test run completed with return code: {result.returncode}")