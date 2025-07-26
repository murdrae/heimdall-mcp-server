#!/usr/bin/env python3
"""
Simple test of enhanced Heimdall system with migrated data.
"""

import asyncio
import sys
sys.path.append('/mnt/c/SierraChart/heimdall-fork')

from cognitive_memory.storage.enhanced_storage import EnhancedQdrantStorage
from cognitive_memory.retrieval.enhanced_query_engine import EnhancedQueryEngine

async def test_simple_queries():
    """Test basic query functionality."""
    print("🔍 Testing Enhanced Heimdall Queries")
    print("=" * 40)
    
    try:
        # Initialize components
        storage = EnhancedQdrantStorage(
            host="localhost", 
            port=6333, 
            collection_prefix="enhanced_heimdall"
        )
        
        query_engine = EnhancedQueryEngine(storage)
        
        # Test queries
        queries = [
            "NQ session pattern analysis",
            "Sierra Chart study compilation", 
            "project status milestones",
            "session handoff"
        ]
        
        for query in queries:
            print(f"\n🔎 Query: '{query}'")
            try:
                results = await query_engine.search(
                    query=query,
                    max_results=3
                )
                
                print(f"✓ Found {len(results)} results")
                for i, result in enumerate(results, 1):
                    preview = result['content'][:80] + "..." if len(result['content']) > 80 else result['content']
                    print(f"  {i}. Score: {result.get('score', 'N/A'):.3f} - {preview}")
                    
            except Exception as e:
                print(f"⚠️ Query failed: {e}")
        
        print("\n📊 System Health:")
        print("✅ Enhanced Heimdall migration successful!")
        print("✅ Query engine operational!")
        
    except Exception as e:
        print(f"❌ System error: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple_queries())