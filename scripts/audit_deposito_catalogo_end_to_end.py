"""Audit end-to-end del catalogo deposito PCT/UNEP.

Lo script controlla tutti i tipi del catalogo tecnico condiviso:
- ogni tipo deve avere regole coerenti con il canale;
- il server non deve mai risultare canale SMTP per depositi/notifiche;
- tutti i tipi PCT devono generare un DatiAtto.xml sintetico;
- nessun tipo PCT puo' restare sospeso per "generatore dedicato da completare";
- il contratto busta/PEC deve conservare Local Signer, get certificato ufficio,
  Atto.msg, Atto.enc e invio PEC dal PC locale.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.busta import BustaTelematica, DatiBusta
from pct.datiatto_xsd import validate_datiatto_xml
from pct.deposito_studio_telematico_validation import validate_studio_telematico_deposit
from pct.deposito_telematico_catalogo import list_deposit_catalog_entries
from web.services.deposito_anagrafica_ministeriale import (
    _anagrafica_procedimento_deposito_xml,
    _namespace_anagrafica_per_generatore,
)


QUICKORGANIZER_LISTA_UFFICI = Path(r"C:\QuickOrganizer\ListaUfficiGiudiziari.xml")
QUICKORGANIZER_QC_UFFICI = Path(r"C:\QuickOrganizer\QC_Uffici.xml")
NON_OPERATIVE_OFFICE_MARKERS = (
    "EX GIUD",
    "NON ATTIVO",
    "EX SD",
    "SEZIONE DISTACCATA",
    "MODEL OFFICE",
    "FORMAZIONE",
)
PCT_OFFICE_TYPES_REQUIRING_DEPOSIT_RESOLUTION = {"CA", "OR", "SC", "TM", "GP", "CC"}


ANAGRAFICA_PROCEDIMENTO_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<AnagraficaProcedimento xmlns="http://schemi.processotelematico.giustizia.it/sicid/tipi/anagrafiche/v6">
  <Parte ID="parte_1">
    <codiceFiscale>RSSMRA80A01H501Z</codiceFiscale>
  </Parte>
  <ControParte ID="debitore_1">
    <codiceFiscale>BNCLGU70A01H501Y</codiceFiscale>
  </ControParte>
  <Avvocato ID="avv_1">
    <cognome>Rossi</cognome>
    <nome>Mario</nome>
    <codiceFiscale>RSSMRA80A01H501Z</codiceFiscale>
    <via>Via Roma 1</via>
    <cap>00100</cap>
    <localita>Roma</localita>
    <provincia>RM</provincia>
  </Avvocato>
</AnagraficaProcedimento>
"""


def _sample_anagrafica(entry: dict[str, Any]) -> bytes | None:
    if not _needs_anagrafica(entry):
        return None
    generator_class = str(_schema(entry).get("generatorClass") or "")
    root_name = str(_schema(entry).get("ministerialRoot") or "")
    atti_ns, anagrafiche_ns = _namespace_anagrafica_per_generatore(generator_class, root_name)
    cliente = SimpleNamespace(
        tipo="PERSONA_FISICA",
        nome="Mario",
        cognome="Rossi",
        ragione_sociale="",
        codice_fiscale="RSSMRA80A01H501Z",
        partita_iva="",
        indirizzo_residenza=SimpleNamespace(
            via="Via Roma",
            civico="1",
            cap="00100",
            comune="Roma",
            provincia="RM",
        ),
        indirizzo_domicilio=None,
        indirizzo_sede_legale=None,
    )
    fascicolo = SimpleNamespace(
        nome_cliente="Mario Rossi",
        controparte="Luigi Bianchi",
        cf_controparte="BNCLGU70A01H501Y",
    )
    config = SimpleNamespace(
        studio=SimpleNamespace(
            codice_fiscale_avvocato="VRDLGI80A01H501X",
            avvocato="Luigi Verdi",
            indirizzo="Via Milano 2",
            city="Roma",
            province="RM",
        ),
        firma=SimpleNamespace(cf_avvocato="", certificato_codice_fiscale=""),
    )
    return _anagrafica_procedimento_deposito_xml(
        fascicolo=fascicolo,
        cliente=cliente,
        cfg_studio=config,
        operatore="Luigi Verdi",
        atti_ns=atti_ns,
        anagrafiche_ns=anagrafiche_ns,
    )

