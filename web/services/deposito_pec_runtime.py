"""Runtime helpers for deposito PEC preparation and no-send checks."""

from __future__ import annotations

from datetime import date, datetime
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
