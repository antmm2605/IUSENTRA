"""Un messaggio alla volta: dalla PEC collegata con certezza ai documenti del fascicolo.

Il collegamento è certo solo se l'ultimo esito del linker è certificato (``LINK_STATI_CERTIFICATI``:
ruolo citato dall'ufficio, identificativi della ricevuta verificati, scelta manuale) oppure se l'avvocato
lo conferma (``conferma_collegamento``). Un collegamento solo proposto o automatico non salva nulla: il
messaggio resta «in attesa di conferma» nel registro del flusso.

Il filtro «PEC del fascicolo» resta quello del presidio (``pec_messages.linked_fascicolo_id`` con il suo
ultimo esito in ``pec_fascicolo_links``), lo stesso che usa la scheda del fascicolo
(``web/services/fascicolo_pec_presidio.messaggi_pec_per_fascicolo`` con ``solo_collegate``): nessun secondo
abbinatore per nome o ruolo.
"""

from __future__ import annotations

import json
import logging
import uuid
from email import message_from_bytes, policy
from pathlib import Path
from typing import Any, Callable

from pct.pec_fascicolo_documenti import classificazione as cl
from pct.pec_fascicolo_documenti import registro as reg
from pct.pec_fascicolo_documenti.salvataggio import (
    Provenienza, eml_presente, impronte_presenti, nome_eml, salva_allegato, salva_eml,
)
from pct.pec_pipeline import LINK_STATI_CERTIFICATI

logger = logging.getLogger(__name__)

#: Gli esiti del linker che rendono certo il collegamento PEC → fascicolo.
# «automatico»: il linker ha trovato coincidenti ruolo, cliente e ufficio (pct/pec_pipeline.decidi_collegamento).
# L'avvocato ha chiesto (02/11/2026) che i documenti delle PEC entrino nel fascicolo in modo del tutto automatico:
# anche questi collegamenti alimentano il fascicolo, con la provenienza scritta nel documento. Le sole «proposte»
# (identità incompleta o ambigua) restano in attesa della conferma.
STATI_COLLEGAMENTO_CERTI = frozenset(LINK_STATI_CERTIFICATI) | {"automatico"}

Eventi = Callable[[str, int, bool], None]
_SCHEMI_PRONTI: set[str] = set()


def _schema(repo: Any) -> None:
    chiave = str(Path(repo.db_path).resolve())
    if chiave in _SCHEMI_PRONTI:
        return
    with repo.connect() as conn:
        reg.prepara(conn)
    _SCHEMI_PRONTI.add(chiave)


def eventi_predefiniti(fascicolo_id: str, documenti_nuovi: int, pec_nuova: bool) -> None:
    """Registro delle letture: inventario del fascicolo e lettura in sfondo dei soli oggetti nuovi."""
    from pct.pec_pipeline import _notifica_documento_aggiunto, _notifica_pec_collegata

    if pec_nuova:
        _notifica_pec_collegata(fascicolo_id)
    if documenti_nuovi:
        _notifica_documento_aggiunto(fascicolo_id, None)


def _gestione_fascicoli(repo: Any) -> Any:
    from pct.fascicoli import GestioneFascicoli

    return GestioneFascicoli(
        db_path=str(repo.fascicoli_db_path),
        documents_dir=str(repo.fascicoli_docs_path or Path(repo.fascicoli_db_path).parent / "documenti"),
        studio_db=repo._studio_db_for_data_path(repo.fascicoli_db_path),
    )


def ultimo_collegamento(conn: Any, message_id: str) -> dict[str, Any]:
    """L'ultimo esito del linker per il messaggio (a parità di istante vale l'ultimo scritto)."""
    riga = conn.execute(
        "SELECT fascicolo_id, status, candidates_json FROM pec_fascicolo_links WHERE message_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (message_id,),
    ).fetchone()
    if not riga:
        return {}
    return {"fascicolo_id": riga["fascicolo_id"], "status": riga["status"], "candidates": json.loads(riga["candidates_json"] or "[]")}