DATIATTO_EXTRA_BASE: dict[str, Any] = {
    "parte_codice_fiscale": "RSSMRA80A01H501Z",
    "avvocato_codice_fiscale": "RSSMRA80A01H501Z",
    "procedente_codice_fiscale": "RSSMRA80A01H501Z",
    "debitore_codice_fiscale": "BNCLGU70A01H501Y",
    "data_consegna_pignoramento": "01/07/2026",
    "importo_precetto": "1234,56",
    "data_pignoramento": "02/07/2026",
    "data_notifica_precetto": "03/07/2026",
    "stima_diritto": "1234,56",
    "data_citazione": "05/07/2026",
    "data_notifica_pignoramento": "04/07/2026",
    "unep_natura_atto": "PRECETTO",
    "unep_codice_natura": "1",
    "unep_data_richiesta": "01/07/2026",
    "unep_data_scadenza": "15/07/2026",
    "unep_ente_debito": "Ministero della giustizia",
    "unep_numero_debito": "2026-1",
    "unep_data_debito": "01/07/2026",
    "unep_causa_ufficio": "0580010",
    "unep_causa_numero": "1234",
    "unep_causa_anno": "2026",
    "unep_causa_data_udienza": "20/07/2026",
    "unep_inoltro_ufficiale_giudiziario": "0580010",
    "unep_importo_precetto": "1234,56",
    "unep_autorita_tipo": "1",
    "unep_autorita_sede": "Tribunale di Roma",
    "unep_autorizzazione_numero": "1234",
    "unep_autorizzazione_data": "01/07/2026",
    "unep_data_notifica_precetto": "30/06/2026",
    "unep_rito_codice": "1",
    "unep_codice_pagamento": "12345",
    "data_atto_deposito": "01/07/2026",
    "unep_registro_bilancio": "1",
    "unep_anno_bilancio": "2026",
    "unep_iban": "IT60X0542811101000000123456",
    "unep_destinatari": [
        {
            "id": "debitore-audit",
            "tipo_notifica": "Mani",
            "data_notifica_precetto": "30/06/2026",
        }
    ],
    "unep_beni": [
        {
            "id": "bene-audit",
            "tipo": "mobile",
            "tipologia": "ARREDI",
            "descrizione": "Bene mobile per audit",
            "valore": "1200,00",
            "diritti": [{"tipo": "1", "quota": "1"}],
        }
    ],
    "unep_titoli": [
        {
            "parte_id": "procedente-audit",
            "fattispecie": "Titolo esecutivo",
            "tipologia": "1",
            "descrizione": "Sentenza di condanna",
            "numero": "1",
            "data_emissione": "01/06/2026",
        }
    ],
    "precedente_fascicolo_numero": "321",
    "precedente_fascicolo_anno": "2025",
    "precedente_provvedimento_numero": "45",
    "precedente_provvedimento_anno": "2025",
    "data_precedente_provvedimento": "15/05/2025",
    "decreto_causa_numero": "789",
    "decreto_causa_anno": "2025",
    "decreto_numero": "123",
    "decreto_anno": "2025",
    "decreto_data": "20/05/2025",
    "decreto_esecutivo": False,
    "divorzio_sentenza_numero": "77",
    "divorzio_sentenza_anno": "2024",
    "separazione_tipo": "consensuale",
    "defunto_cognome": "Verdi",
    "defunto_nome": "Anna",
    "soggetto_interessato_cognome": "Bianchi",
    "soggetto_interessato_nome": "Luca",
    "successione_tipo_atto": "Istanza",
    "testamento_tipo": "NonSpecificato",
    "successione_parte_istante": "Proprio",
    "cui": "CUI123456789",
    "codice_vestanet": "VEST12345",
    "nazione_provenienza": "Albania",
    "data_decreto_immigrazione": "10/05/2026",
    "credito_capitale": "1000,00",
    "credito_importo": "1000,00",
    "credito_data_decorrenza": "01/01/2026",
    "credito_data_aggiornamento": "10/07/2026",
    "opposizione_istanza_sospensione": False,
    "osa_numero_verbale": "OSA-2026-001",
    "osa_data_verbale": "01/07/2026",
    "osa_motivazione": "Altro",
    "osa_riferimento_cartella": "12345678901234567",
    "osa_riferimento_ordinanza": "ORD-2026-001",
    "tipo_concordato_ccipu": "Ordinario",
    "misure_cautelari": False,
    "misure_protettive": False,
    "tipo_ricorso_cassazione": "Ricorso ordinario",
    "data_richiesta_notifica_cassazione": "01/07/2026",
    "data_effettiva_notifica_cassazione": "02/07/2026",
    "provvedimento_impugnato": {
        "ufficio": "0580910098",
        "ruolo": "Contenzioso",
        "numero_fascicolo": "321",
        "anno_fascicolo": "2025",
    },
    "inizio_primo_grado_anno": "2024",
    "inizio_primo_grado_ufficio": "0580910098",
    "materia_ricorso_cassazione": "001",
    "parole_chiave_cassazione": "controversia agraria",
    "motivi_cassazione": [
        {
            "numero": "1",
            "numero_art_360": "1",
            "pagina": "1",
            "descrizione": "Motivo sintetico per audit",
        }
    ],
    "contromotivi_cassazione": [
        {
            "numero_riferimento_motivo": "1",
            "pagina": "1",
            "descrizione": "Contromotivo sintetico per audit",
        }
    ],
    "lotto_numero": "1",
    "aggiudicazione_importo_aumento": "1000,00",
    "aggiudicazione_importo_offerta": "50000,00",
    "aggiudicazione_cauzione": "5000,00",
    "aggiudicatario_cognome": "Rossi",
    "aggiudicatario_nome": "Mario",
    "aggiudicatario_codice_fiscale": "RSSMRA80A01H501Z",
    "aggiudicazione_termine_conguaglio": "31/07/2026",
    "deposito_progetto": "Progetto di distribuzione sintetico per audit",
    "beni_pignorati": [
        {
            "tipo": "immobiliare",
            "descrizione": "Immobile sintetico per audit",
            "valore": "1234,56",
            "indirizzo": {"via": "Via Roma 1", "cap": "00100", "localita": "Roma", "provincia": "RM"},
            "dati_catastali": {"sezione": "U", "foglio": "1", "particella": "1"},
            "catasto": "NCEU",
            "classe": "A",
        }
    ],
    "titolo": {
        "descrizione": "Titolo esecutivo sintetico per audit",
        "tipologia": "Sentenza",
        "numero": "1",
        "data_emissione": "01/06/2026",
    },
    "custode": {
        "codice_fiscale": "CSTGNN80A01H501A",
        "cognome": "Custode",
        "nome": "Gianni",
        "via": "Via Roma 2",
        "cap": "00100",
        "localita": "Roma",
        "provincia": "RM",
    },
    "terzo": {
        "codice_fiscale": "TRZPLA80A01H501B",
        "cognome": "Terzo",
        "nome": "Paola",
        "via": "Via Napoli 3",
        "cap": "00100",
        "localita": "Roma",
        "provincia": "RM",
        "data_notifica_pignoramento": "04/07/2026",
        "data_notifica_precetto": "03/07/2026",
    },
    "terzi": [
        {
            "codice_fiscale": "TRZPLA80A01H501B",
            "cognome": "Terzo",
            "nome": "Paola",
            "via": "Via Napoli 3",
            "cap": "00100",
            "localita": "Roma",
            "provincia": "RM",
            "data_notifica_pignoramento": "04/07/2026",
            "data_notifica_precetto": "03/07/2026",
        },
        {
            "codice_fiscale": "TRZLNZ80A01H501C",
            "cognome": "Terzo",
            "nome": "Lorenzo",
            "via": "Via Milano 4",
            "cap": "00100",
            "localita": "Roma",
            "provincia": "RM",
            "data_notifica_pignoramento": "05/07/2026",
        },
    ],
}


def _sample_pdf(path: Path) -> Path:
    path.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF"
    )
    return path


