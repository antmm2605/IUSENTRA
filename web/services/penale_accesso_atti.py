"""Accesso agli atti del procedimento penale (art. 116 c.p.p.) nella sezione React del fascicolo.

La procedura esiste ed è collaudata nelle rotte classiche di
``web/bootstrap/fascicoli_pdp_routes.py`` (richiesta, generazione dell'atto,
PEC con la password, import del pacchetto scaricato, attività). Qui non si
riscrive nulla: la lettura usa lo stesso ``pdp_penale_build_workspace`` e ogni
azione chiama la stessa funzione di rotta nella richiesta corrente, poi
restituisce in JSON i messaggi che la rotta avrebbe mostrato.

Il link al fascicolo resta valido 3 giorni e la password arriva via PEC
all'indirizzo ReGIndE (manuale PDP, «Accesso agli atti»). Il deposito
diretto via REST della vecchia procedura non è esposto: il PDP non ha API,
il deposito si prepara nella sezione «Deposito penale».
"""

from __future__ import annotations

import json
from typing import Any

from flask import current_app, get_flashed_messages, request

from web.services import penale_pdp_contesto as contesto

# azione React -> (funzione di rotta classica, parametro identificativo)
AZIONI: dict[str, tuple[str, str]] = {
    "richiesta": ("pdp_penale_create_access_request", "case_id"),
    "genera-richiesta": ("pdp_penale_generate_access_request", "case_id"),
    "cerca-pec": ("pdp_penale_sync_pec", "case_id"),
    "registra-pec": ("pdp_penale_register_pec", "case_id"),
    "importa-scaricato": ("pdp_penale_import_download", "case_id"),
    "collega-documento": ("pdp_penale_link_local_document", "case_id"),
    "nuova-attivita": ("pdp_penale_create_task", "case_id"),
    "completa-attivita": ("pdp_penale_complete_task", "task_id"),
}

TIPI_RICHIESTA = [
    ("access_to_case_file", "Accesso al fascicolo"), ("document_copy_request", "Copia di atti"),
    ("supplementary_request", "Richiesta integrativa"), ("reissue_password", "Nuova password"), ("other", "Altro"),
]
STATI_RICHIESTA = [
    ("draft", "Bozza"), ("prepared", "Preparata"), ("submitted", "Depositata"), ("in_review", "In verifica"),
    ("authorized", "Autorizzata"), ("denied", "Respinta"), ("expired", "Scaduta"), ("downloaded", "Scaricata"),
    ("closed", "Chiusa"), ("technical_error", "Errore tecnico"),
]
RUOLI_DOCUMENTO = [
    ("nomination", "Nomina"), ("access_request", "Richiesta di accesso"), ("payment_receipt", "Ricevuta di pagamento"),
    ("legal_aid_order", "Ammissione al gratuito patrocinio"), ("decree", "Decreto"), ("ordinance", "Ordinanza"),
    ("judgment", "Sentenza"), ("hearing_minutes", "Verbale d'udienza"), ("defense_brief", "Memoria difensiva"),
    ("attachment", "Allegato"), ("other", "Altro"),
]
TIPI_ATTIVITA = [
    ("check_pec", "Controlla la PEC"), ("download_case_file", "Scarica il fascicolo"), ("import_documents", "Importa i documenti"),
    ("verify_documents", "Verifica i documenti"), ("wait_office_response", "Attendi l'ufficio"), ("manual_review", "Verifica dell'avvocato"),
    ("other", "Altro"),
]
PRIORITA = [("low", "Bassa"), ("medium", "Media"), ("high", "Alta"), ("urgent", "Urgente")]
_ETICHETTE = {c: e for elenco in (TIPI_RICHIESTA, STATI_RICHIESTA, RUOLI_DOCUMENTO, TIPI_ATTIVITA, PRIORITA) for c, e in elenco}


def _runtime(nome: str) -> Any:
    return current_app.extensions["application_runtime_bundle"].pdp_penale[nome]


def _etichetta(codice: Any) -> str:
    return _ETICHETTE.get(str(codice or ""), str(codice or "").replace("_", " "))


def _opzioni(elenco: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"valore": c, "etichetta": e} for c, e in elenco]


def _evento(riga: dict[str, Any]) -> dict[str, Any]:
    try:
        dati = json.loads(riga.get("payload_json") or "{}")
    except (TypeError, ValueError):
        dati = {}
    return {"id": riga["id"], "quando": riga.get("created_at") or "", "titolo": riga.get("title") or "",
            "descrizione": riga.get("description") or "", "fonte": riga.get("event_source") or "", "dati": dati}


