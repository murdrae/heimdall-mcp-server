"""
SQLite persistence layer for cognitive memory metadata and connection graph.

This module implements structured data storage using SQLite with a complete
database schema for memory metadata, connection graphs, bridge cache, and
retrieval statistics to support the cognitive memory system.
"""

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from ..core.interfaces import ConnectionGraph, MemoryStorage
from ..core.memory import CognitiveMemory


class DatabaseManager:
    """SQLite database manager with schema management and migrations."""

    def __init__(self, db_path: str = "data/cognitive_memory.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Path to migration files
        self.migrations_path = Path(__file__).parent / "migrations"

        # Initialize database schema
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database with complete schema using migration files."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Create migration tracking table
                self._create_migration_table(cursor)

                # Run migrations
                self._run_migrations(cursor)

                conn.commit()
                logger.info("Database schema initialized", db_path=str(self.db_path))

        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise

    def _create_migration_table(self, cursor: sqlite3.Cursor) -> None:
        """Create table to track applied migrations."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at REAL NOT NULL DEFAULT (julianday('now'))
            )
        """)

    def _run_migrations(self, cursor: sqlite3.Cursor) -> None:
        """Run all pending migrations."""
        # Get applied migrations
        cursor.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cursor.fetchall()}

        # Get available migration files
        migration_files = sorted(self.migrations_path.glob("*.sql"))

        for migration_file in migration_files:
            version = migration_file.stem  # e.g., "001_memories"

            if version not in applied:
                logger.info(f"Applying migration: {version}")

                # Read and execute migration SQL
                sql_content = migration_file.read_text()
                # Split and execute individual statements to avoid auto-commit issues
                statements = [
                    stmt.strip() for stmt in sql_content.split(";") if stmt.strip()
                ]
                for statement in statements:
                    cursor.execute(statement)

                # Record migration as applied
                cursor.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
                )

                logger.debug(f"Migration applied successfully: {version}")

        logger.info(f"All migrations applied. Total: {len(migration_files)}")

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        """Get database connection with proper context management."""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable dict-like access

            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")

            # Set performance optimizations
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = 10000")
            conn.execute("PRAGMA temp_store = MEMORY")

            yield conn

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("Database operation failed", error=str(e))
            raise
        finally:
            if conn:
                conn.close()

    def vacuum_database(self) -> bool:
        """Vacuum database to reclaim space and optimize performance."""
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                logger.info("Database vacuumed successfully")
                return True
        except Exception as e:
            logger.error("Failed to vacuum database", error=str(e))
            return False

    def get_database_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                stats = {}
                tables = [
                    "memories",
                    "memory_connections",
                    "bridge_cache",
                    "retrieval_stats",
                ]

                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                    count = cursor.fetchone()["count"]
                    stats[f"{table}_count"] = count

                # Get database file size
                stats["database_size_bytes"] = self.db_path.stat().st_size

                return stats

        except Exception as e:
            logger.error("Failed to get database stats", error=str(e))
            return {"error": str(e)}


