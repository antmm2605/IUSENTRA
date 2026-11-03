"""Effetti del collegamento certo di una notifica L. 53/1994: stato certificato, documenti nel fascicolo, copia PST.

Decisione dell'avvocato (03/11/2026): il collegamento ricavato da .eml, Notifica_ID, stesso invio o relata conta
come certo (``STATO_CERTIFICATO`` in ``pct.pec_pipeline.LINK_STATI_CERTIFICATI``); i documenti della notifica
(atto, relata, .eml, ricevute) si portano nel fascicolo con il flusso esistente (``pct/pec_fascicolo_documenti``,
senza doppioni per impronta); per i provvedimenti del giudice si prepara la voce «Copia originale da scaricare dal
PST» (``pct/notifiche_l53_collegamento/copia_originale``). Un collegamento certificato verso un altro fascicolo
non si tocca mai.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from pct.notifiche_l53_collegamento.copia_originale import voce_copia_originale
from pct.notifiche_l53_collegamento.regola import STATO_CERTIFICATO, chiave_invio
from pct.precedenti_notifica.categorie import tipo_atto

SCHEMA = """
CREATE TABLE IF NOT EXISTS pec_notifiche_l53_copie_pst (
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    invio TEXT NOT NULL,
    tipo_atto TEXT NOT NULL,
    impronte_json TEXT NOT NULL DEFAULT '[]',
    messaggi_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, fascicolo_id, invio)
);
"""
_NON_ATTO = re.compile(r"relata|procura|daticert|smime|postacert|attestazion|\.xml$|\.eml$", re.IGNORECASE)


def applica_collegamento(repo: Any, message_id: str, fascicolo_id: str, *, fonte: str, actor: str = "notifiche-l53") -> dict[str, Any]:
    """Collegamento certificato e documenti nel fascicolo; mai sopra un collegamento certificato altrove."""
    from pct.pec_fascicolo_documenti.flusso import STATI_COLLEGAMENTO_CERTI, processa_messaggio, ultimo_collegamento
    from pct.pec_pipeline import canonical_json, iso_now

    with repo.connect() as conn:
        ultimo = ultimo_collegamento(conn, message_id)
        collegato = str(ultimo.get("fascicolo_id") or "")
        certo = str(ultimo.get("status") or "") in STATI_COLLEGAMENTO_CERTI and bool(collegato)
        if certo and collegato != fascicolo_id:
            return {"ok": True, "stato": "certificato_ad_altro_fascicolo", "salvati": 0, "eml_salvati": 0}
        if not certo:
            versione = repo.latest_parsed_row(conn, message_id)
            if versione is None:
                return {"ok": True, "stato": "pec_non_ancora_letta", "salvati": 0, "eml_salvati": 0}
            conn.execute(
                "INSERT INTO pec_fascicolo_links (id, message_id, parsed_version_id, fascicolo_id, score, status, seeds_json, "
                "candidates_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, message_id, versione["id"], fascicolo_id, 1.0, STATO_CERTIFICATO,
                 canonical_json({"fonte": fonte}), canonical_json(ultimo.get("candidates") or []), iso_now()),
            )
            conn.execute("UPDATE pec_messages SET linked_fascicolo_id=?, linked_fascicolo_score=1.0, status='linked' WHERE tenant_id=? AND id=?",
                         (fascicolo_id, repo.tenant_id, message_id))
            repo.append_audit(conn, action="pec.fascicolo.notifica_l53", resource_type="pec_message", resource_id=message_id,
                              payload={"fascicolo_id": fascicolo_id, "fonte": fonte, "stato_precedente": ultimo.get("status") or ""}, actor=actor)
    return processa_messaggio(repo, message_id, fascicolo_id=fascicolo_id, actor=actor)


def registra_copie(repo: Any, messaggi: list[dict[str, Any]], decisioni: dict[str, dict[str, Any]]) -> int:
    """Per ogni invio collegato: tipo di atto e impronte dell'atto allegato (per la voce «Copia originale»)."""
    invii: dict[tuple[str, str], dict[str, Any]] = {}
    for m in messaggi:
        fascicolo = (decisioni.get(m["id"]) or {}).get("fascicolo_id")
        if not fascicolo:
            continue
        voce = invii.setdefault((fascicolo, chiave_invio(m)), {"nomi": [], "impronte": set(), "messaggi": []})
        voce["messaggi"].append(m["id"])
        for allegato in (m.get("parsed") or {}).get("attachments") or []:
            nome = str((allegato or {}).get("filename") or "")
            if nome and not _NON_ATTO.search(nome):
                voce["nomi"].append(nome)
                if allegato.get("sha256"):
                    voce["impronte"].add(str(allegato["sha256"]).casefold())
    adesso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with repo.connect() as conn:
        conn.executescript(SCHEMA)
        for (fascicolo, invio), voce in invii.items():
            conn.execute(
                "INSERT INTO pec_notifiche_l53_copie_pst VALUES (?,?,?,?,?,?,?) ON CONFLICT(tenant_id, fascicolo_id, invio) DO UPDATE SET "
                "tipo_atto=excluded.tipo_atto, impronte_json=excluded.impronte_json, messaggi_json=excluded.messaggi_json, updated_at=excluded.updated_at",
                (repo.tenant_id, fascicolo, invio, tipo_atto(voce["nomi"]), json.dumps(sorted(voce["impronte"])),
                 json.dumps(sorted(voce["messaggi"])), adesso),
            )
    return len(invii)


