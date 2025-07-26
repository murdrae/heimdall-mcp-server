#!/usr/bin/env python3
"""
Automated cleanup of legacy Heimdall collections (non-interactive).
"""

from qdrant_client import QdrantClient
import json

LEGACY_COLLECTIONS = [
    "SierraChart_233e90b7_concepts",
    "SierraChart_233e90b7_contexts", 
    "SierraChart_233e90b7_episodes",
    "SierraChart_d0cb726d_concepts",
    "SierraChart_d0cb726d_contexts",
    "SierraChart_d0cb726d_episodes"
]

def cleanup_legacy_collections():
    """Remove legacy collections after backup verification."""
    print("🧹 Starting automated legacy cleanup...")
    client = QdrantClient(host="localhost", port=6333)
    
    # Verify backup exists
    try:
        with open("legacy_heimdall_backup.json", "r") as f:
            backup = json.load(f)
        print("✓ Backup file verified")
    except:
        print("❌ No backup found! Aborting cleanup.")
        return
    
    cleanup_results = {
        "deleted": [],
        "failed": [],
        "not_found": []
    }
    
    # Verify enhanced system is healthy
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
            total_enhanced += info.points_count
        except:
            print("❌ Enhanced system not healthy! Aborting cleanup.")
            return
    
    if total_enhanced < 83:
        print("❌ Enhanced system has insufficient memories! Aborting cleanup.")
        return
    
    print(f"✓ Enhanced system healthy: {total_enhanced} memories")
    
    # Delete legacy collections
    for collection_name in LEGACY_COLLECTIONS:
        try:
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if collection_name not in collection_names:
                print(f"⚠️ {collection_name} not found")
                cleanup_results["not_found"].append(collection_name)
                continue
            
            client.delete_collection(collection_name)
            print(f"✓ Deleted {collection_name}")
            cleanup_results["deleted"].append(collection_name)
            
        except Exception as e:
            print(f"❌ Failed to delete {collection_name}: {e}")
            cleanup_results["failed"].append({"collection": collection_name, "error": str(e)})
    
    # Final verification
    print(f"\n📊 Cleanup Results:")
    print(f"  Deleted: {len(cleanup_results['deleted'])} collections")
    print(f"  Failed: {len(cleanup_results['failed'])} collections")
    print(f"  Not found: {len(cleanup_results['not_found'])} collections")
    
    # Verify enhanced system still healthy
    total_enhanced_after = 0
    for collection in enhanced_collections:
        try:
            info = client.get_collection(collection)
            total_enhanced_after += info.points_count
        except Exception as e:
            print(f"❌ Enhanced collection error: {e}")
    
    print(f"\n✅ Enhanced system status: {total_enhanced_after} memories")
    
    if len(cleanup_results['deleted']) > 0:
        print(f"🎉 Legacy Heimdall cleanup completed successfully!")
        print(f"🚀 Enhanced Heimdall is now your primary memory system!")
    
    return cleanup_results

if __name__ == "__main__":
    cleanup_legacy_collections()