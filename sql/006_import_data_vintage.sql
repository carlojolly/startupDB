-- ============================================================================
-- Record each import's data vintage: the newest registration date inside the
-- file, which is what the registry's export was current to.
--
-- Why it needs its own column rather than being derived from the snapshots:
-- an import of an unchanged file writes ZERO snapshot rows, so there would be
-- no record at all of what vintage was checked. Tracking it here answers
-- "has the registry actually refreshed since last time?" even on a no-op run,
-- and makes the export's publication lag visible over time.
-- ============================================================================

ALTER TABLE imports
    ADD COLUMN IF NOT EXISTS data_vintage DATE;

COMMENT ON COLUMN imports.data_vintage IS
    'Newest data iscrizione alla sezione startup in the file. The data''s own '
    'age, as opposed to file_modified_at (a filesystem timestamp that unzipping '
    'or copying resets) and imported_at (when we happened to run the import).';
