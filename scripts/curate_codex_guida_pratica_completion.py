from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_TARGET = ROOT / "pct" / "data" / "legal_knowledge_base_modules" / "kb_99_completamento_codici_ufficiali.json"
DEFAULT_REPORT = ROOT / "artifacts" / "guida-pratica" / "codex-guida-pratica-curation-report.json"
DEFAULT_CSV = ROOT / "artifacts" / "guida-pratica" / "codex-guida-pratica-curation-audit.csv"

CURATION_DATE = "2026-05-22"
CURATION_SOURCE = "codex_ricerca_curata_fonti_ufficiali_2026_05_22"

OFFICIAL_SOURCES: dict[str, dict[str, str]] = {
    "normattiva_cpc": {
        "tipo": "normativa",
        "fonte": "Normattiva",
        "titolo": "Codice di procedura civile, R.D. 28 ottobre 1940, n. 1443",
        "url": "https://www.normattiva.it/eli/stato/REGIO_DECRETO/1940/10/28/1443/CONSOLIDATED",
        "uso": "rito, termini, notifiche, costituzione, impugnazioni, cautelari, volontaria giurisdizione ed esecuzione",
    },
    "normattiva_cc": {
        "tipo": "normativa",
        "fonte": "Normattiva",
        "titolo": "Codice civile, R.D. 16 marzo 1942, n. 262",
        "url": "https://www.normattiva.it/eli/stato/REGIO_DECRETO/1942/03/16/262/CONSOLIDATED",
        "uso": "presupposti sostanziali, prescrizione, decadenza, diritti reali, famiglia, successioni, societario",
    },
    "normattiva_l742_1969": {
        "tipo": "normativa",
        "fonte": "Normattiva",
        "titolo": "L. 7 ottobre 1969, n. 742, sospensione feriale dei termini processuali",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=069U0742",
        "uso": "verifica sospensione feriale, esclusioni e regimi speciali",
    },
    "normattiva_dlg149_2022": {
        "tipo": "normativa",
        "fonte": "Normattiva",
        "titolo": "D.Lgs. 10 ottobre 2022, n. 149, riforma del processo civile",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2022;149=",
        "uso": "procedimenti persone, minorenni e famiglie, razionalizzazione esecuzione e modifiche Cartabia",
    },
    "normattiva_ccii": {
        "tipo": "normativa",
        "fonte": "Normattiva",
        "titolo": "D.Lgs. 12 gennaio 2019, n. 14, Codice della crisi d'impresa e dell'insolvenza",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=19G00007",
        "uso": "procedure concorsuali, crisi, liquidazione giudiziale e strumenti di regolazione",
    },
    "pst_specifiche_dm44_2024": {
        "tipo": "tecnica",
        "fonte": "Portale Servizi Telematici, Ministero della Giustizia",
        "titolo": "Specifiche tecniche ex art. 34 D.M. 44/2011, provvedimento 7 agosto 2024",
        "url": "https://pst.giustizia.it/PST/resources/cms/documents/m_dg.DOG07.07082024.0004292.ID_SPECIFICHETECNICHE_DM_44_2011_FINALE_31_.pdf",
        "uso": "deposito telematico, servizi PST, fascicolo informatico, busta e trattamento dati",
    },
    "pst_comunicazioni_notifiche": {
        "tipo": "tecnica",
        "fonte": "Portale Servizi Telematici, Ministero della Giustizia",
        "titolo": "Comunicazioni e notificazioni telematiche",
        "url": "https://servizipst.giustizia.it/PST/it/pst_1_7.wp",
        "uso": "PEC, RegIndE, comunicazioni di cancelleria e prerequisiti telematici",
    },
    "catalogo_pst_xsd_locale": {
        "tipo": "catalogo_locale_verificato",
        "fonte": "IUSENTRA",
        "titolo": "Catalogo codici oggetto PST/XSD locale verificato",
        "url": "pct/data/cataloghi/codici_oggetto_pst.json",
        "uso": "codice oggetto, registro, file XSD e depositabilità",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _text(value).casefold()


def _unique_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _article_sources(label: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for match in re.finditer(
        r"art\.?\s*(?P<num>\d+(?:[- ]?(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|undecies|duodecies))?)\s*(?P<body>c\.?\s*p\.?\s*c\.?|cpc|c\.?\s*c\.?|cc|c\.?\s*p\.?\s*i\.?|cpi)?",
        label,
        re.I,
    ):
        body = (match.group("body") or "").lower().replace(" ", "")
        fonte = "c.p.c."
        source_key = "normattiva_cpc"
        if body in {"c.c.", "cc", "c.c"}:
            fonte = "c.c."
            source_key = "normattiva_cc"
        elif body in {"c.p.i.", "cpi", "c.p.i"}:
            fonte = "c.p.i."
            source_key = "normattiva_cpc"
        refs.append(
            {
                "fonte": fonte,
                "articolo": match.group("num").replace(" ", "-"),
                "descrizione": f"Riferimento espresso nella denominazione della pratica: art. {match.group('num')} {fonte}.",
                "source_registry_key": source_key,
                "verifica": "estratto dalla denominazione, da controllare sul testo vigente prima dell'uso redazionale",
            }
        )
    return refs


def _source_refs(*keys: str) -> list[dict[str, str]]:
    return [deepcopy(OFFICIAL_SOURCES[key]) for key in keys if key in OFFICIAL_SOURCES]


def _common_source_keys() -> list[str]:
    return ["catalogo_pst_xsd_locale", "normattiva_cpc", "normattiva_l742_1969", "pst_specifiche_dm44_2024", "pst_comunicazioni_notifiche"]


def infer_profile(item: dict[str, Any]) -> str:
    hay = " ".join(
        _lower(item.get(key))
        for key in ("codice", "denominazione", "categoria", "sottocategoria", "rito")
    )
    if any(token in hay for token in ("ingiun", "decreto ingiuntivo", "di ante causam")):
        return "monitorio"
    if any(token in hay for token in ("accertamento tecnico", "consulenza tecnica preventiva", "696-bis", "696 bis", "art. 696")):
        return "atp_istruzione_preventiva"
    if any(token in hay for token in ("cautelar", "sequestro", "700", "urgenza")):
        return "cautelare"
    if any(token in hay for token in ("opposizione", "reclamo", "impugn", "appello", "revocazione", "cassazione")):
        return "impugnazione"
    if any(token in hay for token in ("esecuz", "pignor", "precetto", "rilascio", "vendita forzata", "g.e.")):
        return "esecuzione"
    if any(token in hay for token in ("lavor", "previd", "licenziamento", "inail", "inps", "pubblico impiego")):
        return "lavoro_previdenza"
    if any(token in hay for token in ("fallimento", "concors", "crisi", "insolvenza", "liquidazione", "concordato")):
        return "crisi_impresa"
    if any(token in hay for token in ("impresa", "societ", "c.p.i", "cpi", "march", "brevet", "concorrenza", "segreti commerciali")):
        return "impresa_societario"
    if any(token in hay for token in ("famiglia", "minori", "minoren", "figli", "adozione", "curatela", "giudice tutelare", "persone, minorenni", "diritti della persona")):
        return "famiglia_minori"
    if any(token in hay for token in ("immigrazione", "protezione internazionale", "cittadinanza", "stranier")):
        return "immigrazione_cittadinanza"
    if "volontaria giurisdizione" in hay or "giudice tutelare" in hay:
        return "volontaria_giurisdizione"
    return "contenzioso_ordinario"


def _termine(
    termine: str,
    *,
    decorrenza: str,
    norma: str,
    natura: str = "presidio processuale",
    giorni: int | None = None,
    mesi: int | None = None,
    anni: int | None = None,
    criticita: str = "",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "termine": termine,
        "decorrenza": decorrenza,
        "natura": natura,
        "norma": norma,
        "criticita": criticita or "Confermare sempre evento generatore, rito applicabile, sospensione feriale ed eventuali termini speciali del provvedimento.",
        "fonte_verifica": "Normattiva/PST + catalogo PST/XSD locale",
        "curato_da": "codex",
        "richiede_verifica_avvocato": True,
    }
    if giorni is not None:
        row["giorni"] = giorni
    if mesi is not None:
        row["mesi"] = mesi
    if anni is not None:
        row["anni"] = anni
    return row


def profile_payload(profile: str, item: dict[str, Any]) -> dict[str, Any]:
    label = _text(item.get("denominazione"))
    base_sources = _common_source_keys()
    profile_sources = {
        "famiglia_minori": ["normattiva_cc", "normattiva_dlg149_2022"],
        "lavoro_previdenza": ["normattiva_cpc"],
        "crisi_impresa": ["normattiva_ccii", "normattiva_cc"],
        "impresa_societario": ["normattiva_cc"],
        "volontaria_giurisdizione": ["normattiva_cc"],
        "immigrazione_cittadinanza": ["normattiva_cpc"],
    }.get(profile, [])
    sources = _source_refs(*base_sources, *profile_sources)

    common_terms = [
        _termine(
            "Presidio preliminare di prescrizione, decadenza e condizioni di procedibilità",
            decorrenza="Dall'evento sostanziale indicato nel fascicolo o dalla comunicazione/notifica rilevante",
            norma="c.c. artt. 2934 ss. e 2964 ss.; rito speciale applicabile",
            natura="presidio preliminare",
            criticita="Non è una scadenza automatica unica: Lex e Guida devono chiedere evento, data, materia e rito prima di calcolare.",
        ),
        _termine(
            "Termini fissati dal giudice o dalla cancelleria nel provvedimento di trattazione",
            decorrenza="Dalla comunicazione, notificazione o conoscenza legale del provvedimento",
            norma="c.p.c. art. 155 e disposizioni del rito applicabile",
            natura="termine di fase",
            criticita="Deve essere letto dal provvedimento concreto e non dedotto solo dal codice oggetto.",
        ),
    ]

    config = {
        "profile": profile,
        "profile_label": "Contenzioso civile ordinario",
        "source_keys": [src["titolo"] for src in sources],
        "prima_cosa_da_fare": "Verificare competenza, rito, parti, valore, condizioni di procedibilità e data degli eventi già acquisiti nel fascicolo.",
        "focus": [
            "allineare oggetto pratica, codice PST/XSD e petitum effettivo",
            "controllare legittimazione, valore, competenza e documenti fondativi",
            "presidiare termini di notifica, costituzione, memorie e impugnazione secondo il rito concreto",
        ],
        "presupposti": [
            "Il fascicolo deve contenere cliente, controparte, ufficio, oggetto pratica, codice oggetto, valore, rito, fase, documenti, scadenze e note.",
            "Il codice PST/XSD va usato per classificare il deposito, non per sostituire l'analisi del petitum e delle condizioni di procedibilità.",
            "Prima dell'atto verificare prescrizione, decadenza, mediazione/negoziazione o altra condizione di procedibilità eventualmente applicabile.",
        ],
        "adempimenti": [
            "Controllare ufficio competente, valore e foro territoriale con i dati già presenti nel fascicolo.",
            "Verificare procura, preventivo/conferimento incarico, privacy, antiriciclaggio e conflitto di interessi se presenti nello studio.",
            "Raccogliere documenti fondativi, prove, diffide, notifiche, ricevute PEC e cronologia degli eventi.",
            "Preparare atto e allegati usando il template coerente, senza ricreare campi già acquisiti dal fascicolo.",
            "Prima del deposito controllare busta, firma, DatiAtto.xml, contributo unificato e ricevute.",
        ],
        "termini": common_terms,
        "tipologie_di_intervento": [
            {"id": "atto_introduttivo", "label": "Atto introduttivo o istanza principale", "quando": "quando il fascicolo deve avviare o riassumere il procedimento"},
            {"id": "integrazione_documentale", "label": "Integrazione documentale o memoria", "quando": "quando il provvedimento o la fase richiede chiarimenti, documenti o note"},
            {"id": "istanza_accessoria", "label": "Istanza accessoria o cautelativa", "quando": "quando serve presidiare urgenza, prova, sospensione o misura temporanea"},
        ],
        "legittimati_attivi": [
            {"soggetto": "parte titolare del diritto o dell'interesse sostanziale", "verifica": "controllare titolo, rappresentanza, capacità e interesse ad agire"},
            {"soggetto": "successore, rappresentante o avente causa", "verifica": "ammesso solo con documenti che provano qualità e poteri"},
        ],
        "obbligo_mediazione": {
            "stato": "da_verificare",
            "fonte": "art. 5 D.Lgs. 28/2010 e norme speciali applicabili",
            "criterio": "verificare materia sostanziale, non solo codice oggetto PST/XSD",
            "materie_tipiche": [
                "condominio",
                "diritti reali",
                "divisione",
                "successioni ereditarie",
                "locazione",
                "comodato",
                "affitto di azienda",
                "responsabilità medica e sanitaria",
                "contratti assicurativi, bancari e finanziari",
            ],
            "effetto": "se obbligatoria, va presidiata come condizione di procedibilità e collegata a fascicolo, scadenze e allegati",
        },
        "richiesta_provvedimenti_urgenti": {
            "ammissibile": "da_valutare",
            "quando": "se dal fascicolo emergono pericolo attuale, rischio di dispersione della prova o necessità di misura temporanea",
            "dati_da_verificare": ["fumus", "periculum", "documenti urgenza", "misura richiesta", "competenza"],
            "non_bloccante": True,
        },
        "avvertimenti_obbligatori": [
            "La Guida Pratica è facoltativa: aiuta l'avvocato ma non blocca fascicolo, redazione o deposito.",
            "Il codice oggetto PST/XSD non sostituisce la verifica di rito, competenza, valore, condizioni di procedibilità e termini.",
            "Se il dato è già nel fascicolo, nel preventivo, nel conferimento incarico o nella parcella, la guida deve leggerlo senza duplicarlo.",
            "Ogni termine processuale richiede conferma dell'evento generatore prima del calcolo automatico.",
            "Prima del deposito verificare busta, DatiAtto.xml, firma, contributo unificato, allegati e ricevute PEC.",
        ],
        "esiti_processuali_tipici": [
            {"esito": "accoglimento_totale_o_parziale", "descrizione": "Il giudice accoglie integralmente o parzialmente la domanda o l'istanza.", "frequenza": "variabile"},
            {"esito": "rigetto", "descrizione": "La domanda viene respinta per ragioni di merito, rito o prova.", "frequenza": "variabile"},
            {"esito": "inammissibilita_o_improcedibilita", "descrizione": "La domanda non supera un presupposto processuale o una condizione di procedibilità.", "frequenza": "da verificare"},
            {"esito": "integrazione_documentale_o_memorie", "descrizione": "Il giudice o la cancelleria richiede integrazioni, chiarimenti o memorie.", "frequenza": "variabile"},
            {"esito": "definizione_conciliante_o_transattiva", "descrizione": "La pratica si definisce con accordo, conciliazione, rinuncia o cessazione della materia del contendere.", "frequenza": "variabile"},
        ],
        "campi_specifici": [
            {"id": "evento_generatore_termine", "label": "Evento generatore del termine", "type": "date_or_event", "required": True},
            {"id": "condizione_procedibilita", "label": "Condizione di procedibilità verificata", "type": "textarea", "required": False},
        ],
        "allegati_specifici": [
            {"id": "cronologia_eventi", "label": "Cronologia eventi e notifiche rilevanti", "required": False},
        ],
        "avvertenze": [
            "La guida è facoltativa e non blocca il fascicolo: se un dato manca, rinvia alla sezione corretta invece di duplicarlo.",
            "I termini numerici vanno calcolati solo dopo conferma dell'evento generatore e delle eventuali sospensioni/esclusioni.",
        ],
    }

    if profile == "monitorio":
        config.update(
            profile_label="Procedimento monitorio",
            prima_cosa_da_fare="Verificare prova scritta, liquidità/esigibilità del credito, competenza e richiesta di provvisoria esecutorietà.",
            focus=[
                "identificare titolo del credito, importi, interessi e documento probatorio",
                "presidiare notifica del decreto e opposizione",
                "controllare eventuale clausola ADR o foro speciale prima del deposito",
            ],
            termini=[
                _termine("Notifica del decreto ingiuntivo", giorni=60, decorrenza="Dalla pronuncia del decreto", norma="c.p.c. art. 644", natura="termine di efficacia", criticita="Verificare disciplina per notifiche all'estero e casi particolari."),
                _termine("Opposizione a decreto ingiuntivo", giorni=40, decorrenza="Dalla notificazione del decreto", norma="c.p.c. artt. 641 e 645", natura="termine di impugnazione", criticita="Verificare riduzione/aumento del termine nel decreto e modalità di notificazione."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "credito_importo", "label": "Importo del credito", "type": "currency", "required": True},
                {"id": "prova_scritta", "label": "Prova scritta del credito", "type": "document_ref", "required": True},
                {"id": "interessi_e_spese", "label": "Interessi, rivalutazione e spese richieste", "type": "textarea", "required": False},
            ],
            allegati_specifici=[
                {"id": "titolo_credito", "label": "Titolo/documento del credito", "required": True},
                {"id": "conteggio_credito", "label": "Conteggio analitico di capitale, interessi e spese", "required": True},
            ],
            tipologie_di_intervento=[
                {"id": "ricorso_monitorio", "label": "Ricorso per decreto ingiuntivo", "quando": "credito liquido, esigibile e assistito da prova scritta"},
                {"id": "provvisoria_esecutorieta", "label": "Richiesta di provvisoria esecutorietà", "quando": "titolo qualificato, documentazione sottoscritta o pericolo grave nel ritardo"},
                {"id": "fase_opposizione", "label": "Gestione eventuale opposizione", "quando": "dopo notifica del decreto e opposizione dell'ingiunto"},
            ],
            legittimati_attivi=[
                {"soggetto": "creditore titolare del diritto", "verifica": "prova scritta, esigibilità e legittimazione"},
                {"soggetto": "cessionario o successore del credito", "verifica": "documenti di cessione, successione o rappresentanza"},
            ],
            obbligo_mediazione={
                "obbligatoria_fase_monitoria": False,
                "obbligatoria_fase_opposizione": "solo se la materia sostanziale rientra nell'art. 5 D.Lgs. 28/2010",
                "fonte": "D.Lgs. 28/2010 art. 5 e disciplina speciale post riforma Cartabia",
                "criterio": "verificare materia del credito e fase di opposizione",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "provvisoria esecutorietà o sospensione in opposizione",
                "quando": "ricorrono titolo qualificato, documentazione sottoscritta, grave pericolo nel ritardo o contestazioni sull'esecuzione",
                "dati_da_verificare": ["titolo", "pericolo nel ritardo", "opposizione", "istanze ex artt. 642, 648, 649 c.p.c."],
            },
            esiti_processuali_tipici=[
                {"esito": "decreto_accolto", "descrizione": "Emissione del decreto ingiuntivo con o senza provvisoria esecutorietà.", "frequenza": "alta"},
                {"esito": "rigetto_ex_640", "descrizione": "Rigetto o richiesta integrazione per prova insufficiente.", "frequenza": "variabile"},
                {"esito": "opposizione", "descrizione": "Instaurazione del giudizio di opposizione.", "frequenza": "media"},
                {"esito": "esecutorieta_per_mancata_opposizione", "descrizione": "Esecutorietà o definitività dopo mancata opposizione.", "frequenza": "alta"},
            ],
        )
    elif profile == "atp_istruzione_preventiva":
        config.update(
            profile_label="ATP e istruzione preventiva",
            prima_cosa_da_fare="Verificare interesse all'accertamento, oggetto tecnico, urgenza probatoria e documentazione sanitaria/contrattuale quando pertinente.",
            focus=[
                "definire il quesito tecnico e i documenti da sottoporre al consulente",
                "presidiare condizioni di procedibilità nelle materie in cui l'ATP è necessario o strategico",
                "controllare notifiche alle parti interessate e calendario delle operazioni peritali",
            ],
            termini=[
                _termine("Termini per osservazioni, nomina consulenti di parte e operazioni peritali", decorrenza="Dal provvedimento di nomina o dal calendario del CTU", norma="c.p.c. artt. 696 e 696-bis", natura="termine istruttorio", criticita="Leggere sempre il provvedimento: il termine è normalmente fissato dal giudice o dal CTU."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "quesito_tecnico", "label": "Quesito tecnico richiesto", "type": "textarea", "required": True},
                {"id": "documentazione_tecnica", "label": "Documentazione tecnica/sanitaria/contrattuale", "type": "document_ref", "required": True},
            ],
            allegati_specifici=[
                {"id": "documentazione_tecnica", "label": "Documentazione tecnica fondativa", "required": True},
                {"id": "relazioni_precontenziose", "label": "Relazioni, perizie o cartelle già disponibili", "required": False},
            ],
            tipologie_di_intervento=[
                {"id": "ricorso_atp", "label": "Ricorso per ATP o istruzione preventiva", "quando": "serve cristallizzare una prova tecnica prima o fuori dal merito"},
                {"id": "istanza_ctu", "label": "Nomina CTU e formulazione quesiti", "quando": "la prova richiede accertamento tecnico"},
                {"id": "fase_conciliativa", "label": "Tentativo conciliativo tecnico", "quando": "la consulenza può favorire definizione o condizione di procedibilità"},
            ],
            legittimati_attivi=[
                {"soggetto": "parte interessata all'accertamento tecnico", "verifica": "interesse concreto e attuale alla prova"},
                {"soggetto": "soggetto che deve assolvere condizione di procedibilità", "verifica": "materia sanitaria o altra materia speciale"},
            ],
            obbligo_mediazione={
                "stato": "da_verificare",
                "fonte": "D.Lgs. 28/2010 e disciplina speciale responsabilità sanitaria quando pertinente",
                "criterio": "ATP, mediazione e negoziazione vanno coordinati con la materia sostanziale",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "accertamento tecnico preventivo o istruzione preventiva",
                "quando": "vi è rischio di alterazione, dispersione della prova o esigenza tecnica non rinviabile",
                "dati_da_verificare": ["quesito", "urgenza probatoria", "documentazione tecnica", "parti interessate"],
            },
            esiti_processuali_tipici=[
                {"esito": "nomina_ctu", "descrizione": "Il giudice ammette l'accertamento e nomina il consulente.", "frequenza": "alta"},
                {"esito": "rigetto_per_mancanza_interesse_o_urgenza", "descrizione": "Rigetto per difetto dei presupposti.", "frequenza": "variabile"},
                {"esito": "conciliazione", "descrizione": "Definizione conciliativa dopo attività tecnica.", "frequenza": "variabile"},
                {"esito": "utilizzo_relazione_nel_merito", "descrizione": "La relazione viene usata nel successivo giudizio di merito.", "frequenza": "variabile"},
            ],
        )
    elif profile == "cautelare":
        config.update(
            profile_label="Procedimento cautelare",
            prima_cosa_da_fare="Verificare fumus, periculum, misura richiesta, competenza cautelare e documenti che dimostrano l'urgenza.",
            focus=[
                "separare fatto, diritto, urgenza e misura richiesta",
                "preparare documenti che rendono leggibile il rischio attuale",
                "presidiare reclamo cautelare e provvedimenti di attuazione",
            ],
            termini=[
                _termine("Reclamo contro provvedimento cautelare", giorni=15, decorrenza="Dalla pronuncia in udienza, comunicazione o notificazione del provvedimento", norma="c.p.c. art. 669-terdecies", natura="termine di reclamo", criticita="Verificare decorrenza concreta e rito speciale eventualmente prevalente."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "fumus", "label": "Fumus boni iuris", "type": "textarea", "required": True},
                {"id": "periculum", "label": "Periculum in mora", "type": "textarea", "required": True},
                {"id": "misura_richiesta", "label": "Misura cautelare richiesta", "type": "textarea", "required": True},
            ],
            allegati_specifici=[
                {"id": "documentazione_urgenza", "label": "Documenti sull'urgenza o sul rischio", "required": True},
            ],
            tipologie_di_intervento=[
                {"id": "ricorso_cautelare", "label": "Ricorso cautelare", "quando": "serve una misura urgente ante causam o in corso di causa"},
                {"id": "istanza_inaudita_altera_parte", "label": "Istanza inaudita altera parte", "quando": "la convocazione può pregiudicare l'efficacia della misura"},
                {"id": "reclamo_cautelare", "label": "Reclamo cautelare", "quando": "si impugna il provvedimento cautelare"},
            ],
            legittimati_attivi=[
                {"soggetto": "parte che invoca tutela urgente", "verifica": "fumus, periculum e interesse concreto"},
                {"soggetto": "parte incisa dal provvedimento", "verifica": "legittimazione al reclamo o alla modifica/revoca"},
            ],
            obbligo_mediazione={
                "stato": "normalmente_non_preventiva",
                "fonte": "D.Lgs. 28/2010 e rito cautelare uniforme",
                "criterio": "l'urgenza cautelare non elimina la verifica della condizione di procedibilità del merito quando dovuta",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "misura cautelare, sospensione, sequestro, ordine di fare/non fare",
                "quando": "fumus e periculum sono documentati",
                "dati_da_verificare": ["fumus", "periculum", "irreparabilità", "misura richiesta", "eventuale inaudita altera parte"],
            },
            esiti_processuali_tipici=[
                {"esito": "accoglimento_misura", "descrizione": "Concessione della misura richiesta, anche con prescrizioni.", "frequenza": "variabile"},
                {"esito": "rigetto_cautelare", "descrizione": "Rigetto per difetto di fumus o periculum.", "frequenza": "variabile"},
                {"esito": "reclamo", "descrizione": "Reclamo al collegio contro ordinanza cautelare.", "frequenza": "media"},
                {"esito": "revoca_o_modifica", "descrizione": "Modifica o revoca della misura per fatti sopravvenuti.", "frequenza": "variabile"},
            ],
        )
    elif profile == "impugnazione":
        config.update(
            profile_label="Impugnazione, reclamo od opposizione",
            prima_cosa_da_fare="Individuare provvedimento impugnato, data di pubblicazione, notifica o comunicazione e mezzo di impugnazione corretto.",
            focus=[
                "acquisire provvedimento integrale e relata/comunicazione",
                "distinguere termine breve, termine lungo e termini speciali",
                "verificare procura, motivi specifici e contributo per l'impugnazione",
            ],
            termini=[
                _termine("Termine breve ordinario per appello o revocazione ordinaria", giorni=30, decorrenza="Dalla notificazione del provvedimento quando il rito lo prevede", norma="c.p.c. artt. 325 e 326", natura="termine di impugnazione", criticita="Non usare per ricorso per cassazione o riti speciali senza verifica."),
                _termine("Termine breve per ricorso per cassazione", giorni=60, decorrenza="Dalla notificazione del provvedimento", norma="c.p.c. art. 325", natura="termine di impugnazione", criticita="Applicare solo se il mezzo corretto è il ricorso per cassazione."),
                _termine("Termine lungo di impugnazione", mesi=6, decorrenza="Dalla pubblicazione del provvedimento", norma="c.p.c. art. 327", natura="termine lungo", criticita="Verificare esclusioni, decorrenze speciali e sospensione feriale."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "provvedimento_impugnato", "label": "Provvedimento impugnato", "type": "document_ref", "required": True},
                {"id": "data_pubblicazione_notifica", "label": "Data pubblicazione/notifica/comunicazione", "type": "date", "required": True},
                {"id": "motivi_impugnazione", "label": "Motivi specifici di impugnazione", "type": "textarea", "required": True},
            ],
            allegati_specifici=[
                {"id": "provvedimento_impugnato", "label": "Provvedimento impugnato integrale", "required": True},
                {"id": "relata_notifica_o_comunicazione", "label": "Relata di notifica o comunicazione PEC", "required": True},
            ],
            tipologie_di_intervento=[
                {"id": "atto_impugnazione", "label": "Atto di impugnazione", "quando": "provvedimento impugnabile e termine pendente"},
                {"id": "istanza_sospensione", "label": "Istanza di sospensione dell'efficacia esecutiva", "quando": "ricorrono gravi motivi o pregiudizio"},
                {"id": "integrazione_motivi", "label": "Integrazione o specificazione motivi", "quando": "ammessa dal rito o richiesta dalla fase"},
            ],
            legittimati_attivi=[
                {"soggetto": "parte soccombente o parzialmente soccombente", "verifica": "interesse a impugnare e soccombenza"},
                {"soggetto": "successore o avente causa", "verifica": "titolo di legittimazione e procura"},
            ],
            obbligo_mediazione={
                "stato": "da_verificare_sul_rapporto_sostanziale",
                "fonte": "D.Lgs. 28/2010 e rito dell'impugnazione",
                "criterio": "l'impugnazione non esclude automaticamente mediazione o negoziazione se previste da norma speciale",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "sospensione efficacia esecutiva o inibitoria",
                "quando": "provvedimento impugnato produce effetti pregiudizievoli prima della decisione",
                "dati_da_verificare": ["provvedimento", "notifica", "pregiudizio", "gravi motivi"],
            },
            esiti_processuali_tipici=[
                {"esito": "accoglimento_impugnazione", "descrizione": "Riforma, revoca o cassazione del provvedimento.", "frequenza": "variabile"},
                {"esito": "rigetto_impugnazione", "descrizione": "Conferma del provvedimento impugnato.", "frequenza": "variabile"},
                {"esito": "inammissibilita_tardivita", "descrizione": "Definizione per tardività o difetto dei requisiti dell'impugnazione.", "frequenza": "da presidiare"},
                {"esito": "sospensione_accolta_o_respinta", "descrizione": "Decisione sull'istanza cautelare o inibitoria.", "frequenza": "variabile"},
            ],
        )
    elif profile == "esecuzione":
        config.update(
            profile_label="Esecuzione forzata",
            prima_cosa_da_fare="Verificare titolo esecutivo, precetto, notifica, parte obbligata, beni/aggressione esecutiva e fase davanti al giudice dell'esecuzione.",
            focus=[
                "controllare titolo, formula esecutiva quando richiesta e precetto",
                "presidiare efficacia del precetto e iscrizione a ruolo secondo il tipo di pignoramento",
                "allineare documenti, ricevute e DatiAtto.xml alla fase esecutiva",
            ],
            termini=[
                _termine("Efficacia del precetto", giorni=90, decorrenza="Dalla notificazione del precetto", norma="c.p.c. art. 481", natura="termine di efficacia", criticita="Usare solo quando il fascicolo contiene precetto notificato."),
                _termine("Intervallo minimo ordinario tra precetto ed esecuzione", giorni=10, decorrenza="Dalla notificazione del precetto", norma="c.p.c. art. 482", natura="termine dilatorio", criticita="Verificare autorizzazione all'esecuzione immediata e casi speciali."),
                _termine("Opposizione agli atti esecutivi", giorni=20, decorrenza="Dalla conoscenza legale dell'atto o dal compimento dell'atto", norma="c.p.c. art. 617", natura="termine di opposizione", criticita="Applicare solo se l'oggetto è opposizione agli atti esecutivi."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "titolo_esecutivo", "label": "Titolo esecutivo", "type": "document_ref", "required": True},
                {"id": "precetto_notificato", "label": "Precetto e data di notifica", "type": "document_ref_date", "required": False},
                {"id": "fase_esecutiva", "label": "Fase esecutiva", "type": "select", "required": True},
            ],
            allegati_specifici=[
                {"id": "titolo_esecutivo", "label": "Titolo esecutivo", "required": True},
                {"id": "precetto", "label": "Atto di precetto e relata", "required": False},
            ],
            tipologie_di_intervento=[
                {"id": "atto_esecutivo", "label": "Atto o istanza nella procedura esecutiva", "quando": "titolo, precetto e fase esecutiva sono individuati"},
                {"id": "opposizione_esecutiva", "label": "Opposizione esecutiva", "quando": "si contesta diritto di procedere, atti o pignorabilità"},
                {"id": "istanza_g_e", "label": "Istanza al giudice dell'esecuzione", "quando": "serve provvedimento sulla gestione della procedura"},
            ],
            legittimati_attivi=[
                {"soggetto": "creditore procedente o intervenuto", "verifica": "titolo esecutivo, precetto e legittimazione"},
                {"soggetto": "debitore esecutato o terzo inciso", "verifica": "interesse all'opposizione o all'istanza"},
            ],
            obbligo_mediazione={
                "stato": "normalmente_non_applicabile_alla_fase_esecutiva",
                "fonte": "c.p.c. libro III e D.Lgs. 28/2010 per eventuale merito collegato",
                "criterio": "verificare solo se l'opposizione introduce controversia di merito soggetta a condizione di procedibilità",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "sospensione dell'esecuzione, riduzione, conversione o provvedimento del G.E.",
                "quando": "il fascicolo contiene titolo, precetto, atto esecutivo e pregiudizio attuale",
                "dati_da_verificare": ["titolo", "precetto", "atto esecutivo", "fase", "pregiudizio"],
            },
            esiti_processuali_tipici=[
                {"esito": "prosecuzione_esecuzione", "descrizione": "La procedura prosegue verso vendita, assegnazione o distribuzione.", "frequenza": "variabile"},
                {"esito": "sospensione", "descrizione": "Sospensione totale o parziale dell'esecuzione.", "frequenza": "variabile"},
                {"esito": "estinzione", "descrizione": "Estinzione per rinuncia, inattività, pagamento o altra causa.", "frequenza": "variabile"},
                {"esito": "accoglimento_o_rigetto_opposizione", "descrizione": "Definizione del subprocedimento oppositivo.", "frequenza": "variabile"},
            ],
        )
    elif profile == "lavoro_previdenza":
        config.update(
            profile_label="Lavoro e previdenza",
            prima_cosa_da_fare="Verificare rapporto, datore/ente, date essenziali, tentativi amministrativi o stragiudiziali e documenti retributivi/previdenziali.",
            focus=[
                "ricostruire cronologia del rapporto e atti impugnati",
                "presidiare decadenze speciali, in particolare licenziamento e prestazioni previdenziali",
                "raccogliere buste paga, comunicazioni, provvedimenti e conteggi",
            ],
            termini=[
                _termine("Impugnazione stragiudiziale del licenziamento", giorni=60, decorrenza="Dalla ricezione della comunicazione di licenziamento", norma="L. 604/1966 art. 6", natura="decadenza sostanziale", criticita="Applicare solo alle controversie di licenziamento e verificare atti equiparati."),
                _termine("Deposito ricorso o richiesta di conciliazione/arbitrato dopo impugnazione", giorni=180, decorrenza="Dalla impugnazione stragiudiziale del licenziamento", norma="L. 604/1966 art. 6", natura="decadenza processuale", criticita="Applicare solo se il fascicolo è licenziamento o atto soggetto alla stessa disciplina."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "datore_o_ente", "label": "Datore di lavoro o ente previdenziale", "type": "object_persona", "required": True},
                {"id": "date_rapporto", "label": "Date rapporto/provvedimento/impugnazione", "type": "date_range", "required": True},
                {"id": "conteggi", "label": "Conteggi retributivi o previdenziali", "type": "document_ref", "required": False},
            ],
            allegati_specifici=[
                {"id": "contratto_buste_paga", "label": "Contratto, buste paga, CU o estratti contributivi", "required": False},
                {"id": "atto_impugnato", "label": "Licenziamento, provvedimento INPS/INAIL o comunicazione contestata", "required": False},
            ],
            tipologie_di_intervento=[
                {"id": "ricorso_lavoro", "label": "Ricorso rito lavoro/previdenza", "quando": "controversia su rapporto, licenziamento, credito, qualifica o prestazione"},
                {"id": "istanza_cautelare_lavoro", "label": "Istanza urgente nel rapporto di lavoro", "quando": "serve tutela immediata su licenziamento, trasferimento, retribuzione o condotta datoriale"},
                {"id": "fase_amministrativa_previdenziale", "label": "Presidio fase amministrativa", "quando": "la prestazione richiede domanda, ricorso o provvedimento amministrativo"},
            ],
            legittimati_attivi=[
                {"soggetto": "lavoratore, datore, ente o assicurato", "verifica": "rapporto, provvedimento e interesse ad agire"},
                {"soggetto": "organizzazione sindacale o soggetto collettivo", "verifica": "legittimazione speciale quando prevista"},
            ],
            obbligo_mediazione={
                "stato": "di_regola_non_mediazione_obbligatoria",
                "fonte": "rito lavoro, conciliazione e procedure speciali applicabili",
                "criterio": "verificare tentativi amministrativi, conciliazioni o decadenze speciali invece della sola mediazione civile",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "cautelare lavoro o tutela d'urgenza",
                "quando": "pregiudizio attuale su lavoro, reddito, salute, mansioni o prestazione",
                "dati_da_verificare": ["rapporto", "atto impugnato", "date", "pregiudizio", "documenti retributivi/previdenziali"],
            },
            esiti_processuali_tipici=[
                {"esito": "accoglimento_domanda", "descrizione": "Accertamento del diritto, condanna o reintegra/indennità quando applicabile.", "frequenza": "variabile"},
                {"esito": "rigetto", "descrizione": "Rigetto per difetto di prova, diritto o presupposti.", "frequenza": "variabile"},
                {"esito": "conciliazione", "descrizione": "Verbale conciliativo giudiziale o stragiudiziale.", "frequenza": "media"},
                {"esito": "decadenza_o_prescrizione", "descrizione": "Definizione per mancato rispetto dei termini speciali.", "frequenza": "da presidiare"},
            ],
        )
    elif profile == "famiglia_minori":
        config.update(
            profile_label="Persone, famiglia e minorenni",
            prima_cosa_da_fare="Verificare parti, minori/interessati, provvedimenti già emessi, urgenze, ascolto, documenti economici e stato delle notifiche.",
            focus=[
                "separare dati del minore, responsabilità genitoriale, mantenimento e urgenze",
                "controllare provvedimenti precedenti e condizioni da modificare",
                "presidiare termini del decreto di fissazione e memorie del rito famiglia",
            ],
            termini=[
                _termine("Termini assegnati nel decreto di fissazione udienza", decorrenza="Dalla comunicazione o notificazione del decreto", norma="c.p.c. artt. 473-bis ss.", natura="termine di rito famiglia", criticita="Nel rito famiglia i termini dipendono dal provvedimento e dalla fase: leggere sempre il decreto."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "minori_o_interessati", "label": "Minori o soggetti interessati", "type": "object_list", "required": False},
                {"id": "provvedimenti_precedenti", "label": "Provvedimenti precedenti", "type": "document_ref", "required": False},
                {"id": "dati_economici_familiari", "label": "Redditi, spese e mantenimento", "type": "textarea", "required": False},
            ],
            allegati_specifici=[
                {"id": "provvedimenti_famiglia", "label": "Provvedimenti precedenti e stato di famiglia/documenti minori", "required": False},
                {"id": "documenti_reddito", "label": "Documenti reddituali e patrimoniali", "required": False},
            ],
            tipologie_di_intervento=[
                {"id": "ricorso_famiglia", "label": "Ricorso in materia di persone, famiglia e minorenni", "quando": "serve regolare status, responsabilità, mantenimento o provvedimenti sui minori"},
                {"id": "provvedimenti_temporanei_urgenti", "label": "Provvedimenti temporanei e urgenti", "quando": "esistono esigenze immediate di tutela personale, economica o genitoriale"},
                {"id": "modifica_condizioni", "label": "Modifica o attuazione di provvedimenti", "quando": "cambiano condizioni o serve esecuzione/attuazione"},
            ],
            legittimati_attivi=[
                {"soggetto": "coniuge, genitore, parte dell'unione o interessato", "verifica": "qualità, rapporto e interesse"},
                {"soggetto": "PM, tutore, curatore o soggetto legittimato dalla norma", "verifica": "legittimazione speciale e documenti"},
            ],
            obbligo_mediazione={
                "stato": "non_mediazione_civile_ordinaria",
                "fonte": "c.p.c. artt. 473-bis ss.; negoziazione assistita familiare quando praticabile",
                "criterio": "valutare negoziazione assistita o percorso consensuale senza trattarla come mediazione obbligatoria ordinaria",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "provvedimenti temporanei, urgenti o indifferibili",
                "quando": "rischio per minori, mantenimento, abitazione, frequentazione, protezione o patrimonio familiare",
                "dati_da_verificare": ["minori", "redditi", "provvedimenti precedenti", "urgenza", "documenti economici"],
            },
            esiti_processuali_tipici=[
                {"esito": "provvedimenti_temporanei", "descrizione": "Adozione di misure temporanee su figli, mantenimento, casa o protezione.", "frequenza": "alta"},
                {"esito": "decisione_merito", "descrizione": "Sentenza o decreto che definisce status, condizioni o misure richieste.", "frequenza": "variabile"},
                {"esito": "accordo_consensuale", "descrizione": "Definizione concordata omologata o recepita dal giudice.", "frequenza": "media"},
                {"esito": "rigetto_o_inammissibilita", "descrizione": "Rigetto o inammissibilità per difetto di presupposti.", "frequenza": "variabile"},
            ],
        )
    elif profile in {"impresa_societario", "crisi_impresa"}:
        is_crisi = profile == "crisi_impresa"
        config.update(
            profile_label="Crisi d'impresa" if is_crisi else "Impresa, societario e proprietà industriale",
            prima_cosa_da_fare="Verificare soggetto, registro imprese, assetto societario, provvedimento/atto da chiedere e competenza della sezione specializzata o concorsuale.",
            focus=[
                "raccogliere visure, statuto, delibere, bilanci e contratti rilevanti",
                "controllare competenza specializzata, valore e rito",
                "presidiare termini speciali del CCII, del codice civile o del codice della proprietà industriale",
            ],
            termini=[
                _termine("Termini societari, concorsuali o di proprietà industriale collegati all'atto", decorrenza="Dalla delibera, pubblicazione, comunicazione, provvedimento o evento previsto dalla norma speciale", norma="c.c., c.p.c., c.p.i. o CCII secondo materia", natura="termine speciale", criticita="Materia ad alto rischio: calcolo automatico solo dopo individuazione della norma speciale applicabile."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "soggetto_impresa", "label": "Società/impresa o procedura", "type": "object_company", "required": True},
                {"id": "visura_o_procedura", "label": "Visura, statuto, procedura o provvedimento", "type": "document_ref", "required": True},
            ],
            allegati_specifici=[
                {"id": "visura_bilanci_statuto", "label": "Visura, statuto, bilanci o atti societari", "required": False},
                {"id": "provvedimento_o_domanda_concorsuale", "label": "Provvedimento/domanda/procedura concorsuale", "required": False},
            ],
            tipologie_di_intervento=[
                {"id": "domanda_societaria_o_impresa", "label": "Domanda societaria, industriale o concorsuale", "quando": "la controversia riguarda impresa, società, crisi o proprietà industriale"},
                {"id": "misura_protettiva_o_cautelare", "label": "Misura protettiva, cautelare o urgente", "quando": "serve preservare beni, prova, continuità o segreti"},
                {"id": "istanza_procedura", "label": "Istanza nella procedura o al giudice delegato", "quando": "la fase è concorsuale o camerale"},
            ],
            legittimati_attivi=[
                {"soggetto": "società, socio, amministratore, creditore, titolare IP o procedura", "verifica": "titolo, poteri, visura e interesse"},
                {"soggetto": "organo della procedura o terzo interessato", "verifica": "legittimazione prevista dal CCII o dalla norma speciale"},
            ],
            obbligo_mediazione={
                "stato": "da_verificare_su_materia_sostanziale",
                "fonte": "D.Lgs. 28/2010, c.c., c.p.i., CCII e norme speciali",
                "criterio": "societario, bancario, finanziario o diritti reali possono richiedere ADR o procedura speciale",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "misura cautelare, protettiva, inibitoria, sequestro o autorizzazione urgente",
                "quando": "rischio su patrimonio, continuità, segreti, marchi, quote o procedura",
                "dati_da_verificare": ["visure", "statuto", "bilanci", "delibere", "provvedimenti", "pericolo"],
            },
            esiti_processuali_tipici=[
                {"esito": "accoglimento_domanda_o_misura", "descrizione": "Accoglimento di domanda, misura, autorizzazione o tutela richiesta.", "frequenza": "variabile"},
                {"esito": "rigetto", "descrizione": "Rigetto per difetto di presupposti, prova o competenza.", "frequenza": "variabile"},
                {"esito": "apertura_o_prosecuzione_procedura", "descrizione": "Apertura, prosecuzione o gestione di procedura concorsuale/societaria.", "frequenza": "variabile"},
                {"esito": "accordo_o_piano", "descrizione": "Definizione tramite accordo, piano, omologa o soluzione negoziata.", "frequenza": "variabile"},
            ],
        )
    elif profile == "volontaria_giurisdizione":
        config.update(
            profile_label="Volontaria giurisdizione",
            prima_cosa_da_fare="Verificare soggetto interessato, legittimazione, urgenza, documenti da autorizzare e provvedimento richiesto al giudice.",
            focus=[
                "identificare soggetto protetto o ente interessato",
                "controllare documenti giustificativi e autorizzazione richiesta",
                "presidiare reclamo camerale quando previsto",
            ],
            termini=[
                _termine("Reclamo contro decreto camerale", giorni=10, decorrenza="Dalla comunicazione o notificazione del decreto", norma="c.p.c. art. 739", natura="termine di reclamo", criticita="Applicare solo quando il provvedimento è reclamabile e non opera disciplina speciale."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "soggetto_interessato", "label": "Soggetto interessato/beneficiario", "type": "object_persona", "required": True},
                {"id": "autorizzazione_richiesta", "label": "Autorizzazione o provvedimento richiesto", "type": "textarea", "required": True},
            ],
            tipologie_di_intervento=[
                {"id": "ricorso_camerale", "label": "Ricorso camerale o istanza di autorizzazione", "quando": "serve un provvedimento del giudice tutelare o del tribunale"},
                {"id": "reclamo_camerale", "label": "Reclamo camerale", "quando": "il decreto è reclamabile"},
                {"id": "integrazione_documentale", "label": "Integrazione documentale", "quando": "la cancelleria o il giudice richiedono chiarimenti"},
            ],
            legittimati_attivi=[
                {"soggetto": "interessato, familiare, tutore, curatore, amministratore o ente", "verifica": "legittimazione prevista dalla specifica istanza"},
                {"soggetto": "PM o soggetto pubblico", "verifica": "intervento o iniziativa prevista dalla legge"},
            ],
            obbligo_mediazione={
                "stato": "normalmente_non_applicabile",
                "fonte": "c.p.c. artt. 737 ss. e norme speciali",
                "criterio": "verificare eventuale norma speciale, ma la volontaria giurisdizione non segue la mediazione ordinaria come regola generale",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "autorizzazione o misura urgente camerale",
                "quando": "serve tutela immediata del soggetto o del patrimonio",
                "dati_da_verificare": ["soggetto interessato", "urgenza", "documenti", "provvedimento richiesto"],
            },
            esiti_processuali_tipici=[
                {"esito": "decreto_accoglimento", "descrizione": "Emissione del decreto richiesto.", "frequenza": "alta"},
                {"esito": "richiesta_integrazione", "descrizione": "Richiesta di documenti o chiarimenti.", "frequenza": "media"},
                {"esito": "rigetto", "descrizione": "Rigetto per difetto dei presupposti.", "frequenza": "variabile"},
                {"esito": "reclamo", "descrizione": "Reclamo contro decreto quando previsto.", "frequenza": "variabile"},
            ],
        )
    elif profile == "immigrazione_cittadinanza":
        config.update(
            profile_label="Immigrazione, protezione internazionale o cittadinanza",
            prima_cosa_da_fare="Verificare provvedimento amministrativo, data di comunicazione, autorità, status richiesto e documenti identitari/tradotti.",
            focus=[
                "acquisire provvedimento, ricevute e data certa di comunicazione",
                "controllare rito speciale e giudice competente",
                "verificare traduzioni, documenti consolari e procura",
            ],
            termini=[
                _termine("Termine di ricorso o opposizione nel rito speciale", decorrenza="Dalla comunicazione, notificazione o conoscenza legale del provvedimento", norma="normativa speciale immigrazione/cittadinanza e c.p.c.", natura="termine speciale", criticita="Il termine varia per materia e provvedimento: non calcolare senza identificare la norma speciale."),
                *common_terms,
            ],
            campi_specifici=[
                {"id": "provvedimento_amministrativo", "label": "Provvedimento amministrativo impugnato", "type": "document_ref", "required": True},
                {"id": "data_comunicazione", "label": "Data comunicazione/notifica", "type": "date", "required": True},
            ],
            tipologie_di_intervento=[
                {"id": "ricorso_contro_provvedimento", "label": "Ricorso contro provvedimento amministrativo", "quando": "provvedimento comunicato o notificato e termine da presidiare"},
                {"id": "istanza_sospensione", "label": "Istanza cautelare/sospensiva", "quando": "il provvedimento produce effetti immediati pregiudizievoli"},
                {"id": "integrazione_documentale", "label": "Integrazione documentale e traduzioni", "quando": "mancano documenti identitari, consolari o tradotti"},
            ],
            legittimati_attivi=[
                {"soggetto": "straniero, richiedente protezione, cittadino o familiare interessato", "verifica": "status, procura, identità e provvedimento"},
                {"soggetto": "tutore, rappresentante o ente legittimato", "verifica": "poteri e documenti"},
            ],
            obbligo_mediazione={
                "stato": "non_applicabile_salvo_norma_speciale",
                "fonte": "normativa speciale immigrazione/cittadinanza",
                "criterio": "la priorità è il termine speciale di ricorso e la documentazione del provvedimento",
            },
            richiesta_provvedimenti_urgenti={
                "ammissibile": True,
                "tipo": "sospensione o misura cautelare",
                "quando": "il provvedimento incide immediatamente su soggiorno, espulsione, status o diritti essenziali",
                "dati_da_verificare": ["provvedimento", "data comunicazione", "pregiudizio", "documenti identità"],
            },
            esiti_processuali_tipici=[
                {"esito": "accoglimento_ricorso", "descrizione": "Annullamento o riforma del provvedimento, riconoscimento dello status o del diritto.", "frequenza": "variabile"},
                {"esito": "rigetto", "descrizione": "Conferma del provvedimento o rigetto della domanda.", "frequenza": "variabile"},
                {"esito": "sospensione", "descrizione": "Accoglimento o rigetto dell'istanza cautelare.", "frequenza": "variabile"},
                {"esito": "integrazione_istruttoria", "descrizione": "Richiesta di documenti, traduzioni o chiarimenti.", "frequenza": "media"},
            ],
        )

    article_refs = _article_sources(label)
    normativa_curata = [
        {
            "fonte": "c.p.c.",
            "articolo": "155",
            "descrizione": "Computo dei termini processuali, proroghe e regole di calendario.",
            "source_registry_key": "normattiva_cpc",
        },
        {
            "fonte": "L. 742/1969",
            "articolo": "1 ss.",
            "descrizione": "Sospensione feriale dei termini processuali, salvo esclusioni o regimi speciali.",
            "source_registry_key": "normattiva_l742_1969",
        },
        *article_refs,
    ]
    return {
        **config,
        "fonti_ufficiali": sources,
        "normativa_curata": _unique_dicts(normativa_curata),
    }


def _merge_normativa(item: dict[str, Any], curated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = item.get("normativa")
    if isinstance(existing, dict):
        primari = existing.get("riferimenti_primari") if isinstance(existing.get("riferimenti_primari"), list) else []
        secondari = existing.get("riferimenti_secondari") if isinstance(existing.get("riferimenti_secondari"), list) else []
        existing_list = [*primari, *secondari]
    elif isinstance(existing, list):
        existing_list = existing
    else:
        existing_list = []
    return _unique_dicts([*(x for x in existing_list if isinstance(x, dict)), *curated])


def curate_item(item: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(item)
    profile = infer_profile(out)
    profile_data = profile_payload(profile, out)
    code = _text(out.get("codice"))
    label = _text(out.get("denominazione"))

    out["normativa"] = _merge_normativa(out, profile_data["normativa_curata"])
    out["presupposti_sostanziali"] = _unique_dicts([
        {"testo": text, "profilo": profile, "curato_da": "codex"} for text in profile_data["presupposti"]
    ])
    out["adempimenti_propedeutici"] = [
        {"step": index, "azione": action, "obbligatorio": True, "profilo": profile}
        for index, action in enumerate(profile_data["adempimenti"], 1)
    ]
    out["termini_processuali"] = profile_data["termini"]
    out["tipologie_di_intervento"] = deepcopy(profile_data["tipologie_di_intervento"])
    out["legittimati_attivi"] = deepcopy(profile_data["legittimati_attivi"])
    out["obbligo_mediazione"] = deepcopy(profile_data["obbligo_mediazione"])
    out["richiesta_provvedimenti_urgenti"] = deepcopy(profile_data["richiesta_provvedimenti_urgenti"])
    out["avvertimenti_obbligatori"] = _unique_list([
        *profile_data["avvertimenti_obbligatori"],
        *(_as_list(out.get("avvertimenti_obbligatori"))),
    ])
    out["esiti_processuali_tipici"] = deepcopy(profile_data["esiti_processuali_tipici"])
    out["avvertenze_redazionali"] = _unique_list([*profile_data["avvertenze"], *(_as_list(out.get("avvertenze_redazionali")))])
    out["allegati_obbligatori"] = _merge_allegati(_as_list(out.get("allegati_obbligatori")), profile_data["allegati_specifici"])

    atto = out.setdefault("atto_principale", {})
    if isinstance(atto, dict):
        atto.setdefault("denominazione", label)
        atto["campi_obbligatori"] = _merge_fields(_as_list(atto.get("campi_obbligatori")), profile_data["campi_specifici"])
        atto["avvertimenti_obbligatori"] = _unique_list([
            "Usa i dati già acquisiti nel fascicolo; non duplicare cliente, parti, ufficio, valore, preventivo, incarico o parcella.",
            "Prima del deposito conferma codice oggetto PST/XSD, registro, rito, atto principale e allegati.",
            *(_as_list(atto.get("avvertimenti_obbligatori"))),
        ])

    out["ricerca_curata_codex"] = {
        "stato": "curata_con_fonti_ufficiali",
        "data": CURATION_DATE,
        "curation_source": CURATION_SOURCE,
        "profilo": profile,
        "profilo_label": profile_data["profile_label"],
        "codice": code,
        "denominazione": label,
        "metodo": [
            "aggancio al catalogo PST/XSD locale verificato",
            "classificazione per rito, materia, sottocategoria e parole chiave del codice oggetto",
            "controllo su fonti ufficiali Normattiva e Portale Servizi Telematici",
            "estrazione dei riferimenti normativi espressi nella denominazione",
            "separazione fra termine calcolabile e presidio da revisione professionale",
        ],
        "fonti_ufficiali": profile_data["fonti_ufficiali"],
        "risultato": "scheda trasformata da completamento automatico a guida pratica curata Codex, con termini processuali presidiati e contesto Lex",
        "limite_professionale": "Le scadenze numeriche si attivano solo con evento generatore confermato dall'avvocato; i termini speciali restano in revisione professionale.",
    }
    out["guida_operativa_curata"] = {
        "livello": "curata_codex",
        "non_bloccante": True,
        "prima_cosa_da_fare": profile_data["prima_cosa_da_fare"],
        "focus_operativo": profile_data["focus"],
        "contesto_fascicolo_da_leggere": [
            "cliente",
            "parti",
            "ufficio",
            "oggetto pratica",
            "codice oggetto PST/XSD",
            "valore",
            "rito",
            "fase",
            "documenti",
            "scadenze",
            "note",
            "preventivo",
            "conferimento incarico",
            "procura",
            "privacy",
            "antiriciclaggio",
            "conflitto di interessi",
            "parcella collegata",
        ],
        "campi_da_non_duplicare": [
            "cliente",
            "controparte",
            "ufficio",
            "valore causa",
            "dati studio",
            "preventivo",
            "conferimento incarico",
            "parcella",
        ],
        "fasi_assistite": [
            {"fase": "apertura_fascicolo", "azione": "leggere dati sorgente e suggerire la scheda senza bloccare"},
            {"fase": "preistruttoria", "azione": "evidenziare documenti, condizioni di procedibilità e termini"},
            {"fase": "redazione_atto", "azione": "passare al catalogo template e compilatore con dati fascicolo in sola lettura"},
            {"fase": "deposito", "azione": "controllare coerenza codice oggetto, busta, DatiAtto.xml, firma e ricevute"},
            {"fase": "post_deposito", "azione": "presidiare ricevute, scadenze, provvedimenti e prossimi passi"},
        ],
        "lex_context": (
            f"Quando l'avvocato chiede aiuto su {label}, Lex deve partire dal fascicolo, spiegare il profilo "
            f"{profile_data['profile_label']} in modo pratico, distinguere dati certi e dati da verificare, "
            "e proporre i prossimi passi senza bloccare il lavoro."
        ),
    }
    out["_quality_hint"] = "curata_codex_fonti_ufficiali"
    out["_curation_source"] = CURATION_SOURCE
    return out


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _unique_list(items: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for item in items:
        text = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else _text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(item)
    return out


def _merge_fields(existing: list[Any], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in existing:
        if isinstance(item, dict):
            by_id[_text(item.get("id")) or json.dumps(item, ensure_ascii=False, sort_keys=True)] = item
    for item in extra:
        by_id[_text(item.get("id")) or json.dumps(item, ensure_ascii=False, sort_keys=True)] = item
    return list(by_id.values())


def _merge_allegati(existing: list[Any], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in existing:
        if isinstance(item, dict):
            by_id[_text(item.get("id")) or _text(item.get("label"))] = item
    for item in extra:
        by_id[_text(item.get("id")) or _text(item.get("label"))] = item
    return list(by_id.values())


def curate_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    out = deepcopy(payload)
    rows: list[dict[str, Any]] = []
    profile_counter: Counter[str] = Counter()
    term_counter: Counter[str] = Counter()
    curated_items: list[dict[str, Any]] = []
    for item in out.get("codici_materia", []):
        if not isinstance(item, dict):
            curated_items.append(item)
            continue
        curated = curate_item(item)
        curated_items.append(curated)
        profile = curated["ricerca_curata_codex"]["profilo"]
        profile_counter[profile] += 1
        term_count = len(_as_list(curated.get("termini_processuali")))
        term_counter[profile] += term_count
        rows.append(
            {
                "codice": _text(curated.get("codice")),
                "denominazione": _text(curated.get("denominazione")),
                "profilo": profile,
                "profilo_label": curated["ricerca_curata_codex"]["profilo_label"],
                "termini_processuali": term_count,
                "fonti_ufficiali": len(_as_list(curated["ricerca_curata_codex"].get("fonti_ufficiali"))),
                "quality_hint": _text(curated.get("_quality_hint")),
            }
        )
    out["codici_materia"] = curated_items
    out["curation_codex"] = {
        "stato": "curata_con_fonti_ufficiali",
        "data": CURATION_DATE,
        "generated_at": _utc_now(),
        "curation_source": CURATION_SOURCE,
        "records_curati": len(rows),
        "fonti_ufficiali": list(OFFICIAL_SOURCES.values()),
        "by_profile": dict(profile_counter.most_common()),
        "terms_by_profile": dict(term_counter.most_common()),
    }
    report = {
        "ok": True,
        "generated_at": out["curation_codex"]["generated_at"],
        "target": str(DEFAULT_TARGET),
        "records_curati": len(rows),
        "by_profile": dict(profile_counter.most_common()),
        "terms_by_profile": dict(term_counter.most_common()),
        "official_sources": OFFICIAL_SOURCES,
    }
    return out, report, rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "codice",
                "denominazione",
                "profilo",
                "profilo_label",
                "termini_processuali",
                "fonti_ufficiali",
                "quality_hint",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cura il completamento automatico Codex della Guida Pratica con fonti ufficiali.")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    payload = json.loads(args.target.read_text(encoding="utf-8-sig"))
    curated, report, rows = curate_payload(payload)
    report["target"] = str(args.target)
    report["dry_run"] = bool(args.dry_run)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(rows, args.csv)
    if not args.dry_run:
        args.target.write_text(json.dumps(curated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
