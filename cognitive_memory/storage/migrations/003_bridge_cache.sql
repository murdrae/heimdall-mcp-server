-- 003_bridge_cache.sql
-- Create bridge cache table for cached bridge discovery results

CREATE TABLE IF NOT EXISTS bridge_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_hash TEXT NOT NULL,  -- Hash of query context
    bridge_memory_id TEXT NOT NULL,
    source_memory_id TEXT NOT NULL,
    target_memory_id TEXT NOT NULL,
    bridge_strength REAL NOT NULL,
    discovery_score REAL NOT NULL,
    created_at REAL NOT NULL DEFAULT (julianday('now')),
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed REAL,

    -- Cache metadata
    ttl_hours INTEGER NOT NULL DEFAULT 168,  -- 1 week default TTL
    context_data TEXT,  -- JSON serialized context

    -- Constraints
    FOREIGN KEY (bridge_memory_id) REFERENCES memories (id) ON DELETE CASCADE,
    FOREIGN KEY (source_memory_id) REFERENCES memories (id) ON DELETE CASCADE,
    FOREIGN KEY (target_memory_id) REFERENCES memories (id) ON DELETE CASCADE
);

-- Indexes for bridge cache table
CREATE INDEX IF NOT EXISTS idx_bridge_cache_query ON bridge_cache (query_hash);
CREATE INDEX IF NOT EXISTS idx_bridge_cache_bridge ON bridge_cache (bridge_memory_id);
CREATE INDEX IF NOT EXISTS idx_bridge_cache_created ON bridge_cache (created_at);
CREATE INDEX IF NOT EXISTS idx_bridge_cache_accessed ON bridge_cache (last_accessed);
