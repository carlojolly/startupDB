-- ============================================================================
-- Reference data: the registry's legend, encoded as lookup tables.
--
-- Source: the "Legenda" sheet published with the registry export. Encoding it
-- here is what lets you write `WHERE min_eur >= 1000000` instead of
-- `WHERE classe_produzione IN ('D','E','F','G','H')` and getting it wrong.
--
-- Every statement is an idempotent upsert: safe to re-run.
-- ============================================================================

-- ---- Legend (1): revenue band, most recent financial year ------------------
INSERT INTO ref_classe_produzione (code, min_eur, max_eur, label_it, sort_order) VALUES
    ('A',        0,      100000, '0 - 100.000 euro',                   1),
    ('B',   100001,      500000, '100.001 - 500.000 euro',             2),
    ('C',   500001,     1000000, '500.001 - 1.000.000 euro',           3),
    ('D',  1000001,     2000000, '1.000.001 - 2.000.000 euro',         4),
    ('E',  2000001,     5000000, '2.000.001 - 5.000.000 euro',         5),
    ('F',  5000001,    10000000, '5.000.001 - 10.000.000 euro',        6),
    ('G', 10000001,    50000000, '10.000.001 - 50.000.000 euro',       7),
    ('H', 50000001,        NULL, 'Piu di 50.000.000 euro',             8)
ON CONFLICT (code) DO UPDATE
    SET min_eur = EXCLUDED.min_eur, max_eur = EXCLUDED.max_eur,
        label_it = EXCLUDED.label_it, sort_order = EXCLUDED.sort_order;

-- ---- Legend (2): headcount band --------------------------------------------
INSERT INTO ref_classe_addetti (code, min_employees, max_employees, label_it, sort_order) VALUES
    ('A',   0,    4, '0-4 addetti',        1),
    ('B',   5,    9, '5-9 addetti',        2),
    ('C',  10,   19, '10-19 addetti',      3),
    ('D',  20,   49, '20-49 addetti',      4),
    ('E',  50,  249, '50-249 addetti',     5),
    ('F', 250, NULL, 'Almeno 250 addetti', 6)
ON CONFLICT (code) DO UPDATE
    SET min_employees = EXCLUDED.min_employees, max_employees = EXCLUDED.max_employees,
        label_it = EXCLUDED.label_it, sort_order = EXCLUDED.sort_order;

-- ---- Legend (3): share capital band ----------------------------------------
INSERT INTO ref_classe_capitale (code, min_eur, max_eur, label_it, sort_order) VALUES
    ( 1,       1,       1, '1 euro',                  1),
    ( 2,       1,    5000, 'Da 1 fino a 5mila euro',  2),
    ( 3,    5000,   10000, 'Da 5 a 10mila euro',      3),
    ( 4,   10000,   50000, 'Da 10 a 50mila euro',     4),
    ( 5,   50000,  100000, 'Da 50 a 100mila euro',    5),
    ( 6,  100000,  250000, 'Da 100 a 250mila euro',   6),
    ( 7,  250000,  500000, 'Da 250 a 500mila euro',   7),
    ( 8,  500000, 1000000, 'Da 500 a 1mln euro',      8),
    ( 9, 1000000, 2500000, 'Da 1 a 2,5mln euro',      9),
    (10, 2500000, 5000000, 'Da 2,5 a 5mln euro',     10),
    (11, 5000000,    NULL, 'Piu di 5 mln euro',      11)
ON CONFLICT (code) DO UPDATE
    SET min_eur = EXCLUDED.min_eur, max_eur = EXCLUDED.max_eur,
        label_it = EXCLUDED.label_it, sort_order = EXCLUDED.sort_order;

-- ---- Legend (8): female / youth / foreign prevalence ------------------------
-- Registry formula: [% share capital + % directors] / 2.
-- Bands are nested (Esclusiva is also Forte); the registry assigns the most
-- specific one, so treat these as mutually exclusive when filtering.
INSERT INTO ref_prevalenza (code, min_pct_exclusive, max_pct_inclusive, label_it, sort_order) VALUES
    ('NO',            0.00,  50.00, 'Fino al 50%',            1),
    ('Maggioritaria', 50.00,  66.00, 'Oltre il 50%',          2),
    ('Forte',         66.00,  99.99, 'Oltre il 66%',          3),
    ('Esclusiva',     99.99, 100.00, '100%',                  4)
