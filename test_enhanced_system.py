#!/usr/bin/env python3
"""
Test script for enhanced Heimdall architecture.

This script validates the enhanced memory system functionality
including storage, retrieval, and query processing.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from cognitive_memory.core.enhanced_memory import (
    EnhancedCognitiveMemory,
    TemporalWindow,
    MemoryDomain
)
from cognitive_memory.storage.enhanced_storage import EnhancedQdrantStorage
from cognitive_memory.retrieval.enhanced_query_engine import (
    EnhancedQueryEngine,
    create_query_context
)
from cognitive_memory.retrieval.temporal_semantic_coordinator import (
    TemporalSemanticCoordinator
)


# Mock storage for testing without Qdrant dependency
class MockEnhancedStorage:
    """Mock storage for testing the enhanced architecture."""
    
    def __init__(self):
        self.memories = {}
        self.relationships = {}
        self.clusters = {}
    
    async def initialize(self):
        """Initialize mock storage."""
        print("✓ Mock storage initialized")
    
    async def store_memory(self, memory: EnhancedCognitiveMemory):
        """Store a memory in mock storage."""
        self.memories[memory.id] = memory
        print(f"✓ Stored memory: {memory.id[:8]}... in {memory.temporal_window.value}")
    
    async def store_memories_batch(self, memories):
        """Store multiple memories."""
        for memory in memories:
            await self.store_memory(memory)
    
    async def search_memories_by_window(self, query_text, temporal_window, semantic_domain=None, limit=20, min_similarity=0.1):
        """Search memories by temporal window."""
        results = []
        for memory in self.memories.values():
            if memory.temporal_window == temporal_window:
                # Simple keyword matching for mock
                if any(word.lower() in memory.content.lower() for word in query_text.split()):
                    results.append(memory)
                    if len(results) >= limit:
                        break
        return results
    
    async def get_memory_relationships(self, memory_ids):
        """Get relationships for memories."""
        return self.relationships
    
    async def get_semantic_clusters(self, cluster_ids):
        """Get semantic clusters."""
        return self.clusters
    
    async def get_system_statistics(self):
        """Get system statistics."""
        by_window = {}
        by_domain = {}
        
        for memory in self.memories.values():
            window = memory.temporal_window.value
            domain = memory.semantic_domain.value
            
            by_window[window] = by_window.get(window, 0) + 1
            by_domain[domain] = by_domain.get(domain, 0) + 1
        
        return {
            'total_memories': len(self.memories),
            'active_memories': by_window.get('active', 0),
            'working_memories': by_window.get('working', 0),
            'reference_memories': by_window.get('reference', 0),
            'archive_memories': by_window.get('archive', 0),
            'domain_distribution': by_domain
        }


async def test_enhanced_memory_creation():
    """Test enhanced memory creation and properties."""
    print("\n🧪 Testing Enhanced Memory Creation...")
    
    memory = EnhancedCognitiveMemory(
        content="This is a test memory about Sierra Chart trading patterns",
        temporal_window=TemporalWindow.ACTIVE,
        semantic_domain=MemoryDomain.TECHNICAL_PATTERNS,
        importance_score=0.8
    )
    
    memory.user_defined_tags = {"sierra_chart", "trading", "test"}
    
    # Test basic properties
    assert memory.content != ""
    assert memory.temporal_window == TemporalWindow.ACTIVE
    assert memory.semantic_domain == MemoryDomain.TECHNICAL_PATTERNS
    assert memory.importance_score == 0.8
    assert "sierra_chart" in memory.user_defined_tags
    
    # Test access tracking
    original_count = memory.access_count
    memory.update_access()
    assert memory.access_count == original_count + 1
    
    # Test contextual keywords
    keywords = memory.get_contextual_keywords()
    assert "active" in keywords
    assert "technical_patterns" in keywords
    assert "sierra_chart" in keywords
    
    print("✓ Enhanced memory creation tests passed")
    
    return memory


async def test_temporal_window_transitions():
    """Test temporal window transition logic."""
    print("\n🕒 Testing Temporal Window Transitions...")
    
    # Create an old ACTIVE memory with low access
    memory = EnhancedCognitiveMemory(
        content="Old active memory",
        temporal_window=TemporalWindow.ACTIVE
    )
    memory.created_date = datetime.now() - timedelta(days=10)
    memory.access_count = 1
    
    # Should transition to WORKING
    next_window = memory.should_transition_window()
    assert next_window == TemporalWindow.WORKING
    print("✓ ACTIVE → WORKING transition logic works")
    
    # Create a high-value WORKING memory
    memory.temporal_window = TemporalWindow.WORKING
    memory.access_count = 15
    memory.importance_score = 0.9
    
    # Should transition to REFERENCE
    next_window = memory.should_transition_window()
    assert next_window == TemporalWindow.REFERENCE
    print("✓ WORKING → REFERENCE transition logic works")
    
    print("✓ Temporal window transition tests passed")


async def test_query_engine():
    """Test the enhanced query engine."""
    print("\n🔍 Testing Enhanced Query Engine...")
    
    # Create sample memories
    memories = [
        EnhancedCognitiveMemory(
            id="mem1",
            content="Sierra Chart trading system with OFI indicators",
            temporal_window=TemporalWindow.ACTIVE,
            semantic_domain=MemoryDomain.TECHNICAL_PATTERNS,
            access_count=5,
            importance_score=0.8
        ),
        EnhancedCognitiveMemory(
            id="mem2",
            content="Project status update for NQ futures analysis",
            temporal_window=TemporalWindow.WORKING,
            semantic_domain=MemoryDomain.PROJECT_CONTEXT,
            access_count=3,
            importance_score=0.6
        ),
        EnhancedCognitiveMemory(
            id="mem3",
            content="Old documentation about legacy indicators",
            temporal_window=TemporalWindow.ARCHIVE,
            semantic_domain=MemoryDomain.TECHNICAL_PATTERNS,
            access_count=1,
            importance_score=0.2
        )
    ]
    
    # Test query engine
    query_engine = EnhancedQueryEngine()
    
    # Test query context creation
    context = create_query_context(
        query_text="Sierra Chart trading",
        query_type="technical_pattern",
        max_results=5
    )
    
    assert context.query_text == "Sierra Chart trading"
    assert context.query_type.value == "technical_pattern"
    
    # Apply query type weights manually to test
    query_engine._apply_query_type_weights(context)
    print(f"Debug: semantic_weight after applying = {context.semantic_weight}")
    assert context.semantic_weight == 0.5  # Technical patterns prioritize semantic
    
    # Test query processing
    results = query_engine.process_query(
        query_context=context,
        candidate_memories=memories,
        relationships={},
        semantic_clusters={}
    )
    
    assert len(results) > 0
    assert all(hasattr(r, 'memory') for r in results)
    assert all(hasattr(r, 'relevance') for r in results)
    
    # Results should be sorted by relevance
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i].relevance.total_score >= results[i + 1].relevance.total_score
    
    print(f"✓ Query engine processed {len(results)} results")
    print("✓ Enhanced query engine tests passed")
    
    return results


async def test_storage_and_retrieval():
    """Test storage and retrieval functionality."""
    print("\n💾 Testing Storage and Retrieval...")
    
    # Initialize mock storage
    storage = MockEnhancedStorage()
    await storage.initialize()
    
    # Create test memories
    test_memories = [
        EnhancedCognitiveMemory(
            content="Sierra Chart FRK Wick Rejection study implementation",
            temporal_window=TemporalWindow.ACTIVE,
            semantic_domain=MemoryDomain.TECHNICAL_PATTERNS,
            importance_score=0.9
        ),
        EnhancedCognitiveMemory(
            content="NQ session pattern analysis complete with 65% win rate",
            temporal_window=TemporalWindow.WORKING,
            semantic_domain=MemoryDomain.PROJECT_CONTEXT,
            importance_score=0.8
        ),
        EnhancedCognitiveMemory(
            content="Enhanced Heimdall architecture design decisions",
            temporal_window=TemporalWindow.REFERENCE,
            semantic_domain=MemoryDomain.DECISION_CHAINS,
            importance_score=0.7
        )
    ]
    
    # Store memories
    for memory in test_memories:
        await storage.store_memory(memory)
    
    # Test statistics
    stats = await storage.get_system_statistics()
    assert stats['total_memories'] == 3
    assert stats['active_memories'] == 1
    assert stats['working_memories'] == 1
    assert stats['reference_memories'] == 1
    
    print(f"✓ Stored {stats['total_memories']} memories across temporal windows")
    
    # Test retrieval by window
    active_memories = await storage.search_memories_by_window(
        query_text="Sierra Chart",
        temporal_window=TemporalWindow.ACTIVE
    )
    
    assert len(active_memories) == 1
    assert "FRK Wick Rejection" in active_memories[0].content
    
    print("✓ Retrieval by temporal window works")
    print("✓ Storage and retrieval tests passed")
    
    return storage


async def test_temporal_semantic_coordinator():
    """Test the temporal-semantic coordinator."""
    print("\n🎯 Testing Temporal-Semantic Coordinator...")
    
    # Setup components
    storage = MockEnhancedStorage()
    await storage.initialize()
    
    # Add some test memories to storage
    test_memories = [
        EnhancedCognitiveMemory(
            content="Recent Sierra Chart OFI execution model optimization",
            temporal_window=TemporalWindow.ACTIVE,
            semantic_domain=MemoryDomain.TECHNICAL_PATTERNS
        ),
        EnhancedCognitiveMemory(
            content="Project milestone: NQ pattern analysis deployment ready",
            temporal_window=TemporalWindow.WORKING,
            semantic_domain=MemoryDomain.PROJECT_CONTEXT
        )
    ]
    
    for memory in test_memories:
        await storage.store_memory(memory)
    
    # Create coordinator
    query_engine = EnhancedQueryEngine()
    coordinator = TemporalSemanticCoordinator(storage, query_engine)
    
    # Test query execution
    results, metrics = await coordinator.query_memories(
        query_text="Sierra Chart optimization",
        query_type="technical_pattern",
        max_results=5
    )
    
    assert isinstance(results, list)
    assert isinstance(metrics.total_query_time, float)
    assert metrics.total_query_time > 0
    
    print(f"✓ Coordinator executed query in {metrics.total_query_time:.3f}s")
    print(f"✓ Retrieved {len(results)} results")
    
    # Test performance summary
    summary = coordinator.get_performance_summary()
    assert "total_queries" in summary
    assert summary["total_queries"] == 1
    
    print("✓ Temporal-semantic coordinator tests passed")
    
    return coordinator


async def test_memory_lifecycle():
    """Test complete memory lifecycle simulation."""
    print("\n🔄 Testing Memory Lifecycle...")
    
    # Create a new memory
    memory = EnhancedCognitiveMemory(
        content="New Sierra Chart study development insight",
        temporal_window=TemporalWindow.ACTIVE,
        semantic_domain=MemoryDomain.PROJECT_CONTEXT
    )
    
    print(f"✓ Created memory in {memory.temporal_window.value} window")
    
    # Simulate aging (8 days old, low access)
    memory.created_date = datetime.now() - timedelta(days=8)
    memory.access_count = 1
    
    # Should transition to WORKING
    next_window = memory.should_transition_window()
    assert next_window == TemporalWindow.WORKING
    memory.temporal_window = next_window
    print(f"✓ Memory transitioned to {memory.temporal_window.value}")
    
    # Simulate more aging and high access
    memory.created_date = datetime.now() - timedelta(days=35)
    memory.access_count = 12
    memory.importance_score = 0.85
    
    # Should transition to REFERENCE
    next_window = memory.should_transition_window()
    assert next_window == TemporalWindow.REFERENCE
    memory.temporal_window = next_window
    print(f"✓ Memory transitioned to {memory.temporal_window.value}")
    
    # Reference memories with high importance should stay
    next_window = memory.should_transition_window()
    assert next_window is None  # No transition needed
    print("✓ Reference memory remains stable")
    
    print("✓ Memory lifecycle tests passed")


async def run_integration_test():
    """Run a complete integration test."""
    print("\n🚀 Running Integration Test...")
    
    storage = MockEnhancedStorage()
    await storage.initialize()
    
    query_engine = EnhancedQueryEngine()
    coordinator = TemporalSemanticCoordinator(storage, query_engine)
    
    # Create a comprehensive set of test memories
    integration_memories = [
        EnhancedCognitiveMemory(
            content="Sierra Chart FRK Wick Rejection level mappings and 90m filter logic optimization",
            temporal_window=TemporalWindow.ACTIVE,
            semantic_domain=MemoryDomain.TECHNICAL_PATTERNS,
            importance_score=0.9
        ),
        EnhancedCognitiveMemory(
            content="NQ session patterns: Pattern 25 shows 100% win rate with 21 trades",
            temporal_window=TemporalWindow.WORKING,
            semantic_domain=MemoryDomain.PROJECT_CONTEXT,
            importance_score=0.95
        ),
        EnhancedCognitiveMemory(
            content="Enhanced Heimdall architecture: Replace L0/L1/L2 with temporal windows",
            temporal_window=TemporalWindow.REFERENCE,
            semantic_domain=MemoryDomain.DECISION_CHAINS,
            importance_score=0.8
        ),
        EnhancedCognitiveMemory(
            content="Session handoff: Complete pattern analysis, ready for study compilation",
            temporal_window=TemporalWindow.ACTIVE,
            semantic_domain=MemoryDomain.SESSION_CONTINUITY,
            importance_score=0.7
        )
    ]
    
    # Store all memories
    for memory in integration_memories:
        memory.user_defined_tags = {"integration_test", "sierra_chart"}
        await storage.store_memory(memory)
    
    print(f"✓ Stored {len(integration_memories)} integration test memories")
    
    # Test different query types
    test_queries = [
        ("Sierra Chart FRK optimization", "technical_pattern"),
        ("project status NQ patterns", "project_status"),
        ("session handoff ready", "session_continuity"),
        ("architecture decision temporal", "decision_context"),
        ("pattern analysis", "general_search")
    ]
    
    total_results = 0
    total_time = 0
    
    for query_text, query_type in test_queries:
        results, metrics = await coordinator.query_memories(
            query_text=query_text,
            query_type=query_type,
            max_results=3
        )
        
        total_results += len(results)
        total_time += metrics.total_query_time
        
        print(f"✓ Query '{query_text}' ({query_type}): {len(results)} results in {metrics.total_query_time:.3f}s")
    
    # Final statistics
    final_stats = await storage.get_system_statistics()
    performance = coordinator.get_performance_summary()
    
    print(f"\n📊 Integration Test Results:")
    print(f"  • Total memories: {final_stats['total_memories']}")
    print(f"  • Total queries executed: {len(test_queries)}")
    print(f"  • Total results returned: {total_results}")
    print(f"  • Average query time: {total_time / len(test_queries):.3f}s")
    print(f"  • System queries: {performance['total_queries']}")
    
    print("✅ Integration test completed successfully!")


async def main():
    """Main test execution."""
    print("🧪 Enhanced Heimdall Architecture Test Suite")
    print("=" * 50)
    
    try:
        # Run individual component tests
        await test_enhanced_memory_creation()
        await test_temporal_window_transitions()
        await test_query_engine()
        await test_storage_and_retrieval()
        await test_temporal_semantic_coordinator()
        await test_memory_lifecycle()
        
        # Run integration test
        await run_integration_test()
        
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED! Enhanced architecture is working correctly.")
        print("\nNext steps:")
        print("1. Set up Qdrant for real vector storage")
        print("2. Test with actual Heimdall MCP integration")
        print("3. Run migration from existing Heimdall data")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)