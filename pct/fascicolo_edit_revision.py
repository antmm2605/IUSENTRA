"""Versione dei soli dati modificabili dal modulo principale del fascicolo.

Documenti, letture, incassi e attività in sfondo non sono campi del modulo:
il loro aggiornamento non deve bloccare inutilmente una modifica della nota.
Il confronto SQL del writer continua a proteggere la transazione completa.
"""
from __future__ import annotations

import hashlib
import json

EDIT_FIELDS = (
    'titolo', 'tipo', 'id_cliente', 'controparte', 'cf_controparte', 'tribunale',
    'numero_rg', 'anno_rg', 'giudice', 'sezione', 'ruolo_sezione', 'avvocato_controparte',
    'numero_attori', 'numero_convenuti', 'qualifica_giudiziale_titolare',
    'link_cartella_esterna', 'nome_gruppo', 'numero_cci', 'data_prima_udienza',
    'data_notifica_citazione', 'avvocato_referente', 'avvocato_dominus', 'oggetto',
    'valore_causa', 'valore_preventivato', 'tipo_procedimento', 'id_pratica', 'area_pratica',
    'procedura_operativa_codice', 'codice_oggetto_pst', 'fonte_codice_oggetto',
    'file_fonte_codice_oggetto', 'riferimento_cartaceo', 'attore_principale',
    'istruttore_pm_gip', 'cancelliere', 'ctu', 'ctp', 'stato_pratica_operativa',
    'testo_personalizzabile_1', 'testo_personalizzabile_2', 'personalizzabile',
    'data_apertura', 'data_chiusura', 'compenso_pattuito', 'note',
)


def edit_revision(source: dict, *, row: dict | None = None) -> str:
    row = row or {}
    values = {field: source[field] if field in source else row.get(field) for field in EDIT_FIELDS}
    raw = json.dumps({'id': source.get('id') or row.get('id'), 'values': values},
                     sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()
