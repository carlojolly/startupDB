-- ============================================================================
-- Italian Innovative Startups registry — database schema
--
-- Design in one paragraph:
--   `companies`         = stable identity. One row per company, forever.
--   `company_snapshots` = append-only history. One row per observed change.
--   `imports`           = one row per CSV file we loaded (the audit log).
--   `ref_*`             = lookup tables that decode the registry's coded bands.
--   `company_tags` / `tag_runs` = LLM-generated labels, added later.
--
-- Safe to run more than once: every object uses IF NOT EXISTS.
-- ============================================================================

-- Trigram index support gives us fast fuzzy company-name search.
-- Wrapped in a DO block because some managed Postgres hosts restrict CREATE
-- EXTENSION; if it fails we carry on without it rather than aborting setup.
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
EXCEPTION WHEN insufficient_privilege OR feature_not_supported THEN
    RAISE NOTICE 'pg_trgm unavailable — fuzzy name search will fall back to LIKE.';
END $$;


-- ============================================================================
-- REFERENCE TABLES
-- These encode the legend that ships alongside the registry export. They turn
-- opaque codes ('A', '3') into values you can actually filter and sort on.
-- ============================================================================

-- Legend (1): revenue band for the most recent financial year.
CREATE TABLE IF NOT EXISTS ref_classe_produzione (
    code            CHAR(1) PRIMARY KEY,
    min_eur         BIGINT,          -- inclusive
    max_eur         BIGINT,          -- inclusive; NULL means "no upper bound"
    label_it        TEXT NOT NULL,
    sort_order      SMALLINT NOT NULL
);

-- Legend (2): headcount band.
CREATE TABLE IF NOT EXISTS ref_classe_addetti (
    code            CHAR(1) PRIMARY KEY,
    min_employees   INTEGER,
    max_employees   INTEGER,         -- NULL means "no upper bound"
    label_it        TEXT NOT NULL,
    sort_order      SMALLINT NOT NULL
);

-- Legend (3): share capital band.
CREATE TABLE IF NOT EXISTS ref_classe_capitale (
    code            SMALLINT PRIMARY KEY,
    min_eur         BIGINT,
    max_eur         BIGINT,          -- NULL means "no upper bound"
    label_it        TEXT NOT NULL,
    sort_order      SMALLINT NOT NULL
);

-- Legend (8): female / youth / foreign ownership prevalence.
-- Computed by the registry as [% share capital + % directors] / 2.
CREATE TABLE IF NOT EXISTS ref_prevalenza (
    code            TEXT PRIMARY KEY,
    min_pct_exclusive NUMERIC(5,2),  -- lower bound, exclusive
    max_pct_inclusive NUMERIC(5,2),  -- upper bound, inclusive
    label_it        TEXT NOT NULL,
    sort_order      SMALLINT NOT NULL
);

-- Province -> province name + region. The CSV has no region column, so this
-- table is what makes "show me every startup in Lombardia" possible.
CREATE TABLE IF NOT EXISTS ref_provincia (
    pv              CHAR(2) PRIMARY KEY,
    provincia       TEXT NOT NULL,
    regione         TEXT,
    macro_area      TEXT,            -- Nord-Ovest / Nord-Est / Centro / Sud / Isole
    is_legacy_code  BOOLEAN NOT NULL DEFAULT FALSE  -- e.g. FO before it became FC
);

-- ATECO 2-digit divisions. Self-populating: the importer upserts these from
-- the 'attivita' column, which always agrees with the numeric code.
-- Labels arrive truncated at ~57 chars from the source export.
CREATE TABLE IF NOT EXISTS ref_ateco_division (
    division        CHAR(2) PRIMARY KEY,
    section_letter  CHAR(1),         -- the 'J' in "J 62 PRODUZIONE DI SOFTWARE..."
    label_it        TEXT,
    label_is_truncated BOOLEAN NOT NULL DEFAULT TRUE
);


