"""
Qdrant-based vector storage for cognitive memory system.

This module implements the hierarchical memory storage using Qdrant collections
as defined in the technical specification.
"""

from typing import List, Dict, Any, Optional
import torch
from loguru import logger

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        VectorParams, Distance, PointStruct, Filter, FieldCondition, 
        Range, OptimizersConfig, SearchRequest
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("Qdrant client not available. Vector storage will be disabled.")

from ..core.interfaces import VectorStorage
from ..core.memory import CognitiveMemory, SearchResult
from ..core.config import QdrantConfig


class QdrantVectorStorage(VectorStorage):
    """Qdrant implementation of vector storage interface."""
    
    def __init__(self, config: QdrantConfig):
        """
        Initialize Qdrant vector storage.
        
        Args:
            config: Qdrant configuration
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant client is required but not installed")
        
        self.config = config
        self.client = self._create_client()
        self.collections = {
            'concepts_l0': 'cognitive_concepts',
            'contexts_l1': 'cognitive_contexts',
            'episodes_l2': 'cognitive_episodes'
        }
        self._initialize_collections()
    
    def _create_client(self) -> QdrantClient:
        """Create Qdrant client with configuration."""
        try:
            client = QdrantClient(
                url=self.config.url,
                api_key=self.config.api_key,
                timeout=self.config.timeout,
                prefer_grpc=self.config.prefer_grpc
            )
            
            # Test connection
            client.get_collections()
            logger.info(f"Connected to Qdrant at {self.config.url}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise
    
    def _initialize_collections(self) -> None:
        """Initialize Qdrant collections for hierarchical storage."""
        try:
            existing_collections = {col.name for col in self.client.get_collections().collections}
            
            for level, collection_name in self.collections.items():
                if collection_name not in existing_collections:
                    self.client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=512,  # Cognitive embedding dimension
                            distance=Distance.COSINE
                        ),
                        optimizers_config=OptimizersConfig(
                            default_segment_number=2,
                            memmap_threshold=20000
                        )
                    )
                    logger.info(f"Created collection: {collection_name}")
                else:
                    logger.debug(f"Collection already exists: {collection_name}")
        
        except Exception as e:
            logger.error(f"Failed to initialize collections: {e}")
            raise
    
    def store_vector(self, id: str, vector: torch.Tensor, metadata: Dict[str, Any]) -> None:
        """Store a vector with associated metadata."""
        try:
            # Determine collection based on level
            level = metadata.get('level', 0)
            collection_name = self._get_collection_for_level(level)
            
            # Convert tensor to list
            vector_list = vector.tolist() if isinstance(vector, torch.Tensor) else vector
            
            # Create point
            point = PointStruct(
                id=id,
                vector=vector_list,
                payload=metadata
            )
            
            # Store in appropriate collection
            self.client.upsert(
                collection_name=collection_name,
                points=[point]
            )
            
            logger.debug(f"Stored vector {id} in {collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to store vector {id}: {e}")
            raise
    
    def search_similar(
        self,
        query_vector: torch.Tensor,
        k: int,
        filters: Optional[Dict] = None
    ) -> List[SearchResult]:
        """Search for similar vectors across all collections."""
        try:
            all_results = []
            
            # Convert tensor to list
            query_list = query_vector.tolist() if isinstance(query_vector, torch.Tensor) else query_vector
            
            # Search across all collections
            for collection_name in self.collections.values():
                # Build filter if provided
                search_filter = None
                if filters:
                    conditions = []
                    for key, value in filters.items():
                        if isinstance(value, (list, tuple)) and len(value) == 2:
                            # Range filter
                            conditions.append(FieldCondition(
                                key=key,
                                range=Range(gte=value[0], lte=value[1])
                            ))
                        else:
                            # Exact match
                            conditions.append(FieldCondition(
                                key=key,
                                match=value
                            ))
                    
                    if conditions:
                        search_filter = Filter(must=conditions)
                
                # Search collection
                results = self.client.search(
                    collection_name=collection_name,
                    query_vector=query_list,
                    limit=k,
                    query_filter=search_filter,
                    with_payload=True,
                    with_vectors=False
                )
                
                # Convert to SearchResult objects
                for result in results:
                    # Create minimal CognitiveMemory for SearchResult
                    memory = CognitiveMemory(
                        id=str(result.id),
                        content=result.payload.get('content', ''),
                        level=result.payload.get('level', 0),
                        memory_type=result.payload.get('memory_type', 'episodic')
                    )
                    
                    search_result = SearchResult(
                        memory=memory,
                        similarity_score=result.score,
                        distance=1.0 - result.score
                    )
                    all_results.append(search_result)
            
            # Sort by similarity score and return top k
            all_results.sort(key=lambda x: x.similarity_score, reverse=True)
            return all_results[:k]
            
        except Exception as e:
            logger.error(f"Failed to search similar vectors: {e}")
            return []
    
    def search_level(
        self,
        level: int,
        query_vector: torch.Tensor,
        k: int,
        score_threshold: float = 0.0
    ) -> List[SearchResult]:
        """Search for similar vectors in a specific hierarchy level."""
        try:
            collection_name = self._get_collection_for_level(level)
            query_list = query_vector.tolist() if isinstance(query_vector, torch.Tensor) else query_vector
            
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_list,
                limit=k,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )
            
            search_results = []
            for result in results:
                memory = CognitiveMemory(
                    id=str(result.id),
                    content=result.payload.get('content', ''),
                    level=result.payload.get('level', level),
                    memory_type=result.payload.get('memory_type', 'episodic')
                )
                
                search_result = SearchResult(
                    memory=memory,
                    similarity_score=result.score,
                    distance=1.0 - result.score
                )
                search_results.append(search_result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Failed to search level {level}: {e}")
            return []
    
    def delete_vector(self, id: str) -> bool:
        """Delete a vector by ID from all collections."""
        try:
            success = True
            for collection_name in self.collections.values():
                try:
                    self.client.delete(
                        collection_name=collection_name,
                        points_selector=[id]
                    )
                except Exception as e:
                    # Vector might not exist in this collection, which is fine
                    logger.debug(f"Vector {id} not found in {collection_name}: {e}")
            
            logger.debug(f"Deleted vector {id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete vector {id}: {e}")
            return False
    
    def update_vector(self, id: str, vector: torch.Tensor, metadata: Dict[str, Any]) -> bool:
        """Update an existing vector and its metadata."""
        try:
            # Delete old vector first
            self.delete_vector(id)
            
            # Store updated vector
            self.store_vector(id, vector, metadata)
            return True
            
        except Exception as e:
            logger.error(f"Failed to update vector {id}: {e}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about all collections."""
        try:
            info = {}
            for level, collection_name in self.collections.items():
                collection_info = self.client.get_collection(collection_name)
                info[level] = {
                    'name': collection_name,
                    'vectors_count': collection_info.vectors_count,
                    'segments_count': collection_info.segments_count,
                    'disk_data_size': collection_info.disk_data_size,
                    'ram_data_size': collection_info.ram_data_size
                }
            return info
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}
    
    def _get_collection_for_level(self, level: int) -> str:
        """Get collection name for hierarchy level."""
        if level == 0:
            return self.collections['concepts_l0']
        elif level == 1:
            return self.collections['contexts_l1']
        elif level == 2:
            return self.collections['episodes_l2']
        else:
            # Default to episodes for unknown levels
            logger.warning(f"Unknown level {level}, using episodes collection")
            return self.collections['episodes_l2']
    
    def cleanup_collections(self) -> Dict[str, int]:
        """Clean up empty or low-quality vectors."""
        try:
            cleanup_stats = {}
            
            for level, collection_name in self.collections.items():
                # Get collection info
                collection_info = self.client.get_collection(collection_name)
                initial_count = collection_info.vectors_count
                
                # Here you could implement cleanup logic based on:
                # - Low access count
                # - Old timestamps
                # - Low importance scores
                # For now, just return the count
                
                cleanup_stats[level] = {
                    'initial_count': initial_count,
                    'cleaned': 0,
                    'remaining': initial_count
                }
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup collections: {e}")
            return {}


