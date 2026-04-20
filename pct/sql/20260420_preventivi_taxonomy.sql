ALTER TABLE preventivi_records
    ADD COLUMN classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE conferimenti_records
    ADD COLUMN classificazioni_tassonomiche_json TEXT NOT NULL DEFAULT '[]';
