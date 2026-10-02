"""Riutilizzo governato di una verifica fra copie testualmente identiche.

Non salva decisioni e non certifica notifiche. Usa solo identità prodotte dal
motore corrente, con atto e fonte immutati rispetto alla conferma registrata.
"""
from __future__ import annotations

import json
import re


def impronta_documento(documento) -> str:
    valore = str(getattr(documento, 'hash_sha256', '') or '').strip().lower()
    return valore if re.fullmatch(r'[0-9a-f]{64}', valore) else ''


def verifiche_per_atto(documenti: dict, identita: dict[str, str], verifiche: dict) -> tuple[dict, dict]:
    """Restituisce contesti utilizzabili e motivi espliciti delle revisioni.

    Una verifica storica senza impronte resta sul suo atto, ma non si propaga.
    Decisioni diverse restano autonome; nessuna scelta fra operatori.
    """
    valide, revisioni = {}, {}
    for oid, dati in verifiche.items():
        if oid not in documenti:
            continue
        fonte_id = str(dati.get('fonte_documento_id') or '')
        fonte = documenti.get(fonte_id)
        if fonte is None:
            revisioni[oid] = 'Il documento fonte della verifica non è più presente nel fascicolo.'
            continue
        if dati.get('atto_sha256') and dati['atto_sha256'] != impronta_documento(documenti[oid]):
            revisioni[oid] = 'L’atto è stato sostituito dopo la verifica: riesamina i dati sul documento attuale.'
            continue
        if dati.get('fonte_sha256') and dati['fonte_sha256'] != impronta_documento(fonte):
            revisioni[oid] = 'Il documento fonte è cambiato dopo la verifica: riesamina le date e le condizioni confermate.'
            continue
        valide[oid] = dict(dati, verifica_documento_id=oid)
    gruppi = {}
    for oid, dati in valide.items():
        if identita.get(oid) and dati.get('atto_sha256') and dati.get('fonte_sha256'):
            gruppi.setdefault(identita[oid], []).append((oid, dati))
    esito = dict(valide)
    for oid, impronta in identita.items():
        if oid in verifiche or oid not in documenti:
            continue
        candidati = gruppi.get(impronta, [])
        # L'identità dell'atto non autorizza a scegliere fra due decisioni.
        semantiche = {json.dumps({k: v for k, v in dati.items() if k not in {
            'revisione', 'atto_sha256', 'fonte_sha256', 'fonte_documento_id', 'verifica_documento_id'
        }}, sort_keys=True, ensure_ascii=False) for _, dati in candidati}
        if len(semantiche) > 1:
            revisioni[oid] = 'Le copie di questo atto hanno verifiche discordanti: confronta le fonti prima di confermare.'
        elif candidati:
            esito[oid] = dict(sorted(candidati, key=lambda item: item[0])[0][1])
    return esito, revisioni
