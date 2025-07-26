"""
Temporal-semantic query coordinator for enhanced Heimdall architecture.

This module coordinates between the enhanced storage layer and query engine
to provide optimized retrieval across temporal windows and semantic domains.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
import asyncio
import logging

from ..core.enhanced_memory import (
    EnhancedCognitiveMemory,
    TemporalWindow,
    MemoryDomain,
    SemanticCluster,
    MemoryRelationship
)
from ..storage.enhanced_storage import EnhancedQdrantStorage
from .enhanced_query_engine import (
    EnhancedQueryEngine,
    QueryContext,
    QueryType,
    EnhancedQueryResult,
    create_query_context
)


@dataclass
class QueryStrategy:
    """Defines the strategy for querying across temporal windows and domains."""
    
    # Temporal window search order and limits
    temporal_priorities: List[TemporalWindow] = field(default_factory=lambda: [
        TemporalWindow.ACTIVE,
        TemporalWindow.WORKING,
        TemporalWindow.REFERENCE,
        TemporalWindow.ARCHIVE
    ])
    
    # Maximum candidates to retrieve from each window
    window_limits: Dict[TemporalWindow, int] = field(default_factory=lambda: {
        TemporalWindow.ACTIVE: 50,
        TemporalWindow.WORKING: 30,
        TemporalWindow.REFERENCE: 20,
        TemporalWindow.ARCHIVE: 10
    })
    
    # Whether to stop early if high-quality results found
    early_termination: bool = True
    early_termination_threshold: float = 0.8
    early_termination_count: int = 3
    
    # Semantic domain expansion
    expand_related_domains: bool = True
    domain_expansion_limit: int = 2


@dataclass
class QueryPerformanceMetrics:
    """Tracks query performance for optimization."""
    
    total_query_time: float = 0.0
    storage_retrieval_time: float = 0.0
    relevance_scoring_time: float = 0.0
    
    candidates_retrieved: int = 0
    candidates_scored: int = 0
    results_returned: int = 0
    
    temporal_windows_searched: List[TemporalWindow] = field(default_factory=list)
    semantic_domains_searched: List[MemoryDomain] = field(default_factory=list)
    
    early_termination_triggered: bool = False


class TemporalSemanticCoordinator:
    """
    Coordinates temporal-semantic queries across the enhanced memory architecture.
    
    This coordinator optimizes query execution by:
    1. Intelligently selecting temporal windows to search
    2. Expanding semantic domains when appropriate
    3. Managing query performance and early termination
    4. Coordinating between storage and query engine layers
    """
    
    def __init__(
        self,
        storage: EnhancedQdrantStorage,
        query_engine: EnhancedQueryEngine,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the temporal-semantic coordinator."""
        self.storage = storage
        self.query_engine = query_engine
        self.logger = logger or logging.getLogger(__name__)
        
        # Performance tracking
        self.query_metrics: List[QueryPerformanceMetrics] = []
        
        # Adaptive thresholds based on performance history
        self.adaptive_thresholds = {
            'min_semantic_similarity': 0.1,
            'temporal_boost_factor': 1.2,
            'relationship_expansion_threshold': 0.6
        }
    
    async def query_memories(
        self,
        query_text: str,
        query_type: str = "general_search",
        max_results: int = 10,
        strategy: Optional[QueryStrategy] = None,
        **context_kwargs
    ) -> Tuple[List[EnhancedQueryResult], QueryPerformanceMetrics]:
        """
        Execute a comprehensive temporal-semantic query.
        
        Args:
            query_text: The search query
            query_type: Type of query (affects weighting and strategy)
            max_results: Maximum results to return
            strategy: Custom query strategy (uses default if None)
            **context_kwargs: Additional query context parameters
            
        Returns:
            Tuple of (query results, performance metrics)
        """
        start_time = datetime.now()
        metrics = QueryPerformanceMetrics()
        
        try:
            # Create query context
            query_context = create_query_context(
                query_text=query_text,
                query_type=query_type,
                max_results=max_results,
                **context_kwargs
            )
            
            # Use default strategy if none provided
            if strategy is None:
                strategy = self._create_adaptive_strategy(query_context)
            
            # Execute multi-stage query
            results = await self._execute_staged_query(
                query_context, strategy, metrics
            )
            
            # Calculate total query time
            metrics.total_query_time = (datetime.now() - start_time).total_seconds()
            metrics.results_returned = len(results)
            
            # Store metrics for adaptive learning
            self.query_metrics.append(metrics)
            self._update_adaptive_thresholds()
            
            self.logger.info(
                f"Query completed: {len(results)} results in {metrics.total_query_time:.3f}s"
            )
            
            return results, metrics
            
        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            metrics.total_query_time = (datetime.now() - start_time).total_seconds()
            return [], metrics
    
    async def _execute_staged_query(
        self,
        query_context: QueryContext,
        strategy: QueryStrategy,
        metrics: QueryPerformanceMetrics
    ) -> List[EnhancedQueryResult]:
        """Execute a multi-stage query across temporal windows."""
        all_results = []
        candidates_by_window = {}
        
        # Stage 1: Retrieve candidates from each temporal window
        retrieval_start = datetime.now()
        
        for window in strategy.temporal_priorities:
            window_limit = strategy.window_limits.get(window, 20)
            
            # Get candidates from this temporal window
            candidates = await self._retrieve_window_candidates(
                query_context, window, window_limit
            )
            
            if candidates:
                candidates_by_window[window] = candidates
                metrics.candidates_retrieved += len(candidates)
                metrics.temporal_windows_searched.append(window)
                
                self.logger.debug(
                    f"Retrieved {len(candidates)} candidates from {window.value}"
                )
            
            # Early termination check for very recent high-relevance memories
            if (window == TemporalWindow.ACTIVE and 
                strategy.early_termination and 
                len(candidates) >= strategy.early_termination_count):
                
                # Quick relevance check on ACTIVE window
                quick_results = await self._quick_relevance_check(
                    candidates, query_context
                )
                
                high_quality_count = sum(
                    1 for r in quick_results 
                    if r.relevance.total_score >= strategy.early_termination_threshold
                )
                
                if high_quality_count >= strategy.early_termination_count:
                    metrics.early_termination_triggered = True
                    self.logger.info("Early termination triggered - high quality ACTIVE results")
                    candidates_by_window = {window: candidates}
                    break
        
        metrics.storage_retrieval_time = (datetime.now() - retrieval_start).total_seconds()
        
        # Stage 2: Comprehensive relevance scoring
        scoring_start = datetime.now()
        
        # Combine all candidates
        all_candidates = []
        for candidates in candidates_by_window.values():
            all_candidates.extend(candidates)
        
        metrics.candidates_scored = len(all_candidates)
        
        if all_candidates:
            # Get relationships and clusters for enhanced scoring
            relationships = await self._get_relevant_relationships(
                [m.id for m in all_candidates]
            )
            clusters = await self._get_relevant_clusters(all_candidates)
            
            # Execute comprehensive relevance scoring
            results = self.query_engine.process_query(
                query_context=query_context,
                candidate_memories=all_candidates,
                relationships=relationships,
                semantic_clusters=clusters
            )
            
            all_results.extend(results)
        
        metrics.relevance_scoring_time = (datetime.now() - scoring_start).total_seconds()
        
        # Stage 3: Post-processing and final ranking
        final_results = await self._post_process_results(
            all_results, query_context, strategy
        )
        
        return final_results[:query_context.max_results]
    
    async def _retrieve_window_candidates(
        self,
        query_context: QueryContext,
        window: TemporalWindow,
        limit: int
    ) -> List[EnhancedCognitiveMemory]:
        """Retrieve candidate memories from a specific temporal window."""
        try:
            # Use storage layer to get candidates
            candidates = await self.storage.search_memories_by_window(
                query_text=query_context.query_text,
                temporal_window=window,
                semantic_domain=query_context.domain_focus,
                limit=limit,
                min_similarity=self.adaptive_thresholds['min_semantic_similarity']
            )
            
            return candidates
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve candidates from {window.value}: {e}")
            return []
    
    async def _quick_relevance_check(
        self,
        candidates: List[EnhancedCognitiveMemory],
        query_context: QueryContext
    ) -> List[EnhancedQueryResult]:
        """Perform quick relevance check for early termination decision."""
        # Simplified scoring for performance
        quick_context = QueryContext(
            query_text=query_context.query_text,
            query_type=query_context.query_type,
            max_results=len(candidates),
            min_relevance_threshold=0.0,  # Include all for quick check
            include_relationship_expansion=False  # Skip expensive relationship lookup
        )
        
        return self.query_engine.process_query(
            query_context=quick_context,
            candidate_memories=candidates,
            relationships={},
            semantic_clusters={}
        )
    
    async def _get_relevant_relationships(
        self,
        memory_ids: List[str]
    ) -> Dict[str, List[MemoryRelationship]]:
        """Get relationship information for relevance scoring."""
        try:
            return await self.storage.get_memory_relationships(memory_ids)
        except Exception as e:
            self.logger.error(f"Failed to retrieve relationships: {e}")
            return {}
    
    async def _get_relevant_clusters(
        self,
        memories: List[EnhancedCognitiveMemory]
    ) -> Dict[str, SemanticCluster]:
        """Get semantic cluster information for relevance scoring."""
        try:
            cluster_ids = set()
            for memory in memories:
                cluster_ids.update(memory.auto_discovered_clusters)
            
            if cluster_ids:
                return await self.storage.get_semantic_clusters(list(cluster_ids))
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve clusters: {e}")
            return {}
    
    async def _post_process_results(
        self,
        results: List[EnhancedQueryResult],
        query_context: QueryContext,
        strategy: QueryStrategy
    ) -> List[EnhancedQueryResult]:
        """Post-process results for final ranking and filtering."""
        # Remove duplicates (can happen with relationship expansion)
        seen_ids = set()
        unique_results = []
        
        for result in results:
            if result.memory.id not in seen_ids:
                seen_ids.add(result.memory.id)
                unique_results.append(result)
        
        # Apply final filtering
        filtered_results = [
            r for r in unique_results
            if r.relevance.total_score >= query_context.min_relevance_threshold
        ]
        
        # Sort by relevance (already done in query engine, but ensure consistency)
        filtered_results.sort(key=lambda x: x.relevance.total_score, reverse=True)
        
        return filtered_results
    
    def _create_adaptive_strategy(self, query_context: QueryContext) -> QueryStrategy:
        """Create an adaptive query strategy based on query type and history."""
        strategy = QueryStrategy()
        
        # Adapt based on query type
        if query_context.query_type == QueryType.PROJECT_STATUS:
            # Focus heavily on recent memories
            strategy.temporal_priorities = [
                TemporalWindow.ACTIVE,
                TemporalWindow.WORKING
            ]
            strategy.window_limits[TemporalWindow.ACTIVE] = 100
            strategy.early_termination = True
            
        elif query_context.query_type == QueryType.SESSION_CONTINUITY:
            # Only search very recent memories
            strategy.temporal_priorities = [TemporalWindow.ACTIVE]
            strategy.window_limits[TemporalWindow.ACTIVE] = 50
            strategy.early_termination = True
            
        elif query_context.query_type == QueryType.TECHNICAL_PATTERN:
            # Include reference memories for established patterns
            strategy.temporal_priorities = [
                TemporalWindow.REFERENCE,
                TemporalWindow.WORKING,
                TemporalWindow.ACTIVE
            ]
            strategy.window_limits[TemporalWindow.REFERENCE] = 50
            strategy.early_termination = False
            
        elif query_context.query_type == QueryType.KNOWLEDGE_DISCOVERY:
            # Search all windows with relationship expansion
            strategy.early_termination = False
            strategy.expand_related_domains = True
        
        # Adapt based on performance history
        if len(self.query_metrics) > 10:
            recent_metrics = self.query_metrics[-10:]
            avg_active_results = sum(
                1 for m in recent_metrics 
                if TemporalWindow.ACTIVE in m.temporal_windows_searched
            ) / len(recent_metrics)
            
            # If ACTIVE window frequently produces good results, prioritize it more
            if avg_active_results > 0.8:
                strategy.window_limits[TemporalWindow.ACTIVE] = min(
                    100, strategy.window_limits[TemporalWindow.ACTIVE] * 2
                )
        
        return strategy
    
    def _update_adaptive_thresholds(self) -> None:
        """Update adaptive thresholds based on query performance history."""
        if len(self.query_metrics) < 5:
            return
        
        recent_metrics = self.query_metrics[-20:]  # Last 20 queries
        
        # Adjust minimum semantic similarity based on result quality
        avg_results_returned = sum(m.results_returned for m in recent_metrics) / len(recent_metrics)
        
        if avg_results_returned < 3:
            # Too few results, lower the threshold
            self.adaptive_thresholds['min_semantic_similarity'] *= 0.9
        elif avg_results_returned > 15:
            # Too many results, raise the threshold
            self.adaptive_thresholds['min_semantic_similarity'] *= 1.1
        
        # Clamp thresholds to reasonable ranges
        self.adaptive_thresholds['min_semantic_similarity'] = max(
            0.05, min(0.3, self.adaptive_thresholds['min_semantic_similarity'])
        )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for monitoring and optimization."""
        if not self.query_metrics:
            return {"status": "no_queries_executed"}
        
        recent_metrics = self.query_metrics[-50:]  # Last 50 queries
        
        return {
            "total_queries": len(self.query_metrics),
            "recent_avg_query_time": sum(m.total_query_time for m in recent_metrics) / len(recent_metrics),
            "recent_avg_results": sum(m.results_returned for m in recent_metrics) / len(recent_metrics),
            "early_termination_rate": sum(1 for m in recent_metrics if m.early_termination_triggered) / len(recent_metrics),
            "adaptive_thresholds": self.adaptive_thresholds.copy(),
            "temporal_window_usage": {
                window.value: sum(1 for m in recent_metrics if window in m.temporal_windows_searched)
                for window in TemporalWindow
            }
        }


# Convenience function for easy integration
async def query_enhanced_memory(
    storage: EnhancedQdrantStorage,
    query_text: str,
    query_type: str = "general_search",
    max_results: int = 10,
    **kwargs
) -> List[EnhancedQueryResult]:
    """
    Convenience function for quick enhanced memory queries.
    
    Args:
        storage: Enhanced storage instance
        query_text: Search query
        query_type: Type of query
        max_results: Maximum results to return
        **kwargs: Additional query parameters
        
    Returns:
        List of enhanced query results
    """
    query_engine = EnhancedQueryEngine()
    coordinator = TemporalSemanticCoordinator(storage, query_engine)
    
    results, _ = await coordinator.query_memories(
        query_text=query_text,
        query_type=query_type,
        max_results=max_results,
        **kwargs
    )
    
    return results