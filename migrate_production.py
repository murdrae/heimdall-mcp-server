#!/usr/bin/env python3
"""
Production migration script to move existing Sierra Chart memories 
from legacy L0/L1/L2 hierarchy to enhanced temporal-semantic architecture.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct
import numpy as np
from sentence_transformers import SentenceTransformer

# Legacy collection mapping
LEGACY_COLLECTIONS = {
    "concepts": "SierraChart_233e90b7_concepts",
    "contexts": "SierraChart_233e90b7_contexts", 
    "episodes": "SierraChart_233e90b7_episodes"
}

# Enhanced collection mapping
ENHANCED_COLLECTIONS = {
    "active": "enhanced_heimdall_active",
    "working": "enhanced_heimdall_working",
    "reference": "enhanced_heimdall_reference",
    "archive": "enhanced_heimdall_archive"
}

class ProductionMigrator:
    def __init__(self):
        self.client = QdrantClient(host="localhost", port=6333)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
    def extract_legacy_memories(self) -> List[Dict[str, Any]]:
        """Extract all memories from legacy collections."""
        all_memories = []
        
        for level, collection_name in LEGACY_COLLECTIONS.items():
            try:
                # Get all points from collection
                points, _ = self.client.scroll(
                    collection_name=collection_name,
                    limit=1000,
                    with_payload=True,
                    with_vectors=True
                )
                
                for point in points:
                    memory = {
                        "id": str(point.id),
                        "content": point.payload.get("content", ""),
                        "legacy_level": level,
                        "metadata": point.payload,
                        "vector": point.vector
                    }
                    all_memories.append(memory)
                    
                print(f"✓ Extracted {len(points)} memories from {collection_name}")
                
            except Exception as e:
                print(f"⚠️ Failed to extract from {collection_name}: {e}")
                continue
                
        return all_memories
    
    def infer_temporal_window(self, memory: Dict[str, Any]) -> str:
        """Infer temporal window based on content and recency."""
        content = memory["content"].lower()
        metadata = memory.get("metadata", {})
        
        # Check for session continuity indicators
        if any(keyword in content for keyword in [
            "session", "handoff", "next actions", "immediate", "current", "active"
        ]):
            return "active"
            
        # Check for working context indicators  
        if any(keyword in content for keyword in [
            "project", "status", "development", "implementation", "working"
        ]):
            return "working"
            
        # Check for reference knowledge indicators
        if any(keyword in content for keyword in [
            "pattern", "architecture", "design", "principle", "best practice"
        ]):
            return "reference"
            
        # Default based on legacy level
        level_mapping = {
            "episodes": "active",  # Recent sessions
            "contexts": "working", # Project context
            "concepts": "reference" # Stable knowledge
        }
        
        return level_mapping.get(memory["legacy_level"], "working")
    
    def infer_semantic_domain(self, content: str) -> str:
        """Infer semantic domain from content."""
        content_lower = content.lower()
        
        if any(keyword in content_lower for keyword in [
            "sierra chart", "acsil", "trading", "pattern", "ofi", "fractal"
        ]):
            return "technical_patterns"
            
        if any(keyword in content_lower for keyword in [
            "project", "status", "milestone", "deliverable", "progress"
        ]):
            return "project_context"
            
        if any(keyword in content_lower for keyword in [
            "session", "handoff", "continue", "next", "blockers"
        ]):
            return "session_continuity"
            
        if any(keyword in content_lower for keyword in [
            "decision", "rationale", "why", "approach", "strategy"
        ]):
            return "decision_chains"
            
        return "ai_interactions"
    
    def create_enhanced_memory(self, legacy_memory: Dict[str, Any]) -> Dict[str, Any]:
        """Convert legacy memory to enhanced format."""
        content = legacy_memory["content"]
        temporal_window = self.infer_temporal_window(legacy_memory)
        semantic_domain = self.infer_semantic_domain(content)
        
        # Generate embedding if needed
        vector = legacy_memory.get("vector")
        if vector is None or not isinstance(vector, list):
            vector = self.embedding_model.encode(content).tolist()
        
        enhanced_memory = {
            "id": legacy_memory["id"],
            "content": content,
            "temporal_window": temporal_window,
            "semantic_domain": semantic_domain,
            "importance_score": 0.7,  # Default importance
            "access_count": 0,
            "created_date": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "metadata": {
                **legacy_memory.get("metadata", {}),
                "migrated_from": legacy_memory["legacy_level"],
                "migration_date": datetime.now().isoformat()
            },
            "vector": vector
        }
        
        return enhanced_memory
    
    def store_enhanced_memory(self, memory: Dict[str, Any]) -> bool:
        """Store memory in appropriate enhanced collection."""
        temporal_window = memory["temporal_window"]
        collection_name = ENHANCED_COLLECTIONS.get(temporal_window, "enhanced_heimdall_working")
        
        try:
            point = PointStruct(
                id=memory["id"],
                vector=memory["vector"],
                payload={
                    "content": memory["content"],
                    "temporal_window": memory["temporal_window"],
                    "semantic_domain": memory["semantic_domain"],
                    "importance_score": memory["importance_score"],
                    "access_count": memory["access_count"],
                    "created_date": memory["created_date"],
                    "last_accessed": memory["last_accessed"],
                    "metadata": memory["metadata"]
                }
            )
            
            self.client.upsert(
                collection_name=collection_name,
                points=[point]
            )
            
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to store memory {memory['id']}: {e}")
            return False
    
    def migrate_all(self) -> Dict[str, int]:
        """Execute full migration process."""
        print("🚀 Starting Production Migration to Enhanced Heimdall")
        print("=" * 60)
        
        # Extract legacy memories
        print("📋 Step 1: Extracting legacy memories...")
        legacy_memories = self.extract_legacy_memories()
        print(f"✓ Extracted {len(legacy_memories)} total memories")
        
        # Convert and store
        print("\n🔄 Step 2: Converting and storing enhanced memories...")
        results = {
            "total": len(legacy_memories),
            "migrated": 0,
            "failed": 0,
            "by_window": {"active": 0, "working": 0, "reference": 0, "archive": 0}
        }
        
        for i, legacy_memory in enumerate(legacy_memories):
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(legacy_memories)} ({i/len(legacy_memories)*100:.1f}%)")
            
            try:
                enhanced_memory = self.create_enhanced_memory(legacy_memory)
                success = self.store_enhanced_memory(enhanced_memory)
                
                if success:
                    results["migrated"] += 1
                    results["by_window"][enhanced_memory["temporal_window"]] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                print(f"⚠️ Error processing memory {legacy_memory.get('id', 'unknown')}: {e}")
                results["failed"] += 1
        
        # Summary
        print("\n📊 Migration Results:")
        print(f"  Total memories: {results['total']}")
        print(f"  Successfully migrated: {results['migrated']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Success rate: {results['migrated']/results['total']*100:.1f}%")
        
        print("\n📂 Distribution by temporal window:")
        for window, count in results["by_window"].items():
            print(f"  {window.capitalize()}: {count} memories")
        
        print("\n✅ Migration completed!")
        return results

def main():
    """Run the production migration."""
    migrator = ProductionMigrator()
    results = migrator.migrate_all()
    
    # Save results
    with open("migration_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📁 Results saved to migration_results.json")

if __name__ == "__main__":
    main()