-- ============================================================================
-- Record how each company's homepage text was obtained.
--
-- Until now this lived inside the free-text `evidence` column and had to be
-- recovered with a regex, which silently yields empty columns if that string's
-- format ever changes. Now that the pipeline has two fetch passes, which pass
-- produced the text is real data: it separates a JavaScript-rendered site from
-- a genuinely empty one.
--
-- New file rather than an edit to 001_schema.sql, because that file has
-- already been applied to the shared database.
-- ============================================================================

ALTER TABLE company_tags
    ADD COLUMN IF NOT EXISTS fetch_pass     TEXT,
    ADD COLUMN IF NOT EXISTS fetch_bucket   TEXT,
    ADD COLUMN IF NOT EXISTS homepage_chars INTEGER;

-- 'http'    — pass 1, plain HTTP, was enough
-- 'browser' — pass 2 rescued it: the page needs JavaScript to render
-- 'none'    — neither pass produced usable text
-- NULL      — rows from tag runs 2-4, which predate the two-pass fetch
DO $$
BEGIN
    ALTER TABLE company_tags
        ADD CONSTRAINT company_tags_fetch_pass_valid
        CHECK (fetch_pass IS NULL OR fetch_pass IN ('http', 'browser', 'none'));
EXCEPTION WHEN duplicate_object THEN
    NULL;  -- already applied
END $$;

CREATE INDEX IF NOT EXISTS company_tags_fetch_pass_idx
    ON company_tags (fetch_pass);
