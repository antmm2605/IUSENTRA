"""Servizi catalogo template atti per UI, filtri e controlli deposito."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
import unicodedata
from typing import Any

from pct.compilatore_atti import AREA_LABELS, AREA_ORDINE, MODELS, get_essential_docs
from pct.template_atti_compiler_bindings import compiler_binding_map_by_title
from pct.template_atti_master_catalog import catalogo_master_stats, load_catalogo_master, load_split_catalogs
from pct.template_cartabia_rules import (
    CARTABIA_RULESET_VERSION,
    cartabia_profile_for_template,
    ensure_cartabia_metadata,
    verifica_cartabia_template,
)
from pct.template_deposit_rules import compliance_template_summary, normalizza_canale, portale_deposito_label


SUITE_GROUP_LABELS: dict[str, str] = {
    "core": "Core processuale e civile",
    "advanced": "Studio generalista evoluto",
    "specialist": "Riti e portali specialistici",
    "studio_interno": "Atti interni di studio",
}


QUICK_FILTERS = [
    ("Modelli operativi", "fonte_catalogo", "compilatore"),
    ("Catalogo professionale", "fonte_catalogo", "master"),
    ("Civile", "materia", "Diritto civile"),
    ("Giudice di Pace", "canale_deposito", "PST_GDP"),
    ("Decreto ingiuntivo", "procedimento", "Procedimento monitorio"),
    ("Famiglia", "materia", "Diritto di famiglia"),
    ("Volontaria giurisdizione", "rito", "Volontaria giurisdizione"),
    ("Locazioni", "procedimento", "Locazioni, condominio e immobili"),
    ("Penale", "canale_deposito", "PDP"),
    ("Tributario", "canale_deposito", "PTT"),
    ("Amministrativo", "canale_deposito", "PAT"),
    ("Stragiudiziale", "natura_atto", "stragiudiziale"),
    ("Atti interni", "canale_deposito", "NESSUNO"),
    ("Preventivi e Incarichi", "query", "preventivo"),
    ("Incarichi", "query", "incarico"),
    ("Deposito telematico", "depositabile", "true"),
    ("Cartabia da revisionare", "stato_conformita", "cartabia_review_required"),
    ("Precompilabile", "prefill_completeness", "precompilabile"),
    ("Verifica avvocato", "richiede_verifica_avvocato", "true"),
    ("Firma obbligatoria", "richiede_firma_digitale", "true"),
    ("PDF/A obbligatorio", "richiede_pdfa", "true"),
]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalizza_testo(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", _clean(value).lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _template_prefix(template_id: str, module_codes: list[str]) -> str:
    ordered = sorted(module_codes, key=len, reverse=True)
    for code in ordered:
        if template_id == code or template_id.startswith(f"{code}_"):
            return code
    return template_id.split("_", 1)[0]


def _build_split_index() -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for group_key, payload in load_split_catalogs().items():
        for item in payload.get("template") or []:
            template_id = _clean(item.get("id"))
            if template_id:
                index[template_id] = {
                    "categoria_suite": group_key,
                    "categoria_suite_label": SUITE_GROUP_LABELS.get(group_key, group_key.replace("_", " ").title()),
                }
    return index


def _module_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_clean(item.get("codice")): dict(item) for item in payload.get("moduli") or [] if _clean(item.get("codice"))}


def _derive_natura_atto(item: dict[str, Any]) -> str:
    area = _clean(item.get("area")).lower()
    fase = _clean(item.get("fase")).lower()
    titolo = _clean(item.get("titolo")).lower()
    canale = normalizza_canale(item.get("canale_telematico"))
    if canale == "NESSUNO" or "interno" in area:
        return "interno"
    if "stragiud" in area or canale == "PEC":
        return "stragiudiziale"
    if any(token in titolo for token in ("appello", "cassazione", "reclamo", "opposizione")):
        return "impugnazione"
    if any(token in titolo for token in ("precetto", "pignoramento", "esecuzione", "assegnazione", "vendita")):
        return "esecuzione"
    if any(token in titolo for token in ("istanza", "memoria", "note", "deposito", "osservazioni")):
        return "istanza"
    if "deposito" in fase:
        return "deposito"
    return "giudiziale"


def _derive_tipo_atto(item: dict[str, Any]) -> str:
    titolo = _clean(item.get("titolo"))
    if not titolo:
        return _clean(item.get("procedimento")) or "Template atto"
    return titolo.split(" per ", 1)[0].split(" ex ", 1)[0][:80]


def _requires_pdfa(canale: str, depositabile: bool) -> bool:
    return bool(depositabile and canale in {"PST", "PST_GDP", "PST_CONCORSUALE", "PAT", "PTT", "PDP"})


def _requires_signature(canale: str, depositabile: bool) -> bool:
    return bool(depositabile and canale in {"PST", "PST_GDP", "PST_CONCORSUALE", "PAT", "PTT", "PDP"})


def _requires_dati_atto(canale: str, depositabile: bool) -> bool:
    return bool(depositabile and canale in {"PST", "PST_GDP", "PST_CONCORSUALE"})


def _requires_contributo(item: dict[str, Any], canale: str, depositabile: bool) -> bool:
    if not depositabile or canale not in {"PST", "PST_GDP", "PAT", "PTT"}:
        return False
    title = _clean(item.get("titolo")).lower()
    return any(token in title for token in ("ricorso", "citazione", "appello", "opposizione", "sfratto"))


def _requires_contributo_from_title(title: str, canale: str, depositabile: bool) -> bool:
    if not depositabile or canale not in {"PST", "PST_GDP", "PAT", "PTT"}:
        return False
    clean_title = _clean(title).lower()
    return any(token in clean_title for token in ("ricorso", "citazione", "appello", "opposizione", "sfratto"))


def _output_previsti(item: dict[str, Any], canale: str, depositabile: bool) -> list[str]:
    outputs = ["docx", "pdf"]
    if _requires_pdfa(canale, depositabile):
        outputs.append("pdfa")
    if _requires_dati_atto(canale, depositabile):
        outputs.append("xml")
    if depositabile and canale != "NESSUNO":
        outputs.append("zip deposito")
    return outputs


def _compiler_canale(area_key: str, model: dict[str, Any]) -> tuple[str, bool]:
    area = _clean(area_key).upper()
    title = _clean(model.get("name")).lower()
    if area == "PENALE":
        return "PDP", True
    if area == "AMMINISTRATIVO":
        return "PAT", True
    if area == "TRIBUTARIO":
        return "PTT", True
    if area == "STRAGIUDIZIALE":
        return "PEC", False
    if "giudice di pace" in title:
        return "PST_GDP", True
    return "PST", True


def _compiler_natura_atto(area_key: str, model: dict[str, Any], canale: str) -> str:
    title = _clean(model.get("name")).lower()
    area = _clean(area_key).upper()
    if area == "STRAGIUDIZIALE" or canale == "PEC":
        return "stragiudiziale"
    if any(token in title for token in ("appello", "cassazione", "reclamo", "opposizione")):
        return "impugnazione"
    if any(token in title for token in ("precetto", "pignoramento", "esecuzione", "assegnazione", "vendita")):
        return "esecuzione"
    if any(token in title for token in ("istanza", "memoria", "note", "deposito", "osservazioni")):
        return "istanza"
    return "giudiziale"


@lru_cache(maxsize=1)
def _compiler_code_set() -> frozenset[str]:
    return frozenset(_clean(model.get("code")) for model in MODELS if _clean(model.get("code")))


def _first_compiler_code(*candidates: str) -> str:
    available = _compiler_code_set()
    for candidate in candidates:
        code = _clean(candidate)
        if code in available:
            return code
    return "CIV_MEM_001"


def _unique_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _prefill_source_labels(bindings: dict[str, Any]) -> list[str]:
    labels = {
        "studio_timbro": "timbro studio",
        "studio": "dati studio",
        "utente": "utente corrente",
        "cliente": "cliente",
        "fascicolo": "fascicolo",
        "parti": "parti fascicolo",
        "documenti": "documenti",
        "today": "data odierna",
        "legacy": "dati gia disponibili",
    }
    sources: list[str] = []
    seen: set[str] = set()
    for candidates in bindings.values():
        for candidate in candidates if isinstance(candidates, list) else [candidates]:
            source = "today" if candidate == "today" else _clean(candidate).split(".", 1)[0]
            label = labels.get(source, source.replace("_", " "))
            if label and label not in seen:
                sources.append(label)
                seen.add(label)
    return sources


def _enrich_cartabia_row(row: dict[str, Any]) -> dict[str, Any]:
    enriched = ensure_cartabia_metadata(row)
    bindings = enriched.get("prefill_bindings") if isinstance(enriched.get("prefill_bindings"), dict) else {}
    enriched["dati_obbligatori"] = _unique_strings(
        list(enriched.get("dati_obbligatori") or [])
        + list(enriched.get("required_prefill_fields") or [])
    )
    enriched["prefill_completeness"] = "precompilabile" if bindings else "da completare"
    enriched["fonti_prefill"] = _prefill_source_labels(bindings)
    enriched["cartabia_verifica"] = verifica_cartabia_template(enriched)
    enriched["cartabia_ruleset_version"] = enriched.get("versione_regole", CARTABIA_RULESET_VERSION)
    enriched["search_text"] = " ".join(
        _clean(value).lower()
        for value in [
            enriched.get("search_text"),
            enriched.get("processo_area"),
            enriched.get("stato_conformita"),
            enriched.get("cartabia_profile"),
            enriched.get("prefill_completeness"),
            *_prefill_source_labels(bindings),
        ]
        if _clean(value)
    )
    return enriched


def _contains_any(text: str, *tokens: str) -> bool:
    return any(_normalizza_testo(token) in text for token in tokens)


def _master_compiler_code(
    item: dict[str, Any],
    *,
    module_code: str,
    canale: str,
    natura: str,
    binding: dict[str, Any] | None,
) -> str:
    if binding:
        bound_code = _clean(binding.get("compiler_code"))
        if bound_code in _compiler_code_set():
            return bound_code

    text = _normalizza_testo(
        " ".join(
            _clean(value)
            for value in (
                item.get("id"),
                item.get("titolo"),
                item.get("famiglia"),
                item.get("area"),
                item.get("macro_area"),
                item.get("sottobranca"),
                item.get("procedimento"),
                item.get("rito"),
                item.get("fase"),
                natura,
                module_code,
            )
            if _clean(value)
        )
    )
    module = _clean(module_code).upper()

    if canale == "PDP" or module.startswith("PEN") or "penale" in text:
        if _contains_any(text, "querela", "denuncia"):
            return _first_compiler_code("PEN_SEGNBASE_001", "PEN_IST_001")
        if _contains_any(text, "nomina", "revoca", "rinuncia mandato", "difensore"):
            return _first_compiler_code("PEN_NOM_001", "PEN_IST_001")
        if _contains_any(text, "parte civile", "costituzione"):
            return _first_compiler_code("PEN_PARTECIVBASE_001", "PEN_IST_001")
        if _contains_any(text, "lista testi", "testi"):
            return _first_compiler_code("PEN_LISTATESTI_001", "PEN_IST_001")
        if _contains_any(text, "appello", "cassazione", "riesame", "opposizione"):
            return _first_compiler_code("PEN_IMP_001", "PEN_OPPDP_001", "PEN_IST_001")
        if _contains_any(text, "copie", "accesso fascicolo"):
            return _first_compiler_code("PEN_COPIE_001", "PEN_IST_001")
        if _contains_any(text, "sequestro", "dissequestro", "restituzione beni"):
            return _first_compiler_code("PEN_DISSEQ_001", "PEN_IST_001")
        if _contains_any(text, "memoria", "note"):
            return _first_compiler_code("PEN_MEM_001", "PEN_NOTEUD_001", "PEN_IST_001")
        if _contains_any(text, "rinvio", "legittimo impedimento"):
            return _first_compiler_code("PEN_RINV_001", "PEN_IST_001")
        return _first_compiler_code("PEN_IST_001")

    if canale == "PAT" or module.startswith("AMM") or _contains_any(
        text,
        "diritto amministrativo",
        "contenzioso amministrativo",
        "ricorso al tar",
        "tribunale amministrativo",
        "giustizia amministrativa",
    ):
        if _contains_any(text, "motivi aggiunti"):
            return _first_compiler_code("AMM_MOTAGG_001", "AMM_RIC_001")
        if _contains_any(text, "cautelare", "sospensione"):
            return _first_compiler_code("AMM_ICAUT_001", "AMM_RIC_001")
        if _contains_any(text, "appello", "consiglio di stato"):
            return _first_compiler_code("AMM_APPCDS_001", "AMM_RIC_001")
        if _contains_any(text, "memoria", "replica"):
            return _first_compiler_code("AMM_MEM_001", "AMM_RIC_001")
        if _contains_any(text, "deposito", "documenti", "accesso", "istanza", "oscuramento"):
            return _first_compiler_code("AMM_DEPDOC_001", "AMM_SEG_001", "AMM_RIC_001")
        return _first_compiler_code("AMM_RIC_001")

    if canale == "PTT" or module.startswith("TRI") or "tribut" in text:
        if _contains_any(text, "appello"):
            return _first_compiler_code("TRIB_APP_001", "TRIB_RIC_001")
        if _contains_any(text, "controdeduzioni"):
            return _first_compiler_code("TRIB_CONTRO_001", "TRIB_RIC_001")
        if _contains_any(text, "sospensione", "cautelare"):
            return _first_compiler_code("TRIB_SOSP_001", "TRIB_RIC_001")
        if _contains_any(text, "memoria", "illustrativa"):
            return _first_compiler_code("TRIB_MEMILL_001", "TRIB_RIC_001")
        if _contains_any(text, "deposito", "documenti"):
            return _first_compiler_code("TRIB_DEPDOC_001", "TRIB_IST_001", "TRIB_RIC_001")
        if _contains_any(text, "istanza", "rinvio", "pubblica udienza", "conciliazione"):
            return _first_compiler_code("TRIB_IST_001", "TRIB_RIC_001")
        return _first_compiler_code("TRIB_RIC_001")

    if canale == "NESSUNO" or module.startswith("STD") or "studio interno" in text:
        if _contains_any(text, "preventivo", "proforma", "fondo spese", "parcella"):
            return _first_compiler_code("STR_PREV_001", "STR_COM_001")
        if _contains_any(text, "incarico", "mandato", "accettazione preventivo"):
            return _first_compiler_code("STR_INC_001", "STR_COM_001")
        if _contains_any(text, "procura"):
            return _first_compiler_code("CIV_PROC_001", "STR_INC_001")
        return _first_compiler_code("STR_COM_001")

    if canale == "PEC" or "stragiudiziale" in text or "adr" in text:
        if _contains_any(text, "preventivo"):
            return _first_compiler_code("STR_PREV_001", "STR_COM_001")
        if _contains_any(text, "incarico"):
            return _first_compiler_code("STR_INC_001", "STR_COM_001")
        if _contains_any(text, "messa in mora", "mora"):
            return _first_compiler_code("STR_MM_001", "STR_DIFF_001")
        if _contains_any(text, "sollecito"):
            return _first_compiler_code("STR_SOLL_001", "STR_DIFF_001")
        if _contains_any(text, "diffida ad adempiere"):
            return _first_compiler_code("STR_INVAD_001", "STR_DIFF_001")
        if _contains_any(text, "diffida", "reclamo", "richiesta", "contestazione"):
            return _first_compiler_code("STR_DIFF_001", "STR_CONTEST_001", "STR_COM_001")
        if _contains_any(text, "transazione", "saldo", "stralcio", "accordo"):
            return _first_compiler_code("STR_PTR_001", "STR_ATR_001", "STR_COM_001")
        return _first_compiler_code("STR_COM_001")

    if module.startswith("FAM") or module.startswith("VGS") or "famiglia" in text or "volontaria giurisdizione" in text:
        if _contains_any(text, "separazione consensuale"):
            return _first_compiler_code("FAM_SEPC_001", "FAM_MEMO_001")
        if _contains_any(text, "separazione giudiziale"):
            return _first_compiler_code("FAM_SEPG_001", "FAM_MEMO_001")
        if _contains_any(text, "divorzio congiunto"):
            return _first_compiler_code("FAM_DIVC_001", "FAM_MEMO_001")
        if _contains_any(text, "divorzio giudiziale"):
            return _first_compiler_code("FAM_DIVG_001", "FAM_MEMO_001")
        if _contains_any(text, "amministrazione di sostegno", "ads"):
            return _first_compiler_code("FAM_ADS_001", "FAM_TUT_001")
        if _contains_any(text, "tutore", "curatore", "giudice tutelare", "autorizzazione", "eredita"):
            return _first_compiler_code("FAM_TUT_001", "FAM_VG_003", "FAM_MEMO_001")
        if _contains_any(text, "affidamento", "figli", "minore", "protezione", "responsabilita genitoriale"):
            return _first_compiler_code("FAM_AFF_001", "FAM_MEMO_001")
        if _contains_any(text, "modifica", "revisione", "mantenimento", "revoca", "riduzione"):
            return _first_compiler_code("FAM_MOD_001", "FAM_MEMO_001")
        return _first_compiler_code("FAM_MEMO_001", "FAM_TUT_001")

    if module.startswith("LAV") or "lavoro" in text or "previdenza" in text:
        if _contains_any(text, "appello", "reclamo"):
            return _first_compiler_code("LAV_APP_001", "LAV_RIC_001")
        if _contains_any(text, "memoria", "difensiva"):
            return _first_compiler_code("LAV_MEM_001", "LAV_RIC_001")
        if _contains_any(text, "diffida", "messa in mora"):
            return _first_compiler_code("STR_DIFF_001", "STR_MM_001")
        if _contains_any(text, "previdenziale", "inps", "invalidita", "accompagnamento"):
            return _first_compiler_code("LAV_PREV_001", "LAV_RIC_001")
        return _first_compiler_code("LAV_RIC_001")

    if module.startswith("LOC") or "locazioni" in text or "condominio" in text or "immobili" in text:
        if _contains_any(text, "sfratto", "licenza", "rilascio"):
            return _first_compiler_code("CIV_SFRINT_001", "CIV_CONVSFR_001", "CIV_CIT_001")
        if _contains_any(text, "diffida"):
            return _first_compiler_code("STR_DIFF_001", "STR_COM_001")
        if _contains_any(text, "ricorso monitorio", "canoni"):
            return _first_compiler_code("CIV_RDI_001", "CIV_CIT_001")
        return _first_compiler_code("CIV_CIT_001")

    if module.startswith("MON") or "monitorio" in text or "decreto ingiuntivo" in text:
        if _contains_any(text, "opposizione"):
            return _first_compiler_code("CIV_OPPDI_001", "CIV_COM_001")
        if _contains_any(text, "precetto"):
            return _first_compiler_code("CIV_PREC_001", "CIV_RDI_001")
        if _contains_any(text, "istanza"):
            return _first_compiler_code("CIV_IST_001", "CIV_RDI_001")
        return _first_compiler_code("CIV_RDI_001")

    if module.startswith("ESE") or "esecuzione" in text or "pignoramento" in text or "precetto" in text:
        if _contains_any(text, "precetto"):
            return _first_compiler_code("CIV_PREC_001", "CIV_PIGBASE_001")
        if _contains_any(text, "pignoramento"):
            return _first_compiler_code("CIV_PIGBASE_001", "CIV_ESE_001")
        if _contains_any(text, "opposizione"):
            return _first_compiler_code("CIV_OPESE_001", "CIV_IST_001")
        return _first_compiler_code("CIV_IST_001")

    if module.startswith("GDP") or canale == "PST_GDP" or "giudice di pace" in text:
        if _contains_any(text, "opposizione"):
            return _first_compiler_code("CIV_CIT_001", "CIV_OPPDI_001")
        if _contains_any(text, "comparsa"):
            return _first_compiler_code("CIV_COM_001", "CIV_CIT_001")
        if _contains_any(text, "memoria", "nota conclusiva"):
            return _first_compiler_code("CIV_MEM_001", "CIV_CONCL_001")
        if _contains_any(text, "istanza"):
            return _first_compiler_code("CIV_IST_001", "CIV_CIT_001")
        return _first_compiler_code("CIV_CIT_001")

    if _contains_any(text, "ricorso ex art. 700", "cautelare", "sequestro", "atp", "possesso", "inibitorio"):
        return _first_compiler_code("CIV_RCAUT_001", "CIV_IST_001")
    if _contains_any(text, "appello", "cassazione", "reclamo", "revocazione"):
        return _first_compiler_code("CIV_APP_001", "CIV_COM_001")
    if _contains_any(text, "comparsa"):
        return _first_compiler_code("CIV_COM_001", "CIV_CIT_001")
    if _contains_any(text, "memoria", "note", "conclusionale", "replica"):
        return _first_compiler_code("CIV_MEM_001", "CIV_CONCL_001", "CIV_REPL_001")
    if _contains_any(text, "istanza", "deposito documenti", "ordine di esibizione", "ctu"):
        return _first_compiler_code("CIV_IST_001", "CIV_DEPDOC_001")
    if _contains_any(text, "ricorso"):
        return _first_compiler_code("CIV_CIT_001", "CIV_RCAUT_001")
    return _first_compiler_code("CIV_CIT_001")


def _compiler_catalog_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    area_order = {area: index for index, area in enumerate(AREA_ORDINE, start=1)}
    for index, model in enumerate(MODELS, start=1):
        code = _clean(model.get("code"))
        if not code:
            continue
        area_key = _clean(model.get("area")).upper()
        area_label = AREA_LABELS.get(area_key, area_key.title())
        title = _clean(model.get("name")) or code
        canale, depositabile = _compiler_canale(area_key, model)
        compliance = compliance_template_summary(canale, [])
        essential_docs = [_clean(value) for value in get_essential_docs(code) if _clean(value)]
        required_fields = [_clean(value) for value in model.get("required_extra_fields") or [] if _clean(value)]
        keywords = [
            code,
            title,
            area_key,
            area_label,
            _clean(model.get("summary")),
            canale,
            portale_deposito_label(canale),
            *essential_docs,
            *required_fields,
            *[_clean(value) for value in model.get("sections") or [] if _clean(value)],
        ]
        natura = _compiler_natura_atto(area_key, model, canale)
        richiede_pdfa = _requires_pdfa(canale, depositabile)
        richiede_firma = _requires_signature(canale, depositabile)
        richiede_dati_atto = _requires_dati_atto(canale, depositabile)
        richiede_contributo = _requires_contributo_from_title(title, canale, depositabile)
        items.append(
            {
                "id": code,
                "codice": code,
                "titolo": title,
                "slug": code.lower().replace("_", "-"),
                "descrizione": _clean(model.get("summary"))
                or f"Modello operativo con redazione guidata per {area_label}.",
                "versione": "operativo",
                "categoria_suite": "modelli_operativi",
                "categoria_suite_label": "Modelli operativi con redazione guidata",
                "modulo_professionale": area_label,
                "modulo_codice": area_key,
                "famiglia": area_label,
                "area": area_label,
                "macro_area": area_label,
                "materia": area_label,
                "sottobranca": _clean(model.get("renderer")) or "Redazione guidata",
                "procedimento": title,
                "variante": "",
                "rito": area_label,
                "fase": "Redazione guidata",
                "autorita": "Da pratica / fascicolo",
                "tipo_atto": title,
                "natura_atto": natura,
                "canale_deposito": canale,
                "canale_telematico": canale,
                "portale_deposito": portale_deposito_label(canale),
                "depositabile": depositabile,
                "normativa_riferimento": [
                    {
                        "fonte": rule["fonte_normativa"],
                        "versione": rule["versione_regola"],
                        "data_ultimo_aggiornamento": rule["data_ultimo_aggiornamento"],
                    }
                    for rule in compliance["regole"][:3]
                ],
                "controlli_conformita": [
                    _clean(rule.get("codice") or rule.get("label"))
                    for rule in compliance["regole"]
                    if _clean(rule.get("codice") or rule.get("label"))
                ],
                "controlli_conformita_dettaglio": compliance["regole"],
                "controlli_deposito_disponibili": compliance["totale"],
                "controlli_completi": compliance["completo"],
                "allegati_obbligatori": essential_docs,
                "allegati_facoltativi": [
                    _clean(value) for value in model.get("suggested_attachments") or [] if _clean(value)
                ][:5],
                "dati_obbligatori": required_fields,
                "blocchi_guidati": [_clean(value) for value in model.get("sections") or [] if _clean(value)],
                "richiede_pdfa": richiede_pdfa,
                "richiede_firma_digitale": richiede_firma,
                "richiede_dati_atto_xml": richiede_dati_atto,
                "richiede_contributo_unificato": richiede_contributo,
                "richiede_marca_bollo": False,
                "output_previsti": _output_previsti({}, canale, depositabile),
                "stato": "pronto",
                "priorita": area_order.get(area_key, 99) * 1000 + index,
                "tags": [area_label, "Redazione guidata", "Operativo"],
                "created_at": "",
                "updated_at": "",
                "search_text": " ".join(_clean(value).lower() for value in keywords if _clean(value)),
                "compliance_summary": compliance,
                "fonte_catalogo": "compilatore",
                "is_compiler_model": True,
                "link_compilatore_code": code,
            }
        )
    return sorted((_enrich_cartabia_row(item) for item in items), key=lambda row: (row["priorita"], row["codice"]))


def build_template_catalog_items() -> list[dict[str, Any]]:
    payload = load_catalogo_master()
    split_index = _build_split_index()
    modules = _module_index(payload)
    module_codes = list(modules)
    compiler_links = compiler_binding_map_by_title()
    items: list[dict[str, Any]] = _compiler_catalog_items()

    for raw in payload.get("template") or []:
        item = deepcopy(raw)
        template_id = _clean(item.get("id"))
        title = _clean(item.get("titolo"))
        binding = compiler_links.get(title)
        canale = normalizza_canale(item.get("canale_telematico"))
        depositabile = bool(item.get("depositabile"))
        module_code = _template_prefix(template_id, module_codes)
        module = modules.get(module_code, {})
        split_meta = split_index.get(template_id, {})
        compliance = compliance_template_summary(canale, list(item.get("checklist_conformita") or []))
        campi_precompila = [_clean(value) for value in item.get("campi_precompila") or [] if _clean(value)]
        blocchi_guidati = [_clean(value) for value in item.get("blocchi_guidati") or [] if _clean(value)]
        allegati_obbligatori = [_clean(value) for value in item.get("allegati_essenziali") or [] if _clean(value)]
        tags = [_clean(value) for value in item.get("tags") or [] if _clean(value)]
        natura = _derive_natura_atto(item)
        compiler_code = _master_compiler_code(
            item,
            module_code=module_code,
            canale=canale,
            natura=natura,
            binding=binding,
        )
        richiede_pdfa = _requires_pdfa(canale, depositabile)
        richiede_firma = _requires_signature(canale, depositabile)
        richiede_dati_atto = _requires_dati_atto(canale, depositabile)
        richiede_contributo = _requires_contributo(item, canale, depositabile)
        search_parts = [
            template_id,
            item.get("slug"),
            item.get("titolo"),
            item.get("famiglia"),
            item.get("area"),
            item.get("macro_area"),
            item.get("sottobranca"),
            item.get("procedimento"),
            item.get("rito"),
            item.get("fase"),
            canale,
            portale_deposito_label(canale),
            natura,
            compiler_code,
            module.get("nome"),
            split_meta.get("categoria_suite_label"),
            *tags,
            *allegati_obbligatori,
            *campi_precompila,
        ]
        items.append(
            {
                **item,
                "codice": template_id,
                "descrizione": (
                    f"{_clean(item.get('titolo'))}: modello del catalogo professionale {item.get('versione')} "
                    f"per {_clean(item.get('famiglia'))}, rito {_clean(item.get('rito'))}."
                ),
                "categoria_suite": split_meta.get("categoria_suite", ""),
                "categoria_suite_label": split_meta.get("categoria_suite_label", "Suite professionale"),
                "modulo_professionale": _clean(module.get("nome")) or _clean(item.get("famiglia")),
                "modulo_codice": module_code,
                "materia": _clean(item.get("macro_area")),
                "tipo_atto": _derive_tipo_atto(item),
                "natura_atto": natura,
                "canale_deposito": canale,
                "portale_deposito": portale_deposito_label(canale),
                "normativa_riferimento": [
                    {
                        "fonte": rule["fonte_normativa"],
                        "versione": rule["versione_regola"],
                        "data_ultimo_aggiornamento": rule["data_ultimo_aggiornamento"],
                    }
                    for rule in compliance["regole"][:3]
                ],
                "controlli_conformita_dettaglio": compliance["regole"],
                "controlli_deposito_disponibili": compliance["totale"],
                "controlli_completi": compliance["completo"],
                "allegati_obbligatori": allegati_obbligatori,
                "allegati_facoltativi": [],
                "dati_obbligatori": campi_precompila,
                "blocchi_guidati": blocchi_guidati,
                "richiede_pdfa": richiede_pdfa,
                "richiede_firma_digitale": richiede_firma,
                "richiede_dati_atto_xml": richiede_dati_atto,
                "richiede_contributo_unificato": richiede_contributo,
                "richiede_marca_bollo": False,
                "output_previsti": _output_previsti(item, canale, depositabile),
                "stato": _clean(item.get("stato")) or "pronto",
                "priorita": int(item.get("ordinamento") or 9999),
                "tags": tags,
                "created_at": "",
                "updated_at": "",
                "search_text": " ".join(_clean(value).lower() for value in search_parts if _clean(value)),
                "compliance_summary": compliance,
                "fonte_catalogo": "master",
                "is_compiler_model": False,
                "link_compilatore_code": compiler_code,
                "link_compilatore_tipo": "binding" if binding else "fallback",
            }
        )
    return sorted((_enrich_cartabia_row(item) for item in items), key=lambda row: (row["priorita"], row["codice"]))


def _filter_values(items: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({_clean(item.get(key)) for item in items if _clean(item.get(key))}, key=str.casefold)


def build_template_catalog_filters(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "materia": _filter_values(items, "materia"),
        "area": _filter_values(items, "area"),
        "macro_area": _filter_values(items, "macro_area"),
        "sottobranca": _filter_values(items, "sottobranca"),
        "procedimento": _filter_values(items, "procedimento"),
        "rito": _filter_values(items, "rito"),
        "fase": _filter_values(items, "fase"),
        "tipo_atto": _filter_values(items, "tipo_atto"),
        "categoria_suite": _filter_values(items, "categoria_suite_label"),
        "canale_deposito": _filter_values(items, "canale_deposito"),
        "portale_deposito": _filter_values(items, "portale_deposito"),
        "stato": _filter_values(items, "stato"),
        "stato_conformita": _filter_values(items, "stato_conformita"),
        "processo_area": _filter_values(items, "processo_area"),
        "cartabia_profile": _filter_values(items, "cartabia_profile"),
        "prefill_completeness": _filter_values(items, "prefill_completeness"),
        "natura_atto": _filter_values(items, "natura_atto"),
        "fonte_catalogo": _filter_values(items, "fonte_catalogo"),
    }


def build_suite_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    stats = catalogo_master_stats()
    master_items = [item for item in items if item.get("fonte_catalogo") == "master"]
    compiler_items = [item for item in items if item.get("fonte_catalogo") == "compilatore"]
    canali = Counter(item["canale_deposito"] for item in master_items)
    groups = Counter(item["categoria_suite_label"] for item in master_items)
    cartabia = Counter(item.get("stato_conformita") for item in master_items if item.get("stato_conformita"))
    return {
        "titolo": "Suite professionale completa",
        "versione": f"v{stats.get('versione')}",
        "totale_template": int(stats.get("totale_template") or len(master_items)),
        "totale_catalogo": len(items),
        "template_operativi": len(compiler_items),
        "template_master": len(master_items),
        "moduli_professionali": int(stats.get("moduli") or 0),
        "canali_governati": len(canali),
        "canali": dict(sorted(canali.items())),
        "categorie": dict(sorted(groups.items())),
        "template_con_cartabia_profile": sum(1 for item in master_items if item.get("cartabia_profile")),
        "template_con_prefill_bindings": sum(1 for item in master_items if item.get("prefill_bindings")),
        "template_con_timbro_automatico": len(master_items),
        "cartabia_ready": int(cartabia.get("cartabia_ready", 0)),
        "cartabia_review_required": int(cartabia.get("cartabia_review_required", 0)),
        "badges": [
            "Redazione guidata",
            "Controlli deposito",
            "Regole Cartabia versionate",
            "Pre-verifica governata",
        ],
    }


def build_suite_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = ["Core processuale e civile", "Studio generalista evoluto", "Riti e portali specialistici", "Atti interni di studio"]
    groups: list[dict[str, Any]] = []
    for label in order:
        templates = [item for item in items if item.get("categoria_suite_label") == label]
        if not templates:
            continue
        groups.append({"label": label, "count": len(templates), "examples": templates[:3]})
    return groups


def build_template_catalog_page_context() -> dict[str, Any]:
    items = build_template_catalog_items()
    return {
        "suite_summary": build_suite_summary(items),
        "suite_groups": build_suite_groups(items),
        "template_suite": items,
        "template_filters": build_template_catalog_filters(items),
        "quick_filters": [{"label": label, "field": field, "value": value} for label, field, value in QUICK_FILTERS],
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def get_template_catalog_item(codice: str) -> dict[str, Any] | None:
    requested = _clean(codice).upper()
    for item in build_template_catalog_items():
        if item["codice"].upper() == requested:
            return item
    return None


def verifica_deposito_template(codice: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    item = get_template_catalog_item(codice)
    if not item:
        return {"ok": False, "errore": "Template non trovato.", "codice": codice}
    payload = payload or {}
    missing_data = [
        field
        for field in item.get("dati_obbligatori", [])
        if field and not _clean(payload.get("dati", {}).get(field) if isinstance(payload.get("dati"), dict) else "")
    ]
    missing_attachments = [
        attachment
        for attachment in item.get("allegati_obbligatori", [])
        if attachment and not _clean(payload.get("allegati", {}).get(attachment) if isinstance(payload.get("allegati"), dict) else "")
    ]
    blocking_rules = [rule for rule in item["controlli_conformita_dettaglio"] if rule.get("blocca_deposito")]
    cartabia = verifica_cartabia_template(
        item,
        payload=payload.get("dati") if isinstance(payload.get("dati"), dict) else {},
        strict_data_check=True,
    )
    return {
        "ok": not missing_data and not missing_attachments and not cartabia.get("controlli_bloccanti"),
        "codice": item["codice"],
        "titolo": item["titolo"],
        "canale_deposito": item["canale_deposito"],
        "portale_deposito": item["portale_deposito"],
        "ruleset_version": item["compliance_summary"]["ruleset_version"],
        "cartabia_ruleset_version": cartabia.get("ruleset_version"),
        "cartabia": cartabia,
        "controlli": item["controlli_conformita_dettaglio"],
        "bloccanti_configurati": len(blocking_rules),
        "dati_mancanti": missing_data,
        "allegati_mancanti": missing_attachments,
        "messaggio": "Verifica superata." if not missing_data and not missing_attachments and not cartabia.get("controlli_bloccanti") else "Completare dati, allegati e controlli prima del deposito.",
    }


__all__ = [
    "QUICK_FILTERS",
    "SUITE_GROUP_LABELS",
    "build_suite_summary",
    "build_template_catalog_filters",
    "build_template_catalog_items",
    "build_template_catalog_page_context",
    "get_template_catalog_item",
    "verifica_deposito_template",
]
