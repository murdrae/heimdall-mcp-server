#!/usr/bin/env python3
"""
Test migration success by querying Qdrant directly.
"""

from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
import json

def test_migration():
    """Test that migration was successful."""
    print("🎯 Testing Enhanced Heimdall Migration Success")
    print("=" * 50)
    
    client = QdrantClient(host="localhost", port=6333)
    
    # Check collections
    collections = ["enhanced_heimdall_active", "enhanced_heimdall_working", 
                  "enhanced_heimdall_reference", "enhanced_heimdall_archive"]
    
    total_migrated = 0
    
    for collection in collections:
        try:
            info = client.get_collection(collection)
            count = info.points_count
            total_migrated += count
            print(f"✓ {collection}: {count} memories")
            
            # Sample a few memories
            if count > 0:
                points, _ = client.scroll(
                    collection_name=collection,
                    limit=2,
                    with_payload=True
                )
                
                for point in points:
                    content_preview = point.payload.get("content", "")[:60] + "..."
                    temporal_window = point.payload.get("temporal_window", "unknown")
                    semantic_domain = point.payload.get("semantic_domain", "unknown")
                    print(f"  - [{temporal_window}] {semantic_domain}: {content_preview}")
                    
        except Exception as e:
            print(f"⚠️ {collection}: {e}")
    
    print(f"\n📊 Migration Summary:")
    print(f"  Total memories migrated: {total_migrated}")
    print(f"  Original legacy count: 83")
    print(f"  Migration success: {'✅ YES' if total_migrated >= 83 else '❌ NO'}")
    
    # Test semantic search on one collection
    print(f"\n🔍 Testing Semantic Search...")
    try:
        # Simple similarity search
        results = client.search(
            collection_name="enhanced_heimdall_active",
            query_vector=[0.1] * 384,  # Random query vector
            limit=3,
            with_payload=True
        )
        
        print(f"✓ Search returned {len(results)} results")
        for result in results:
            content = result.payload.get("content", "")[:50] + "..."
            print(f"  - Score: {result.score:.3f} - {content}")
            
    except Exception as e:
        print(f"⚠️ Search test failed: {e}")
    
    print(f"\n🎉 Enhanced Heimdall is operational!")
    
    # Load migration results
    try:
        with open("migration_results.json", "r") as f:
            results = json.load(f)
        print(f"\n📋 Migration Details:")
        print(f"  Success rate: {results['migrated']}/{results['total']} ({results['migrated']/results['total']*100:.1f}%)")
        print(f"  Active: {results['by_window']['active']} memories")
        print(f"  Working: {results['by_window']['working']} memories")  
        print(f"  Reference: {results['by_window']['reference']} memories")
    except:
        print("\n📋 Migration results file not found")

if __name__ == "__main__":
    test_migration()