from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, get_args, get_origin

from pct.motore_preventivo import catalogo_riferimenti_normativi, catalogo_wizard


SCHEMA_PREVENTIVI_REPOSITORY = Path(__file__).with_name("sql") / "20260414_preventivi_repository.sql"

_WORKFLOW_CHANNEL_LABELS = {
    "ONLINE": "Portale cliente",
    "STUDIO": "Studio",
}

_PREVENTIVO_SECTION_MAP: dict[str, str] = {
    "id_cliente": "Cliente e fascicolo",
    "id_fascicolo": "Cliente e fascicolo",
    "oggetto": "Cliente e fascicolo",
    "id_pratica": "Pratica e tassonomia",
    "area_pratica": "Pratica e tassonomia",
    "area_tassonomica": "Pratica e tassonomia",
    "macro_area_tassonomica": "Pratica e tassonomia",
    "sottobranca_tassonomica": "Pratica e tassonomia",
    "tassonomia_codice": "Pratica e tassonomia",
    "fonti_tassonomia": "Pratica e tassonomia",
    "classificazioni_tassonomiche": "Pratica e tassonomia",
    "tipo_compenso": "Tipo compenso",
    "tipo_procedimento": "Pratica e tassonomia",
    "procedura_operativa_codice": "Piattaforma operativa",
    "procedura_operativa_nome": "Piattaforma operativa",
    "subbranch_operativa_codice": "Piattaforma operativa",
    "workflow_operativo_codice": "Piattaforma operativa",
    "copertura_operativa": "Piattaforma operativa",
    "canale_operativo": "Piattaforma operativa",
    "registro_operativo": "Piattaforma operativa",
    "valore_controversia": "Voci economiche",
    "tariffa_oraria": "Voci economiche",
    "ore_stimate": "Voci economiche",
    "voci": "Voci economiche",
    "complessita": "Voci economiche",
    "applica_cassa": "CPA / IVA / Art. 15",
    "applica_iva": "CPA / IVA / Art. 15",
    "anticipazioni_art15": "CPA / IVA / Art. 15",
    "piano_pagamenti": "Piano pagamenti",
    "workflow_channel": "Workflow studio/online",
    "token_portale": "Workflow studio/online",
    "token_portale_il": "Workflow studio/online",
    "portale_aperto_il": "Workflow studio/online",
    "inviato_cliente_il": "Invio / accettazione / conversione",
    "accettato_il": "Invio / accettazione / conversione",
    "accettato_via": "Invio / accettazione / conversione",
    "accettato_ip": "Invio / accettazione / conversione",
    "accettato_user_agent": "Invio / accettazione / conversione",
    "clausola_controversie_attiva": "Clausole e informativa",
    "clausola_controversie_modello": "Clausole e informativa",
    "clausola_controversie_testo": "Clausole e informativa",
    "clausola_controversie_trattativa_individuale": "Clausole e informativa",
    "clausola_controversie_fonte": "Clausole e informativa",
    "note": "Verifica finale",
    "stato": "Invio / accettazione / conversione",
}

_CONFERIMENTO_SECTION_MAP: dict[str, str] = {
    "id_cliente": "Cliente e fascicolo",
    "id_fascicolo": "Cliente e fascicolo",
    "id_preventivo": "Cliente e fascicolo",
    "oggetto": "Cliente e fascicolo",
    "id_pratica": "Pratica e tassonomia",
    "area_pratica": "Pratica e tassonomia",
    "area_tassonomica": "Pratica e tassonomia",
    "macro_area_tassonomica": "Pratica e tassonomia",
    "sottobranca_tassonomica": "Pratica e tassonomia",
    "tassonomia_codice": "Pratica e tassonomia",
    "fonti_tassonomia": "Pratica e tassonomia",
    "classificazioni_tassonomiche": "Pratica e tassonomia",
    "tipo_compenso": "Tipo compenso",
    "tipo_procedimento": "Pratica e tassonomia",
    "procedura_operativa_codice": "Piattaforma operativa",
    "procedura_operativa_nome": "Piattaforma operativa",
    "subbranch_operativa_codice": "Piattaforma operativa",
    "workflow_operativo_codice": "Piattaforma operativa",
    "copertura_operativa": "Piattaforma operativa",
    "canale_operativo": "Piattaforma operativa",
    "registro_operativo": "Piattaforma operativa",
    "tariffa_oraria": "Voci economiche",
    "compenso_pattuito": "Voci economiche",
    "patto_palmario": "Voci economiche",
    "quota_palmario_pct": "Voci economiche",
    "workflow_channel": "Workflow studio/online",
    "firma_cliente_richiesta": "Workflow studio/online",
    "firma_cliente_eseguita": "Workflow studio/online",
    "firma_cliente_il": "Invio / accettazione / conversione",
    "firma_cliente_via": "Invio / accettazione / conversione",
    "firma_cliente_ip": "Invio / accettazione / conversione",
    "firma_cliente_user_agent": "Invio / accettazione / conversione",
    "fascicolo_aperto_il": "Invio / accettazione / conversione",
    "informativa_art13_resa": "Clausole e informativa",
    "clausola_adr_resa": "Clausole e informativa",
    "clausola_controversie_attiva": "Clausole e informativa",
    "clausola_controversie_modello": "Clausole e informativa",
    "clausola_controversie_testo": "Clausole e informativa",
    "clausola_controversie_trattativa_individuale": "Clausole e informativa",
    "clausola_controversie_fonte": "Clausole e informativa",
    "note": "Verifica finale",
    "stato": "Invio / accettazione / conversione",
}

_COMPENSO_A_TEMPO_PREVENTIVO_FIELDS = {
    "criterio_arrotondamento_orario",
    "minuti_stimati",
    "ore_fatturabili_calcolate",
    "compenso_orario_base",
    "massimale_ore",
    "soglia_preapprovazione_ore",
    "richiede_consenso_superamento_soglia",
    "attivita_orarie_incluse",
    "attivita_orarie_escluse",
    "warning_compenso_orario",
}
_COMPENSO_A_TEMPO_CONFERIMENTO_FIELDS = {
    "criterio_arrotondamento_orario",
    "massimale_ore",
    "soglia_preapprovazione_ore",
    "richiede_consenso_superamento_soglia",
    "attivita_orarie_incluse",
    "attivita_orarie_escluse",
    "warning_compenso_orario",
}
_PREVENTIVO_SECTION_MAP.update({
    field_name: "Compenso a tempo"
    for field_name in _COMPENSO_A_TEMPO_PREVENTIVO_FIELDS
})
_CONFERIMENTO_SECTION_MAP.update({
    field_name: "Compenso a tempo"
    for field_name in _COMPENSO_A_TEMPO_CONFERIMENTO_FIELDS
})

_FIELD_OVERRIDES: dict[str, dict[str, Any]] = {
    "id_cliente": {
        "label": "Cliente collegato",
        "help_text": "Anagrafica cliente a cui appartiene il preventivo o il conferimento.",
        "required_runtime": True,
        "step_key": "cliente_fascicolo",
    },
    "id_fascicolo": {
        "label": "Fascicolo collegato",
        "help_text": "Fascicolo esistente oppure fascicolo che verra' aperto dopo l'accettazione.",
        "required_runtime": False,
        "step_key": "cliente_fascicolo",
    },
    "oggetto": {
        "label": "Oggetto pratica",
        "help_text": "Descrizione sintetica e spendibile della pratica o dell'incarico.",
        "required_runtime": True,
        "step_key": "cliente_fascicolo",
    },
    "id_pratica": {
        "label": "Tipologia pratica",
        "help_text": "Slug della pratica del wizard preventivi e del motore tariffario.",
        "required_runtime": True,
        "step_key": "pratica_tassonomia",
    },
    "area_pratica": {
        "label": "Area pratica",
        "help_text": "Macro-area del preventivo: civile, penale, amministrativo, tributario o stragiudiziale.",
        "required_runtime": True,
        "step_key": "pratica_tassonomia",
    },
    "tipo_compenso": {
        "label": "Tipo compenso",
        "help_text": "Modalita economica: fisso, orario o per fasi processuali.",
        "required_runtime": True,
        "step_key": "tipo_compenso",
    },
    "tipo_procedimento": {
        "label": "Tipo procedimento",
        "help_text": "Descrizione del procedimento o del rito usato nel preventivo.",
        "required_runtime": True,
        "step_key": "pratica_tassonomia",
    },
    "classificazioni_tassonomiche": {
        "label": "Classificazioni tassonomiche aggiuntive",
        "help_text": "Blocchi ulteriori di area, macro-area, sottobranca e tipologia collegata che ampliano il preventivo con voci coerenti allo sviluppo reale della pratica.",
        "required_runtime": False,
        "step_key": "pratica_tassonomia",
    },
    "procedura_operativa_codice": {
        "label": "Codice procedura operativa",
        "help_text": "Codice univoco della procedura della piattaforma legale operativa associata al caso.",
        "required_runtime": True,
        "step_key": "pratica_tassonomia",
    },
    "procedura_operativa_nome": {
        "label": "Procedura operativa",
        "help_text": "Nome della procedura operativa condivisa tra preventivo, conferimento, fascicolo e fatturazione.",
        "required_runtime": True,
        "step_key": "pratica_tassonomia",
    },
    "subbranch_operativa_codice": {
        "label": "Sottobranca operativa",
        "help_text": "Codice della sottobranca specialistica collegata alla procedura operativa.",
        "required_runtime": False,
        "step_key": "pratica_tassonomia",
    },
    "workflow_operativo_codice": {
        "label": "Workflow operativo",
        "help_text": "Workflow di piattaforma da seguire per la pratica selezionata.",
        "required_runtime": False,
        "step_key": "pratica_tassonomia",
    },
    "copertura_operativa": {
        "label": "Copertura operativa",
        "help_text": "Livello di copertura della procedura nella piattaforma legale operativa.",
        "required_runtime": False,
        "step_key": "pratica_tassonomia",
    },
    "canale_operativo": {
        "label": "Canale operativo",
        "help_text": "Canale di lavoro previsto: telematico, portale ministeriale o presidio di studio.",
        "required_runtime": False,
        "step_key": "pratica_tassonomia",
    },
    "registro_operativo": {
        "label": "Registro operativo",
        "help_text": "Registro o superficie procedurale da presidiare nella gestione del caso.",
        "required_runtime": False,
        "step_key": "pratica_tassonomia",
    },
    "valore_controversia": {
        "label": "Valore controversia",
        "help_text": "Valore economico usato dal motore tariffario quando la pratica lo richiede.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "tariffa_oraria": {
        "label": "Tariffa oraria",
        "help_text": "Compenso per ora da usare quando il preventivo e' a tempo.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "ore_stimate": {
        "label": "Ore stimate",
        "help_text": "Stima ore per i preventivi a tariffa oraria.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "voci": {
        "label": "Voci economiche",
        "help_text": "Onorari, spese forfettarie e spese vive del preventivo.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "applica_cassa": {
        "label": "Applica CPA",
        "help_text": "Indica se la Cassa Forense integrativa deve essere calcolata dal motore.",
        "required_runtime": False,
        "step_key": "fiscalita",
    },
    "applica_iva": {
        "label": "Applica IVA",
        "help_text": "Indica se l'IVA deve essere applicata sulla base imponibile.",
        "required_runtime": False,
        "step_key": "fiscalita",
    },
    "anticipazioni_art15": {
        "label": "Anticipazioni art. 15",
        "help_text": "Spese anticipate in nome e per conto del cliente, escluse da imponibile e IVA.",
        "required_runtime": False,
        "step_key": "fiscalita",
    },
    "piano_pagamenti": {
        "label": "Piano pagamenti",
        "help_text": "Rate o acconti previsti nel percorso di pagamento del preventivo.",
        "required_runtime": False,
        "step_key": "piano_pagamenti",
    },
    "workflow_channel": {
        "label": "Canale workflow",
        "help_text": "Indica se il flusso e' gestito in studio o sul portale cliente.",
        "required_runtime": True,
        "step_key": "workflow_canale",
    },
    "clausola_controversie_attiva": {
        "label": "Clausola controversie attiva",
        "help_text": "Attiva la clausola multistep o nessuna clausola specifica.",
        "required_runtime": False,
        "step_key": "clausole_informativa",
    },
    "clausola_controversie_modello": {
        "label": "Modello clausola controversie",
        "help_text": "Modello della clausola sulle controversie collegata a preventivo o conferimento.",
        "required_runtime": False,
        "step_key": "clausole_informativa",
    },
    "clausola_controversie_testo": {
        "label": "Testo clausola controversie",
        "help_text": "Testo effettivo della clausola, da verificare prima dell'invio.",
        "required_runtime": False,
        "step_key": "clausole_informativa",
    },
    "informativa_art13_resa": {
        "label": "Informativa art. 13 resa",
        "help_text": "Conferma che l'informativa economica e professionale e' stata resa al cliente.",
        "required_runtime": False,
        "step_key": "clausole_informativa",
    },
    "clausola_adr_resa": {
        "label": "Informativa ADR resa",
        "help_text": "Conferma che il cliente ha ricevuto l'informativa su ADR e strumenti alternativi.",
        "required_runtime": False,
        "step_key": "clausole_informativa",
    },
    "firma_cliente_richiesta": {
        "label": "Firma cliente richiesta",
        "help_text": "Segnala se il conferimento richiede una firma cliente formale.",
        "required_runtime": False,
        "step_key": "invio_conversione",
    },
    "firma_cliente_eseguita": {
        "label": "Firma cliente eseguita",
        "help_text": "Esito della firma del conferimento prima dell'apertura fascicolo.",
        "required_runtime": False,
        "step_key": "invio_conversione",
    },
}

