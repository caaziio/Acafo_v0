-- Database schema for Resume Builder
-- This file contains the SQL commands to create the necessary tables

-- Enable Row Level Security (RLS) for data isolation
-- ALTER TABLE experiences ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE ai_logs ENABLE ROW LEVEL SECURITY;

-- Experiences table to store user resume experiences
CREATE TABLE IF NOT EXISTS experiences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title TEXT NOT NULL,
    experience_text TEXT NOT NULL,
    bullets JSONB NOT NULL DEFAULT '[]',
    skills JSONB NOT NULL DEFAULT '[]',
    experience_type TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- AI logs table to store AI call details (replaces Google Sheets logging)
CREATE TABLE IF NOT EXISTS ai_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    request_id TEXT NOT NULL,
    session_id TEXT,
    method TEXT NOT NULL,
    experience_type TEXT,
    text_length INTEGER DEFAULT 0,
    text_hash TEXT,
    elapsed_ms INTEGER DEFAULT 0,
    success BOOLEAN DEFAULT TRUE,
    error TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_experiences_user_id ON experiences(user_id);
CREATE INDEX IF NOT EXISTS idx_experiences_created_at ON experiences(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_logs_user_id ON ai_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_logs_timestamp ON ai_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_logs_request_id ON ai_logs(request_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for experiences table
CREATE TRIGGER update_experiences_updated_at 
    BEFORE UPDATE ON experiences 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security Policies (uncomment when ready to use)
-- Policy for experiences table
-- CREATE POLICY "Users can only access their own experiences" ON experiences
--     FOR ALL USING (auth.uid() = user_id);

-- Policy for ai_logs table  
-- CREATE POLICY "Users can only access their own AI logs" ON ai_logs
--     FOR ALL USING (auth.uid() = user_id);

-- Grant necessary permissions (adjust based on your Supabase setup)
-- GRANT ALL ON experiences TO authenticated;
-- GRANT ALL ON ai_logs TO authenticated;

