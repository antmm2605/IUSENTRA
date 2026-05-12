"""Payload React per il workflow notifiche legali e comunicazioni cliente."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pct.notifiche_legali import (
    DOCUMENT_ORIGIN_LABELS,
    LEGAL_NOTIFICATION_SUBJECT,
    LEGAL_RECIPIENT_ROLES,
    PUBLIC_PEC_REGISTERS,
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _config_object(config_manager_or_config: Any) -> Any:
    return getattr(config_manager_or_config, "config", config_manager_or_config)


def build_react_notifiche_legali_payload(*, config_studio: Any = None) -> dict[str, Any]:
    cfg = _config_object(config_studio)
    studio = getattr(cfg, "studio", None)
    pec = getattr(cfg, "pec", None)

    avvocato_nome = _text(getattr(studio, "avvocato", ""))
    studio_nome = _text(getattr(studio, "nome", "")) or "IUSENTRA"
    city = _text(getattr(studio, "city", ""))
    province = _text(getattr(studio, "province", ""))
    return {
        "source": "configurazione_studio",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "contracts": {
            "separateLegalNotification": True,
            "clientCommunicationWithoutRelata": True,
            "depositProofWithOriginalReceipts": True,
        },
        "mandatorySubject": LEGAL_NOTIFICATION_SUBJECT,
        "defaults": {
            "studioNome": studio_nome,
            "avvocatoNome": avvocato_nome,
            "avvocatoCf": _text(getattr(studio, "codice_fiscale_avvocato", "")) or _text(getattr(studio, "cf", "")),
            "avvocatoForo": _text(getattr(studio, "ordine_avvocati", "")),
            "studioIndirizzo": _text(getattr(studio, "indirizzo", "")),
            "studioCitta": " ".join(part for part in (city, province) if part),
            "mittentePec": _text(getattr(pec, "indirizzo", "")),
            "fontePecMittente": "ReGIndE",
        },
        "registriPec": [
            {"value": key, "label": label}
            for key, label in PUBLIC_PEC_REGISTERS.items()
        ],
        "ruoliDestinatario": [
            {"value": role, "label": _recipient_role_label(role)}
            for role in sorted(LEGAL_RECIPIENT_ROLES)
        ],
        "originiDocumento": [
            {"value": key, "label": label, "needsAttestazione": key in {"copia_fascicolo", "comunicazione_cancelleria", "scansione"}}
            for key, label in DOCUMENT_ORIGIN_LABELS.items()
        ],
        "azioni": {
            "notifica": "/api/v1/ui/notifiche-legali/notifica",
            "comunicazioneCliente": "/api/v1/ui/notifiche-legali/comunicazione-cliente",
            "provaDeposito": "/api/v1/ui/notifiche-legali/prova-deposito",
            "pecCompose": "/email/scrivi?tipo=notifica_l53",
            "clientCompose": "/email-ordinaria/scrivi?tipo=comunicazione_cliente",
            "fascicoli": "/fascicoli",
            "depositoChecklist": "/deposito/checklist",
        },
        "fontiOperative": [
            "Portale Servizi Telematici: notificazioni via PEC degli avvocati, L. 53/1994.",
            "Art. 16-ter D.L. 179/2012: pubblici elenchi rilevanti per notificazioni e comunicazioni.",
            "Specifiche tecniche deposito: ricevute RAC/RdAC in originale digitale e indicizzazione in DatiAtto.xml.",
        ],
    }


def _recipient_role_label(value: str) -> str:
    return {
        "controparte": "Controparte",
        "difensore": "Difensore avversario",
        "impresa": "Impresa",
        "pa": "Pubblica amministrazione",
        "professionista": "Professionista",
        "terzo": "Terzo destinatario",
    }.get(value, value.replace("_", " ").title())
