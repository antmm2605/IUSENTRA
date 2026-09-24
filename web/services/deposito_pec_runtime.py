"""Runtime helpers for deposito PEC preparation and no-send checks."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from typing import Any, Callable
import uuid

from pct.deposito_compatibilita import build_deposito_compatibility_report
from pct.deposito_simulazione import simulated_deposit_note
from pct.fascicoli import (
    AttivitaProcessuale,
    EsitoAttivita,
    EsitoDepositoPCT,
    TIPO_ATTO_LABEL,
    _tipo_attivita_da_tipo_atto,
)
from web.services.local_pec_runtime import local_pec_required_response


DEPOSIT_WORKFLOW_VERSION = 1
DEPOSIT_WORKFLOW_STAGES = ("proof", "simulation", "send")


def _workflow_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalise_workflow_documents(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    normalised: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        document_id = str(raw.get("documentId") or raw.get("document_id") or "").strip()
        if not document_id:
            continue
        normalised.append(
            {
                "documentId": document_id,
                "selected": bool(raw.get("selected")),
                "role": str(raw.get("role") or "").strip(),
                "studioDocumentType": str(
                    raw.get("studioDocumentType") or raw.get("studio_document_type") or ""
                ).strip(),
                "alreadySigned": bool(raw.get("alreadySigned") or raw.get("already_signed")),
                "requiresSignature": bool(
                    raw.get("requiresSignature") or raw.get("requires_signature")
                ),
                "additionalSignature": bool(
                    raw.get("additionalSignature") or raw.get("additional_signature")
                ),
            }
        )
    return sorted(normalised, key=lambda row: row["documentId"])


def deposito_workflow_fingerprint(preparation: Any) -> str:
    """Impronta il contenuto effettivo della preparazione, esclusi stato e metadati."""

    row = preparation if isinstance(preparation, dict) else {}
    canonical = {
        "typeKey": str(row.get("tipo_deposito_telematico_key") or "").strip(),
        "policy": str(row.get("tipo_deposito_telematico_policy") or "").strip(),
        "datiattoExtra": row.get("datiatto_extra") if isinstance(row.get("datiatto_extra"), dict) else {},
        "documents": _normalise_workflow_documents(row.get("documents")),
        "pecBody": str(row.get("corpo_pec") or "").replace("\r\n", "\n").strip(),
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def deposito_workflow_state(preparation: Any) -> dict[str, Any]:
    row = preparation if isinstance(preparation, dict) else {}
    fingerprint = deposito_workflow_fingerprint(row)
    raw = row.get("workflow") if isinstance(row.get("workflow"), dict) else {}
    if str(raw.get("fingerprint") or "") != fingerprint:
        raw = {}
    state: dict[str, Any] = {
        "version": DEPOSIT_WORKFLOW_VERSION,
        "fingerprint": fingerprint,
    }
    for stage in DEPOSIT_WORKFLOW_STAGES:
        stage_raw = raw.get(stage) if isinstance(raw.get(stage), dict) else {}
        state[stage] = {
            "ok": bool(stage_raw.get("ok")),
            "completed_at": str(stage_raw.get("completed_at") or "").strip(),
            "id_deposito": str(stage_raw.get("id_deposito") or "").strip(),
        }
    return state


def preserve_deposito_workflow(
    preparation: dict[str, Any],
    previous_preparation: Any,
    *,
    reset: bool = False,
) -> dict[str, Any]:
    """Mantiene gli esiti positivi solo se la preparazione è identica."""

    next_preparation = dict(preparation)
    next_fingerprint = deposito_workflow_fingerprint(next_preparation)
    previous_state = deposito_workflow_state(previous_preparation)
    if reset or previous_state["fingerprint"] != next_fingerprint:
        clean_preparation = dict(next_preparation)
        clean_preparation.pop("workflow", None)
        previous_state = deposito_workflow_state(clean_preparation)
    previous_state["fingerprint"] = next_fingerprint
    next_preparation["workflow"] = previous_state
    return next_preparation


def mark_deposito_workflow_stage(
    profile: Any,
    stage: str,
    *,
    id_deposito: str = "",
    completed_at: str = "",
) -> dict[str, Any]:
    """Registra un esito positivo rispettando l'ordine obbligatorio del ciclo."""

    if stage not in DEPOSIT_WORKFLOW_STAGES:
        raise ValueError("Fase deposito non riconosciuta.")
    next_profile = dict(profile) if isinstance(profile, dict) else {}
    preparation = dict(next_profile.get("preparazione_busta") or {})
    if not preparation:
        raise ValueError("Preparazione del deposito non salvata.")
    workflow = deposito_workflow_state(preparation)
    if stage == "simulation" and not workflow["proof"]["ok"]:
        raise ValueError("Esegui prima la prova senza invio reale e attendi l'esito positivo.")
    if stage == "send" and not (workflow["proof"]["ok"] and workflow["simulation"]["ok"]):
        raise ValueError("Esegui prima prova e simulazione PEC con esito positivo.")
    if stage != "send" and workflow["send"]["ok"]:
        raise ValueError("Il deposito risulta già inviato. Avvia un nuovo ciclo per un ulteriore deposito.")
    if stage == "send" and workflow["send"]["ok"]:
        raise ValueError("Il deposito risulta già inviato: un secondo invio è bloccato.")

    if stage == "proof":
        workflow["simulation"] = {"ok": False, "completed_at": "", "id_deposito": ""}
        workflow["send"] = {"ok": False, "completed_at": "", "id_deposito": ""}
    elif stage == "simulation":
        workflow["send"] = {"ok": False, "completed_at": "", "id_deposito": ""}
    workflow[stage] = {
        "ok": True,
        "completed_at": completed_at or _workflow_timestamp(),
        "id_deposito": str(id_deposito or "").strip(),
    }
    preparation["workflow"] = workflow
    next_profile["preparazione_busta"] = preparation
    return next_profile


