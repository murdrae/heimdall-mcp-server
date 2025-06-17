"""
Dual memory system implementation with episodic and semantic memory.

This module implements the dual memory system that mirrors human memory
characteristics with fast-decaying episodic memory and slow-decaying semantic
memory, including automatic consolidation mechanisms.
"""

import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

from ..core.memory import CognitiveMemory
from .sqlite_persistence import DatabaseManager


class MemoryType(Enum):
    """Memory types in the dual memory system."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"


@dataclass
class MemoryAccessPattern:
    """Tracks access patterns for memory consolidation."""

    memory_id: str
    access_times: list[float] = field(default_factory=list)
    last_consolidation_check: float = 0.0
    consolidation_score: float = 0.0

    def add_access(self, timestamp: float) -> None:
        """Add an access timestamp."""
        self.access_times.append(timestamp)
        # Keep only recent accesses (last 30 days)
        cutoff = timestamp - (30 * 24 * 3600)  # 30 days in seconds
        self.access_times = [t for t in self.access_times if t >= cutoff]

    def calculate_access_frequency(self, window_hours: float = 168.0) -> float:
        """Calculate access frequency within time window (default 1 week)."""
        now = time.time()
        cutoff = now - (window_hours * 3600)
        recent_accesses = [t for t in self.access_times if t >= cutoff]
        return len(recent_accesses) / window_hours if window_hours > 0 else 0.0

    def calculate_recency_score(self) -> float:
        """Calculate recency score (0-1, higher = more recent)."""
        if not self.access_times:
            return 0.0

        now = time.time()
        last_access = max(self.access_times)
        hours_since = (now - last_access) / 3600

        # Exponential decay with half-life of 7 days
        return math.exp(-hours_since / (7 * 24))

    def calculate_consolidation_score(self) -> float:
        """Calculate consolidation score based on access patterns."""
        frequency = self.calculate_access_frequency()
        recency = self.calculate_recency_score()

        # Access distribution (more distributed = higher score)
        if len(self.access_times) < 2:
            distribution = 0.0
        else:
            intervals = []
            sorted_times = sorted(self.access_times)
            for i in range(1, len(sorted_times)):
                intervals.append(sorted_times[i] - sorted_times[i - 1])

            if intervals:
                # Calculate coefficient of variation (std/mean)
                mean_interval = sum(intervals) / len(intervals)
                if mean_interval > 0:
                    std_interval = math.sqrt(
                        sum((x - mean_interval) ** 2 for x in intervals)
                        / len(intervals)
                    )
                    distribution = 1.0 - min(1.0, std_interval / mean_interval)
                else:
                    distribution = 0.0
            else:
                distribution = 0.0

        # Combine factors (frequency 40%, recency 30%, distribution 30%)
        self.consolidation_score = (
            0.4 * min(1.0, frequency) + 0.3 * recency + 0.3 * distribution
        )

        return self.consolidation_score


class EpisodicMemoryStore:
    """
    Episodic memory store with fast decay and specific experiences.

    Episodic memories represent specific experiences and events with
    fast decay rates, typically persisting for days to weeks.
    """

    def __init__(self, db_manager: DatabaseManager):
        """Initialize episodic memory store."""
        self.db_manager = db_manager
        self.decay_rate = 0.1  # Fast decay rate
        self.max_retention_days = 30  # Maximum retention period

    def store_episodic_memory(self, memory: CognitiveMemory) -> bool:
        """Store an episodic memory with fast decay parameters."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Set episodic-specific parameters
                dimensions_json = json.dumps(memory.dimensions)
                tags_json = json.dumps(memory.tags) if memory.tags else None
                now = time.time()

                # Convert datetime to timestamp if needed
                timestamp_val = (
                    memory.timestamp.timestamp()
                    if hasattr(memory.timestamp, "timestamp")
                    else memory.timestamp
                )

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO memories (
                        id, content, memory_type, hierarchy_level,
                        dimensions, timestamp, strength, access_count,
                        last_accessed, created_at, updated_at,
                        decay_rate, importance_score, consolidation_status,
                        tags, context_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        memory.id,
                        memory.content,
                        MemoryType.EPISODIC.value,
                        memory.hierarchy_level,
                        dimensions_json,
                        timestamp_val,
                        memory.strength,
                        memory.access_count,
                        now,
                        now,
                        now,
                        self.decay_rate,
                        0.0,  # Initial importance score
                        "none",  # Initial consolidation status
                        tags_json,
                        None,
                    ),
                )

                conn.commit()

                logger.debug(
                    "Episodic memory stored",
                    memory_id=memory.id,
                    content_preview=memory.content[:50] + "..."
                    if len(memory.content) > 50
                    else memory.content,
                )

                return True

        except Exception as e:
            logger.error(
                "Failed to store episodic memory", memory_id=memory.id, error=str(e)
            )
            return False

    def get_episodic_memories(
        self, limit: int | None = None, min_strength: float = 0.0
    ) -> list[CognitiveMemory]:
        """Get episodic memories with optional filtering."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                sql = """
                    SELECT * FROM memories
                    WHERE memory_type = ? AND strength >= ?
                    ORDER BY last_accessed DESC, strength DESC
                """

                params = [MemoryType.EPISODIC.value, min_strength]
                if limit:
                    sql += " LIMIT ?"
                    params.append(limit)

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                memories = []
                for row in rows:
                    memory = self._row_to_memory(row)
                    # Apply decay calculation
                    memory.strength = self._calculate_decayed_strength(memory)
                    memories.append(memory)

                return memories

        except Exception as e:
            logger.error("Failed to get episodic memories", error=str(e))
            return []

    def _calculate_decayed_strength(self, memory: CognitiveMemory) -> float:
        """Calculate current strength after decay."""
        now = time.time()
        # Convert datetime to timestamp - CognitiveMemory always uses datetime
        timestamp_val = memory.timestamp.timestamp()
        hours_elapsed = (now - timestamp_val) / 3600

        # Exponential decay: strength = initial * exp(-decay_rate * time)
        decayed_strength = memory.strength * math.exp(
            -self.decay_rate * hours_elapsed / 24
        )

        return max(0.0, min(1.0, decayed_strength))

    def cleanup_expired_memories(self) -> int:
        """Remove episodic memories that have decayed below threshold."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Calculate cutoff time for maximum retention
                cutoff_time = time.time() - (self.max_retention_days * 24 * 3600)

                # Delete very old or completely decayed memories
                cursor.execute(
                    """
                    DELETE FROM memories
                    WHERE memory_type = ?
                    AND (
                        timestamp < ?
                        OR strength < 0.01
                        OR importance_score < 0.01
                    )
                """,
                    (MemoryType.EPISODIC.value, cutoff_time),
                )

                deleted_count = int(cursor.rowcount or 0)
                conn.commit()

                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired episodic memories")

                return deleted_count

        except Exception as e:
            logger.error("Failed to cleanup expired memories", error=str(e))
            return 0

    def _row_to_memory(self, row: Any) -> CognitiveMemory:
        """Convert database row to CognitiveMemory object."""
        dimensions = json.loads(row["dimensions"]) if row["dimensions"] else {}
        tags = json.loads(row["tags"]) if row["tags"] else None

        return CognitiveMemory(
            id=row["id"],
            content=row["content"],
            memory_type=row["memory_type"],
            hierarchy_level=row["hierarchy_level"],
            dimensions=dimensions,
            timestamp=datetime.fromtimestamp(row["timestamp"])
            if row["timestamp"]
            else datetime.now(),
            strength=row["strength"],
            access_count=row["access_count"],
            tags=tags,
        )