def _payload(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else {}


def _schema(entry: dict[str, Any]) -> dict[str, Any]:
    schema = entry.get("schema")
    return schema if isinstance(schema, dict) else {}


def _rules(entry: dict[str, Any]) -> dict[str, Any]:
    rules = entry.get("rules")
    return rules if isinstance(rules, dict) else {}


def _fixed_object_code(entry: dict[str, Any]) -> str:
    schema = _schema(entry)
    fixed = schema.get("quickFixedObjectCodes") if isinstance(schema.get("quickFixedObjectCodes"), list) else []
    for item in fixed:
        if isinstance(item, dict) and str(item.get("code") or "").strip():
            return str(item["code"]).strip()
    if "SIGP" in str(schema.get("generatorClass") or ""):
        return "010001"
    return "110001"


def _needs_anagrafica(entry: dict[str, Any]) -> bool:
    schema = _schema(entry)
    generator_class = str(schema.get("generatorClass") or "")
    mode = str(schema.get("generatorMode") or "")
    return bool(
        generator_class.startswith("Introduttivi")
        or generator_class.startswith("Parte")
        or generator_class.startswith("CorsoCausa")
        or mode == "cassazione_parte"
    )


def _extra_for(entry: dict[str, Any]) -> dict[str, Any]:
    key = str(entry.get("key") or "")
    extra = dict(DATIATTO_EXTRA_BASE)
    if "MobiliarePressoDebitore" in key:
        extra["tipo_pignoramento"] = "mobiliare_presso_debitore"
        extra["beni_pignorati"] = [
            {"tipo": "mobile", "descrizione": "Bene mobile sintetico per audit", "tipologia": "ARREDI", "valore": "1200,00"}
        ]
    elif "MobiliarePressoTerzi" in key:
        extra["tipo_pignoramento"] = "mobiliare_presso_terzi"
        extra["beni_pignorati"] = [
            {"tipo": "mobile", "descrizione": "Credito sintetico presso terzi", "tipologia": "CREDITO", "valore": "1200,00"}
        ]
    elif "PignoramentoImmobiliare" in key:
        extra["tipo_pignoramento"] = "immobiliare"
    return extra


def _dati_busta_for(entry: dict[str, Any], atto_principale: Path) -> DatiBusta:
    payload = _payload(entry)
    schema = _schema(entry)
    registry = entry.get("registry") if isinstance(entry.get("registry"), dict) else {}
    codice_registro = str(payload.get("codice_registro") or registry.get("code") or "SICID").strip()
    codice_ufficio = "80417740588" if codice_registro == "CASSCI" else "0580010"
    root_name = str(schema.get("ministerialRoot") or payload.get("datiatto_root_name") or "").strip()
    required_data = list(schema.get("requiredData") or [])
    contribution_required = bool(schema.get("contributionRequired"))
    key = str(entry.get("key") or "")
    if "ADebito" in key or key.endswith("Debito"):
        contribution = {"resolved": True, "mode": "prenotato_a_debito", "importo": 0.0, "debito": True}
    elif key.startswith("Atti_UNEP::") and ("Esente" in key or "MateriaLavoro" in key):
        contribution = {"resolved": True, "mode": "esente", "importo": 0.0, "debito": False}
    elif contribution_required:
        contribution = {"resolved": True, "mode": "pagato", "importo": 259.0, "debito": False}
    else:
        contribution = None
    return DatiBusta(
        codice_ufficio=codice_ufficio,
        codice_registro=codice_registro,
        oggetto=_fixed_object_code(entry),
        tipo_atto=str(payload.get("tipo_atto") or "ATTO_GENERICO").strip(),
        atto_principale=str(atto_principale),
        numero_rg="1234",
        anno_rg=2026,
        operatore="Audit IUSENTRA",
        cf_mittente="RSSMRA80A01H501Z",
        valore_causa=1000.0,
        contributo_unificato=contribution,
        contributo_unificato_richiesto=contribution_required,
        contributo_unificato_xml_mode=str(schema.get("contributionXmlMode") or ""),
        anagrafica_procedimento_xml=_sample_anagrafica(entry),
        datiatto_generator_class=str(schema.get("generatorClass") or "").strip(),
        datiatto_root_name=root_name,
        datiatto_studio_variable=str(schema.get("studioVariable") or "").strip(),
        datiatto_catalog_key=str(entry.get("key") or "").strip(),
        datiatto_generator_mode=str(schema.get("generatorMode") or "").strip(),
        datiatto_required_data=required_data,
        datiatto_extra=_extra_for(entry),
        professionista={
            "ruolo": "DIFENSORE",
            "cognome": "Rossi",
            "nome": "Mario",
            "codice_fiscale": "RSSMRA80A01H501Z",
            "indirizzo": "Via Roma",
            "civico": "1",
            "cap": "00100",
            "citta": "Roma",
            "provincia": "RM",
            "nazione": "IT",
            "iban": "IT60X0542811101000000123456",
        },
        parti=[
            {
                "id": "procedente-audit",
                "gruppo": "parte",
                "ruolo": "ASSISTITO",
                "nome": "Mario",
                "cognome": "Rossi",
                "denominazione": "",
                "codice_fiscale": "RSSMRA80A01H501Z",
                "natura_giuridica": "PFI",
                "indirizzo": {
                    "via": "Via Roma",
                    "civico": "1",
                    "cap": "00100",
                    "citta": "Roma",
                    "provincia": "RM",
                    "nazione": "IT",
                },
                "domicilio": {
                    "via": "Via Roma",
                    "civico": "1",
                    "cap": "00100",
                    "citta": "Roma",
                    "provincia": "RM",
                    "nazione": "IT",
                },
            },
            {
                "id": "debitore-audit",
                "gruppo": "controparte",
                "ruolo": "DEBITORE",
                "nome": "Luigi",
                "cognome": "Bianchi",
                "denominazione": "",
                "codice_fiscale": "BNCLGU70A01H501Y",
                "natura_giuridica": "PFI",
                "tipo_notifica": "Mani",
                "data_notifica_precetto": "30/06/2026",
                "indirizzo": {
                    "via": "Via Milano",
                    "civico": "2",
                    "cap": "00100",
                    "citta": "Roma",
                    "provincia": "RM",
                    "nazione": "IT",
                },
                "domicilio": {
                    "via": "Via Milano",
                    "civico": "2",
                    "cap": "00100",
                    "citta": "Roma",
                    "provincia": "RM",
                    "nazione": "IT",
                },
            },
            {
                "id": "terzo-audit",
                "gruppo": "altro",
                "ruolo": "TERZO_PIGNORATO",
                "nome": "Anna",
                "cognome": "Verdi",
                "denominazione": "",
                "codice_fiscale": "VRDNNA80A41H501B",
                "natura_giuridica": "PFI",
                "indirizzo": {
                    "via": "Via Napoli",
                    "civico": "3",
                    "cap": "00100",
                    "citta": "Roma",
                    "provincia": "RM",
                    "nazione": "IT",
                },
                "domicilio": {
                    "via": "Via Napoli",
                    "civico": "3",
                    "cap": "00100",
                    "citta": "Roma",
                    "provincia": "RM",
                    "nazione": "IT",
                },
            },
        ],
        data_notifica_citazione=(
            "30/06/2026"
            if "citazione" in root_name.casefold() or root_name == "OpposizioneDecretoIngiuntivo"
            else ""
        ),
    )


def _check_common_contract(entry: dict[str, Any], errors: list[str]) -> None:
    key = str(entry.get("key") or "")
    rules = _rules(entry)
    schema = _schema(entry)
    ui = entry.get("ui") if isinstance(entry.get("ui"), dict) else {}
    if rules.get("server_smtp_allowed") is not False:
        errors.append(f"{key}: server_smtp_allowed deve essere False")
    if not ui.get("documents"):
        errors.append(f"{key}: documenti attesi mancanti")
    if not ui.get("controls"):
        errors.append(f"{key}: controlli operativi mancanti")
    if rules.get("channel_kind") == "pct_civile_dm44":
        for field in ("requires_datiatto", "requires_indice_busta", "requires_atto_enc", "requires_pst_cer"):
            if rules.get(field) is not True:
                errors.append(f"{key}: regola PCT {field} non attiva")
        expected_transport = {
            "indice_busta_mode": "interno_datiatto",
            "document_signature_profile": "pdf_pades_non_pdf_cades",
            "datiatto_signature_profile": "cades_bes_sha256_signing_certificate_v2",
            "mime_disposition": "attachment",
        }
        for field, expected in expected_transport.items():
            if rules.get(field) != expected:
                errors.append(f"{key}: profilo Studio Telematico {field}={expected!r} non rispettato")
        if not schema.get("generatorClass"):
            errors.append(f"{key}: classe generatore mancante")
        if not schema.get("ministerialRoot"):
            errors.append(f"{key}: radice ministeriale mancante")
        if not schema.get("evidenceMethods"):
            errors.append(f"{key}: metodo generatore di origine mancante")
        input_fields = schema.get("inputFields") if isinstance(schema.get("inputFields"), list) else []
        input_ids = [str(field.get("id") or "").strip() for field in input_fields if isinstance(field, dict)]
        if len(input_ids) != len(set(input_ids)):
            errors.append(f"{key}: campi UI deposito duplicati")
        for field in input_fields:
            if not isinstance(field, dict) or not str(field.get("id") or "").strip() or not str(field.get("label") or "").strip():
                errors.append(f"{key}: descrittore campo UI deposito incompleto")
    elif rules.get("channel_kind") == "unep_deposito_telematico":
        for field in ("requires_datiatto", "requires_indice_busta", "requires_atto_enc", "requires_pst_cer"):
            if rules.get(field) is not True:
                errors.append(f"{key}: regola deposito UNEP {field} non attiva")
        if rules.get("can_prepare_in_pct_panel") is not True:
            errors.append(f"{key}: il deposito UNEP deve prepararsi nel pannello deposito")
        if rules.get("requires_relata") is not False:
            errors.append(f"{key}: il deposito UNEP non deve dipendere dalla relata di notifica")
        if not schema.get("generatorClass") or not schema.get("ministerialRoot"):
            errors.append(f"{key}: generatore DatiAtto UNEP incompleto")


def _check_source_contracts(errors: list[str]) -> None:
    checks = [
        (
            ROOT / "tools" / "local_signer.py",
            [
                "/pst/certificato-ufficio",
                "<ser:getCertificato>",
                "certificato_b64",
                "_PST_CATALOGO_SERVIZI_URLS",
            ],
        ),
        (
            ROOT / "web" / "bootstrap" / "deposito_routes.py",
            [
                "deposito_catalogo_datiatto_extra",
                "deposito_catalogo_busta_metadata",
                "certificato-cifratura",
                "local_pec_required_response",
                "prova_senza_invio",
                "simula_invio_pec",
            ],
        ),
        (
            ROOT / "web" / "services" / "deposito_catalogo_runtime.py",
            [
                "def deposito_catalogo_busta_metadata",
                '"datiatto_extra": extra',
            ],
        ),
        (
            ROOT / "web" / "services" / "local_pec_runtime.py",
            [
                "build_local_pec_payload",
                "Allegato Atto.enc non conforme",
                "LOCAL_SIGNER_BASE_URL",
                "attachment_name=\"Atto.enc\"",
            ],
        ),
        (
            ROOT / "frontend" / "src" / "components" / "FascicoloDepositoPage.tsx",
            [
                "recoverPstOfficeCertificateBeforePackage",
                "localSignerEndpointForStatus('/pst/certificato-ufficio'",
                "assertLocalPecAttoEncBase64(localPayload)",
                "const pecWorkflowAvailable = depositOfficePecAvailable",
                "IUSENTRA non ha risolto automaticamente la PEC dell’ufficio",
            ],
        ),
    ]
    for path, needles in checks:
        try:
            source = path.read_text(encoding="utf-8")
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: sorgente non leggibile: {exc}")
            continue
        for needle in needles:
            if needle not in source:
                errors.append(f"{path.relative_to(ROOT)}: contratto mancante `{needle}`")


def _child_text(element: etree._Element, localname: str) -> str:
    found = element.find(f".//{{*}}{localname}")
    return str(found.text or "").strip() if found is not None and found.text else ""


def _office_services_from_xml(element: etree._Element) -> list[str]:
    services: list[str] = []
    for service in element.findall(".//{*}servizi"):
        code = _child_text(service, "codice").upper()
        if code:
            services.append(code)
    return services


def _quickorganizer_office_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if QUICKORGANIZER_LISTA_UFFICI.exists():
        root = etree.parse(str(QUICKORGANIZER_LISTA_UFFICI)).getroot()
        rows: list[dict[str, Any]] = []
        for item in root.iter():
            if etree.QName(item).localname != "return":
                continue
            services = _office_services_from_xml(item)
            rows.append(
                {
                    "codice": _child_text(item, "codiceUfficio"),
                    "descrizione": _child_text(item, "descrizione"),
                    "pec": _child_text(item, "indirizzoPec").lower(),
                    "tipo": _child_text(item, "tipoUfficio").upper(),
                    "codice_gl": _child_text(item, "codiceGL"),
                    "servizi": services,
                    "source": str(QUICKORGANIZER_LISTA_UFFICI),
                }
            )
        return rows, {
            "source": str(QUICKORGANIZER_LISTA_UFFICI),
            "qc_uffici_found": QUICKORGANIZER_QC_UFFICI.exists(),
        }

    fallback = ROOT / "pct" / "data" / "uffici_ministero.json"
    data = json.loads(fallback.read_text(encoding="utf-8"))
    rows = []
    uffici = data.get("uffici", [])
    office_items = uffici.values() if isinstance(uffici, dict) else uffici
    for item in office_items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "codice": str(item.get("codice_ministero") or "").strip(),
                "descrizione": str(item.get("descrizione_ministero") or item.get("nome") or "").strip(),
                "pec": str(item.get("pec_ministero") or item.get("pec") or "").strip().lower(),
                "tipo": str(item.get("tipo_ministero") or item.get("tipo") or "").strip().upper(),
                "codice_gl": str(item.get("codice_gl") or "").strip(),
                "servizi": [str(service or "").strip().upper() for service in item.get("servizi_ministero", [])],
                "source": str(fallback),
            }
        )
    return rows, {"source": str(fallback), "qc_uffici_found": False}


