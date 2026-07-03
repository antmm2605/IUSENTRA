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


def _norm_code(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _text(value).casefold())


DATIATTO_GENERATOR_CLASSES = frozenset(
    {
        "IntroduttiviSicid",
        "Introduttivi_SIGP",
        "IntroduttiviSiecicConcorsuali",
        "IntroduttiviSiecicEsecuzioni",
        "Parte",
        "ParteCassazione",
        "ParteSiecicConcorsuali",
        "ParteSiecicEsecuzioni",
        "CorsoCausa_SIGP",
        "Professionista",
        "Professionista_SIGP",
        "ProfSiecicConcorsuali",
        "ProfSiecicEsecuzioni",
        "CurSiecicConcorsuali",
        "CusSiecicEsecuzioni",
        "DelSiecicEsecuzioni",
        "AttoSistemaSicid",
        "AttoSistemaSiecic",
        "AttoSistema_SIGP",
    }
)


def _studio_variable_from_root(root_name: str) -> str:
    if not root_name:
        return ""
    return root_name[:1].casefold() + root_name[1:]


def _split_datiatto_root(root: str) -> tuple[str, str, str]:
    parts = [part for part in _text(root).split(".") if part]
    if len(parts) >= 3:
        return parts[0], parts[-2], parts[-1]
    if len(parts) == 2:
        if parts[0] in DATIATTO_GENERATOR_CLASSES:
            return parts[0], parts[1], _studio_variable_from_root(parts[1])
        return "", parts[0], parts[1]
    if len(parts) == 1:
        return "", parts[0], ""
    return "", "", ""


def _method_generator_class(entry: dict[str, Any]) -> str:
    key = _text(entry.get("key"))
    methods = [_text(item) for item in (entry.get("datiatto_methods") or [])]
    for method in methods:
        if not method.startswith("Create_DatiAtto_"):
            continue
        name = method.removeprefix("Create_DatiAtto_")
        if name.startswith("Introduttivi_SICID"):
            return "IntroduttiviSicid"
        if name.startswith("Introduttivi_SIGP"):
            return "Introduttivi_SIGP"
        if name.startswith("Introduttivi_SIECIC"):
            if "CONCORSUALI" in key:
                return "IntroduttiviSiecicConcorsuali"
            return "IntroduttiviSiecicEsecuzioni"
        if name.startswith("ParteCassazione"):
            return "ParteCassazione"
        if name.startswith("Parte_ESECUZIONI_SIECIC") or name.startswith("ParteSiecicEsecuzioni"):
            return "ParteSiecicEsecuzioni"
        if name.startswith("Parte_CONCORSUALI_SIECIC") or name.startswith("ParteSiecicConcorsuali"):
            return "ParteSiecicConcorsuali"
        if name.startswith("Parte_"):
            return "Parte"
        if name.startswith("CorsoCausa_SIGP"):
            return "CorsoCausa_SIGP"
        if name.startswith("Professionista_SIGP"):
            return "Professionista_SIGP"
        if name.startswith("Professionista_"):
            return "Professionista"
        if name.startswith("ProfSiecicEsecuzioni"):
            return "ProfSiecicEsecuzioni"
        if name.startswith("ProfSiecicConcorsuali"):
            return "ProfSiecicConcorsuali"
        if name.startswith("CusSiecicEsecuzioni"):
            return "CusSiecicEsecuzioni"
        if name.startswith("CurSiecicConcorsuali"):
            return "CurSiecicConcorsuali"
        if name.startswith("DelSiecicEsecuzioni"):
            return "DelSiecicEsecuzioni"
        if name.startswith("AttoSistema_SIGP"):
            return "AttoSistema_SIGP"
        if name.startswith("AttoSistemaSicid"):
            return "AttoSistemaSicid"
        if name.startswith("AttoSistemaSiecic"):
            return "AttoSistemaSiecic"
        if name.startswith("DepositiComplementari_SIGP"):
            return "AttoSistema_SIGP"
        if name.startswith("DepositiComplementari_Sicid"):
            return "AttoSistemaSicid"
        if name.startswith("DepositiComplementari_Siecic"):
            return "AttoSistemaSiecic"
    return ""


