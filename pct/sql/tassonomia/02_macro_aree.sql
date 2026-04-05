-- ============================================================
--  TASSONOMIA GIURIDICA — 02  MACRO_AREE (27)
--
--  Livello 2: branche del diritto all'interno di ciascuna Area.
--  Ogni macro-area è associata ai codici Cassazione e STOP-CNR
--  per allineamento con i registri statistici ufficiali.
--
--  Distribuzioni per Area:
--    GIU  (id=1) → CIV, LAV, FAM, AMM, TRB, PRE, PEN_CIV, IMM, PEN, SOC, MIG  (11)
--    STR  (id=2) → CONS, REC_STR, PAR                                            (3)
--    ADR  (id=3) → MED, NEG                                                       (2)
--    ESE  (id=4) → ESE_CIV, CRI                                                   (2)
--    VOL  (id=5) → VG_PROC                                                        (1)
--    ARB  (id=6) → ARB_PROC                                                       (1)
--    TEC  (id=7) → DIG, COM                                                       (2)
--    SPE  (id=8) → CONT, SUP, VAR                                                 (3)
--  Totale: 25 macro-aree + indice (copertura 100% NODE_CATALOG)
-- ============================================================

INSERT INTO macro_aree (id, codice, nome, area_id, codice_cassazione, codice_stop_cnr, descrizione, ordine) VALUES

-- ── Area GIU: Giudiziale ordinario ──────────────────────────
(101, 'CIV',     'Diritto Civile',                    1, '001-050', 'B03',
    'Obbligazioni, contratti, responsabilità, diritti reali', 1),
(102, 'LAV',     'Diritto del Lavoro',                1, '101-105', 'D01',
    'Rapporti subordinati, licenziamenti, retribuzioni, sindacato', 2),
(103, 'FAM',     'Diritto di Famiglia',               1, '051-055', 'B02',
    'Matrimonio, separazione, divorzio, minori, filiazione', 3),
(104, 'AMM',     'Diritto Amministrativo',            1, '181-203', 'E01',
    'Appalti, PA, accesso atti, TAR, Consiglio di Stato', 4),
(105, 'TRB',     'Diritto Tributario',                1, '204-215', 'E04',
    'Imposte dirette/indirette, accertamenti, contenzioso fiscale', 5),
(106, 'PRE',     'Previdenza & Assistenza',           1, '216-220', 'D03',
    'Pensioni, invalidità, INPS/INAIL, ricorsi previdenziali', 6),
(115, 'PEN_CIV', 'Diritto Penale (rif. civili)',      1, '154-180', 'F01',
    'Parte civile, risarcimento da reato, sequestri penali', 4),
(116, 'IMM',     'Diritto Immobiliare & Urbanistico', 1, '004',     'B04',
    'Compravendite, locazioni, usucapione, abusi edilizi, condoni', 5),

-- ── Area ESE: Esecuzione Forzata ────────────────────────────
(107, 'ESE_CIV', 'Esecuzioni Civili',                4, '301-310', 'C06',
    'Pignoramenti mobiliari/immobiliari/presso terzi, vendite', 1),
(108, 'CRI',     'Crisi d''Impresa / CCII',           4, '204',     'C07',
    'Composizione negoziata, concordato, liquidazione giudiziale', 2),

-- ── Area ADR: Composizione Assistita ────────────────────────
(109, 'MED',     'Mediazione Civile',                3, 'G01',     'G01',
    'Mediazione obbligatoria/facoltativa, organismi, omologhe', 1),
(110, 'NEG',     'Negoziazione Assistita',           3, 'G02',     'G02',
    'Convenzioni, accordi, omologhe familiari/civili', 2),

-- ── Area VOL: Volontaria Giurisdizione ──────────────────────
(112, 'VG_PROC', 'Volontaria Giurisdizione',         5,  NULL,     'C07',
    'Amministrazione di sostegno, interdizioni, inventari, autorizzazioni', 1),

-- ── Area ARB: Arbitrato ─────────────────────────────────────
(111, 'ARB_PROC','Arbitrato (Proc.)',                6, 'G03',     'G03',
    'Clausole, lodi, impugnazioni, esecutività', 1),

-- ── Area TEC: Legal Tech & Compliance ───────────────────────
(113, 'DIG',     'Diritto Digitale & Privacy',       7, '205',     'A04',
    'GDPR, data breach, cybersecurity, e-commerce, AI', 1),
(114, 'COM',     'Compliance Aziendale',             7, '208',     'E02',
    'Modelli 231, anticorruzione, whistleblowing, audit', 2),

-- ── Area GIU: nuove macro-aree ───────────────────────────────
(117, 'PEN',     'Diritto Penale',                   1, '154-180', 'F02',
    'Difesa imputato, indagini, udienza preliminare, dibattimento, impugnazioni, esecuzione penale, misure di prevenzione', 9),
(118, 'SOC',     'Diritto Societario & Commerciale', 1, '001-003', 'B05',
    'Società di capitali e persone, M&A, governance, impugnazione delibere, contratti commerciali, startup, joint venture', 10),
(119, 'MIG',     'Immigrazione & Cittadinanza',      1, NULL,      'E03',
    'Permessi soggiorno, cittadinanza, protezione internazionale, ricongiungimento familiare, espulsioni', 11),

-- ── Area STR: Stragiudiziale ─────────────────────────────────
(120, 'CONS',    'Consulenza & Contrattualistica',   2, NULL,      'A01',
    'Pareri legali, redazione contratti, revisione, assistenza trattative e transazioni', 1),
(121, 'REC_STR', 'Recupero crediti stragiudiziale',  2, NULL,      'C01',
    'Diffide, messe in mora, recupero bonario crediti e sinistri stradali', 2),
(122, 'PAR',     'Pareri e consulenze spot',         2, NULL,      'A02',
    'Pareri occasionali, primo inquadramento e consulenze tecniche di parte', 3),

-- ── Area SPE: Giurisdizioni e servizi speciali ───────────────
(123, 'CONT',    'Giustizia Contabile',              8, '301',     'H01',
    'Responsabilità erariale e pensionistica innanzi alla Corte dei Conti', 1),
(124, 'SUP',     'Giurisdizioni superiori',          8, '401',     'H02',
    'Corte Costituzionale, CEDU, CGUE, rinvii pregiudiziali europei', 2),
(125, 'VAR',     'Servizi professionali vari',       8, NULL,      'A99',
    'Domiciliazioni, attività a tempo, procedure particolari e incarichi speciali', 3)

ON CONFLICT (id) DO NOTHING;