def _external_office_is_operational_pct(row: dict[str, Any]) -> bool:
    description = str(row.get("descrizione") or "").upper()
    if any(marker in description for marker in NON_OPERATIVE_OFFICE_MARKERS):
        return False
    if str(row.get("tipo") or "").upper() not in PCT_OFFICE_TYPES_REQUIRING_DEPOSIT_RESOLUTION:
        return False
    services = {str(service or "").strip().upper() for service in row.get("servizi", []) if str(service or "").strip()}
    return any(service.startswith("JPW_") for service in services)


def _office_aliases_for_deposit_audit(office: dict[str, Any], source_row: dict[str, Any]) -> list[str]:
    aliases = {
        str(office.get("nome") or "").strip(),
        str(office.get("descrizione_ministero") or source_row.get("descrizione") or "").strip(),
    }
    office_type = str(office.get("tipo") or "").strip().upper()
    comune = str(office.get("comune_ministero") or "").strip()
    if comune:
        if office_type == "TRIBUNALE":
            aliases.update(
                {
                    f"TRIBUNALE DI {comune.upper()}",
                    f"TRIBUNALE ORDINARIO DI {comune.upper()}",
                    f"Tribunale Ordinario - {comune}",
                }
            )
        elif office_type == "GDP":
            aliases.update({f"GIUDICE DI PACE DI {comune.upper()}", f"Giudice di Pace - {comune}"})
        elif office_type == "CORTE_APPELLO":
            aliases.update({f"CORTE D'APPELLO DI {comune.upper()}", f"Corte d'Appello - {comune}"})
        elif office_type == "TM":
            aliases.update({f"TRIBUNALE PER I MINORENNI DI {comune.upper()}"})
    return sorted(alias for alias in aliases if alias)


