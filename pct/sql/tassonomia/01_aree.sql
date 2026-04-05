-- ============================================================
--  TASSONOMIA GIURIDICA — 01  AREE (8)
--
--  Livello 1: macro-contenitori che raggruppano per natura
--  dell'attività professionale (giudiziale, stragiudiziale, ecc.).
--  Ogni area corrisponde a un "canale" procedurale distinto.
--
--  id  codice  nome
--   1  GIU     Giudiziale ordinario
--   2  STR     Stragiudiziale
--   3  ADR     ADR / Composizione Assistita
--   4  ESE     Esecuzione Forzata
--   5  VOL     Volontaria Giurisdizione
--   6  ARB     Arbitrato
--   7  TEC     Legal Tech & Compliance
--   8  SPE     Giurisdizioni e servizi speciali
-- ============================================================

INSERT INTO aree (id, codice, nome, descrizione, ordine) VALUES
(1, 'GIU', 'Giudiziale ordinario',
    'Contenzioso civile, penale, amministrativo, tributario e del lavoro innanzi alle giurisdizioni ordinarie.', 1),
(2, 'STR', 'Stragiudiziale',
    'Attività professionale fuori dal giudizio: pareri, contratti, trattative, recupero crediti, sinistri.', 2),
(3, 'ADR', 'ADR / Composizione Assistita',
    'Mediazione civile, negoziazione assistita e altre forme di risoluzione alternativa delle controversie.', 3),
(4, 'ESE', 'Esecuzione Forzata',
    'Procedimenti esecutivi mobiliari, immobiliari e presso terzi; crisi d''impresa e procedure concorsuali.', 4),
(5, 'VOL', 'Volontaria Giurisdizione',
    'Procedimenti non contenziosi: amministrazione di sostegno, tutela, curatela, autorizzazioni giudiziali.', 5),
(6, 'ARB', 'Arbitrato',
    'Arbitrato rituale e irrituale, clausole compromissorie, lodi arbitrali e loro impugnazione.', 6),
(7, 'TEC', 'Legal Tech & Compliance',
    'Diritto digitale, privacy (GDPR), compliance aziendale (D.Lgs. 231/2001), cybersecurity.', 7),
(8, 'SPE', 'Giurisdizioni e servizi speciali',
    'Corte dei Conti, Corte Costituzionale, CEDU, CGUE, giurisdizioni superiori e servizi professionali vari.', 8)

ON CONFLICT (id) DO NOTHING;
