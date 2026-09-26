"""La vista «Provenienza» del fascicolo: ogni uscita AI, chi l'ha prodotta e chi l'ha approvata.

Raccoglie, senza chiedere nulla a un modello, i record di provenienza già
scritti dal gestionale (`pct.provenienza_ai.Provenienza`):

- la seconda lettura del catalogo documentale (metadati della catalogazione);
- le bozze dell'editor AI (eventi `editor_ai.generation.completed`).

Per ogni uscita espone il modello, la versione delle regole, l'esito del
cancello (voce del catalogo chiuso, citazione ritrovata nel documento, valori
ancorati), l'approvazione dell'avvocato, il sigillo con la verifica di
integrità e, se il presidio probatorio è attivo, l'evento della catena
(`AI_OUTPUT_RECORDED` / `AI_OUTPUT_REVIEWED`).

Base normativa: artt. 12, 13 e 14 Reg. UE 2024/1689 (registrazione,
trasparenza e sorveglianza umana dei sistemi di AI); art. 20 CAD (integrità
del documento informatico).
"""

from __future__ import annotations

import logging
from typing import Any

from pct.provenienza_ai import verifica_sigillo

logger = logging.getLogger(__name__)

AZIONI = {
    "catalogo.seconda_lettura": "Seconda lettura del catalogo",
    "editor.bozza": "Bozza dell'editor AI",
    "pec.profilo": "Profilo processuale della PEC",
}


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _modello_leggibile(modello: str) -> str:
    modello = _testo(modello)
    if not modello or modello in {"non indicato", "generatore-configurato"}:
        return "Modello non indicato"
    if modello == "bozza-strutturata-senza-modello":
        return "Nessun modello (bozza strutturata dalle regole)"
    return modello.split("/")[-1]


def _cancello(provenienza: dict[str, Any]) -> dict[str, Any]:
    cancello = dict(provenienza.get("cancello") or {})
    controlli = [
        {"campo": _testo(c.get("campo")), "valore": _testo(c.get("valore"))[:120], "esito": _testo(c.get("esito")), "motivo": _testo(c.get("motivo"))}
        for c in list(cancello.get("controlli") or []) if isinstance(c, dict)
    ]
    if not controlli:
        return {"stato": "non_applicabile", "etichetta": "Nessun valore da ancorare", "controlli": []}
    bloccati = [c for c in controlli if c["esito"] == "bloccato"]
    return {
        "stato": "bloccato" if bloccati else "ammesso",
        "etichetta": ("1 valore bloccato dal cancello" if len(bloccati) == 1 else f"{len(bloccati)} valori bloccati dal cancello")
        if bloccati else "Tutti i valori ancorati alla fonte",
        "controlli": controlli,
    }


def _voce(
    provenienza: dict[str, Any], *, oggetto: str, oggetto_id: str, approvazione: str, approvazione_etichetta: str,
    proposta: str = "", attuale: str = "", esito: str = "",
) -> dict[str, Any]:
    azione = _testo(provenienza.get("azione"))
    return {
        "sigillo": _testo(provenienza.get("sigillo")),
        "azione": azione,
        "azioneEtichetta": AZIONI.get(azione, azione or "Uscita AI"),
        "modello": _testo(provenienza.get("modello")),
        "modelloEtichetta": _modello_leggibile(provenienza.get("modello")),
        "versioneRegole": _testo(provenienza.get("versione_regole")),
        "impronta": _testo(provenienza.get("sha256_input"))[:16],
        "citazione": _testo(provenienza.get("citazione"))[:240],
        "creatoIl": _testo(provenienza.get("creato_il")),
        "oggetto": oggetto,
        "oggettoId": oggetto_id,
        "proposta": proposta,
        "attuale": attuale,
        "esito": esito,
        "cancello": _cancello(provenienza),
        "approvazione": approvazione,
        "approvazioneEtichetta": approvazione_etichetta,
        "integro": verifica_sigillo(provenienza),
        "catena": {"registrato": False, "rivisto": False, "evento": ""},
    }


