"""Campi operativi richiesti dai generatori ministeriali di deposito."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from lxml import etree


def _field(
    field_id: str,
    label: str,
    field_type: str = "text",
    *,
    required: bool = True,
    group: str = "Dati del deposito",
    options: tuple[tuple[str, str], ...] = (),
    note: str = "",
) -> dict[str, Any]:
    return {
        "id": field_id,
        "label": label,
        "type": field_type,
        "required": required,
        "group": group,
        "options": [{"value": value, "label": option_label} for value, option_label in options],
        "note": note,
    }


def _append_unique(fields: list[dict[str, Any]], *new_fields: dict[str, Any]) -> None:
    known = {str(field.get("id") or "") for field in fields}
    for field in new_fields:
        field_id = str(field.get("id") or "")
        if field_id and field_id not in known:
            fields.append(field)
            known.add(field_id)


TITLE_OPTIONS = (
    ("1", "Sentenza di condanna di primo grado"),
    ("2", "Sentenza di condanna di secondo grado"),
    ("3", "Decreto ingiuntivo"),
    ("4", "Cambiale"),
    ("5", "Ordinanza"),
    ("6", "Ordinanza in corso di causa"),
    ("7", "Ingiunzione in corso di causa"),
    ("8", "Omologa della separazione consensuale"),
    ("9", "Verbale di conciliazione"),
    ("10", "Cartella esattoriale"),
    ("11", "Assegno"),
    ("12", "Contratto di finanziamento"),
    ("13", "Contratto di vendita"),
    ("14", "Contratto di sovvenzione"),
    ("15", "Polizza di pegno"),
    ("16", "Fattura"),
    ("17", "Mutuo fondiario"),
    ("18", "Mutuo ipotecario"),
    ("19", "Atto notarile"),
    ("20", "Lodo arbitrale"),
    ("21", "Scrittura contabile autenticata"),
    ("99", "Altro titolo da specificare"),
)

CASSAZIONE_ROLE_OPTIONS = (
    ("Speciale", "Ruolo speciale"),
    ("Contenzioso", "Contenzioso"),
    ("Lavoro", "Lavoro"),
    ("Agraria", "Agraria"),
    ("VolontariaGiurisdizione", "Volontaria giurisdizione"),
    ("EsecuzioniCivili", "Esecuzioni civili"),
    ("EspropriazioniImmobiliari", "Espropriazioni immobiliari"),
    ("Notifiche", "Notifiche"),
    ("AffariCivili", "Affari civili"),
)


def datiatto_input_fields(catalog_key: str, generator_class: str, root_name: str) -> list[dict[str, Any]]:
    """Restituisce solo i campi pertinenti al tipo di deposito selezionato."""

    key = str(catalog_key or "")
    suffix = key.rsplit("::", 1)[-1]
    fields: list[dict[str, Any]] = []

    if generator_class.startswith("Introduttivi") and (
        "citazione" in root_name.casefold() or root_name == "OpposizioneDecretoIngiuntivo"
    ):
        _append_unique(fields, _field("data_notifica_citazione", "Data di notificazione", "date"))

    if root_name in {"CitazioneAppello", "RicorsoAppello"}:
        _append_unique(
            fields,
            _field("precedente_provvedimento_numero", "Numero del provvedimento impugnato"),
            _field("precedente_provvedimento_anno", "Anno del provvedimento impugnato", "year"),
            _field("precedente_fascicolo_numero", "Numero del fascicolo precedente", required=False),
            _field("precedente_fascicolo_anno", "Anno del fascicolo precedente", "year", required=False),
        )
    if root_name == "CitazioneInRiassunzione":
        _append_unique(
            fields,
            _field("precedente_fascicolo_numero", "Numero del procedimento da riassumere"),
            _field("precedente_fascicolo_anno", "Anno del procedimento da riassumere", "year"),
            _field("data_precedente_provvedimento", "Data del provvedimento", "date"),
        )
        if "Appello" in key:
            _append_unique(
                fields,
                _field("precedente_provvedimento_numero", "Numero del provvedimento impugnato"),
                _field("precedente_provvedimento_anno", "Anno del provvedimento impugnato", "year"),
            )
    if root_name in {"OpposizioneDecretoIngiuntivo", "RicorsoOpposizioneDecretoIngiuntivo"}:
        _append_unique(
            fields,
            _field("decreto_numero", "Numero del decreto ingiuntivo"),
            _field("decreto_anno", "Anno del decreto ingiuntivo", "year"),
            _field("decreto_data", "Data del decreto ingiuntivo", "date"),
            _field("decreto_causa_numero", "Numero della causa collegata", required=False),
            _field("decreto_causa_anno", "Anno della causa collegata", "year", required=False),
        )
    if root_name == "RicorsoDecretoIngiuntivo":
        _append_unique(fields, _field("decreto_esecutivo", "Decreto immediatamente esecutivo", "boolean", required=False))

    if root_name in {
        "RicorsoSeparazione",
        "RicorsoDivorzio",
        "ModificaCondizioniSeparazione",
        "ModificaCondizioniDivorzio",
    }:
        marriage_group = "Dati del matrimonio"
        _append_unique(
            fields,
            _field("matrimonio_numero", "Numero atto", required=False, group=marriage_group),
            _field("matrimonio_registro", "Registro", required=False, group=marriage_group),
            _field("matrimonio_serie", "Serie", required=False, group=marriage_group),
            _field("matrimonio_citta", "Comune", required=False, group=marriage_group),
            _field("matrimonio_provincia", "Provincia", required=False, group=marriage_group),
            _field("matrimonio_data_celebrazione", "Data di celebrazione", "date", required=False, group=marriage_group),
        )
    if root_name in {"RicorsoDivorzio", "ModificaCondizioniSeparazione"}:
        _append_unique(
            fields,
            _field(
                "separazione_tipo",
                "Tipo di separazione",
                "select",
                options=(("consensuale", "Consensuale"), ("giudiziale", "Giudiziale")),
            ),
            _field("separazione_sentenza_numero", "Numero della sentenza di separazione", required=False),
            _field("separazione_sentenza_anno", "Anno della sentenza di separazione", "year", required=False),
        )
    if root_name == "ModificaCondizioniDivorzio":
        _append_unique(
            fields,
            _field("divorzio_sentenza_numero", "Numero della sentenza di divorzio"),
            _field("divorzio_sentenza_anno", "Anno della sentenza di divorzio", "year"),
        )
    if root_name == "Successioni":
        _append_unique(
            fields,
            _field("defunto_cognome", "Cognome del defunto"),
            _field("defunto_nome", "Nome del defunto"),
            _field(
                "testamento_tipo",
                "Testamento",
                "select",
                required=False,
                options=(("NonSpecificato", "Non specificato"), ("Olografo", "Olografo"), ("Pubblico", "Pubblico"), ("Segreto", "Segreto")),
            ),
        )
    if root_name == "RicorsoMinorenniSoggettoInteressato":
        _append_unique(
            fields,
            _field("soggetto_interessato_cognome", "Cognome del soggetto interessato"),
            _field("soggetto_interessato_nome", "Nome del soggetto interessato"),
        )
    if root_name in {"RicorsoImmigrazioneConvalida", "RicorsoReclamoSospensiva"}:
        _append_unique(
            fields,
            _field("cui", "Codice identificativo della persona"),
            _field("codice_vestanet", "Codice pratica", required=False),
            _field("nazione_provenienza", "Nazione di provenienza", required=False),
            _field("data_decreto_immigrazione", "Data del decreto", "date", required=False),
        )
        if root_name == "RicorsoReclamoSospensiva":
            _append_unique(
                fields,
                _field("precedente_provvedimento_numero", "Numero del provvedimento impugnato"),
                _field("precedente_provvedimento_anno", "Anno del provvedimento impugnato", "year"),
                _field("precedente_fascicolo_numero", "Numero del fascicolo precedente", required=False),
                _field("precedente_fascicolo_anno", "Anno del fascicolo precedente", "year", required=False),
            )

    if generator_class == "Introduttivi_SIGP" and root_name == "OSA":
        _append_unique(
            fields,
            _field("osa_numero_verbale", "Numero del verbale o della sanzione"),
            _field("osa_data_verbale", "Data del verbale o della sanzione", "date"),
            _field("osa_motivazione", "Motivazione", required=False),
        )
        if suffix == "OSA_CartellaEsattoriale":
            _append_unique(fields, _field("osa_riferimento_cartella", "Riferimento della cartella (17 caratteri)"))
        elif suffix == "OSA_IngiunzionePagamento":
            _append_unique(fields, _field("osa_riferimento_ordinanza", "Riferimento dell'ordinanza"))

    if root_name in {"AttoIntervento", "NotaPrecisazioneCredito"}:
        _append_unique(
            fields,
            _field("credito_capitale", "Capitale del credito", "currency"),
            _field("credito_importo", "Importo aggiornato", "currency", required=False),
            _field("credito_data_decorrenza", "Data di decorrenza del credito", "date"),
            _field("credito_data_aggiornamento", "Data di aggiornamento", "date", required=False),
        )
    if root_name == "Opposizione" and generator_class.startswith("ParteSiecic"):
        _append_unique(fields, _field("opposizione_istanza_sospensione", "È richiesta la sospensione", "boolean", required=False))

    if generator_class == "DelSiecicEsecuzioni":
        if root_name in {"MinutaDecreto", "AggiudicazioneLotto"} or suffix in {
            "avvisoVendita",
            "depositoPrezzo",
            "istanzaRevocaDecadenzaAggiudicatario",
            "verbaleAggiudicazione",
        }:
            _append_unique(fields, _field("lotto_numero", "Numero del lotto", "integer"))
        if root_name == "AggiudicazioneLotto":
            _append_unique(
                fields,
                _field("aggiudicazione_importo_aumento", "Importo minimo in aumento", "currency"),
                _field("aggiudicazione_importo_offerta", "Importo dell'offerta", "currency"),
                _field("aggiudicazione_cauzione", "Cauzione", "currency"),
                _field("aggiudicatario_cognome", "Cognome o denominazione dell'aggiudicatario"),
                _field("aggiudicatario_nome", "Nome dell'aggiudicatario", required=False),
                _field("aggiudicatario_codice_fiscale", "Codice fiscale dell'aggiudicatario"),
                _field("aggiudicazione_termine_conguaglio", "Termine per il conguaglio", "date"),
            )

    if generator_class == "IntroduttiviSiecicEsecuzioni" and root_name == "IscrizioneRuoloPignoramento":
        pign_group = "Dati del pignoramento"
        _append_unique(
            fields,
            _field("data_consegna_pignoramento", "Data di consegna del pignoramento", "date", group=pign_group),
            _field("importo_precetto", "Importo del precetto", "currency", group=pign_group),
            _field("data_notifica_precetto", "Data di notifica del precetto", "date", required=False, group=pign_group),
            _field("data_pignoramento", "Data del pignoramento", "date", group=pign_group),
            _field("stima_diritto", "Valore del diritto pignorato", "currency", group=pign_group),
            _field("cronologico_pignoramento", "Cronologico", required=False, group=pign_group),
            _field("beni_pignorati", "Beni pignorati", "beni-pignorati", group="Beni"),
            _field("titolo", "Titolo esecutivo", "titolo-esecutivo", group="Titolo"),
        )
        if "MobiliarePressoDebitore" in key:
            _append_unique(fields, _field("custode", "Custode", "persona-indirizzo", group="Custode"))
        elif "MobiliarePressoTerzi" in key:
            _append_unique(
                fields,
                _field("data_citazione", "Data di citazione del terzo", "date", group=pign_group),
                _field("terzi", "Terzi pignorati", "terzi-pignorati", group="Terzi"),
            )

    if generator_class == "IntroduttiviSiecicConcorsuali" and root_name.endswith("CCIPU"):
        ccipu_group = "Richieste al giudice"
        _append_unique(
            fields,
            _field("misure_cautelari", "Misure cautelari", "boolean", required=False, group=ccipu_group),
            _field("misure_protettive", "Misure protettive", "boolean", required=False, group=ccipu_group),
            _field(
                "gruppo_debitori",
                "Gruppo di debitori",
                "select",
                required=False,
                group=ccipu_group,
                options=(("", "Nessun gruppo"), ("GI", "Gruppo di imprese"), ("CF", "Crisi familiare")),
            ),
        )
        if root_name == "RicorsoAmmissConcordatoPreventivoCCIPU":
            _append_unique(
                fields,
                _field(
                    "tipo_concordato_ccipu",
                    "Tipo di concordato",
                    "select",
                    options=(("Ordinario", "Ordinario"), ("Bianco", "In bianco")),
                ),
            )

    if generator_class.startswith("ParteCassazione") and root_name in {
        "Ricorso",
        "ControRicorso",
        "ControRicorsoIncidentale",
    }:
        cass_group = "Dati del ricorso"
        _append_unique(
            fields,
            _field(
                "tipo_ricorso_cassazione",
                "Tipo di ricorso",
                "select",
                group=cass_group,
                options=(
                    ("RicorsoOrdinario", "Ricorso ordinario"),
                    ("RegolamentoDiCompetenza", "Regolamento di competenza"),
                    ("RegolamentoPreventivoDiGiurisdizione", "Regolamento di giurisdizione"),
                    ("RicorsoPerRevocazione", "Ricorso per revocazione"),
                    ("Ricorso_ex_art_348_TER", "Ricorso ex art. 348-ter"),
                ),
            ),
            _field("data_richiesta_notifica_cassazione", "Data della prima notifica", "date", group=cass_group),
            _field("data_effettiva_notifica_cassazione", "Data di perfezionamento dell'ultima notifica", "date", required=False, group=cass_group),
            _field("materia_ricorso_cassazione", "Materia del ricorso", "cassazione-materia", group=cass_group),
            _field("parole_chiave_cassazione", "Parole chiave", required=False, group=cass_group),
            _field("provvedimento_impugnato", "Provvedimento impugnato", "provvedimento-cassazione", group="Provvedimento impugnato"),
        )
        if root_name == "Ricorso":
            _append_unique(
                fields,
                _field("inizio_primo_grado_anno", "Anno di inizio del primo grado", "year", group=cass_group),
                _field("inizio_primo_grado_ufficio", "Ufficio del primo grado", group=cass_group),
            )
        if root_name in {"Ricorso", "ControRicorsoIncidentale"}:
            _append_unique(fields, _field("motivi_cassazione", "Motivi", "motivi-cassazione", group="Motivi"))
        if root_name in {"ControRicorso", "ControRicorsoIncidentale"}:
            _append_unique(fields, _field("contromotivi_cassazione", "Contromotivi", "contromotivi-cassazione", group="Contromotivi"))

    return fields


@lru_cache(maxsize=1)
def cassazione_materie_options() -> list[dict[str, str]]:
    xsd = (
        Path(__file__).resolve().parents[1]
        / "docs/specs/ministero/parte/base_v13/tipi-base.xsd"
    )
    if not xsd.is_file():
        return []
    try:
        root = etree.parse(str(xsd)).getroot()
    except (OSError, etree.XMLSyntaxError):
        return []
    ns = {"xs": "http://www.w3.org/2001/XMLSchema"}
    values = root.xpath("./xs:simpleType[@name='MaterieRicorso']/xs:restriction/xs:enumeration", namespaces=ns)
    options: list[dict[str, str]] = []
    for node in values:
        value = str(node.get("value") or "").strip()
        label_parts = [
            " ".join(str(text).split())
            for text in node.xpath("./xs:annotation/xs:documentation//text()", namespaces=ns)
            if str(text).strip()
        ]
        if value:
            options.append({"value": value, "label": label_parts[0] if label_parts else value})
    return options


@lru_cache(maxsize=1)
def classi_immobiliari_options() -> list[dict[str, str]]:
    xsd = (
        Path(__file__).resolve().parents[1]
        / "docs/specs/ministero/xsd/2026-05-12-sici/XSD_SICI_20260508/XSD_SICI_20260508/Atti/sici/enum/tipi-enum-siecic.xsd"
    )
    if not xsd.is_file():
        return []
    try:
        root = etree.parse(str(xsd)).getroot()
    except (OSError, etree.XMLSyntaxError):
        return []
    ns = {"xs": "http://www.w3.org/2001/XMLSchema"}
    values = root.xpath(
        "./xs:simpleType[@name='TipologiaClasseImmobiliare']/xs:restriction/xs:enumeration",
        namespaces=ns,
    )
    options: list[dict[str, str]] = []
    for node in values:
        value = str(node.get("value") or "").strip()
        documentation = " ".join(
            " ".join(str(text).split())
            for text in node.xpath("./xs:annotation/xs:documentation//text()", namespaces=ns)
            if str(text).strip()
        ).strip()
        if value:
            options.append({"value": value, "label": f"{value} - {documentation}" if documentation else value})
    return options


def datiatto_reference_data() -> dict[str, Any]:
    return {
        "titoliEsecutivi": [{"value": value, "label": label} for value, label in TITLE_OPTIONS],
        "ruoliProvvedimentoCassazione": [
            {"value": value, "label": label} for value, label in CASSAZIONE_ROLE_OPTIONS
        ],
        "materieCassazione": cassazione_materie_options(),
        "classiImmobiliari": classi_immobiliari_options(),
    }
