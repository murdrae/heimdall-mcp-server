-- 002_memory_connections.sql
-- Create memory connections table for connection graph

CREATE TABLE IF NOT EXISTS memory_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    strength REAL NOT NULL CHECK (strength >= 0.0 AND strength <= 1.0),
    connection_type TEXT NOT NULL DEFAULT 'associative',
    created_at REAL NOT NULL DEFAULT (julianday('now')),
    last_activated REAL,
    activation_count INTEGER NOT NULL DEFAULT 0,

    -- Connection metadata
    weight REAL NOT NULL DEFAULT 1.0,
    bidirectional BOOLEAN NOT NULL DEFAULT 1,
    context TEXT,  -- JSON object for connection context

    -- Constraints
    UNIQUE(source_id, target_id, connection_type),
    FOREIGN KEY (source_id) REFERENCES memories (id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES memories (id) ON DELETE CASCADE
);

-- Indexes for memory connections table
CREATE INDEX IF NOT EXISTS idx_connections_source ON memory_connections (source_id);
CREATE INDEX IF NOT EXISTS idx_connections_target ON memory_connections (target_id);
CREATE INDEX IF NOT EXISTS idx_connections_strength ON memory_connections (strength);
CREATE INDEX IF NOT EXISTS idx_connections_type ON memory_connections (connection_type);
CREATE INDEX IF NOT EXISTS idx_connections_activated ON memory_connections (last_activated);
