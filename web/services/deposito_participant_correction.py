"""Provenienza delle schede correggibili, senza deduplicare o modificare le parti."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def party_link_revision(parte: Any, soggetto: Any) -> str:
    payload = {"link": parte.to_dict(), "subject": soggetto.to_dict()}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def participant_correction_sources(parti: list, fascicolo_id: str) -> list[dict[str, str]]:
    rows = []
    for parte, soggetto in parti:
        sid = str(soggetto.id)
        rows.append({
            "linkId": str(parte.id), "subjectId": sid,
            "name": str(soggetto.nome_completo),
            "role": str(getattr(parte.ruolo, "label", parte.ruolo)),
            "taxCode": str(soggetto.codice_fiscale or soggetto.partita_iva or "").strip().upper(),
            "editHref": f"/soggetti/{sid}/modifica",
            "unlinkAction": f"/fascicoli/{fascicolo_id}/parti/{parte.id}/rimuovi",
            "revision": party_link_revision(parte, soggetto),
        })
    return rows
