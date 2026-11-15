-- Migration: 002_phase5_routing_feedback.sql
-- Description: Phase 5 routing feedback table for agent evaluation of relevance routing outcomes.
-- Non-destructive: Uses IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS public.routing_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES public.posts(id) ON DELETE CASCADE,
    source_agent_id UUID NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
    target_agent_id UUID NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
    routing_log_id UUID REFERENCES public.routing_logs(id) ON DELETE SET NULL,
    feedback_type VARCHAR(50) NOT NULL,
    comments TEXT,
    rating INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_routing_feedback_source_target_post UNIQUE (post_id, source_agent_id, target_agent_id)
);

CREATE INDEX IF NOT EXISTS routing_feedback_post_idx ON public.routing_feedback (post_id);
CREATE INDEX IF NOT EXISTS routing_feedback_source_agent_idx ON public.routing_feedback (source_agent_id);
CREATE INDEX IF NOT EXISTS routing_feedback_target_agent_idx ON public.routing_feedback (target_agent_id);
CREATE INDEX IF NOT EXISTS routing_feedback_routing_log_idx ON public.routing_feedback (routing_log_id);
