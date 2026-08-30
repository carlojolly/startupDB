-- ============================================================================
-- Search indexes.
--
-- Split into its own file because 001_schema.sql had already been applied to
-- the shared database by the time these were added. Per the contributing
-- rules in the README: new schema goes in a new numbered file, never by
-- editing one people have already run.
--
-- These need pg_trgm, which 001_schema.sql installs. If that extension was
-- unavailable on your host, the DO block below skips the indexes rather than
-- failing the whole init.
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN

        -- Fuzzy company-name search. GIN + gin_trgm_ops makes both
        -- `ILIKE '%foo%'` and the similarity operators fast, which a plain
        -- B-tree index cannot do for a leading-wildcard match.
        CREATE INDEX IF NOT EXISTS companies_name_trgm_idx
            ON companies USING gin (latest_denominazione gin_trgm_ops);

        -- Same for the historical names on snapshots, so you can find a
        -- company by a name it used to have.
        CREATE INDEX IF NOT EXISTS snapshots_name_trgm_idx
            ON company_snapshots USING gin (denominazione gin_trgm_ops);

        -- Town names: useful for a "search by place" box.
        CREATE INDEX IF NOT EXISTS snapshots_comune_trgm_idx
            ON company_snapshots USING gin (comune gin_trgm_ops);
    ELSE
        RAISE NOTICE 'pg_trgm not installed - skipping trigram search indexes.';
    END IF;
END $$;

-- Plain B-tree for exact/prefix lookups on the denormalised current name.
CREATE INDEX IF NOT EXISTS companies_name_idx ON companies (latest_denominazione);
