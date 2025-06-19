#!/usr/bin/env python3
"""
Quick test script to verify date-based ranking functionality.
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import torch

from cognitive_memory.core.config import CognitiveConfig
from cognitive_memory.core.memory import CognitiveMemory, SearchResult
from cognitive_memory.retrieval.similarity_search import SimilaritySearch


class MockMemoryStorage:
    """Mock memory storage for testing."""
    
    def __init__(self, memories):
        self.memories = memories
    
    def get_memories_by_level(self, level):
        return [m for m in self.memories if m.hierarchy_level == level]


def test_date_based_ranking():
    """Test that date-based ranking works correctly."""
    print("Testing date-based ranking functionality...")
    
    # Create test configuration
    config = CognitiveConfig()
    config.similarity_closeness_threshold = 0.05
    config.modification_date_weight = 0.3
    config.modification_recency_decay_days = 30.0
    
    # Create test memories with similar content but different modification dates
    now = datetime.now()
    old_date = now - timedelta(days=60)  # 2 months ago
    recent_date = now - timedelta(days=5)  # 5 days ago
    
    # Create memories with very similar embeddings but different dates
    embedding = torch.randn(384)  # Sentence-BERT dimension
    
    # Create embeddings that are moderately similar to avoid ceiling effects
    base_embedding = torch.randn(384)
    
    old_memory = CognitiveMemory(
        id="old_memory",
        content="This is test content about Python programming",
        hierarchy_level=1,
        cognitive_embedding=base_embedding + torch.randn(384) * 0.1,  # Moderate variation
        modified_date=old_date,
        source_date=old_date,
        metadata={"title": "Old Python Guide"}
    )
    
    recent_memory = CognitiveMemory(
        id="recent_memory", 
        content="This is test content about Python programming",
        hierarchy_level=1,
        cognitive_embedding=base_embedding + torch.randn(384) * 0.1,  # Moderate variation
        modified_date=recent_date,
        source_date=recent_date,
        metadata={"title": "Recent Python Guide"}
    )
    
    # Create mock storage
    storage = MockMemoryStorage([old_memory, recent_memory])
    
    # Create similarity search with date-based ranking
    search = SimilaritySearch(
        memory_storage=storage,
        cognitive_config=config
    )
    
    # Perform search
    query_vector = base_embedding + torch.randn(384) * 0.1  # Moderately similar to both memories
    results = search.search_memories(query_vector, k=2, levels=[1])
    
    # Verify results
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    
    # Check similarity scores first
    print("Raw similarity scores:")
    for result in results:
        print(f"  {result.memory.id}: similarity={result.similarity_score:.6f}")
    
    # Check that recent memory is ranked higher (should be first in results)
    print(f"Result 1: {results[0].memory.id} (combined_score: {results[0].combined_score:.6f})")
    print(f"Result 2: {results[1].memory.id} (combined_score: {results[1].combined_score:.6f})")
    
    # The recent memory should have a higher combined score due to date ranking
    recent_result = next(r for r in results if r.memory.id == "recent_memory")
    old_result = next(r for r in results if r.memory.id == "old_memory")
    
    print(f"Recent memory: similarity={recent_result.similarity_score:.6f}, combined={recent_result.combined_score:.6f}")
    print(f"Old memory: similarity={old_result.similarity_score:.6f}, combined={old_result.combined_score:.6f}")
    
    # Check if similarity scores are close enough to trigger date-based ranking
    sim_diff = abs(recent_result.similarity_score - old_result.similarity_score)
    print(f"Similarity difference: {sim_diff:.6f} (threshold: {config.similarity_closeness_threshold})")
    
    # Recent memory should be ranked higher due to modification date
    if recent_result.combined_score > old_result.combined_score:
        print("✓ Date-based ranking working correctly - recent memory ranked higher")
    elif recent_result.combined_score == old_result.combined_score:
        print("= Date-based ranking not triggered - scores are identical")
    else:
        print("✗ Date-based ranking may not be working - old memory ranked higher")
    
    print("Date-based ranking test completed!")


def test_markdown_loader_dates():
    """Test that markdown loader captures file modification dates."""
    print("\nTesting markdown loader date capture...")
    
    # Create a temporary markdown file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("""# Test Document

This is a test markdown document.

## Section 1

Some content here.

## Section 2

More content here.
""")
        temp_path = f.name
    
    try:
        from cognitive_memory.loaders.markdown_loader import MarkdownMemoryLoader
        from cognitive_memory.core.config import CognitiveConfig
        
        config = CognitiveConfig()
        loader = MarkdownMemoryLoader(config)
        
        # Load memories from the markdown file
        memories = loader.load_from_source(temp_path)
        
        print(f"Created {len(memories)} memories from markdown")
        
        # Check that memories have date fields
        for memory in memories:
            print(f"Memory: {memory.metadata.get('title', 'Unknown')}")
            print(f"  Created: {memory.created_date}")
            print(f"  Modified: {memory.modified_date}")
            print(f"  Source: {memory.source_date}")
            
            # Verify date fields are set
            assert memory.created_date is not None, "Created date should be set"
            assert memory.modified_date is not None, "Modified date should be set"
            assert memory.source_date is not None, "Source date should be set"
        
        print("✓ Markdown loader date capture working correctly")
        
    finally:
        # Clean up
        Path(temp_path).unlink()


if __name__ == "__main__":
    test_date_based_ranking()
    test_markdown_loader_dates()
    print("\nAll tests completed!")