#!/usr/bin/env python3
"""Completa la Guida Pratica per i codici PST/XSD ufficiali non ancora curati.

Il comando crea un modulo KB separato, senza modificare il catalogo ministeriale.
Le schede usano lo stesso formato dei moduli Guida Pratica: codice, atto,
campi, allegati, adempimenti, avvertenze e fonte XSD.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica import GuidaPraticaService  # noqa: E402
from pct.guida_pratica.service import normalize_codice_materia  # noqa: E402
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry  # noqa: E402

DATA_DIR = ROOT / "pct" / "data"
MODULES_DIR = DATA_DIR / "legal_knowledge_base_modules"
FULL_KB = DATA_DIR / "legal_knowledge_base.full.json"
DEFAULT_OUTPUT = MODULES_DIR / "kb_99_completamento_codici_ufficiali.json"


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text if text else default


def _words(*values: Any) -> str:
    return " ".join(_text(value).casefold() for value in values if _text(value))


def _contains(haystack: str, *needles: str) -> bool:
    return any(needle in haystack for needle in needles)


def _clean_label(value: str) -> str:
    replacements = {
        "responsabilita'": "responsabilità",
        "paternita'": "paternità",
        "maternita'": "maternità",
        "capacita'": "capacità",
        "attivita'": "attività",
        "proprieta'": "proprietà",
        "eredita'": "eredità",
        "eta'": "età",
        "liberta'": "libertà",
        "invalidita'": "invalidità",
        "indennita'": "indennità",
        "contrarietà": "contrarietà",
    }
    out = value
    for old, new in replacements.items():
        out = re.sub(re.escape(old), new, out, flags=re.IGNORECASE)
    return out


def _load_existing_codes(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    codes: set[str] = set()
    for item in payload.get("codici_materia") if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        codice = normalize_codice_materia(item.get("codice") or item.get("codice_logico"))
        if codice:
            codes.add(codice)
    return codes


def _normative_base() -> list[dict[str, str]]:
    return [
        {"fonte": "c.p.c.", "articolo": "125", "descrizione": "Contenuto degli atti di parte"},
        {"fonte": "D.P.R. 115/2002", "articolo": "9 ss.", "descrizione": "Contributo unificato e spese di giustizia"},
        {"fonte": "D.M. 44/2011", "articolo": "12-14", "descrizione": "Deposito telematico e busta informatica"},
    ]


def _base_fields() -> list[dict[str, Any]]:
    return [
        {"id": "ufficio_giudiziario", "label": "Ufficio giudiziario competente", "type": "select_ufficio", "required": True},
        {"id": "registro_e_rito", "label": "Registro e rito applicabile", "type": "string", "required": True},
        {"id": "parte_assistita", "label": "Parte assistita", "type": "object_persona", "required": True},
        {"id": "controparte_o_soggetto_interessato", "label": "Controparte o soggetto interessato", "type": "object_persona", "required": True},
        {"id": "difensore", "label": "Difensore e domicilio digitale", "type": "object_avvocato", "required": True},
        {"id": "oggetto_domanda", "label": "Oggetto della domanda o dell'istanza", "type": "textarea", "required": True},
        {"id": "valore_o_esenzione", "label": "Valore, esenzione o contributo unificato", "type": "currency_or_exemption", "required": True},
    ]


def _base_structure() -> list[dict[str, str]]:
    return [
        {"sezione": "Intestazione", "contenuto": "Ufficio, registro, codice oggetto e parti"},
        {"sezione": "Premesse", "contenuto": "Fatti, titolo della domanda e documenti richiamati"},
        {"sezione": "Diritto", "contenuto": "Norme e presupposti del procedimento"},
        {"sezione": "Domande", "contenuto": "Richieste al giudice o alla cancelleria"},
        {"sezione": "Valore e spese", "contenuto": "Valore della causa, contributo ed eventuali esenzioni"},
        {"sezione": "Allegati", "contenuto": "Elenco numerato dei documenti depositati"},
    ]


def _profile(label: str, parent: str, area: str, codice: str) -> dict[str, Any]:
    hay = _words(label, parent, area, codice)
    profile = {
        "tipo_atto": "atto_introduttivo_o_istanza_telematica",
        "rito": "Rito da verificare sul codice oggetto e sul registro di destinazione",
        "normativa": _normative_base(),
        "presupposti": [
            "Verificare che il codice oggetto selezionato corrisponda al petitum effettivo e al registro dell'ufficio.",
            "Controllare competenza, rito, legittimazione delle parti e condizioni di procedibilità prima del deposito.",
            "Confrontare l'atto principale con il fascicolo, gli allegati e la ricevuta di deposito attesa.",
        ],
        "campi": _base_fields(),
        "allegati": [
            {"id": "procura_alle_liti", "label": "Procura alle liti o titolo di rappresentanza", "required": True},
            {"id": "documenti_fondativi", "label": "Documenti fondativi della domanda o dell'istanza", "required": True},
            {"id": "ricevuta_contributo_unificato", "label": "Ricevuta contributo unificato o indicazione di esenzione", "required": False},
        ],
        "adempimenti": [
            {"step": 1, "azione": "Verificare codice oggetto PST/XSD, registro e ufficio destinatario", "obbligatorio": True},
            {"step": 2, "azione": "Controllare procura, parti, valore e documenti fondativi", "obbligatorio": True},
            {"step": 3, "azione": "Preparare atto principale e allegati in formato ammesso dal deposito", "obbligatorio": True},
            {"step": 4, "azione": "Eseguire controllo busta, firma digitale e coerenza DatiAtto.xml prima dell'invio", "obbligatorio": True},
        ],
        "avvertimenti": [
            "Non usare il codice oggetto se il petitum o il registro del fascicolo non coincidono con la descrizione PST/XSD.",
            "Verificare sempre eventuali prassi dell'ufficio e aggiornamenti ministeriali prima del deposito.",
        ],
        "termini": [
            {"termine": "Termini processuali del procedimento", "durata_giorni": None, "decorrenza": "Da verificare secondo rito, provvedimento o notifica", "tipo": "variabile"},
        ],
    }
    if _contains(hay, "ingiunz", "decreto ingiuntivo"):
        profile.update(
            {
                "tipo_atto": "ricorso_decreto_ingiuntivo",
                "rito": "Procedimento monitorio ex artt. 633-656 c.p.c.",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "c.p.c.", "articolo": "633-656", "descrizione": "Procedimento di ingiunzione"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "credito_importo", "label": "Importo del credito", "type": "currency", "required": True},
                    {"id": "titolo_credito", "label": "Titolo e prova scritta del credito", "type": "textarea", "required": True},
                    {"id": "provvisoria_esecuzione", "label": "Richiesta di provvisoria esecuzione", "type": "boolean", "required": False},
                ],
                "allegati": [
                    {"id": "procura_alle_liti", "label": "Procura alle liti", "required": True},
                    {"id": "prova_scritta_credito", "label": "Prova scritta del credito", "required": True},
                    {"id": "conteggio_credito", "label": "Conteggio capitale, interessi e spese", "required": True},
                    {"id": "diffida_o_messa_in_mora", "label": "Diffida o messa in mora se disponibile", "required": False},
                ],
            }
        )
    elif _contains(hay, "cautelar", "sequestro", "urgenza", "inibitoria", "istruzione preventiva", "accertamento tecnico", "696"):
        profile.update(
            {
                "tipo_atto": "ricorso_cautelare_o_istruzione_preventiva",
                "rito": "Procedimento cautelare o istruzione preventiva",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "c.p.c.", "articolo": "669-bis ss.", "descrizione": "Procedimento cautelare uniforme"},
                    {"fonte": "c.p.c.", "articolo": "692-699", "descrizione": "Istruzione preventiva quando applicabile"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "fumus", "label": "Fumus boni iuris", "type": "textarea", "required": True},
                    {"id": "periculum", "label": "Periculum in mora o urgenza", "type": "textarea", "required": True},
                    {"id": "misura_richiesta", "label": "Misura richiesta", "type": "textarea", "required": True},
                ],
                "allegati": [
                    {"id": "procura_alle_liti", "label": "Procura alle liti", "required": True},
                    {"id": "documenti_fondativi", "label": "Documenti sul diritto fatto valere", "required": True},
                    {"id": "documentazione_urgenza", "label": "Documentazione su urgenza o rischio", "required": True},
                ],
            }
        )
    elif _contains(hay, "famiglia", "minore", "minori", "separazione", "divorzio", "responsabilità genitoriale", "paternità", "maternità", "matrimonio", "adozione"):
        profile.update(
            {
                "tipo_atto": "ricorso_famiglia_minori",
                "rito": "Procedimenti in materia di persone, minorenni e famiglie",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "c.p.c.", "articolo": "473-bis ss.", "descrizione": "Procedimenti in materia di persone, minorenni e famiglie"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "nucleo_familiare", "label": "Nucleo familiare e figli", "type": "textarea", "required": True},
                    {"id": "provvedimenti_richiesti", "label": "Provvedimenti richiesti", "type": "textarea", "required": True},
                    {"id": "situazione_economica", "label": "Situazione economica e patrimoniale", "type": "textarea", "required": False},
                ],
                "allegati": [
                    {"id": "procura_alle_liti", "label": "Procura alle liti", "required": True},
                    {"id": "certificati_anagrafici", "label": "Certificati anagrafici o stato di famiglia se richiesti", "required": True},
                    {"id": "documentazione_economica", "label": "Documentazione reddituale e patrimoniale", "required": False},
                    {"id": "provvedimenti_precedenti", "label": "Provvedimenti precedenti o accordi", "required": False},
                ],
            }
        )
    elif _contains(hay, "lavor", "previd", "inps", "inail", "licenziamento", "retribut"):
        profile.update(
            {
                "tipo_atto": "ricorso_lavoro_previdenza",
                "rito": "Rito del lavoro",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "c.p.c.", "articolo": "409-441", "descrizione": "Controversie individuali di lavoro e previdenza"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "rapporto_lavoro_o_prestazione", "label": "Rapporto di lavoro o prestazione previdenziale", "type": "textarea", "required": True},
                    {"id": "periodo_rilevante", "label": "Periodo rilevante", "type": "string", "required": True},
                    {"id": "conteggi", "label": "Conteggi e differenze richieste", "type": "table", "required": False},
                ],
                "allegati": [
                    {"id": "procura_alle_liti", "label": "Procura alle liti", "required": True},
                    {"id": "documenti_lavoro", "label": "Contratto, buste paga, comunicazioni o provvedimenti", "required": True},
                    {"id": "conteggi", "label": "Conteggi analitici", "required": False},
                ],
            }
        )
    elif _contains(hay, "esecuz", "pignor", "rilascio", "obblighi di fare", "precetto", "vendita", "distribuzione"):
        profile.update(
            {
                "tipo_atto": "atto_esecutivo",
                "rito": "Esecuzione forzata",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "c.p.c.", "articolo": "474 ss.", "descrizione": "Titolo esecutivo, precetto ed esecuzione"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "titolo_esecutivo", "label": "Titolo esecutivo", "type": "string", "required": True},
                    {"id": "precetto", "label": "Precetto e notifica", "type": "string", "required": False},
                    {"id": "beni_o_obbligo", "label": "Beni, credito o obbligo oggetto di esecuzione", "type": "textarea", "required": True},
                ],
                "allegati": [
                    {"id": "procura_alle_liti", "label": "Procura alle liti", "required": True},
                    {"id": "titolo_esecutivo", "label": "Titolo esecutivo", "required": True},
                    {"id": "precetto_notifica", "label": "Precetto e prova di notifica se richiesti", "required": False},
                ],
            }
        )
    elif _contains(hay, "volontaria", "tutela", "curatela", "interdizione", "inabilitazione", "amministrazione di sostegno", "giudice tutelare"):
        profile.update(
            {
                "tipo_atto": "ricorso_volontaria_giurisdizione",
                "rito": "Volontaria giurisdizione",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "c.c.", "articolo": "404 ss. / 414 ss.", "descrizione": "Misure di protezione, quando applicabili"},
                    {"fonte": "c.p.c.", "articolo": "737 ss.", "descrizione": "Procedimenti in camera di consiglio"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "beneficiario_o_interessato", "label": "Beneficiario o soggetto interessato", "type": "object_persona", "required": True},
                    {"id": "misura_richiesta", "label": "Misura o autorizzazione richiesta", "type": "textarea", "required": True},
                    {"id": "documentazione_sanitaria_o_familiare", "label": "Documentazione sanitaria, familiare o patrimoniale", "type": "file_multi", "required": False},
                ],
            }
        )
    elif _contains(hay, "succession", "eredit", "testament", "divisione"):
        profile.update(
            {
                "tipo_atto": "ricorso_successioni",
                "rito": "Procedimento successorio o divisionale",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "c.c.", "articolo": "456 ss.", "descrizione": "Successioni"},
                    {"fonte": "c.c.", "articolo": "713 ss.", "descrizione": "Divisione quando applicabile"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "de_cuius", "label": "De cuius", "type": "object_persona", "required": True},
                    {"id": "eredi_o_chiamati", "label": "Eredi, chiamati o interessati", "type": "textarea", "required": True},
                    {"id": "beni_ereditari", "label": "Beni o quota controversa", "type": "textarea", "required": True},
                ],
            }
        )
    elif _contains(hay, "societ", "impresa", "falliment", "liquidazione", "crisi", "insolvenza"):
        profile.update(
            {
                "tipo_atto": "ricorso_societario_o_crisi",
                "rito": "Procedimento societario, impresa o crisi d'impresa",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "D.Lgs. 14/2019", "articolo": "40 ss.", "descrizione": "Procedimento unitario e strumenti di regolazione della crisi quando applicabili"},
                    {"fonte": "c.c.", "articolo": "2380 ss. / 2475 ss.", "descrizione": "Società di capitali quando applicabile"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "societa_o_impresa", "label": "Società, impresa o procedura", "type": "object_persona", "required": True},
                    {"id": "organo_o_procedura", "label": "Organo, procedura o provvedimento richiesto", "type": "textarea", "required": True},
                    {"id": "documenti_contabili", "label": "Documenti contabili o societari rilevanti", "type": "file_multi", "required": False},
                ],
            }
        )
    elif _contains(hay, "immigrazione", "protezione internazionale", "cittadinanza", "permesso", "trattenimento", "stranier"):
        profile.update(
            {
                "tipo_atto": "ricorso_immigrazione_protezione",
                "rito": "Procedimento immigrazione, protezione internazionale o cittadinanza",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "D.Lgs. 25/2008", "articolo": "35-bis", "descrizione": "Impugnazione decisioni protezione internazionale quando applicabile"},
                    {"fonte": "D.Lgs. 286/1998", "articolo": "13-14", "descrizione": "Espulsione e trattenimento quando applicabili"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "provvedimento_impugnato", "label": "Provvedimento impugnato", "type": "file_multi", "required": True},
                    {"id": "status_richiesto", "label": "Status, permesso o tutela richiesta", "type": "textarea", "required": True},
                    {"id": "situazione_personale", "label": "Situazione personale e vulnerabilità", "type": "textarea", "required": False},
                ],
            }
        )
    elif _contains(hay, "reclamo", "appello", "revocazione", "impugnazione", "opposizione"):
        profile.update(
            {
                "tipo_atto": "atto_impugnazione_o_opposizione",
                "rito": "Impugnazione, reclamo od opposizione",
                "normativa": [
                    *_normative_base(),
                    {"fonte": "c.p.c.", "articolo": "323 ss.", "descrizione": "Impugnazioni"},
                    {"fonte": "c.p.c.", "articolo": "395 ss.", "descrizione": "Revocazione quando applicabile"},
                ],
                "campi": [
                    *_base_fields(),
                    {"id": "provvedimento_impugnato", "label": "Provvedimento o atto impugnato", "type": "file_multi", "required": True},
                    {"id": "motivi_impugnazione", "label": "Motivi di impugnazione o opposizione", "type": "textarea", "required": True},
                    {"id": "termine_impugnazione", "label": "Termine e decorrenza", "type": "string", "required": True},
                ],
                "allegati": [
                    {"id": "procura_alle_liti", "label": "Procura alle liti", "required": True},
                    {"id": "provvedimento_impugnato", "label": "Provvedimento o atto impugnato", "required": True},
                    {"id": "prova_notifica_comunicazione", "label": "Prova di notifica o comunicazione", "required": False},
                ],
            }
        )
    return profile


def _entry(row: dict[str, Any], *, depositabile: bool) -> dict[str, Any]:
    codice = normalize_codice_materia(row.get("codice"))
    label = _clean_label(_text(row.get("descrizione") or row.get("denominazione"), f"Codice materia {codice}"))
    parent_label = _clean_label(_text(row.get("parent_label")))
    area = _clean_label(_text(row.get("area_label") or row.get("area") or "Catalogo PST ufficiale"))
    profile = _profile(label, parent_label, area, codice)
    registri = [_text(item) for item in _text(row.get("registri")).split(",") if _text(item)]
    return {
        "codice": codice,
        "denominazione": label,
        "denominazione_ufficiale_pst": _text(row.get("descrizione")),
        "categoria": area,
        "sottocategoria": parent_label,
        "rito": profile["rito"],
        "competenza": "Da verificare in base a ufficio, valore, materia, foro speciale e fase processuale.",
        "uffici_destinatari": registri or ["SICID"],
        "catalogo_pst_xsd": {
            "codice": codice,
            "parent_codice": _text(row.get("parent_codice")),
            "parent_label": parent_label,
            "file_fonte": _text(row.get("file_fonte")),
            "depositabile": depositabile,
        },
        "normativa": profile["normativa"],
        "presupposti_sostanziali": profile["presupposti"],
        "adempimenti_propedeutici": profile["adempimenti"],
        "atto_principale": {
            "tipo_atto": profile["tipo_atto"],
            "denominazione": label,
            "schema_xsd_ministeriale": _text(row.get("file_fonte")) or "tipi-base.xsd",
            "struttura_obbligatoria": _base_structure(),
            "campi_obbligatori": profile["campi"],
            "avvertimenti_obbligatori": profile["avvertimenti"],
        },
        "allegati_obbligatori": profile["allegati"],
        "adempimenti_fiscali_telematici": {
            "contributo_unificato": {"scaglione": "Da verificare in base a valore, rito ed esenzioni"},
            "deposito_telematico": {
                "obbligatorio": True,
                "controllo": "Verificare coerenza tra codice oggetto, atto principale, allegati e DatiAtto.xml.",
            },
        },
        "termini_processuali": profile["termini"],
        "controlli_deposito_telematico": [
            "Il codice oggetto deve essere quello ufficiale PST/XSD indicato nel catalogo caricato.",
            "Il formato dell'atto e degli allegati deve essere compatibile con le regole del canale di deposito.",
            "La busta deve superare il controllo locale prima dell'invio e le ricevute PEC vanno presidiate fino all'esito finale.",
        ],
        "avvertenze_redazionali": [
            "La scheda è una guida pratica operativa: prima del deposito verificare aggiornamenti ministeriali, rito e prassi dell'ufficio.",
            "Non sostituire il controllo professionale su competenza, termini, valore, contributo unificato e allegati.",
        ],
        "_quality_hint": "operativa_curata",
        "_curation_source": "completamento_guida_pratica_2026_05_22",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=str(FULL_KB))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    service = GuidaPraticaService(kb_path=Path(args.kb))
    current_rows = {
        normalize_codice_materia(row.get("codice")): dict(row)
        for row in service.list_guidance(limit=20000)
        if normalize_codice_materia(row.get("codice"))
    }
    existing_output_codes = _load_existing_codes(Path(args.output))
    target_codes = set(existing_output_codes)
    for codice, row in current_rows.items():
        coverage = row.get("coverage") if isinstance(row.get("coverage"), dict) else {}
        if coverage.get("level") != "curata":
            target_codes.add(codice)
    entries = [
        _entry(current_rows[codice], depositabile=bool(codice_oggetto_pst_entry(codice)))
        for codice in sorted(target_codes)
        if codice in current_rows
    ]
    payload = {
        "$schema": "iusentra/legal-knowledge-base/v1",
        "macro_area_id": "completamento_codici_ufficiali_pst_xsd",
        "denominazione": "Completamento codici ufficiali PST/XSD",
        "registro": "PST_XSD",
        "fonte": "Catalogo codici oggetto PST/XSD ufficiale caricato in pct/data/cataloghi/codici_oggetto_pst.json",
        "scopo": "Portare tutti i codici non ancora curati allo stesso formato operativo della Guida Pratica.",
        "codici_materia": entries,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output), "codici_curati_aggiunti": len(entries)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
