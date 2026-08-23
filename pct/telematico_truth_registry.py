"""Registro di operatività verificata e sentinella per i canali telematici.

Il modulo non avvia richieste di rete e non modifica il fascicolo: trasforma il
catalogo governato e gli esiti del monitor ufficiale in una lettura prodotto.
La fonte dei dati rimane il repository SQL telematico; le strutture qui sotto
sono policy versionata del prodotto e impediscono di presentare come pronto un
canale che richiede ancora una verifica o un passaggio esterno.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable, Mapping


_KNOWN_FAILURES = ("errore", "error", "failed", "fallito", "non disponibile", "blocc")
_KNOWN_ATTENTION = ("warning", "avviso", "degrad", "attenzione", "manual", "attesa")


# La policy è deliberatamente esplicita. Un nuovo canale non eredità lo stato
# "pronta": deve essere aggiunto qui con prova, perimetro e prerequisiti.
CAPABILITY_TRUTH_POLICY: dict[str, dict[str, Any]] = {
    "pst_consultazione_fascicoli": {
        "platform_status": "pronta",
        "proof": "Flusso governato di consultazione e riscontro dal canale ufficiale.",
        "scope": "Ricerca e lettura dei fascicoli telematici civili.",
        "studio_requirement": "Certificato locale valido e accesso personale al portale.",
        "limit": "È consultazione, non effettua un deposito civile.",
        "source_ids": ("pst_giustizia", "pst_servizi_web"),
    },
    "pst_consultazione_documenti": {
        "platform_status": "pronta",
        "proof": "Consultazione guidata con collegamento di documento, fascicolo e provenienza.",
        "scope": "Lettura e acquisizione autorizzata dei documenti disponibili nel fascicolo.",
        "studio_requirement": "Certificato locale valido e accesso personale al portale.",
        "limit": "Il documento resta prova del portale di origine.",
        "source_ids": ("pst_giustizia", "pst_servizi_web"),
    },
    "pst_import_fascicolo": {
        "platform_status": "pronta",
        "proof": "Import controllato in fascicolo, agenda, scadenze e documenti tenant-aware.",
        "scope": "Importa dati già autorizzati e file ottenuti dal portale nel fascicolo dello studio.",
        "studio_requirement": "Certificato locale valido e conferma dell’avvocato sui dati acquisiti.",
        "limit": "Non usa credenziali del portale sul server.",
        "source_ids": ("pst_giustizia", "pst_servizi_web"),
    },
    "pct_prevalidazione_civile": {
        "platform_status": "pronta",
        "proof": "Controlli formali prima della busta, con blocchi spiegati nel fascicolo.",
        "scope": "Verifica documenti, limiti e requisiti noti prima della preparazione del deposito civile.",
        "studio_requirement": "Documenti definitivi e dati fascicolo completi.",
        "limit": "La verifica non sostituisce l’esito della cancelleria.",
        "source_ids": ("pst_servizi_web", "pst_download"),
    },
    "pct_deposito_civile": {
        "platform_status": "condizionata",
        "proof": "Busta, firme, destinatario, ricevute e controllo locale sono governati nel fascicolo.",
        "scope": "Prepara e abilita il deposito civile quando ogni requisito obbligatorio è verificato.",
        "studio_requirement": "Firma valida, PEC locale, certificato dell’ufficio e busta conforme al caso concreto.",
        "limit": "L’invio effettivo parte dal PC dell’avvocato; non viene dichiarato valido senza ricevute.",
        "source_ids": ("pst_giustizia", "pst_servizi_web", "pst_download", "pst_xsd_sici", "pst_xsd_sigp"),
    },
    "pdp_deposito_penale": {
        "platform_status": "assistita",
        "proof": "Percorso penale guidato con documenti, esiti e fascicolo collegato.",
        "scope": "Assiste la preparazione e raccoglie le prove del deposito dal portale penale.",
        "studio_requirement": "Accesso personale PDP con dispositivo di identità richiesto dal portale.",
        "limit": "Il deposito è perfezionato solo dall’esito restituito dal portale penale.",
        "source_ids": ("pst_pdp_specifiche", "pst_giustizia"),
    },
    "xsd_monitoraggio": {
        "platform_status": "pronta",
        "proof": "Monitor delle fonti ufficiali, variazioni e stato dei pacchetti pubblicati.",
        "scope": "Sorveglia canali, specifiche e avvisi che possono incidere sui flussi telematici.",
        "studio_requirement": "Nessuno: il controllo è svolto dal sistema.",
        "limit": "Una variazione apre un presidio, non modifica automaticamente un deposito in corso.",
        "source_ids": ("pst_xsd_sici", "pst_xsd_sigp", "pst_xsd_unep", "pst_xsd_cassazione"),
    },
    "wsdl_monitoraggio": {
        "platform_status": "pronta",
        "proof": "Catalogo documentazione ufficiale con stato e data dell’ultimo riscontro.",
        "scope": "Sorveglia le fonti tecniche ufficiali dei servizi telematici.",
        "studio_requirement": "Nessuno: il controllo è svolto dal sistema.",
        "limit": "Un aggiornamento richiede valutazione prima di cambiare i flussi dello studio.",
        "source_ids": ("pst_servizi_web",),
    },
    "reginde_reference": {
        "platform_status": "pronta",
        "proof": "Catalogo governato di riferimenti e regole formali del canale.",
        "scope": "Supporta i controlli formali e la lettura dei prerequisiti tecnici.",
        "studio_requirement": "Dati del mittente e del fascicolo coerenti.",
        "limit": "Non sostituisce una verifica puntuale del destinatario PEC.",
        "source_ids": ("pst_giustizia", "pst_servizi_web"),
    },
    "telematico_handoff_portali": {
        "platform_status": "assistita",
        "proof": "Passaggio esplicito al portale competente, senza simulare automazioni non disponibili.",
        "scope": "Indirizza PAT, PTT o altri canali al percorso governato applicabile.",
        "studio_requirement": "Accesso personale al portale competente e documenti del fascicolo pronti.",
        "limit": "Non trasforma l’handoff in deposito telematico concluso.",
        "source_ids": ("pst_giustizia",),
    },
}

_PLATFORM_LABELS = {
    "pronta": "Pronta nella piattaforma",
    "condizionata": "Pronta con requisiti",
    "assistita": "Assistita dall’avvocato",
    "da_validare": "Da validare",
}
_PLATFORM_TONES = {
    "pronta": "success",
    "condizionata": "warning",
    "assistita": "info",
    "da_validare": "danger",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "si", "sì"}
    return bool(value)


def _source_health(rows: Iterable[Mapping[str, Any]]) -> tuple[str, str, str, str]:
    """Ritorna stato, etichetta, tono e ultimo controllo delle fonti collegate."""

    values = [dict(row) for row in rows]
    if not values:
        return (
            "non_misurata",
            "Fonte da riscontrare",
            "warning",
            "",
        )

    last_check = max(
        (_text(row.get("last_check") or row.get("lastCheck")) for row in values),
        default="",
    )
    for row in values:
        status = _text(row.get("status")).lower()
        warning = _text(row.get("warning")).lower()
        status_code = int(row.get("status_code") or row.get("statusCode") or 0)
        if status_code >= 400 or any(marker in f"{status} {warning}" for marker in _KNOWN_FAILURES):
            return "bloccata", "Fonte con anomalia", "danger", last_check
    for row in values:
        status = _text(row.get("status")).lower()
        warning = _text(row.get("warning")).lower()
        if _bool(row.get("changed")) or warning or any(marker in status for marker in _KNOWN_ATTENTION):
            return "attenzione", "Fonte da verificare", "warning", last_check
    return "presidiata", "Fonte presidiata", "success", last_check


def _official_references(
    source_ids: Iterable[str],
    sources_by_id: Mapping[str, Mapping[str, Any]],
    monitors_by_source: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for source_id in source_ids:
        source = dict(sources_by_id.get(source_id) or {})
        monitor_rows = list(monitors_by_source.get(source_id) or [])
        source_name = _text(source.get("nome") or (monitor_rows[0].get("nome") if monitor_rows else source_id))
        href = _text(source.get("official_url") or (monitor_rows[0].get("official_url") if monitor_rows else ""))
        if source:
            status, status_label, status_tone, last_check = _source_health(monitor_rows)
            if not monitor_rows:
                status, status_label, status_tone = "acquisizione_programmata", "Acquisizione automatica programmata", "info"
        else:
            status, status_label, status_tone, last_check = "non_censita", "Fonte ufficiale da recuperare", "danger", ""
        references.append(
            {
                "id": source_id,
                "label": source_name,
                "href": href,
                "status": status,
                "statusLabel": status_label,
                "statusTone": status_tone,
                "lastCheck": last_check,
            }
        )
    return references

def build_capability_truth_registry(
    capabilities: Iterable[Mapping[str, Any]] | None,
    monitoring: Iterable[Mapping[str, Any]] | None,
    sources: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Costruisce la lettura prodotto della reale operatività dichiarata.

    Il primo stato risponde a "cosa può fare IUSENTRA". Il secondo, separato,
    risponde a "la fonte esterna collegata risulta presidiata?". La distinzione
    evita di usare un monitor pulito per promuovere una funzione assistita o di
    nascondere un requisito del singolo studio.
    """

    monitors_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in monitoring or []:
        row = dict(raw or {})
        source_id = _text(row.get("source_id") or row.get("sourceId"))
        if source_id:
            monitors_by_source[source_id].append(row)

    sources_by_id = {
        _text(raw.get("source_id") or raw.get("id")): dict(raw or {})
        for raw in (sources or [])
        if _text(raw.get("source_id") or raw.get("id"))
    }
    entries: list[dict[str, Any]] = []
    for raw in capabilities or []:
        capability = dict(raw or {})
        capability_id = _text(capability.get("capability_id") or capability.get("id"))
        if not capability_id:
            continue
        policy = dict(CAPABILITY_TRUTH_POLICY.get(capability_id) or {})
        platform_status = _text(policy.get("platform_status") or "da_validare")
        source_ids = [str(item) for item in policy.get("source_ids") or ()]
        monitor_rows = [row for source_id in source_ids for row in monitors_by_source.get(source_id, [])]
        source_references = _official_references(source_ids, sources_by_id, monitors_by_source)
        source_status, source_label, source_tone, last_check = _source_health(monitor_rows)
        entries.append(
            {
                "id": capability_id,
                "label": _text(capability.get("label") or capability_id),
                "area": _text(capability.get("channel") or capability.get("topic")),
                "platformStatus": platform_status,
                "platformLabel": _PLATFORM_LABELS.get(platform_status, _PLATFORM_LABELS["da_validare"]),
                "platformTone": _PLATFORM_TONES.get(platform_status, _PLATFORM_TONES["da_validare"]),
                "proof": _text(policy.get("proof") or "Prova operativa non ancora registrata."),
                "scope": _text(policy.get("scope") or capability.get("operational_text")),
                "studioRequirement": _text(policy.get("studio_requirement") or "Verifica richiesta per il singolo studio."),
                "limit": _text(policy.get("limit") or "Perimetro da verificare."),
                "sourceStatus": source_status,
                "sourceLabel": source_label,
                "sourceTone": source_tone,
                "lastCheck": last_check,
                # Sono metadati di dominio, non vengono resi come dettaglio tecnico nella UI.
                "references": source_references,
                "sourceIds": source_ids,
            }
        )

    entries.sort(key=lambda row: (row["platformStatus"] != "pronta", row["label"]))
    return {
        "generatedAt": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "entries": entries,
        "summary": {
            "total": len(entries),
            "ready": sum(1 for row in entries if row["platformStatus"] == "pronta"),
            "conditional": sum(1 for row in entries if row["platformStatus"] == "condizionata"),
            "assisted": sum(1 for row in entries if row["platformStatus"] == "assistita"),
            "toValidate": sum(1 for row in entries if row["platformStatus"] == "da_validare"),
            "sourceAttention": sum(1 for row in entries if row["sourceStatus"] in {"attenzione", "bloccata", "non_misurata"}),
        },
    }


