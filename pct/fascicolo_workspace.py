"""Classificazione condivisa del workspace di un fascicolo."""

from __future__ import annotations

from typing import Any, Optional

from pct.fascicoli import Fascicolo, TipoAttivita, TipoDocumento
from pct.pst_servizi_catalogo import (
    SEZIONE_COMUNICAZIONI_CANCELLERIA,
    SEZIONE_DOCUMENTI_FASCICOLO,
    SEZIONE_ISTANZE,
    SEZIONE_UDIENZE_SCADENZE,
    sezione_fascicolo_da_servizio_pst,
)

_DOC_TIPI_ATTI_PRINCIPALI = {
    TipoDocumento.ATTO_GIUDIZIARIO,
    TipoDocumento.MEMORIA,
    TipoDocumento.RICORSO,
    TipoDocumento.CITAZIONE,
    TipoDocumento.COMPARSA,
}
_DOC_TIPI_PROVVEDIMENTI = {
    TipoDocumento.SENTENZA,
    TipoDocumento.ORDINANZA,
    TipoDocumento.DECRETO,
    TipoDocumento.VERBALE,
}
_DOC_TIPI_RICEVUTE = {
    TipoDocumento.COMUNICAZIONE,
    TipoDocumento.DEPOSITO_PCT,
    TipoDocumento.NOTIFICA,
}
_ATTIVITA_UDIENZE_SCADENZE = {
    TipoAttivita.UDIENZA,
    TipoAttivita.TERMINE_SCADENZA,
    TipoAttivita.RINVIO,
}


def fascicolo_text(*parts: object) -> str:
    return " ".join(str(part or "").strip() for part in parts if str(part or "").strip()).lower()


def documento_bucket(doc: Any) -> str:
    tipo = getattr(doc, "tipo", None)
    if tipo in _DOC_TIPI_PROVVEDIMENTI:
        return "provvedimenti"
    if tipo in _DOC_TIPI_RICEVUTE:
        return "ricevute"
    if tipo in _DOC_TIPI_ATTI_PRINCIPALI:
        return "atti_principali"
    return "allegati"


def documento_is_istanza(doc: Any) -> bool:
    testo = fascicolo_text(getattr(doc, "nome", ""), getattr(doc, "note", ""), getattr(doc, "tipo", ""))
    return "istanza" in testo


def deposito_servizio_portale(dep: Any) -> str:
    return str(getattr(dep, "servizio_portale", "") or "").strip()


def deposito_sezione_portale(dep: Any) -> str:
    servizio = deposito_servizio_portale(dep)
    return sezione_fascicolo_da_servizio_pst(servizio) if servizio else ""


def deposito_ha_ricevute(dep: Any) -> bool:
    return any(
        (
            getattr(dep, "ricevuta_accettazione", ""),
            getattr(dep, "ricevuta_consegna", ""),
            getattr(dep, "ricevuta_controlli_automatici", ""),
            getattr(dep, "ricevuta_cancelleria", ""),
        )
    )


def deposito_is_istanza(dep: Any) -> bool:
    sezione_portale = deposito_sezione_portale(dep)
    if sezione_portale:
        return sezione_portale == SEZIONE_ISTANZE
    testo = fascicolo_text(
        getattr(dep, "tipo_atto", ""),
        getattr(dep, "messaggio", ""),
        getattr(dep, "note", ""),
        getattr(dep, "nome_atto_principale", ""),
    )
    return "istanza" in testo


def deposito_is_udienza_scadenza(dep: Any) -> bool:
    sezione_portale = deposito_sezione_portale(dep)
    if sezione_portale:
        return sezione_portale == SEZIONE_UDIENZE_SCADENZE
    testo = fascicolo_text(
        getattr(dep, "tipo_atto", ""),
        getattr(dep, "note", ""),
        getattr(dep, "nome_atto_principale", ""),
    )
    return any(token in testo for token in ("udienza", "verbale", "scadenz", "rinvio", "termine"))