def validate_deposito_action_preparation(
    preparation: Any,
    *,
    type_key: str,
    datiatto_extra: Any,
    corpo_pec: str,
    selected_document_ids: list[str],
    main_document_id: str,
) -> dict[str, Any]:
    """Blocca il riuso degli esiti se il form non coincide con la preparazione salvata."""

    row = preparation if isinstance(preparation, dict) else {}
    if not row:
        raise ValueError("Salva la preparazione del deposito prima di eseguire la prova.")
    if str(row.get("tipo_deposito_telematico_key") or "").strip() != str(type_key or "").strip():
        raise ValueError("Il tipo di deposito è cambiato: il ciclo deve ripartire dalla prova.")
    saved_data = row.get("datiatto_extra") if isinstance(row.get("datiatto_extra"), dict) else {}
    submitted_data = datiatto_extra if isinstance(datiatto_extra, dict) else {}
    if json.dumps(saved_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) != json.dumps(
        submitted_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ):
        raise ValueError("I dati del deposito sono cambiati: il ciclo deve ripartire dalla prova.")
    saved_body = str(row.get("corpo_pec") or "").replace("\r\n", "\n").strip()
    submitted_body = str(corpo_pec or "").replace("\r\n", "\n").strip()
    if saved_body != submitted_body:
        raise ValueError("Il testo PEC è cambiato: il ciclo deve ripartire dalla prova.")
    documents = _normalise_workflow_documents(row.get("documents"))
    saved_selected = sorted(
        item["documentId"]
        for item in documents
        if item["selected"] and item["role"] != "fuori_busta"
    )
    submitted_selected = sorted({str(item or "").strip() for item in selected_document_ids if str(item or "").strip()})
    if saved_selected != submitted_selected:
        raise ValueError("I documenti del deposito sono cambiati: il ciclo deve ripartire dalla prova.")
    saved_main = next(
        (item["documentId"] for item in documents if item["selected"] and item["role"] == "atto_principale"),
        "",
    )
    if saved_main != str(main_document_id or "").strip():
        raise ValueError("L’atto principale è cambiato: il ciclo deve ripartire dalla prova.")
    return deposito_workflow_state(row)


def con_avviso_pec_mittente(payload: dict[str, Any], pec_config_error: str | None) -> dict[str, Any]:
    if not pec_config_error:
        return payload
    next_actions = [
        str(item or "").strip()
        for item in payload.get("next_actions", [])
        if str(item or "").strip()
    ]
    avviso = f"{pec_config_error} Configura la PEC dello studio prima dell'invio reale."
    if avviso not in next_actions:
        next_actions.append(avviso)
    payload["next_actions"] = next_actions
    payload["pec_sender_ready"] = False
    return payload


def build_compatibility_report(
    *,
    id_deposito: str,
    pec_dest: str,
    oggetto_pec: str,
    corpo_pec: str,
    documenti_busta: list[str],
    attachment_path: str,
    busta_audit: dict[str, Any],
    validation: Any,
    codice_ufficio: str,
    ufficio_nome: str,
    tipo_atto: str,
    numero_rg: str,
    anno_rg: str,
    simulazione_senza_invio: bool,
) -> dict[str, Any]:
    return build_deposito_compatibility_report(
        id_deposito=id_deposito,
        pec_dest=pec_dest,
        oggetto_pec=oggetto_pec,
        corpo_pec=corpo_pec,
        documenti_busta=documenti_busta,
        attachment_path=attachment_path,
        busta_audit=busta_audit,
        validation=validation,
        codice_ufficio=codice_ufficio,
        ufficio_nome=ufficio_nome,
        tipo_atto=tipo_atto,
        numero_rg=numero_rg,
        anno_rg=anno_rg,
        simulazione_senza_invio=simulazione_senza_invio,
    )


