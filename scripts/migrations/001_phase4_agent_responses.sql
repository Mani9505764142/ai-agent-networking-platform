-- Migration: 001_phase4_agent_responses.sql
-- Description: Phase 4 agent responses table and routing log delivery tracking columns.
-- Non-destructive: Uses IF NOT EXISTS.

-- 1. Create agent_responses table for webhook replies / interaction records
CREATE TABLE IF NOT EXISTS public.agent_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES public.posts(id) ON DELETE CASCADE,
    responding_agent_id UUID NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
    routing_log_id UUID REFERENCES public.routing_logs(id) ON DELETE SET NULL,
    response_type VARCHAR(50) NOT NULL DEFAULT 'INTERESTED',
    content TEXT NOT NULL,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS agent_responses_post_idx ON public.agent_responses (post_id);
CREATE INDEX IF NOT EXISTS agent_responses_agent_idx ON public.agent_responses (responding_agent_id);

-- 2. Add delivery auditing columns to routing_logs
ALTER TABLE public.routing_logs 
ADD COLUMN IF NOT EXISTS delivery_attempts INTEGER DEFAULT 0;

ALTER TABLE public.routing_logs 
ADD COLUMN IF NOT EXISTS error_message TEXT;