def _check_office_catalog_contracts(errors: list[str]) -> dict[str, Any]:
    try:
        from pct.pst_cifratura import _iter_certificati_cifratura_target_rows
        from pct.uffici_giudiziari import get_gestore
        from web.services.react_fascicoli_bridge import _deposit_office_payload, _uffici_cache_path
    except Exception as exc:
        errors.append(f"catalogo uffici: import resolver non riuscito: {exc}")
        return {"ok": False, "error": str(exc)}

    offices = get_gestore(_uffici_cache_path()).carica()
    offices_by_ministerial = {
        str(office.get("codice_ministero") or office.get("codice") or "").strip(): office
        for office in offices
        if str(office.get("codice_ministero") or office.get("codice") or "").strip()
    }
    target_rows = list(_iter_certificati_cifratura_target_rows())
    target_codes = sorted({str(row.get("codice_ufficio") or "").strip() for row in target_rows if str(row.get("codice_ufficio") or "").strip()})

    missing_target: list[dict[str, str]] = []
    empty_target: list[dict[str, str]] = []
    resolver_errors: list[dict[str, str]] = []
    for row in target_rows:
        code = str(row.get("codice_ufficio") or "").strip()
        if not code:
            continue
        office = offices_by_ministerial.get(code)
        if office is None:
            missing_target.append({"codice": code, "descrizione": str(row.get("descrizione") or "")})
            continue
        pec = str(office.get("pec") or office.get("pec_ministero") or "").strip()
        name = str(office.get("nome") or row.get("descrizione") or "").strip()
        internal_code = str(office.get("codice") or "").strip()
        if not pec or not internal_code:
            empty_target.append({"codice": code, "nome": name, "pec": pec, "codice_iusentra": internal_code})
            continue
        for alias in _office_aliases_for_deposit_audit(office, row):
            resolved = _deposit_office_payload(
                SimpleNamespace(
                    tribunale=alias,
                    profilo_deposito={},
                )
            )
            if not (
                resolved.get("pec")
                and (resolved.get("code") or resolved.get("ministerialCode"))
                and resolved.get("verified")
            ):
                resolver_errors.append(
                    {
                        "codice": code,
                        "nome": name,
                        "alias": alias,
                        "pec": pec,
                        "resolver_message": str(resolved.get("message") or ""),
                    }
                )
                break

    external_rows, external_source = _quickorganizer_office_rows()
    external_operational = [row for row in external_rows if _external_office_is_operational_pct(row)]
    external_missing: list[dict[str, str]] = []
    external_mismatch: list[dict[str, str]] = []
    external_no_pec: list[dict[str, str]] = []
    for row in external_operational:
        code = str(row.get("codice") or "").strip()
        expected_pec = str(row.get("pec") or "").strip().lower()
        office = offices_by_ministerial.get(code)
        if office is None:
            external_missing.append({"codice": code, "descrizione": str(row.get("descrizione") or "")})
            continue
        actual_pec = str(office.get("pec") or office.get("pec_ministero") or "").strip().lower()
        if not expected_pec:
            external_no_pec.append({"codice": code, "descrizione": str(row.get("descrizione") or "")})
        elif actual_pec != expected_pec:
            external_mismatch.append(
                {
                    "codice": code,
                    "descrizione": str(row.get("descrizione") or ""),
                    "pec_fonte": expected_pec,
                    "pec_iusentra": actual_pec,
                }
            )

    for label, rows in (
        ("target PCT senza catalogo interno", missing_target),
        ("target PCT senza PEC/codice interno", empty_target),
        ("resolver React non risolve PEC/codice", resolver_errors),
        ("fonte Studio/PST operativa mancante in IUSENTRA", external_missing),
        ("fonte Studio/PST operativa senza PEC", external_no_pec),
        ("PEC diversa da fonte Studio/PST", external_mismatch),
    ):
        if rows:
            sample = "; ".join(
                (
                    f"{row.get('codice')} "
                    f"{row.get('alias') or row.get('nome') or row.get('descrizione') or row.get('resolver_message') or ''}"
                ).strip()
                for row in rows[:8]
            )
            errors.append(f"catalogo uffici: {label}: {len(rows)} ({sample})")

    return {
        "ok": not (missing_target or empty_target or resolver_errors or external_missing or external_no_pec or external_mismatch),
        "source": external_source,
        "iusentra_offices": len(offices),
        "pct_target_codes": len(target_codes),
        "pct_target_missing_in_iusentra": len(missing_target),
        "pct_target_without_pec_or_code": len(empty_target),
        "react_resolver_errors": len(resolver_errors),
        "external_operational_pct_rows": len(external_operational),
        "external_operational_missing_in_iusentra": len(external_missing),
        "external_operational_without_pec": len(external_no_pec),
        "external_operational_pec_mismatch": len(external_mismatch),
    }


