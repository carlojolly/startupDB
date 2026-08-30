-- ============================================================================
-- Views. These exist so nobody building the frontend has to know how the
-- snapshot history works — they just SELECT from companies_current.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- companies_current — one row per company, carrying its most recent snapshot
-- with every coded band already decoded. This is the main read surface.
--
-- DISTINCT ON is Postgres-specific and does exactly what we need: sort by
-- company then newest-first, and keep the first row of each company group.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW companies_current AS
SELECT
    c.codice_fiscale,
    s.denominazione,
    s.natura_giuridica,
    s.in_liquidazione,
    c.is_active,
    c.first_seen_on,
    c.last_seen_on,
    c.delisted_on,

    -- geography, with the region the CSV never gave us
    s.pv,
    p.provincia,
    p.regione,
    p.macro_area,
    s.comune,

    -- dates
    s.data_iscrizione_sezione_startup,
    s.data_iscrizione_registro_imprese,
    s.data_inizio_attivita,
    s.data_dichiarazione,
    -- Age in the startup section. Note this can be negative for ~327 companies
    -- whose section date precedes their registry date (usually a re-registration
    -- after moving registered office) — filter those out if it matters.
    (CURRENT_DATE - s.data_iscrizione_sezione_startup) AS days_in_startup_section,

    -- industry
    s.ateco_raw,
    s.ateco_division,
    d.label_it            AS ateco_division_label,
    s.settore,
    s.attivita_label,

    -- size bands: raw code AND decoded bounds, so you can filter numerically
    s.classe_produzione,
    cp.label_it           AS classe_produzione_label,
    cp.min_eur            AS produzione_min_eur,
    cp.max_eur            AS produzione_max_eur,

    s.classe_addetti,
    ca.label_it           AS classe_addetti_label,
    ca.min_employees      AS addetti_min,
    ca.max_employees      AS addetti_max,

    s.classe_capitale,
    cc.label_it           AS classe_capitale_label,
    cc.min_eur            AS capitale_min_eur,
    cc.max_eur            AS capitale_max_eur,

    -- qualifying criteria
    s.req_ricerca_sviluppo,
    s.req_personale_qualificato,
    s.req_brevetto,
    (s.req_ricerca_sviluppo::int + s.req_personale_qualificato::int
        + s.req_brevetto::int) AS req_count,

    -- designations
    s.vocazione_sociale,
    s.alto_valore_tecnologico_energetico,

    -- ownership
    s.prevalenza_femminile,
    s.prevalenza_giovanile,
    s.prevalenza_straniera,

    -- web
    s.sito_internet_raw,
    s.sito_internet_url,
    s.sito_internet_domain,

    -- provenance: which import produced this view of the company
    s.import_id           AS latest_import_id,
    s.observed_on         AS latest_observed_on,
    s.id                  AS latest_snapshot_id
FROM companies c
JOIN LATERAL (
    SELECT * FROM company_snapshots cs
    WHERE cs.codice_fiscale = c.codice_fiscale
    ORDER BY cs.observed_on DESC, cs.id DESC
    LIMIT 1
) s ON TRUE
LEFT JOIN ref_provincia         p  ON p.pv       = s.pv
LEFT JOIN ref_ateco_division    d  ON d.division = s.ateco_division
LEFT JOIN ref_classe_produzione cp ON cp.code    = s.classe_produzione
LEFT JOIN ref_classe_addetti    ca ON ca.code    = s.classe_addetti
LEFT JOIN ref_classe_capitale   cc ON cc.code    = s.classe_capitale;


-- ---------------------------------------------------------------------------
-- company_change_log — every recorded change, newest first, with the previous
-- snapshot alongside it. Answers "what changed about this company, and when".
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW company_change_log AS
SELECT
    s.codice_fiscale,
    s.observed_on,
    s.import_id,
    s.denominazione,
    LAG(s.denominazione)     OVER w AS prev_denominazione,
    s.classe_produzione,
    LAG(s.classe_produzione) OVER w AS prev_classe_produzione,
    s.classe_addetti,
    LAG(s.classe_addetti)    OVER w AS prev_classe_addetti,
    s.classe_capitale,
    LAG(s.classe_capitale)   OVER w AS prev_classe_capitale,
    s.comune,
    LAG(s.comune)            OVER w AS prev_comune,
    s.sito_internet_url,
    LAG(s.sito_internet_url) OVER w AS prev_sito_internet_url,
    ROW_NUMBER()             OVER w AS snapshot_number
FROM company_snapshots s
WINDOW w AS (PARTITION BY s.codice_fiscale ORDER BY s.observed_on, s.id);


-- ---------------------------------------------------------------------------
-- current_company_tags — tags from the most recent tagging run only.
-- Older runs stay in company_tags so you can compare prompt versions.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW current_company_tags AS
SELECT t.*
FROM company_tags t
WHERE t.run_id = (SELECT id FROM tag_runs WHERE finished_at IS NOT NULL
                  ORDER BY finished_at DESC LIMIT 1);


-- ---------------------------------------------------------------------------
-- import_history — quick health check on the weekly loads.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW import_history AS
SELECT
    id, source_filename, imported_at, completed_at,
    rows_valid, rows_skipped, snapshots_inserted,
    companies_new, companies_delisted,
    CASE WHEN completed_at IS NULL THEN 'INCOMPLETE' ELSE 'ok' END AS status
FROM imports
ORDER BY imported_at DESC;
