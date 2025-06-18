-- Migration: Add cognitive_embedding column to memories table
-- This stores the 384-dimensional embedding as a JSON array for fast retrieval

ALTER TABLE memories ADD COLUMN cognitive_embedding TEXT;

-- Add index for faster queries (optional, can be added later if needed)
-- CREATE INDEX idx_memories_embedding_not_null ON memories(cognitive_embedding) WHERE cognitive_embedding IS NOT NULL;
