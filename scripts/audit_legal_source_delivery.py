from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lex.legal_sources.registry import create_default_registry  # noqa: E402
from lex.operational_knowledge.source_registry import DEFAULT_SOURCE_DEFINITIONS  # noqa: E402
from lex.sources.registry import load_sources  # noqa: E402
from pct.guida_pratica.web_enrichment import SOURCE_LIBRARY as GUIDA_PRATICA_SOURCE_LIBRARY  # noqa: E402
from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS  # noqa: E402
from pct.legal_update_source_capabilities import SOURCE_CAPABILITIES  # noqa: E402
from pct.normative_tables import FONTI_OPERATIVE  # noqa: E402
from pct.template_atti_legal_sources import TEMPLATE_ATTI_LEGAL_SOURCES  # noqa: E402


AUDIT_DATE = date(2026, 6, 6).isoformat()
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "legal-sources"
OFFICIAL_CONFIG = ROOT / "config" / "lex_official_sources.example.json"
RESEARCH_REGISTRY = ROOT / "lex" / "research" / "source_policy" / "sources_registry.yaml"


SOURCE_ENTRYPOINTS: dict[str, str] = {
    "agcm_bollettino": "https://www.agcm.it/pubblicazioni/bollettino-settimanale",
    "agcom_provvedimenti": "https://www.agcom.it/provvedimenti",
    "agenzia_entrate": "https://www.agenziaentrate.gov.it/portale/web/guest/provvedimenti",
    "anac_documenti": "https://www.anticorruzione.it/",
    "banca_italia_normativa": "https://www.bancaditalia.it/compiti/vigilanza/normativa/",
    "cassazione": "https://www.cortedicassazione.it/",
    "cassazione_citazioni_verificate": "https://www.cortedicassazione.it/",
    "cassazione_massimario": "https://www.cortedicassazione.it/",
    "cassazione_ultime_sent_ord_questioni": "https://www.cortedicassazione.it/",
    "codice_civile": "https://www.normattiva.it/",
    "codice_penale": "https://www.normattiva.it/",
    "codice_procedura_civile": "https://www.normattiva.it/",
    "codice_procedura_penale": "https://www.normattiva.it/",
    "codice_processo_amministrativo": "https://www.normattiva.it/",
    "codice_strada": "https://www.normattiva.it/",
    "curia_cgue_rss": "https://curia.europa.eu/",
    "dati_normattiva": "https://dati.normattiva.it/",
    "eur_lex": "https://eur-lex.europa.eu/",
    "eurlex": "https://eur-lex.europa.eu/",
    "garante_privacy": "https://www.garanteprivacy.it/normativa-e-provvedimenti",
    "giustizia_amministrativa": "https://www.giustizia-amministrativa.it/dcsnprr",
    "hudoc": "https://hudoc.echr.coe.int/",
    "inail_istruzioni_operative": "https://www.inail.it/portale/it/atti-e-documenti/note-provvedimenti-e-istruzioni-operative/normativa-circolari-inail.html",
    "inps_circolari": "https://www.inps.it/it/it/inps-comunica/atti/circolari-messaggi-e-normativa.html",
    "inps_messaggi": "https://www.inps.it/it/it/inps-comunica/atti/circolari-messaggi-e-normativa.html",
    "inps_sentenze": "https://www.inps.it/it/it/inps-comunica/atti.html",
    "ipa": "https://www.indicepa.gov.it/ipa-dati/",
    "istat_prezzi": "https://www.istat.it/statistiche-per-temi/prezzi/",
    "leggi_regionali": "https://www.normattiva.it/",
    "mimit_incentivi": "https://www.mimit.gov.it/it/incentivi",
    "ministero_lavoro": "https://www.lavoro.gov.it/",
    "ministero_lavoro_interpelli": "https://www.lavoro.gov.it/",
    "openga_calendario_udienze": "https://openga.giustizia-amministrativa.it/dataset/",
    "openga_decreti": "https://openga.giustizia-amministrativa.it/dataset/",
    "openga_giustizia_amministrativa": "https://openga.giustizia-amministrativa.it/dataset/",
    "openga_ordinanze": "https://openga.giustizia-amministrativa.it/dataset/",
    "openga_pareri": "https://openga.giustizia-amministrativa.it/dataset/",
    "openga_provvedimenti_pubblicati": "https://openga.giustizia-amministrativa.it/dataset/",
    "openga_ricorsi_definiti": "https://openga.giustizia-amministrativa.it/dataset/",
    "openga_ricorsi_pendenti": "https://openga.giustizia-amministrativa.it/dataset/",
    "openga_ricorsi_pervenuti": "https://openga.giustizia-amministrativa.it/dataset/",
    "openga_sentenze": "https://openga.giustizia-amministrativa.it/dataset/",
    "pst_giustizia_download": "https://pst.giustizia.it/PST/it/download.page",
}


SOURCE_CANONICAL_IDS: dict[str, str] = {
    "eurlex": "eur_lex",
    "gazzetta_rss": "gazzetta_ufficiale",
    "cassazione": "cassazione_ultime_sent_ord_questioni",
    "banca_dati_merito": "bdp_giustizia",
    "camera": "camera_open_data",
    "senato": "senato_open_data",
    "inipec": "ini_pec",
    "ipa": "ipa_open_data",
}


LAWYER_USE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("cassazione", "sentenz", "ordinanz", "massim", "corte", "hudoc", "curia", "cgue", "giurisprud", "udienz", "provvediment"), "strategia processuale, precedenti, udienze, provvedimenti ed esito pratica"),
    (("lavoro", "inps", "inail", "previd", "ministero lavoro"), "contenzioso lavoro/previdenza, termini amministrativi e istruzioni operative"),
    (("deontolog", "forense", "compens", "parametr", "cassa forense", "equo compenso"), "mandato, compenso, informazione al cliente e presidio deontologico"),
    (("pct", "pst", "telematic", "pdp", "siga", "sigit", "deposit", "firma", "pec", "inad", "inipec", "ipa"), "notifica, deposito telematico, prova, destinatari e fascicolo"),
    (("tributario", "agenzia entrate", "interpello", "fisc", "ptt", "sigit"), "atto tributario, termini fiscali, prassi dell'ente e difesa in commissione"),
    (("banca", "usura", "tegm", "abf", "mutu", "credito"), "causa bancaria, soglie, interessi, eccezioni e consulenza tecnica"),
    (("privacy", "gdpr", "garante", "dati personali"), "privacy, prova del consenso, istanze, reclami e misure organizzative"),
    (("lavoro", "inps", "inail", "previd", "ministero lavoro"), "contenzioso lavoro/previdenza, termini amministrativi e istruzioni operative"),
    (("anac", "appalt", "contratti pubblici", "gare"), "appalti, accesso atti, rito, documenti di gara e autorità competente"),
    (("agcom", "agcm", "consum", "concorren", "conciliaweb", "corecom"), "consumatori, comunicazioni, conciliazioni e provvedimenti di autorità"),
    (("normattiva", "codice", "gazzetta", "legge", "decreto", "normativa"), "inquadramento giuridico, norma vigente, rito e termine applicabile"),
)


