#!/usr/bin/env python3
"""
Cleanup legacy Heimdall collections after successful migration to enhanced architecture.
"""

from qdrant_client import QdrantClient
import json

# Legacy collections to remove after migration
LEGACY_COLLECTIONS = [
    "SierraChart_233e90b7_concepts",
    "SierraChart_233e90b7_contexts", 
    "SierraChart_233e90b7_episodes",
    "SierraChart_d0cb726d_concepts",
    "SierraChart_d0cb726d_contexts",
    "SierraChart_d0cb726d_episodes"
]

def backup_legacy_data():
    """Create backup of legacy data before deletion."""
    print("💾 Creating backup of legacy data...")
    client = QdrantClient(host="localhost", port=6333)
    
    backup_data = {}
    
    for collection_name in LEGACY_COLLECTIONS:
        try:
            # Get collection info
            collection_info = client.get_collection(collection_name)
            
            # Extract all points
            points, _ = client.scroll(
                collection_name=collection_name,
                limit=1000,
                with_payload=True,
                with_vectors=True
            )
            
            backup_data[collection_name] = {
                "collection_info": {
                    "points_count": collection_info.points_count,
                    "vectors_count": collection_info.vectors_count
                },
                "points": [
                    {
                        "id": str(point.id),
                        "payload": point.payload,
                        "vector": point.vector
                    }
                    for point in points
                ]
            }
            
            print(f"✓ Backed up {collection_name}: {len(points)} memories")
            
        except Exception as e:
            print(f"⚠️ Failed to backup {collection_name}: {e}")
            backup_data[collection_name] = {"error": str(e)}
    
    # Save backup
    with open("legacy_heimdall_backup.json", "w") as f:
        json.dump(backup_data, f, indent=2)
    
    print(f"✓ Backup saved to legacy_heimdall_backup.json")
    return backup_data

def cleanup_legacy_collections():
    """Remove legacy collections after backup."""
    print("\n🧹 Cleaning up legacy collections...")
    client = QdrantClient(host="localhost", port=6333)
    
    cleanup_results = {
        "deleted": [],
        "failed": [],
        "not_found": []
    }
    
    for collection_name in LEGACY_COLLECTIONS:
        try:
            # Check if collection exists
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if collection_name not in collection_names:
                print(f"⚠️ Collection {collection_name} not found")
                cleanup_results["not_found"].append(collection_name)
                continue
            
            # Delete collection
            client.delete_collection(collection_name)
            print(f"✓ Deleted {collection_name}")
            cleanup_results["deleted"].append(collection_name)
            
        except Exception as e:
            print(f"❌ Failed to delete {collection_name}: {e}")
            cleanup_results["failed"].append({"collection": collection_name, "error": str(e)})
    
    return cleanup_results

def verify_enhanced_system():
    """Verify enhanced system is still operational after cleanup."""
    print("\n🔍 Verifying enhanced system...")
    client = QdrantClient(host="localhost", port=6333)
    
    enhanced_collections = [
        "enhanced_heimdall_active",
        "enhanced_heimdall_working", 
        "enhanced_heimdall_reference",
        "enhanced_heimdall_archive"
    ]
    
    total_enhanced = 0
    
    for collection in enhanced_collections:
        try:
            info = client.get_collection(collection)
            count = info.points_count
            total_enhanced += count
            print(f"✓ {collection}: {count} memories")
        except Exception as e:
            print(f"❌ {collection}: {e}")
    
    print(f"\n📊 Enhanced System Status:")
    print(f"  Total enhanced memories: {total_enhanced}")
    print(f"  Expected: 83")
    print(f"  Status: {'✅ HEALTHY' if total_enhanced >= 83 else '⚠️ DEGRADED'}")
    
    return total_enhanced >= 83

def main():
    """Execute legacy cleanup process."""
    print("🚀 Legacy Heimdall Cleanup Process")
    print("=" * 40)
    
    # Step 1: Backup legacy data
    backup_data = backup_legacy_data()
    
    # Step 2: Verify enhanced system before cleanup
    print("\n🔍 Pre-cleanup verification...")
    if not verify_enhanced_system():
        print("❌ Enhanced system not healthy! Aborting cleanup.")
        return
    
    # Step 3: User confirmation
    print(f"\n⚠️  CONFIRMATION REQUIRED")
    print(f"This will permanently delete {len(LEGACY_COLLECTIONS)} legacy collections.")
    print(f"Enhanced system is verified operational with 83+ memories.")
    print(f"Backup created: legacy_heimdall_backup.json")
    
    confirmation = input("\nProceed with cleanup? (type 'YES' to confirm): ")
    
    if confirmation != "YES":
        print("❌ Cleanup cancelled by user")
        return
    
    # Step 4: Clean up legacy collections
    cleanup_results = cleanup_legacy_collections()
    
    # Step 5: Post-cleanup verification
    print("\n🔍 Post-cleanup verification...")
    enhanced_healthy = verify_enhanced_system()
    
    # Step 6: Summary
    print(f"\n📋 Cleanup Summary:")
    print(f"  Deleted collections: {len(cleanup_results['deleted'])}")
    print(f"  Failed deletions: {len(cleanup_results['failed'])}")
    print(f"  Not found: {len(cleanup_results['not_found'])}")
    print(f"  Enhanced system: {'✅ HEALTHY' if enhanced_healthy else '❌ DEGRADED'}")
    
    if len(cleanup_results['deleted']) > 0:
        print(f"\n✅ Legacy Heimdall cleanup completed!")
        print(f"🎯 Enhanced Heimdall is now your primary memory system!")
    else:
        print(f"\n⚠️ No collections were deleted. Check for errors above.")
    
    # Save cleanup results
    with open("cleanup_results.json", "w") as f:
        json.dump(cleanup_results, f, indent=2)

if __name__ == "__main__":
    main()