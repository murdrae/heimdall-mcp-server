"""
Enhanced storage layer implementing semantic-temporal memory organization.

This module replaces the rigid L0/L1/L2 collections with flexible temporal layers
and semantic clustering for optimized AI assistant query patterns.
"""

from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timedelta
import numpy as np
from loguru import logger

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, PointStruct, VectorParams, Filter, FieldCondition

from ..core.enhanced_memory import (
    EnhancedCognitiveMemory, 
    TemporalWindow, 
    MemoryDomain,
    SemanticCluster,
    MemoryRelationship,
    TemporalLayer
)
from ..core.interfaces import VectorStorage
from ..core.config import QdrantConfig


class EnhancedQdrantStorage(VectorStorage):
    """
    Enhanced vector storage using semantic-temporal organization.
    
    Replaces hierarchical L0/L1/L2 collections with temporal windows + semantic clustering
    for natural AI assistant query patterns and improved relevance scoring.
    """
    
    def __init__(self, host: str = "localhost", port: int = 6333, collection_prefix: str = "enhanced_heimdall"):
        """Initialize enhanced storage with flexible parameters."""
        self.host = host
        self.port = port
        self.collection_prefix = collection_prefix
        self.client = QdrantClient(host=host, port=port)
        self.project_id = collection_prefix
        
        # Temporal layer management
        self.temporal_layers: Dict[TemporalWindow, TemporalLayer] = {
            window: TemporalLayer(window) for window in TemporalWindow
        }
        
        # Semantic organization
        self.semantic_clusters: Dict[str, SemanticCluster] = {}
        self.memory_relationships: Dict[str, MemoryRelationship] = {}
        
        # Collection names for temporal windows
        self.collections = {
            TemporalWindow.ACTIVE: f"{self.project_id}_active",
            TemporalWindow.WORKING: f"{self.project_id}_working", 
            TemporalWindow.REFERENCE: f"{self.project_id}_reference",
            TemporalWindow.ARCHIVE: f"{self.project_id}_archive"
        }
        
        # Global collections for relationships and clusters
        self.relationships_collection = f"{self.project_id}_relationships"
        self.clusters_collection = f"{self.project_id}_clusters"
        
        self._initialize_collections()
    
    async def initialize(self):
        """Async initialization for storage components."""
        pass  # Collections are initialized in constructor
    
    # Implement abstract methods from VectorStorage interface
    def store_vector(self, id: str, vector: np.ndarray, metadata: Dict[str, Any]) -> None:
        """Store a vector with associated metadata."""
        # Determine temporal window from metadata
        temporal_window = metadata.get('temporal_window', 'active')
        if isinstance(temporal_window, str):
            temporal_window = TemporalWindow(temporal_window)
        
        collection_name = self.collections[temporal_window]
        
        point = PointStruct(
            id=id,
            vector=vector.tolist(),
            payload=metadata
        )
        
        self.client.upsert(
            collection_name=collection_name,
            points=[point]
        )
    
    def search_similar(self, query_vector: np.ndarray, k: int, filters: Dict = None) -> List[Any]:
        """Search for similar vectors across temporal windows."""
        all_results = []
        
        # Search across all temporal windows by default
        windows_to_search = list(TemporalWindow)
        if filters and 'temporal_window' in filters:
            windows_to_search = [TemporalWindow(filters['temporal_window'])]
        
        for window in windows_to_search:
            collection_name = self.collections[window]
            
            # Build Qdrant filter
            qdrant_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if key != 'temporal_window':  # Already handled
                        conditions.append(FieldCondition(key=key, match=models.MatchValue(value=value)))
                
                if conditions:
                    qdrant_filter = Filter(must=conditions)
            
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector.tolist(),
                limit=k,
                query_filter=qdrant_filter
            )
            
            all_results.extend(results)
        
        # Sort by score and limit to k
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:k]
    
    def delete_vector(self, id: str) -> bool:
        """Delete a vector by ID from all collections."""
        deleted = False
        for collection_name in self.collections.values():
            try:
                self.client.delete(
                    collection_name=collection_name,
                    points_selector=models.PointIdsList(points=[id])
                )
                deleted = True
            except Exception:
                pass  # Vector might not exist in this collection
        return deleted
    
    def update_vector(self, id: str, vector: np.ndarray, metadata: Dict[str, Any]) -> bool:
        """Update an existing vector and its metadata."""
        # For now, implement as delete + store
        self.delete_vector(id)
        self.store_vector(id, vector, metadata)
        return True
    
    def delete_vectors_by_ids(self, memory_ids: List[str]) -> List[str]:
        """Delete vectors by their IDs."""
        deleted_ids = []
        for memory_id in memory_ids:
            if self.delete_vector(memory_id):
                deleted_ids.append(memory_id)
        return deleted_ids
    
    # Enhanced memory storage methods
    async def store_memory(self, memory: EnhancedCognitiveMemory) -> None:
        """Store an enhanced cognitive memory."""
        # Convert memory to vector and metadata
        # For now, use simple text encoding (should use actual embeddings in production)
        import hashlib
        
        # Create a simple embedding from content hash (placeholder)
        content_hash = hashlib.md5(memory.content.encode()).hexdigest()
        # Create a deterministic vector from content hash
        import random
        random.seed(int(content_hash[:8], 16))  # Use first 8 chars of hash as seed
        vector = np.array([random.random() for _ in range(384)])  # Placeholder vector
        
        metadata = {
            'content': memory.content,
            'temporal_window': memory.temporal_window.value,
            'semantic_domain': memory.semantic_domain.value,
            'importance_score': memory.importance_score,
            'access_count': memory.access_count,
            'created_date': memory.created_date.isoformat(),
            'last_accessed': memory.last_accessed.isoformat(),
            'tags': list(memory.user_defined_tags),
            'memory_type': memory.memory_type
        }
        
        try:
            self.store_vector(memory.id, vector, metadata)
            logger.info(f"Successfully stored memory {memory.id[:8]}... in {memory.temporal_window.value}")
        except Exception as e:
            logger.error(f"Error storing memory {memory.id}: {e}")
            raise
    
    async def search_memories_by_window(
        self,
        query_text: str,
        temporal_window: TemporalWindow,
        semantic_domain: MemoryDomain = None,
        limit: int = 20,
        min_similarity: float = 0.1
    ) -> List[EnhancedCognitiveMemory]:
        """Search memories within a specific temporal window."""
        # Create query vector (placeholder)
        query_vector = np.random.random(384)
        
        # Build filters
        filters = {'temporal_window': temporal_window.value}
        if semantic_domain:
            filters['semantic_domain'] = semantic_domain.value
        
        # Search
        results = self.search_similar(query_vector, limit, filters)
        
        # Convert results to EnhancedCognitiveMemory objects
        memories = []
        for result in results:
            if result.score >= min_similarity:
                memory = self._point_to_memory(result)
                if memory:
                    memories.append(memory)
        
        return memories
    
    async def get_memory_relationships(self, memory_ids: List[str]) -> Dict[str, List[MemoryRelationship]]:
        """Get relationships for the specified memory IDs."""
        # Placeholder implementation
        return {}
    
    async def get_semantic_clusters(self, cluster_ids: List[str]) -> Dict[str, SemanticCluster]:
        """Get semantic clusters by IDs."""
        # Placeholder implementation
        return {}
    
    async def get_system_statistics(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        stats = {
            'total_memories': 0,
            'active_memories': 0,
            'working_memories': 0,
            'reference_memories': 0,
            'archive_memories': 0,
            'domain_distribution': {}
        }
        
        # Count memories in each temporal window
        for window, collection_name in self.collections.items():
            try:
                info = self.client.get_collection(collection_name)
                count = info.points_count if hasattr(info, 'points_count') else 0
                stats['total_memories'] += count
                
                if window == TemporalWindow.ACTIVE:
                    stats['active_memories'] = count
                elif window == TemporalWindow.WORKING:
                    stats['working_memories'] = count
                elif window == TemporalWindow.REFERENCE:
                    stats['reference_memories'] = count
                elif window == TemporalWindow.ARCHIVE:
                    stats['archive_memories'] = count
            except Exception:
                pass
        
        return stats
    
    def _point_to_memory(self, point) -> Optional[EnhancedCognitiveMemory]:
        """Convert a Qdrant point to an EnhancedCognitiveMemory object."""
        try:
            payload = point.payload
            
            memory = EnhancedCognitiveMemory(
                id=str(point.id),
                content=payload.get('content', ''),
                temporal_window=TemporalWindow(payload.get('temporal_window', 'active')),
                semantic_domain=MemoryDomain(payload.get('semantic_domain', 'ai_interactions')),
                importance_score=payload.get('importance_score', 0.5),
                access_count=payload.get('access_count', 0),
                memory_type=payload.get('memory_type', 'enhanced')
            )
            
            # Parse dates
            if 'created_date' in payload:
                memory.created_date = datetime.fromisoformat(payload['created_date'])
            if 'last_accessed' in payload:
                memory.last_accessed = datetime.fromisoformat(payload['last_accessed'])
            
            # Parse tags
            if 'tags' in payload:
                memory.user_defined_tags = set(payload['tags'])
            
            return memory
            
        except Exception as e:
            logger.error(f"Failed to convert point to memory: {e}")
            return None
    
    def _initialize_collections(self) -> None:
        """Initialize Qdrant collections for enhanced storage."""
        vector_size = 384  # all-MiniLM-L6-v2 embedding size
        
        # Create temporal window collections
        for window, collection_name in self.collections.items():
            if not self.client.collection_exists(collection_name):
                logger.info(f"Creating collection: {collection_name}")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                
                # Create indexes for efficient filtering
                self._create_collection_indexes(collection_name)
        
        # Create relationship collection (smaller vectors for relationship embeddings)
        if not self.client.collection_exists(self.relationships_collection):
            logger.info(f"Creating relationships collection: {self.relationships_collection}")
            self.client.create_collection(
                collection_name=self.relationships_collection,
                vectors_config=VectorParams(
                    size=128,  # Smaller vectors for relationships
                    distance=Distance.COSINE
                )
            )
        
        # Create clusters collection
        if not self.client.collection_exists(self.clusters_collection):
            logger.info(f"Creating clusters collection: {self.clusters_collection}")
            self.client.create_collection(
                collection_name=self.clusters_collection,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )
    
    def _create_collection_indexes(self, collection_name: str) -> None:
        """Create indexes for efficient filtering and querying."""
        # Index on semantic domain for domain-specific queries
        self.client.create_payload_index(
            collection_name=collection_name,
            field_name="semantic_domain",
            field_schema="keyword"
        )
        
        # Index on creation date for temporal queries
        self.client.create_payload_index(
            collection_name=collection_name,
            field_name="created_date",
            field_schema="datetime"
        )
        
        # Index on importance score for relevance filtering
        self.client.create_payload_index(
            collection_name=collection_name,
            field_name="importance_score",
            field_schema="float"
        )
        
        # Index on memory type for compatibility queries
        self.client.create_payload_index(
            collection_name=collection_name,
            field_name="memory_type",
            field_schema="keyword"
        )
    
    def store_memory(self, memory: EnhancedCognitiveMemory) -> bool:
        """Store enhanced memory in appropriate temporal collection."""
        try:
            collection_name = self.collections[memory.temporal_window]
            
            # Prepare payload with enhanced metadata
            payload = {
                "content": memory.content,
                "temporal_window": memory.temporal_window.value,
                "semantic_domain": memory.semantic_domain.value,
                "created_date": memory.created_date.isoformat(),
                "last_accessed": memory.last_accessed.isoformat(),
                "last_modified": memory.last_modified.isoformat(),
                "access_count": memory.access_count,
                "importance_score": memory.importance_score,
                "memory_type": memory.memory_type,
                "strength": memory.strength,
                "user_defined_tags": list(memory.user_defined_tags),
                "auto_discovered_clusters": list(memory.auto_discovered_clusters),
                "contextual_keywords": memory.get_contextual_keywords(),
                "metadata": memory.metadata
            }
            
            # Add source date if available
            if memory.source_date:
                payload["source_date"] = memory.source_date.isoformat()
            
            # Store the point
            self.client.upsert(
                collection_name=collection_name,
                points=[PointStruct(
                    id=memory.id,
                    vector=memory.cognitive_embedding.tolist() if memory.cognitive_embedding is not None else None,
                    payload=payload
                )]
            )
            
            # Update local temporal layer
            self.temporal_layers[memory.temporal_window].add_memory(memory)
            
            logger.debug(f"Stored memory {memory.id} in {memory.temporal_window.value} collection")
            return True
            
        except Exception as e:
            logger.error(f"Error storing memory {memory.id}: {e}")
            return False
    
    def search_memories(
        self, 
        query_vector: np.ndarray,
        temporal_windows: Optional[List[TemporalWindow]] = None,
        semantic_domains: Optional[List[MemoryDomain]] = None,
        limit: int = 10,
        min_importance: float = 0.0,
        include_relationships: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Enhanced memory search with temporal and semantic filtering.
        
        Args:
            query_vector: Query embedding vector
            temporal_windows: Which temporal windows to search (default: all)
            semantic_domains: Which semantic domains to search (default: all) 
            limit: Maximum number of results
            min_importance: Minimum importance score threshold
            include_relationships: Whether to include relationship context
        
        Returns:
            List of search results with enhanced metadata
        """
        if temporal_windows is None:
            temporal_windows = list(TemporalWindow)
        
        all_results = []
        
        # Search across specified temporal windows
        for window in temporal_windows:
            collection_name = self.collections[window]
            
            # Build filter conditions
            filter_conditions = []
            
            # Filter by semantic domains if specified
            if semantic_domains:
                domain_values = [domain.value for domain in semantic_domains]
                filter_conditions.append(
                    FieldCondition(
                        key="semantic_domain",
                        match=models.MatchAny(any=domain_values)
                    )
                )
            
            # Filter by minimum importance
            if min_importance > 0.0:
                filter_conditions.append(
                    FieldCondition(
                        key="importance_score",
                        range=models.Range(gte=min_importance)
                    )
                )
            
            # Build filter
            search_filter = None
            if filter_conditions:
                search_filter = Filter(must=filter_conditions)
            
            # Perform search
            try:
                results = self.client.search(
                    collection_name=collection_name,
                    query_vector=query_vector.tolist(),
                    query_filter=search_filter,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False
                )
                
                # Enhance results with temporal context
                for result in results:
                    result_dict = {
                        "id": result.id,
                        "score": result.score,
                        "temporal_window": window.value,
                        "payload": result.payload
                    }
                    
                    # Calculate age-adjusted relevance score
                    created_date = datetime.fromisoformat(result.payload["created_date"])
                    age_days = (datetime.now() - created_date).total_seconds() / 86400
                    
                    # Temporal relevance multiplier (recent memories get boost)
                    temporal_multiplier = self._calculate_temporal_relevance(window, age_days)
                    result_dict["temporal_relevance"] = temporal_multiplier
                    result_dict["adjusted_score"] = result.score * temporal_multiplier
                    
                    all_results.append(result_dict)
                    
            except Exception as e:
                logger.error(f"Error searching {collection_name}: {e}")
                continue
        
        # Sort by adjusted relevance score
        all_results.sort(key=lambda x: x["adjusted_score"], reverse=True)
        
        # Include relationship context if requested
        if include_relationships:
            all_results = self._enrich_with_relationships(all_results[:limit])
        
        return all_results[:limit]
    
    def _calculate_temporal_relevance(self, window: TemporalWindow, age_days: float) -> float:
        """Calculate temporal relevance multiplier based on window and age."""
        match window:
            case TemporalWindow.ACTIVE:
                # Recent active memories are highly relevant
                return max(0.5, 1.0 - (age_days / 7.0) * 0.3)
                
            case TemporalWindow.WORKING:
                # Working context maintains good relevance
                return max(0.4, 0.8 - (age_days / 30.0) * 0.2)
                
            case TemporalWindow.REFERENCE:
                # Reference knowledge is consistently valuable
                return 0.9  # High base relevance regardless of age
                
            case TemporalWindow.ARCHIVE:
                # Archive has lower base relevance
                return 0.3
    
    def _enrich_with_relationships(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich search results with relationship context."""
        # This would query the relationships collection to find connected memories
        # Implementation would fetch related memories and add them to context
        for result in results:
            result["related_memories"] = []  # Placeholder for relationship context
            
        return results
    
    def transition_memory_window(
        self, 
        memory_id: str, 
        from_window: TemporalWindow, 
        to_window: TemporalWindow
    ) -> bool:
        """Move memory from one temporal window to another."""
        try:
            # Get memory from source collection
            from_collection = self.collections[from_window]
            to_collection = self.collections[to_window]
            
            # Retrieve the memory
            results = self.client.retrieve(
                collection_name=from_collection,
                ids=[memory_id],
                with_payload=True,
                with_vectors=True
            )
            
            if not results:
                logger.warning(f"Memory {memory_id} not found in {from_window.value}")
                return False
            
            memory_data = results[0]
            
            # Update temporal window in payload
            memory_data.payload["temporal_window"] = to_window.value
            memory_data.payload["window_transition_date"] = datetime.now().isoformat()
            
            # Store in target collection
            self.client.upsert(
                collection_name=to_collection,
                points=[PointStruct(
                    id=memory_data.id,
                    vector=memory_data.vector,
                    payload=memory_data.payload
                )]
            )
            
            # Remove from source collection
            self.client.delete(
                collection_name=from_collection,
                points_selector=models.PointIdsList(points=[memory_id])
            )
            
            # Update local temporal layers
            memory = self.temporal_layers[from_window].remove_memory(memory_id)
            if memory:
                memory.temporal_window = to_window
                self.temporal_layers[to_window].add_memory(memory)
            
            logger.info(f"Transitioned memory {memory_id} from {from_window.value} to {to_window.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error transitioning memory {memory_id}: {e}")
            return False
    
    def cleanup_temporal_layers(self) -> Dict[str, int]:
        """Perform automated cleanup and transitions of temporal layers."""
        transition_counts = {window.value: 0 for window in TemporalWindow}
        
        for window, layer in self.temporal_layers.items():
            memories_to_transition = layer.get_memories_for_transition()
            
            for memory in memories_to_transition:
                target_window = memory.should_transition_window()
                if target_window and self.transition_memory_window(memory.id, window, target_window):
                    transition_counts[target_window.value] += 1
        
        return transition_counts
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics for enhanced architecture."""
        stats = {
            "temporal_windows": {},
            "semantic_domains": {},
            "total_memories": 0,
            "total_relationships": 0,
            "total_clusters": len(self.semantic_clusters)
        }
        
        # Count memories in each temporal window
        for window in TemporalWindow:
            collection_name = self.collections[window]
            try:
                collection_info = self.client.get_collection(collection_name)
                count = collection_info.points_count
                layer = self.temporal_layers[window]
                
                stats["temporal_windows"][window.value] = {
                    "memory_count": count,
                    "average_age_days": layer.get_average_age_days()
                }
                stats["total_memories"] += count
                
            except Exception as e:
                logger.error(f"Error getting stats for {collection_name}: {e}")
                stats["temporal_windows"][window.value] = {"memory_count": 0, "average_age_days": 0}
        
        return stats