-- ============================================================================
-- IMPORTS — one row per CSV file processed.
-- The UNIQUE constraint on file_sha256 is what makes re-running the same file
-- a detectable no-op rather than a duplicate load.
-- ============================================================================
CREATE TABLE IF NOT EXISTS imports (
    id                  BIGSERIAL PRIMARY KEY,
    source_filename     TEXT        NOT NULL,
    file_sha256         CHAR(64)    NOT NULL UNIQUE,
    file_size_bytes     BIGINT,
    file_modified_at    TIMESTAMPTZ,
    imported_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Populated once the load finishes, so a crashed run is visibly incomplete.
    rows_in_file        INTEGER,
    rows_valid          INTEGER,
    rows_skipped        INTEGER,
    snapshots_inserted  INTEGER,
    companies_new       INTEGER,
    companies_delisted  INTEGER,
    completed_at        TIMESTAMPTZ,

    notes               TEXT
);


-- ============================================================================
-- COMPANIES — stable identity. One row per codice fiscale, for all time.
-- Deliberately narrow: only identity and lifecycle live here. Anything that
-- can change week to week belongs in company_snapshots.
-- ============================================================================
CREATE TABLE IF NOT EXISTS companies (
    codice_fiscale      CHAR(11) PRIMARY KEY
        CONSTRAINT codice_fiscale_is_11_digits CHECK (codice_fiscale ~ '^[0-9]{11}$'),

    -- Denormalised copy of the newest name. Snapshots hold the authoritative
    -- history; this exists so the future search UI can query one table.
    latest_denominazione TEXT,

    first_seen_import_id BIGINT REFERENCES imports(id),
    last_seen_import_id  BIGINT REFERENCES imports(id),
    first_seen_on        DATE NOT NULL,
    last_seen_on         DATE NOT NULL,

    -- FALSE once a company stops appearing in the newest import: it either
    -- aged out of the 5-year startup window, or was dissolved.
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    delisted_on          DATE,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS companies_is_active_idx  ON companies (is_active);
CREATE INDEX IF NOT EXISTS companies_last_seen_idx  ON companies (last_seen_on DESC);


-- ============================================================================
-- COMPANY_SNAPSHOTS — append-only. Never UPDATE, never DELETE.
-- A row is written only when a company is new, or when its content_hash
-- differs from its previous snapshot. So every row here is a real change.
-- ============================================================================
CREATE TABLE IF NOT EXISTS company_snapshots (
    id                  BIGSERIAL PRIMARY KEY,
    codice_fiscale      CHAR(11) NOT NULL REFERENCES companies(codice_fiscale),
    import_id           BIGINT   NOT NULL REFERENCES imports(id),

    -- SHA-256 over the meaningful business fields (not over raw_record, so
    -- cosmetic whitespace changes in the export don't create false churn).
    content_hash        CHAR(64) NOT NULL,
    observed_on         DATE     NOT NULL,   -- the date this import ran

    -- ---- identity & legal form -------------------------------------------
    denominazione       TEXT,
    natura_giuridica    TEXT,
    -- Derived from the company name: the registry gives no status column, so
    -- "IN LIQUIDAZIONE" / "IN SCIOGLIMENTO" in the name is the only signal.
    in_liquidazione     BOOLEAN NOT NULL DEFAULT FALSE,

    -- ---- geography --------------------------------------------------------
    pv                  CHAR(2) REFERENCES ref_provincia(pv),
    comune              TEXT,

    -- ---- key dates --------------------------------------------------------
    data_iscrizione_sezione_startup   DATE,
    data_iscrizione_registro_imprese  DATE,
    data_inizio_attivita              DATE,
    data_dichiarazione                DATE,

    -- ---- industry classification -----------------------------------------
    -- ateco_raw is kept verbatim: the source mixes 2/3/4/5/6-digit codes and
    -- the literal string 'NC'. Do NOT zero-pad it — short codes are genuinely
    -- coarser levels of the hierarchy, not truncated 6-digit ones.
    ateco_raw           TEXT,
    ateco_division      CHAR(2) REFERENCES ref_ateco_division(division),
    settore             TEXT,
    attivita_label      TEXT,

    -- ---- size bands (all nullable: the registry often leaves these blank) --
    classe_produzione   CHAR(1)  REFERENCES ref_classe_produzione(code),
    classe_addetti      CHAR(1)  REFERENCES ref_classe_addetti(code),
    classe_capitale     SMALLINT REFERENCES ref_classe_capitale(code),

    -- ---- qualifying criteria (legend 6) ----------------------------------
    -- Source encodes these as 'SI' or blank — never 'NO' — so blank is FALSE.
    req_ricerca_sviluppo      BOOLEAN NOT NULL DEFAULT FALSE, -- >=15% R&D spend
    req_personale_qualificato BOOLEAN NOT NULL DEFAULT FALSE, -- qualified team
    req_brevetto              BOOLEAN NOT NULL DEFAULT FALSE, -- patent/software

    -- ---- special designations --------------------------------------------
    vocazione_sociale                  BOOLEAN,  -- legend (5)
    alto_valore_tecnologico_energetico BOOLEAN,  -- legend (4)

    -- ---- ownership prevalence (legend 8) ---------------------------------
    prevalenza_femminile  TEXT REFERENCES ref_prevalenza(code),
    prevalenza_giovanile  TEXT REFERENCES ref_prevalenza(code),
    prevalenza_straniera  TEXT REFERENCES ref_prevalenza(code),

    -- ---- website ----------------------------------------------------------
    sito_internet_raw     TEXT,  -- exactly as published, warts and all
    sito_internet_url     TEXT,  -- normalised to https://... or NULL if unusable
    sito_internet_domain  TEXT,  -- bare domain, for grouping/dedup

    -- ---- escape hatch -----------------------------------------------------
    raw_record            JSONB NOT NULL,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- A company can appear at most once per import. Belt-and-braces against
    -- duplicates even if the importer is interrupted and retried.
    CONSTRAINT company_snapshots_one_per_import UNIQUE (codice_fiscale, import_id)
);

CREATE INDEX IF NOT EXISTS snapshots_cf_observed_idx ON company_snapshots (codice_fiscale, observed_on DESC);
CREATE INDEX IF NOT EXISTS snapshots_import_idx      ON company_snapshots (import_id);
CREATE INDEX IF NOT EXISTS snapshots_pv_idx          ON company_snapshots (pv);
CREATE INDEX IF NOT EXISTS snapshots_division_idx    ON company_snapshots (ateco_division);
CREATE INDEX IF NOT EXISTS snapshots_iscrizione_idx  ON company_snapshots (data_iscrizione_sezione_startup DESC);
CREATE INDEX IF NOT EXISTS snapshots_domain_idx      ON company_snapshots (sito_internet_domain);


-- ============================================================================
-- LLM TAGS
-- Tags describe what a company *does*, which changes far more slowly than the
-- registry data. So they attach to the company (stable identity), not to a
-- snapshot. Every tag records the run that produced it, so you can re-tag with
-- a better prompt and compare results instead of destroying the old ones.
-- ============================================================================
CREATE TABLE IF NOT EXISTS tag_runs (
    id              BIGSERIAL PRIMARY KEY,
    model           TEXT NOT NULL,        -- e.g. 'claude-opus-5'
    prompt_version  TEXT,                 -- your own label, e.g. 'v3-sector'
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    companies_tagged INTEGER,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS company_tags (
    id              BIGSERIAL PRIMARY KEY,
    codice_fiscale  CHAR(11) NOT NULL REFERENCES companies(codice_fiscale) ON DELETE CASCADE,
    run_id          BIGINT   NOT NULL REFERENCES tag_runs(id) ON DELETE CASCADE,

    -- tag_type groups tags into facets so the UI can offer separate filters:
    -- 'sector', 'business_model', 'technology', 'customer', 'stage', ...
    tag_type        TEXT NOT NULL,
    tag_value       TEXT NOT NULL,

    confidence      NUMERIC(3,2) CHECK (confidence BETWEEN 0 AND 1),
    -- What the model was shown, so a bad tag can be traced to a thin input.
    evidence        TEXT,
    source          TEXT NOT NULL DEFAULT 'llm' CHECK (source IN ('llm','manual','rule')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT company_tags_unique_per_run UNIQUE (codice_fiscale, run_id, tag_type, tag_value)
);

CREATE INDEX IF NOT EXISTS company_tags_cf_idx     ON company_tags (codice_fiscale);
CREATE INDEX IF NOT EXISTS company_tags_lookup_idx ON company_tags (tag_type, tag_value);
CREATE INDEX IF NOT EXISTS company_tags_run_idx    ON company_tags (run_id);