def _dal_catalogo(tenant_id: str, fascicolo_id: str, nomi: dict[str, str]) -> list[dict[str, Any]]:
    try:
        from web.services.document_intelligence_runtime import build_document_ai_service

        assegnazioni = build_document_ai_service().repository.list_catalog_assignments(tenant_id, fascicolo_id)
    except Exception:
        logger.debug("Catalogo non disponibile per la provenienza di %s", fascicolo_id, exc_info=True)
        return []
    voci: list[dict[str, Any]] = []
    for assegnazione in assegnazioni:
        lettura = dict((assegnazione.metadata or {}).get("lex_lettura") or {})
        provenienza = dict(lettura.get("provenienza") or {})
        if not provenienza.get("sigillo"):
            continue
        proposta = _testo(lettura.get("etichetta"))
        attuale = _testo(assegnazione.document_label)
        stato = _testo(assegnazione.status)
        if stato == "confirmed" and proposta and attuale.casefold() != proposta.casefold():
            approvazione, etichetta = "corretta", "Corretta dall'avvocato"
        elif stato == "confirmed":
            approvazione, etichetta = "confermata", "Confermata dall'avvocato"
        elif stato == "rejected":
            approvazione, etichetta = "respinta", "Respinta dall'avvocato"
        else:
            approvazione, etichetta = "da_approvare", "Da approvare"
        esito = {
            "scelta": "Voce proposta con la frase del documento",
            "nessuna": "Nessuna voce del catalogo: resta la proposta delle regole",
            "errore": "Voce fuori dal catalogo chiuso o risposta non valida: scartata",
            "non_verificata": "Frase non trovata nel documento: risposta scartata",
            "senza_testo": "Documento senza testo leggibile",
        }.get(_testo(lettura.get("esito")), _testo(lettura.get("motivo")) or _testo(lettura.get("esito")))
        documento_id = _testo(assegnazione.document_id)
        voci.append(_voce(
            provenienza, oggetto=nomi.get(documento_id) or _testo((assegnazione.metadata or {}).get("filename")) or "Documento",
            oggetto_id=documento_id, approvazione=approvazione, approvazione_etichetta=etichetta,
            proposta=proposta, attuale=attuale, esito=esito,
        ))
    return voci


def _dall_editor(tenant_id: str, fascicolo_id: str) -> list[dict[str, Any]]:
    try:
        from web.services.editor_ai_runtime import build_editor_ai_service, editor_ai_tenant_id

        repository = build_editor_ai_service().repository
        tenant_id = editor_ai_tenant_id() or tenant_id
        eventi = repository.list_audit_events(tenant_id, fascicolo_id, event_types=("editor_ai.generation.completed",))
        stati = {record.id: record for record in repository.list_records(tenant_id, fascicolo_id)}
    except Exception:
        logger.debug("Editor AI non disponibile per la provenienza di %s", fascicolo_id, exc_info=True)
        return []
    voci: list[dict[str, Any]] = []
    for evento in eventi:
        provenienza = dict((evento.get("payload") or {}).get("provenienza") or {})
        if not provenienza.get("sigillo"):
            continue
        record = stati.get(_testo(evento.get("atto_ai_id")))
        stato = _testo(getattr(record, "status", ""))
        if stato in {"approved", "exported"}:
            approvazione, etichetta = "confermata", "Approvata dall'avvocato"
        elif stato == "archived":
            approvazione, etichetta = "respinta", "Archiviata"
        else:
            approvazione, etichetta = "da_approvare", "Da rivedere nell'editor"
        titolo = _testo(getattr(record, "title", "")) or _testo(getattr(record, "tipo_atto", "")) or "Bozza"
        voci.append(_voce(
            provenienza, oggetto=titolo, oggetto_id=_testo(evento.get("atto_ai_id")),
            approvazione=approvazione, approvazione_etichetta=etichetta,
            esito=_testo((provenienza.get("parametri") or {}).get("tipo_atto")),
        ))
    return voci