class SemanticMemoryStore:
    """
    Semantic memory store with slow decay and generalized knowledge.

    Semantic memories represent generalized patterns and knowledge with
    slow decay rates, typically persisting for months to years.
    """

    def __init__(self, db_manager: DatabaseManager):
        """Initialize semantic memory store."""
        self.db_manager = db_manager
        self.decay_rate = 0.01  # Slow decay rate
        self.min_consolidation_score = 0.6  # Minimum score for consolidation

    def store_semantic_memory(self, memory: CognitiveMemory) -> bool:
        """Store a semantic memory with slow decay parameters."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                dimensions_json = json.dumps(memory.dimensions)
                tags_json = json.dumps(memory.tags) if memory.tags else None
                now = time.time()

                # Convert datetime to timestamp if needed
                timestamp_val = (
                    memory.timestamp.timestamp()
                    if hasattr(memory.timestamp, "timestamp")
                    else memory.timestamp
                )

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO memories (
                        id, content, memory_type, hierarchy_level,
                        dimensions, timestamp, strength, access_count,
                        last_accessed, created_at, updated_at,
                        decay_rate, importance_score, consolidation_status,
                        tags, context_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        memory.id,
                        memory.content,
                        MemoryType.SEMANTIC.value,
                        memory.hierarchy_level,
                        dimensions_json,
                        timestamp_val,
                        memory.strength,
                        memory.access_count,
                        now,
                        now,
                        now,
                        self.decay_rate,
                        memory.strength,  # Use strength as initial importance
                        "consolidated",  # Semantic memories are already consolidated
                        tags_json,
                        None,
                    ),
                )

                conn.commit()

                logger.debug(
                    "Semantic memory stored",
                    memory_id=memory.id,
                    content_preview=memory.content[:50] + "..."
                    if len(memory.content) > 50
                    else memory.content,
                )

                return True

        except Exception as e:
            logger.error(
                "Failed to store semantic memory", memory_id=memory.id, error=str(e)
            )
            return False

    def get_semantic_memories(
        self, limit: int | None = None, min_strength: float = 0.0
    ) -> list[CognitiveMemory]:
        """Get semantic memories with optional filtering."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                sql = """
                    SELECT * FROM memories
                    WHERE memory_type = ? AND strength >= ?
                    ORDER BY importance_score DESC, access_count DESC
                """

                params = [MemoryType.SEMANTIC.value, min_strength]
                if limit:
                    sql += " LIMIT ?"
                    params.append(limit)

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                memories = []
                for row in rows:
                    memory = self._row_to_memory(row)
                    # Apply slow decay calculation
                    memory.strength = self._calculate_decayed_strength(memory)
                    memories.append(memory)

                return memories

        except Exception as e:
            logger.error("Failed to get semantic memories", error=str(e))
            return []

    def _calculate_decayed_strength(self, memory: CognitiveMemory) -> float:
        """Calculate current strength after slow decay."""
        now = time.time()
        # Convert datetime to timestamp - CognitiveMemory always uses datetime
        timestamp_val = memory.timestamp.timestamp()
        days_elapsed = (now - timestamp_val) / (24 * 3600)

        # Very slow exponential decay
        decayed_strength = memory.strength * math.exp(
            -self.decay_rate * days_elapsed / 30
        )

        return max(0.0, min(1.0, decayed_strength))

    def _row_to_memory(self, row: Any) -> CognitiveMemory:
        """Convert database row to CognitiveMemory object."""
        dimensions = json.loads(row["dimensions"]) if row["dimensions"] else {}
        tags = json.loads(row["tags"]) if row["tags"] else None

        return CognitiveMemory(
            id=row["id"],
            content=row["content"],
            memory_type=row["memory_type"],
            hierarchy_level=row["hierarchy_level"],
            dimensions=dimensions,
            timestamp=datetime.fromtimestamp(row["timestamp"])
            if row["timestamp"]
            else datetime.now(),
            strength=row["strength"],
            access_count=row["access_count"],
            tags=tags,
        )


class MemoryConsolidation:
    """
    Handles consolidation of episodic memories to semantic memories.

    Implements automatic consolidation based on access patterns,
    importance scoring, and time-based criteria.
    """

    def __init__(self, db_manager: DatabaseManager):
        """Initialize memory consolidation system."""
        self.db_manager = db_manager
        self.access_patterns: dict[str, MemoryAccessPattern] = {}
        self.consolidation_threshold = 0.6
        self.min_accesses_for_consolidation = 3
        self.consolidation_cooldown_hours = 24  # Wait between consolidation attempts

    def track_memory_access(
        self, memory_id: str, timestamp: float | None = None
    ) -> None:
        """Track memory access for consolidation scoring."""
        if timestamp is None:
            timestamp = time.time()

        if memory_id not in self.access_patterns:
            self.access_patterns[memory_id] = MemoryAccessPattern(memory_id)

        self.access_patterns[memory_id].add_access(timestamp)

    def identify_consolidation_candidates(self) -> list[tuple[str, float]]:
        """Identify episodic memories ready for consolidation."""
        candidates = []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get episodic memories not recently checked for consolidation
                cutoff_time = time.time() - (self.consolidation_cooldown_hours * 3600)

                cursor.execute(
                    """
                    SELECT id, access_count, last_accessed, created_at, strength
                    FROM memories
                    WHERE memory_type = ?
                    AND consolidation_status = 'none'
                    AND access_count >= ?
                    AND (last_accessed IS NULL OR last_accessed < ?)
                """,
                    (
                        MemoryType.EPISODIC.value,
                        self.min_accesses_for_consolidation,
                        cutoff_time,
                    ),
                )

                rows = cursor.fetchall()

                for row in rows:
                    memory_id = row["id"]

                    # Calculate consolidation score
                    if memory_id in self.access_patterns:
                        pattern = self.access_patterns[memory_id]
                        score = pattern.calculate_consolidation_score()
                    else:
                        # Fallback scoring based on database data
                        age_days = (time.time() - row["created_at"]) / (24 * 3600)
                        access_rate = row["access_count"] / max(1, age_days)
                        score = min(1.0, access_rate * row["strength"])

                    if score >= self.consolidation_threshold:
                        candidates.append((memory_id, score))

                # Sort by consolidation score
                candidates.sort(key=lambda x: x[1], reverse=True)

                logger.debug(f"Found {len(candidates)} consolidation candidates")
                return candidates

        except Exception as e:
            logger.error("Failed to identify consolidation candidates", error=str(e))
            return []

    def consolidate_memory(self, memory_id: str) -> bool:
        """Consolidate an episodic memory to semantic memory."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get the episodic memory
                cursor.execute(
                    """
                    SELECT * FROM memories WHERE id = ? AND memory_type = ?
                """,
                    (memory_id, MemoryType.EPISODIC.value),
                )

                row = cursor.fetchone()
                if not row:
                    logger.warning(
                        "Memory not found for consolidation", memory_id=memory_id
                    )
                    return False

                # Create semantic version
                semantic_id = f"{memory_id}_semantic"
                now = time.time()

                # Calculate consolidated importance score
                access_pattern = self.access_patterns.get(memory_id)
                if access_pattern:
                    importance_score = access_pattern.calculate_consolidation_score()
                else:
                    importance_score = row["strength"]

                cursor.execute(
                    """
                    INSERT INTO memories (
                        id, content, memory_type, hierarchy_level,
                        dimensions, timestamp, strength, access_count,
                        last_accessed, created_at, updated_at,
                        decay_rate, importance_score, consolidation_status,
                        tags, context_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        semantic_id,
                        row["content"],
                        MemoryType.SEMANTIC.value,
                        row["hierarchy_level"],
                        row["dimensions"],
                        now,  # New timestamp for semantic memory
                        min(1.0, row["strength"] * 1.2),  # Boost strength for semantic
                        row["access_count"],
                        now,
                        now,
                        now,
                        0.01,  # Semantic decay rate
                        importance_score,
                        "consolidated",
                        row["tags"],
                        json.dumps({"source_episodic_id": memory_id}),
                    ),
                )

                # Mark original episodic memory as consolidated
                cursor.execute(
                    """
                    UPDATE memories
                    SET consolidation_status = 'consolidated',
                        updated_at = julianday('now')
                    WHERE id = ?
                """,
                    (memory_id,),
                )

                conn.commit()

                logger.info(
                    "Memory consolidated successfully",
                    episodic_id=memory_id,
                    semantic_id=semantic_id,
                    importance_score=importance_score,
                )

                return True

        except Exception as e:
            logger.error(
                "Failed to consolidate memory", memory_id=memory_id, error=str(e)
            )
            return False

    def run_consolidation_cycle(self) -> dict[str, int]:
        """Run a complete consolidation cycle."""
        stats = {"candidates_identified": 0, "memories_consolidated": 0, "errors": 0}

        try:
            # Identify candidates
            candidates = self.identify_consolidation_candidates()
            stats["candidates_identified"] = len(candidates)

            # Consolidate memories
            for memory_id, _score in candidates:
                try:
                    if self.consolidate_memory(memory_id):
                        stats["memories_consolidated"] += 1
                    else:
                        stats["errors"] += 1
                except Exception as e:
                    logger.error(
                        "Error consolidating memory", memory_id=memory_id, error=str(e)
                    )
                    stats["errors"] += 1

            logger.info("Consolidation cycle completed", stats=stats)

        except Exception as e:
            logger.error("Consolidation cycle failed", error=str(e))
            stats["errors"] += 1

        return stats


class DualMemorySystem:
    """
    Complete dual memory system combining episodic and semantic stores.

    Provides unified interface for storing, retrieving, and managing
    both episodic and semantic memories with automatic consolidation.
    """

    def __init__(self, db_manager: DatabaseManager):
        """Initialize dual memory system."""
        self.db_manager = db_manager
        self.episodic_store = EpisodicMemoryStore(db_manager)
        self.semantic_store = SemanticMemoryStore(db_manager)
        self.consolidation = MemoryConsolidation(db_manager)

    def store_experience(self, memory: CognitiveMemory) -> bool:
        """Store a new experience as episodic memory."""
        return self.episodic_store.store_episodic_memory(memory)

    def store_knowledge(self, memory: CognitiveMemory) -> bool:
        """Store generalized knowledge as semantic memory."""
        return self.semantic_store.store_semantic_memory(memory)

    def retrieve_memories(
        self,
        memory_types: list[MemoryType] | None = None,
        limit: int | None = None,
        min_strength: float = 0.0,
    ) -> dict[MemoryType, list[CognitiveMemory]]:
        """Retrieve memories from both stores."""
        if memory_types is None:
            memory_types = [MemoryType.EPISODIC, MemoryType.SEMANTIC]

        results = {}

        if MemoryType.EPISODIC in memory_types:
            results[MemoryType.EPISODIC] = self.episodic_store.get_episodic_memories(
                limit=limit, min_strength=min_strength
            )

        if MemoryType.SEMANTIC in memory_types:
            results[MemoryType.SEMANTIC] = self.semantic_store.get_semantic_memories(
                limit=limit, min_strength=min_strength
            )

        return results

    def access_memory(self, memory_id: str) -> CognitiveMemory | None:
        """Access a memory and track the access for consolidation."""
        self.consolidation.track_memory_access(memory_id)

        # Try episodic store first
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
                row = cursor.fetchone()

                if row:
                    # Update access count
                    cursor.execute(
                        """
                        UPDATE memories
                        SET access_count = access_count + 1,
                            last_accessed = julianday('now')
                        WHERE id = ?
                    """,
                        (memory_id,),
                    )
                    conn.commit()

                    # Convert to CognitiveMemory
                    dimensions = (
                        json.loads(row["dimensions"]) if row["dimensions"] else {}
                    )
                    tags = json.loads(row["tags"]) if row["tags"] else None

                    return CognitiveMemory(
                        id=row["id"],
                        content=row["content"],
                        memory_type=row["memory_type"],
                        hierarchy_level=row["hierarchy_level"],
                        dimensions=dimensions,
                        timestamp=datetime.fromtimestamp(row["timestamp"])
                        if row["timestamp"]
                        else datetime.now(),
                        strength=row["strength"],
                        access_count=row["access_count"] + 1,
                        tags=tags,
                    )

                return None

        except Exception as e:
            logger.error("Failed to access memory", memory_id=memory_id, error=str(e))
            return None

    def consolidate_memories(self) -> dict[str, int]:
        """Trigger memory consolidation cycle."""
        return self.consolidation.run_consolidation_cycle()

    def cleanup_expired_memories(self) -> dict[str, int]:
        """Clean up expired memories from both stores."""
        episodic_cleaned = self.episodic_store.cleanup_expired_memories()

        return {
            "episodic_cleaned": episodic_cleaned,
            "semantic_cleaned": 0,  # Semantic memories don't expire automatically
        }

    def get_memory_stats(self) -> dict[str, Any]:
        """Get comprehensive memory system statistics."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                stats = {}

                # Count memories by type
                for memory_type in [
                    MemoryType.EPISODIC.value,
                    MemoryType.SEMANTIC.value,
                ]:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) as total,
                            AVG(strength) as avg_strength,
                            AVG(access_count) as avg_access_count,
                            MAX(access_count) as max_access_count
                        FROM memories WHERE memory_type = ?
                    """,
                        (memory_type,),
                    )

                    row = cursor.fetchone()
                    stats[memory_type] = {
                        "total_memories": row["total"],
                        "average_strength": row["avg_strength"] or 0.0,
                        "average_access_count": row["avg_access_count"] or 0.0,
                        "max_access_count": row["max_access_count"] or 0,
                    }

                # Consolidation statistics
                cursor.execute("""
                    SELECT COUNT(*) as consolidated_count
                    FROM memories
                    WHERE consolidation_status = 'consolidated'
                """)
                stats["consolidation"] = {
                    "consolidated_memories": cursor.fetchone()["consolidated_count"]
                }

                # Access pattern statistics
                stats["access_patterns"] = {
                    "tracked_patterns": len(self.consolidation.access_patterns)
                }

                return stats

        except Exception as e:
            logger.error("Failed to get memory stats", error=str(e))
            return {"error": str(e)}


def create_dual_memory_system(
    db_path: str = "data/cognitive_memory.db",
) -> DualMemorySystem:
    """
    Factory function to create dual memory system.

    Args:
        db_path: Path to SQLite database file

    Returns:
        DualMemorySystem: Configured dual memory system
    """
    db_manager = DatabaseManager(db_path)
    return DualMemorySystem(db_manager)
