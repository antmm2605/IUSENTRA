"""Runtime dei precedenti di notifica dello studio: raccolta dal presidio PEC, memoria, annotazione delle proposte.

I precedenti si leggono dalle ricevute PEC già nel presidio (pec_audit.sqlite, sola lettura): ricevute di
avvenuta e mancata consegna di notificazioni L. 53/1994 collegate a un fascicolo, con il dominio del
destinatario come categoria. Il calcolo si registra in un file accanto al presidio con un'impronta
(ultimo messaggio e fascicoli): se nulla cambia non si ricalcola. Mai bloccante: in errore nessuna proposta.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from pct.precedenti_notifica.categorie import categoria_controparte, domicilio_da_indirizzo, tipo_atto
from pct.precedenti_notifica.regola import Precedente, proposta

logger = logging.getLogger(__name__)
VERSIONE = "1"
_L53 = re.compile(r"notificazione\s+ai\s+sensi\s+della\s+legge\s+n\.?\s*53|\[notifica_id:", re.IGNORECASE)


def _esito_ricevuta(tipo: str, oggetto: str) -> bool | None:
    v, o = str(tipo or "").casefold(), str(oggetto or "").casefold()
    if "errore" in v or "non-accett" in v or "non_accett" in v or "mancata" in v or o.startswith("avviso di mancata"):
        return False
    if "consegna" in v or o.startswith("consegna"):
        return True
    return None


def _collegamenti_l53(conn: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """Collegamento certo e destinatario riletto (web.services.notifiche_l53_collegamento_runtime), se registrati."""
    try:
        return {str(r[0]): (str(r[1] or ""), str(r[2] or "")) for r in conn.execute(
            "SELECT message_id, fascicolo_id, destinatario FROM pec_notifiche_l53_collegamenti")}
    except sqlite3.Error:
        return {}


def _righe(conn: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    return conn.execute(
        """
        SELECT m.id, m.folder, COALESCE(NULLIF(m.linked_fascicolo_id, ''), (SELECT l.fascicolo_id FROM pec_fascicolo_links l WHERE l.message_id = m.id ORDER BY l.created_at DESC, l.rowid DESC LIMIT 1), '') AS linked_fascicolo_id, m.received_at, p.parsed_json
        FROM pec_messages m JOIN pec_parsed_versions p ON p.message_id = m.id
        WHERE p.version = (SELECT MAX(version) FROM pec_parsed_versions WHERE message_id = m.id)
          AND (p.parsed_json LIKE '%legge n. 53%' OR p.parsed_json LIKE '%legge n.53%' OR p.parsed_json LIKE '%otifica_ID%')
        """
    )


def leggi_precedenti(conn: sqlite3.Connection, controparti: dict[str, str]) -> list[Precedente]:
    """Le notifiche consegnate o fallite dello studio, una per ricevuta (controparti: id fascicolo → nome)."""
    ricevute, allegati_invio, destinatari_invio = [], {}, {}
    collegati = _collegamenti_l53(conn)
    for riga in _righe(conn):
        try:
            parsed = json.loads(riga["parsed_json"] or "{}")
        except ValueError:
            continue
        intest = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
        oggetto = str(intest.get("subject") or "")
        if not _L53.search(oggetto):
            continue
        allegati = [str(a.get("filename") or "") for a in parsed.get("attachments") or [] if isinstance(a, dict)]
        ricevuta = parsed.get("pec_receipt") if isinstance(parsed.get("pec_receipt"), dict) else {}
        esito = _esito_ricevuta(str(ricevuta.get("type") or ""), oggetto)
        if esito is None:
            chiave = str(intest.get("message_id") or "").strip("<>").casefold()
            allegati_invio[chiave] = allegati
            destinatari_invio[chiave] = [str(a) for a in (intest.get("to") or []) if a] if isinstance(intest.get("to"), list) else []
            continue
        ricevute.append((riga, ricevuta, esito, allegati))
    precedenti = []
    for riga, ricevuta, esito, allegati in ricevute:
        certo = collegati.get(str(riga["id"]), ("", ""))
        fid = certo[0] or str(riga["linked_fascicolo_id"] or "")
        if not fid or fid not in controparti:
            continue
        originale = str(ricevuta.get("original_message_id") or "").strip("<>").casefold()
        indirizzo = str(ricevuta.get("recipient_address") or "") or certo[1]
        if not indirizzo and len(destinatari_invio.get(originale, [])) == 1:
            indirizzo = destinatari_invio[originale][0]  # ricevuta senza destinatario: l'unico dell'invio
        precedenti.append(Precedente(
            fascicolo_id=fid, prova_id=str(riga["id"]), data=str(riga["received_at"] or "")[:10],
            tipo_atto=tipo_atto(allegati_invio.get(originale, []) + allegati),
            categoria_controparte=categoria_controparte(controparti[fid]),
            domicilio=domicilio_da_indirizzo(indirizzo), consegnata=esito))
    return precedenti


def _impronta(conn: sqlite3.Connection, controparti: dict[str, str]) -> str:
    ultimo = conn.execute("SELECT COUNT(*), COALESCE(MAX(ingested_at), '') FROM pec_messages").fetchone()
    collegati = sorted(_collegamenti_l53(conn).items())
    base = json.dumps([VERSIONE, list(ultimo), collegati, sorted(controparti.items())], ensure_ascii=False)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def precedenti_memorizzati(db_path: Path, controparti: dict[str, str]) -> list[Precedente]:
    """I precedenti dal file di memoria se l'impronta non è cambiata, altrimenti ricalcolati e registrati."""
    if not db_path.exists():
        return []
    memoria = db_path.with_name("precedenti_notifica.json")
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        impronta = _impronta(conn, controparti)
        try:
            salvato = json.loads(memoria.read_text(encoding="utf-8"))
            if salvato.get("impronta") == impronta:
                return [Precedente(**voce) for voce in salvato.get("precedenti", [])]
        except (OSError, ValueError, TypeError):
            pass
        precedenti = leggi_precedenti(conn, controparti)
    try:
        memoria.write_text(json.dumps({"impronta": impronta, "precedenti": [p.__dict__ for p in precedenti]}, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.debug("Memoria dei precedenti non registrata: %s", exc)
    return precedenti


def annota_proposte(obblighi: list[dict[str, Any]], precedenti: list[Precedente], *, fascicolo_id: str) -> list[dict[str, Any]]:
    """Aggiunge a ogni destinatario la proposta dai precedenti (la regola normativa resta in «presso»)."""
    for obbligo in obblighi:
        atto = tipo_atto([str(obbligo.get("etichetta") or ""), str(obbligo.get("documento") or "")])
        for destinatario in obbligo.get("destinatari") or []:
            destinatario["precedenti"] = proposta(
                precedenti, tipo_atto=atto, categoria_controparte=categoria_controparte(destinatario.get("nome", "")),
                presso_normativo=str(destinatario.get("presso") or ""), fascicolo_id=fascicolo_id)
    return obblighi


def annota_fascicolo(fascicolo: Any, obblighi: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Punto d'ingresso per il fascicolo nella richiesta: mai bloccante."""
    try:
        from web.helpers import get_fascicoli
        from web.services.notification_presidia_runtime import _presidio_db_path

        controparti = {str(f.id): str(getattr(f, "controparte", "") or "") for f in get_fascicoli().tutti()}
        precedenti = precedenti_memorizzati(_presidio_db_path(), controparti)
        return annota_proposte(obblighi, precedenti, fascicolo_id=str(getattr(fascicolo, "id", "")))
    except Exception as exc:  # noqa: BLE001 - i precedenti non bloccano mai gli obblighi
        logger.warning("Precedenti di notifica non disponibili: %s", type(exc).__name__)
        return obblighi
