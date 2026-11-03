"""Riconvalida notturna del collegamento certo delle notifiche L. 53/1994 al fascicolo (a lotti, registrata).

Gira nel recupero notturno delle PEC nei fascicoli (``web.services.pec_fascicolo_documenti_runtime``). Ogni
messaggio di notificazione o ricevuta si annota in ``pec_notifiche_l53_collegamenti`` con il fascicolo, la fonte
(``pct.notifiche_l53_collegamento.regola``), il destinatario riletto dal daticert e l'impronta dei dati che
decidono; un messaggio già annotato con la stessa impronta non si riesamina. Solo conteggi in uscita.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from pct.notifiche_l53_collegamento.daticert import daticert_dal_messaggio, destinatario_da_daticert
from pct.notifiche_l53_collegamento.regola import L53, VERSIONE_REGOLA, collega_tutti, notifica_id
from pct.notifiche_l53_collegamento.relata import lettura_con_relata, testi_dal_messaggio, ufficio_dal_testo

LIMITE_PREDEFINITO = 200
SCHEMA = """
CREATE TABLE IF NOT EXISTS pec_notifiche_l53_collegamenti (
    tenant_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL DEFAULT '',
    fonte TEXT NOT NULL DEFAULT '',
    motivo TEXT NOT NULL DEFAULT '',
    destinatario TEXT NOT NULL DEFAULT '',
    impronta TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, message_id)
);
"""


def messaggi_l53(conn: sqlite3.Connection, tenant_id: str) -> list[dict[str, Any]]:
    """Le PEC di notificazione L. 53/1994 e le loro ricevute (ultima lettura), senza il MIME."""
    righe = conn.execute(
        """
        SELECT m.id, m.message_id_header, m.mime_sha256, p.parsed_json FROM pec_messages m
        JOIN pec_parsed_versions p ON p.message_id = m.id
        WHERE m.tenant_id = ? AND p.version = (SELECT MAX(version) FROM pec_parsed_versions WHERE message_id = m.id)
          AND (p.parsed_json LIKE '%legge n. 53%' OR p.parsed_json LIKE '%legge n.53%' OR p.parsed_json LIKE '%otifica_ID%')
        """,
        (tenant_id,),
    ).fetchall()
    esito = []
    for riga in righe:
        try:
            parsed = json.loads(riga["parsed_json"] or "{}")
        except ValueError:
            continue
        intest = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
        if not L53.search(str(intest.get("subject") or "")):
            continue
        ricevuta = parsed.get("pec_receipt") if isinstance(parsed.get("pec_receipt"), dict) else {}
        esito.append({"id": str(riga["id"]), "message_id": str(riga["message_id_header"] or intest.get("message_id") or ""),
                      "sha256": str(riga["mime_sha256"] or ""), "oggetto": str(intest.get("subject") or ""), "originale": str(ricevuta.get("original_message_id") or ""),
                      "ricevuta": bool(ricevuta.get("type")), "indirizzo": str(ricevuta.get("recipient_address") or ""),
                      "parsed": parsed})
    return esito


def indice_notifica_id(fascicoli: list[Any]) -> dict[str, set]:
    """Codici Notifica_ID registrati nei documenti dei fascicoli (nome, note, etichette)."""
    indice: dict[str, set] = {}
    for fascicolo in fascicoli:
        for documento in getattr(fascicolo, "documenti", []) or []:
            testo = " ".join(str(getattr(documento, campo, "") or "") for campo in ("nome", "note", "descrizione"))
            testo += " " + " ".join(str(t) for t in (getattr(documento, "tags", []) or []))
            codice = notifica_id(testo)
            if codice:
                indice.setdefault(codice, set()).add(str(fascicolo.id))
    return indice


def indici_eml(conn: sqlite3.Connection, tenant_id: str, fascicoli: list[Any]) -> tuple[dict[str, set], dict[str, set]]:
    """Impronte e Message-ID degli .eml già nei fascicoli (documenti del fascicolo e registro del flusso PEC)."""
    impronte: dict[str, set] = {}
    message_id: dict[str, set] = {}
    for fascicolo in fascicoli:
        for documento in getattr(fascicolo, "documenti", []) or []:
            nome = str(getattr(documento, "nome_file", "") or getattr(documento, "nome", "") or "").casefold()
            if not nome.endswith(".eml"):
                continue
            for campo in ("hash_sha256", "hash_contenuto_sha256"):
                valore = str(getattr(documento, campo, "") or "").casefold()
                if valore:
                    impronte.setdefault(valore, set()).add(str(fascicolo.id))
    try:
        for riga in conn.execute("SELECT fascicolo_id, sha256, message_id_header FROM pec_fascicolo_documenti "
                                 "WHERE tenant_id=? AND documento_id<>'' AND lower(nome_originale) LIKE '%.eml'", (tenant_id,)):
            if riga["sha256"]:
                impronte.setdefault(str(riga["sha256"]).casefold(), set()).add(str(riga["fascicolo_id"]))
            if riga["message_id_header"]:
                message_id.setdefault(str(riga["message_id_header"]).strip("<>").casefold(), set()).add(str(riga["fascicolo_id"]))
    except sqlite3.Error:
        pass  # registro del flusso PEC non ancora creato
    return impronte, message_id


def certo_per(fascicoli: list[Any], leggi_mime=None):
    """I tre controlli sulla PEC e, se non bastano, sulla relata allegata con l'ufficio della relata."""
    from pct.pec_collegamento_certo import STATO_CERTO, _indice_bundle, cerca_collegamento_certo, chiave_ufficio

    def _certo(messaggio: dict[str, Any]) -> str:
        parsed = messaggio.get("parsed") or {}
        trovato = cerca_collegamento_certo(parsed, fascicoli)
        if trovato.get("stato") != STATO_CERTO and leggi_mime is not None:
            testi = testi_dal_messaggio(leggi_mime(messaggio["id"]))
            if testi:
                ufficio = ufficio_dal_testo(testi, _indice_bundle()[0], chiave_ufficio)
                trovato = cerca_collegamento_certo(lettura_con_relata(parsed, testi, ufficio), fascicoli)
        return str(trovato.get("fascicolo_id") or "") if trovato.get("stato") == STATO_CERTO else ""

    return _certo


