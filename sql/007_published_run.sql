-- ============================================================================
-- published_run — which tag run the dashboard shows.
--
-- Until now current_company_tags picked "the run with the newest finished_at",
-- so any run that finished — a 200-company benchmark, a recovery attempt —
-- silently replaced the full-registry view. Publishing is now an explicit
-- human step:
--
--     python scripts/publish_run.py --run-id 17
--
-- New file rather than an edit to 003_views.sql, because that file has
-- already been applied to the shared database. init_db.py runs this one
-- after it, so the view definition below is the one that stays in force.
-- ============================================================================

CREATE TABLE IF NOT EXISTS published_run (
    id            SMALLINT    PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- exactly one row
    run_id        BIGINT      NOT NULL REFERENCES tag_runs(id),
    published_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    note          TEXT
);

-- Seed once with the run the old rule would have shown, so applying this file
-- changes nothing on screen. ON CONFLICT DO NOTHING means re-running init_db.py
-- never moves the pointer; only publish_run.py does that.
INSERT INTO published_run (id, run_id, note)
SELECT 1, id, 'seeded by 007_published_run.sql from the newest finished run'
FROM tag_runs
WHERE finished_at IS NOT NULL
ORDER BY finished_at DESC
LIMIT 1
ON CONFLICT (id) DO NOTHING;

-- Same columns as before; only the choice of run changes.
CREATE OR REPLACE VIEW current_company_tags AS
SELECT t.*
FROM company_tags t
WHERE t.run_id = (SELECT run_id FROM published_run WHERE id = 1);