def _xml_localnames(root: etree._Element) -> set[str]:
    return {etree.QName(element).localname for element in root.iter()}


def _required_xml_fields(entry: dict[str, Any]) -> list[str]:
    key = str(entry.get("key") or "")
    schema = _schema(entry)
    root = str(schema.get("ministerialRoot") or "")
    generator = str(schema.get("generatorClass") or "")
    source_required = {
        "".join(character for character in str(item or "").casefold() if character.isalnum())
        for item in (schema.get("requiredData") or [])
    }
    contribution_xml_mode = str(schema.get("contributionXmlMode") or "")
    required = ["AttoRichiestaVisibilita", "Parte", "Avvocato", "codiceFiscale", "parteRappresentata"] if root == "AttoRichiestaVisibilita" else []
    if root == "IscrizioneRuoloPignoramento":
        required = [
            "AnagraficaProcedimento",
            "DataConsegnaPignoramento",
            "ImportoPrecetto",
            "Beni",
            "EstensioneAnagrafica",
            "DatiDebitore",
            "DatiProcedente",
            "EstensioneDatiRito",
            "titolo",
            "titoloEsecutivo",
            "benePignorato",
        ]
        if "MobiliarePressoDebitore" in key:
            required.extend(["pressoDebitore", "Custode"])
        elif "MobiliarePressoTerzi" in key:
            required.extend(["pressoTerzo", "DatiTerzo", "dataNotificaPignoramento"])
        else:
            required.append("immobiliare")
    elif root == "ProgettoDistribuzione":
        required = (
            ["procedimento", "dispositivo", "accoglimentoPianoRiparto"]
            if generator == "DelSiecicEsecuzioni"
            else ["procedimento", "deposito", "depositoPianoRiparto"]
        )
    elif root == "DepositoRelazioneIniziale":
        required = ["procedimento", "numero", "anno"]
    elif generator == "IntroduttiviSiecicConcorsuali" and root.startswith("Ricorso") and root.endswith("CCIPU"):
        required = ["destinazione", "Oggetto", "AnagraficaProcedimentoPU", "misureCautelari", "misureProtettive"]
        if root in {"RicorsoAmmissConcordatoPreventivoCCIPU", "RicorsoOmologaAccordiRistrutturazCCIPU"}:
            required.extend(["EstensioneAnagrafica", "DatiDebitore", "formaSocietaria", "tipoConcordato"])
        else:
            required.extend(["TipoParteIstante", "Creditore", "creditore"])
    elif generator.startswith("ParteCassazione") and root in {"Ricorso", "ControRicorso", "ControRicorsoIncidentale"}:
        required = [
            "TipoRicorso",
            "dataRichiestaNotifica",
            "dataEffettivaNotifica",
            "Provvedimento",
            "DatiFascicolo",
            "Materia",
            "AnagraficaProcedimento",
            "DocumentiECLI",
        ]
        if root in {"Ricorso", "ControRicorsoIncidentale"}:
            required.extend(["Motivi", "Motivo"])
        if root in {"ControRicorso", "ControRicorsoIncidentale"}:
            required.extend(["ControMotivi", "ControMotivo"])
    elif generator.startswith("ParteCassazione") and root == "AttoGenerico":
        required = ["procedimento", "numero", "anno", "deposito"]
    elif generator.startswith("ParteCassazione") and root == "IntegrazioneAnagrafica":
        required = ["procedimento", "numero", "anno", "ModificheAnagrafica", "deposito"]
    elif generator.startswith("Introduttivi"):
        required = ["destinazione", "Oggetto", "AnagraficaProcedimento"]
    elif generator.startswith(("Parte", "CorsoCausa", "Professionista", "ProfSiecic", "CurSiecic", "CusSiecic", "DelSiecic")):
        required = ["procedimento", "numero", "anno"]
    if "valorecausa" in source_required:
        required.append("ValoreCausa")
    if contribution_xml_mode in {"atto_introduttivo", "cassazione_spese_giustizia", "cassazione_integrazione_spese"}:
        required.extend(["ContributoUnificato", "Importo"])
    elif contribution_xml_mode == "siecic_istanza_vendita":
        required.extend(["creditore", "contributoUnificato", "Importo"])
    return required


def _contribution_amount_node(root: etree._Element, xml_mode: str) -> etree._Element | None:
    wrapper = "contributoUnificato" if xml_mode == "siecic_istanza_vendita" else "ContributoUnificato"
    return root.find(f".//{{*}}{wrapper}/{{*}}Importo")


def _check_xml_fields(entry: dict[str, Any], root: etree._Element) -> list[str]:
    names = _xml_localnames(root)
    missing = [field for field in _required_xml_fields(entry) if field not in names]
    if missing:
        return [f"campo XML mancante `{field}`" for field in missing]
    return []


def _validation_context(entry: dict[str, Any], dati: DatiBusta, extra: dict[str, Any]) -> dict[str, Any]:
    key = str(entry.get("key") or "")
    office_name = "UNEP TRIBUNALE DI ROMA" if key.startswith("Atti_UNEP::") else "Tribunale di Roma"
    return {
        "atto_principale_id": "atto-principale-audit",
        "ufficio_giudiziario": office_name,
        "codice_registro": dati.codice_registro,
        "oggetto": dati.oggetto,
        "codice_oggetto_pst": dati.oggetto,
        "numero_rg": dati.numero_rg,
        "anno_rg": dati.anno_rg,
        "datiatto_extra": extra,
        "contributo_unificato": dati.contributo_unificato or {},
        "professionista": {
            "ruolo": "DIFENSORE",
            "cognome": "Rossi",
            "nome": "Mario",
            "codice_fiscale": "RSSMRA80A01H501Z",
            "indirizzo": "Via Roma 1",
            "cap": "00100",
            "citta": "Roma",
            "iban": "IT60X0542811101000000123456",
        },
        "parti": [
            {
                "ruolo": "PARTE",
                "natura_giuridica": "PFI",
                "data_nascita": "01/01/1980",
                "domicilio": {"via": "Via Roma 1", "citta": "Roma"},
            },
            {
                "ruolo": "CONTROPARTE",
                "natura_giuridica": "PFI",
                "data_nascita": "01/01/1970",
                "tipo_notifica": "Mani",
                "domicilio": {"via": "Via Milano 2", "citta": "Roma"},
            },
        ],
    }