def _lettore_mime(repo: Any):
    def _leggi(message_id: str) -> bytes:
        with repo.connect() as conn:
            riga = conn.execute("SELECT original_mime FROM pec_messages WHERE id=?", (message_id,)).fetchone()
        return bytes(riga[0] or b"") if riga else b""

    return _leggi


def _impronta(fascicoli: list[Any], impronte: dict, message_id: dict) -> str:
    from pct.pec_collegamento_certo_riconvalida import impronta_fascicoli

    base = [VERSIONE_REGOLA, impronta_fascicoli(fascicoli), str(sorted((k, sorted(v)) for k, v in impronte.items())),
            str(sorted((k, sorted(v)) for k, v in message_id.items()))]
    return hashlib.sha256("\n".join(base).encode("utf-8")).hexdigest()


def riconvalida_notifiche_l53(repo: Any, *, limite: int = LIMITE_PREDEFINITO, fascicoli: list[Any] | None = None) -> dict[str, Any]:
    """Un lotto: annota i messaggi nuovi o con impronta cambiata; restituisce solo conteggi."""
    if fascicoli is None:
        from pct.pec_fascicolo_documenti.flusso import _gestione_fascicoli

        fascicoli = list(_gestione_fascicoli(repo).tutti(archiviati=True))
    tenant = repo.tenant_id
    with repo.connect() as conn:
        conn.executescript(SCHEMA)
        messaggi = messaggi_l53(conn, tenant)
        impronte, message_id = indici_eml(conn, tenant, fascicoli)
        codici = indice_notifica_id(fascicoli)
        impronta = _impronta(fascicoli, impronte, {**message_id, **{"id:" + k: v for k, v in codici.items()}})
        registrati = {r[0]: r[1] for r in conn.execute("SELECT message_id, impronta FROM pec_notifiche_l53_collegamenti WHERE tenant_id=?", (tenant,))}
    da_fare = [m for m in messaggi if registrati.get(m["id"]) != impronta]
    conteggi = {"esaminati": 0, "collegati": 0, "non_certi": 0, "destinatari_riletti": 0, "documenti_salvati": 0,
                "gia_altrove": 0, "copie_pst": 0, "errori": 0}
    if not da_fare:
        return {"ok": True, **conteggi, "restano": 0}
    decisioni = collega_tutti(messaggi, indice_impronte=impronte, indice_message_id=message_id,
                              certo_per_messaggio=certo_per(fascicoli, _lettore_mime(repo)), indice_notifica_id=codici)
    adesso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for m in da_fare[: max(1, int(limite))]:
        decisione = decisioni.get(m["id"], {})
        destinatario = m["indirizzo"]
        try:
            if m["ricevuta"] and not destinatario:
                with repo.connect() as conn:
                    riga = conn.execute("SELECT original_mime FROM pec_messages WHERE id=?", (m["id"],)).fetchone()
                destinatario = destinatario_da_daticert(daticert_dal_messaggio(bytes(riga[0] or b"")) if riga else "")
                conteggi["destinatari_riletti"] += int(bool(destinatario))
        except Exception:  # noqa: BLE001 - MIME guasto: il collegamento si registra comunque
            conteggi["errori"] += 1
        conteggi["esaminati"] += 1
        conteggi["collegati" if decisione.get("fascicolo_id") else "non_certi"] += 1
        riuscito = True
        if decisione.get("fascicolo_id"):
            try:
                from web.services.notifiche_l53_applicazione_runtime import applica_collegamento

                effetto = applica_collegamento(repo, m["id"], decisione["fascicolo_id"], fonte=decisione.get("fonte", ""))
                conteggi["documenti_salvati"] += int(effetto.get("salvati") or 0) + int(effetto.get("eml_salvati") or 0)
                conteggi["gia_altrove"] += int(effetto.get("stato") == "certificato_ad_altro_fascicolo")
                riuscito = bool(effetto.get("ok", True))
            except Exception:  # noqa: BLE001 - senza impronta il messaggio torna in coda al giro dopo
                riuscito = False
            conteggi["errori"] += int(not riuscito)
        with repo.connect() as conn:
            conn.execute(
                "INSERT INTO pec_notifiche_l53_collegamenti VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id, message_id) DO UPDATE SET "
                "fascicolo_id=excluded.fascicolo_id, fonte=excluded.fonte, motivo=excluded.motivo, destinatario=excluded.destinatario, "
                "impronta=excluded.impronta, updated_at=excluded.updated_at",
                (tenant, m["id"], decisione.get("fascicolo_id", ""), decisione.get("fonte", ""), decisione.get("motivo", ""),
                 destinatario, impronta if riuscito else "", adesso),
            )
    try:
        from web.services.notifiche_l53_applicazione_runtime import registra_copie

        conteggi["copie_pst"] = registra_copie(repo, messaggi, decisioni)
    except Exception:  # noqa: BLE001
        conteggi["errori"] += 1
    return {"ok": conteggi["errori"] == 0, **conteggi, "restano": max(0, len(da_fare) - conteggi["esaminati"])}
