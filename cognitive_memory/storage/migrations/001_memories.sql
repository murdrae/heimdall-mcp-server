-- 001_memories.sql
-- Create memories table for core memory metadata

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    hierarchy_level INTEGER NOT NULL CHECK (hierarchy_level IN (0, 1, 2)),
    dimensions TEXT NOT NULL,  -- JSON serialized dimensions
    timestamp REAL NOT NULL,
    strength REAL NOT NULL DEFAULT 1.0 CHECK (strength >= 0.0 AND strength <= 1.0),
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed REAL,
    created_at REAL NOT NULL DEFAULT (julianday('now')),
    updated_at REAL NOT NULL DEFAULT (julianday('now')),

    -- Memory lifecycle tracking
    decay_rate REAL NOT NULL DEFAULT 0.1,
    importance_score REAL NOT NULL DEFAULT 0.0,
    consolidation_status TEXT NOT NULL DEFAULT 'none'
        CHECK (consolidation_status IN ('none', 'candidate', 'consolidated')),

    -- Optional metadata
    tags TEXT,  -- JSON array of tags
    context_metadata TEXT  -- JSON object for additional context
);

-- Indexes for memories table
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories (memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_level ON memories (hierarchy_level);
CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories (timestamp);
CREATE INDEX IF NOT EXISTS idx_memories_strength ON memories (strength);
CREATE INDEX IF NOT EXISTS idx_memories_access_count ON memories (access_count);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories (last_accessed);
CREATE INDEX IF NOT EXISTS idx_memories_consolidation ON memories (consolidation_status);