def _check_declared_input_contract(entry: dict[str, Any], dati: DatiBusta) -> tuple[list[str], int]:
    """Verifica i campi nello stesso ordine di Studio: validatore, poi generatore/XSD."""

    schema = _schema(entry)
    fields = [field for field in (schema.get("inputFields") or []) if isinstance(field, dict)]
    field_ids = {str(field.get("id") or "").strip() for field in fields if str(field.get("id") or "").strip()}
    source_extra = dict(dati.datiatto_extra or {})
    derived_keys = {"tipo_pignoramento"}
    declared_extra = {
        key: value
        for key, value in source_extra.items()
        if key in field_ids or key in derived_keys
    }
    declared_data = replace(
        dati,
        datiatto_extra=declared_extra,
        data_notifica_citazione=(
            dati.data_notifica_citazione if "data_notifica_citazione" in field_ids else ""
        ),
    )
    errors: list[str] = []
    try:
        payload = BustaTelematica(declared_data).crea_dati_atto_xml_per_firma()
        validation = validate_datiatto_xml(payload)
        if not validation.ok:
            errors.append("i soli campi esposti in UI producono XML non valido: " + "; ".join(validation.errors[:2]))
    except Exception as exc:
        errors.append(f"campo richiesto dal generatore non esposto in UI: {exc}")
        return errors, 0

    guards_checked = 0
    for field in fields:
        if not bool(field.get("required")):
            continue
        field_id = str(field.get("id") or "").strip()
        if not field_id:
            continue
        without_field = dict(declared_extra)
        without_field.pop(field_id, None)
        missing_data = replace(
            declared_data,
            datiatto_extra=without_field,
            data_notifica_citazione=(
                "" if field_id == "data_notifica_citazione" else declared_data.data_notifica_citazione
            ),
        )
        context = _validation_context(entry, missing_data, without_field)
        findings = validate_studio_telematico_deposit(
            key=str(entry.get("key") or ""),
            context=context,
            selected_documents=[],
            resolver={
                "effective_office_found": True,
                "official_office_found": True,
                "effective_office_name": context["ufficio_giudiziario"],
            },
        )
        blocked_by_source_validator = any(
            finding.get("level") == "BLOCK" and finding.get("field") == field_id
            for finding in findings
        )
        try:
            BustaTelematica(missing_data).crea_dati_atto_xml_per_firma()
        except Exception:
            blocked_by_generator = True
        else:
            blocked_by_generator = False
        if blocked_by_source_validator or blocked_by_generator:
            guards_checked += 1
        else:
            errors.append(
                f"campo UI obbligatorio non presidiato dal validatore Studio ne' dal generatore: "
                f"{field.get('label') or field_id}"
            )
    return errors, guards_checked


