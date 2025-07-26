#!/usr/bin/env python3
"""
Test enhanced Heimdall query capabilities with migrated data.
"""

import asyncio
import sys
sys.path.append('/mnt/c/SierraChart/heimdall-fork')

from cognitive_memory.core.enhanced_memory import EnhancedCognitiveMemory
from cognitive_memory.storage.enhanced_storage import EnhancedQdrantStorage
from cognitive_memory.query.enhanced_query_engine import EnhancedQueryEngine

async def test_enhanced_queries():
    """Test enhanced query system with migrated data."""
    print("🧠 Testing Enhanced Heimdall Query System")
    print("=" * 50)
    
    # Initialize enhanced system
    storage = EnhancedQdrantStorage(
        host="localhost", 
        port=6333, 
        collection_prefix="enhanced_heimdall"
    )
    
    query_engine = EnhancedQueryEngine(storage)
    
    # Test queries
    test_queries = [
        {
            "query": "NQ session pattern analysis results",
            "description": "Trading pattern analysis context"
        },
        {
            "query": "Sierra Chart study compilation",
            "description": "Development workflow context"
        },
        {
            "query": "project status current milestones",
            "description": "Project management context"
        },
        {
            "query": "OFI execution model optimization",
            "description": "Technical implementation details"
        },
        {
            "query": "session handoff next actions",
            "description": "Session continuity context"
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n🔍 Test {i}: {test['description']}")
        print(f"Query: '{test['query']}'")
        print("-" * 40)
        
        try:
            # Execute enhanced query
            results = await query_engine.multi_dimensional_search(
                query=test["query"],
                max_results=3,
                temporal_windows=["active", "working", "reference"]
            )
            
            print(f"✓ Found {len(results)} results")
            
            if results:
                for j, result in enumerate(results, 1):
                    content_preview = result.content[:100] + "..." if len(result.content) > 100 else result.content
                    print(f"  {j}. [{result.temporal_window}] {result.semantic_domain}")
                    print(f"     Score: {result.relevance_score:.3f}")
                    print(f"     Preview: {content_preview}")
            else:
                print("  (No matching memories found)")
                
        except Exception as e:
            print(f"⚠️ Query failed: {e}")
    
    # Test temporal window distribution
    print(f"\n📊 System Status:")
    try:
        status = await storage.get_system_status()
        print(f"  Active memories: {status.get('active_count', 0)}")
        print(f"  Working memories: {status.get('working_count', 0)}")
        print(f"  Reference memories: {status.get('reference_count', 0)}")
        print(f"  Archive memories: {status.get('archive_count', 0)}")
    except Exception as e:
        print(f"  Status unavailable: {e}")
    
    print("\n✅ Enhanced query testing completed!")

if __name__ == "__main__":
    asyncio.run(test_enhanced_queries())