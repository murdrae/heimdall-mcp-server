-- 004_retrieval_stats.sql
-- Create retrieval stats table for usage statistics and meta-learning

CREATE TABLE IF NOT EXISTS retrieval_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_type TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    retrieval_score REAL NOT NULL,
    retrieval_rank INTEGER NOT NULL,
    user_feedback INTEGER,  -- -1 (negative), 0 (neutral), 1 (positive)
    session_id TEXT,
    timestamp REAL NOT NULL DEFAULT (julianday('now')),

    -- Query context
    query_metadata TEXT,  -- JSON serialized query context
    retrieval_metadata TEXT,  -- JSON serialized retrieval context

    -- Performance metrics
    search_latency_ms REAL,
    total_candidates INTEGER,

    -- Constraints
    FOREIGN KEY (memory_id) REFERENCES memories (id) ON DELETE CASCADE
);

-- Indexes for retrieval stats table
CREATE INDEX IF NOT EXISTS idx_retrieval_stats_query ON retrieval_stats (query_type, query_hash);
CREATE INDEX IF NOT EXISTS idx_retrieval_stats_memory ON retrieval_stats (memory_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_stats_timestamp ON retrieval_stats (timestamp);
CREATE INDEX IF NOT EXISTS idx_retrieval_stats_session ON retrieval_stats (session_id);