class MemoryMetadataStore(MemoryStorage):
    """SQLite-based memory metadata storage implementing MemoryStorage interface."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize memory metadata store."""
        self.db_manager = db_manager

    def store_memory(self, memory: CognitiveMemory) -> bool:
        """Store a cognitive memory with full metadata."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Serialize dimensions and tags
                dimensions_json = json.dumps(memory.dimensions)
                tags_json = json.dumps(memory.tags) if memory.tags else None

                # Current timestamp
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
                        memory.memory_type,
                        memory.hierarchy_level,
                        dimensions_json,
                        timestamp_val,
                        memory.strength,
                        memory.access_count,
                        now,  # last_accessed
                        now,  # created_at (will be ignored if record exists)
                        now,  # updated_at
                        memory.decay_rate,  # Use memory's decay rate
                        memory.importance_score,  # Use memory's importance score
                        "none",  # consolidation_status
                        tags_json,
                        None,  # context_metadata
                    ),
                )

                conn.commit()

                logger.debug(
                    "Memory stored successfully",
                    memory_id=memory.id,
                    memory_type=memory.memory_type,
                    level=memory.hierarchy_level,
                )

                return True

        except Exception as e:
            logger.error("Failed to store memory", memory_id=memory.id, error=str(e))
            return False

    def retrieve_memory(self, memory_id: str) -> CognitiveMemory | None:
        """Retrieve a memory by ID."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT * FROM memories WHERE id = ?
                """,
                    (memory_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                # Update access count and last accessed
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

                # Convert row to CognitiveMemory
                return self._row_to_memory(row)

        except Exception as e:
            logger.error("Failed to retrieve memory", memory_id=memory_id, error=str(e))
            return None

    def update_memory(self, memory: CognitiveMemory) -> bool:
        """Update an existing memory."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                dimensions_json = json.dumps(memory.dimensions)
                tags_json = json.dumps(memory.tags) if memory.tags else None

                # Convert datetime to timestamp if needed
                timestamp_val = (
                    memory.timestamp.timestamp()
                    if hasattr(memory.timestamp, "timestamp")
                    else memory.timestamp
                )

                cursor.execute(
                    """
                    UPDATE memories SET
                        content = ?, memory_type = ?, hierarchy_level = ?,
                        dimensions = ?, timestamp = ?, strength = ?,
                        access_count = ?, tags = ?, updated_at = julianday('now')
                    WHERE id = ?
                """,
                    (
                        memory.content,
                        memory.memory_type,
                        memory.hierarchy_level,
                        dimensions_json,
                        timestamp_val,
                        memory.strength,
                        memory.access_count,
                        tags_json,
                        memory.id,
                    ),
                )

                if cursor.rowcount == 0:
                    logger.warning("Memory not found for update", memory_id=memory.id)
                    return False

                conn.commit()
                return True

        except Exception as e:
            logger.error("Failed to update memory", memory_id=memory.id, error=str(e))
            return False

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

                if cursor.rowcount == 0:
                    logger.warning("Memory not found for deletion", memory_id=memory_id)
                    return False

                conn.commit()

                logger.debug("Memory deleted successfully", memory_id=memory_id)
                return True

        except Exception as e:
            logger.error("Failed to delete memory", memory_id=memory_id, error=str(e))
            return False

    def get_memories_by_level(self, level: int) -> list[CognitiveMemory]:
        """Get all memories at a specific hierarchy level."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT * FROM memories
                    WHERE hierarchy_level = ?
                    ORDER BY strength DESC, access_count DESC
                """,
                    (level,),
                )

                rows = cursor.fetchall()
                return [self._row_to_memory(row) for row in rows]

        except Exception as e:
            logger.error("Failed to get memories by level", level=level, error=str(e))
            return []

    def get_memories_by_type(
        self, memory_type: str, limit: int | None = None
    ) -> list[CognitiveMemory]:
        """Get memories by type with optional limit."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                sql = """
                    SELECT * FROM memories
                    WHERE memory_type = ?
                    ORDER BY strength DESC, access_count DESC
                """

                params: list[Any] = [memory_type]
                if limit:
                    sql += " LIMIT ?"
                    params.append(str(limit))

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                return [self._row_to_memory(row) for row in rows]

        except Exception as e:
            logger.error(
                "Failed to get memories by type", memory_type=memory_type, error=str(e)
            )
            return []

    def _row_to_memory(self, row: sqlite3.Row) -> CognitiveMemory:
        """Convert database row to CognitiveMemory object."""
        dimensions = json.loads(row["dimensions"]) if row["dimensions"] else {}
        tags = json.loads(row["tags"]) if row["tags"] else None

        # Convert timestamp back to datetime
        timestamp = (
            datetime.fromtimestamp(row["timestamp"])
            if row["timestamp"]
            else datetime.now()
        )

        return CognitiveMemory(
            id=row["id"],
            content=row["content"],
            memory_type=row["memory_type"],
            hierarchy_level=row[
                "hierarchy_level"
            ],  # Use level instead of hierarchy_level for CognitiveMemory constructor
            dimensions=dimensions,
            timestamp=timestamp,
            strength=row["strength"],
            access_count=row["access_count"],
            tags=tags,
            importance_score=row["importance_score"]
            if "importance_score" in row.keys()
            else 0.0,
            decay_rate=row["decay_rate"] if "decay_rate" in row.keys() else 0.1,
        )


class ConnectionGraphStore(ConnectionGraph):
    """SQLite-based connection graph storage implementing ConnectionGraph interface."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize connection graph store."""
        self.db_manager = db_manager

    def add_connection(
        self,
        source_id: str,
        target_id: str,
        strength: float,
        connection_type: str = "associative",
    ) -> bool:
        """Add a connection between two memories."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO memory_connections (
                        source_id, target_id, strength, connection_type,
                        created_at, last_activated, activation_count, weight
                    ) VALUES (?, ?, ?, ?, julianday('now'), julianday('now'), 1, ?)
                """,
                    (source_id, target_id, strength, connection_type, strength),
                )

                conn.commit()

                logger.debug(
                    "Connection added successfully",
                    source_id=source_id,
                    target_id=target_id,
                    strength=strength,
                    connection_type=connection_type,
                )

                return True

        except Exception as e:
            logger.error(
                "Failed to add connection",
                source_id=source_id,
                target_id=target_id,
                error=str(e),
            )
            return False

    def get_connections(
        self, memory_id: str, min_strength: float = 0.0
    ) -> list[CognitiveMemory]:
        """Get connected memories above minimum strength threshold."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get connections where memory_id is either source or target
                cursor.execute(
                    """
                    SELECT m.*, mc.strength as connection_strength
                    FROM memory_connections mc
                    JOIN memories m ON (
                        (mc.source_id = ? AND m.id = mc.target_id) OR
                        (mc.target_id = ? AND m.id = mc.source_id)
                    )
                    WHERE mc.strength >= ?
                    ORDER BY mc.strength DESC, m.access_count DESC
                """,
                    (memory_id, memory_id, min_strength),
                )

                rows = cursor.fetchall()

                # Update activation count for accessed connections
                if rows:
                    cursor.execute(
                        """
                        UPDATE memory_connections
                        SET activation_count = activation_count + 1,
                            last_activated = julianday('now')
                        WHERE (source_id = ? OR target_id = ?) AND strength >= ?
                    """,
                        (memory_id, memory_id, min_strength),
                    )
                    conn.commit()

                # Convert to CognitiveMemory objects
                memories = []
                for row in rows:
                    memory = self._row_to_memory(row)
                    memories.append(memory)

                return memories

        except Exception as e:
            logger.error(
                "Failed to get connections",
                memory_id=memory_id,
                min_strength=min_strength,
                error=str(e),
            )
            return []

    def update_connection_strength(
        self, source_id: str, target_id: str, new_strength: float
    ) -> bool:
        """Update the strength of an existing connection."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    UPDATE memory_connections
                    SET strength = ?,
                        weight = ?,
                        last_activated = julianday('now')
                    WHERE (source_id = ? AND target_id = ?)
                       OR (source_id = ? AND target_id = ?)
                """,
                    (
                        new_strength,
                        new_strength,
                        source_id,
                        target_id,
                        target_id,
                        source_id,
                    ),
                )

                if cursor.rowcount == 0:
                    logger.warning(
                        "Connection not found for strength update",
                        source_id=source_id,
                        target_id=target_id,
                    )
                    return False

                conn.commit()
                return True

        except Exception as e:
            logger.error(
                "Failed to update connection strength",
                source_id=source_id,
                target_id=target_id,
                error=str(e),
            )
            return False

    def remove_connection(self, source_id: str, target_id: str) -> bool:
        """Remove a connection between memories."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    DELETE FROM memory_connections
                    WHERE (source_id = ? AND target_id = ?)
                       OR (source_id = ? AND target_id = ?)
                """,
                    (source_id, target_id, target_id, source_id),
                )

                if cursor.rowcount == 0:
                    logger.warning(
                        "Connection not found for removal",
                        source_id=source_id,
                        target_id=target_id,
                    )
                    return False

                conn.commit()

                logger.debug(
                    "Connection removed successfully",
                    source_id=source_id,
                    target_id=target_id,
                )

                return True

        except Exception as e:
            logger.error(
                "Failed to remove connection",
                source_id=source_id,
                target_id=target_id,
                error=str(e),
            )
            return False

    def get_connection_strength(self, source_id: str, target_id: str) -> float | None:
        """Get the strength of a connection between two memories."""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT strength FROM memory_connections
                    WHERE (source_id = ? AND target_id = ?)
                       OR (source_id = ? AND target_id = ?)
                    LIMIT 1
                """,
                    (source_id, target_id, target_id, source_id),
                )

                row = cursor.fetchone()
                return row["strength"] if row else None

        except Exception as e:
            logger.error(
                "Failed to get connection strength",
                source_id=source_id,
                target_id=target_id,
                error=str(e),
            )
            return None

    def _row_to_memory(self, row: sqlite3.Row) -> CognitiveMemory:
        """Convert database row to CognitiveMemory object."""
        dimensions = json.loads(row["dimensions"]) if row["dimensions"] else {}
        tags = json.loads(row["tags"]) if row["tags"] else None

        # Convert timestamp back to datetime
        timestamp = (
            datetime.fromtimestamp(row["timestamp"])
            if row["timestamp"]
            else datetime.now()
        )

        return CognitiveMemory(
            id=row["id"],
            content=row["content"],
            memory_type=row["memory_type"],
            hierarchy_level=row[
                "hierarchy_level"
            ],  # Use level instead of hierarchy_level for CognitiveMemory constructor
            dimensions=dimensions,
            timestamp=timestamp,
            strength=row["strength"],
            access_count=row["access_count"],
            tags=tags,
            importance_score=row["importance_score"]
            if "importance_score" in row.keys()
            else 0.0,
            decay_rate=row["decay_rate"] if "decay_rate" in row.keys() else 0.1,
        )


def create_sqlite_persistence(
    db_path: str = "data/cognitive_memory.db",
) -> tuple[MemoryMetadataStore, ConnectionGraphStore]:
    """
    Factory function to create SQLite persistence components.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Tuple of (MemoryMetadataStore, ConnectionGraphStore)
    """
    db_manager = DatabaseManager(db_path)
    memory_store = MemoryMetadataStore(db_manager)
    connection_store = ConnectionGraphStore(db_manager)

    return memory_store, connection_store
