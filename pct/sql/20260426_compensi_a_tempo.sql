-- Compenso a tempo ex art. 22-bis D.M. 55/2014
-- SQLite: eseguire in modo idempotente tramite repository/runtime che verifica le colonne esistenti.

ALTER TABLE preventivi_records ADD COLUMN criterio_arrotondamento_orario TEXT NOT NULL DEFAULT '';
ALTER TABLE preventivi_records ADD COLUMN minuti_stimati INTEGER NOT NULL DEFAULT 0;
ALTER TABLE preventivi_records ADD COLUMN ore_fatturabili_calcolate REAL NOT NULL DEFAULT 0;
ALTER TABLE preventivi_records ADD COLUMN compenso_orario_base REAL NOT NULL DEFAULT 0;
ALTER TABLE preventivi_records ADD COLUMN massimale_ore REAL NOT NULL DEFAULT 0;
ALTER TABLE preventivi_records ADD COLUMN soglia_preapprovazione_ore REAL NOT NULL DEFAULT 0;
ALTER TABLE preventivi_records ADD COLUMN warning_compenso_orario_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE conferimenti_records ADD COLUMN criterio_arrotondamento_orario TEXT NOT NULL DEFAULT '';
ALTER TABLE conferimenti_records ADD COLUMN massimale_ore REAL NOT NULL DEFAULT 0;
ALTER TABLE conferimenti_records ADD COLUMN soglia_preapprovazione_ore REAL NOT NULL DEFAULT 0;
ALTER TABLE conferimenti_records ADD COLUMN warning_compenso_orario_json TEXT NOT NULL DEFAULT '[]';