def _best_datiatto_root(entry: dict[str, Any], roots: list[str], tipo_atto: str) -> str:
    if not roots:
        return ""
    key_tail = _text(entry.get("key")).split("::")[-1]
    key_norm = _norm_code(key_tail)
    label_norm = _norm_code(entry.get("text"))
    tipo_norm = _norm_code(tipo_atto)
    best_root = roots[0]
    best_score = -1
    for index, root in enumerate(roots):
        generator_class, root_name, studio_variable = _split_datiatto_root(root)
        root_norm = _norm_code(root_name)
        variable_norm = _norm_code(studio_variable)
        class_norm = _norm_code(generator_class)
        score = 0
        if key_norm and root_norm == key_norm:
            score += 1000
        if key_norm and variable_norm == key_norm:
            score += 920
        if key_norm and root_norm and (key_norm in root_norm or root_norm in key_norm):
            score += 420 - min(180, abs(len(root_norm) - len(key_norm)))
        if root_norm and root_norm in label_norm:
            score += 160
        if variable_norm and variable_norm in label_norm:
            score += 130
        if tipo_norm == "ricorso" and root_norm == "ricorso":
            score += 900
        if tipo_norm == "attodicitazione" and root_norm == "citazione":
            score += 900
        if class_norm:
            score += 20
        score -= index
        if score > best_score:
            best_score = score
            best_root = root
    return best_root


_PROCEDIMENTO_BASE_ROOTS = {
    "Comparsa180",
    "DepositoNoteConclusionali",
    "Memoria183",
    "MemoriaReplica183",
    "MemoriaReplica183N3",
    "PrecisazioneConclusioni",
    "ProduzioneDocumentiRichiesti",
    "ScrittiDifensivi",
}


def _quick_required_data(entry: dict[str, Any]) -> list[str]:
    return _unique_texts([_text(item) for item in (entry.get("datiatto_required_data") or [])])


def _operational_required_data(
    *,
    generator_class: str,
    root_name: str,
    quick_required: list[str],
) -> list[str]:
    required: list[str] = []
    quick_norm = {_norm_code(item) for item in quick_required}
    if generator_class.startswith("Introduttivi"):
        required.append("AnagraficaProcedimento")
    if root_name and "citazione" in _norm_code(root_name):
        required.append("Datacitazione")
    if (
        "riferimentoprocedimento" in quick_norm
        or (
            _is_procedimento_generator_class(generator_class)
            and not _is_sistema_generator_class(generator_class)
        )
    ):
        required.extend(["numero RG", "anno RG"])
    if "codiceoggetto" in quick_norm:
        required.append("codice oggetto")
    if "valorecausa" in quick_norm:
        required.append("valore causa quando presente")
    return _unique_texts(required)


def _is_procedimento_generator_class(generator_class: str) -> bool:
    return bool(
        generator_class
        and (
            generator_class == "Parte"
            or generator_class.startswith("ParteSiecic")
            or generator_class.startswith("CorsoCausa")
            or generator_class.startswith("Professionista")
            or generator_class.startswith("ProfSiecic")
            or generator_class.startswith("CurSiecic")
            or generator_class.startswith("CusSiecic")
            or generator_class.startswith("DelSiecic")
            or generator_class.startswith("AttoSistema")
        )
    )


def _is_sistema_generator_class(generator_class: str) -> bool:
    return bool(generator_class and generator_class.startswith("AttoSistema"))


