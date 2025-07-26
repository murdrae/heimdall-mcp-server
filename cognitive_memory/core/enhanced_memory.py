"""
Enhanced cognitive memory architecture with semantic-temporal organization.

This module replaces the rigid L0/L1/L2 hierarchy with a flexible temporal-semantic
system optimized for AI assistant query patterns and natural information flow.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

import numpy as np


class TemporalWindow(Enum):
    """Temporal classification for memories based on relevance and usage patterns."""
    ACTIVE = "active"        # Last 7 days - immediate context, session continuity
    WORKING = "working"      # Last 30 days - current project context
    REFERENCE = "reference"  # Permanent - validated patterns, architectural decisions
    ARCHIVE = "archive"      # Historical - searchable but not primary


class MemoryDomain(Enum):
    """Semantic domains for automatic clustering and organization."""
    PROJECT_CONTEXT = "project_context"          # Project state, milestones, status
    TECHNICAL_PATTERNS = "technical_patterns"    # Code patterns, architectures, solutions
    DECISION_CHAINS = "decision_chains"          # Decision rationale, trade-offs, outcomes
    SESSION_CONTINUITY = "session_continuity"    # Handoffs, next actions, blockers
    DEVELOPMENT_HISTORY = "development_history"  # Git commits, file changes, iterations
    AI_INTERACTIONS = "ai_interactions"          # AI assistant conversations, insights


@dataclass
class SemanticCluster:
    """Represents an automatically discovered semantic cluster of related memories."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    centroid_embedding: Optional[np.ndarray] = None
    member_memory_ids: Set[str] = field(default_factory=set)
    coherence_score: float = 0.0  # How tightly clustered the memories are
    created_date: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    access_frequency: int = 0


@dataclass 
class MemoryRelationship:
    """Represents a relationship between two memories with typed connections."""
    
    source_memory_id: str
    target_memory_id: str
    relationship_type: str  # causal, temporal, semantic, contextual, dependency
    strength: float = 0.0   # Connection strength 0.0-1.0
    created_date: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnhancedCognitiveMemory:
    """
    Enhanced cognitive memory with semantic-temporal organization.
    
    Replaces rigid hierarchy with flexible temporal windows, semantic domains,
    and rich relationship graphs for natural AI assistant query patterns.
    """
    
    # Core identity
    id: str = field(default_factory=lambda: str(uuid4()))
    content: str = ""
    
    # Temporal classification (replaces hierarchy_level)
    temporal_window: TemporalWindow = TemporalWindow.ACTIVE
    window_transition_date: Optional[datetime] = None  # When it should move to next window
    
    # Semantic organization
    semantic_domain: MemoryDomain = MemoryDomain.AI_INTERACTIONS
    auto_discovered_clusters: Set[str] = field(default_factory=set)  # Cluster IDs
    user_defined_tags: Set[str] = field(default_factory=set)
    
    # Vector embeddings (preserve existing multi-dimensional encoding)
    cognitive_embedding: Optional[np.ndarray] = None
    dimensions: Dict[str, np.ndarray] = field(default_factory=dict)
    
    # Temporal metadata
    created_date: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    last_modified: datetime = field(default_factory=datetime.now)
    source_date: Optional[datetime] = None  # Original timestamp if different
    
    # Access and relevance tracking
    access_count: int = 0
    importance_score: float = 0.0
    relevance_decay_rate: float = 0.1
    
    # Relationship tracking
    outgoing_relationships: Set[str] = field(default_factory=set)  # Relationship IDs
    incoming_relationships: Set[str] = field(default_factory=set)   # Relationship IDs
    
    # Memory type and metadata (preserve compatibility)
    memory_type: str = "enhanced"  # enhanced, episodic, semantic for compatibility
    strength: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_access(self) -> None:
        """Update access timestamp and increment access count."""
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def calculate_age_days(self) -> float:
        """Calculate age in days since creation."""
        return (datetime.now() - self.created_date).total_seconds() / 86400
        
    def should_transition_window(self) -> Optional[TemporalWindow]:
        """Determine if memory should transition to a different temporal window."""
        age_days = self.calculate_age_days()
        
        match self.temporal_window:
            case TemporalWindow.ACTIVE:
                if age_days > 7 and self.access_count < 2:
                    # Low access active memories become working context
                    return TemporalWindow.WORKING
                elif age_days > 14:
                    # Old active memories definitely become working context
                    return TemporalWindow.WORKING
                    
            case TemporalWindow.WORKING:
                if age_days > 30 and self.access_count < 3:
                    # Low access working memories become archive
                    return TemporalWindow.ARCHIVE
                elif self.access_count > 10 and self.importance_score > 0.8:
                    # High value working memories become reference
                    return TemporalWindow.REFERENCE
                    
            case TemporalWindow.REFERENCE:
                # Reference memories are permanent unless explicitly archived
                if self.importance_score < 0.3 and age_days > 365:
                    return TemporalWindow.ARCHIVE
                    
            case TemporalWindow.ARCHIVE:
                # Archive memories don't transition automatically
                pass
                
        return None
    
    def get_contextual_keywords(self) -> List[str]:
        """Extract contextual keywords for enhanced searchability."""
        keywords = []
        
        # Add domain-specific keywords
        keywords.append(self.semantic_domain.value)
        
        # Add temporal context
        keywords.append(self.temporal_window.value)
        
        # Add user tags
        keywords.extend(self.user_defined_tags)
        
        # Add relationship context
        if self.outgoing_relationships:
            keywords.append("has_connections")
        if self.incoming_relationships:
            keywords.append("is_referenced")
            
        return keywords


@dataclass
class TemporalLayer:
    """Represents a temporal layer containing memories of similar recency/relevance."""
    
    window: TemporalWindow
    memories: Dict[str, EnhancedCognitiveMemory] = field(default_factory=dict)
    access_patterns: Dict[str, int] = field(default_factory=dict)  # memory_id -> access_count
    last_cleanup: datetime = field(default_factory=datetime.now)
    
    def add_memory(self, memory: EnhancedCognitiveMemory) -> None:
        """Add a memory to this temporal layer."""
        memory.temporal_window = self.window
        self.memories[memory.id] = memory
        self.access_patterns[memory.id] = 0
    
    def remove_memory(self, memory_id: str) -> Optional[EnhancedCognitiveMemory]:
        """Remove a memory from this temporal layer."""
        memory = self.memories.pop(memory_id, None)
        self.access_patterns.pop(memory_id, None)
        return memory
    
    def get_memories_for_transition(self) -> List[EnhancedCognitiveMemory]:
        """Get memories that should transition to different temporal windows."""
        transition_candidates = []
        
        for memory in self.memories.values():
            target_window = memory.should_transition_window()
            if target_window and target_window != self.window:
                transition_candidates.append(memory)
                
        return transition_candidates
    
    def get_memory_count(self) -> int:
        """Get total number of memories in this layer."""
        return len(self.memories)
    
    def get_average_age_days(self) -> float:
        """Get average age of memories in this layer."""
        if not self.memories:
            return 0.0
            
        total_age = sum(memory.calculate_age_days() for memory in self.memories.values())
        return total_age / len(self.memories)