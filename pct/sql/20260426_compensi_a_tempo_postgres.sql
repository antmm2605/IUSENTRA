-- Compenso a tempo ex art. 22-bis D.M. 55/2014
-- PostgreSQL: migrazione idempotente per repository preventivi/conferimenti.

ALTER TABLE preventivi_records
    ADD COLUMN IF NOT EXISTS criterio_arrotondamento_orario TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS minuti_stimati INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ore_fatturabili_calcolate DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS compenso_orario_base DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS massimale_ore DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS soglia_preapprovazione_ore DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS warning_compenso_orario_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE conferimenti_records
    ADD COLUMN IF NOT EXISTS criterio_arrotondamento_orario TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS massimale_ore DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS soglia_preapprovazione_ore DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS warning_compenso_orario_json TEXT NOT NULL DEFAULT '[]';