def quadro(fid: str) -> dict[str, Any]:
    """Lo stato dell'accesso agli atti del fascicolo, senza percorsi del server."""
    fascicolo = contesto.fascicolo_penale(fid)
    caso = contesto.caso(fid)
    cliente = None
    if getattr(fascicolo, "id_cliente", ""):
        try:
            cliente = current_app.extensions["core_runtime"]["get_clienti"]().get(fascicolo.id_cliente)
        except Exception:
            cliente = None
    # Il workspace classico legge il caso attivo da ?case_id: la richiesta React lo passa uguale.
    if request.args.get("case_id") != caso["id"]:
        request.args = request.args.copy()
        request.args["case_id"] = caso["id"]  # type: ignore[index]
    ws = _runtime("pdp_penale_build_workspace")(fascicolo, cliente)
    return {
        "ok": True,
        "casoId": caso["id"],
        "checklist": [{"titolo": c.get("title", ""), "fatto": bool(c.get("done")), "tono": c.get("variant", ""),
                       "dettaglio": c.get("detail", "")} for c in ws["wizard_checklist"]],
        "download": {"stato": ws["download_state"], "finoAl": ws["download_available_until"],
                     "passwordDisponibile": bool(ws["password_available"])},
        "richieste": [{
            "id": r["id"], "tipo": _etichetta(r.get("request_type")), "stato": r.get("request_status") or "",
            "statoEtichetta": _etichetta(r.get("request_status")), "riferimento": r.get("request_reference") or "",
            "depositataIl": r.get("submitted_at") or "", "downloadFinoAl": r.get("download_available_until") or "",
            "pagamento": bool(r.get("payment_required")), "importo": r.get("payment_amount"),
            "gratuitoPatrocinio": bool(r.get("legal_aid_declared")), "note": r.get("notes") or "",
        } for r in ws["access_requests"]],
        "pec": [{
            "id": m["id"], "oggetto": m.get("subject") or "", "data": m.get("message_date") or m.get("received_at") or "",
            "mittente": m.get("sender") or "", "password": m.get("extracted_password") or "",
            "avvisoDownload": bool(m.get("contains_download_notice")),
        } for m in ws["pec_messages"]],
        "attivita": [{
            "id": t["id"], "titolo": t.get("title") or "", "tipo": _etichetta(t.get("task_type")),
            "priorita": t.get("priority") or "", "prioritaEtichetta": _etichetta(t.get("priority")),
            "scadenza": t.get("due_at") or "", "aperta": t.get("status") in {"open", "in_progress"},
            "descrizione": t.get("description") or "",
        } for t in ws["tasks"]],
        "documentiCollegati": [{
            "id": d["id"], "titolo": d.get("title") or "", "ruolo": _etichetta(d.get("document_role")),
            "fonte": d.get("source_type") or "", "firmato": bool(d.get("signed")), "documentoId": d.get("local_doc_id") or "",
            "quando": d.get("created_at") or "",
        } for d in ws["module_documents"]],
        "documentiFascicolo": [{
            "id": d["id"], "nome": d.get("nome") or "", "firmato": bool(d.get("firmato")),
            "ruoloSuggerito": d.get("role_suggestion") or "other",
        } for d in ws["local_documents"]],
        "cronologia": [_evento(e) for e in ws["events"][:30]],
        "opzioni": {"tipiRichiesta": _opzioni(TIPI_RICHIESTA), "statiRichiesta": _opzioni(STATI_RICHIESTA),
                    "ruoliDocumento": _opzioni(RUOLI_DOCUMENTO), "tipiAttivita": _opzioni(TIPI_ATTIVITA),
                    "priorita": _opzioni(PRIORITA)},
    }


def esegui(fid: str, azione: str, identificativo: str = "") -> dict[str, Any]:
    """Esegue l'azione con la rotta classica collaudata e ne restituisce i messaggi."""
    if azione not in AZIONI:
        raise ValueError("Azione non prevista per l'accesso agli atti.")
    contesto.fascicolo_penale(fid)
    endpoint, chiave = AZIONI[azione]
    valore = identificativo if chiave == "task_id" else contesto.caso(fid)["id"]
    if not valore:
        raise ValueError("Indica l'attività da completare.")
    get_flashed_messages()  # messaggi di altre pagine: non appartengono a questa azione
    current_app.view_functions[endpoint](id_fasc=fid, **{chiave: valore})
    messaggi = [{"tono": categoria, "testo": str(testo)} for categoria, testo in get_flashed_messages(with_categories=True)]
    errore = next((m["testo"] for m in messaggi if m["tono"] in {"danger", "error"}), "")
    if errore:
        raise ValueError(errore)
    return {"ok": True, "messaggi": messaggi}


__all__ = ["AZIONI", "esegui", "quadro"]