def deposito_is_comunicazione(dep: Any) -> bool:
    sezione_portale = deposito_sezione_portale(dep)
    if sezione_portale:
        return sezione_portale == SEZIONE_COMUNICAZIONI_CANCELLERIA
    if deposito_ha_ricevute(dep):
        return True
    return str(getattr(dep, "stato", "") or "").strip().upper() in {
        "INVIATO",
        "ACCETTATO",
        "ACCETTATO_PEC",
        "CONSEGNATO",
        "WARN_CONTROLLI",
        "ERRORE_CONTROLLI",
        "RIFIUTATO",
        "ACCETTATO_CANCELLERIA",
        "RIFIUTATO_CANCELLERIA",
        "ERRORE",
    }


def deposito_is_catalogo_documenti(dep: Any) -> bool:
    """True per i depositi PST/SIGP che rappresentano il catalogo documentale."""
    if deposito_sezione_portale(dep) == SEZIONE_DOCUMENTI_FASCICOLO:
        return True
    servizio = deposito_servizio_portale(dep).upper()
    fonte = str(getattr(dep, "fonte_portale", "") or "").strip().upper()
    has_documenti_portale = bool(getattr(dep, "documenti_portale", []) or [])
    portali_documentali = {"PST", "POLISWEB", "PDP", "PAT", "PTT", "SIGIT"}
    return has_documenti_portale and (servizio in portali_documentali or fonte in portali_documentali)


def _documento_portale_identity(dep: Any, pdoc: Any) -> str:
    item = pdoc if isinstance(pdoc, dict) else {}
    dep_id = str(getattr(dep, "id", "") or item.get("id_deposito") or "").strip()
    for field in ("id_documento", "id_cat", "id_repeatto", "msg_id"):
        value = str(item.get(field) or "").strip()
        if value:
            return f"{field}::{value}"
    nome = str(item.get("nome") or "").strip().casefold()
    tipo = str(item.get("tipo") or item.get("tipo_atto") or "").strip().casefold()
    return f"{dep_id}::nome::{nome}::{tipo}"


def _count_documenti_portale_unici(depositi: list[Any]) -> int:
    keys = {
        key
        for dep in depositi
        for item in (getattr(dep, "documenti_portale", []) or [])
        for key in [_documento_portale_identity(dep, item)]
        if key and not key.endswith("::nome::::")
    }
    return len(keys)


