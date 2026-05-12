"""Ruleset governato per profili Cartabia e controlli redazionali.

Il modulo non dichiara conformita' assoluta: assegna profili verificabili,
campi richiesti, controlli e stato di revisione. Le citazioni puntuali restano
aggiornabili nel catalogo senza riscrivere i template.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import unicodedata
from typing import Any

from pct.template_atti_prefill import DEFAULT_PREFILL_BINDINGS


CARTABIA_RULESET_VERSION = "2026.05.12.1"
CARTABIA_RULESET_SOURCE = "Ruleset operativo IUSENTRA con fonti ufficiali tracciate in docs/legal_sources/cartabia_sources.jsonl"
CARTABIA_RULESET_DATE = date(2026, 5, 12).isoformat()
STATUS_DRAFT = "draft_professionale"
STATUS_REVIEW = "cartabia_review_required"
STATUS_READY = "cartabia_ready"

PROCESS_AREAS = {
    "civile",
    "famiglia_minori",
    "adr",
    "penale",
    "tributario",
    "amministrativo",
    "esecuzione",
    "cautelare",
    "monitorio",
    "studio_interno",
}

AREA_EVIDENCE_IDS: dict[str, list[str]] = {
    "civile": ["CARTABIA-CIVILE-DLGS-149-2022", "PST-DEPOSITO-ATTI-GIUDIZIARI", "PST-DOCUMENTAZIONE-TECNICA"],
    "famiglia_minori": ["CARTABIA-CIVILE-DLGS-149-2022", "PST-DEPOSITO-ATTI-GIUDIZIARI"],
    "adr": ["CARTABIA-CIVILE-DLGS-149-2022", "MEDIAZIONE-DLGS-28-2010"],
    "penale": ["CARTABIA-PENALE-DLGS-150-2022", "PDP-SPECIFICHE-TECNICHE-2023"],
    "tributario": ["PTT-SPECIFICHE-TECNICHE-2021"],
    "amministrativo": ["PAT-REGOLE-TECNICHE-2021-2025"],
    "esecuzione": ["CARTABIA-CIVILE-DLGS-149-2022", "PST-DEPOSITO-ATTI-GIUDIZIARI"],
    "cautelare": ["CARTABIA-CIVILE-DLGS-149-2022", "PST-DEPOSITO-ATTI-GIUDIZIARI"],
    "monitorio": ["CARTABIA-CIVILE-DLGS-149-2022", "PST-DEPOSITO-ATTI-GIUDIZIARI"],
    "studio_interno": ["PRIVACY-GDPR-GARANTE", "CNF-DEONTOLOGIA-PROFESSIONALE"],
}

COMMON_REQUIRED = ["cliente", "difensore", "oggetto", "data_atto"]
COMMON_OPTIONAL = ["controparte", "ufficio_giudiziario", "rg", "pec_studio", "codice_fiscale_studio", "partita_iva_studio"]

AREA_RULES: dict[str, dict[str, Any]] = {
    "civile": {
        "cartabia_profile": "civile_ordinario_semplificato",
        "normativa_riferimento": ["Codice di procedura civile e riforme processuali vigenti, da verificare sul caso concreto"],
        "condizioni_procedibilita": ["mediazione o negoziazione assistita quando previste dalla materia"],
        "termini_processuali_rilevanti": ["termini di comparizione, costituzione, memorie e decadenze da verificare sul rito"],
        "required": COMMON_REQUIRED + ["ufficio_giudiziario", "controparte"],
        "cartabia_required": ["dati parti", "difensore", "ufficio", "rito", "oggetto domande", "procura", "allegati"],
        "deposit_required": ["pdfa", "firma_digitale", "dati_atto_xml", "allegati", "procura"],
        "checks": ["dati parti completi", "domande e conclusioni presenti", "procura collegata", "pre-verifica deposito telematico"],
        "warnings": ["Verificare il rito applicabile e le condizioni di procedibilita prima del deposito."],
        "review": True,
    },
    "famiglia_minori": {
        "cartabia_profile": "famiglia_minori",
        "normativa_riferimento": ["Norme processuali famiglia, persone e minori vigenti, da validare sul procedimento"],
        "condizioni_procedibilita": ["documentazione familiare, reddituale e patrimoniale quando richiesta"],
        "termini_processuali_rilevanti": ["udienza, termini difensivi e provvedimenti temporanei da verificare"],
        "required": COMMON_REQUIRED + ["ufficio_giudiziario", "figli_minori", "documentazione_reddituale", "piano_genitoriale"],
        "cartabia_required": ["dati coniugi o genitori", "presenza minori", "interesse del minore", "condizioni richieste", "documentazione reddituale e patrimoniale", "piano genitoriale"],
        "deposit_required": ["pdfa", "firma_digitale", "allegati essenziali", "procura"],
        "checks": ["dati minori", "assetto genitoriale", "documenti reddituali", "provvedimenti temporanei se richiesti"],
        "warnings": ["Dati sensibili e minori richiedono verifica professionale obbligatoria."],
        "review": True,
    },
    "adr": {
        "cartabia_profile": "adr_mediazione_negoziazione",
        "normativa_riferimento": ["Disciplina ADR, mediazione e negoziazione assistita vigente, da verificare sulla materia"],
        "condizioni_procedibilita": ["obbligatorieta, facoltativita o invio demandato da verificare"],
        "termini_processuali_rilevanti": ["termini ADR e collegamento al giudizio da verificare"],
        "required": COMMON_REQUIRED + ["tipo_adr", "organismo_adr", "valore_causa"],
        "cartabia_required": ["tipo ADR", "organismo", "parti", "oggetto controversia", "valore", "procura o delega", "documenti allegati", "fase o esito"],
        "deposit_required": ["delega o procura", "documenti allegati", "verbale o istanza quando disponibile"],
        "checks": ["condizione di procedibilita", "organismo ADR", "valore controversia", "collegamento a fascicolo o incarico"],
        "warnings": ["La condizione di procedibilita va validata sulla materia e sul rito effettivo."],
        "review": True,
    },
    "penale": {
        "cartabia_profile": "penale_difesa_pdp",
        "normativa_riferimento": ["Codice di procedura penale e canale PDP dove previsto"],
        "condizioni_procedibilita": ["nomina, procura o legittimazione difensiva secondo fase e atto"],
        "termini_processuali_rilevanti": ["termini di fase e impugnazione da verificare"],
        "required": COMMON_REQUIRED + ["ufficio_giudiziario", "assistito_imputato_indagato", "fase_procedimento"],
        "cartabia_required": ["ufficio", "procedimento", "assistito", "nomina o procura", "fase", "richieste", "allegati"],
        "deposit_required": ["firma_digitale", "canale PDP se previsto", "allegati"],
        "checks": ["qualifica assistito", "fase procedimento", "legittimazione difensore", "compatibilita canale PDP"],
        "warnings": ["Verificare sempre fase, termini e canale di deposito penale."],
        "review": True,
    },
    "tributario": {
        "cartabia_profile": "tributario_ptt",
        "normativa_riferimento": ["Processo tributario telematico e norme fiscali processuali vigenti"],
        "condizioni_procedibilita": ["atto impugnato, ente impositore e termini da verificare"],
        "termini_processuali_rilevanti": ["termine di impugnazione e sospensione da validare"],
        "required": COMMON_REQUIRED + ["atto_impugnato", "ente_impositore", "valore_causa"],
        "cartabia_required": ["atto impugnato", "ente impositore", "valore", "termini", "procura", "documenti fiscali"],
        "deposit_required": ["pdfa", "firma_digitale", "PTT", "procura", "documenti fiscali"],
        "checks": ["atto impugnato", "ente impositore", "valore lite", "termini impugnazione"],
        "warnings": ["Termini e valore tributario richiedono controllo professionale."],
        "review": True,
    },
    "amministrativo": {
        "cartabia_profile": "amministrativo_pat",
        "normativa_riferimento": ["Processo amministrativo telematico e rito applicabile"],
        "condizioni_procedibilita": ["provvedimento impugnato e amministrazione resistente"],
        "termini_processuali_rilevanti": ["termini di impugnazione, deposito e cautelare da verificare"],
        "required": COMMON_REQUIRED + ["provvedimento_impugnato", "amministrazione_resistente"],
        "cartabia_required": ["provvedimento impugnato", "amministrazione resistente", "controinteressati", "termini", "procura", "PAT"],
        "deposit_required": ["pdfa", "firma_digitale", "PAT", "procura", "allegati"],
        "checks": ["provvedimento", "amministrazione resistente", "controinteressati", "termini"],
        "warnings": ["Controinteressati e termini PAT vanno verificati sul fascicolo."],
        "review": True,
    },
    "esecuzione": {
        "cartabia_profile": "esecuzioni",
        "normativa_riferimento": ["Norme su esecuzione forzata e deposito telematico applicabile"],
        "condizioni_procedibilita": ["titolo esecutivo, precetto e notifiche"],
        "termini_processuali_rilevanti": ["efficacia titolo, precetto e termini oppositivi da verificare"],
        "required": COMMON_REQUIRED + ["titolo_esecutivo", "precetto", "debitore", "creditore", "importi"],
        "cartabia_required": ["titolo esecutivo", "precetto", "notifiche", "importi", "debitore", "creditore", "beni o crediti"],
        "deposit_required": ["pdfa", "firma_digitale", "titolo", "precetto", "notifiche"],
        "checks": ["titolo", "precetto", "notifiche", "importi"],
        "warnings": ["Verificare titolo, precetto, notifiche e aggiornamento importi."],
        "review": True,
    },
    "cautelare": {
        "cartabia_profile": "cautelare",
        "normativa_riferimento": ["Riti cautelari e norme processuali applicabili"],
        "condizioni_procedibilita": ["fumus, periculum e allegati essenziali"],
        "termini_processuali_rilevanti": ["termini di fissazione, reclamo e integrazioni da verificare"],
        "required": COMMON_REQUIRED + ["ufficio_giudiziario", "urgenza", "allegati"],
        "cartabia_required": ["ufficio", "parti", "fumus", "periculum", "urgenza", "allegati"],
        "deposit_required": ["pdfa", "firma_digitale", "allegati", "procura"],
        "checks": ["urgenza", "fumus", "periculum", "documenti essenziali"],
        "warnings": ["La misura cautelare richiede revisione professionale prima del deposito."],
        "review": True,
    },
    "monitorio": {
        "cartabia_profile": "monitorio",
        "normativa_riferimento": ["Procedimento monitorio e deposito telematico applicabile"],
        "condizioni_procedibilita": ["prova scritta, credito, competenza e importi"],
        "termini_processuali_rilevanti": ["opposizione, provvisoria esecuzione e notifica da verificare"],
        "required": COMMON_REQUIRED + ["ufficio_giudiziario", "credito", "prova_scritta", "debitore"],
        "cartabia_required": ["creditore", "debitore", "credito", "prova scritta", "competenza", "procura"],
        "deposit_required": ["pdfa", "firma_digitale", "dati_atto_xml", "prova scritta", "procura"],
        "checks": ["credito", "prova scritta", "competenza", "importi"],
        "warnings": ["Verificare documenti probatori, competenza e calcolo accessori."],
        "review": True,
    },
    "studio_interno": {
        "cartabia_profile": "studio_interno",
        "normativa_riferimento": ["Regole interne di mandato, privacy e gestione studio"],
        "condizioni_procedibilita": ["cliente, fascicolo e incarico quando collegati"],
        "termini_processuali_rilevanti": [],
        "required": ["cliente", "difensore", "oggetto", "timbro_studio"],
        "cartabia_required": ["preventivo", "conferimento", "procura", "privacy", "incarico", "firme necessarie"],
        "deposit_required": ["timbro studio", "firme necessarie"],
        "checks": ["collegamento cliente", "incarico", "privacy", "timbro studio"],
        "warnings": ["Gli atti interni non sostituiscono la verifica del mandato e delle firme."],
        "review": False,
    },
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean(value).lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _contains(text: str, *tokens: str) -> bool:
    return any(token in text for token in tokens)


def derive_processo_area(item: dict[str, Any]) -> str:
    text = _norm(
        " ".join(
            _clean(item.get(key))
            for key in (
                "id",
                "titolo",
                "famiglia",
                "area",
                "macro_area",
                "sottobranca",
                "procedimento",
                "rito",
                "fase",
                "canale_telematico",
            )
        )
    )
    channel = _clean(item.get("canale_telematico") or item.get("canale_deposito")).upper()
    template_id = _clean(item.get("id") or item.get("codice")).upper()
    if channel == "PDP" or template_id.startswith("PEN") or "penal" in text:
        return "penale"
    if channel == "PTT" or template_id.startswith("TRI") or "tribut" in text:
        return "tributario"
    if channel == "PAT" or template_id.startswith("AMM") or "amministrativ" in text:
        return "amministrativo"
    if channel == "NESSUNO" or template_id.startswith("STD") or _contains(text, "studio interno", "preventivo", "incarico", "privacy"):
        return "studio_interno"
    if _contains(text, "famiglia", "minore", "figli", "separazione", "divorzio", "genitor", "volontaria giurisdizione"):
        return "famiglia_minori"
    if _contains(text, "mediazione", "negoziazione", "adr", "conciliazione"):
        return "adr"
    if _contains(text, "esecuzione", "pignoramento", "precetto", "assegnazione", "vendita"):
        return "esecuzione"
    if _contains(text, "cautel", "sequestro", "700", "atp", "urgenza"):
        return "cautelare"
    if _contains(text, "monitorio", "decreto ingiuntivo", "ingiunzione"):
        return "monitorio"
    return "civile"


def _prefill_for_area(area: str) -> dict[str, list[str]]:
    bindings = deepcopy(DEFAULT_PREFILL_BINDINGS)
    area_extra = {
        "famiglia_minori": {
            "figli_minori": ["fascicolo.figli_minori", "parti.minori"],
            "documentazione_reddituale": ["fascicolo.documentazione_reddituale", "documenti.nomi"],
            "piano_genitoriale": ["fascicolo.piano_genitoriale"],
        },
        "adr": {
            "tipo_adr": ["fascicolo.tipo_adr", "fascicolo.rito"],
            "organismo_adr": ["fascicolo.organismo_adr"],
            "valore_causa": ["fascicolo.valore_causa"],
        },
        "penale": {
            "assistito_imputato_indagato": ["parti.assistito_principale.nome_completo", "cliente.nome_completo"],
            "fase_procedimento": ["fascicolo.fase", "fascicolo.rito"],
        },
        "tributario": {
            "atto_impugnato": ["fascicolo.atto_impugnato", "fascicolo.oggetto"],
            "ente_impositore": ["fascicolo.ente_impositore", "fascicolo.controparte"],
            "valore_causa": ["fascicolo.valore_causa"],
        },
        "amministrativo": {
            "provvedimento_impugnato": ["fascicolo.provvedimento_impugnato", "fascicolo.oggetto"],
            "amministrazione_resistente": ["fascicolo.amministrazione_resistente", "fascicolo.controparte"],
        },
        "esecuzione": {
            "titolo_esecutivo": ["fascicolo.titolo_esecutivo", "documenti.nomi"],
            "precetto": ["fascicolo.precetto", "documenti.nomi"],
            "debitore": ["parti.controparte_principale.nome_completo", "fascicolo.controparte"],
            "creditore": ["parti.assistito_principale.nome_completo", "cliente.nome_completo"],
            "importi": ["fascicolo.importi", "fascicolo.valore_causa"],
        },
        "cautelare": {
            "urgenza": ["fascicolo.urgenza", "fascicolo.note"],
            "allegati": ["documenti.nomi"],
        },
        "monitorio": {
            "credito": ["fascicolo.credito", "fascicolo.valore_causa"],
            "prova_scritta": ["fascicolo.prova_scritta", "documenti.nomi"],
            "debitore": ["parti.controparte_principale.nome_completo", "fascicolo.controparte"],
        },
        "studio_interno": {
            "timbro_studio": ["studio_timbro.studio_nome"],
            "preventivo": ["fascicolo.preventivo", "legacy.preventivo"],
            "conferimento": ["fascicolo.conferimento", "legacy.conferimento"],
        },
    }
    bindings.update(area_extra.get(area, {}))
    return bindings


def cartabia_profile_for_template(item: dict[str, Any]) -> dict[str, Any]:
    area = derive_processo_area(item)
    rules = deepcopy(AREA_RULES[area])
    depositabile = bool(item.get("depositabile"))
    evidence_ids = list(AREA_EVIDENCE_IDS.get(area) or [])
    status = STATUS_READY if evidence_ids else STATUS_REVIEW
    required_prefill = list(dict.fromkeys(rules["required"]))
    optional_prefill = [field for field in COMMON_OPTIONAL if field not in required_prefill]
    controlli_deposito = list(dict.fromkeys(rules["deposit_required"]))
    if depositabile:
        controlli_deposito.extend(["pdfa", "firma_digitale"])
        if _clean(item.get("canale_telematico")).upper() in {"PST", "PST_GDP", "PST_CONCORSUALE"}:
            controlli_deposito.append("dati_atto_xml")
    return {
        "cartabia_profile": rules["cartabia_profile"],
        "processo_area": area,
        "normativa_riferimento": rules["normativa_riferimento"],
        "condizioni_procedibilita": rules["condizioni_procedibilita"],
        "termini_processuali_rilevanti": rules["termini_processuali_rilevanti"],
        "dati_obbligatori_cartabia": list(dict.fromkeys(rules["cartabia_required"])),
        "controlli_cartabia": list(dict.fromkeys(rules["checks"])),
        "controlli_redazionali": list(dict.fromkeys(rules["checks"] + ["completezza dati", "coerenza allegati", "revisione professionale"])),
        "controlli_deposito": list(dict.fromkeys(controlli_deposito)),
        "avvisi_redazionali": rules["warnings"],
        "richiede_verifica_avvocato": bool(rules.get("review")),
        "stato_conformita": status,
        "data_ultimo_aggiornamento_normativo": CARTABIA_RULESET_DATE,
        "versione_regole": CARTABIA_RULESET_VERSION,
        "fonte_regole": CARTABIA_RULESET_SOURCE,
        "source_evidence_ids": evidence_ids,
        "prefill_bindings": _prefill_for_area(area),
        "required_prefill_fields": required_prefill,
        "optional_prefill_fields": optional_prefill,
        "cartabia_required_fields": list(dict.fromkeys(rules["cartabia_required"])),
        "deposit_required_fields": list(dict.fromkeys(controlli_deposito)),
    }


def ensure_cartabia_metadata(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    profile = cartabia_profile_for_template(enriched)
    declared_area = _clean(enriched.get("processo_area"))
    declared_area_invalid = bool(declared_area and declared_area not in PROCESS_AREAS)
    for key, value in profile.items():
        current = enriched.get(key)
        if current in (None, "", [], {}):
            enriched[key] = value
        elif key in {"prefill_bindings"} and isinstance(current, dict):
            merged = deepcopy(value)
            merged.update(current)
            enriched[key] = merged
    if declared_area_invalid:
        enriched["source_evidence_ids"] = []
    if not enriched.get("source_evidence_ids"):
        enriched["source_evidence_ids"] = list(AREA_EVIDENCE_IDS.get(enriched.get("processo_area"), []))
    if not enriched.get("source_evidence_ids"):
        enriched["fonte_regole"] = "fonte ufficiale non documentata"
        enriched["richiede_verifica_avvocato"] = True
        enriched["stato_conformita"] = STATUS_REVIEW
    return enriched


def verifica_cartabia_template(
    item: dict[str, Any],
    *,
    prefill_resolution: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = ensure_cartabia_metadata(item)
    payload = payload or {}
    prefill_resolution = prefill_resolution or {}
    required = list(enriched.get("cartabia_required_fields") or enriched.get("required_prefill_fields") or [])
    resolved_fields = prefill_resolution.get("fields") or {}
    missing = []
    available = []
    for field in enriched.get("required_prefill_fields") or []:
        resolved = resolved_fields.get(field, {})
        value = payload.get(field, resolved.get("value"))
        if value not in (None, "", [], {}):
            available.append(field)
        else:
            missing.append(field)
    recommended = [
        {"codice": "revisione_avvocato", "label": "Revisione professionale richiesta", "severity": "warning"}
    ] if enriched.get("richiede_verifica_avvocato") else []
    if not enriched.get("source_evidence_ids"):
        missing.append("fonte_normativa")
    blocking = [
        {"codice": f"dato_{field}", "label": f"Completa {field.replace('_', ' ')}", "severity": "block"}
        for field in missing
    ]
    if not enriched.get("source_evidence_ids"):
        blocking.append(
            {
                "codice": "fonte_normativa_mancante",
                "label": "Fonte normativa ufficiale da documentare",
                "severity": "block",
            }
        )
    return {
        "ok": not blocking and enriched.get("stato_conformita") == STATUS_READY,
        "stato_conformita": enriched.get("stato_conformita"),
        "processo_area": enriched.get("processo_area"),
        "cartabia_profile": enriched.get("cartabia_profile"),
        "ruleset_version": enriched.get("versione_regole", CARTABIA_RULESET_VERSION),
        "fonte_regole": enriched.get("fonte_regole"),
        "source_evidence_ids": list(enriched.get("source_evidence_ids") or []),
        "required_fields": required,
        "available_fields": available,
        "missing_fields": missing,
        "controlli_bloccanti": blocking,
        "controlli_consigliati": recommended,
        "avvisi_redazionali": list(enriched.get("avvisi_redazionali") or []),
        "fonti_dati": prefill_resolution.get("sources", []),
    }


__all__ = [
    "AREA_EVIDENCE_IDS",
    "CARTABIA_RULESET_VERSION",
    "STATUS_DRAFT",
    "STATUS_READY",
    "STATUS_REVIEW",
    "cartabia_profile_for_template",
    "derive_processo_area",
    "ensure_cartabia_metadata",
    "verifica_cartabia_template",
]
