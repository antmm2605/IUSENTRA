"""Catalogo tipi deposito estratto da Studio Telematico.

Il file JSON sorgente resta un catalogo tecnico condiviso, non un dato tenant.
Questo modulo lo normalizza con regole ministeriali e guardrail di invio.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pct.pst_cifratura import canali_telematici_cifratura_policy
from pct.pst_catalog import (
    PST_CASSAZIONE_XSD_20260611_PACKAGE_URL,
    PST_CASSAZIONE_XSD_20260615_DOWNLOAD_PAGE_URL,
    PST_SICI_XSD_20260611_CHANGELOG_URL,
    PST_SICI_XSD_20260611_NEW_ACT,
    PST_SICI_XSD_20260611_NEW_OBJECT_CODE,
    PST_SICI_XSD_20260611_PACKAGE_URL,
    get_xsd_channels,
)

DATA_DIR = Path(__file__).resolve().parent / "data" / "cataloghi"
CATALOG_PATH = DATA_DIR / "quickorganizer_depositi_studio_telematico.json"

PST_DM44_URL = "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429"
PST_XSD_URL = "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC1579"
NORMATTIVA_DM44_URL = "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=011G0087"
PDP_PPT_URL = (
    "https://pst.giustizia.it/PST/resources/cms/documents/"
    "Specifiche_Tecniche_PPT_11.07.2023_post_DM_2023_signed.pdf"
)
PAT_FORMWEB_URL = "https://www.giustizia-amministrativa.it/-/152174-737"
PTT_GU_URL = "https://www.gazzettaufficiale.it/eli/id/2023/05/03/23A02531/SG"

OFFICIAL_SOURCES: tuple[dict[str, str], ...] = (
    {
        "id": "pst_specifiche_tecniche_dm44_2024",
        "label": "PST - Specifiche Tecniche ex art. 34 DM 44/2011, provvedimento 7 agosto 2024",
        "url": PST_DM44_URL,
        "note": "Efficaci dal 30/09/2024; presidiano busta PCT civile via PEC.",
    },
    {
        "id": "normattiva_dm44_2011",
        "label": "Normattiva - Decreto Ministero Giustizia 21 febbraio 2011, n. 44",
        "url": NORMATTIVA_DM44_URL,
        "note": "Regole tecniche base del processo telematico, art. 34.",
    },
    {
        "id": "pst_xsd_pct",
        "label": "PST - XSD ufficiali Processo Civile Telematico",
        "url": PST_XSD_URL,
        "note": "Schemi XSD ufficiali per gli atti del Processo Civile Telematico.",
    },
    {
        "id": "pst_xsd_sici_preview_20260611",
        "label": "PST - XSD SICI 11/06/2026 per software house",
        "url": PST_SICI_XSD_20260611_PACKAGE_URL,
        "note": (
            "Pacchetto preview non ancora sostitutivo degli schemi in esercizio; "
            f"delta noto: {PST_SICI_XSD_20260611_NEW_ACT} e codice oggetto "
            f"{PST_SICI_XSD_20260611_NEW_OBJECT_CODE}."
        ),
    },
    {
        "id": "pst_xsd_sici_delta_20260611",
        "label": "PST - nota modifiche XSD SICI 11/06/2026",
        "url": PST_SICI_XSD_20260611_CHANGELOG_URL,
        "note": "Documento ministeriale di delta per il pacchetto SICI 11/06/2026.",
    },
    {
        "id": "pst_xsd_cassazione_preview_20260615",
        "label": "PST - XSD Cassazione 15/06/2026 per software house",
        "url": PST_CASSAZIONE_XSD_20260611_PACKAGE_URL,
        "note": "Pacchetto preview Cassazione; la messa in esercizio resta subordinata a successivo avviso PST.",
    },
    {
        "id": "pst_xsd_cassazione_preview_page_20260615",
        "label": "PST - pagina XSD Cassazione aggiornata al 15/06/2026",
        "url": PST_CASSAZIONE_XSD_20260615_DOWNLOAD_PAGE_URL,
        "note": "Pagina ministeriale con avviso che gli schemi non sostituiscono quelli in esercizio.",
    },
    {
        "id": "pst_pdp_penale_2023",
        "label": "PST - Specifiche tecniche Portale Deposito atti Penali",
        "url": PDP_PPT_URL,
        "note": "Canale penale separato dal PCT civile e da Atto.enc.",
    },
    {
        "id": "giustizia_amministrativa_pat_formweb_2026",
        "label": "Giustizia Amministrativa - PAT/Formweb prioritario dal 01/02/2026",
        "url": PAT_FORMWEB_URL,
        "note": "Canale amministrativo separato; PEC residuale nei casi previsti.",
    },
    {
        "id": "gazzetta_ufficiale_ptt_2023",
        "label": "Gazzetta Ufficiale - specifiche tecniche PTT/SIGIT 2023",
        "url": PTT_GU_URL,
        "note": "Canale tributario separato dal PCT civile.",
    },
)


def _text(value: Any, default: str = "") -> str:
    value = str(value if value is not None else "").strip()
    return value or default


def _slug(value: str) -> str:
    try:
        import unicodedata

        value = "".join(
            ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn"
        )
    except Exception:
        pass
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or "catalogo"


def _unique_texts(values: list[str], limit: int | None = None) -> list[str]:
    out: list[str] = []
    for value in values:
        item = _text(value)
        if item and item not in out:
            out.append(item)
        if limit and len(out) >= limit:
            break
    return out


def _raw_roots(entry: dict[str, Any]) -> list[str]:
    roots: list[str] = []
    for item in entry.get("datiatto_roots") or []:
        if isinstance(item, dict):
            roots.append(".".join(part for part in (_text(item.get("type")), _text(item.get("variable"))) if part))
        else:
            roots.append(_text(item))
    return _unique_texts(roots)


@lru_cache(maxsize=1)
def load_deposit_catalog_raw() -> dict[str, Any]:
    if not CATALOG_PATH.exists() or CATALOG_PATH.stat().st_size == 0:
        return {"schema_version": 1, "counts": {"total_deposit_types": 0, "macroareas": {}}, "entries": []}
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {"entries": []}


def _registry_for(entry: dict[str, Any]) -> dict[str, str]:
    channel = _text(entry.get("channel"))
    key = _text(entry.get("key"))
    label = _text(entry.get("text"))
    haystack = f"{channel} {key} {label}".casefold()
    if "unep" in haystack:
        return {"code": "UNEP", "label": "UNEP"}
    if "cassazione" in haystack:
        return {"code": "CASSCI", "label": "Cassazione civile"}
    if "sigp" in haystack or "giudice di pace" in haystack:
        return {"code": "SIGP", "label": "SIGP / Giudice di Pace"}
    if "concorsuali" in haystack:
        return {"code": "SIECIC_CONCORSUALI", "label": "SIECIC concorsuali"}
    if "esecuzioni" in haystack or "esecutiv" in haystack:
        if "immobiliare" in haystack:
            return {"code": "SIECIC_ESIM", "label": "SIECIC esecuzioni immobiliari"}
        if "mobiliare" in haystack or "presso terzi" in haystack or "pressoterzi" in haystack:
            return {"code": "SIECIC_ESM", "label": "SIECIC esecuzioni mobiliari"}
        return {"code": "SIECIC_ESECUZIONI", "label": "SIECIC esecuzioni"}
    if "lavoro" in haystack or "previdenza" in haystack:
        return {"code": "SIL", "label": "Lavoro / SIL"}
    if "minorenni" in haystack or "minor" in haystack:
        return {"code": "SIMIN", "label": "Minorenni / SIMIN"}
    if "volontaria" in haystack or "tutela" in haystack or "curatela" in haystack:
        return {"code": "SIVG", "label": "Volontaria giurisdizione / SIVG"}
    return {"code": "SICID", "label": "Civile ordinario / SICID"}


def _iusentra_act_code(entry: dict[str, Any]) -> str:
    key_tail = _text(entry.get("key")).split("::")[-1]
    text = f"{key_tail} {_text(entry.get('text'))}".casefold()
    if "decretoingiuntivo" in text or "decreto ingiuntivo" in text or "ingiuntiv" in text:
        return "DECRETO_INGIUNTIVO"
    if "controricorso" in text or "contro ricorso" in text or "controricorso" in text:
        return "CONTRORICORSO"
    if "ricorso" in text:
        return "RICORSO"
    if "citazione" in text:
        return "ATTO_DI_CITAZIONE"
    if "comparsa" in text or "costituzione" in text:
        return "COMPARSA_RISPOSTA"
    if "memoria" in text or "memorie" in text:
        return "MEMORIA"
    if "istanza" in text:
        return "ISTANZA"
    if "precetto" in text:
        return "PRECETTO"
    if "pignoramento" in text:
        return "PIGNORAMENTO"
    return "ATTO_GENERICO"


def _schema_status(entry: dict[str, Any], rules: dict[str, Any], tipo_atto: str) -> dict[str, Any]:
    channel_kind = _text(rules.get("channel_kind"))
    roots = _raw_roots(entry)
    methods = _unique_texts([_text(item) for item in (entry.get("datiatto_methods") or [])])
    if channel_kind == "unep_notifiche":
        return {
            "status": "canale_notifiche_separato",
            "label": "Schema UNEP/notifiche separato dal PCT civile",
            "supported": False,
            "requiresSpecificGenerator": True,
            "supportedMinisterialRoot": "",
            "evidenceMethodsCount": len(methods),
            "evidenceRootsCount": len(roots),
            "evidenceMethods": methods[:12],
            "evidenceRoots": roots[:12],
        }
    if tipo_atto == "RICORSO":
        return {
            "status": "supportato_ricorso_base",
            "label": "DatiAtto ministeriale Ricorso governato dal generatore attuale",
            "supported": True,
            "requiresSpecificGenerator": False,
            "supportedMinisterialRoot": "Ricorso",
            "evidenceMethodsCount": len(methods),
            "evidenceRootsCount": len(roots),
            "evidenceMethods": methods[:12],
            "evidenceRoots": roots[:12],
        }
    return {
        "status": "generatore_specifico_da_completare",
        "label": "Richiede generatore DatiAtto ministeriale specifico per questo tipo",
        "supported": False,
        "requiresSpecificGenerator": True,
        "supportedMinisterialRoot": "",
        "evidenceMethodsCount": len(methods),
        "evidenceRootsCount": len(roots),
        "evidenceMethods": methods[:12],
        "evidenceRoots": roots[:12],
    }


def _rules_for(entry: dict[str, Any], registry: dict[str, str]) -> dict[str, Any]:
    channel = _text(entry.get("channel"))
    haystack = f"{channel} {_text(entry.get('key'))} {_text(entry.get('text'))}".casefold()
    if "unep" in haystack:
        return {
            "policy_code": "unep_notifiche",
            "channel_kind": "unep_notifiche",
            "official_channel": "UNEP",
            "registry_code": registry["code"],
            "registry_label": registry["label"],
            "transport_kind": "notifiche_unep",
            "requires_datiatto": False,
            "requires_indice_busta": False,
            "requires_atto_enc": False,
            "requires_pst_cer": False,
            "requires_local_signer": True,
            "requires_local_pec": True,
            "requires_relata": True,
            "requires_receipts": True,
            "server_smtp_allowed": False,
            "can_prepare_in_pct_panel": False,
            "real_send_allowed_from_pct_panel": False,
            "real_send_blocker": (
                "Questo tipo Studio Telematico appartiene al canale UNEP/notifiche: "
                "va gestito dal flusso notifiche/UNEP e non come deposito PCT civile con Atto.enc."
            ),
        }
    return {
        "policy_code": "pct_civile_dm44",
        "channel_kind": "pct_civile_dm44",
        "official_channel": channel or "PCT civile",
        "registry_code": registry["code"],
        "registry_label": registry["label"],
        "transport_kind": "pct_pec_atto_enc",
        "requires_datiatto": True,
        "requires_indice_busta": True,
        "requires_atto_enc": True,
        "requires_pst_cer": True,
        "requires_local_signer": True,
        "requires_local_pec": True,
        "requires_relata": False,
        "requires_receipts": True,
        "server_smtp_allowed": False,
        "can_prepare_in_pct_panel": True,
        "real_send_allowed_from_pct_panel": True,
        "real_send_blocker": "",
    }


def _documents_for(entry: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    category = _text(entry.get("categoria"))
    if rules.get("channel_kind") == "unep_notifiche":
        return ["atto da notificare", "relata o richiesta", "destinatari", "allegati", "ricevute"]
    documents = ["atto principale", "procura alle liti", "allegati"]
    if "introduttivi" in category.casefold():
        documents.append("dati iscrizione a ruolo")
    if "cassazione" in _text(entry.get("channel")).casefold():
        documents.extend(["provvedimento impugnato", "prova notifica"])
    if "siecic" in _text(entry.get("channel")).casefold():
        documents.append("dati procedura SIECIC quando richiesti")
    return _unique_texts(documents)


def _controls_for(entry: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    controls = ["ufficio giudiziario", "registro e ruolo", "codice deposito / oggetto", "atto principale"]
    if rules.get("requires_local_signer"):
        controls.append("firma digitale")
    if rules.get("requires_datiatto"):
        controls.extend(["DatiAtto.xml", "DatiAtto.xml.p7m", "IndiceBusta.xml"])
    if rules.get("requires_atto_enc"):
        controls.append("Atto.enc AES256")
    if rules.get("requires_pst_cer"):
        controls.append("certificato PST .cer")
    if rules.get("requires_local_pec"):
        controls.append("PEC locale dal PC dell'avvocato")
    if rules.get("requires_relata"):
        controls.append("relata e destinatari")
    if rules.get("requires_receipts"):
        controls.append("ricevute e presidio PEC")
    return _unique_texts(controls)


def _normalise_entry(entry: dict[str, Any], index: int) -> dict[str, Any]:
    label = _text(entry.get("text"), _text(entry.get("key"), f"Deposito {index + 1}"))
    macro = _text(entry.get("macro"), "Catalogo Studio Telematico")
    category = _text(entry.get("categoria"), "Senza categoria")
    path = _text(entry.get("path"), " > ".join(part for part in (macro, category, label) if part))
    key = _text(entry.get("key")) or f"studio-telematico::{_slug(path)}::{index + 1}"
    prefix = _text(entry.get("prefix"), key.split("::")[0] + "::" if "::" in key else "")
    registry = _registry_for({**entry, "key": key, "text": label, "macro": macro, "categoria": category, "path": path})
    rules = _rules_for({**entry, "key": key, "text": label}, registry)
    tipo_atto = _iusentra_act_code({**entry, "key": key, "text": label})
    schema = _schema_status(entry, rules, tipo_atto)
    if rules["real_send_allowed_from_pct_panel"] and schema["requiresSpecificGenerator"]:
        rules = {
            **rules,
            "real_send_allowed_from_pct_panel": False,
            "real_send_blocker": (
                "Il catalogo Studio Telematico è stato riconosciuto, ma per questo tipo serve "
                "un generatore DatiAtto ministeriale specifico prima dell'invio reale."
            ),
        }
    return {
        "key": key,
        "label": label,
        "macro": macro,
        "category": category,
        "path": path,
        "prefix": prefix,
        "channel": _text(entry.get("channel"), rules["official_channel"]),
        "registry": registry,
        "quickOrganizer": {
            "rawKey": _text(entry.get("key")),
            "prefix": prefix,
            "datiattoMethodsCount": schema["evidenceMethodsCount"],
            "datiattoRootsCount": schema["evidenceRootsCount"],
        },
        "payload": {
            "tipo_atto": tipo_atto,
            "codice_registro": registry["code"],
            "tipo_deposito_telematico_key": key,
            "tipo_deposito_telematico_label": label,
            "tipo_deposito_telematico_channel": _text(entry.get("channel"), rules["official_channel"]),
            "tipo_deposito_telematico_registry": registry["code"],
            "tipo_deposito_telematico_policy": rules["policy_code"],
            "tipo_deposito_telematico_schema_status": schema["status"],
        },
        "rules": rules,
        "schema": schema,
        "ui": {
            "service": registry["label"],
            "transport": (
                "Atto.msg, DatiAtto.xml.p7m, IndiceBusta.xml, Atto.enc e PEC locale"
                if rules["channel_kind"] == "pct_civile_dm44"
                else "Flusso UNEP/notifiche con relata, destinatari e ricevute"
            ),
            "behavior": (
                "Deposito PCT: il software deve risolvere ufficio, registro, codice oggetto, firme, busta e ricevute."
                if rules["channel_kind"] == "pct_civile_dm44"
                else "Canale notifiche/UNEP: alimenta notifiche, fascicolo, ricevute, agenda e scadenziario."
            ),
            "controls": _controls_for(entry, rules),
            "documents": _documents_for(entry, rules),
        },
    }


@lru_cache(maxsize=1)
def list_deposit_catalog_entries() -> tuple[dict[str, Any], ...]:
    raw = load_deposit_catalog_raw()
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw.get("entries") or []):
        if isinstance(item, dict):
            rows.append(_normalise_entry(item, index))
    return tuple(rows)


@lru_cache(maxsize=1)
def _entries_by_key() -> dict[str, dict[str, Any]]:
    return {row["key"]: row for row in list_deposit_catalog_entries()}


def resolve_deposit_catalog_entry(key: str) -> dict[str, Any] | None:
    return _entries_by_key().get(_text(key))


def _macroareas_payload(entries: tuple[dict[str, Any], ...], macro_counts: dict[str, Any]) -> list[dict[str, Any]]:
    ordered_macro_names = [
        _text(item)
        for item in list(macro_counts.keys()) + [entry["macro"] for entry in entries]
        if _text(item)
    ]
    ordered_macro_names = _unique_texts(ordered_macro_names)
    macroareas: list[dict[str, Any]] = []
    for macro in ordered_macro_names:
        macro_entries = [entry for entry in entries if entry["macro"] == macro]
        categories = _unique_texts([entry["category"] for entry in macro_entries])
        macroareas.append(
            {
                "id": _slug(macro),
                "label": macro,
                "total": int(macro_counts.get(macro) or len(macro_entries)),
                "service": _macro_service(macro, macro_entries),
                "categories": [
                    {
                        "id": f"{_slug(macro)}-{_slug(category)}",
                        "label": category,
                        "total": len([entry for entry in macro_entries if entry["category"] == category]),
                        "optionKeys": [entry["key"] for entry in macro_entries if entry["category"] == category],
                    }
                    for category in categories
                ],
            }
        )
    return [macro for macro in macroareas if macro["total"] > 0]


def _macro_service(macro: str, entries: list[dict[str, Any]]) -> str:
    text = macro.casefold()
    if "contenzioso" in text or "lavoro" in text or "minorenni" in text or "volontaria" in text:
        return "SICID / SIL / SIVG / MIN"
    if "cassazione" in text:
        return "CASSCI"
    if "giudice di pace" in text:
        return "SIGP / GDP"
    if "concorsuali" in text:
        return "SIECIC / FALL"
    if "esecutivo" in text:
        return "SIECIC / ESIM / ESM"
    if "unep" in text:
        return "UNEP"
    return " / ".join(_unique_texts([entry["channel"] for entry in entries])) or "Canale da verificare"


def build_deposit_catalog_payload(*, include_entries: bool = True) -> dict[str, Any]:
    raw = load_deposit_catalog_raw()
    counts = raw.get("counts") if isinstance(raw.get("counts"), dict) else {}
    macro_counts = counts.get("macroareas") if isinstance(counts.get("macroareas"), dict) else {}
    entries = list_deposit_catalog_entries()
    policy = canali_telematici_cifratura_policy()
    return {
        "schemaVersion": 2,
        "source": "studio_telematico_quickorganizer",
        "sourceOfTruth": str(CATALOG_PATH.as_posix()),
        "jsonAuthoritative": False,
        "tenantScope": "catalogo_tecnico_condiviso_non_tenant",
        "generatedAt": _text(raw.get("generated_at")),
        "counts": {
            "totalDepositTypes": int((counts or {}).get("total_deposit_types") or len(entries)),
            "macroareas": macro_counts,
            "categories": counts.get("categories") if isinstance(counts.get("categories"), dict) else {},
        },
        "sourceMeta": raw.get("source") if isinstance(raw.get("source"), dict) else {},
        "officialSources": list(OFFICIAL_SOURCES),
        "ministerialXsdChannels": [channel.to_dict() for channel in get_xsd_channels()],
        "ministerialSchemaEvidence": {
            "siciPreview20260611": {
                "packageUrl": PST_SICI_XSD_20260611_PACKAGE_URL,
                "changelogUrl": PST_SICI_XSD_20260611_CHANGELOG_URL,
                "xsdCount": 156,
                "newAct": PST_SICI_XSD_20260611_NEW_ACT,
                "newObjectCode": PST_SICI_XSD_20260611_NEW_OBJECT_CODE,
                "productionReady": False,
            },
            "cassazionePreview20260615": {
                "packageUrl": PST_CASSAZIONE_XSD_20260611_PACKAGE_URL,
                "downloadPageUrl": PST_CASSAZIONE_XSD_20260615_DOWNLOAD_PAGE_URL,
                "xsdCount": 116,
                "productionReady": False,
            },
        },
        "channelPolicies": {
            **policy,
            "unep_notifiche": {
                "nome": "UNEP / notifiche / richieste esecuzione",
                "usa_certificati_pst_cer": False,
                "trasporto": "Flusso notifiche/UNEP separato, senza Atto.enc PCT civile",
                "server_smtp_allowed": False,
                "fonte": "Catalogo Studio Telematico e regole notifiche/UNEP da flusso dedicato",
            },
        },
        "macroareas": _macroareas_payload(entries, macro_counts),
        "entries": list(entries) if include_entries else [],
    }


def resolve_deposit_type_payload(key: str) -> dict[str, Any] | None:
    entry = resolve_deposit_catalog_entry(key)
    if not entry:
        return None
    return dict(entry)
