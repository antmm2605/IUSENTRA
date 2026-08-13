"""Campi operativi richiesti dai generatori ministeriali di deposito."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from lxml import etree

from pct.deposito_studio_telematico_contract import studio_telematico_type_contract


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

DEPOSITO_PROFESSIONISTA_ROLE_OPTIONS = (
    ("ARCH.", "Arch."),
    ("AVV.", "Avv."),
    ("CAV.", "Cav."),
    ("CTU", "Consulente"),
    ("CUR", "Curatore"),
    ("CUS", "Custode"),
    ("DR.", "Dr."),
    ("DOTT.", "Dott."),
    ("GEOM.", "Geom."),
    ("ING.", "Ing."),
    ("NOT", "Notaio"),
    ("ON.", "On."),
    ("CTU", "Perito"),
    ("P.M.", "P.M."),
    ("PROF.", "Prof."),
    ("RAG.", "Rag."),
    ("REV.", "Rev."),
    ("SIG.", "Sig."),
    ("SOC.", "Soc."),
    ("TUT", "Tutore"),
)

DEPOSITO_PROFESSIONISTA_CASSAZIONE_ROLE_OPTIONS = (
    ("SOLODIFENSORE", "Avvocato (solo difensore)"),
    ("DIFENSOREDOMICILIATARIO", "Avvocato (difensore e domiciliatario)"),
)


def deposito_professionista_role_options(tipo_deposito_key: str = "") -> tuple[tuple[str, str], ...]:
    if str(tipo_deposito_key or "").strip().startswith("Parte_CASSAZIONE::"):
        return DEPOSITO_PROFESSIONISTA_CASSAZIONE_ROLE_OPTIONS
    return DEPOSITO_PROFESSIONISTA_ROLE_OPTIONS


def normalize_deposito_professionista_role(value: Any, tipo_deposito_key: str = "") -> str:
    normalized = str(value or "").strip()
    allowed = {option_value for option_value, _label in deposito_professionista_role_options(tipo_deposito_key)}
    return normalized if normalized in allowed else ""

PAYMENT_MODE_OPTIONS = (
    ("NonDovuto", "Non dovuto"),
    ("Esente", "Esente"),
    ("ADebito", "Prenotato a debito"),
    ("Pagato", "Pagato"),
)

SUCCESSION_ACT_OPTIONS = (
    ("AttoGiudiziario", "Atto giudiziario"),
    ("AttoNotarile", "Atto notarile"),
    ("Dichiarazione", "Dichiarazione"),
    ("Istanza", "Istanza"),
    ("Segnalazione", "Segnalazione"),
    ("Altro", "Altro"),
)

SUCCESSION_PART_OPTIONS = (
    ("Proprio", "In proprio"),
    ("ProprioQualita", "In proprio e nella qualita'"),
    ("Qualita", "Nella qualita'"),
)

SUCCESSION_QUALITY_OPTIONS = (
    ("AmministratoreDiSostegno", "Amministratore di sostegno"),
    ("Curatore", "Curatore"),
    ("CuratoreSpeciale", "Curatore speciale"),
    ("Genitore", "Genitore"),
    ("ProcuratoreSpeciale", "Procuratore speciale"),
    ("Tutore", "Tutore"),
)

CASSAZIONE_JUSTICE_EXPENSE_KEYS = {
    "Parte_CASSAZIONE::Ricorso",
    "Parte_CASSAZIONE::ControRicorso",
    "Parte_CASSAZIONE::ControRicorsoIscrittoDalControricorrente",
    "Parte_CASSAZIONE::ControRicorsoIncidentale",
    "Parte_CASSAZIONE::ControRicorsoIncidentaleIscrittoDalControricorrente",
    "Parte_CASSAZIONE::IntegrazioneContradittorio",
    "Parte_CASSAZIONE::IntegrazioneSpeseGiustizia",
}


def _append_payment_branch(fields: list[dict[str, Any]], prefix: str, label: str) -> None:
    group = "Spese di giustizia"
    _append_unique(
        fields,
        _field(f"{prefix}_importo", f"Importo {label}", "currency", required=False, group=group),
        _field(
            f"{prefix}_tipo_pagamento",
            f"Pagamento {label}",
            "select",
            required=False,
            group=group,
            options=PAYMENT_MODE_OPTIONS,
        ),
        _field(
            f"{prefix}_ricevuta",
            f"Ricevuta {label}",
            "document-reference",
            required=False,
            group=group,
            note="Richiesta solo quando il pagamento è dovuto e non risulta esente o prenotato a debito.",
        ),
    )


def datiatto_input_fields(catalog_key: str, generator_class: str, root_name: str) -> list[dict[str, Any]]:
    """Restituisce solo i campi pertinenti al tipo di deposito selezionato."""

    key = str(catalog_key or "")
    suffix = key.rsplit("::", 1)[-1]
    fields: list[dict[str, Any]] = []
    contract = studio_telematico_type_contract(key) or {}
    controls = contract.get("controls") if isinstance(contract.get("controls"), dict) else {}

    def enabled(control: str) -> bool:
        state = controls.get(control)
        return isinstance(state, dict) and str(state.get("Enabled") or "").casefold() == "true"

    common_group = "Dati richiesti dal tipo di deposito"
    if enabled("txtCCI"):
        _append_unique(fields, _field("cci", "Numero Codice della crisi d'impresa (CCI)", "integer", required=False, group=common_group))
    if enabled("txtSub_Procedimento"):
        _append_unique(fields, _field("sub_procedimento", "Sub-procedimento", "integer", required=False, group=common_group))
    if enabled("cboRito"):
        _append_unique(fields, _field("rito", "Rito", group=common_group))
    if enabled("cboRiferimentoProvvedimento"):
        _append_unique(fields, _field("precedente_provvedimento_tipo", "Tipologia del provvedimento", group=common_group))
    if enabled("txtRiferimentoProvvedimentoNumero"):
        _append_unique(fields, _field("precedente_provvedimento_numero", "Numero del provvedimento", group=common_group))
    if enabled("dtpDataPrecedenteProvvedimento"):
        _append_unique(fields, _field("data_precedente_provvedimento", "Data del provvedimento", "date", group=common_group))
    if enabled("cboPrecedenteFascicolo"):
        _append_unique(fields, _field("precedente_fascicolo_ufficio", "Ufficio del fascicolo precedente", group=common_group))
    if enabled("txtPrecedenteFascicoloNumero"):
        _append_unique(fields, _field("precedente_fascicolo_numero", "Numero del fascicolo precedente", group=common_group))
    if enabled("txtPrecedenteFascicoloAnno"):
        _append_unique(fields, _field("precedente_fascicolo_anno", "Anno del fascicolo precedente", "year", group=common_group))
    if enabled("cboIstanze"):
        _append_unique(fields, _field("istanza", "Istanza", group=common_group))
    if enabled("dtpDataAttoDaDepositare"):
        _append_unique(fields, _field("data_atto_deposito", "Data dell'atto", "date", group=common_group))

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
        succession_group = "Eredita' e successioni"
        deceased_group = "Dati del defunto"
        testament_group = "Dati del testamento"
        _append_unique(
            fields,
            _field("successione_parte_istante", "Nome o denominazione della parte istante", group=succession_group),
            _field(
                "successione_parte_agisce",
                "La parte agisce",
                "select",
                group=succession_group,
                options=SUCCESSION_PART_OPTIONS,
            ),
            _field(
                "successione_qualita",
                "Qualita' della parte",
                "select",
                required=False,
                group=succession_group,
                options=SUCCESSION_QUALITY_OPTIONS,
            ),
            _field(
                "successione_tipo_atto",
                "Atto introduttivo della successione",
                "select",
                group=succession_group,
                options=SUCCESSION_ACT_OPTIONS,
            ),
            _field("defunto_cognome", "Cognome del defunto", group=deceased_group),
            _field("defunto_nome", "Nome del defunto", group=deceased_group),
            _field("defunto_codice_fiscale", "Codice fiscale del defunto", group=deceased_group),
            _field("defunto_data_nascita", "Data di nascita del defunto", "date", required=False, group=deceased_group),
            _field("defunto_data_decesso", "Data del decesso", "date", required=False, group=deceased_group),
            _field("defunto_luogo_decesso", "Luogo del decesso", required=False, group=deceased_group),
            _field("defunto_indirizzo", "Ultimo domicilio - indirizzo", required=False, group=deceased_group),
            _field("defunto_civico", "Ultimo domicilio - civico", required=False, group=deceased_group),
            _field("defunto_cap", "Ultimo domicilio - CAP", required=False, group=deceased_group),
            _field("defunto_citta", "Ultimo domicilio - citta'", required=False, group=deceased_group),
            _field(
                "testamento_tipo",
                "Tipo di testamento",
                "select",
                group=testament_group,
                options=(("NonSpecificato", "Non specificato"), ("Olografo", "Olografo"), ("Pubblico", "Pubblico"), ("Segreto", "Segreto"), ("AB", "AB")),
            ),
            _field("testamento_notaio", "Notaio", required=False, group=testament_group),
            _field("testamento_numero_repertorio", "Numero repertorio", "integer", required=False, group=testament_group),
            _field("testamento_ufficio_registrazione", "Ufficio di registrazione", required=False, group=testament_group),
            _field("testamento_numero_registrazione", "Numero registrazione", "integer", required=False, group=testament_group),
            _field("testamento_data_pubblicazione", "Data pubblicazione", "date", required=False, group=testament_group),
            _field("testamento_data", "Data testamento", "date", required=False, group=testament_group),
            _field("testamento_data_registrazione", "Data registrazione", "date", required=False, group=testament_group),
            _field("verbalizzazione_cancelliere", "Cancelliere della verbalizzazione", required=False, group=succession_group),
            _field("verbalizzazione_data", "Data verbalizzazione", "date", required=False, group=succession_group),
            _field("inventario_data_deposito", "Data deposito inventario", "date", required=False, group=succession_group),
            _field("inventario_data_compimento", "Data compimento inventario", "date", required=False, group=succession_group),
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
                _field("data_notifica_pignoramento", "Data di notifica del pignoramento", "date", group=pign_group),
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
            _field("data_effettiva_notifica_cassazione", "Data di perfezionamento dell'ultima notifica", "date", group=cass_group),
            _field("materia_ricorso_cassazione", "Materia del ricorso", "cassazione-materia", group=cass_group),
            _field("parole_chiave_cassazione", "Parole chiave", group=cass_group),
            _field("provvedimento_impugnato", "Provvedimento impugnato", "provvedimento-cassazione", group="Provvedimento impugnato"),
        )
        if root_name in {"Ricorso", "ControRicorso", "ControRicorsoIncidentale"}:
            _append_unique(
                fields,
                _field("inizio_primo_grado_anno", "Anno di inizio del primo grado", "year", group=cass_group),
                _field("inizio_primo_grado_ufficio", "Ufficio del primo grado", group=cass_group),
            )
        if root_name in {"Ricorso", "ControRicorsoIncidentale"}:
            _append_unique(fields, _field("motivi_cassazione", "Motivi", "motivi-cassazione", group="Motivi"))
        if root_name in {"ControRicorso", "ControRicorsoIncidentale"}:
            _append_unique(fields, _field("contromotivi_cassazione", "Contromotivi", "contromotivi-cassazione", group="Contromotivi"))

    if key in CASSAZIONE_JUSTICE_EXPENSE_KEYS:
        _append_payment_branch(fields, "spese_integrazione_art13", "integrazione ex art. 13, comma 2-bis, T.U.")
        _append_payment_branch(fields, "spese_diritti_art30", "diritti di registrazione a ruolo ex art. 30 T.U.")
        _append_payment_branch(fields, "spese_notifica_art34", "notifica avvocati ex art. 34 T.U.")

    if key == "Introduttivi_CONCORSUALI_SIECIC::RicorsoLiquidazioneControllataCCIPUIstanzaCreditore":
        organ_group = "Organo di gestione della crisi"
        occ_group = "Referente OCC"
        _append_unique(
            fields,
            _field("organo_crisi_tipo", "Tipo organo", "select", group=organ_group, options=(("OCC", "OCC"), ("Gestore", "Gestore della crisi"), ("Altro", "Altro"))),
            _field("organo_crisi_natura_giuridica", "Natura giuridica", "select", group=organ_group, options=(("PFI", "Persona fisica"), ("PGI", "Persona giuridica"), ("PAM", "Pubblica amministrazione"))),
            _field("organo_crisi_denominazione", "Cognome o denominazione", group=organ_group),
            _field("organo_crisi_codice_fiscale", "Codice fiscale", group=organ_group),
            _field("occ_referente_presente", "Referente OCC presente", "boolean", required=False, group=occ_group),
            _field("occ_referente_qualifica", "Qualifica referente OCC", "select", required=False, group=occ_group, options=(("Referente", "Referente"), ("Gestore", "Gestore"), ("Altro", "Altro"))),
            _field("occ_referente_natura_giuridica", "Natura giuridica referente OCC", "select", required=False, group=occ_group, options=(("PFI", "Persona fisica"), ("PGI", "Persona giuridica"), ("PAM", "Pubblica amministrazione"))),
            _field("occ_referente_denominazione", "Cognome o denominazione referente OCC", required=False, group=occ_group),
            _field("occ_referente_codice_fiscale", "Codice fiscale referente OCC", required=False, group=occ_group),
        )

    if generator_class == "UNEP":
        unep_group = "Dati UNEP"
        cause_group = "Riferimento del procedimento UNEP"
        controls = contract.get("controls") if isinstance(contract.get("controls"), dict) else {}
        natura_state = controls.get("cboCodiciNaturaUNEP") if isinstance(controls.get("cboCodiciNaturaUNEP"), dict) else {}
        natura_visible = str(natura_state.get("Visible") or "").casefold() == "true"
        natura_enabled = str(natura_state.get("Enabled") or "true").casefold() == "true"

        def append_cause_fields(*, required: bool) -> None:
            _append_unique(
                fields,
                _field("unep_causa_ufficio", "Ufficio del procedimento", required=required, group=cause_group),
                _field("unep_causa_numero", "Numero R.G. del procedimento", required=required, group=cause_group),
                _field("unep_causa_sub", "Sub-procedimento", "integer", required=False, group=cause_group),
                _field("unep_causa_cci", "Numero CCI", "integer", required=False, group=cause_group),
                _field("unep_causa_anno", "Anno del procedimento", "year", required=required, group=cause_group),
                _field("unep_causa_data_udienza", "Data dell'udienza", "date", required=required, group=cause_group),
            )

        if natura_visible and natura_enabled:
            _append_unique(
                fields,
                _field("unep_natura_atto", "Natura del deposito UNEP", group=unep_group),
                _field(
                    "unep_codice_natura",
                    "Codice natura UNEP",
                    required=not suffix.startswith("PagamentoRichiesta"),
                    group=unep_group,
                ),
            )
        if suffix.startswith("Atto"):
            _append_unique(
                fields,
                _field("unep_data_richiesta", "Data della richiesta di notifica", "date", group=unep_group),
                _field("unep_data_scadenza", "Data di scadenza della notifica", "date", group=unep_group),
                _field(
                    "unep_destinatari",
                    "Destinatari e tipologia di notifica",
                    "unep-destinatari",
                    required=False,
                    group=unep_group,
                ),
            )
        if suffix in {"AttoEsenteLavoro", "AttoCivileDebito", "AttoPenaleDebito"}:
            append_cause_fields(required=True)
        if suffix.endswith("Debito"):
            _append_unique(
                fields,
                _field("unep_ente_debito", "Ente concedente il debito", group=unep_group),
                _field("unep_numero_debito", "Numero della concessione a debito", group=unep_group),
                _field("unep_data_debito", "Data della concessione a debito", "date", group=unep_group),
            )
        if suffix.startswith("PagamentoRichiesta"):
            _append_unique(fields, _field("unep_codice_pagamento", "Codice di pagamento", group=unep_group))
        if suffix == "RichiestaRestituzioneSomme":
            _append_unique(
                fields,
                _field("unep_codice_pagamento", "Codice di pagamento", group=unep_group),
                _field("unep_registro_bilancio", "Numero registro del bilancio UNEP", group=unep_group),
                _field("unep_anno_bilancio", "Anno del bilancio UNEP", "year", group=unep_group),
                _field("unep_iban", "IBAN per la restituzione", group=unep_group),
            )
        if suffix.startswith("RichiestaPignoramento"):
            source_blocks_missing_assets = (
                "Mobiliare" in suffix
                or "PressoTerzi" in suffix
                or suffix in {"RichiestaPignoramentoImmobiliare", "RichiestaPignoramentoImmobiliareADebito"}
            )
            _append_unique(
                fields,
                _field("unep_inoltro_ufficiale_giudiziario", "Sede dell'ufficiale giudiziario", group=unep_group),
                _field("unep_importo_precetto", "Importo dell'atto di precetto", "currency", required=False, group=unep_group),
                _field("unep_destinatari", "Debitori e dati di notifica del precetto", "unep-destinatari", required=False, group=unep_group),
                _field("unep_titoli", "Titolo del procedente", "unep-titoli", group=unep_group),
                _field(
                    "unep_beni",
                    "Beni da pignorare e diritti reali",
                    "beni-pignorati-unep",
                    required=source_blocks_missing_assets,
                    group=unep_group,
                ),
            )
            if "PressoTerzi" in suffix:
                _append_unique(
                    fields,
                    _field("unep_terzi", "Terzi pignorati", "unep-terzi", required=False, group=unep_group),
                )
            append_cause_fields(required=suffix.endswith("MateriaLavoro") or suffix.endswith("ADebito"))
        if suffix == "RichiestaRicercaBeni":
            _append_unique(
                fields,
                _field("unep_inoltro_ufficiale_giudiziario", "Sede dell'ufficiale giudiziario", group=unep_group),
                _field("unep_autorita_tipo", "Autorita' che ha autorizzato la ricerca", group=unep_group),
                _field("unep_autorita_sede", "Sede dell'autorita'", group=unep_group),
                _field("unep_autorizzazione_numero", "Numero autorizzazione", group=unep_group),
                _field("unep_autorizzazione_data", "Data autorizzazione", "date", group=unep_group),
                _field("unep_data_notifica_precetto", "Data notifica dell'atto di precetto", "date", required=False, group=unep_group),
                _field("unep_importo_precetto", "Importo dell'atto di precetto", "currency", required=False, group=unep_group),
            )

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
        "qualificheProfessionista": [
            {"value": value, "label": label}
            for value, label in DEPOSITO_PROFESSIONISTA_ROLE_OPTIONS
        ],
        "qualificheProfessionistaCassazione": [
            {"value": value, "label": label}
            for value, label in DEPOSITO_PROFESSIONISTA_CASSAZIONE_ROLE_OPTIONS
        ],
        "titoliEsecutivi": [{"value": value, "label": label} for value, label in TITLE_OPTIONS],
        "ruoliProvvedimentoCassazione": [
            {"value": value, "label": label} for value, label in CASSAZIONE_ROLE_OPTIONS
        ],
        "materieCassazione": cassazione_materie_options(),
        "classiImmobiliari": classi_immobiliari_options(),
    }
