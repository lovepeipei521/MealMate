-- File: 11-llm_usage_logs_tool_name.sql
-- Migration: Add tool_name column to llm_usage_logs table
-- Description: Adds tool_name field to track which tool was used in LLM calls
-- Created: 2026-01-16

-- Add tool_name column to existing llm_usage_logs table
ALTER TABLE llm_usage_logs
ADD COLUMN IF NOT EXISTS tool_name VARCHAR(100);

-- Create index on tool_name for fast lookups
CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_tool_name
    ON llm_usage_logs (tool_name);

-- Create composite index for tool_name + time queries (most common usage pattern)
CREATE INDEX IF NOT EXISTS ix_llm_usage_tool_created
    ON llm_usage_logs (tool_name, created_at DESC);
    
-- Add comment to document the new column
COMMENT ON COLUMN llm_usage_logs.tool_name IS
    'The name of the tool used in this LLM call (null if no tool was used)';