def copie_da_righe(conn: Any, tenant_id: str, fascicoli: dict[str, Any], righe: list[Any]) -> list[dict[str, Any]]:
    voci = []
    for riga in righe:
        fascicolo = fascicoli.get(str(riga["fascicolo_id"]))
        if fascicolo is None:
            continue
        messaggi = json.loads(riga["messaggi_json"] or "[]")
        segnaposti = ",".join("?" for _ in messaggi) or "''"
        try:
            dalla_pec = [r[0] for r in conn.execute(
                f"SELECT documento_id FROM pec_fascicolo_documenti WHERE tenant_id=? AND message_id IN ({segnaposti}) AND documento_id<>''",
                (tenant_id, *messaggi))]
        except Exception:  # noqa: BLE001 - registro del flusso non ancora creato
            dalla_pec = []
        voce = voce_copia_originale(fascicolo, tipo_atto=str(riga["tipo_atto"]), impronte_atto=json.loads(riga["impronte_json"] or "[]"),
                                    invio=str(riga["invio"]), documenti_dalla_pec=dalla_pec)
        if voce:
            voci.append(voce)
    return voci


def copie_pst(repo: Any, fascicoli: dict[str, Any], *, fascicolo_id: str = "", solo_da_scaricare: bool = False, limite: int = 100) -> list[dict[str, Any]]:
    """Le voci «Copia originale da scaricare dal PST» del fascicolo (o dello studio); lo stato si calcola ora."""
    try:
        with repo.connect() as conn:
            conn.executescript(SCHEMA)
            sql = "SELECT * FROM pec_notifiche_l53_copie_pst WHERE tenant_id=?" + (" AND fascicolo_id=?" if fascicolo_id else "")
            righe = conn.execute(sql + " ORDER BY updated_at DESC", (repo.tenant_id, *([fascicolo_id] if fascicolo_id else []))).fetchall()
            voci = copie_da_righe(conn, repo.tenant_id, fascicoli, righe)
    except Exception:  # noqa: BLE001 - la voce non blocca il pannello
        return []
    if solo_da_scaricare:
        voci = [v for v in voci if v["stato"] == "da_scaricare"]
    return voci[:limite]


def copie_pst_richiesta(*, fascicolo: Any = None, solo_da_scaricare: bool = False) -> list[dict[str, Any]]:
    """Le voci per la richiesta corrente (pannello del fascicolo o pagina Notifiche legali); mai bloccante."""
    try:
        from web.helpers import get_fascicoli
        from web.services.pec_pipeline_runtime import repository_for_current_request

        if fascicolo is not None:
            indice = {str(fascicolo.id): fascicolo}
        else:
            indice = {str(f.id): f for f in get_fascicoli().tutti()}
        return copie_pst(repository_for_current_request(), indice, fascicolo_id=str(getattr(fascicolo, "id", "") or ""),
                         solo_da_scaricare=solo_da_scaricare)
    except Exception:  # noqa: BLE001
        return []