LAWYER_USE_BY_SOURCE: dict[str, str] = {
    "agenzia_entrate": "atto tributario, termini fiscali, prassi dell'ente e difesa in commissione",
    "ptt_sigit": "atto tributario, deposito PTT, prova telematica e difesa in commissione",
    "inps": "contenzioso lavoro/previdenza, termini amministrativi e istruzioni operative",
    "inps_circolari": "contenzioso lavoro/previdenza, termini amministrativi e istruzioni operative",
    "inps_messaggi": "contenzioso lavoro/previdenza, termini amministrativi e istruzioni operative",
    "inps_sentenze": "contenzioso previdenziale, precedenti, esiti e prova amministrativa",
    "inail": "infortuni, malattie professionali, termini amministrativi e istruzioni operative",
    "inail_istruzioni_operative": "infortuni, malattie professionali, termini amministrativi e istruzioni operative",
    "banca_italia": "causa bancaria, soglie, interessi, eccezioni e consulenza tecnica",
    "banca_italia_normativa": "causa bancaria, soglie, interessi, eccezioni e consulenza tecnica",
    "cassazione": "strategia processuale, precedenti, massime e verifica orientamenti",
    "cassazione_massimario": "strategia processuale, precedenti, massime e verifica orientamenti",
    "cassazione_ultime_sent_ord_questioni": "strategia processuale, precedenti, questioni pendenti e provvedimenti",
    "cassazione_citazioni_verificate": "strategia processuale, citazione corretta del precedente e controllo ufficiale",
    "corte_costituzionale": "questioni di legittimità, norme parametro, effetti sul rito e strategia",
    "giustizia_amministrativa": "ricorsi TAR/Consiglio di Stato, udienze, decreti, ordinanze e sentenze",
    "hudoc": "diritti fondamentali, CEDU, equo processo e strategia sovranazionale",
    "agcm": "consumatori, pratiche scorrette, clausole vessatorie e provvedimenti AGCM",
    "agcm_bollettino": "consumatori, pratiche scorrette, clausole vessatorie e provvedimenti AGCM",
    "agcom": "comunicazioni, ConciliaWeb, Corecom, provvedimenti temporanei e tutela utenti",
    "agcom_provvedimenti": "comunicazioni, ConciliaWeb, Corecom, provvedimenti temporanei e tutela utenti",
    "anac": "appalti, accesso atti, rito, documenti di gara e autorità competente",
    "anac_documenti": "appalti, accesso atti, rito, documenti di gara e autorità competente",
    "ipa": "notifiche e comunicazioni alla PA, domicili digitali e verifica destinatario",
    "inipec": "notifiche PEC a imprese e professionisti, prova destinatario e relata",
    "inad": "domicilio digitale persone fisiche, comunicazioni PA e notifiche",
    "cnf": "mandato, compenso, informazione al cliente e presidio deontologico",
}


PRODUCT_DESTINATIONS = {
    "ricerca_legale": "Ricerca Legale",
    "lex_rag": "Lex AI/RAG Legal",
    "template_editor": "Template Atti/editor",
    "guida_pratica": "Guida Pratica",
    "scadenziario": "Scadenziario/agenda/task",
    "legal_updates": "Aggiornamenti legali",
    "normative_db": "DB normativa",
}


@dataclass
class SourceAuditRow:
    registry: str
    source_id: str
    title: str
    official: bool
    authority: str = ""
    url: str = ""
    enabled: bool | None = None
    connector: str = ""
    category: str = ""
    topics: list[str] = field(default_factory=list)
    destinations: set[str] = field(default_factory=set)
    delivery_status: str = "da_verificare"
    gap_reason: str = ""
    lawyer_use: str = ""
    notes: list[str] = field(default_factory=list)
    activation_action: str = ""
    lex_test_question: str = ""
    practice_phase: str = ""
    expected_output: str = ""
    professional_context: str = ""
    legal_materials: list[str] = field(default_factory=list)
    articles_and_codes: list[str] = field(default_factory=list)
    decrees_and_rules: list[str] = field(default_factory=list)
    case_law_and_hearings: list[str] = field(default_factory=list)
    research_steps: list[str] = field(default_factory=list)

    def merge(self, other: "SourceAuditRow") -> None:
        if not self.title and other.title:
            self.title = other.title
        if not self.authority and other.authority:
            self.authority = other.authority
        if not self.url and other.url:
            self.url = other.url
        if other.enabled is True:
            self.enabled = True
        elif self.enabled is None and other.enabled is not None:
            self.enabled = other.enabled
        if not self.connector and other.connector:
            self.connector = other.connector
        if not self.category and other.category:
            self.category = other.category
        self.official = self.official or other.official
        self.topics = _dedupe_list([*self.topics, *other.topics])
        self.destinations.update(other.destinations)
        self.notes = _dedupe_list([*self.notes, *other.notes])
        if not self.activation_action and other.activation_action:
            self.activation_action = other.activation_action
        if not self.lex_test_question and other.lex_test_question:
            self.lex_test_question = other.lex_test_question
        if not self.practice_phase and other.practice_phase:
            self.practice_phase = other.practice_phase
        if not self.expected_output and other.expected_output:
            self.expected_output = other.expected_output
        if not self.professional_context and other.professional_context:
            self.professional_context = other.professional_context
        self.legal_materials = _dedupe_list([*self.legal_materials, *other.legal_materials])
        self.articles_and_codes = _dedupe_list([*self.articles_and_codes, *other.articles_and_codes])
        self.decrees_and_rules = _dedupe_list([*self.decrees_and_rules, *other.decrees_and_rules])
        self.case_law_and_hearings = _dedupe_list([*self.case_law_and_hearings, *other.case_law_and_hearings])
        self.research_steps = _dedupe_list([*self.research_steps, *other.research_steps])

    def to_dict(self) -> dict[str, Any]:
        destination_labels = [PRODUCT_DESTINATIONS[key] for key in sorted(self.destinations)]
        return {
            "registry": self.registry,
            "source_id": self.source_id,
            "title": self.title,
            "official": self.official,
            "authority": self.authority,
            "url": self.url,
            "enabled": self.enabled,
            "connector": self.connector,
            "category": self.category,
            "topics": self.topics,
            "destinations": destination_labels,
            "delivery_status": self.delivery_status,
            "gap_reason": self.gap_reason,
            "lawyer_use": self.lawyer_use,
            "activation_action": self.activation_action,
            "lex_test_question": self.lex_test_question,
            "practice_phase": self.practice_phase,
            "expected_output": self.expected_output,
            "professional_context": self.professional_context,
            "legal_materials": self.legal_materials,
            "articles_and_codes": self.articles_and_codes,
            "decrees_and_rules": self.decrees_and_rules,
            "case_law_and_hearings": self.case_law_and_hearings,
            "research_steps": self.research_steps,
            "notes": self.notes,
        }


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("-", "_").split())


