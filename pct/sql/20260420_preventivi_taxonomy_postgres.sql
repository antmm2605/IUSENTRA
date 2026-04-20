ALTER TABLE preventivi_records
    ADD COLUMN IF NOT EXISTS classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE conferimenti_records
    ADD COLUMN IF NOT EXISTS classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]';