def _letture(repo: Any, message_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    with repo.connect() as conn:
        riga = dict(repo.get_message_row(conn, message_id))
        collegamento = ultimo_collegamento(conn, message_id)
        versione = repo.latest_parsed_row(conn, message_id)
        report = repo.latest_report(conn, message_id)
    parsed = json.loads(versione["parsed_json"] or "{}") if versione else {}
    return riga, collegamento, parsed, report


def _provenienza(riga: dict[str, Any], parsed: dict[str, Any], message_id: str) -> Provenienza:
    from pct.pec_change_receipt import receipt_datetime_rome
    from pct.pec_pipeline import _field_date_value, ufficio_giudiziario_mittente

    intestazioni = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    mittenti = intestazioni.get("from") or []
    mittente = mittenti[0] if isinstance(mittenti, list) and mittenti else str(mittenti or "")
    consegna = receipt_datetime_rome(_field_date_value(parsed, "data_consegna"), riga.get("received_at"))
    return Provenienza(
        message_id=message_id,
        message_id_header=str(riga.get("message_id_header") or "")[:320],
        mittente=str(mittente)[:240],
        consegnata_il=consegna.isoformat(timespec="minutes") if consegna else "",
        da_ufficio=bool(ufficio_giudiziario_mittente(parsed)),
    )


def _tipo_ricevuta(repo: Any, parsed: dict[str, Any], report: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    profilo = repo._notification_receipt_profile(parsed, report)
    if profilo.get("skipped"):
        return "", {}
    tipo = profilo.get("kind")
    return str(getattr(tipo, "value", tipo) or ""), profilo


def processa_messaggio(repo: Any, message_id: str, *, fascicolo_id: str = "", conferma_avvocato: bool = False,
                       actor: str = "pec-fascicolo-documenti", eventi: Eventi | None = None) -> dict[str, Any]:
    """Salva nel fascicolo il contenuto utile della PEC; idempotente per Message-ID e impronta SHA-256."""
    _schema(repo)
    tenant = repo.tenant_id
    try:
        riga, collegamento, parsed, report = _letture(repo, message_id)
    except KeyError:
        return {"ok": True, "stato": "messaggio_non_trovato", "salvati": 0, "eml_salvati": 0}
    destinazione = str(fascicolo_id or riga.get("linked_fascicolo_id") or "")
    stato_link = str(collegamento.get("status") or "")
    certo = conferma_avvocato or (
        stato_link in STATI_COLLEGAMENTO_CERTI and str(collegamento.get("fascicolo_id") or "") == destinazione
    )
    with repo.connect() as conn:
        precedente = reg.stato_messaggio(conn, tenant, message_id)
        if not destinazione or not certo:
            if not destinazione and not collegamento.get("candidates"):
                return {"ok": True, "stato": "non_collegata", "collegamento": stato_link, "salvati": 0, "eml_salvati": 0}
            reg.registra_messaggio(conn, tenant, message_id, fascicolo_id=destinazione, stato="in_attesa_conferma",
                                   motivo=f"Collegamento «{stato_link or 'assente'}»: serve la conferma dell'avvocato")
            return {"ok": True, "stato": "in_attesa_conferma", "collegamento": stato_link, "salvati": 0, "eml_salvati": 0}
        # Un messaggio completato con regole precedenti si rivede: il salvataggio è idempotente per impronta.
        if (precedente.get("stato") == "completato" and precedente.get("fascicolo_id") == destinazione and not conferma_avvocato
                and precedente.get("versione_regole") == cl.VERSIONE):
            return {"ok": True, "stato": "gia_elaborato", "salvati": 0, "eml_salvati": 0}
    try:
        esito = _salva(repo, message_id, destinazione, riga, parsed, report, actor=actor)
    except Exception as exc:  # il collegamento e il presidio restano validi; il recupero riprova
        logger.warning("PEC %s non portata nel fascicolo %s: %s", message_id, destinazione, type(exc).__name__)
        with repo.connect() as conn:
            reg.registra_messaggio(conn, tenant, message_id, fascicolo_id=destinazione, stato="errore", motivo=type(exc).__name__)
        return {"ok": False, "stato": "errore", "errore": type(exc).__name__, "salvati": 0, "eml_salvati": 0}
    nuovi = esito["salvati"] + esito["eml_salvati"]
    try:
        (eventi or eventi_predefiniti)(destinazione, nuovi, conferma_avvocato or precedente.get("stato") != "completato")
    except Exception as exc:  # pragma: no cover - gli eventi non annullano il salvataggio
        logger.debug("Eventi del registro non inviati per %s: %s", destinazione, exc)
    return {"ok": True, "stato": "completato", "fascicolo_id": destinazione, **esito}


def _salva(repo: Any, message_id: str, destinazione: str, riga: dict[str, Any], parsed: dict[str, Any],
           report: dict[str, Any], *, actor: str) -> dict[str, Any]:
    tenant = repo.tenant_id
    raw = bytes(riga.get("original_mime") or b"")
    impronta_eml = str(riga.get("mime_sha256") or "").lower()
    intestazioni = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    oggetto = str(intestazioni.get("subject") or "")
    from pct.pec_pipeline import extract_message_parts

    _testo, _html, parti = extract_message_parts(message_from_bytes(raw, policy=policy.default))
    tipo_ricevuta, profilo = _tipo_ricevuta(repo, parsed, report)
    genere = cl.genere_messaggio(oggetto, [parte.filename for parte in parti], tipo_ricevuta)
    provenienza = _provenienza(riga, parsed, message_id)
    profilo_processuale = parsed.get("procedural_profile") if isinstance(parsed.get("procedural_profile"), dict) else {}
    # Il tipo del provvedimento allegato (sentenza, ordinanza…) si legge anche dall'evento della comunicazione.
    contesto = " ".join(str(v or "") for v in (oggetto, profilo_processuale.get("oggetto_evento"),
                                                 profilo_processuale.get("descrizione_evento")))
    base = {"tenant_id": tenant, "message_id": message_id, "fascicolo_id": destinazione,
            "message_id_header": provenienza.message_id_header, "mittente": provenienza.mittente,
            "consegnata_il": provenienza.consegnata_il}
    righe: list[dict[str, Any]] = []
    conteggi = {"salvati": 0, "eml_salvati": 0, "gia_presenti": 0, "scartati": 0, "genere": genere}
    if genere in {cl.RICEVUTA_DEPOSITO, cl.RICEVUTA_ALTRA}:
        motivo = "ricevuta_deposito_telematico" if genere == cl.RICEVUTA_DEPOSITO else "ricevuta_non_di_notifica"
        righe.append({**base, "ruolo": "messaggio", "nome_originale": "messaggio.eml", "sha256": impronta_eml,
                      "esito": "scartato", "motivo": motivo})
        conteggi["scartati"] = 1
        return _chiudi(repo, message_id, destinazione, righe, conteggi, actor=actor)
    if genere == cl.RICEVUTA_NOTIFICA:
        # Prima la riconciliazione del presidio notifiche (idempotente): se la ricevuta si abbina a una notifica
        # dello studio, l'.eml entra nel fascicolo come prova del destinatario per la sua strada.
        repo.reconcile_legal_notification_receipt(message_id, actor=actor)
    manager = _gestione_fascicoli(repo)
    fascicolo = manager.get(destinazione)
    if fascicolo is None:
        raise LookupError("fascicolo_non_trovato")
    presenti = impronte_presenti(fascicolo)
    with repo.connect() as conn:
        if cl.conserva_eml(genere, da_ufficio=provenienza.da_ufficio):
            nome = nome_eml(repo._notification_receipt_display_subject(profilo) if profilo else oggetto, genere)
            esistente = reg.esito_oggetto(conn, tenant, message_id, destinazione, impronta_eml).get("documento_id") or eml_presente(fascicolo, message_id, impronta_eml)
            documento_id, esito = esistente, "gia_presente"
            if not esistente:
                # Stesse righe della riconciliazione del presidio: la matrice delle prove le riconosce.
                etichetta = {"rac": "RAC", "rdac": "RdAC", "delivery_failure": "MANCATA_CONSEGNA"}.get(tipo_ricevuta, tipo_ricevuta)
                righe_ricevuta = [riga for riga in (
                    f"receipt_kind: {etichetta}", f"notification_id: {profilo.get('notification_id') or ''}",
                    f"sent_message_id: {profilo.get('original_message_id') or ''}",
                    f"pec_audit_message_id: {message_id}") if not riga.endswith(": ")] if profilo else []
                documento = salva_eml(manager, destinazione, raw, impronta_eml, provenienza, genere=genere, nome=nome,
                                      righe_ricevuta=righe_ricevuta, actor=actor, etichetta_ricevuta=etichetta if profilo else "")
                documento_id, esito = str(getattr(documento, "id", "") or ""), "salvato"
                conteggi["eml_salvati"] += 1
            else:
                conteggi["gia_presenti"] += 1
            presenti.setdefault(impronta_eml, documento_id)
            righe.append({**base, "ruolo": "eml", "nome_originale": nome, "sha256": impronta_eml, "esito": esito, "documento_id": documento_id})
        da_salvare, scarti = cl.scegli_allegati([(parte.filename, parte.data) for parte in parti], genere=genere)
        for scarto in [*cl.involucri(raw), *scarti]:
            righe.append({**base, "ruolo": "allegato", "nome_originale": scarto.nome, "sha256": scarto.sha256,
                          "esito": "scartato", "motivo": scarto.motivo})
            conteggi["scartati"] += 1
        for allegato in da_salvare:
            esistente = reg.esito_oggetto(conn, tenant, message_id, destinazione, allegato.sha256).get("documento_id") or presenti.get(allegato.sha256, "")
            if esistente:
                righe.append({**base, "ruolo": "allegato", "nome_originale": allegato.nome, "sha256": allegato.sha256,
                              "esito": "gia_presente", "motivo": "gia_nel_fascicolo", "documento_id": esistente})
                conteggi["gia_presenti"] += 1
                continue
            documento = salva_allegato(manager, destinazione, allegato, provenienza, oggetto=contesto, actor=actor)
            documento_id = str(getattr(documento, "id", "") or "")
            presenti[allegato.sha256] = documento_id
            righe.append({**base, "ruolo": "allegato", "nome_originale": allegato.nome, "sha256": allegato.sha256,
                          "esito": "salvato", "documento_id": documento_id})
            conteggi["salvati"] += 1
    return _chiudi(repo, message_id, destinazione, righe, conteggi, actor=actor)


def _chiudi(repo: Any, message_id: str, destinazione: str, righe: list[dict[str, Any]], conteggi: dict[str, Any], *, actor: str) -> dict[str, Any]:
    tenant = repo.tenant_id
    with repo.connect() as conn:
        reg.registra_oggetti(conn, righe)
        reg.registra_messaggio(conn, tenant, message_id, fascicolo_id=destinazione, stato="completato",
                               salvati=conteggi["salvati"], eml_salvati=conteggi["eml_salvati"], scartati=conteggi["scartati"],
                               versione_regole=cl.VERSIONE)
        if conteggi["salvati"] or conteggi["eml_salvati"]:
            # Evidenza nella catena di audit del presidio (hash concatenati): provenienza di ogni file salvato.
            repo.append_audit(conn, action="pec.fascicolo_documenti.salvati", resource_type="pec_message", resource_id=message_id,
                              payload={"fascicolo_id": destinazione, "genere": conteggi["genere"], "documenti": [
                                  {k: r.get(k, "") for k in ("ruolo", "nome_originale", "sha256", "documento_id", "consegnata_il", "message_id_header")}
                                  for r in righe if r["esito"] == "salvato"]}, actor=actor)
    return conteggi


def conferma_collegamento(repo: Any, message_id: str, fascicolo_id: str, *, actor: str = "avvocato",
                          eventi: Eventi | None = None) -> dict[str, Any]:
    """L'avvocato conferma il fascicolo della PEC: collegamento «manuale» e documenti nel fascicolo.

    Un collegamento già certificato verso un altro fascicolo non si sovrascrive: lo si dice e non si salva nulla.
    """
    from pct.pec_pipeline import canonical_json, iso_now

    fascicolo_id = str(fascicolo_id or "").strip()
    if not fascicolo_id:
        return {"ok": False, "stato": "fascicolo_mancante"}
    with repo.connect() as conn:
        repo.get_message_row(conn, message_id)
        ultimo = ultimo_collegamento(conn, message_id)
        collegato = str(ultimo.get("fascicolo_id") or "")
        if str(ultimo.get("status") or "") in STATI_COLLEGAMENTO_CERTI and collegato and collegato != fascicolo_id:
            return {"ok": False, "stato": "collegamento_certificato_ad_altro_fascicolo"}
        if not (str(ultimo.get("status") or "") in STATI_COLLEGAMENTO_CERTI and collegato == fascicolo_id):
            versione = repo.latest_parsed_row(conn, message_id)
            if versione is None:
                return {"ok": False, "stato": "pec_non_ancora_letta"}
            conn.execute(
                "INSERT INTO pec_fascicolo_links (id, message_id, parsed_version_id, fascicolo_id, score, status, seeds_json, "
                "candidates_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, message_id, versione["id"], fascicolo_id, 1.0, "manuale",
                 canonical_json({"conferma": actor}), canonical_json(ultimo.get("candidates") or []), iso_now()),
            )
            conn.execute("UPDATE pec_messages SET linked_fascicolo_id=?, linked_fascicolo_score=1.0, status='linked' WHERE tenant_id=? AND id=?",
                         (fascicolo_id, repo.tenant_id, message_id))
            repo.append_audit(conn, action="pec.fascicolo.confirmed", resource_type="pec_message", resource_id=message_id,
                              payload={"fascicolo_id": fascicolo_id, "stato_precedente": ultimo.get("status") or ""}, actor=actor)
    return processa_messaggio(repo, message_id, fascicolo_id=fascicolo_id, conferma_avvocato=True, actor=actor, eventi=eventi)


__all__ = ["STATI_COLLEGAMENTO_CERTI", "conferma_collegamento", "eventi_predefiniti", "processa_messaggio"]