def _datiatto_root_hint(entry: dict[str, Any], rules: dict[str, Any], tipo_atto: str) -> dict[str, Any]:
    roots = _raw_roots(entry)
    primary = _best_datiatto_root(entry, roots, tipo_atto)
    generator_class, root_name, studio_variable = _split_datiatto_root(primary)
    if not generator_class:
        generator_class = _method_generator_class(entry)
    if not root_name and tipo_atto == "RICORSO":
        generator_class = "IntroduttiviSicid"
        root_name = "Ricorso"
        studio_variable = "ricorso"
    quick_required = _quick_required_data(entry)
    if rules.get("channel_kind") == "unep_notifiche":
        mode = "canale_notifiche_separato"
        required_data: list[str] = []
    elif generator_class.startswith("Introduttivi") and root_name and "citazione" in _norm_code(root_name):
        mode = "introduttivo_citazione"
        required_data = _operational_required_data(
            generator_class=generator_class,
            root_name=root_name,
            quick_required=quick_required,
        )
    elif generator_class.startswith("Introduttivi"):
        mode = "introduttivo_anagrafica"
        required_data = _operational_required_data(
            generator_class=generator_class,
            root_name=root_name,
            quick_required=quick_required,
        )
    elif generator_class.startswith("ParteCassazione"):
        mode = "cassazione_parte"
        required_data = _operational_required_data(
            generator_class=generator_class,
            root_name=root_name,
            quick_required=quick_required,
        ) or ["campi Cassazione previsti dallo XSD ministeriale"]
    elif _is_sistema_generator_class(generator_class):
        mode = "sistema_destinazione"
        required_data = _operational_required_data(
            generator_class=generator_class,
            root_name=root_name,
            quick_required=quick_required,
        )
    elif (
        generator_class.startswith("Parte")
        or _is_procedimento_generator_class(generator_class)
        or root_name in _PROCEDIMENTO_BASE_ROOTS
    ):
        mode = "procedimento_base"
        required_data = _operational_required_data(
            generator_class=generator_class,
            root_name=root_name,
            quick_required=quick_required,
        ) or ["numero RG", "anno RG"]
    elif root_name:
        mode = "schema_root_catalogato"
        required_data = _operational_required_data(
            generator_class=generator_class,
            root_name=root_name,
            quick_required=quick_required,
        ) or ["dati obbligatori previsti dallo XSD ministeriale"]
    else:
        mode = "datiatto_generico_iusentra"
        required_data = []
    return {
        "generatorClass": generator_class,
        "ministerialRoot": root_name,
        "studioVariable": studio_variable,
        "generatorMode": mode,
        "requiredData": required_data,
        "quickRequiredData": quick_required,
        "quickDepositFlags": entry.get("deposit_menu_flags") if isinstance(entry.get("deposit_menu_flags"), dict) else {},
        "quickFixedObjectCodes": entry.get("deposit_fixed_object_codes")
        if isinstance(entry.get("deposit_fixed_object_codes"), list)
        else [],
        "primaryEvidenceRoot": primary,
    }


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
    hint = _datiatto_root_hint(entry, rules, tipo_atto)
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
            **hint,
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
            **hint,
        }
    return {
        "status": "supportato_root_catalogo",
        "label": (
            f"DatiAtto.xml {hint['ministerialRoot']} governato dal catalogo"
            if hint["ministerialRoot"]
            else "DatiAtto.xml governato dal generatore attuale"
        ),
        "supported": True,
        "requiresSpecificGenerator": False,
        "supportedMinisterialRoot": hint["ministerialRoot"],
        "evidenceMethodsCount": len(methods),
        "evidenceRootsCount": len(roots),
        "evidenceMethods": methods[:12],
        "evidenceRoots": roots[:12],
        **hint,
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


def _deposit_menu_flags(entry: dict[str, Any]) -> dict[str, Any]:
    flags = entry.get("deposit_menu_flags")
    return flags if isinstance(flags, dict) else {}


def _flag_enabled(flags: dict[str, Any], key: str) -> bool:
    value = flags.get(key)
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return _text(value).casefold() in {"1", "true", "si", "sì", "yes", "on"}


def _required_data_codes(entry: dict[str, Any]) -> set[str]:
    return {_norm_code(_text(item)) for item in (entry.get("datiatto_required_data") or []) if _text(item)}


def _documents_for(entry: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    flags = _deposit_menu_flags(entry)
    required = _required_data_codes(entry)
    haystack = " ".join(
        _text(entry.get(key))
        for key in ("key", "text", "channel", "macro", "categoria", "path")
    ).casefold()
    need_procura = _flag_enabled(flags, "needProcura")
    need_contributo = _flag_enabled(flags, "needContributoUnificato") or "contributounificato" in required
    need_nota_ruolo = _flag_enabled(flags, "needNotaIscrizioneRuolo")
    if rules.get("channel_kind") == "unep_notifiche":
        documents = ["atto da notificare", "relata o richiesta", "destinatari"]
        if need_contributo:
            documents.append("contributo o anticipazione spese UNEP")
        documents.extend(["allegati", "ricevute"])
        return _unique_texts(documents)

    documents = ["atto principale"]
    if need_procura:
        documents.append("procura alle liti")
    if need_contributo:
        documents.append("ricevuta contributo unificato")
    if need_nota_ruolo:
        documents.append("nota iscrizione a ruolo")
    if "cassazione" in haystack:
        documents.extend(["provvedimento impugnato", "prova notifica"])
    if "siecic" in haystack:
        documents.append("dati procedura SIECIC quando richiesti")
    if _flag_enabled(flags, "VisualizzaGrigliaTerzi"):
        documents.append("dati terzi pignorati")
    if _flag_enabled(flags, "VisualizzaAnagraficaProcedimento") or "anagraficaprocedimento" in required:
        documents.append("anagrafica procedimento")
    if "datacitazione" in required:
        documents.append("data citazione")
    if "valorecausa" in required:
        documents.append("valore causa o esenzione")
    if "istanze" in required:
        documents.append("istanze o richieste")
    if "modificheanagrafica" in required:
        documents.append("modifiche anagrafica")
    if "riferimentoprocedimento" in required:
        documents.append("riferimento procedimento")
    if "allegatiinindicebusta" in required:
        documents.append("allegati")
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
    macro = _text(entry.get("macro"), "Catalogo depositi")
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
                "Il catalogo depositi è stato riconosciuto, ma questo canale non è abilitato "
                "nel pannello PCT corrente."
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
            "datiatto_generator_class": schema["generatorClass"],
            "datiatto_root_name": schema["ministerialRoot"],
            "datiatto_studio_variable": schema["studioVariable"],
            "datiatto_generator_mode": schema["generatorMode"],
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