def build_telematico_sentinel(
    registry: Mapping[str, Any] | None,
    monitoring: Iterable[Mapping[str, Any]] | None,
    sources: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Traduce le variazioni delle fonti ufficiali in impatti operativi leggibili."""

    source_index = {
        _text(item.get("source_id") or item.get("id")): dict(item or {})
        for item in (sources or [])
        if _text(item.get("source_id") or item.get("id"))
    }
    impacts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in list((registry or {}).get("entries") or []):
        for source_id in entry.get("sourceIds") or []:
            impacts[str(source_id)].append(dict(entry))

    alerts: list[dict[str, Any]] = []
    monitored = 0
    healthy = 0
    for raw in monitoring or []:
        row = dict(raw or {})
        source_id = _text(row.get("source_id") or row.get("sourceId"))
        if not source_id:
            continue
        monitored += 1
        status = _text(row.get("status")).lower()
        warning = _text(row.get("warning"))
        code = int(row.get("status_code") or row.get("statusCode") or 0)
        changed = _bool(row.get("changed"))
        failed = code >= 400 or any(marker in f"{status} {warning.lower()}" for marker in _KNOWN_FAILURES)
        attention = changed or bool(warning) or any(marker in status for marker in _KNOWN_ATTENTION)
        if not failed and not attention:
            healthy += 1
            continue
        related = impacts.get(source_id, [])
        source = source_index.get(source_id, {})
        source_label = _text(source.get("nome") or row.get("nome") or source_id)
        if failed:
            tone, title = "danger", "Fonte ufficiale con anomalia"
            detail = "Il controllo non può confermare la fonte. Verifica il canale prima di usare il flusso interessato."
        elif changed:
            tone, title = "warning", "Variazione ufficiale rilevata"
            detail = "La fonte ha pubblicato una variazione. Valuta l’impatto sui flussi indicati prima della prossima operazione."
        else:
            tone, title = "warning", "Fonte ufficiale da verificare"
            detail = "Il controllo ha rilevato un avviso da esaminare prima di usare il flusso interessato."
        if warning:
            detail = warning
        labels = [str(entry.get("label") or "") for entry in related if entry.get("label")]
        alerts.append(
            {
                "id": f"{source_id}:{_text(row.get('last_check') or row.get('checked_at') or row.get('detected_version'))}",
                "tone": tone,
                "title": title,
                "sourceLabel": source_label,
                "detail": detail,
                "affected": labels[:4],
                "lastCheck": _text(row.get("last_check") or row.get("checked_at") or row.get("ended_at")),
                "href": _text(source.get("official_url") or row.get("official_url") or row.get("monitor_url")),
            }
        )

    alerts.sort(key=lambda row: (row["tone"] != "danger", row["lastCheck"]), reverse=False)
    blocked = sum(1 for row in alerts if row["tone"] == "danger")
    warning_count = len(alerts) - blocked
    source_attention = int((registry or {}).get("summary", {}).get("sourceAttention") or 0)
    acquisition_pending = monitored == 0 or source_attention > 0
    status = "attenzione" if alerts else ("da_presidiare" if acquisition_pending else "presidiata")
    status_label = (
        "Intervento richiesto"
        if alerts
        else ("Acquisizione o verifica fonte necessaria" if acquisition_pending else "Nessuna variazione aperta")
    )
    return {
        "status": status,
        "statusLabel": status_label,
        "summary": {
            "monitored": monitored,
            "healthy": healthy,
            "changes": sum(1 for row in alerts if "Variazione" in row["title"]),
            "attention": warning_count + source_attention,
            "blocked": blocked,
        },
        "alerts": alerts[:12],
    }


__all__ = [
    "CAPABILITY_TRUTH_POLICY",
    "build_capability_truth_registry",
    "build_telematico_sentinel",
]