def _id(value: Any) -> str:
    return _norm(value).replace(" ", "_")


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _dedupe_list(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = _text(value)
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _urls_from_settings(settings: dict[str, Any]) -> list[str]:
    urls = settings.get("urls")
    if isinstance(urls, list):
        return [_text(url) for url in urls if _text(url)]
    entrypoints = settings.get("entrypoints")
    if isinstance(entrypoints, dict):
        return [_text(url) for url in entrypoints.values() if _text(url)]
    return []


def _lawyer_use(*values: Any) -> str:
    for value in values:
        source_key = _id(value)
        if source_key in LAWYER_USE_BY_SOURCE:
            return LAWYER_USE_BY_SOURCE[source_key]
    haystack = " ".join(_text(value).lower() for value in values if _text(value))
    for tokens, label in LAWYER_USE_RULES:
        if any(token in haystack for token in tokens):
            return label
    return "contesto giuridico da collegare a una scelta, un atto, una prova o un termine"


def _activation_action(row: SourceAuditRow) -> str:
    status = _text(row.delivery_status)
    if status == "operativa_controllabile":
        return "Mantenere la fonte nel monitor aggiornamenti, verificare ultimo run e usare i record in Ricerca Legale/Lex prima di redigere o depositare."
    if status == "da_attivare_controllabile":
        return "Attivare acquisizione governata per la fonte, eseguire run a blocchi, esportare indice RAG e validare una domanda Lex prima dell'uso professionale."
    if status == "gap":
        if "manca URL" in row.gap_reason:
            return "Trovare e registrare entrypoint ufficiale, canale API/feed/PDF o procedura manuale documentata; poi rieseguire audit e test Lex."
        return "Chiudere il blocco indicato con canary fonte, configurazione o integrazione nel motore aggiornamenti prima di dichiarare copertura."
    return "Usare solo come know-how o confronto; non chiude modelli, scadenze o risposte Lex senza fonte ufficiale collegata."


def _lex_test_question(row: SourceAuditRow) -> str:
    use = row.lawyer_use or _lawyer_use(row.source_id, row.title, row.category, " ".join(row.topics))
    title = row.title or row.source_id
    if "tributario" in use or "fisc" in use:
        return f"Quali provvedimenti o prassi fiscali aggiornati devo controllare su {title} per questa pratica tributaria?"
    if "previd" in use or "lavoro" in use:
        return f"Quali circolari, messaggi o istruzioni {title} incidono sui termini e sui documenti della pratica?"
    if "notifica" in use or "deposito" in use or "telematico" in use:
        return f"Quale destinatario, prova o regola telematica devo verificare usando {title} prima di notificare o depositare?"
    if "precedenti" in use or "giurisprud" in use or "sentenze" in use:
        return f"Quali provvedimenti o precedenti da {title} sono pertinenti alla strategia e all'esito della pratica?"
    if "deontologico" in use or "compenso" in use:
        return f"Quale presidio deontologico o di compenso devo controllare su {title} prima di procedere?"
    if "bancaria" in use or "soglie" in use:
        return f"Quale soglia, tasso o disposizione {title} devo usare per valutare il rischio bancario della pratica?"
    return f"Come devo usare {title} nella pratica, quali documenti produce e quali limiti devo dichiarare?"


def _professional_context(row: SourceAuditRow) -> tuple[str, str, str]:
    use = row.lawyer_use or _lawyer_use(row.source_id, row.title, row.category, " ".join(row.topics))
    title = row.title or row.source_id
    if "mandato" in use or "compenso" in use or "deontologico" in use:
        return (
            "mandato, compenso e presidio deontologico",
            "informativa cliente, preventivo, controllo equo compenso, conflitto e tracciamento revisione",
            f"{title} serve a evitare incarichi, compensi o condotte processuali non presidiati e a spiegare il limite deontologico prima della redazione.",
        )
    if "notifica" in use or "deposito" in use or "telematico" in use:
        return (
            "notifica, deposito telematico e prova",
            "destinatario corretto, canale, relata, ricevute, busta/deposito, prova completa e scadenza collegata",
            f"{title} deve aiutare a scegliere il destinatario, verificare il canale, produrre prova e impedire notifiche o depositi improcedibili.",
        )
    if "precedenti" in use or "giurisprud" in use or "sentenze" in use or "udienze" in use:
        return (
            "strategia, udienza, provvedimento e precedente",
            "precedenti pertinenti, provvedimenti, udienze, esito, ragione decisiva e rischio di orientamento contrario",
            f"{title} deve portare casi e provvedimenti utili alla strategia, non massime isolate senza collegamento al fatto e all'esito.",
        )
    if "tributario" in use or "fisc" in use:
        return (
            "difesa tributaria e prassi fiscale",
            "atto o istanza, termine, prassi dell'ente, documento fiscale e rischio di decadenza o inammissibilità",
            f"{title} deve guidare l'avvocato su fonte fiscale, documento da produrre, termine e prassi applicabile alla difesa.",
        )
    if "previd" in use or "lavoro" in use or "infortuni" in use:
        return (
            "lavoro, previdenza e infortuni",
            "domanda amministrativa, ricorso, circolare/messaggio, documenti sanitari o contributivi e termini",
            f"{title} deve collegare prassi amministrativa, documenti richiesti e termini alla difesa del lavoratore o dell'azienda.",
        )
    if "bancaria" in use or "soglie" in use or "interessi" in use:
        return (
            "bancario, usura, interessi e consulenza tecnica",
            "soglia, trimestre, categoria, contratto, conteggio, prova contabile e quesito tecnico",
            f"{title} deve trasformare tassi e disposizioni in un controllo tecnico utilizzabile per domanda, eccezione o CTU.",
        )
    if "appalti" in use:
        return (
            "appalti, accesso atti e rito amministrativo",
            "bando, provvedimento, accesso, parere, termine impugnazione e fonte autorità",
            f"{title} deve aiutare a decidere accesso, precontenzioso, ricorso o difesa su gara e documenti amministrativi.",
        )
    if "consumatori" in use or "comunicazioni" in use:
        return (
            "consumatori, comunicazioni e autorità",
            "reclamo, conciliazione, provvedimento temporaneo, segnalazione e documento probatorio",
            f"{title} deve orientare reclamo, conciliazione, segnalazione o azione giudiziale con prova e competenza corretta.",
        )
    return (
        "inquadramento e controllo fonte",
        "norma vigente, decreto attuativo, documento collegato, limite e prossima attività",
        f"{title} deve essere collegata a una decisione concreta della pratica: cosa fare, cosa produrre, cosa provare e quale limite dichiarare.",
    )


def _legal_material_profile(row: SourceAuditRow) -> dict[str, list[str]]:
    haystack = _text(
        " ".join(
            [
                row.source_id,
                row.title,
                row.authority,
                row.category,
                row.connector,
                row.lawyer_use,
                row.practice_phase,
                row.expected_output,
                " ".join(row.topics),
            ]
        )
    ).lower()
    legal_materials = [
        "Norma primaria vigente o testo coordinato applicabile alla pratica",
        "Fonte secondaria, attuativa, tecnica o di autorità quando incide su rito, termini, prova o documento da produrre",
        "Prassi, circolari, provvedimenti o istruzioni dell'autorità competente se pertinenti",
    ]
    articles_and_codes = [
        "Articoli pertinenti di codice civile, procedura civile, penale, procedura penale, processo amministrativo, tributario o norma speciale",
    ]
    decrees_and_rules = [
        "D.Lgs., decreto-legge, D.M., regolamento, specifica tecnica o regime transitorio collegato alla materia",
    ]
    case_law_and_hearings = [
        "Sentenze, ordinanze, decreti, provvedimenti, verbali o udienze che incidono su strategia, prova, termine o precedente",
    ]
    research_steps = [
        "Verificare testo vigente, data di pubblicazione e autorità competente prima di citare o usare la fonte",
        "Collegare la fonte a fascicolo, modello, scadenza, prova o domanda Lex prima di dichiararla coperta",
        "Registrare limite, fonte sostituita/abrogata o necessità di revisione dell'avvocato quando presenti",
    ]

    def add(
        *,
        materials: list[str] | None = None,
        articles: list[str] | None = None,
        decrees: list[str] | None = None,
        cases: list[str] | None = None,
        steps: list[str] | None = None,
    ) -> None:
        legal_materials.extend(materials or [])
        articles_and_codes.extend(articles or [])
        decrees_and_rules.extend(decrees or [])
        case_law_and_hearings.extend(cases or [])
        research_steps.extend(steps or [])

    if any(token in haystack for token in ("normattiva", "codice", "gazzetta", "legge", "decreto", "normativa")):
        add(
            materials=[
                "Leggi, decreti-legge convertiti, decreti legislativi e testo vigente coordinato",
                "Gazzetta Ufficiale per pubblicazione, entrata in vigore, abrogazioni e transitori",
            ],
            articles=[
                "Articoli di codice civile, c.p.c., codice penale, c.p.p., codice del processo amministrativo e norme speciali collegate",
            ],
            decrees=[
                "D.Lgs. settoriali, decreti attuativi, correttivi, riforme processuali e disposizioni transitorie",
            ],
            steps=[
                "Partire dal testo vigente, controllare modifiche e abrogazioni, poi collegare giurisprudenza e prassi applicativa",
            ],
        )
    if any(token in haystack for token in ("pct", "pst", "telematic", "deposit", "notifica", "firma", "pec", "pdp", "pat", "siga", "sigit", "ptt")):
        add(
            materials=[
                "Regole tecniche ministeriali, specifiche del portale competente e tracciati di deposito/notifica",
                "Ricevute PEC, accettazione, consegna, esito deposito, busta, allegati e attestazioni di conformità",
            ],
            articles=[
                "Disposizioni c.p.c. e disp. att. c.p.c. su deposito, notifiche, fascicolo informatico e attestazioni",
                "Per PAT/PTT: codice processo amministrativo, D.Lgs. 546/1992 e norme telematiche del rito competente",
            ],
            decrees=[
                "D.M. 44/2011, D.M. 217/2023, specifiche PST/DGSIA e provvedimenti tecnici collegati",
                "Per PTT: D.M. 163/2013 e specifiche tecniche MEF/SIGIT quando pertinenti",
                "Per PAT: D.P.C.M. 40/2016 e regole tecnico-operative SIGA quando pertinenti",
            ],
            cases=[
                "Provvedimenti su nullità, improcedibilità, perfezionamento della notifica e prova del deposito",
                "Udienze, rinvii, verbali e decreti del giudice che generano termini o adempimenti telematici",
            ],
            steps=[
                "Verificare canale, destinatario digitale, formato allegati, firma, ricevute e prova completa prima di chiudere il task",
            ],
        )
    if any(token in haystack for token in ("cassazione", "massim", "sentenz", "ordinanz", "giurisprud", "openga", "giustizia amministrativa", "hudoc", "curia", "cgue", "udienz")):
        add(
            materials=[
                "Precedenti pertinenti con fatto, principio, esito e orientamento contrario",
                "Norma applicata dal giudice e questione decisiva del provvedimento",
            ],
            articles=[
                "Articoli citati nella decisione e norme processuali su ammissibilità, rito, prova e impugnazione",
            ],
            decrees=[
                "Decreti o norme speciali applicate dalla decisione, inclusi correttivi e transitori",
            ],
            cases=[
                "Sentenze, ordinanze, decreti, pareri, provvedimenti pubblicati, RG, ECLI, ricorsi pendenti/definiti e calendario udienze",
                "Verbali e udienze rilevanti quando spiegano istruttoria, rinvii, riserve, termini o attività decisive",
            ],
            steps=[
                "Estrarre ragione decisiva, domanda accolta o rigettata, prove valutate e passaggio replicabile nella pratica dello studio",
            ],
        )
    if any(token in haystack for token in ("tribut", "agenzia entrate", "fisc", "interpello", "imposta", "sigit", "ptt")):
        add(
            materials=[
                "Provvedimenti, circolari, risoluzioni, risposte a interpello e istruzioni fiscali ufficiali",
                "Avviso, cartella, accertamento, istanza, autotutela, reclamo/mediazione tributaria o ricorso",
            ],
            articles=[
                "D.Lgs. 546/1992, DPR 600/1973, DPR 633/1972, TUIR e norme fiscali speciali pertinenti",
            ],
            decrees=[
                "D.M. 163/2013 e specifiche PTT/SIGIT se la difesa richiede deposito tributario telematico",
            ],
            cases=[
                "Sentenze tributarie, Cassazione tributaria e provvedimenti che incidono su decadenza, prova o motivazione",
            ],
            steps=[
                "Collegare atto impugnato, termine, prova della notifica, prassi dell'ente e documento fiscale da produrre",
            ],
        )
    if any(token in haystack for token in ("deontolog", "forense", "compens", "parametr", "cassa forense", "equo compenso", "cnf")):
        add(
            materials=[
                "Codice deontologico forense, ordinamento professionale e atti CNF/Gazzetta pertinenti",
                "Mandato, preventivo, informazione cliente, conflitto, segreto, rinuncia/revoca e restituzione documenti",
            ],
            articles=[
                "L. 247/2012, Codice deontologico forense, L. 49/2023 su equo compenso e articoli deontologici collegati",
            ],
            decrees=[
                "D.M. 55/2014, D.M. 147/2022, parametri forensi, contributi Cassa Forense e aggiornamenti ufficiali",
            ],
            cases=[
                "Decisioni CNF, provvedimenti disciplinari e giurisprudenza su compenso, mandato, conflitto e condotta processuale",
            ],
            steps=[
                "Prima di generare il modello verificare obblighi informativi, compenso, conflitto e limite deontologico da mostrare all'avvocato",
            ],
        )
    if any(token in haystack for token in ("banca", "italia", "usura", "tegm", "mutu", "credito", "abf", "interessi", "mora")):
        add(
            materials=[
                "Tassi soglia, TEGM, istruzioni Banca d'Italia, contratto, estratti conto e conteggi",
            ],
            articles=[
                "Articoli c.c. su interessi, mora, anatocismo e responsabilità; TUB e L. 108/1996 quando pertinenti",
            ],
            decrees=[
                "D.M. MEF trimestrali sui tassi soglia, D.Lgs. 385/1993 TUB e provvedimenti Banca d'Italia",
            ],
            cases=[
                "Cassazione bancaria, decisioni ABF e precedenti su usura, interessi, trasparenza e prova contabile",
            ],
            steps=[
                "Selezionare trimestre, categoria, capitale, decorrenza, documento contabile e quesito tecnico prima della risposta Lex",
            ],
        )
    if any(token in haystack for token in ("privacy", "gdpr", "garante", "dati personali")):
        add(
            materials=[
                "GDPR, Codice privacy, provvedimenti, linee guida, sanzioni e reclami Garante",
            ],
            articles=[
                "Reg. UE 2016/679, D.Lgs. 196/2003, D.Lgs. 101/2018 e articoli su base giuridica, informativa, diritti e misure",
            ],
            decrees=[
                "Provvedimenti generali Garante, linee guida EDPB e regole tecniche collegate quando pertinenti",
            ],
            cases=[
                "Provvedimenti sanzionatori, ordinanze e giurisprudenza su danno, consenso, prova e responsabilità",
            ],
            steps=[
                "Collegare trattamento, base giuridica, documento informativo, prova del consenso o del rifiuto e misura correttiva",
            ],
        )
    if any(token in haystack for token in ("anac", "appalt", "contratti pubblici", "gara", "precontenzioso")):
        add(
            materials=[
                "Codice contratti, allegati, bandi, disciplinari, delibere ANAC, pareri e comunicati",
            ],
            articles=[
                "D.Lgs. 36/2023, allegati, norme su accesso atti, esclusione, soccorso istruttorio, rito appalti e termini",
            ],
            decrees=[
                "Correttivi, decreti attuativi, linee guida o provvedimenti ANAC collegati alla gara",
            ],
            cases=[
                "TAR, Consiglio di Stato, pareri ANAC, provvedimenti di ammissione/esclusione e udienze cautelari",
            ],
            steps=[
                "Individuare bando, provvedimento lesivo, termine di impugnazione, accesso atti e precedente utile prima del ricorso",
            ],
        )
    if any(token in haystack for token in ("lavoro", "inps", "inail", "previd", "infortun", "ministero lavoro")):
        add(
            materials=[
                "Norme lavoro/previdenza, circolari, messaggi, istruzioni operative e documenti amministrativi",
            ],
            articles=[
                "Statuto dei lavoratori, D.Lgs. 81/2015, D.Lgs. 150/2011, D.Lgs. 81/2008 e norme speciali previdenziali quando pertinenti",
            ],
            decrees=[
                "Decreti attuativi, circolari INPS/INAIL, istruzioni ministeriali e provvedimenti ispettivi",
            ],
            cases=[
                "Giurisprudenza lavoro/previdenza, verbali, accertamenti, CTU, udienze e provvedimenti su prova e termini",
            ],
            steps=[
                "Collegare domanda amministrativa, provvedimento, termine, documento sanitario/contributivo e prova da produrre",
            ],
        )
    if any(token in haystack for token in ("agcom", "agcm", "consum", "conciliaweb", "corecom", "concorren")):
        add(
            materials=[
                "Provvedimenti autorità, reclami, delibere, bollettini, conciliazioni e documenti probatori",
            ],
            articles=[
                "Codice consumo, Codice comunicazioni elettroniche, norme su pratiche scorrette, clausole e tutela utenti",
            ],
            decrees=[
                "D.Lgs. 206/2005, D.Lgs. 259/2003, regolamenti AGCOM/AGCM e delibere procedurali",
            ],
            cases=[
                "Provvedimenti AGCM/AGCOM, decisioni Corecom/ConciliaWeb e giurisprudenza su prova, indennizzo o clausola",
            ],
            steps=[
                "Partire da reclamo, prova comunicazione, provvedimento autorità e termine di conciliazione o azione",
            ],
        )
    if any(token in haystack for token in ("eur_lex", "eurlex", "curia", "cgue", "unione europea", "diritto ue", "guue", "europa")):
        add(
            materials=[
                "Regolamenti, direttive, decisioni, GUUE e atti preparatori UE pertinenti",
            ],
            articles=[
                "Norme UE direttamente applicabili, norme nazionali di recepimento e articoli della Carta dei diritti UE quando pertinenti",
            ],
            decrees=[
                "D.Lgs. di recepimento, regolamenti attuativi nazionali e transitori UE/nazionali",
            ],
            cases=[
                "Sentenze CGUE, conclusioni dell'Avvocato generale e precedenti europei su interpretazione vincolante",
            ],
            steps=[
                "Verificare versione linguistica, vigenza UE, recepimento nazionale e compatibilità con il caso concreto",
            ],
        )
    if any(token in haystack for token in ("hudoc", "cedu", "corte europea", "diritti fondamentali")):
        add(
            materials=[
                "CEDU, protocolli, casi HUDOC e criteri su equo processo, proprietà, vita privata e garanzie difensive",
            ],
            articles=[
                "Articoli CEDU, Costituzione e norme processuali nazionali che dialogano con il diritto convenzionale",
            ],
            cases=[
                "Sentenze e decisioni CEDU con fatto, violazione, rimedio e impatto sulla strategia nazionale",
            ],
            steps=[
                "Verificare ricevibilità, termine, esaurimento rimedi interni e collegamento al motivo di causa",
            ],
        )
    if row.registry == "lex_operational_sources" or "studio/tenant" in haystack or "fonte locale" in haystack or "fonte_locale" in haystack or "fonti interne studio" in haystack:
        add(
            materials=[
                "Documenti del fascicolo, PEC, agenda, scadenziario, prove, verbali, atti prodotti e cronologia dello studio",
            ],
            articles=[
                "Norme e articoli richiamati dai documenti interni, da verificare sempre su fonte ufficiale prima della citazione",
            ],
            cases=[
                "Udienze, provvedimenti, sentenze ed esiti del fascicolo caricati nel tenant dello studio",
            ],
            steps=[
                "Mantenere isolamento tenant e distinguere prova interna da fonte ufficiale esterna",
            ],
        )
    return {
        "legal_materials": _dedupe_list(legal_materials),
        "articles_and_codes": _dedupe_list(articles_and_codes),
        "decrees_and_rules": _dedupe_list(decrees_and_rules),
        "case_law_and_hearings": _dedupe_list(case_law_and_hearings),
        "research_steps": _dedupe_list(research_steps),
    }


def _apply_legal_material_profile(row: SourceAuditRow) -> None:
    profile = _legal_material_profile(row)
    row.legal_materials = _dedupe_list([*row.legal_materials, *profile["legal_materials"]])
    row.articles_and_codes = _dedupe_list([*row.articles_and_codes, *profile["articles_and_codes"]])
    row.decrees_and_rules = _dedupe_list([*row.decrees_and_rules, *profile["decrees_and_rules"]])
    row.case_law_and_hearings = _dedupe_list([*row.case_law_and_hearings, *profile["case_law_and_hearings"]])
    row.research_steps = _dedupe_list([*row.research_steps, *profile["research_steps"]])


def _row_key(row: SourceAuditRow) -> str:
    normalized_id = SOURCE_CANONICAL_IDS.get(_id(row.source_id or row.title), _id(row.source_id or row.title))
    normalized_url = _text(row.url).rstrip("/").lower()
    if normalized_id:
        return normalized_id
    if normalized_url:
        return f"url:{normalized_url}"
    return _id(row.title)


def _merge_rows(rows: list[SourceAuditRow]) -> list[SourceAuditRow]:
    merged: dict[str, SourceAuditRow] = {}
    for row in rows:
        key = _row_key(row)
        if key in merged:
            merged[key].merge(row)
        else:
            merged[key] = row
    return sorted(merged.values(), key=lambda item: (not item.official, item.source_id, item.registry))


def _classify_delivery(row: SourceAuditRow) -> None:
    if not _text(row.url):
        row.url = SOURCE_ENTRYPOINTS.get(_id(row.source_id), "")
    has_url = bool(_text(row.url))
    product_destinations = {
        "ricerca_legale",
        "lex_rag",
        "template_editor",
        "guida_pratica",
        "scadenziario",
        "legal_updates",
        "normative_db",
    }
    reaches_product = bool(row.destinations & product_destinations)
    gaps: list[str] = []
    is_local_placeholder = row.registry == "lex_official_config" and row.category == "fonte_locale"
    if row.enabled is False and row.registry == "lex_official_config" and not is_local_placeholder:
        gaps.append("fonte disattivata nella configurazione di acquisizione")
    if not has_url and row.registry not in {"lex_operational_sources"} and not is_local_placeholder:
        gaps.append("manca URL o entrypoint ufficiale controllabile")
    if not reaches_product:
        gaps.append("non risulta collegata a Ricerca Legale, Lex/RAG, Guida, editor, scadenziario o aggiornamenti")
    if row.official and row.registry == "legal_source_engine" and row.enabled is not True:
        row.notes.append(
            "Adapter ufficiale censito: la rete resta governata da configurazione runtime, ma la scheda fonte è pubblicabile in Ricerca Legale e Lex/RAG."
        )

    row.lawyer_use = _lawyer_use(row.source_id, row.title, row.authority, row.category, " ".join(row.topics))
    row.practice_phase, row.expected_output, row.professional_context = _professional_context(row)
    _apply_legal_material_profile(row)
    if is_local_placeholder:
        row.delivery_status = "contesto_non_ufficiale"
        row.gap_reason = "fonte locale di studio: richiede caricamento documentale tenant-aware, non URL pubblico"
        row.activation_action = "Collegare cartelle o documenti dello studio tramite import autorizzato tenant-aware; non usare come fonte ufficiale esterna."
        row.lex_test_question = "Quali fonti interne dello studio sono state caricate per questa pratica e quali limiti devo dichiarare?"
        row.practice_phase = "fonti interne e fascicolo"
        row.expected_output = "documenti studio caricati, tenant isolato, citazioni interne e limiti probatori"
        row.professional_context = "Le fonti locali servono solo se acquisite nel tenant dello studio e collegate a fascicolo, modello o prova: non sostituiscono fonti ufficiali."
        _apply_legal_material_profile(row)
        return
    if gaps == ["fonte disattivata nella configurazione di acquisizione"] and has_url and reaches_product:
        row.delivery_status = "da_attivare_controllabile"
        row.gap_reason = "fonte ufficiale visibile in Ricerca Legale ma non ancora acquisita automaticamente"
        row.activation_action = _activation_action(row)
        row.lex_test_question = _lex_test_question(row)
        return
    if gaps:
        row.delivery_status = "gap"
        row.gap_reason = "; ".join(gaps)
        row.activation_action = _activation_action(row)
        row.lex_test_question = _lex_test_question(row)
        return
    if row.official:
        row.delivery_status = "operativa_controllabile"
        row.gap_reason = ""
    else:
        row.delivery_status = "contesto_non_ufficiale"
        row.gap_reason = "fonte non ufficiale: utilizzabile solo come know-how o confronto, non come copertura sufficiente"
    row.activation_action = _activation_action(row)
    row.lex_test_question = _lex_test_question(row)


def _lex_config_rows() -> list[SourceAuditRow]:
    rows: list[SourceAuditRow] = []
    for source in load_sources(OFFICIAL_CONFIG):
        urls = _urls_from_settings(source.settings)
        url = urls[0] if urls else _text(source.base_url)
        destinations = {"legal_updates", "lex_rag", "ricerca_legale"} if source.enabled else {"ricerca_legale"}
        if source.connector in {"static_urls", "gazzetta_ufficiale", "normattiva_collection"}:
            destinations.add("legal_updates")
        rows.append(
            SourceAuditRow(
                registry="lex_official_config",
                source_id=source.id,
                title=source.name,
                official=source.type not in {"fonte_locale"},
                authority=source.name,
                url=url,
                enabled=source.enabled,
                connector=source.connector,
                category=source.type,
                topics=list(source.topics),
                destinations=destinations,
                notes=[
                    f"refresh={source.refresh}",
                    f"priorità={source.priority}",
                    f"entrypoint configurati={len(urls)}",
                ],
            )
        )
    return rows


def _legal_engine_rows() -> list[SourceAuditRow]:
    registry = create_default_registry(env={})
    rows: list[SourceAuditRow] = []
    for source in registry.all_sources():
        meta = source.metadata
        enabled = registry.is_source_enabled(meta.source_id)
        rows.append(
            SourceAuditRow(
                registry="legal_source_engine",
                source_id=meta.source_id,
                title=meta.display_name,
                official=meta.official,
                authority=meta.display_name,
                url=meta.base_url,
                enabled=enabled,
                connector="native_adapter",
                category=meta.category,
                topics=[meta.category, meta.jurisdiction],
                destinations={"lex_rag", "ricerca_legale"} if enabled else {"ricerca_legale"},
                notes=[
                    f"supporta ricerca={meta.supports_search}",
                    f"versioni={meta.supports_versions}",
                    f"autenticazione richiesta={meta.requires_auth}",
                ],
            )
        )
    return rows


def _research_policy_rows() -> list[SourceAuditRow]:
    data = yaml.safe_load(RESEARCH_REGISTRY.read_text(encoding="utf-8"))
    rows: list[SourceAuditRow] = []
    for item in data.get("sources", []):
        if not isinstance(item, dict):
            continue
        entrypoints = item.get("entrypoints") if isinstance(item.get("entrypoints"), dict) else {}
        url = _text(next(iter(entrypoints.values()), "")) or _text(item.get("base_url"))
        rows.append(
            SourceAuditRow(
                registry="research_source_policy",
                source_id=_text(item.get("key")),
                title=_text(item.get("label") or item.get("key")),
                official=bool(item.get("official")),
                authority=_text(item.get("label") or item.get("key")),
                url=url,
                enabled=item.get("status") not in {"disabled"},
                connector=_text(item.get("status")),
                category=_text(item.get("category")),
                topics=[*_dedupe_list(item.get("use_cases") or []), *_dedupe_list(item.get("formats") or [])],
                destinations={"ricerca_legale", "lex_rag"},
                notes=[f"priorità={item.get('priority')}", f"auth={item.get('auth')}"],
            )
        )
    return rows


def _source_capability_rows() -> list[SourceAuditRow]:
    rows: list[SourceAuditRow] = []
    for code, capability in SOURCE_CAPABILITIES.items():
        destinations: set[str] = {"legal_updates"}
        if capability.rag_destination not in {"none", ""}:
            destinations.add("lex_rag")
        if capability.publication_destination not in {"out_of_scope", ""}:
            destinations.add("ricerca_legale")
        if "telematico" in capability.rag_destination or "telematico" in capability.publication_destination:
            destinations.add("template_editor")
        rows.append(
            SourceAuditRow(
                registry="legal_update_capability",
                source_id=code,
                title=code.replace("_", " ").title(),
                official=capability.publication_destination != "out_of_scope",
                authority=code.replace("_", " ").title(),
                enabled=capability.publication_destination != "out_of_scope",
                connector=capability.item_strategy,
                category=capability.publication_destination,
                topics=[capability.relevance_policy, capability.rag_destination, capability.jurisprudence_destination],
                destinations=destinations,
                notes=[
                    f"dettaglio={capability.detail_strategy}",
                    f"allegati={capability.attachment_strategy}",
                    capability.exclusion_policy,
                ],
            )
        )
    return rows


def _legal_update_source_rows() -> list[SourceAuditRow]:
    rows: list[SourceAuditRow] = []
    for source in DEFAULT_SOURCE_ROWS:
        if not isinstance(source, dict):
            continue
        code = _text(source.get("code"))
        enabled = bool(source.get("enabled"))
        destinations: set[str] = {"legal_updates", "ricerca_legale"}
        capability = SOURCE_CAPABILITIES.get(code)
        if capability and capability.rag_destination not in {"", "none"}:
            destinations.add("lex_rag")
        if capability and "telematico" in f"{capability.rag_destination} {capability.publication_destination}":
            destinations.add("template_editor")
        if code.startswith("openga_") or "sentenz" in code or "cassazione" in code:
            destinations.add("lex_rag")
        rows.append(
            SourceAuditRow(
                registry="legal_update_sources",
                source_id=code,
                title=_text(source.get("name") or code),
                official=bool(source.get("is_official")),
                authority=_text(source.get("name") or code),
                url=_text(source.get("base_url")),
                enabled=enabled,
                connector=_text(source.get("parser_type")),
                category=_text(source.get("category")),
                topics=_dedupe_list([source.get("notes"), source.get("source_type"), source.get("trust_class")]),
                destinations=destinations,
                notes=[
                    f"polling_minuti={source.get('polling_minutes')}",
                    f"classe={source.get('trust_class')}",
                    f"parser={source.get('parser_type')}",
                ],
            )
        )
    return rows


def _template_source_rows() -> list[SourceAuditRow]:
    rows: list[SourceAuditRow] = []
    for source in TEMPLATE_ATTI_LEGAL_SOURCES:
        if not isinstance(source, dict):
            continue
        rows.append(
            SourceAuditRow(
                registry="template_atti_sources",
                source_id=_text(source.get("id")),
                title=_text(source.get("title")),
                official=_text(source.get("source_type")) not in {"fonte_secondaria_non_ufficiale"},
                authority=_text(source.get("authority") or source.get("source_title")),
                url=_text(source.get("official_url")),
                enabled=not bool(source.get("deprecated")),
                connector="template_registry",
                category=_text(source.get("source_type")),
                topics=_dedupe_list(
                    [
                        source.get("scope"),
                        source.get("role"),
                        *list(source.get("applies_to_prefixes") or []),
                        *list(source.get("match_terms") or []),
                    ]
                ),
                destinations={"ricerca_legale", "lex_rag", "template_editor"},
                notes=[
                    f"ruolo={source.get('role')}",
                    f"verifica={source.get('verification_status')}",
                    f"ultima_verifica={source.get('last_verified_at')}",
                ],
            )
        )
    return rows


def _guida_source_rows() -> list[SourceAuditRow]:
    rows: list[SourceAuditRow] = []
    for source_id, source in sorted(GUIDA_PRATICA_SOURCE_LIBRARY.items()):
        if not isinstance(source, dict):
            continue
        rows.append(
            SourceAuditRow(
                registry="guida_pratica_sources",
                source_id=source_id,
                title=_text(source.get("title") or source_id),
                official=True,
                authority=_text(source.get("ente") or source.get("authority") or source.get("title")),
                url=_text(source.get("url")),
                enabled=True,
                connector="guida_pratica_web_enrichment",
                category=_text(source.get("type") or source.get("role")),
                topics=_dedupe_list([source.get("ambito"), source.get("role"), source.get("ente")]),
                destinations={"ricerca_legale", "lex_rag", "guida_pratica", "scadenziario"},
                notes=[f"ambito={source.get('ambito')}", f"ruolo={source.get('role')}"],
            )
        )
    return rows


def _normative_db_rows() -> list[SourceAuditRow]:
    rows: list[SourceAuditRow] = []
    for code, source in FONTI_OPERATIVE.items():
        source_dict = source.to_dict()
        rows.append(
            SourceAuditRow(
                registry="normative_db_sources",
                source_id=code,
                title=_text(source_dict.get("title")),
                official=True,
                authority=_text(source_dict.get("authority") or source_dict.get("title")),
                url=_text(source_dict.get("url")),
                enabled=True,
                connector="normative_tables",
                category=_text(source_dict.get("kind") or "fonte normativa operativa"),
                topics=_dedupe_list([source_dict.get("description"), source_dict.get("authority")]),
                destinations={"ricerca_legale", "lex_rag", "normative_db"},
                notes=[f"versione={source_dict.get('version')}", f"consultata={source_dict.get('last_checked_at')}"],
            )
        )
    return rows


def _operational_source_rows() -> list[SourceAuditRow]:
    rows: list[SourceAuditRow] = []
    for source in DEFAULT_SOURCE_DEFINITIONS:
        rows.append(
            SourceAuditRow(
                registry="lex_operational_sources",
                source_id=source.source_id,
                title=source.display_name,
                official=bool(source.official_public_source),
                authority="Studio/Tenant" if source.internal else "Fonte pubblica",
                enabled=True,
                connector=source.repository_module,
                category=source.category,
                topics=_dedupe_list([source.source_type, source.category, source.notes, *source.deterministic_tools]),
                destinations={"lex_rag"},
                notes=[
                    f"tenant_keys={', '.join(source.tenant_keys)}",
                    f"permessi={', '.join(source.required_permissions)}",
                    f"sensibile={source.sensitive}",
                ],
            )
        )
    return rows


def build_audit() -> dict[str, Any]:
    raw_rows = [
        *_lex_config_rows(),
        *_legal_engine_rows(),
        *_research_policy_rows(),
        *_legal_update_source_rows(),
        *_source_capability_rows(),
        *_template_source_rows(),
        *_guida_source_rows(),
        *_normative_db_rows(),
        *_operational_source_rows(),
    ]
    rows = _merge_rows(raw_rows)
    for row in rows:
        _classify_delivery(row)
    row_dicts = [row.to_dict() for row in rows]
    gaps = [row for row in row_dicts if row["delivery_status"] == "gap"]
    official_gaps = [row for row in gaps if row["official"]]
    activation_pending = [row for row in row_dicts if row["delivery_status"] == "da_attivare_controllabile"]
    summary = {
        "audit_date": AUDIT_DATE,
        "total_sources": len(row_dicts),
        "official_sources": sum(1 for row in row_dicts if row["official"]),
        "operational_sources": sum(1 for row in row_dicts if row["delivery_status"] == "operativa_controllabile"),
        "activation_pending_sources": len(activation_pending),
        "context_sources": sum(1 for row in row_dicts if row["delivery_status"] == "contesto_non_ufficiale"),
        "gaps": len(gaps),
        "official_gaps": len(official_gaps),
        "sources_with_legal_materials": sum(1 for row in row_dicts if row.get("legal_materials")),
        "sources_with_articles_and_codes": sum(1 for row in row_dicts if row.get("articles_and_codes")),
        "sources_with_decrees_and_rules": sum(1 for row in row_dicts if row.get("decrees_and_rules")),
        "sources_with_case_law_and_hearings": sum(1 for row in row_dicts if row.get("case_law_and_hearings")),
        "sources_with_research_steps": sum(1 for row in row_dicts if row.get("research_steps")),
        "registries": {
            registry: sum(1 for row in row_dicts if row["registry"] == registry)
            for registry in sorted({row["registry"] for row in row_dicts})
        },
        "gap_reasons": {
            reason: sum(1 for row in gaps if reason in row["gap_reason"])
            for reason in sorted({reason for row in gaps for reason in row["gap_reason"].split("; ") if reason})
        },
    }
    return {"summary": summary, "sources": row_dicts}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "registry",
        "source_id",
        "title",
        "official",
        "authority",
        "url",
        "enabled",
        "connector",
        "category",
        "topics",
        "destinations",
        "delivery_status",
        "gap_reason",
        "lawyer_use",
        "activation_action",
        "lex_test_question",
        "practice_phase",
        "expected_output",
        "professional_context",
        "legal_materials",
        "articles_and_codes",
        "decrees_and_rules",
        "case_law_and_hearings",
        "research_steps",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            for key in (
                "topics",
                "destinations",
                "legal_materials",
                "articles_and_codes",
                "decrees_and_rules",
                "case_law_and_hearings",
                "research_steps",
                "notes",
            ):
                serialized[key] = " | ".join(str(item) for item in serialized.get(key) or [])
            writer.writerow(serialized)


def _audit_material_summary(row: dict[str, Any]) -> str:
    chunks: list[str] = []
    fields = (
        ("Materiali", "legal_materials"),
        ("Codici/articoli", "articles_and_codes"),
        ("Decreti/regole", "decrees_and_rules"),
        ("Sentenze/udienze", "case_law_and_hearings"),
    )
    for label, key in fields:
        values = [str(item) for item in row.get(key) or [] if _text(item)]
        if values:
            chunks.append(f"{label}: {'; '.join(values[:2])}")
    return " | ".join(chunks)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    gaps = [row for row in payload["sources"] if row["delivery_status"] == "gap"]
    official_gaps = [row for row in gaps if row["official"]]
    lines = [
        "# Audit consegna fonti legali",
        "",
        f"Data audit: {AUDIT_DATE}.",
        "",
        "Questo audit controlla se le fonti già presenti nel progetto arrivano davvero al prodotto: Ricerca Legale, Lex AI/RAG Legal, Guida Pratica, Scadenziario, Template Atti/editor, aggiornamenti legali o DB normativa.",
        "",
        "## Sintesi",
        "",
        f"- Fonti totali censite: {summary['total_sources']}",
        f"- Fonti ufficiali: {summary['official_sources']}",
        f"- Fonti operative e controllabili: {summary['operational_sources']}",
        f"- Fonti ufficiali in acquisizione governata: {summary['activation_pending_sources']}",
        f"- Fonti di contesto non ufficiale: {summary['context_sources']}",
        f"- Fonti da completare: {summary['gaps']}",
        f"- Fonti ufficiali da completare: {summary['official_gaps']}",
        f"- Fonti con materiali giuridici espliciti: {summary['sources_with_legal_materials']}",
        f"- Fonti con articoli/codici espliciti: {summary['sources_with_articles_and_codes']}",
        f"- Fonti con decreti/regole esplicite: {summary['sources_with_decrees_and_rules']}",
        f"- Fonti con sentenze/udienze/provvedimenti espliciti: {summary['sources_with_case_law_and_hearings']}",
        "",
        "## Registri attraversati",
        "",
    ]
    for registry, count in summary["registries"].items():
        lines.append(f"- `{registry}`: {count}")
    lines.extend(["", "## Fonti da completare", ""])
    if not gaps:
        lines.append("Nessuna fonte da completare rilevata.")
    else:
        for reason, count in summary["gap_reasons"].items():
            lines.append(f"- {reason}: {count}")
    lines.extend(["", "## Fonti ufficiali da chiudere", ""])
    if not official_gaps:
        lines.append("Nessuna fonte ufficiale da completare.")
    else:
        for row in official_gaps[:80]:
            destinations = ", ".join(row["destinations"]) or "nessuna destinazione"
            materials = _audit_material_summary(row)
            suffix = f" Materiali: {materials}." if materials else ""
            lines.append(
                f"- `{row['source_id']}` ({row['registry']}): {row['title']} - {row['gap_reason']}. Destinazioni: {destinations}. Uso avvocato: {row['lawyer_use']}.{suffix}"
            )
    lines.extend(["", "## Fonti operative controllabili", ""])
    for row in payload["sources"]:
        if row["delivery_status"] != "operativa_controllabile":
            continue
        destinations = ", ".join(row["destinations"]) or "nessuna destinazione"
        materials = _audit_material_summary(row)
        material_suffix = f" Materiali: {materials}." if materials else ""
        lines.append(f"- `{row['source_id']}`: {row['title']} -> {destinations}.{material_suffix}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit consegna fonti legali verso Ricerca Legale, Lex/RAG e UI.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-official-gaps", action="store_true")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = build_audit()
    stem = f"legal-source-delivery-audit-{AUDIT_DATE}"
    _write_json(output_dir / f"{stem}.json", payload)
    _write_csv(output_dir / f"{stem}.csv", payload["sources"])
    _write_markdown(output_dir / f"{stem}.md", payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    if args.fail_on_official_gaps and payload["summary"]["official_gaps"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