def audit_deposit_catalog() -> dict[str, Any]:
    entries = list(list_deposit_catalog_entries())
    errors: list[str] = []
    generated: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    contribution_exemption_checked = 0
    required_input_guards_checked = 0
    channels = {"pct": 0, "unep": 0, "other": 0}

    with tempfile.TemporaryDirectory(prefix="iusentra-deposito-audit-") as tmp_dir:
        atto = _sample_pdf(Path(tmp_dir) / "atto.pdf")
        for entry in entries:
            key = str(entry.get("key") or "")
            rules = _rules(entry)
            schema = _schema(entry)
            _check_common_contract(entry, errors)

            channel_kind = str(rules.get("channel_kind") or "")
            if channel_kind == "pct_civile_dm44":
                channels["pct"] += 1
            elif channel_kind == "unep_deposito_telematico":
                channels["unep"] += 1
            else:
                channels["other"] += 1

            real_allowed = bool(rules.get("real_send_allowed_from_pct_panel"))
            supported = bool(schema.get("supported"))
            requires_specific = bool(schema.get("requiresSpecificGenerator"))

            is_ministerial_deposit = channel_kind in {"pct_civile_dm44", "unep_deposito_telematico"}

            if is_ministerial_deposit and requires_specific:
                errors.append(f"{key}: ramo deposito ancora sospeso, completare generatore e campi prima del verde")
                blocked.append(
                    {
                        "key": key,
                        "root": str(schema.get("ministerialRoot") or ""),
                        "generator": str(schema.get("generatorClass") or ""),
                        "status": str(schema.get("status") or ""),
                    }
                )
                continue

            if is_ministerial_deposit and not real_allowed:
                errors.append(f"{key}: invio reale del deposito non abilitato dal catalogo")
                blocked.append(
                    {
                        "key": key,
                        "root": str(schema.get("ministerialRoot") or ""),
                        "generator": str(schema.get("generatorClass") or ""),
                        "status": str(schema.get("status") or ""),
                    }
                )
                continue

            if is_ministerial_deposit and supported and real_allowed:
                entry_errors: list[str] = []
                try:
                    dati = _dati_busta_for(entry, atto)
                    busta = BustaTelematica(dati)
                    xml_payload = busta.crea_dati_atto_xml_per_firma()
                    root = etree.fromstring(xml_payload)
                    busta_audit = busta.audit_conformita_pst()
                except Exception as exc:  # pragma: no cover - diagnostic detail matters.
                    errors.append(f"{key}: generazione DatiAtto.xml fallita: {exc}")
                    continue
                expected_root = str(schema.get("ministerialRoot") or "")
                actual_root = etree.QName(root).localname
                if actual_root != expected_root:
                    entry_errors.append(f"radice generata {actual_root}, attesa {expected_root}")
                entry_errors.extend(_check_xml_fields(entry, root))
                xsd_validation = validate_datiatto_xml(xml_payload)
                if not xsd_validation.ok:
                    schema_label = xsd_validation.schema_path or "schema non individuato"
                    details = "; ".join(xsd_validation.errors[:3])
                    entry_errors.append(f"XSD {schema_label}: {details}")
                input_errors, input_guards = _check_declared_input_contract(entry, dati)
                entry_errors.extend(input_errors)
                required_input_guards_checked += input_guards
                contribution_required = bool(schema.get("contributionRequired"))
                contribution_xml_mode = str(schema.get("contributionXmlMode") or "")
                if contribution_required:
                    amount_node = _contribution_amount_node(root, contribution_xml_mode)
                    initial_contribution = dati.contributo_unificato if isinstance(dati.contributo_unificato, dict) else {}
                    initial_mode = str(initial_contribution.get("mode") or "")
                    documentary_only = contribution_xml_mode == "controllo_documentale" and not key.startswith("Atti_UNEP::")
                    if documentary_only:
                        if root.find(".//{*}ContributoUnificato") is not None or root.find(".//{*}contributoUnificato") is not None:
                            entry_errors.append("il controllo documentale non deve aggiungere il contributo a una radice che non lo prevede")
                        try:
                            unresolved_data = replace(dati, contributo_unificato={"resolved": False, "mode": "da_definire"})
                            BustaTelematica(unresolved_data).crea_dati_atto_xml_per_firma()
                        except ValueError:
                            contribution_exemption_checked += 1
                        else:
                            entry_errors.append("il contributo obbligatorio non definito non blocca la generazione")
                        amount_node = None
                    elif initial_mode in {"pagato", "prenotato_a_debito"}:
                        expected_amount = f"{float(initial_contribution.get('importo') or 0):.2f}"
                        if amount_node is None or str(amount_node.text or "").strip() != expected_amount:
                            entry_errors.append("ContributoUnificato senza Importo ministeriale coerente")
                        elif initial_mode == "pagato" and key.startswith("Atti_UNEP::") and "debito" in amount_node.attrib:
                            entry_errors.append("ContributoUnificato pagato con attributo debito non previsto da Studio Telematico")
                        elif initial_mode == "pagato" and not key.startswith("Atti_UNEP::") and amount_node.get("debito") != "false":
                            entry_errors.append("ContributoUnificato pagato senza attributo debito=false")
                        elif initial_mode == "prenotato_a_debito" and amount_node.get("debito") != "true":
                            entry_errors.append("ContributoUnificato prenotato a debito senza attributo debito=true")
                    elif amount_node is not None:
                        entry_errors.append("ContributoUnificato presente per una modalita' che Studio Telematico non serializza")
                    if documentary_only:
                        pass
                    elif contribution_xml_mode == "cassazione_integrazione_spese":
                        try:
                            exempt_data = replace(
                                dati,
                                valore_causa=None,
                                contributo_unificato={"resolved": True, "mode": "esente", "importo": None, "debito": False},
                            )
                            BustaTelematica(exempt_data).crea_dati_atto_xml_per_firma()
                        except ValueError:
                            contribution_exemption_checked += 1
                        else:
                            entry_errors.append("l’integrazione spese non deve accettare il contributo come esente")
                    else:
                        try:
                            exempt_data = replace(
                                dati,
                                valore_causa=None,
                                contributo_unificato={"resolved": True, "mode": "esente", "importo": None, "debito": False},
                            )
                            exempt_root = etree.fromstring(BustaTelematica(exempt_data).crea_dati_atto_xml_per_firma())
                        except Exception as exc:
                            entry_errors.append(f"ramo esenzione non generabile: {exc}")
                        else:
                            if contribution_xml_mode == "cassazione_spese_giustizia":
                                exempt_node = exempt_root.find(".//{*}ContributoUnificato/{*}Esente")
                                if exempt_node is None or str(exempt_node.text or "").strip().casefold() != "true":
                                    entry_errors.append("l’esenzione Cassazione deve generare Esente=true")
                            else:
                                wrapper = "contributoUnificato" if contribution_xml_mode == "siecic_istanza_vendita" else "ContributoUnificato"
                                if exempt_root.find(f".//{{*}}{wrapper}") is not None:
                                    entry_errors.append("l'esenzione non deve generare ContributoUnificato")
                            if contribution_xml_mode == "atto_introduttivo" and _child_text(exempt_root, "ValoreCausa") != "0.00":
                                entry_errors.append("l'esenzione senza valore deve generare ValoreCausa=0.00")
                            contribution_exemption_checked += 1
                    if not documentary_only:
                        try:
                            debt_data = replace(
                                dati,
                                contributo_unificato={"resolved": True, "mode": "prenotato_a_debito", "importo": 259.0, "debito": True},
                            )
                            debt_root = etree.fromstring(BustaTelematica(debt_data).crea_dati_atto_xml_per_firma())
                            debt_amount = _contribution_amount_node(debt_root, contribution_xml_mode)
                        except Exception as exc:
                            entry_errors.append(f"ramo prenotazione a debito non generabile: {exc}")
                        else:
                            if debt_amount is None or debt_amount.get("debito") != "true":
                                entry_errors.append("la prenotazione a debito deve generare Importo con debito=true")
                if busta_audit.get("indice_documenti_generated") is not True:
                    entry_errors.append("IndiceDocumentiDepositati.PDF non generato")
                if busta_audit.get("indice_busta_generated") is not True:
                    entry_errors.append("IndiceBusta ministeriale non generato")
                if busta_audit.get("indice_busta_mime_contract_ok") is not True:
                    entry_errors.append("IndiceBusta non coerente con i file fisici della busta")
                if entry_errors:
                    errors.extend(f"{key}: {message}" for message in entry_errors)
                else:
                    generated.append(
                        {
                            "key": key,
                            "root": actual_root,
                            "generator": str(schema.get("generatorClass") or ""),
                            "channel": channel_kind,
                        }
                    )
            elif is_ministerial_deposit:
                errors.append(f"{key}: schema ministeriale non supportato dal generatore")

    office_catalog = _check_office_catalog_contracts(errors)
    _check_source_contracts(errors)

    pct_generated = sum(item.get("channel") == "pct_civile_dm44" for item in generated)
    unep_generated = sum(item.get("channel") == "unep_deposito_telematico" for item in generated)
    return {
        "ok": not errors,
        "source_of_truth": "catalogo_tecnico_condiviso_confronto_funzionale_interno_specifiche_pst",
        "total": len(entries),
        "channels": channels,
        "pct_generated_datiatto": pct_generated,
        "unep_generated_datiatto": unep_generated,
        "ministerial_generated_datiatto": len(generated),
        "pct_real_send_suspended_until_dedicated_generator": len(blocked),
        "pct_expected_datiatto": channels["pct"],
        "unep_expected_datiatto": channels["unep"],
        "ministerial_expected_datiatto": channels["pct"] + channels["unep"],
        "pct_contribution_exemption_branches_checked": contribution_exemption_checked,
        "pct_required_input_guards_checked": required_input_guards_checked,
        "office_catalog": office_catalog,
        "blocked_keys": blocked,
        "sample_generated": generated[:12],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Percorso JSON report opzionale.")
    args = parser.parse_args()
    report = audit_deposit_catalog()
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
