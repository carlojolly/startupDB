-- ============================================================================
-- feedback — what a reader of the dashboard says about what they are looking at.
--
-- The dashboard is shared with dealflow analysts who have no account and no
-- reason to write an email. A textarea in the header writes here instead.
--
-- Two columns carry the context the writer should not have to type:
--   `page`   — the path they were on, so "this is wrong" has a referent.
--   `run_id` — the tag run that was published when they wrote, because the
--              labels they are judging belong to a run, not to the company.
--
-- `codice_fiscale` deliberately carries no foreign key: a note about a company
-- is worth keeping even if that company later leaves the registry, and a write
-- from the dashboard must never fail on referential state.
-- ============================================================================

CREATE TABLE IF NOT EXISTS feedback (
    id              BIGSERIAL   PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    message         TEXT        NOT NULL
        CONSTRAINT feedback_message_is_reasonable
        CHECK (length(btrim(message)) BETWEEN 1 AND 4000),
    page            TEXT,
    codice_fiscale  CHAR(11),
    run_id          BIGINT      REFERENCES tag_runs(id),
    -- Kept for triage: a note that has been acted on stops appearing in
    -- `scripts/read_feedback.py --new`.
    handled_at      TIMESTAMPTZ
);

-- The only read pattern: newest first, optionally unhandled only.
CREATE INDEX IF NOT EXISTS feedback_created_idx ON feedback (created_at DESC);