ON CONFLICT (code) DO UPDATE
    SET min_pct_exclusive = EXCLUDED.min_pct_exclusive,
        max_pct_inclusive = EXCLUDED.max_pct_inclusive,
        label_it = EXCLUDED.label_it, sort_order = EXCLUDED.sort_order;

-- ---- Provinces -> region ----------------------------------------------------
-- The CSV has no region column; this table supplies it.
-- Includes provinces absent from the current file, plus the legacy codes the
-- registry still emits (FO for Forli-Cesena, PS for Pesaro e Urbino), so a
-- future export cannot fail the foreign key.
INSERT INTO ref_provincia (pv, provincia, regione, macro_area, is_legacy_code) VALUES
    ('AL','Alessandria','Piemonte','Nord-Ovest',FALSE),
    ('AT','Asti','Piemonte','Nord-Ovest',FALSE),
    ('BI','Biella','Piemonte','Nord-Ovest',FALSE),
    ('CN','Cuneo','Piemonte','Nord-Ovest',FALSE),
    ('NO','Novara','Piemonte','Nord-Ovest',FALSE),
    ('TO','Torino','Piemonte','Nord-Ovest',FALSE),
    ('VB','Verbano-Cusio-Ossola','Piemonte','Nord-Ovest',FALSE),
    ('VC','Vercelli','Piemonte','Nord-Ovest',FALSE),
    ('AO','Aosta','Valle d''Aosta','Nord-Ovest',FALSE),
    ('GE','Genova','Liguria','Nord-Ovest',FALSE),
    ('IM','Imperia','Liguria','Nord-Ovest',FALSE),
    ('SP','La Spezia','Liguria','Nord-Ovest',FALSE),
    ('SV','Savona','Liguria','Nord-Ovest',FALSE),
    ('BG','Bergamo','Lombardia','Nord-Ovest',FALSE),
    ('BS','Brescia','Lombardia','Nord-Ovest',FALSE),
    ('CO','Como','Lombardia','Nord-Ovest',FALSE),
    ('CR','Cremona','Lombardia','Nord-Ovest',FALSE),
    ('LC','Lecco','Lombardia','Nord-Ovest',FALSE),
    ('LO','Lodi','Lombardia','Nord-Ovest',FALSE),
    ('MB','Monza e della Brianza','Lombardia','Nord-Ovest',FALSE),
    ('MI','Milano','Lombardia','Nord-Ovest',FALSE),
    ('MN','Mantova','Lombardia','Nord-Ovest',FALSE),
    ('PV','Pavia','Lombardia','Nord-Ovest',FALSE),
    ('SO','Sondrio','Lombardia','Nord-Ovest',FALSE),
    ('VA','Varese','Lombardia','Nord-Ovest',FALSE),
    ('BZ','Bolzano','Trentino-Alto Adige','Nord-Est',FALSE),
    ('TN','Trento','Trentino-Alto Adige','Nord-Est',FALSE),
    ('BL','Belluno','Veneto','Nord-Est',FALSE),
    ('PD','Padova','Veneto','Nord-Est',FALSE),
    ('RO','Rovigo','Veneto','Nord-Est',FALSE),
    ('TV','Treviso','Veneto','Nord-Est',FALSE),
    ('VE','Venezia','Veneto','Nord-Est',FALSE),
    ('VI','Vicenza','Veneto','Nord-Est',FALSE),
    ('VR','Verona','Veneto','Nord-Est',FALSE),
    ('GO','Gorizia','Friuli-Venezia Giulia','Nord-Est',FALSE),
    ('PN','Pordenone','Friuli-Venezia Giulia','Nord-Est',FALSE),
    ('TS','Trieste','Friuli-Venezia Giulia','Nord-Est',FALSE),
    ('UD','Udine','Friuli-Venezia Giulia','Nord-Est',FALSE),
    ('BO','Bologna','Emilia-Romagna','Nord-Est',FALSE),
    ('FE','Ferrara','Emilia-Romagna','Nord-Est',FALSE),
    ('FC','Forli-Cesena','Emilia-Romagna','Nord-Est',FALSE),
    ('FO','Forli-Cesena','Emilia-Romagna','Nord-Est',TRUE),
    ('MO','Modena','Emilia-Romagna','Nord-Est',FALSE),
    ('PC','Piacenza','Emilia-Romagna','Nord-Est',FALSE),
    ('PR','Parma','Emilia-Romagna','Nord-Est',FALSE),
    ('RA','Ravenna','Emilia-Romagna','Nord-Est',FALSE),
    ('RE','Reggio Emilia','Emilia-Romagna','Nord-Est',FALSE),
    ('RN','Rimini','Emilia-Romagna','Nord-Est',FALSE),
    ('AR','Arezzo','Toscana','Centro',FALSE),
    ('FI','Firenze','Toscana','Centro',FALSE),
    ('GR','Grosseto','Toscana','Centro',FALSE),
    ('LI','Livorno','Toscana','Centro',FALSE),
    ('LU','Lucca','Toscana','Centro',FALSE),
    ('MS','Massa-Carrara','Toscana','Centro',FALSE),
    ('PI','Pisa','Toscana','Centro',FALSE),
    ('PO','Prato','Toscana','Centro',FALSE),
    ('PT','Pistoia','Toscana','Centro',FALSE),
    ('SI','Siena','Toscana','Centro',FALSE),
    ('PG','Perugia','Umbria','Centro',FALSE),
    ('TR','Terni','Umbria','Centro',FALSE),
    ('AN','Ancona','Marche','Centro',FALSE),
    ('AP','Ascoli Piceno','Marche','Centro',FALSE),
    ('FM','Fermo','Marche','Centro',FALSE),
    ('MC','Macerata','Marche','Centro',FALSE),
    ('PU','Pesaro e Urbino','Marche','Centro',FALSE),
    ('PS','Pesaro e Urbino','Marche','Centro',TRUE),
    ('FR','Frosinone','Lazio','Centro',FALSE),
    ('LT','Latina','Lazio','Centro',FALSE),
    ('RI','Rieti','Lazio','Centro',FALSE),
    ('RM','Roma','Lazio','Centro',FALSE),
    ('VT','Viterbo','Lazio','Centro',FALSE),
    ('AQ','L''Aquila','Abruzzo','Sud',FALSE),
    ('CH','Chieti','Abruzzo','Sud',FALSE),
    ('PE','Pescara','Abruzzo','Sud',FALSE),
    ('TE','Teramo','Abruzzo','Sud',FALSE),
    ('CB','Campobasso','Molise','Sud',FALSE),
    ('IS','Isernia','Molise','Sud',FALSE),
    ('AV','Avellino','Campania','Sud',FALSE),
    ('BN','Benevento','Campania','Sud',FALSE),
    ('CE','Caserta','Campania','Sud',FALSE),
    ('NA','Napoli','Campania','Sud',FALSE),
    ('SA','Salerno','Campania','Sud',FALSE),
    ('BA','Bari','Puglia','Sud',FALSE),
    ('BT','Barletta-Andria-Trani','Puglia','Sud',FALSE),
    ('BR','Brindisi','Puglia','Sud',FALSE),
    ('FG','Foggia','Puglia','Sud',FALSE),
    ('LE','Lecce','Puglia','Sud',FALSE),
    ('TA','Taranto','Puglia','Sud',FALSE),
    ('MT','Matera','Basilicata','Sud',FALSE),
    ('PZ','Potenza','Basilicata','Sud',FALSE),
    ('CS','Cosenza','Calabria','Sud',FALSE),
    ('CZ','Catanzaro','Calabria','Sud',FALSE),
    ('KR','Crotone','Calabria','Sud',FALSE),
    ('RC','Reggio Calabria','Calabria','Sud',FALSE),
    ('VV','Vibo Valentia','Calabria','Sud',FALSE),
    ('AG','Agrigento','Sicilia','Isole',FALSE),
    ('CL','Caltanissetta','Sicilia','Isole',FALSE),
    ('CT','Catania','Sicilia','Isole',FALSE),
    ('EN','Enna','Sicilia','Isole',FALSE),
    ('ME','Messina','Sicilia','Isole',FALSE),
    ('PA','Palermo','Sicilia','Isole',FALSE),
    ('RG','Ragusa','Sicilia','Isole',FALSE),
    ('SR','Siracusa','Sicilia','Isole',FALSE),
    ('TP','Trapani','Sicilia','Isole',FALSE),
    ('CA','Cagliari','Sardegna','Isole',FALSE),
    ('NU','Nuoro','Sardegna','Isole',FALSE),
    ('OR','Oristano','Sardegna','Isole',FALSE),
    ('SS','Sassari','Sardegna','Isole',FALSE),
    ('SU','Sud Sardegna','Sardegna','Isole',FALSE)
ON CONFLICT (pv) DO UPDATE
    SET provincia = EXCLUDED.provincia, regione = EXCLUDED.regione,
        macro_area = EXCLUDED.macro_area, is_legacy_code = EXCLUDED.is_legacy_code;
