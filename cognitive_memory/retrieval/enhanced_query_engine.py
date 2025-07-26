"""
Enhanced query engine with multi-dimensional relevance scoring.

This module implements sophisticated query processing that combines temporal,
semantic, access frequency, and relationship strength factors for optimal
AI assistant information retrieval.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import math
import numpy as np

from ..core.enhanced_memory import (
    EnhancedCognitiveMemory, 
    TemporalWindow, 
    MemoryDomain,
    SemanticCluster,
    MemoryRelationship
)


class QueryType(Enum):
    """Different types of queries requiring different relevance weighting."""
    PROJECT_STATUS = "project_status"        # Current project state, recent activities
    TECHNICAL_PATTERN = "technical_pattern"  # Code patterns, solutions, architectures
    DECISION_CONTEXT = "decision_context"    # Past decisions, trade-offs, rationale
    SESSION_CONTINUITY = "session_continuity" # Handoffs, next actions, blockers
    KNOWLEDGE_DISCOVERY = "knowledge_discovery" # Exploratory queries, connections
    GENERAL_SEARCH = "general_search"        # Default broad search


@dataclass
class QueryContext:
    """Rich context for query processing and relevance scoring."""
    
    query_text: str
    query_type: QueryType = QueryType.GENERAL_SEARCH
    temporal_focus: Optional[TemporalWindow] = None
    domain_focus: Optional[MemoryDomain] = None
    required_tags: Set[str] = field(default_factory=set)
    excluded_tags: Set[str] = field(default_factory=set)
    max_results: int = 10
    min_relevance_threshold: float = 0.1
    include_relationship_expansion: bool = True
    boost_recent_access: bool = True
    
    # Query-specific boosting factors
    temporal_weight: float = 0.3
    semantic_weight: float = 0.4
    frequency_weight: float = 0.2
    relationship_weight: float = 0.1


@dataclass
class RelevanceScore:
    """Detailed relevance scoring breakdown for transparency and debugging."""
    
    total_score: float = 0.0
    
    # Individual component scores (0.0 - 1.0)
    semantic_score: float = 0.0
    temporal_score: float = 0.0
    frequency_score: float = 0.0
    relationship_score: float = 0.0
    
    # Boosting factors
    domain_match_boost: float = 0.0
    tag_match_boost: float = 0.0
    recent_access_boost: float = 0.0
    
    # Penalty factors
    age_penalty: float = 0.0
    low_access_penalty: float = 0.0
    
    def __post_init__(self):
        """Calculate total score from components."""
        self.total_score = (
            self.semantic_score + 
            self.temporal_score + 
            self.frequency_score + 
            self.relationship_score +
            self.domain_match_boost +
            self.tag_match_boost +
            self.recent_access_boost -
            self.age_penalty -
            self.low_access_penalty
        )


@dataclass
class EnhancedQueryResult:
    """Rich query result with detailed relevance information."""
    
    memory: EnhancedCognitiveMemory
    relevance: RelevanceScore
    query_context: QueryContext
    related_memories: List[str] = field(default_factory=list)  # Memory IDs
    explanation: str = ""  # Human-readable relevance explanation


class EnhancedQueryEngine:
    """
    Advanced query engine with multi-dimensional relevance scoring.
    
    Combines semantic similarity, temporal relevance, access patterns, and 
    relationship strength to provide optimal results for AI assistant queries.
    """
    
    def __init__(self):
        """Initialize the enhanced query engine."""
        self.query_type_weights = {
            QueryType.PROJECT_STATUS: {
                'temporal_weight': 0.5,
                'semantic_weight': 0.3,
                'frequency_weight': 0.1,
                'relationship_weight': 0.1
            },
            QueryType.TECHNICAL_PATTERN: {
                'temporal_weight': 0.2,
                'semantic_weight': 0.5,
                'frequency_weight': 0.2,
                'relationship_weight': 0.1
            },
            QueryType.DECISION_CONTEXT: {
                'temporal_weight': 0.3,
                'semantic_weight': 0.4,
                'frequency_weight': 0.1,
                'relationship_weight': 0.2
            },
            QueryType.SESSION_CONTINUITY: {
                'temporal_weight': 0.6,
                'semantic_weight': 0.2,
                'frequency_weight': 0.1,
                'relationship_weight': 0.1
            },
            QueryType.KNOWLEDGE_DISCOVERY: {
                'temporal_weight': 0.1,
                'semantic_weight': 0.4,
                'frequency_weight': 0.2,
                'relationship_weight': 0.3
            },
            QueryType.GENERAL_SEARCH: {
                'temporal_weight': 0.3,
                'semantic_weight': 0.4,
                'frequency_weight': 0.2,
                'relationship_weight': 0.1
            }
        }
    
    def process_query(
        self,
        query_context: QueryContext,
        candidate_memories: List[EnhancedCognitiveMemory],
        relationships: Dict[str, List[MemoryRelationship]] = None,
        semantic_clusters: Dict[str, SemanticCluster] = None
    ) -> List[EnhancedQueryResult]:
        """
        Process a query with multi-dimensional relevance scoring.
        
        Args:
            query_context: Rich query specification with context
            candidate_memories: Pre-filtered memory candidates
            relationships: Memory relationship graph
            semantic_clusters: Discovered semantic clusters
            
        Returns:
            List of query results ranked by relevance
        """
        relationships = relationships or {}
        semantic_clusters = semantic_clusters or {}
        
        # Update query context with query-type specific weights
        self._apply_query_type_weights(query_context)
        
        # Score all candidate memories
        scored_results = []
        for memory in candidate_memories:
            if self._passes_filters(memory, query_context):
                relevance = self._calculate_relevance(
                    memory, query_context, relationships, semantic_clusters
                )
                
                if relevance.total_score >= query_context.min_relevance_threshold:
                    result = EnhancedQueryResult(
                        memory=memory,
                        relevance=relevance,
                        query_context=query_context,
                        explanation=self._generate_explanation(memory, relevance)
                    )
                    
                    # Add related memories if requested
                    if query_context.include_relationship_expansion:
                        result.related_memories = self._get_related_memory_ids(
                            memory.id, relationships
                        )
                    
                    scored_results.append(result)
        
        # Sort by total relevance score (descending)
        scored_results.sort(key=lambda x: x.relevance.total_score, reverse=True)
        
        # Limit results
        return scored_results[:query_context.max_results]
    
    def _apply_query_type_weights(self, query_context: QueryContext) -> None:
        """Apply query-type specific weighting to the query context."""
        if query_context.query_type in self.query_type_weights:
            weights = self.query_type_weights[query_context.query_type]
            query_context.temporal_weight = weights['temporal_weight']
            query_context.semantic_weight = weights['semantic_weight']
            query_context.frequency_weight = weights['frequency_weight']
            query_context.relationship_weight = weights['relationship_weight']
    
    def _passes_filters(self, memory: EnhancedCognitiveMemory, context: QueryContext) -> bool:
        """Check if memory passes basic filtering criteria."""
        # Temporal window filter
        if context.temporal_focus and memory.temporal_window != context.temporal_focus:
            return False
        
        # Domain filter
        if context.domain_focus and memory.semantic_domain != context.domain_focus:
            return False
        
        # Required tags filter
        if context.required_tags and not context.required_tags.issubset(memory.user_defined_tags):
            return False
        
        # Excluded tags filter
        if context.excluded_tags and context.excluded_tags.intersection(memory.user_defined_tags):
            return False
        
        return True
    
    def _calculate_relevance(
        self,
        memory: EnhancedCognitiveMemory,
        context: QueryContext,
        relationships: Dict[str, List[MemoryRelationship]],
        semantic_clusters: Dict[str, SemanticCluster]
    ) -> RelevanceScore:
        """Calculate multi-dimensional relevance score for a memory."""
        relevance = RelevanceScore()
        
        # 1. Semantic similarity (placeholder - would use actual embeddings)
        relevance.semantic_score = self._calculate_semantic_similarity(memory, context)
        
        # 2. Temporal relevance
        relevance.temporal_score = self._calculate_temporal_relevance(memory, context)
        
        # 3. Access frequency relevance
        relevance.frequency_score = self._calculate_frequency_relevance(memory, context)
        
        # 4. Relationship strength
        relevance.relationship_score = self._calculate_relationship_relevance(
            memory, context, relationships
        )
        
        # 5. Boost factors
        relevance.domain_match_boost = self._calculate_domain_boost(memory, context)
        relevance.tag_match_boost = self._calculate_tag_boost(memory, context)
        relevance.recent_access_boost = self._calculate_recent_access_boost(memory, context)
        
        # 6. Penalty factors
        relevance.age_penalty = self._calculate_age_penalty(memory, context)
        relevance.low_access_penalty = self._calculate_low_access_penalty(memory, context)
        
        # Apply weighting
        weighted_score = (
            relevance.semantic_score * context.semantic_weight +
            relevance.temporal_score * context.temporal_weight +
            relevance.frequency_score * context.frequency_weight +
            relevance.relationship_score * context.relationship_weight
        )
        
        # Add boosts and subtract penalties
        final_score = (
            weighted_score +
            relevance.domain_match_boost +
            relevance.tag_match_boost +
            relevance.recent_access_boost -
            relevance.age_penalty -
            relevance.low_access_penalty
        )
        
        relevance.total_score = max(0.0, min(1.0, final_score))  # Clamp to [0,1]
        
        return relevance
    
    def _calculate_semantic_similarity(
        self, 
        memory: EnhancedCognitiveMemory, 
        context: QueryContext
    ) -> float:
        """Calculate semantic similarity between query and memory content."""
        # Placeholder implementation - would use actual embeddings
        # For now, simple keyword matching
        query_words = set(context.query_text.lower().split())
        memory_words = set(memory.content.lower().split())
        
        if not query_words:
            return 0.0
        
        intersection = query_words.intersection(memory_words)
        union = query_words.union(memory_words)
        
        jaccard_similarity = len(intersection) / len(union) if union else 0.0
        
        # Boost for exact phrase matches
        if context.query_text.lower() in memory.content.lower():
            jaccard_similarity = min(1.0, jaccard_similarity + 0.3)
        
        return jaccard_similarity
    
    def _calculate_temporal_relevance(
        self, 
        memory: EnhancedCognitiveMemory, 
        context: QueryContext
    ) -> float:
        """Calculate temporal relevance based on recency and temporal window."""
        now = datetime.now()
        
        # Base score from temporal window
        window_scores = {
            TemporalWindow.ACTIVE: 1.0,
            TemporalWindow.WORKING: 0.7,
            TemporalWindow.REFERENCE: 0.5,
            TemporalWindow.ARCHIVE: 0.2
        }
        base_score = window_scores.get(memory.temporal_window, 0.1)
        
        # Recency boost for very recent memories
        hours_since_created = (now - memory.created_date).total_seconds() / 3600
        if hours_since_created < 24:
            recency_boost = 0.3 * (1 - hours_since_created / 24)
        else:
            recency_boost = 0.0
        
        # Recent access boost
        hours_since_accessed = (now - memory.last_accessed).total_seconds() / 3600
        if hours_since_accessed < 6:
            access_boost = 0.2 * (1 - hours_since_accessed / 6)
        else:
            access_boost = 0.0
        
        return min(1.0, base_score + recency_boost + access_boost)
    
    def _calculate_frequency_relevance(
        self, 
        memory: EnhancedCognitiveMemory, 
        context: QueryContext
    ) -> float:
        """Calculate relevance based on access frequency and importance."""
        # Normalize access count (assuming max reasonable access count is 50)
        normalized_access = min(1.0, memory.access_count / 50.0)
        
        # Combine with importance score
        frequency_component = normalized_access * 0.7
        importance_component = memory.importance_score * 0.3
        
        return frequency_component + importance_component
    
    def _calculate_relationship_relevance(
        self,
        memory: EnhancedCognitiveMemory,
        context: QueryContext,
        relationships: Dict[str, List[MemoryRelationship]]
    ) -> float:
        """Calculate relevance based on relationship strength and connectivity."""
        memory_relationships = relationships.get(memory.id, [])
        
        if not memory_relationships:
            return 0.0
        
        # Average relationship strength
        total_strength = sum(rel.strength for rel in memory_relationships)
        avg_strength = total_strength / len(memory_relationships)
        
        # Connectivity bonus (more connections = higher relevance)
        connectivity_score = min(1.0, len(memory_relationships) / 10.0)
        
        return avg_strength * 0.7 + connectivity_score * 0.3
    
    def _calculate_domain_boost(
        self, 
        memory: EnhancedCognitiveMemory, 
        context: QueryContext
    ) -> float:
        """Calculate boost for domain matching."""
        if context.domain_focus and memory.semantic_domain == context.domain_focus:
            return 0.1
        return 0.0
    
    def _calculate_tag_boost(
        self, 
        memory: EnhancedCognitiveMemory, 
        context: QueryContext
    ) -> float:
        """Calculate boost for tag matching."""
        if not context.required_tags:
            return 0.0
        
        matched_tags = context.required_tags.intersection(memory.user_defined_tags)
        if matched_tags:
            return 0.05 * len(matched_tags)
        
        return 0.0
    
    def _calculate_recent_access_boost(
        self, 
        memory: EnhancedCognitiveMemory, 
        context: QueryContext
    ) -> float:
        """Calculate boost for recently accessed memories."""
        if not context.boost_recent_access:
            return 0.0
        
        hours_since_accessed = (datetime.now() - memory.last_accessed).total_seconds() / 3600
        
        if hours_since_accessed < 1:
            return 0.15
        elif hours_since_accessed < 6:
            return 0.1
        elif hours_since_accessed < 24:
            return 0.05
        
        return 0.0
    
    def _calculate_age_penalty(
        self, 
        memory: EnhancedCognitiveMemory, 
        context: QueryContext
    ) -> float:
        """Calculate penalty for very old memories in non-reference contexts."""
        if memory.temporal_window == TemporalWindow.REFERENCE:
            return 0.0  # Reference memories don't get age penalties
        
        age_days = memory.calculate_age_days()
        
        if age_days > 365:
            return 0.1
        elif age_days > 90:
            return 0.05
        
        return 0.0
    
    def _calculate_low_access_penalty(
        self, 
        memory: EnhancedCognitiveMemory, 
        context: QueryContext
    ) -> float:
        """Calculate penalty for memories with very low access counts."""
        if memory.access_count == 0 and memory.calculate_age_days() > 30:
            return 0.05
        
        return 0.0
    
    def _get_related_memory_ids(
        self,
        memory_id: str,
        relationships: Dict[str, List[MemoryRelationship]]
    ) -> List[str]:
        """Get IDs of memories related to the given memory."""
        related_ids = []
        
        # Get outgoing relationships
        outgoing = relationships.get(memory_id, [])
        for rel in outgoing:
            if rel.strength > 0.5:  # Only strong relationships
                related_ids.append(rel.target_memory_id)
        
        # Get incoming relationships
        for other_memory_id, relations in relationships.items():
            for rel in relations:
                if rel.target_memory_id == memory_id and rel.strength > 0.5:
                    related_ids.append(other_memory_id)
        
        return list(set(related_ids))  # Remove duplicates
    
    def _generate_explanation(
        self, 
        memory: EnhancedCognitiveMemory, 
        relevance: RelevanceScore
    ) -> str:
        """Generate human-readable explanation for relevance score."""
        explanations = []
        
        if relevance.semantic_score > 0.7:
            explanations.append("high semantic similarity")
        elif relevance.semantic_score > 0.4:
            explanations.append("moderate semantic similarity")
        
        if relevance.temporal_score > 0.8:
            explanations.append("very recent/active")
        elif relevance.temporal_score > 0.6:
            explanations.append("recent")
        
        if relevance.frequency_score > 0.6:
            explanations.append("frequently accessed")
        
        if relevance.relationship_score > 0.5:
            explanations.append("well connected")
        
        if relevance.domain_match_boost > 0:
            explanations.append("domain match")
        
        if relevance.recent_access_boost > 0:
            explanations.append("recently accessed")
        
        if not explanations:
            explanations.append("baseline relevance")
        
        return f"Relevant due to: {', '.join(explanations)}"


def create_query_context(
    query_text: str,
    query_type: str = "general_search",
    max_results: int = 10,
    **kwargs
) -> QueryContext:
    """
    Convenience function to create QueryContext from simple parameters.
    
    Args:
        query_text: The search query
        query_type: Type of query (project_status, technical_pattern, etc.)
        max_results: Maximum number of results to return
        **kwargs: Additional context parameters
        
    Returns:
        QueryContext object ready for query processing
    """
    # Convert string query type to enum
    try:
        query_type_enum = QueryType(query_type.lower())
    except ValueError:
        query_type_enum = QueryType.GENERAL_SEARCH
    
    return QueryContext(
        query_text=query_text,
        query_type=query_type_enum,
        max_results=max_results,
        **kwargs
    )