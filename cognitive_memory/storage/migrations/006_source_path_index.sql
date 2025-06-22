-- 006_source_path_index.sql
-- Create JSON index on source_path for efficient file monitoring queries

-- Create an index on the source_path field extracted from context_metadata JSON
-- This optimizes queries that filter by source_path for file monitoring operations
CREATE INDEX IF NOT EXISTS idx_memories_source_path ON memories (
    JSON_EXTRACT(context_metadata, '$.source_path')
);

-- Create a partial index that only indexes rows where source_path exists
-- This is more efficient as not all memories have source_path metadata
CREATE INDEX IF NOT EXISTS idx_memories_source_path_exists ON memories (
    JSON_EXTRACT(context_metadata, '$.source_path')
) WHERE JSON_EXTRACT(context_metadata, '$.source_path') IS NOT NULL;