def _con_catena(tenant_id: str, fascicolo_id: str, voci: list[dict[str, Any]]) -> dict[str, Any]:
    """Gli eventi della catena probatoria per sigillo, se il presidio è attivo."""
    try:
        from flask import current_app

        from audit.service import AuditService, audit_config_diagnostics

        if not audit_config_diagnostics(current_app.config).get("ready"):
            return {"attiva": False, "messaggio": "Catena probatoria non attiva su questa installazione: la provenienza resta nei metadati sigillati."}
        servizio = current_app.extensions.get("legal_audit_service")
        if not isinstance(servizio, AuditService):
            servizio = AuditService.from_config(current_app.config)
        righe = servizio.repository.list_events(tenant_id=tenant_id, fascicolo_id=fascicolo_id, limit=1000)
    except Exception:
        return {"attiva": False, "messaggio": "Catena probatoria non raggiungibile: la provenienza resta nei metadati sigillati."}
    per_chiave = {str(r.get("idempotency_key") or ""): r for r in righe}
    for voce in voci:
        registrato = per_chiave.get(f"AI_OUTPUT_RECORDED:{voce['sigillo']}")
        rivisto = any(chiave.startswith(f"AI_OUTPUT_REVIEWED:{voce['sigillo']}:") for chiave in per_chiave)
        voce["catena"] = {"registrato": bool(registrato), "rivisto": rivisto,
                          "evento": str((registrato or {}).get("event_hash") or "")[:16]}
    return {"attiva": True, "messaggio": ""}


def provenienze_fascicolo(fascicolo: Any) -> dict[str, Any]:
    """Tutte le uscite AI del fascicolo, dalla più recente."""
    from web.services.document_intelligence_runtime import document_ai_tenant_id

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    tenant_id = document_ai_tenant_id()
    nomi = {_testo(getattr(d, "id", "")): _testo(getattr(d, "nome", "")) for d in list(getattr(fascicolo, "documenti", []) or [])}
    voci = _dal_catalogo(tenant_id, fascicolo_id, nomi) + _dall_editor(tenant_id, fascicolo_id)
    voci.sort(key=lambda voce: voce["creatoIl"], reverse=True)
    catena = _con_catena(tenant_id, fascicolo_id, voci) if voci else {"attiva": False, "messaggio": ""}
    riepilogo = {
        "totale": len(voci),
        "daApprovare": sum(1 for v in voci if v["approvazione"] == "da_approvare"),
        "bloccate": sum(1 for v in voci if v["cancello"]["stato"] == "bloccato"),
        "nonIntegre": sum(1 for v in voci if not v["integro"]),
        "modelli": sorted({v["modelloEtichetta"] for v in voci}),
    }
    return {"voci": voci, "riepilogo": riepilogo, "catena": catena}


def registra_uscita(fascicolo_id: str, provenienza: dict[str, Any], *, oggetto: str = "", tenant_id: str = "") -> None:
    """Porta l'uscita nella catena probatoria (se attiva). Non interrompe mai il flusso che la chiama."""
    try:
        from audit.integrations import emit_ai_output_recorded

        emit_ai_output_recorded(fascicolo_id=fascicolo_id, provenienza=provenienza, oggetto=oggetto, tenant_id=tenant_id)
    except Exception:
        logger.warning("Uscita AI non registrata nella catena probatoria del fascicolo %s", fascicolo_id, exc_info=True)


def registra_revisione(fascicolo_id: str, provenienza: dict[str, Any], esito: str, *, oggetto: str = "", tenant_id: str = "", riferimento: str = "") -> None:
    try:
        from audit.integrations import emit_ai_output_reviewed

        emit_ai_output_reviewed(fascicolo_id=fascicolo_id, sigillo=str(provenienza.get("sigillo") or ""), esito=esito,
                                oggetto=oggetto, tenant_id=tenant_id, riferimento=riferimento)
    except Exception:
        logger.warning("Revisione dell'uscita AI non registrata nella catena probatoria del fascicolo %s", fascicolo_id, exc_info=True)


__all__ = ["AZIONI", "provenienze_fascicolo", "registra_revisione", "registra_uscita"]
