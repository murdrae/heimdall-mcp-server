"""
SQLite-based persistence layer for cognitive memory system.

This module implements the database schema and operations as defined in the
technical specification, providing ACID transactions and flexible schema evolution.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager
from loguru import logger

from ..core.memory import CognitiveMemory, MemoryConnection, SystemStats
from ..core.interfaces import MemoryStorage, ConnectionGraph


class SQLiteMemoryStorage(MemoryStorage):
    """SQLite implementation of memory storage interface."""
    
    def __init__(self, db_path: str, enable_wal: bool = True):
        """
        Initialize SQLite memory storage.
        
        Args:
            db_path: Path to SQLite database file
            enable_wal: Enable WAL mode for better concurrency
        """
        self.db_path = Path(db_path)
        self.enable_wal = enable_wal
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize database schema and enable optimizations."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            if self.enable_wal:
                conn.execute("PRAGMA journal_mode=WAL")
            
            # Performance optimizations
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            
            # Create schema
            self._create_schema(conn)
            
            logger.info(f"Initialized SQLite database at {self.db_path}")
    
    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """Create database schema from technical specification."""
        
        # Memory metadata and relationships
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                level INTEGER NOT NULL,
                content TEXT NOT NULL,
                dimensions_json TEXT NOT NULL,
                qdrant_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                last_accessed DATETIME NOT NULL,
                access_count INTEGER DEFAULT 0,
                importance_score REAL DEFAULT 0.0,
                parent_id TEXT,
                memory_type TEXT DEFAULT 'episodic',
                decay_rate REAL DEFAULT 0.1,
                metadata_json TEXT DEFAULT '{}',
                FOREIGN KEY (parent_id) REFERENCES memories(id)
            )
        """)
        
        # Connection graph for activation spreading
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_connections (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                connection_strength REAL NOT NULL,
                connection_type TEXT DEFAULT 'associative',
                created_at DATETIME NOT NULL,
                last_activated DATETIME,
                activation_count INTEGER DEFAULT 0,
                PRIMARY KEY (source_id, target_id),
                FOREIGN KEY (source_id) REFERENCES memories(id),
                FOREIGN KEY (target_id) REFERENCES memories(id)
            )
        """)
        
        # Bridge discovery cache
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bridge_cache (
                query_hash TEXT NOT NULL,
                bridge_memory_id TEXT NOT NULL,
                bridge_score REAL NOT NULL,
                novelty_score REAL NOT NULL,
                connection_potential REAL NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (query_hash, bridge_memory_id),
                FOREIGN KEY (bridge_memory_id) REFERENCES memories(id)
            )
        """)
        
        # Usage statistics for meta-learning
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retrieval_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_hash TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                retrieval_type TEXT NOT NULL,
                success_score REAL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (memory_id) REFERENCES memories(id)
            )
        """)
        
        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_level ON memories(level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_access_count ON memories(access_count)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_connections_strength ON memory_connections(connection_strength)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bridge_cache_query ON bridge_cache(query_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_retrieval_stats_timestamp ON retrieval_stats(timestamp)")
        
        conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def store_memory(self, memory: CognitiveMemory) -> bool:
        """Store a cognitive memory."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO memories (
                        id, level, content, dimensions_json, qdrant_id,
                        timestamp, last_accessed, access_count, importance_score,
                        parent_id, memory_type, decay_rate, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory.id,
                    memory.level,
                    memory.content,
                    json.dumps({k: v.tolist() for k, v in memory.dimensions.items()}),
                    memory.id,  # Use memory ID as Qdrant ID for simplicity
                    memory.timestamp,
                    memory.last_accessed,
                    memory.access_count,
                    memory.importance_score,
                    memory.parent_id,
                    memory.memory_type,
                    memory.decay_rate,
                    json.dumps(memory.metadata)
                ))
                conn.commit()
                logger.debug(f"Stored memory {memory.id} at level {memory.level}")
                return True
        except Exception as e:
            logger.error(f"Failed to store memory {memory.id}: {e}")
            return False
    
    def retrieve_memory(self, memory_id: str) -> Optional[CognitiveMemory]:
        """Retrieve a memory by ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM memories WHERE id = ?
                """, (memory_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_memory(row)
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve memory {memory_id}: {e}")
            return None
    
    def update_memory(self, memory: CognitiveMemory) -> bool:
        """Update an existing memory."""
        return self.store_memory(memory)  # Using INSERT OR REPLACE
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        try:
            with self._get_connection() as conn:
                # Delete connections first
                conn.execute("""
                    DELETE FROM memory_connections 
                    WHERE source_id = ? OR target_id = ?
                """, (memory_id, memory_id))
                
                # Delete from bridge cache
                conn.execute("""
                    DELETE FROM bridge_cache WHERE bridge_memory_id = ?
                """, (memory_id,))
                
                # Delete memory
                cursor = conn.execute("""
                    DELETE FROM memories WHERE id = ?
                """, (memory_id,))
                
                conn.commit()
                success = cursor.rowcount > 0
                if success:
                    logger.debug(f"Deleted memory {memory_id}")
                return success
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False
    
    def get_memories_by_level(self, level: int) -> List[CognitiveMemory]:
        """Get all memories at a specific hierarchy level."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM memories WHERE level = ? ORDER BY timestamp DESC
                """, (level,))
                
                return [self._row_to_memory(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get memories by level {level}: {e}")
            return []
    
    def get_memories_by_type(self, memory_type: str) -> List[CognitiveMemory]:
        """Get all memories of a specific type."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM memories WHERE memory_type = ? ORDER BY timestamp DESC
                """, (memory_type,))
                
                return [self._row_to_memory(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get memories by type {memory_type}: {e}")
            return []
    
    def get_memory_stats(self) -> SystemStats:
        """Get comprehensive system statistics."""
        try:
            with self._get_connection() as conn:
                stats = SystemStats()
                
                # Total memories
                cursor = conn.execute("SELECT COUNT(*) FROM memories")
                stats.total_memories = cursor.fetchone()[0]
                
                # Memories by level
                cursor = conn.execute("""
                    SELECT level, COUNT(*) FROM memories GROUP BY level
                """)
                stats.memories_by_level = dict(cursor.fetchall())
                
                # Memories by type
                cursor = conn.execute("""
                    SELECT memory_type, COUNT(*) FROM memories GROUP BY memory_type
                """)
                stats.memories_by_type = dict(cursor.fetchall())
                
                # Total connections
                cursor = conn.execute("SELECT COUNT(*) FROM memory_connections")
                stats.total_connections = cursor.fetchone()[0]
                
                # Storage size (approximate)
                cursor = conn.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
                result = cursor.fetchone()
                if result and result[0]:
                    stats.storage_size_mb = result[0] / (1024 * 1024)
                
                return stats
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return SystemStats()
    
    def _row_to_memory(self, row: sqlite3.Row) -> CognitiveMemory:
        """Convert database row to CognitiveMemory object."""
        import torch
        
        # Parse dimensions
        dimensions = {}
        if row['dimensions_json']:
            dims_data = json.loads(row['dimensions_json'])
            dimensions = {k: torch.tensor(v) for k, v in dims_data.items()}
        
        # Parse metadata
        metadata = {}
        if row['metadata_json']:
            metadata = json.loads(row['metadata_json'])
        
        return CognitiveMemory(
            id=row['id'],
            content=row['content'],
            level=row['level'],
            dimensions=dimensions,
            timestamp=datetime.fromisoformat(row['timestamp']),
            last_accessed=datetime.fromisoformat(row['last_accessed']),
            access_count=row['access_count'],
            importance_score=row['importance_score'],
            parent_id=row['parent_id'],
            memory_type=row['memory_type'],
            decay_rate=row['decay_rate'],
            metadata=metadata
        )


class SQLiteConnectionGraph(ConnectionGraph):
    """SQLite implementation of connection graph interface."""
    
    def __init__(self, db_path: str):
        """Initialize connection graph with database path."""
        self.db_path = Path(db_path)
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def add_connection(
        self,
        source_id: str,
        target_id: str,
        strength: float,
        connection_type: str = 'associative'
    ) -> bool:
        """Add a connection between two memories."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO memory_connections (
                        source_id, target_id, connection_strength, connection_type,
                        created_at, activation_count
                    ) VALUES (?, ?, ?, ?, ?, 0)
                """, (source_id, target_id, strength, connection_type, datetime.now()))
                conn.commit()
                logger.debug(f"Added connection {source_id} -> {target_id} (strength: {strength})")
                return True
        except Exception as e:
            logger.error(f"Failed to add connection {source_id} -> {target_id}: {e}")
            return False
    
    def get_connections(
        self,
        memory_id: str,
        min_strength: float = 0.0
    ) -> List[MemoryConnection]:
        """Get connected memories above minimum strength threshold."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM memory_connections 
                    WHERE (source_id = ? OR target_id = ?) 
                    AND connection_strength >= ?
                    ORDER BY connection_strength DESC
                """, (memory_id, memory_id, min_strength))
                
                connections = []
                for row in cursor.fetchall():
                    connection = MemoryConnection(
                        source_id=row['source_id'],
                        target_id=row['target_id'],
                        connection_strength=row['connection_strength'],
                        connection_type=row['connection_type'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        last_activated=datetime.fromisoformat(row['last_activated']) if row['last_activated'] else None,
                        activation_count=row['activation_count']
                    )
                    connections.append(connection)
                
                return connections
        except Exception as e:
            logger.error(f"Failed to get connections for {memory_id}: {e}")
            return []
    
    def update_connection_strength(
        self,
        source_id: str,
        target_id: str,
        new_strength: float
    ) -> bool:
        """Update the strength of an existing connection."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    UPDATE memory_connections 
                    SET connection_strength = ?
                    WHERE source_id = ? AND target_id = ?
                """, (new_strength, source_id, target_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update connection {source_id} -> {target_id}: {e}")
            return False
    
    def remove_connection(self, source_id: str, target_id: str) -> bool:
        """Remove a connection between memories."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM memory_connections 
                    WHERE source_id = ? AND target_id = ?
                """, (source_id, target_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove connection {source_id} -> {target_id}: {e}")
            return False
    
    def activate_connection(self, source_id: str, target_id: str) -> bool:
        """Mark a connection as activated."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE memory_connections 
                    SET last_activated = ?, activation_count = activation_count + 1
                    WHERE source_id = ? AND target_id = ?
                """, (datetime.now(), source_id, target_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to activate connection {source_id} -> {target_id}: {e}")
            return False