def build_simulazione_pec_payload(
    *,
    pec_cfg: Any,
    pec_dest: str,
    tipo_atto: str,
    id_deposito: str,
    timestamp: str,
    oggetto_pec: str,
    attachment_path: str,
    validation: Any,
    documenti: list[str],
    corpo_pec: str,
    busta_audit: dict[str, Any],
    compatibility_report: dict[str, Any],
    pec_config_error: str | None,
) -> dict[str, Any]:
    payload = local_pec_required_response(
        pec_cfg=pec_cfg,
        pec_dest=pec_dest,
        tipo_atto=tipo_atto,
        id_deposito=id_deposito,
        timestamp=timestamp,
        oggetto_pec=oggetto_pec,
        attachment_path=attachment_path,
        validation=validation,
        documenti=documenti,
        corpo_pec=corpo_pec,
        busta_audit=busta_audit,
    )
    payload.update(
        {
            "ok": True,
            "simulazione": True,
            "requires_local_pec": False,
            "package_ready": True,
            "compatibility_report": compatibility_report,
            "messaggio": (
                f"Simulazione PEC completata senza invio reale: compatibilità "
                f"{compatibility_report.get('percentuale', 0)}%. "
                "Il pacchetto locale e l'allegato Atto.enc sono stati preparati come per l'invio reale dal PC locale."
            ),
            "next_actions": [
                "Controlla destinatario, oggetto e corpo PEC prima dell'invio reale.",
                "Quando l'avvocato conferma, usa Invia deposito reale: l'invio parte dal PC locale tramite Local Signer.",
                "Presidia ricevuta di accettazione, RdAC, controlli automatici ed esito cancelleria nel fascicolo.",
            ],
        }
    )
    return con_avviso_pec_mittente(payload, pec_config_error)


def registra_prova_senza_invio_pec(
    *,
    fascicolo: Any,
    gestore_fascicoli: Any,
    atto_id: str,
    allegati_ids: list[str],
    id_deposito: str,
    timestamp: str,
    tipo_atto: str,
    pec_dest: str,
    note: str,
    username: str,
    audit: Callable[..., None],
    sync_pubblica: Callable[..., None],
    id_fascicolo: str,
) -> None:
    atto_doc = next((doc for doc in fascicolo.documenti if doc.id == atto_id), None)
    tutti_ids = [atto_id] + [aid for aid in allegati_ids if aid != atto_id]
    label_atto = TIPO_ATTO_LABEL.get(tipo_atto, tipo_atto)
    fascicolo.depositi_pct.append(
        EsitoDepositoPCT(
            id=id_deposito,
            timestamp=timestamp,
            stato="PROVA_SENZA_INVIO",
            tipo_atto=tipo_atto,
            pec_destinatario=pec_dest,
            messaggio=(
                f"Prova senza invio PEC: busta {id_deposito} predisposta verso {pec_dest}. "
                "Payload Local Signer completo con Atto.enc; Nessun invio esterno eseguito."
            ),
            note=simulated_deposit_note(note),
            registrato_da=username,
            documenti_ids=tutti_ids,
            nome_atto_principale=atto_doc.nome if atto_doc else "",
        )
    )
    fascicolo.attivita.append(
        AttivitaProcessuale(
            id=uuid.uuid4().hex[:8].upper(),
            tipo=_tipo_attivita_da_tipo_atto(tipo_atto),
            data=date.today().isoformat(),
            titolo=f"Prova deposito telematico senza invio - {label_atto}",
            descrizione=(
                f"Tipo atto: {label_atto}. PEC: {pec_dest}. Busta: {id_deposito}. "
                "Nessun invio reale eseguito."
            ),
            esito=EsitoAttivita.NON_APPLICABILE,
            id_deposito_pct=id_deposito,
            avvocato=username,
        )
    )
    fascicolo.modificato_il = datetime.now().isoformat()
    gestore_fascicoli._salva()
    audit(
        "fascicoli.deposito.simula_invio_pec",
        "fascicolo",
        id_fascicolo,
        dettagli=f"Prova senza invio {id_deposito} - {tipo_atto} -> {pec_dest}",
    )
    sync_pubblica("modifica", "fascicoli", id_fascicolo, utente=username)