class HierarchicalMemoryStorage:
    """
    High-level interface for hierarchical memory storage using Qdrant.
    
    This class implements the 3-tier hierarchy (L0→L1→L2) as specified
    in the technical architecture.
    """
    
    def __init__(self, qdrant_storage: QdrantVectorStorage):
        """Initialize with Qdrant storage backend."""
        self.storage = qdrant_storage
    
    def store_memory(self, memory: CognitiveMemory, level: int) -> bool:
        """Store memory at appropriate hierarchy level."""
        try:
            if memory.cognitive_embedding is None:
                logger.error(f"Memory {memory.id} has no cognitive embedding")
                return False
            
            metadata = {
                'content': memory.content,
                'level': level,
                'timestamp': memory.timestamp.isoformat(),
                'parent_id': memory.parent_id,
                'access_count': memory.access_count,
                'importance_score': memory.importance_score,
                'memory_type': memory.memory_type
            }
            
            self.storage.store_vector(memory.id, memory.cognitive_embedding, metadata)
            logger.debug(f"Stored memory {memory.id} at level {level}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store memory {memory.id} at level {level}: {e}")
            return False
    
    def search_hierarchy(
        self,
        query_vector: torch.Tensor,
        max_results_per_level: int = 10
    ) -> Dict[int, List[SearchResult]]:
        """Search across all hierarchy levels."""
        results = {}
        
        for level in [0, 1, 2]:  # L0, L1, L2
            level_results = self.storage.search_level(
                level=level,
                query_vector=query_vector,
                k=max_results_per_level
            )
            results[level] = level_results
        
        return results
    
    def get_all_memories(self) -> List[CognitiveMemory]:
        """Get all memories from vector storage (for bridge discovery)."""
        # This is a simplified implementation
        # In practice, you might want to batch this or use scrolling
        all_memories = []
        
        for collection_name in self.storage.collections.values():
            try:
                # Use scroll to get all points
                points, _ = self.storage.client.scroll(
                    collection_name=collection_name,
                    limit=10000,  # Adjust based on expected size
                    with_payload=True,
                    with_vectors=False
                )
                
                for point in points:
                    memory = CognitiveMemory(
                        id=str(point.id),
                        content=point.payload.get('content', ''),
                        level=point.payload.get('level', 0),
                        memory_type=point.payload.get('memory_type', 'episodic')
                    )
                    all_memories.append(memory)
                    
            except Exception as e:
                logger.error(f"Error retrieving memories from {collection_name}: {e}")
        
        return all_memories