def build_fascicolo_workspace(
    fasc: Fascicolo,
    *,
    apps: Optional[list[Any]] = None,
    scadenze: Optional[list[Any]] = None,
) -> dict[str, Any]:
    documenti = list(getattr(fasc, "documenti", []) or [])
    attivita = list(getattr(fasc, "attivita", []) or [])
    depositi = list(getattr(fasc, "depositi_pct", []) or [])
    appuntamenti = list(apps or [])
    termini = list(scadenze or [])
    depositi_documentali = [dep for dep in depositi if deposito_is_catalogo_documenti(dep)]
    depositi_documentali_ids = {
        str(getattr(dep, "id", "") or "").strip()
        for dep in depositi_documentali
        if str(getattr(dep, "id", "") or "").strip()
    }
    documenti_portale_catalogo = _count_documenti_portale_unici(depositi_documentali)
    documenti_portale_importati_da_deposito = {
        str(doc_id or "").strip()
        for dep in depositi_documentali
        for doc_id in (getattr(dep, "documenti_ids", []) or [])
        if str(doc_id or "").strip()
    }
    documenti_portale_importati_da_documenti = {
        str(getattr(doc, "id", "") or "").strip()
        for doc in documenti
        if str(getattr(doc, "id_deposito_pct", "") or "").strip() in depositi_documentali_ids
        and str(getattr(doc, "id", "") or "").strip()
    }
    documenti_portale_importati = min(
        documenti_portale_catalogo,
        len(documenti_portale_importati_da_deposito | documenti_portale_importati_da_documenti),
    )
    documenti_portale_solo_catalogo = max(documenti_portale_catalogo - documenti_portale_importati, 0)
    documenti_totali_governati = len(documenti) + documenti_portale_solo_catalogo

    documenti_buckets = {
        "all": len(documenti),
        "atti_principali": 0,
        "allegati": 0,
        "ricevute": 0,
        "provvedimenti": 0,
        "istanze": 0,
    }
    for doc in documenti:
        documenti_buckets[documento_bucket(doc)] += 1
        if documento_is_istanza(doc):
            documenti_buckets["istanze"] += 1

    attivita_processuali = [
        att
        for att in attivita
        if str(getattr(att, "id_deposito_pct", "") or "").strip() not in depositi_documentali_ids
        and att.tipo not in _ATTIVITA_UDIENZE_SCADENZE
        and att.tipo != TipoAttivita.COMUNICAZIONE_CANCELLERIA
    ]
    udienze_attivita = [
        att
        for att in attivita
        if str(getattr(att, "id_deposito_pct", "") or "").strip() not in depositi_documentali_ids
        and att.tipo in _ATTIVITA_UDIENZE_SCADENZE
    ]
    comunicazioni_attivita = [
        att
        for att in attivita
        if str(getattr(att, "id_deposito_pct", "") or "").strip() not in depositi_documentali_ids
        and att.tipo == TipoAttivita.COMUNICAZIONE_CANCELLERIA
    ]
    istanze_documenti = [doc for doc in documenti if documento_is_istanza(doc)]
    istanze_depositi = [dep for dep in depositi if deposito_is_istanza(dep)]
    comunicazioni_depositi = [
        dep for dep in depositi if dep not in istanze_depositi and deposito_is_comunicazione(dep)
    ]
    udienze_depositi = [
        dep
        for dep in depositi
        if dep not in istanze_depositi and dep not in comunicazioni_depositi and deposito_is_udienza_scadenza(dep)
    ]

    attivita_processuali.sort(key=lambda att: getattr(att, "data", "") or "", reverse=True)
    udienze_attivita.sort(key=lambda att: getattr(att, "data", "") or "")
    udienze_depositi.sort(key=lambda dep: getattr(dep, "timestamp", "") or "", reverse=True)
    comunicazioni_attivita.sort(key=lambda att: getattr(att, "data", "") or "", reverse=True)
    comunicazioni_depositi.sort(key=lambda dep: getattr(dep, "timestamp", "") or "", reverse=True)
    termini.sort(key=lambda sc: getattr(sc, "data_scadenza", "") or getattr(sc, "data", "") or "")
    appuntamenti.sort(key=lambda app_obj: getattr(app_obj, "data_ora", "") or "")

    return {
        "counts": {
            "profilo": 1,
            "documenti": len(documenti),
            "documenti_governati": documenti_totali_governati,
            "documenti_fisici": len(documenti),
            "documenti_catalogo_portale": documenti_portale_catalogo,
            "documenti_solo_catalogo_portale": documenti_portale_solo_catalogo,
            "attivita": len(attivita_processuali),
            "udienze_scadenze": len(udienze_attivita) + len(udienze_depositi) + len(termini) + len(appuntamenti),
            "comunicazioni": len(comunicazioni_attivita) + len(comunicazioni_depositi),
            "istanze": len(istanze_documenti) + len(istanze_depositi),
        },
        "documenti_buckets": documenti_buckets,
        "attivita_processuali": attivita_processuali,
        "udienze_attivita": udienze_attivita,
        "udienze_depositi": udienze_depositi,
        "scadenze": termini,
        "appuntamenti": appuntamenti,
        "comunicazioni_attivita": comunicazioni_attivita,
        "comunicazioni_depositi": comunicazioni_depositi,
        "istanze_documenti": istanze_documenti,
        "istanze_depositi": istanze_depositi,
    }


__all__ = [
    "build_fascicolo_workspace",
    "deposito_is_catalogo_documenti",
    "deposito_is_comunicazione",
    "deposito_is_istanza",
    "deposito_is_udienza_scadenza",
    "deposito_sezione_portale",
    "documento_bucket",
    "documento_is_istanza",
    "fascicolo_text",
]