_FIELD_OVERRIDES.update({
    "criterio_arrotondamento_orario": {
        "label": "Criterio arrotondamento orario",
        "help_text": "Regola pattuita per trasformare minuti e frazioni in ore fatturabili.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "minuti_stimati": {
        "label": "Minuti stimati",
        "help_text": "Minuti aggiuntivi alla stima ore del compenso a tempo.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "ore_fatturabili_calcolate": {
        "label": "Ore fatturabili calcolate",
        "help_text": "Ore risultanti dal criterio art. 22-bis D.M. 55/2014.",
        "required_runtime": False,
        "step_key": "voci_economiche",
        "derived": True,
    },
    "compenso_orario_base": {
        "label": "Compenso orario base",
        "help_text": "Importo base del compenso a tempo prima di CPA, IVA e anticipazioni.",
        "required_runtime": False,
        "step_key": "voci_economiche",
        "derived": True,
    },
    "massimale_ore": {
        "label": "Massimale ore",
        "help_text": "Tetto pattuito oltre il quale serve approvazione espressa del cliente.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "soglia_preapprovazione_ore": {
        "label": "Soglia preapprovazione ore",
        "help_text": "Soglia operativa oltre cui chiedere conferma preventiva al cliente.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "richiede_consenso_superamento_soglia": {
        "label": "Consenso oltre soglia",
        "help_text": "Indica se il superamento della soglia richiede approvazione cliente.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "attivita_orarie_incluse": {
        "label": "Attivita incluse nel compenso a tempo",
        "help_text": "Attivita comprese nella pattuizione a ore.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "attivita_orarie_escluse": {
        "label": "Attivita escluse dal compenso a tempo",
        "help_text": "Attivita escluse o da autorizzare separatamente.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
    "warning_compenso_orario": {
        "label": "Avvisi compenso a tempo",
        "help_text": "Warning normativi e operativi del calcolo art. 22-bis.",
        "required_runtime": False,
        "step_key": "voci_economiche",
    },
})


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _drop_keys(row: sqlite3.Row, *keys: str) -> dict[str, Any]:
    payload = dict(row)
    for key in keys:
        payload.pop(key, None)
    return payload


def _query_terms(question: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for raw in _clean_spaces(question).lower().replace("/", " ").replace("-", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) < 3 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def _prettify_name(name: str) -> str:
    text = _clean_spaces(name).replace("_", " ")
    return text[:1].upper() + text[1:] if text else ""


def _channel_label(value: str) -> str:
    return _WORKFLOW_CHANNEL_LABELS.get(_clean_spaces(value).upper(), "Studio")


def derive_preventivi_repository_db_path(preventivi_db_path: str) -> str:
    target = Path(preventivi_db_path).resolve()
    return str(target.with_name("preventivi_repository.db"))


def derive_preventivi_repository_json_path(preventivi_db_path: str) -> str:
    target = Path(preventivi_db_path).resolve()
    return str(target.with_name("preventivi_repository.json"))


def derive_preventivi_workflow_states_json_path(preventivi_db_path: str) -> str:
    target = Path(preventivi_db_path).resolve()
    return str(target.with_name("preventivi_workflow_states.json"))


def derive_preventivi_field_map_json_path(preventivi_db_path: str) -> str:
    target = Path(preventivi_db_path).resolve()
    return str(target.with_name("preventivi_field_map.json"))


def derive_preventivi_rules_json_path(preventivi_db_path: str) -> str:
    target = Path(preventivi_db_path).resolve()
    return str(target.with_name("preventivi_rules.json"))


def _field_type_name(field_name: str, annotation: Any, default: Any) -> str:
    origin = get_origin(annotation)
    args = get_args(annotation)
    base_annotation = annotation
    if origin is not None and args:
        non_none = [item for item in args if item is not type(None)]
        if len(non_none) == 1:
            base_annotation = non_none[0]
            origin = get_origin(base_annotation)
            args = get_args(base_annotation)
    lowered_name = field_name.lower()
    if lowered_name.startswith("data_") and lowered_name.endswith("_il"):
        return "datetime"
    if lowered_name.startswith("data_"):
        return "date"
    if lowered_name.endswith("_il"):
        return "datetime"
    if origin in {list, tuple}:
        return "list"
    if origin in {dict}:
        return "json"
    if base_annotation in {bool} or isinstance(default, bool):
        return "bool"
    if base_annotation in {int, float} or isinstance(default, (int, float)):
        return "number"
    if isinstance(base_annotation, type) and issubclass(base_annotation, Enum):
        return "enum"
    return "text"


def _enum_values(annotation: Any) -> list[str]:
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return [str(item.value) for item in annotation]
    origin = get_origin(annotation)
    args = get_args(annotation)
    for item in args:
        if isinstance(item, type) and issubclass(item, Enum):
            return [str(value.value) for value in item]
    return []


def _build_field_map(model_cls: type[Any], *, scope: str) -> list[dict[str, Any]]:
    if not is_dataclass(model_cls):
        raise TypeError(f"Il modello {model_cls!r} non e' un dataclass.")
    section_map = _PREVENTIVO_SECTION_MAP if scope == "preventivo" else _CONFERIMENTO_SECTION_MAP
    rows: list[dict[str, Any]] = []
    for order, row in enumerate(fields(model_cls), start=1):
        override = _FIELD_OVERRIDES.get(row.name, {})
        default_value = None
        if row.default is not MISSING:
            default_value = row.default
        field_type = _field_type_name(row.name, row.type, default_value)
        rows.append(
            {
                "scope": scope,
                "field_name": row.name,
                "label": override.get("label") or _prettify_name(row.name),
                "field_type": field_type,
                "section_name": override.get("section_name") or section_map.get(row.name) or "Metadati",
                "help_text": override.get("help_text") or "",
                "required_runtime": bool(override.get("required_runtime", False)),
                "derived": bool(override.get("derived", False)),
                "source_model": model_cls.__name__,
                "step_key": override.get("step_key") or "",
                "enum_values": _enum_values(row.type),
                "sort_order": order,
            }
        )
    return rows


def _wizard_steps() -> list[dict[str, Any]]:
    return [
        {
            "step_key": "cliente_fascicolo",
            "label": "Cliente e fascicolo",
            "description": "Individua cliente, eventuale fascicolo collegato e oggetto sintetico della pratica.",
            "section_names": ["Cliente e fascicolo"],
            "sort_order": 1,
        },
        {
            "step_key": "pratica_tassonomia",
            "label": "Pratica e tassonomia",
            "description": "Seleziona tipologia pratica, area, procedimento e tassonomia del wizard.",
            "section_names": ["Pratica e tassonomia"],
            "sort_order": 2,
        },
        {
            "step_key": "tipo_compenso",
            "label": "Tipo compenso",
            "description": "Distingui compenso fisso, compenso per fasi o tariffa oraria.",
            "section_names": ["Tipo compenso"],
            "sort_order": 3,
        },
        {
            "step_key": "voci_economiche",
            "label": "Voci economiche",
            "description": "Completa valore, voci onorari, ore stimate, complessita e accessori economici.",
            "section_names": ["Voci economiche", "Compenso a tempo"],
            "sort_order": 4,
        },
        {
            "step_key": "fiscalita",
            "label": "CPA / IVA / Art. 15",
            "description": "Verifica Cassa Forense, IVA e anticipazioni escluse ex art. 15.",
            "section_names": ["CPA / IVA / Art. 15"],
            "sort_order": 5,
        },
        {
            "step_key": "piano_pagamenti",
            "label": "Piano pagamenti",
            "description": "Definisci rate, acconti e scadenze di pagamento collegate al preventivo.",
            "section_names": ["Piano pagamenti"],
            "sort_order": 6,
        },
        {
            "step_key": "workflow_canale",
            "label": "Workflow studio/online",
            "description": "Stabilisci se il percorso avviene in studio o sul portale cliente.",
            "section_names": ["Workflow studio/online"],
            "sort_order": 7,
        },
        {
            "step_key": "clausole_informativa",
            "label": "Clausole e informativa",
            "description": "Completa clausole, informativa art. 13, ADR e testi negoziali.",
            "section_names": ["Clausole e informativa"],
            "sort_order": 8,
        },
        {
            "step_key": "verifica_finale",
            "label": "Verifica finale",
            "description": "Controlla completezza, note e coerenza economica prima della generazione.",
            "section_names": ["Verifica finale"],
            "sort_order": 9,
        },
        {
            "step_key": "invio_conversione",
            "label": "Invio / accettazione / conversione",
            "description": "Gestisci invio, apertura cliente, accettazione, conferimento, firma e conversione in fascicolo.",
            "section_names": ["Invio / accettazione / conversione"],
            "sort_order": 10,
        },
    ]


def _workflow_states_catalog() -> list[dict[str, Any]]:
    return [
        {
            "scope": "preventivo",
            "state_code": "BOZZA",
            "label": "Bozza",
            "operational_meaning": "Preventivo aperto ma ancora da completare nei dati essenziali.",
            "is_active": True,
            "is_terminal": False,
            "allowed_actions": ["completa_wizard", "aggiungi_voci", "calcola", "salva"],
            "next_actions": ["Completa i campi chiave e porta il preventivo in calcolo o generazione."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 1,
        },
        {
            "scope": "preventivo",
            "state_code": "IN_CALCOLO",
            "label": "In calcolo",
            "operational_meaning": "Wizard preventivo in corso con motore economico ancora da rifinire.",
            "is_active": True,
            "is_terminal": False,
            "allowed_actions": ["ricalcola", "verifica_voci", "definisci_piano_pagamenti"],
            "next_actions": ["Chiudi il riepilogo economico e genera il documento."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 2,
        },
        {
            "scope": "preventivo",
            "state_code": "GENERATO",
            "label": "Generato",
            "operational_meaning": "Documento di preventivo creato ma non ancora verificato o inviato.",
            "is_active": True,
            "is_terminal": False,
            "allowed_actions": ["verifica", "invia", "revisione"],
            "next_actions": ["Verifica la bozza finale e scegli il canale di invio."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 3,
        },
        {
            "scope": "preventivo",
            "state_code": "VERIFICATO",
            "label": "Verificato",
            "operational_meaning": "Preventivo controllato dall'avvocato e pronto per essere inviato.",
            "is_active": True,
            "is_terminal": False,
            "allowed_actions": ["invia", "revisione"],
            "next_actions": ["Invia il preventivo al cliente o registra la consegna in studio."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 4,
        },
        {
            "scope": "preventivo",
            "state_code": "INVIATO",
            "label": "Inviato",
            "operational_meaning": "Preventivo trasmesso al cliente e in attesa di apertura o accettazione.",
            "is_active": True,
            "is_terminal": False,
            "allowed_actions": ["monitor_apertura", "registra_accettazione", "crea_revisione"],
            "next_actions": ["Monitora l'apertura o registra la risposta del cliente."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 5,
        },
        {
            "scope": "preventivo",
            "state_code": "APERTO",
            "label": "Aperto",
            "operational_meaning": "Preventivo aperto dal cliente sul portale ma non ancora accettato.",
            "is_active": True,
            "is_terminal": False,
            "allowed_actions": ["sollecito", "registra_accettazione", "crea_revisione"],
            "next_actions": ["Verifica se il cliente accetta o se serve una revisione."],
            "channel_modes": ["ONLINE"],
            "sort_order": 6,
        },
        {
            "scope": "preventivo",
            "state_code": "ACCETTATO",
            "label": "Accettato",
            "operational_meaning": "Preventivo accettato dal cliente e pronto per il conferimento di incarico.",
            "is_active": False,
            "is_terminal": False,
            "allowed_actions": ["crea_conferimento", "raccogli_firma", "apri_fascicolo"],
            "next_actions": ["Genera o completa il conferimento e raccogli la firma cliente."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 7,
        },
        {
            "scope": "preventivo",
            "state_code": "RIFIUTATO",
            "label": "Rifiutato",
            "operational_meaning": "Preventivo rifiutato dal cliente e da analizzare per eventuale revisione.",
            "is_active": False,
            "is_terminal": True,
            "allowed_actions": ["analizza_rifiuto", "crea_revisione"],
            "next_actions": ["Valuta una revisione o archivia l'offerta."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 8,
        },
        {
            "scope": "preventivo",
            "state_code": "SCADUTO",
            "label": "Scaduto",
            "operational_meaning": "Preventivo non accettato entro la data limite.",
            "is_active": False,
            "is_terminal": True,
            "allowed_actions": ["proroga", "crea_revisione", "archivia"],
            "next_actions": ["Valuta proroga o nuova versione del preventivo."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 9,
        },
        {
            "scope": "preventivo",
            "state_code": "REVISIONATO",
            "label": "Revisionato",
            "operational_meaning": "Preventivo sostituito da una versione successiva.",
            "is_active": False,
            "is_terminal": True,
            "allowed_actions": ["consulta_storico"],
            "next_actions": ["Lavora sulla revisione piu' recente collegata."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 10,
        },
        {
            "scope": "preventivo",
            "state_code": "CONVERTITO",
            "label": "Convertito",
            "operational_meaning": "Preventivo trasformato in incarico e fascicolo operativo.",
            "is_active": False,
            "is_terminal": True,
            "allowed_actions": ["consulta_conferimento", "consulta_fascicolo"],
            "next_actions": ["Prosegui dal fascicolo o dal conferimento collegato."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 11,
        },
        {
            "scope": "conferimento",
            "state_code": "ATTIVO",
            "label": "Attivo",
            "operational_meaning": "Conferimento creato e ancora nel ciclo di firma o apertura fascicolo.",
            "is_active": True,
            "is_terminal": False,
            "allowed_actions": ["raccogli_firma", "apri_fascicolo", "aggiorna_clausole"],
            "next_actions": ["Completa la firma cliente e poi apri il fascicolo."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 1,
        },
        {
            "scope": "conferimento",
            "state_code": "DEFINITO",
            "label": "Definito",
            "operational_meaning": "Conferimento completato e consolidato nel workflow di studio.",
            "is_active": False,
            "is_terminal": True,
            "allowed_actions": ["consulta_fascicolo", "consulta_storico"],
            "next_actions": ["Gestisci la pratica dal fascicolo operativo."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 2,
        },
        {
            "scope": "conferimento",
            "state_code": "REVOCATO",
            "label": "Revocato",
            "operational_meaning": "Conferimento interrotto o revocato dal cliente o dallo studio.",
            "is_active": False,
            "is_terminal": True,
            "allowed_actions": ["archivia", "documenta_esito"],
            "next_actions": ["Archivia il workflow e documenta la revoca."],
            "channel_modes": ["STUDIO", "ONLINE"],
            "sort_order": 3,
        },
    ]


def _rules_catalog() -> list[dict[str, Any]]:
    return [
        {
            "rule_code": "calcolo_imponibile",
            "category": "formula",
            "title": "Imponibile preventivo",
            "formula": "imponibile = somma(voci)",
            "operational_text": "L'imponibile nasce sempre dalla somma delle voci economiche del preventivo.",
            "warning_text": "Lex non deve inventare voci o importi mancanti fuori dal motore.",
            "deterministic": True,
            "sort_order": 1,
        },
        {
            "rule_code": "calcolo_cassa_forense",
            "category": "formula",
            "title": "Cassa Forense",
            "formula": "cassa_forense = imponibile × aliquota_cassa se applica_cassa",
            "operational_text": "Il contributo integrativo Cassa Forense dipende dall'aliquota tabellare e dal flag applica_cassa.",
            "warning_text": "Il modello linguistico puo' spiegare la logica ma non sostituire il calcolo deterministico.",
            "deterministic": True,
            "sort_order": 2,
        },
        {
            "rule_code": "calcolo_base_iva",
            "category": "formula",
            "title": "Base IVA",
            "formula": "base_iva = imponibile + cassa_forense",
            "operational_text": "La base IVA comprende imponibile e cassa forense quando attiva.",
            "warning_text": "",
            "deterministic": True,
            "sort_order": 3,
        },
        {
            "rule_code": "calcolo_iva",
            "category": "formula",
            "title": "IVA",
            "formula": "iva = base_iva × 0.22 se applica_iva",
            "operational_text": "L'IVA si applica sulla base imponibile fiscale se il preventivo la prevede.",
            "warning_text": "Non cambiare aliquote o imponibile fuori dal motore.",
            "deterministic": True,
            "sort_order": 4,
        },
        {
            "rule_code": "calcolo_totale",
            "category": "formula",
            "title": "Totale preventivo",
            "formula": "totale = base_iva + iva + anticipazioni_art15",
            "operational_text": "Le anticipazioni ex art. 15 si sommano dopo IVA e CPA perche' restano escluse dall'imponibile.",
            "warning_text": "Le anticipazioni vanno trattate come spese esenti e motivate.",
            "deterministic": True,
            "sort_order": 5,
        },
        {
            "rule_code": "workflow_preventivo_conferimento",
            "category": "workflow",
            "title": "Preventivo e conferimento sono distinti",
            "formula": "",
            "operational_text": "Il preventivo e' la proposta economica, il conferimento e' il passaggio successivo che puo' nascere dall'accettazione.",
            "warning_text": "Lex deve distinguere sempre proposta, accettazione, conferimento e fascicolo.",
            "deterministic": True,
            "sort_order": 10,
        },
        {
            "rule_code": "workflow_channel",
            "category": "workflow",
            "title": "Canale operativo",
            "formula": "workflow_channel ∈ {STUDIO, ONLINE}",
            "operational_text": "Il workflow e' sempre tracciato come Studio o Portale cliente.",
            "warning_text": "Nessun canale diverso deve essere inventato.",
            "deterministic": True,
            "sort_order": 11,
        },
        {
            "rule_code": "clausola_controversie_attivazione",
            "category": "clausole",
            "title": "Clausola controversie",
            "formula": "clausola attiva solo se modello != NESSUNA e testo coerente",
            "operational_text": "La clausola multistep mediazione/arbitrato si attiva solo con modello valido e testo confermato.",
            "warning_text": "Lex deve segnalare se la clausola e' attiva ma il testo non e' pronto.",
            "deterministic": True,
            "sort_order": 20,
        },
        {
            "rule_code": "firma_cliente_conferimento",
            "category": "workflow",
            "title": "Firma cliente prima dell'apertura",
            "formula": "",
            "operational_text": "Il conferimento richiede la firma cliente prima dell'apertura automatica del fascicolo.",
            "warning_text": "Se la firma manca, la prossima azione non puo' essere l'apertura pratica.",
            "deterministic": True,
            "sort_order": 21,
        },
        {
            "rule_code": "lex_no_free_fiscal_math",
            "category": "guardrail",
            "title": "Niente calcoli liberi del LLM",
            "formula": "",
            "operational_text": "Lex puo' spiegare il calcolo, guidare il wizard e segnalare dati mancanti, ma non deve ricalcolare liberamente valori fiscali fuori dal motore.",
            "warning_text": "Se mancano dati fiscali o voci, Lex deve chiedere o segnalare il dato mancante invece di inventarlo.",
            "deterministic": True,
            "sort_order": 30,
        },
    ]


def _practice_catalog_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    references = catalogo_riferimenti_normativi()
    refs_by_practice: dict[str, list[dict[str, Any]]] = {}
    for item in references:
        for practice_id in item.get("tipologie_ids") or []:
            refs_by_practice.setdefault(str(practice_id), []).append(item)
    for wizard_area, items in (catalogo_wizard() or {}).items():
        for item in items:
            practice_id = _clean_spaces(item.get("id"))
            taxonomy = {
                "area_tassonomica": _clean_spaces(item.get("area_tassonomica")),
                "macro_area_tassonomica": _clean_spaces(item.get("macro_area_tassonomica")),
                "sottobranca_tassonomica": _clean_spaces(item.get("sottobranca_tassonomica")),
                "tassonomia_codice": _clean_spaces(item.get("tassonomia_codice")),
            }
            parts: list[str] = [
                practice_id,
                _clean_spaces(item.get("label")),
                _clean_spaces(item.get("area")),
                wizard_area,
                _clean_spaces(item.get("summary")),
                _clean_spaces(item.get("when_to_use")),
                _clean_spaces(item.get("base_normativa")),
                _clean_spaces(item.get("tipo_compenso_default")),
                _clean_spaces(item.get("grado_default")),
            ]
            for key in ("fasi_default", "fasi_default_keys", "checklist_iniziale"):
                for value in item.get(key) or []:
                    text = _clean_spaces(value)
                    if text:
                        parts.append(text)
            for ref in refs_by_practice.get(practice_id, []):
                parts.append(_clean_spaces(ref.get("title")))
                parts.append(_clean_spaces(ref.get("article")))
            rows.append(
                {
                    "practice_id": practice_id,
                    "wizard_area": wizard_area,
                    "area": _clean_spaces(item.get("area")),
                    "label": _clean_spaces(item.get("label")),
                    "tipo_compenso_default": _clean_spaces(item.get("tipo_compenso_default")),
                    "richiede_valore": bool(item.get("richiede_valore")),
                    "grado_default": _clean_spaces(item.get("grado_default")),
                    "fasi_default": list(item.get("fasi_default") or []),
                    "fasi_default_keys": list(item.get("fasi_default_keys") or []),
                    "base_normativa": _clean_spaces(item.get("base_normativa")),
                    "summary": _clean_spaces(item.get("summary")),
                    "when_to_use": _clean_spaces(item.get("when_to_use")),
                    "checklist": list(item.get("checklist_iniziale") or []),
                    "normative_references": list(refs_by_practice.get(practice_id, [])),
                    "regole_tariffarie": list(item.get("regole_tariffarie") or []),
                    "tassonomia": taxonomy,
                    "search_text": "\n".join(part for part in parts if part).strip(),
                }
            )
    rows.sort(key=lambda item: (item.get("wizard_area") or "", item.get("label") or ""))
    return rows


def _payload_signature(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _record_search_text(parts: Iterable[Any]) -> str:
    return "\n".join(_clean_spaces(part) for part in parts if _clean_spaces(part)).strip()


def _resolve_wizard_step(
    preventivo: Any,
    *,
    practice_row: dict[str, Any] | None,
    conferimento: Any | None,
) -> tuple[str, str]:
    tipo_compenso = _clean_spaces(getattr(preventivo, "tipo_compenso", "")).lower()
    if not _clean_spaces(getattr(preventivo, "id_cliente", "")) or not _clean_spaces(getattr(preventivo, "oggetto", "")):
        return "cliente_fascicolo", "Completa cliente, fascicolo e oggetto."
    if not _clean_spaces(getattr(preventivo, "id_pratica", "")) or not _clean_spaces(getattr(preventivo, "area_pratica", "")):
        return "pratica_tassonomia", "Seleziona tipologia pratica e tassonomia."
    if not _clean_spaces(getattr(preventivo, "tipo_compenso", "")):
        return "tipo_compenso", "Definisci il tipo di compenso."
    if "orari" in tipo_compenso or "orario" in tipo_compenso or "compenso_a_tempo" in tipo_compenso or "compenso a tempo" in tipo_compenso:
        if float(getattr(preventivo, "tariffa_oraria", 0.0) or 0.0) <= 0 or float(getattr(preventivo, "ore_stimate", 0.0) or 0.0) <= 0:
            return "voci_economiche", "Completa tariffa oraria e ore stimate."
    richiede_valore = bool((practice_row or {}).get("richiede_valore"))
    if richiede_valore and float(getattr(preventivo, "valore_controversia", 0.0) or 0.0) <= 0:
        return "voci_economiche", "Manca il valore controversia richiesto dalla pratica."
    if not list(getattr(preventivo, "voci", []) or []):
        return "voci_economiche", "Inserisci le voci economiche del preventivo."
    if getattr(preventivo, "applica_cassa", None) is None or getattr(preventivo, "applica_iva", None) is None:
        return "fiscalita", "Verifica l'applicazione di CPA e IVA."
    if not list(getattr(preventivo, "piano_pagamenti", []) or []):
        return "piano_pagamenti", "Definisci almeno il piano pagamenti o l'acconto."
    if bool(getattr(preventivo, "clausola_controversie_attiva", False)) and not _clean_spaces(getattr(preventivo, "clausola_controversie_testo", "")):
        return "clausole_informativa", "Completa il testo della clausola sulle controversie."
    stato = _clean_spaces(getattr(getattr(preventivo, "stato", None), "value", getattr(preventivo, "stato", ""))).upper()
    if stato in {"BOZZA", "IN_CALCOLO", "GENERATO", "VERIFICATO"}:
        return "verifica_finale", "Controlla il riepilogo finale prima dell'invio."
    if stato in {"INVIATO", "APERTO", "ACCETTATO", "CONVERTITO"} or conferimento:
        return "invio_conversione", "Gestisci accettazione, conferimento, firma e conversione."
    return "verifica_finale", "Controlla la coerenza finale del preventivo."


def _preventivo_missing_fields(preventivo: Any, practice_row: dict[str, Any] | None) -> list[str]:
    missing: list[str] = []
    if not _clean_spaces(getattr(preventivo, "id_cliente", "")):
        missing.append("id_cliente")
    if not _clean_spaces(getattr(preventivo, "oggetto", "")):
        missing.append("oggetto")
    if not _clean_spaces(getattr(preventivo, "id_pratica", "")):
        missing.append("id_pratica")
    if not _clean_spaces(getattr(preventivo, "area_pratica", "")):
        missing.append("area_pratica")
    if not _clean_spaces(getattr(preventivo, "tipo_compenso", "")):
        missing.append("tipo_compenso")
    if not _clean_spaces(getattr(preventivo, "tipo_procedimento", "")):
        missing.append("tipo_procedimento")
    if _clean_spaces(getattr(preventivo, "id_pratica", "")) and not _clean_spaces(getattr(preventivo, "procedura_operativa_codice", "")):
        missing.append("procedura_operativa_codice")
    if _clean_spaces(getattr(preventivo, "id_pratica", "")) and not _clean_spaces(getattr(preventivo, "procedura_operativa_nome", "")):
        missing.append("procedura_operativa_nome")
    tipo_compenso = _clean_spaces(getattr(preventivo, "tipo_compenso", "")).lower()
    if "orari" in tipo_compenso or "orario" in tipo_compenso or "compenso_a_tempo" in tipo_compenso or "compenso a tempo" in tipo_compenso:
        if float(getattr(preventivo, "tariffa_oraria", 0.0) or 0.0) <= 0:
            missing.append("tariffa_oraria")
        if float(getattr(preventivo, "ore_stimate", 0.0) or 0.0) <= 0:
            missing.append("ore_stimate")
    if bool((practice_row or {}).get("richiede_valore")) and float(getattr(preventivo, "valore_controversia", 0.0) or 0.0) <= 0:
        missing.append("valore_controversia")
    if not list(getattr(preventivo, "voci", []) or []):
        missing.append("voci")
    if bool(getattr(preventivo, "clausola_controversie_attiva", False)) and not _clean_spaces(getattr(preventivo, "clausola_controversie_testo", "")):
        missing.append("clausola_controversie_testo")
    return missing


def _preventivo_warnings(preventivo: Any, conferimento: Any | None) -> list[str]:
    warnings: list[str] = []
    warnings.extend(str(item) for item in (getattr(preventivo, "warning_compenso_orario", []) or []) if item)
    if not list(getattr(preventivo, "piano_pagamenti", []) or []):
        warnings.append("Manca il piano pagamenti.")
    if float(getattr(preventivo, "anticipazioni_art15", 0.0) or 0.0) > 0:
        warnings.append("Verifica i giustificativi delle anticipazioni art. 15.")
    channel = _clean_spaces(getattr(preventivo, "workflow_channel", "")).upper() or "STUDIO"
    stato = _clean_spaces(getattr(getattr(preventivo, "stato", None), "value", getattr(preventivo, "stato", ""))).upper()
    if channel == "ONLINE" and stato in {"INVIATO", "APERTO"} and not _clean_spaces(getattr(preventivo, "token_portale", "")):
        warnings.append("Workflow online senza token portale attivo.")
    if stato == "ACCETTATO" and not conferimento:
        warnings.append("Preventivo accettato ma conferimento non ancora creato.")
    if stato == "CONVERTITO" and not _clean_spaces(getattr(preventivo, "id_fascicolo", "")):
        warnings.append("Preventivo convertito senza fascicolo collegato.")
    if _clean_spaces(getattr(preventivo, "id_pratica", "")) and not _clean_spaces(getattr(preventivo, "canale_operativo", "")):
        warnings.append("Procedura operativa senza canale operativo associato.")
    if _clean_spaces(getattr(preventivo, "id_pratica", "")) and not _clean_spaces(getattr(preventivo, "registro_operativo", "")):
        warnings.append("Procedura operativa senza registro operativo associato.")
    return warnings


def _preventivo_next_action(preventivo: Any, conferimento: Any | None) -> str:
    stato = _clean_spaces(getattr(getattr(preventivo, "stato", None), "value", getattr(preventivo, "stato", ""))).upper()
    if stato in {"BOZZA", "IN_CALCOLO"}:
        return "Completa i dati mancanti e chiudi il riepilogo economico."
    if stato == "GENERATO":
        return "Verifica il documento e prepara l'invio al cliente."
    if stato == "VERIFICATO":
        return "Invia il preventivo con il canale scelto."
    if stato in {"INVIATO", "APERTO"}:
        return "Monitora il cliente e registra accettazione o revisione."
    if stato == "ACCETTATO" and not conferimento:
        return "Crea il conferimento di incarico dal preventivo accettato."
    if stato == "ACCETTATO" and conferimento:
        return "Raccogli la firma del conferimento."
    if stato == "RIFIUTATO":
        return "Valuta se emettere una revisione o chiudere la trattativa."
    if stato == "SCADUTO":
        return "Valuta proroga o nuova emissione."
    if stato == "CONVERTITO":
        return "Continua dal fascicolo o dal conferimento collegato."
    return "Verifica il prossimo passaggio del workflow commerciale."


def _conferimento_warnings(conferimento: Any) -> list[str]:
    warnings: list[str] = []
    warnings.extend(str(item) for item in (getattr(conferimento, "warning_compenso_orario", []) or []) if item)
    if bool(getattr(conferimento, "firma_cliente_richiesta", False)) and not bool(getattr(conferimento, "firma_cliente_eseguita", False)):
        warnings.append("Firma cliente ancora da raccogliere.")
    if bool(getattr(conferimento, "clausola_controversie_attiva", False)) and not _clean_spaces(getattr(conferimento, "clausola_controversie_testo", "")):
        warnings.append("Clausola controversie attiva senza testo completo.")
    if not bool(getattr(conferimento, "informativa_art13_resa", False)):
        warnings.append("Informativa art. 13 non ancora marcata come resa.")
    if not bool(getattr(conferimento, "clausola_adr_resa", False)):
        warnings.append("Informativa ADR non ancora marcata come resa.")
    if _clean_spaces(getattr(conferimento, "id_pratica", "")) and not _clean_spaces(getattr(conferimento, "procedura_operativa_nome", "")):
        warnings.append("Conferimento senza procedura operativa associata.")
    return warnings


def _conferimento_next_action(conferimento: Any) -> str:
    if bool(getattr(conferimento, "firma_cliente_richiesta", False)) and not bool(getattr(conferimento, "firma_cliente_eseguita", False)):
        return "Raccogli la firma cliente sul conferimento."
    if not _clean_spaces(getattr(conferimento, "id_fascicolo", "")):
        return "Apri o collega il fascicolo operativo."
    return "Continua dal fascicolo o definisci il conferimento."


def _build_preventivo_record(
    preventivo: Any,
    *,
    practice_row: dict[str, Any] | None,
    conferimento: Any | None,
) -> dict[str, Any]:
    wizard_step, wizard_step_label = _resolve_wizard_step(
        preventivo,
        practice_row=practice_row,
        conferimento=conferimento,
    )
    missing_fields = _preventivo_missing_fields(preventivo, practice_row)
    warnings = _preventivo_warnings(preventivo, conferimento)
    numero = _clean_spaces(getattr(preventivo, "numero", ""))
    stato = _clean_spaces(getattr(getattr(preventivo, "stato", None), "value", getattr(preventivo, "stato", "")))
    workflow_channel = _clean_spaces(getattr(preventivo, "workflow_channel", "")) or "STUDIO"
    classificazioni_tassonomiche = list(
        getattr(preventivo, "classificazioni_tassonomiche", []) or []
    )
    parts = [
        numero,
        getattr(preventivo, "oggetto", ""),
        getattr(preventivo, "tipo_procedimento", ""),
        getattr(preventivo, "tipo_compenso", ""),
        getattr(preventivo, "area_pratica", ""),
        getattr(preventivo, "id_pratica", ""),
        getattr(preventivo, "procedura_operativa_codice", ""),
        getattr(preventivo, "procedura_operativa_nome", ""),
        getattr(preventivo, "subbranch_operativa_codice", ""),
        getattr(preventivo, "workflow_operativo_codice", ""),
        getattr(preventivo, "copertura_operativa", ""),
        getattr(preventivo, "canale_operativo", ""),
        getattr(preventivo, "registro_operativo", ""),
        stato,
        workflow_channel,
        wizard_step,
        wizard_step_label,
    ]
    for row in classificazioni_tassonomiche:
        if not isinstance(row, dict):
            continue
        parts.extend(
            [
                row.get("area_tassonomica", ""),
                row.get("macro_area_tassonomica", ""),
                row.get("sottobranca_tassonomica", ""),
                row.get("tipologia_pratica_label", ""),
                row.get("tipologia_pratica_id", ""),
            ]
        )
    for voce in getattr(preventivo, "voci", []) or []:
        parts.extend(
            [
                getattr(voce, "descrizione", ""),
                getattr(getattr(voce, "tipo", None), "value", getattr(voce, "tipo", "")),
            ]
        )
    return {
        "preventivo_id": _clean_spaces(getattr(preventivo, "id", "")),
        "numero": numero,
        "data_emissione": _clean_spaces(getattr(preventivo, "data_emissione", "")),
        "data_scadenza": _clean_spaces(getattr(preventivo, "data_scadenza", "")),
        "id_cliente": _clean_spaces(getattr(preventivo, "id_cliente", "")),
        "id_fascicolo": _clean_spaces(getattr(preventivo, "id_fascicolo", "")),
        "oggetto": _clean_spaces(getattr(preventivo, "oggetto", "")),
        "stato": stato,
        "workflow_channel": workflow_channel,
        "workflow_channel_label": _channel_label(workflow_channel),
        "tipo_compenso": _clean_spaces(getattr(preventivo, "tipo_compenso", "")),
        "tipo_procedimento": _clean_spaces(getattr(preventivo, "tipo_procedimento", "")),
        "area_pratica": _clean_spaces(getattr(preventivo, "area_pratica", "")),
        "id_pratica": _clean_spaces(getattr(preventivo, "id_pratica", "")),
        "procedura_operativa_codice": _clean_spaces(getattr(preventivo, "procedura_operativa_codice", "")),
        "procedura_operativa_nome": _clean_spaces(getattr(preventivo, "procedura_operativa_nome", "")),
        "subbranch_operativa_codice": _clean_spaces(getattr(preventivo, "subbranch_operativa_codice", "")),
        "workflow_operativo_codice": _clean_spaces(getattr(preventivo, "workflow_operativo_codice", "")),
        "copertura_operativa": _clean_spaces(getattr(preventivo, "copertura_operativa", "")),
        "canale_operativo": _clean_spaces(getattr(preventivo, "canale_operativo", "")),
        "registro_operativo": _clean_spaces(getattr(preventivo, "registro_operativo", "")),
        "valore_controversia": float(getattr(preventivo, "valore_controversia", 0.0) or 0.0),
        "tariffa_oraria": float(getattr(preventivo, "tariffa_oraria", 0.0) or 0.0),
        "ore_stimate": float(getattr(preventivo, "ore_stimate", 0.0) or 0.0),
        "criterio_arrotondamento_orario": _clean_spaces(getattr(preventivo, "criterio_arrotondamento_orario", "")),
        "minuti_stimati": int(getattr(preventivo, "minuti_stimati", 0) or 0),
        "ore_fatturabili_calcolate": float(getattr(preventivo, "ore_fatturabili_calcolate", 0.0) or 0.0),
        "compenso_orario_base": float(getattr(preventivo, "compenso_orario_base", 0.0) or 0.0),
        "massimale_ore": float(getattr(preventivo, "massimale_ore", 0.0) or 0.0),
        "soglia_preapprovazione_ore": float(getattr(preventivo, "soglia_preapprovazione_ore", 0.0) or 0.0),
        "warning_compenso_orario": list(getattr(preventivo, "warning_compenso_orario", []) or []),
        "complessita": _clean_spaces(getattr(preventivo, "complessita", "")),
        "applica_cassa": bool(getattr(preventivo, "applica_cassa", True)),
        "applica_iva": bool(getattr(preventivo, "applica_iva", True)),
        "anticipazioni_art15": float(getattr(preventivo, "anticipazioni_art15", 0.0) or 0.0),
        "imponibile": float(getattr(preventivo, "imponibile", 0.0) or 0.0),
        "cassa_forense": float(getattr(preventivo, "cassa_forense", 0.0) or 0.0),
        "base_iva": float(getattr(preventivo, "base_iva", 0.0) or 0.0),
        "iva": float(getattr(preventivo, "iva", 0.0) or 0.0),
        "totale": float(getattr(preventivo, "totale", 0.0) or 0.0),
        "piano_pagamenti_count": len(list(getattr(preventivo, "piano_pagamenti", []) or [])),
        "clausola_controversie_attiva": bool(getattr(preventivo, "clausola_controversie_attiva", False)),
        "clausola_controversie_modello": _clean_spaces(getattr(preventivo, "clausola_controversie_modello", "")),
        "token_portale_present": bool(_clean_spaces(getattr(preventivo, "token_portale", ""))),
        "inviato_cliente_il": _clean_spaces(getattr(preventivo, "inviato_cliente_il", "")),
        "accettato_il": _clean_spaces(getattr(preventivo, "accettato_il", "")),
        "versione": int(getattr(preventivo, "versione", 1) or 1),
        "id_preventivo_precedente": _clean_spaces(getattr(preventivo, "id_preventivo_precedente", "")),
        "wizard_step": wizard_step,
        "wizard_step_label": wizard_step_label,
        "classificazioni_tassonomiche": classificazioni_tassonomiche,
        "classificazioni_tassonomiche_count": len(classificazioni_tassonomiche),
        "campi_mancanti": missing_fields,
        "warning": warnings,
        "next_action": _preventivo_next_action(preventivo, conferimento),
        "search_text": _record_search_text(parts),
    }


def _build_conferimento_record(conferimento: Any) -> dict[str, Any]:
    workflow_channel = _clean_spaces(getattr(conferimento, "workflow_channel", "")) or "STUDIO"
    stato = _clean_spaces(getattr(getattr(conferimento, "stato", None), "value", getattr(conferimento, "stato", "")))
    classificazioni_tassonomiche = list(
        getattr(conferimento, "classificazioni_tassonomiche", []) or []
    )
    parts = [
        getattr(conferimento, "numero", ""),
        getattr(conferimento, "oggetto", ""),
        getattr(conferimento, "tipo_procedimento", ""),
        getattr(conferimento, "tipo_compenso", ""),
        getattr(conferimento, "area_pratica", ""),
        getattr(conferimento, "id_pratica", ""),
        getattr(conferimento, "procedura_operativa_codice", ""),
        getattr(conferimento, "procedura_operativa_nome", ""),
        getattr(conferimento, "subbranch_operativa_codice", ""),
        getattr(conferimento, "workflow_operativo_codice", ""),
        getattr(conferimento, "copertura_operativa", ""),
        getattr(conferimento, "canale_operativo", ""),
        getattr(conferimento, "registro_operativo", ""),
        stato,
        workflow_channel,
    ]
    for row in classificazioni_tassonomiche:
        if not isinstance(row, dict):
            continue
        parts.extend(
            [
                row.get("area_tassonomica", ""),
                row.get("macro_area_tassonomica", ""),
                row.get("sottobranca_tassonomica", ""),
                row.get("tipologia_pratica_label", ""),
                row.get("tipologia_pratica_id", ""),
            ]
        )
    return {
        "conferimento_id": _clean_spaces(getattr(conferimento, "id", "")),
        "numero": _clean_spaces(getattr(conferimento, "numero", "")),
        "data_incarico": _clean_spaces(getattr(conferimento, "data_incarico", "")),
        "id_preventivo": _clean_spaces(getattr(conferimento, "id_preventivo", "")),
        "id_cliente": _clean_spaces(getattr(conferimento, "id_cliente", "")),
        "id_fascicolo": _clean_spaces(getattr(conferimento, "id_fascicolo", "")),
        "oggetto": _clean_spaces(getattr(conferimento, "oggetto", "")),
        "stato": stato,
        "workflow_channel": workflow_channel,
        "workflow_channel_label": _channel_label(workflow_channel),
        "tipo_compenso": _clean_spaces(getattr(conferimento, "tipo_compenso", "")),
        "tipo_procedimento": _clean_spaces(getattr(conferimento, "tipo_procedimento", "")),
        "area_pratica": _clean_spaces(getattr(conferimento, "area_pratica", "")),
        "id_pratica": _clean_spaces(getattr(conferimento, "id_pratica", "")),
        "procedura_operativa_codice": _clean_spaces(getattr(conferimento, "procedura_operativa_codice", "")),
        "procedura_operativa_nome": _clean_spaces(getattr(conferimento, "procedura_operativa_nome", "")),
        "subbranch_operativa_codice": _clean_spaces(getattr(conferimento, "subbranch_operativa_codice", "")),
        "workflow_operativo_codice": _clean_spaces(getattr(conferimento, "workflow_operativo_codice", "")),
        "copertura_operativa": _clean_spaces(getattr(conferimento, "copertura_operativa", "")),
        "canale_operativo": _clean_spaces(getattr(conferimento, "canale_operativo", "")),
        "registro_operativo": _clean_spaces(getattr(conferimento, "registro_operativo", "")),
        "compenso_pattuito": float(getattr(conferimento, "compenso_pattuito", 0.0) or 0.0),
        "criterio_arrotondamento_orario": _clean_spaces(getattr(conferimento, "criterio_arrotondamento_orario", "")),
        "massimale_ore": float(getattr(conferimento, "massimale_ore", 0.0) or 0.0),
        "soglia_preapprovazione_ore": float(getattr(conferimento, "soglia_preapprovazione_ore", 0.0) or 0.0),
        "warning_compenso_orario": list(getattr(conferimento, "warning_compenso_orario", []) or []),
        "informativa_art13_resa": bool(getattr(conferimento, "informativa_art13_resa", False)),
        "clausola_adr_resa": bool(getattr(conferimento, "clausola_adr_resa", False)),
        "firma_cliente_richiesta": bool(getattr(conferimento, "firma_cliente_richiesta", True)),
        "firma_cliente_eseguita": bool(getattr(conferimento, "firma_cliente_eseguita", False)),
        "firma_cliente_il": _clean_spaces(getattr(conferimento, "firma_cliente_il", "")),
        "fascicolo_aperto_il": _clean_spaces(getattr(conferimento, "fascicolo_aperto_il", "")),
        "clausola_controversie_attiva": bool(getattr(conferimento, "clausola_controversie_attiva", False)),
        "clausola_controversie_modello": _clean_spaces(getattr(conferimento, "clausola_controversie_modello", "")),
        "classificazioni_tassonomiche": classificazioni_tassonomiche,
        "classificazioni_tassonomiche_count": len(classificazioni_tassonomiche),
        "warning": _conferimento_warnings(conferimento),
        "next_action": _conferimento_next_action(conferimento),
        "search_text": _record_search_text(parts),
    }


class GestionePreventiviRepository:
    def __init__(
        self,
        db_path: str,
        *,
        json_path: str | None = None,
        workflow_states_json_path: str | None = None,
        field_map_json_path: str | None = None,
        rules_json_path: str | None = None,
        schema_path: Path | None = None,
    ):
        self.db_path = str(db_path)
        self.json_path = str(json_path or "")
        self.workflow_states_json_path = str(workflow_states_json_path or "")
        self.field_map_json_path = str(field_map_json_path or "")
        self.rules_json_path = str(rules_json_path or "")
        self.schema_path = Path(schema_path or SCHEMA_PREVENTIVI_REPOSITORY)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        for raw_path in (
            self.json_path,
            self.workflow_states_json_path,
            self.field_map_json_path,
            self.rules_json_path,
        ):
            if raw_path:
                Path(raw_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _ensure_table_columns(self, conn: sqlite3.Connection, table_name: str, columns: dict[str, str]) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        for column_name, ddl in columns.items():
            if column_name in existing:
                continue
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def _ensure_schema(self) -> None:
        schema_sql = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema_sql)
            self._ensure_table_columns(
                conn,
                "preventivi_records",
                {
                    "procedura_operativa_codice": "TEXT NOT NULL DEFAULT ''",
                    "procedura_operativa_nome": "TEXT NOT NULL DEFAULT ''",
                    "subbranch_operativa_codice": "TEXT NOT NULL DEFAULT ''",
                    "workflow_operativo_codice": "TEXT NOT NULL DEFAULT ''",
                    "copertura_operativa": "TEXT NOT NULL DEFAULT ''",
                    "canale_operativo": "TEXT NOT NULL DEFAULT ''",
                    "registro_operativo": "TEXT NOT NULL DEFAULT ''",
                    "classificazioni_tassonomiche_json": "TEXT NOT NULL DEFAULT '[]'",
                    "classificazioni_tassonomiche_count": "INTEGER NOT NULL DEFAULT 0",
                    "criterio_arrotondamento_orario": "TEXT NOT NULL DEFAULT ''",
                    "minuti_stimati": "INTEGER NOT NULL DEFAULT 0",
                    "ore_fatturabili_calcolate": "REAL NOT NULL DEFAULT 0",
                    "compenso_orario_base": "REAL NOT NULL DEFAULT 0",
                    "massimale_ore": "REAL NOT NULL DEFAULT 0",
                    "soglia_preapprovazione_ore": "REAL NOT NULL DEFAULT 0",
                    "warning_compenso_orario_json": "TEXT NOT NULL DEFAULT '[]'",
                },
            )
            self._ensure_table_columns(
                conn,
                "conferimenti_records",
                {
                    "procedura_operativa_codice": "TEXT NOT NULL DEFAULT ''",
                    "procedura_operativa_nome": "TEXT NOT NULL DEFAULT ''",
                    "subbranch_operativa_codice": "TEXT NOT NULL DEFAULT ''",
                    "workflow_operativo_codice": "TEXT NOT NULL DEFAULT ''",
                    "copertura_operativa": "TEXT NOT NULL DEFAULT ''",
                    "canale_operativo": "TEXT NOT NULL DEFAULT ''",
                    "registro_operativo": "TEXT NOT NULL DEFAULT ''",
                    "classificazioni_tassonomiche_json": "TEXT NOT NULL DEFAULT '[]'",
                    "classificazioni_tassonomiche_count": "INTEGER NOT NULL DEFAULT 0",
                    "criterio_arrotondamento_orario": "TEXT NOT NULL DEFAULT ''",
                    "massimale_ore": "REAL NOT NULL DEFAULT 0",
                    "soglia_preapprovazione_ore": "REAL NOT NULL DEFAULT 0",
                    "warning_compenso_orario_json": "TEXT NOT NULL DEFAULT '[]'",
                },
            )
            conn.commit()

    def _get_meta(self, key: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT meta_value FROM preventivi_repository_meta WHERE meta_key = ?",
                (_clean_spaces(key),),
            ).fetchone()
        return _clean_spaces(row["meta_value"]) if row else ""

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO preventivi_repository_meta(meta_key, meta_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(meta_key) DO UPDATE SET
                meta_value = excluded.meta_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (_clean_spaces(key), _clean_spaces(value)),
        )

    def storage_stats(self) -> dict[str, Any]:
        tables = (
            "preventivi_workflow_states",
            "preventivi_field_map",
            "preventivi_rules",
            "preventivi_wizard_steps",
            "preventivi_practice_catalog",
            "preventivi_records",
            "conferimenti_records",
        )
        stats: dict[str, Any] = {
            "db_path": self.db_path,
            "json_path": self.json_path,
            "workflow_states_json_path": self.workflow_states_json_path,
            "field_map_json_path": self.field_map_json_path,
            "rules_json_path": self.rules_json_path,
        }
        with self._connect() as conn:
            for table_name in tables:
                stats[table_name] = int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        stats["source_signature"] = self._get_meta("source_signature")
        return stats

    def synchronize_runtime(
        self,
        *,
        preventivi: Iterable[Any],
        conferimenti: Iterable[Any],
        preventivo_model: type[Any],
        conferimento_model: type[Any],
        export_json: bool = True,
    ) -> dict[str, Any]:
        payload = self._build_payload(
            preventivi=preventivi,
            conferimenti=conferimenti,
            preventivo_model=preventivo_model,
            conferimento_model=conferimento_model,
        )
        signature = _payload_signature(payload)
        current_signature = self._get_meta("source_signature")
        if signature == current_signature and int(self.storage_stats().get("preventivi_records", 0)) == len(payload["preventivi"]):
            if export_json:
                self.export_repository_json()
                self.export_split_jsons()
            return self.storage_stats()
        self.rebuild_from_payload(payload, source_label="preventivi_runtime")
        if export_json:
            self.export_repository_json()
            self.export_split_jsons()
        return self.storage_stats()

    def _build_payload(
        self,
        *,
        preventivi: Iterable[Any],
        conferimenti: Iterable[Any],
        preventivo_model: type[Any],
        conferimento_model: type[Any],
    ) -> dict[str, Any]:
        practice_rows = _practice_catalog_rows()
        practice_index = {row["practice_id"]: row for row in practice_rows}
        conferimenti_rows = list(conferimenti)
        conferimenti_by_preventivo: dict[str, Any] = {}
        for conferimento in conferimenti_rows:
            preventivo_id = _clean_spaces(getattr(conferimento, "id_preventivo", ""))
            if preventivo_id and preventivo_id not in conferimenti_by_preventivo:
                conferimenti_by_preventivo[preventivo_id] = conferimento
        preventivo_rows = [
            _build_preventivo_record(
                preventivo,
                practice_row=practice_index.get(_clean_spaces(getattr(preventivo, "id_pratica", ""))),
                conferimento=conferimenti_by_preventivo.get(_clean_spaces(getattr(preventivo, "id", ""))),
            )
            for preventivo in list(preventivi)
        ]
        conferimento_rows = [_build_conferimento_record(conferimento) for conferimento in conferimenti_rows]
        return {
            "workflow_states": _workflow_states_catalog(),
            "field_map": {
                "preventivo": _build_field_map(preventivo_model, scope="preventivo"),
                "conferimento": _build_field_map(conferimento_model, scope="conferimento"),
            },
            "rules": _rules_catalog(),
            "wizard_steps": _wizard_steps(),
            "practice_catalog": practice_rows,
            "preventivi": preventivo_rows,
            "conferimenti": conferimento_rows,
        }

    def rebuild_from_payload(self, payload: dict[str, Any], *, source_label: str = "preventivi_runtime") -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM preventivi_workflow_states")
            conn.execute("DELETE FROM preventivi_field_map")
            conn.execute("DELETE FROM preventivi_rules")
            conn.execute("DELETE FROM preventivi_wizard_steps")
            conn.execute("DELETE FROM preventivi_practice_catalog")
            conn.execute("DELETE FROM preventivi_records")
            conn.execute("DELETE FROM conferimenti_records")

            for row in payload.get("workflow_states") or []:
                conn.execute(
                    """
                    INSERT INTO preventivi_workflow_states (
                        scope, state_code, label, operational_meaning, is_active,
                        is_terminal, allowed_actions_json, next_actions_json,
                        channel_modes_json, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("scope"),
                        row.get("state_code"),
                        row.get("label"),
                        row.get("operational_meaning"),
                        1 if row.get("is_active") else 0,
                        1 if row.get("is_terminal") else 0,
                        _to_json(row.get("allowed_actions") or []),
                        _to_json(row.get("next_actions") or []),
                        _to_json(row.get("channel_modes") or []),
                        int(row.get("sort_order") or 0),
                    ),
                )

            for rows in (payload.get("field_map") or {}).values():
                for row in rows or []:
                    conn.execute(
                        """
                        INSERT INTO preventivi_field_map (
                            scope, field_name, label, field_type, section_name, help_text,
                            required_runtime, derived, source_model, step_key,
                            enum_values_json, sort_order
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row.get("scope"),
                            row.get("field_name"),
                            row.get("label"),
                            row.get("field_type"),
                            row.get("section_name"),
                            row.get("help_text") or "",
                            1 if row.get("required_runtime") else 0,
                            1 if row.get("derived") else 0,
                            row.get("source_model"),
                            row.get("step_key") or "",
                            _to_json(row.get("enum_values") or []),
                            int(row.get("sort_order") or 0),
                        ),
                    )

            for row in payload.get("rules") or []:
                conn.execute(
                    """
                    INSERT INTO preventivi_rules (
                        rule_code, category, title, formula, operational_text,
                        warning_text, deterministic, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("rule_code"),
                        row.get("category"),
                        row.get("title"),
                        row.get("formula") or "",
                        row.get("operational_text"),
                        row.get("warning_text") or "",
                        1 if row.get("deterministic", True) else 0,
                        int(row.get("sort_order") or 0),
                    ),
                )

            for row in payload.get("wizard_steps") or []:
                conn.execute(
                    """
                    INSERT INTO preventivi_wizard_steps (
                        step_key, label, description, section_names_json, sort_order
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("step_key"),
                        row.get("label"),
                        row.get("description"),
                        _to_json(row.get("section_names") or []),
                        int(row.get("sort_order") or 0),
                    ),
                )

            for row in payload.get("practice_catalog") or []:
                conn.execute(
                    """
                    INSERT INTO preventivi_practice_catalog (
                        practice_id, wizard_area, area, label, tipo_compenso_default,
                        richiede_valore, grado_default, fasi_default_json,
                        fasi_default_keys_json, base_normativa, summary, when_to_use,
                        checklist_json, normative_references_json, regole_tariffarie_json,
                        tassonomia_json, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("practice_id"),
                        row.get("wizard_area"),
                        row.get("area"),
                        row.get("label"),
                        row.get("tipo_compenso_default"),
                        1 if row.get("richiede_valore") else 0,
                        row.get("grado_default"),
                        _to_json(row.get("fasi_default") or []),
                        _to_json(row.get("fasi_default_keys") or []),
                        row.get("base_normativa") or "",
                        row.get("summary") or "",
                        row.get("when_to_use") or "",
                        _to_json(row.get("checklist") or []),
                        _to_json(row.get("normative_references") or []),
                        _to_json(row.get("regole_tariffarie") or []),
                        _to_json(row.get("tassonomia") or {}),
                        row.get("search_text") or "",
                    ),
                )

            for row in payload.get("preventivi") or []:
                columns = [
                    "preventivo_id", "numero", "data_emissione", "data_scadenza", "id_cliente",
                    "id_fascicolo", "oggetto", "stato", "workflow_channel", "workflow_channel_label",
                    "tipo_compenso", "tipo_procedimento", "area_pratica", "id_pratica",
                    "procedura_operativa_codice", "procedura_operativa_nome", "subbranch_operativa_codice",
                    "workflow_operativo_codice", "copertura_operativa", "canale_operativo", "registro_operativo",
                    "valore_controversia", "tariffa_oraria", "ore_stimate", "complessita",
                    "criterio_arrotondamento_orario", "minuti_stimati", "ore_fatturabili_calcolate",
                    "compenso_orario_base", "massimale_ore", "soglia_preapprovazione_ore",
                    "warning_compenso_orario_json",
                    "applica_cassa", "applica_iva", "anticipazioni_art15", "imponibile", "cassa_forense",
                    "base_iva", "iva", "totale", "piano_pagamenti_count", "clausola_controversie_attiva",
                    "clausola_controversie_modello", "token_portale_present", "inviato_cliente_il", "accettato_il",
                    "versione", "id_preventivo_precedente", "wizard_step", "wizard_step_label",
                    "classificazioni_tassonomiche_json", "classificazioni_tassonomiche_count",
                    "campi_mancanti_json", "warning_json", "next_action", "search_text",
                ]
                conn.execute(
                    f"INSERT INTO preventivi_records ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                    (
                        row.get("preventivo_id"), row.get("numero"), row.get("data_emissione"), row.get("data_scadenza"),
                        row.get("id_cliente"), row.get("id_fascicolo"), row.get("oggetto"), row.get("stato"),
                        row.get("workflow_channel"), row.get("workflow_channel_label"), row.get("tipo_compenso"),
                        row.get("tipo_procedimento"), row.get("area_pratica"), row.get("id_pratica"),
                        row.get("procedura_operativa_codice") or "", row.get("procedura_operativa_nome") or "",
                        row.get("subbranch_operativa_codice") or "", row.get("workflow_operativo_codice") or "",
                        row.get("copertura_operativa") or "", row.get("canale_operativo") or "",
                        row.get("registro_operativo") or "", float(row.get("valore_controversia") or 0.0),
                        float(row.get("tariffa_oraria") or 0.0), float(row.get("ore_stimate") or 0.0),
                        row.get("complessita") or "",
                        row.get("criterio_arrotondamento_orario") or "",
                        int(row.get("minuti_stimati") or 0),
                        float(row.get("ore_fatturabili_calcolate") or 0.0),
                        float(row.get("compenso_orario_base") or 0.0),
                        float(row.get("massimale_ore") or 0.0),
                        float(row.get("soglia_preapprovazione_ore") or 0.0),
                        _to_json(row.get("warning_compenso_orario") or []),
                        1 if row.get("applica_cassa") else 0,
                        1 if row.get("applica_iva") else 0, float(row.get("anticipazioni_art15") or 0.0),
                        float(row.get("imponibile") or 0.0), float(row.get("cassa_forense") or 0.0),
                        float(row.get("base_iva") or 0.0), float(row.get("iva") or 0.0), float(row.get("totale") or 0.0),
                        int(row.get("piano_pagamenti_count") or 0), 1 if row.get("clausola_controversie_attiva") else 0,
                        row.get("clausola_controversie_modello") or "", 1 if row.get("token_portale_present") else 0,
                        row.get("inviato_cliente_il") or "", row.get("accettato_il") or "", int(row.get("versione") or 1),
                        row.get("id_preventivo_precedente") or "", row.get("wizard_step") or "", row.get("wizard_step_label") or "",
                        _to_json(row.get("classificazioni_tassonomiche") or []),
                        int(row.get("classificazioni_tassonomiche_count") or 0),
                        _to_json(row.get("campi_mancanti") or []), _to_json(row.get("warning") or []),
                        row.get("next_action") or "", row.get("search_text") or "",
                    ),
                )

            for row in payload.get("conferimenti") or []:
                columns = [
                    "conferimento_id", "numero", "data_incarico", "id_preventivo", "id_cliente",
                    "id_fascicolo", "oggetto", "stato", "workflow_channel", "workflow_channel_label",
                    "tipo_compenso", "tipo_procedimento", "area_pratica", "id_pratica",
                    "procedura_operativa_codice", "procedura_operativa_nome", "subbranch_operativa_codice",
                    "workflow_operativo_codice", "copertura_operativa", "canale_operativo", "registro_operativo",
                    "compenso_pattuito", "informativa_art13_resa", "clausola_adr_resa",
                    "criterio_arrotondamento_orario", "massimale_ore", "soglia_preapprovazione_ore",
                    "warning_compenso_orario_json",
                    "firma_cliente_richiesta", "firma_cliente_eseguita", "firma_cliente_il", "fascicolo_aperto_il",
                    "clausola_controversie_attiva", "clausola_controversie_modello",
                    "classificazioni_tassonomiche_json", "classificazioni_tassonomiche_count",
                    "warning_json", "next_action", "search_text",
                ]
                conn.execute(
                    f"INSERT INTO conferimenti_records ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                    (
                        row.get("conferimento_id"), row.get("numero"), row.get("data_incarico"), row.get("id_preventivo"),
                        row.get("id_cliente"), row.get("id_fascicolo"), row.get("oggetto"), row.get("stato"),
                        row.get("workflow_channel"), row.get("workflow_channel_label"), row.get("tipo_compenso"),
                        row.get("tipo_procedimento"), row.get("area_pratica"), row.get("id_pratica"),
                        row.get("procedura_operativa_codice") or "", row.get("procedura_operativa_nome") or "",
                        row.get("subbranch_operativa_codice") or "", row.get("workflow_operativo_codice") or "",
                        row.get("copertura_operativa") or "", row.get("canale_operativo") or "",
                        row.get("registro_operativo") or "", float(row.get("compenso_pattuito") or 0.0),
                        1 if row.get("informativa_art13_resa") else 0, 1 if row.get("clausola_adr_resa") else 0,
                        row.get("criterio_arrotondamento_orario") or "",
                        float(row.get("massimale_ore") or 0.0),
                        float(row.get("soglia_preapprovazione_ore") or 0.0),
                        _to_json(row.get("warning_compenso_orario") or []),
                        1 if row.get("firma_cliente_richiesta") else 0, 1 if row.get("firma_cliente_eseguita") else 0,
                        row.get("firma_cliente_il") or "", row.get("fascicolo_aperto_il") or "",
                        1 if row.get("clausola_controversie_attiva") else 0, row.get("clausola_controversie_modello") or "",
                        _to_json(row.get("classificazioni_tassonomiche") or []),
                        int(row.get("classificazioni_tassonomiche_count") or 0),
                        _to_json(row.get("warning") or []), row.get("next_action") or "", row.get("search_text") or "",
                    ),
                )

            self._set_meta(conn, "source_signature", _payload_signature(payload))
            self._set_meta(conn, "source_label", source_label)
            conn.commit()

    def load_repository_payload(self) -> dict[str, Any]:
        with self._connect() as conn:
            workflow_states = [
                {
                    **_drop_keys(row, "allowed_actions_json", "next_actions_json", "channel_modes_json"),
                    "allowed_actions": json.loads(row["allowed_actions_json"] or "[]"),
                    "next_actions": json.loads(row["next_actions_json"] or "[]"),
                    "channel_modes": json.loads(row["channel_modes_json"] or "[]"),
                }
                for row in conn.execute(
                    "SELECT * FROM preventivi_workflow_states ORDER BY scope, sort_order, state_code"
                ).fetchall()
            ]
            field_map_rows = [
                {
                    **_drop_keys(row, "enum_values_json"),
                    "enum_values": json.loads(row["enum_values_json"] or "[]"),
                }
                for row in conn.execute(
                    "SELECT * FROM preventivi_field_map ORDER BY scope, sort_order, field_name"
                ).fetchall()
            ]
            rules = [dict(row) for row in conn.execute("SELECT * FROM preventivi_rules ORDER BY sort_order, rule_code").fetchall()]
            wizard_steps = [
                {
                    **_drop_keys(row, "section_names_json"),
                    "section_names": json.loads(row["section_names_json"] or "[]"),
                }
                for row in conn.execute(
                    "SELECT * FROM preventivi_wizard_steps ORDER BY sort_order, step_key"
                ).fetchall()
            ]
            practice_catalog = [
                {
                    **_drop_keys(
                        row,
                        "fasi_default_json",
                        "fasi_default_keys_json",
                        "checklist_json",
                        "normative_references_json",
                        "regole_tariffarie_json",
                        "tassonomia_json",
                    ),
                    "fasi_default": json.loads(row["fasi_default_json"] or "[]"),
                    "fasi_default_keys": json.loads(row["fasi_default_keys_json"] or "[]"),
                    "checklist": json.loads(row["checklist_json"] or "[]"),
                    "normative_references": json.loads(row["normative_references_json"] or "[]"),
                    "regole_tariffarie": json.loads(row["regole_tariffarie_json"] or "[]"),
                    "tassonomia": json.loads(row["tassonomia_json"] or "{}"),
                }
                for row in conn.execute(
                    "SELECT * FROM preventivi_practice_catalog ORDER BY wizard_area, label"
                ).fetchall()
            ]
            preventivi = [
                {
                    **_drop_keys(
                        row,
                        "campi_mancanti_json",
                        "warning_json",
                        "warning_compenso_orario_json",
                        "classificazioni_tassonomiche_json",
                    ),
                    "classificazioni_tassonomiche": json.loads(
                        row["classificazioni_tassonomiche_json"] or "[]"
                    ),
                    "campi_mancanti": json.loads(row["campi_mancanti_json"] or "[]"),
                    "warning": json.loads(row["warning_json"] or "[]"),
                    "warning_compenso_orario": json.loads(row["warning_compenso_orario_json"] or "[]"),
                }
                for row in conn.execute(
                    "SELECT * FROM preventivi_records ORDER BY data_emissione DESC, numero DESC"
                ).fetchall()
            ]
            conferimenti = [
                {
                    **_drop_keys(
                        row,
                        "warning_json",
                        "warning_compenso_orario_json",
                        "classificazioni_tassonomiche_json",
                    ),
                    "classificazioni_tassonomiche": json.loads(
                        row["classificazioni_tassonomiche_json"] or "[]"
                    ),
                    "warning": json.loads(row["warning_json"] or "[]"),
                    "warning_compenso_orario": json.loads(row["warning_compenso_orario_json"] or "[]"),
                }
                for row in conn.execute(
                    "SELECT * FROM conferimenti_records ORDER BY data_incarico DESC, numero DESC"
                ).fetchall()
            ]
        return {
            "source": self._get_meta("source_label") or "preventivi_runtime",
            "counts": {
                "workflow_states": len(workflow_states),
                "field_map": len(field_map_rows),
                "rules": len(rules),
                "wizard_steps": len(wizard_steps),
                "practice_catalog": len(practice_catalog),
                "preventivi": len(preventivi),
                "conferimenti": len(conferimenti),
            },
            "workflow_states": workflow_states,
            "field_map": {
                "preventivo": [row for row in field_map_rows if row["scope"] == "preventivo"],
                "conferimento": [row for row in field_map_rows if row["scope"] == "conferimento"],
            },
            "rules": rules,
            "wizard_steps": wizard_steps,
            "practice_catalog": practice_catalog,
            "preventivi": preventivi,
            "conferimenti": conferimenti,
        }

    def export_repository_json(self, path: str | None = None) -> str:
        target = Path(path or self.json_path)
        if not str(target):
            raise ValueError("Percorso JSON repository preventivi non configurato.")
        payload = self.load_repository_payload()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)

    def export_split_jsons(self, base_dir: str | None = None) -> dict[str, str]:
        payload = self.load_repository_payload()
        if base_dir:
            base = Path(base_dir)
            paths = {
                "repository": str(base / "preventivi_repository.json"),
                "workflow_states": str(base / "preventivi_workflow_states.json"),
                "field_map": str(base / "preventivi_field_map.json"),
                "rules": str(base / "preventivi_rules.json"),
            }
        else:
            paths = {
                "repository": self.json_path,
                "workflow_states": self.workflow_states_json_path,
                "field_map": self.field_map_json_path,
                "rules": self.rules_json_path,
            }
        if paths["repository"]:
            Path(paths["repository"]).parent.mkdir(parents=True, exist_ok=True)
            Path(paths["repository"]).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if paths["workflow_states"]:
            Path(paths["workflow_states"]).parent.mkdir(parents=True, exist_ok=True)
            Path(paths["workflow_states"]).write_text(
                json.dumps(
                    {
                        "source": payload["source"],
                        "count": len(payload["workflow_states"]),
                        "workflow_states": payload["workflow_states"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["field_map"]:
            field_rows = payload["field_map"]["preventivo"] + payload["field_map"]["conferimento"]
            Path(paths["field_map"]).parent.mkdir(parents=True, exist_ok=True)
            Path(paths["field_map"]).write_text(
                json.dumps(
                    {
                        "source": payload["source"],
                        "count": len(field_rows),
                        "field_map": payload["field_map"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if paths["rules"]:
            Path(paths["rules"]).parent.mkdir(parents=True, exist_ok=True)
            Path(paths["rules"]).write_text(
                json.dumps(
                    {
                        "source": payload["source"],
                        "count": len(payload["rules"]),
                        "rules": payload["rules"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return paths

    def list_preventivi(self) -> list[dict[str, Any]]:
        return list(self.load_repository_payload().get("preventivi") or [])

    def list_conferimenti(self) -> list[dict[str, Any]]:
        return list(self.load_repository_payload().get("conferimenti") or [])

    def list_practices(self) -> list[dict[str, Any]]:
        return list(self.load_repository_payload().get("practice_catalog") or [])

    def select_best_preventivi(self, question: str, *, limit: int = 3) -> dict[str, Any]:
        rows = self.list_preventivi()
        terms = _query_terms(question)
        scored: list[tuple[int, int, dict[str, Any]]] = []
        for index, row in enumerate(rows):
            haystack = _clean_spaces(row.get("search_text")).lower()
            score = sum(1 for term in terms if term in haystack)
            if row.get("stato") in {"IN_CALCOLO", "GENERATO", "VERIFICATO", "INVIATO", "APERTO", "ACCETTATO"}:
                score += 1
            scored.append((score, -index, row))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = [row for score, _order, row in scored if score > 0][:limit]
        if not selected:
            selected = rows[:limit]
        return {
            "best_preventivo": selected[0] if selected else None,
            "alternatives": selected[1:],
            "matches": selected,
        }

    def select_best_practices(self, question: str, *, limit: int = 3) -> dict[str, Any]:
        rows = self.list_practices()
        terms = _query_terms(question)
        scored: list[tuple[int, int, dict[str, Any]]] = []
        for index, row in enumerate(rows):
            haystack = _clean_spaces(row.get("search_text")).lower()
            score = sum(1 for term in terms if term in haystack)
            scored.append((score, -index, row))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = [row for score, _order, row in scored if score > 0][:limit]
        if not selected:
            selected = rows[:limit]
        return {
            "best_practice": selected[0] if selected else None,
            "alternatives": selected[1:],
            "matches": selected,
        }
