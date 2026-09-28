"""Catalogo operativo PAT/SIGA per il Portale Avvocato.

La fonte primaria resta la documentazione ufficiale della Giustizia
Amministrativa: questo modulo contiene solo metadati e regole di scelta usati
da IUSENTRA per guidare l'avvocato verso Formweb e i moduli PDF ufficiali.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

DOCUMENTATION_URL = "https://www.giustizia-amministrativa.it/documentazione-operativa-e-modulistica"
PORTALE_AVVOCATO_URL = "https://pe.prod.cloud.giustizia-amministrativa.it"
PORTALE_AVVOCATO_INFO_URL = "https://www.giustizia-amministrativa.it/portale-avvocato"
FAQ_NUOVO_PORTALE_URL = "https://www.giustizia-amministrativa.it/faq-nuovo-portale"
PROCESSO_AMMINISTRATIVO_URL = "https://www.giustizia-amministrativa.it/processo-amministrativo-telematico"
NTO_FORMWEB_URL = (
    "https://www.giustizia-amministrativa.it/documents/20142/74204502/"
    "pubblicazione%2BNTO%2Bdel%2BPAT%2BPortale%2Bavvocato-def.pdf/"
    "9cbe814a-21fa-2c0c-4fb6-ac775e9f8225?t=1754059365413"
)
MANUALE_AVVOCATO_URL = (
    "https://www.giustizia-amministrativa.it/documents/20142/98875166/"
    "Manuale_Avvocato_18.07.2026.pdf/1fad3004-f904-2fad-8e16-557bcf16434f?t=1784305133558"
)
ISTRUZIONI_COMPILAZIONE_MODULI_URL = (
    "https://www.giustizia-amministrativa.it/documents/20142/98875166/"
    "PAT%2BIstruzioni%2Bper%2BCompilazione%2BModuli%2BDeposito%2Bv9.6.2.pdf/"
    "da357453-5de2-0402-9748-5c27777884e2?t=1784305138566"
)
AGGIORNAMENTO_MODULI_URL = (
    "https://www.giustizia-amministrativa.it/documents/20142/98875166/"
    "Aggiornamento%2Bmoduli%2Bdi%2Bdeposito_v.18.07.2026.pdf/"
    "d340b5c7-35f7-6e39-8ed3-80eb3ec7359c?t=1784305132562"
)
GUIDA_FIRMA_READER_URL = (
    "https://www.giustizia-amministrativa.it/documents/20142/46830/"
    "nsiga_4155421.pdf/1b2eac21-0c92-c73a-d56b-ce44f736dfcc?t=1532445632000"
)
ISTRUZIONI_DOWNLOAD_PDF_URL = (
    "https://www.giustizia-amministrativa.it/documents/20142/22698058/"
    "Impostazione%2Bin%2Bchrome%2Bper%2Bdownload%2Bpdf.pdf/"
    "c15e8619-c90e-b60c-0454-676eea6c1889?t=1652785121000"
)
ISTRUZIONI_INVIO_MODULI_URL = (
    "https://www.giustizia-amministrativa.it/documents/20142/2140648/"
    "PAT_Istruzioni_per_Invio_Moduli_di_Deposito_v30.pdf/"
    "cd7ee536-d869-bb74-3e83-9c9fe1d09ceb?t=1608306620000"
)
REQUISITI_TECNICI_URL = (
    "https://www.giustizia-amministrativa.it/documents/20142/378005/"
    "Requisiti%2Bed%2BInfo%2Btecnici%2Bper%2Bavvocati.pdf/"
    "de700f16-6f10-db6f-6187-7eb7d8e1ad5e?t=1570643179000"
)
INDIRIZZI_PEC_PAT_URL = (
    "https://www.giustizia-amministrativa.it/documents/20142/46830/"
    "nsiga_4148489.pdf/b423693d-4fad-1dc0-dfe2-4aa9ba395673?t=1528734009000"
)


@dataclass(frozen=True, slots=True)
class PatOfficialDocument:
    id: str
    title: str
    url: str
    kind: str
    updated: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class PatModule:
    id: str
    title: str
    version: str
    url: str
    formweb_types: tuple[str, ...]
    recommended_for: tuple[str, ...]
    required_data: tuple[str, ...]
    attachments: tuple[str, ...]
    fillable_fields: tuple["PatModuleField", ...]
    keywords: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True, slots=True)
class PatModuleField:
    id: str
    label: str
    type: str
    required: bool = True
    placeholder: str = ""
    help: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PatFormwebDeposit:
    id: str
    title: str
    module_id: str
    steps: str
    mandatory_focus: tuple[str, ...]
    produces: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PatWorkflowStep:
    id: str
    title: str
    body: str
    actions: tuple[str, ...] = field(default_factory=tuple)


COMMON_MODULE_FIELDS: tuple[PatModuleField, ...] = (
    PatModuleField("sede", "Sede TAR / CDS / CGARS", "text", True, "TAR Lazio - Roma"),
    PatModuleField("parte_depositante", "Parte depositante", "text", True, "Nome parte o difensore"),
    PatModuleField("codice_fiscale", "Codice fiscale / partita IVA", "text", False, "CF o P.IVA"),
    PatModuleField("oggetto", "Oggetto sintetico", "textarea", True, "Sintesi chiara dell'atto o della richiesta"),
)

RG_MODULE_FIELDS: tuple[PatModuleField, ...] = (
    PatModuleField("nrg", "Numero RG / NRG", "text", True, "1234"),
    PatModuleField("anno_rg", "Anno RG", "text", True, "2026"),
)

RICORSO_MODULE_FIELDS: tuple[PatModuleField, ...] = COMMON_MODULE_FIELDS + (
    PatModuleField("tipo_ricorso", "Tipo ricorso", "select", True, options=("Ordinario", "Appalti", "Accesso", "Silenzio", "Ottemperanza", "Rito sportivo", "PNRR")),
    PatModuleField("ricorrente", "Ricorrente", "text", True, "Nome o denominazione ricorrente"),
    PatModuleField("resistente", "Amministrazione resistente", "text", True, "Amministrazione o controparte"),
    PatModuleField("contributo_unificato", "Contributo unificato", "select", True, options=("Da pagare", "Pagato", "Esente", "Prenotato a debito")),
)

ATTO_MODULE_FIELDS: tuple[PatModuleField, ...] = COMMON_MODULE_FIELDS + RG_MODULE_FIELDS + (
    PatModuleField("tipologia_atto", "Tipologia atto", "select", True, options=("Memoria", "Replica", "Motivi aggiunti", "Istanza cautelare", "Documenti", "Notifiche", "Altro atto")),
    PatModuleField("descrizione_allegati", "Descrizione allegati", "textarea", False, "Elenco sintetico dei documenti depositati"),
)

SEGRETERIA_MODULE_FIELDS: tuple[PatModuleField, ...] = COMMON_MODULE_FIELDS + (
    PatModuleField("riferimento_fascicolo", "Riferimento fascicolo", "text", False, "NRG, protocollo o altro riferimento"),
    PatModuleField("tipo_richiesta", "Tipo richiesta", "select", True, options=("Rilascio copie", "Comunicazione", "Istanza amministrativa", "Correzione dati", "Altro")),
    PatModuleField("dettaglio_richiesta", "Dettaglio richiesta", "textarea", True, "Cosa deve fare la segreteria"),
)

AUSILIARI_MODULE_FIELDS: tuple[PatModuleField, ...] = COMMON_MODULE_FIELDS + RG_MODULE_FIELDS + (
    PatModuleField("qualifica_depositante", "Qualifica depositante", "select", True, options=("Ausiliario del giudice", "Commissario", "CTU", "Parte non rituale", "Altro")),
    PatModuleField("descrizione_deposito", "Descrizione deposito", "textarea", True, "Relazione, istanza o documento prodotto"),
)

ANTE_CAUSAM_MODULE_FIELDS: tuple[PatModuleField, ...] = COMMON_MODULE_FIELDS + (
    PatModuleField("istante", "Istante", "text", True, "Nome o denominazione istante"),
    PatModuleField("amministrazione_resistente", "Amministrazione resistente", "text", True, "Amministrazione destinataria"),
    PatModuleField("ragioni_urgenza", "Ragioni di urgenza", "textarea", True, "Fatti e ragioni della misura richiesta"),
)

RIMBORSO_MODULE_FIELDS: tuple[PatModuleField, ...] = COMMON_MODULE_FIELDS + RG_MODULE_FIELDS + (
    PatModuleField("dati_pagamento", "Dati pagamento", "textarea", True, "IUV, F24, data, importo o ricevuta"),
    PatModuleField("iban", "IBAN o dati rimborso", "text", False, "IBAN intestato al richiedente"),
    PatModuleField("motivo_rimborso", "Motivo rimborso", "textarea", True, "Pagamento non dovuto, doppio pagamento o altra ragione"),
)

PARTI_EXCEL_FIELDS: tuple[PatModuleField, ...] = (
    PatModuleField("ruolo_processuale", "Ruolo processuale", "select", True, options=("Ricorrente", "Resistente", "Controinteressato", "Interveniente", "Altro")),
    PatModuleField("nome_parte", "Cognome, nome o denominazione", "text", True, "Parte da inserire"),
    PatModuleField("codice_fiscale", "Codice fiscale / partita IVA", "text", False, "CF o P.IVA"),
    PatModuleField("pec", "PEC o domicilio digitale", "text", False, "indirizzo@pec.it"),
    PatModuleField("note", "Note parte", "textarea", False, "Qualifica, rappresentante, riferimenti"),
)


OFFICIAL_DOCUMENTS: tuple[PatOfficialDocument, ...] = (
    PatOfficialDocument(
        "documentazione-operativa",
        "Documentazione operativa, modulistica e manualistica",
        DOCUMENTATION_URL,
        "indice ufficiale",
        "pagina corrente",
        "Pagina ufficiale da cui IUSENTRA ricava link e versioni dei moduli.",
    ),
    PatOfficialDocument(
        "manuale-avvocato",
        "Manuale avvocato Portali esterni nuovo SIGA-PAT",
        MANUALE_AVVOCATO_URL,
        "manuale",
        "18 luglio 2026",
    ),
    PatOfficialDocument(
        "nuove-regole-formweb",
        "Nuove regole tecnico-operative PAT e Formweb",
        NTO_FORMWEB_URL,
        "regole operative",
        "2025",
    ),
    PatOfficialDocument(
        "compilazione-moduli",
        "Istruzioni per la compilazione dei moduli di deposito",
        ISTRUZIONI_COMPILAZIONE_MODULI_URL,
        "istruzioni",
        "18 luglio 2026 (v9.6.2)",
    ),
    PatOfficialDocument(
        "aggiornamento-moduli",
        "Aggiornamento moduli di deposito (moduli 4.x del 18/07/2026)",
        AGGIORNAMENTO_MODULI_URL,
        "novità",
        "18 luglio 2026",
        "PEC della parte fino a 100 caratteri, procura sempre allegata, vincolo antistatario, nomi dei file allegati.",
    ),
    PatOfficialDocument(
        "firma-reader",
        "Guida alla configurazione di Acrobat Reader DC per la firma digitale",
        GUIDA_FIRMA_READER_URL,
        "firma",
        "documento ufficiale",
        "La firma PAdES si appone in Adobe Reader sul campo firma del modulo, che prima esegue i controlli bloccanti.",
    ),
    PatOfficialDocument(
        "download-pdf",
        "Istruzioni per il download dei PDF con Chrome",
        ISTRUZIONI_DOWNLOAD_PDF_URL,
        "istruzioni",
        "documento ufficiale",
    ),
    PatOfficialDocument(
        "requisiti-tecnici",
        "Requisiti tecnici per avvocati difensori e cittadini",
        REQUISITI_TECNICI_URL,
        "requisiti",
        "documento ufficiale",
    ),
)


PAT_MODULES: tuple[PatModule, ...] = (
    PatModule(
        "deposito_ricorso",
        "Modulo PDF deposito ricorso",
        "4.03",
        "https://www.giustizia-amministrativa.it/documents/20142/98875166/"
        "ModuloDepositoRicorso_4.03.pdf/4d8eef6c-61fc-0fd7-c66e-f382bf44c734?t=1784305137463",
        ("ricorso",),
        ("ricorso introduttivo", "appalti", "PNRR", "rito sportivo", "accesso", "silenzio", "ottemperanza"),
        ("sede TAR/CDS/CGARS", "tipo ricorso", "ricorrente", "resistente", "oggetto", "procura", "contributo unificato"),
        ("ricorso", "procura alle liti", "notifiche", "documenti", "ricevuta contributo unificato"),
        RICORSO_MODULE_FIELDS,
        ("ricorso", "appalto", "appalti", "cig", "pnrr", "accesso", "silenzio", "ottemperanza", "sportivo"),
        "IUSENTRA compila direttamente il modello ministeriale XFA 4.03 (18/07/2026); gli allegati restano file separati pronti per Formweb.",
    ),
    PatModule(
        "deposito_atto",
        "Modulo PDF deposito atto",
        "4.03",
        "https://www.giustizia-amministrativa.it/documents/20142/98875166/"
        "ModuloDepositoAtto_4.03.pdf/224d37c5-2068-2e1a-7478-8dc49c893410?t=1784305134980",
        ("atto_successivo", "documento_successivo", "istanze_al_giudice", "successivo_notifiche"),
        ("atto successivo", "memoria", "replica", "motivi aggiunti", "istanza cautelare", "documenti successivi"),
        ("sede", "NRG", "anno", "parte depositante", "tipologia atto", "oggetto sintetico"),
        ("atto principale", "documenti", "prove", "relata o notifiche", "ricevute"),
        ATTO_MODULE_FIELDS,
        ("atto", "memoria", "replica", "motivi aggiunti", "istanza", "cautelare", "documento", "notifiche"),
    ),
    PatModule(
        "richieste_segreteria",
        "Modulo PDF deposito richieste segreteria",
        "4.02",
        "https://www.giustizia-amministrativa.it/documents/20142/98875166/"
        "ModuloDepositoRichiesteSegreteria_4.02.pdf/7dc1094d-ad8e-ab78-816a-0becaf2f2d09?t=1784305136921",
        ("richieste_alla_segreteria",),
        ("richieste alla segreteria", "istanze amministrative al fascicolo", "accesso copie"),
        ("sede", "NRG o riferimento", "richiedente", "oggetto richiesta"),
        ("istanza", "documenti a supporto"),
        SEGRETERIA_MODULE_FIELDS,
        ("segreteria", "copie", "richiesta", "rilascio", "comunicazione"),
    ),
    PatModule(
        "ausiliari_parti_non_rituali",
        "Modulo PDF deposito ausiliari del giudice e parti non rituali",
        "4.02",
        "https://www.giustizia-amministrativa.it/documents/20142/98875166/"
        "ModuloDepositoPerAusiliariDelGiudiceEPartiNonRituali_4.02.pdf/"
        "6dab0c78-536b-f855-f236-eb25133ce565?t=1784305136173",
        ("ausiliari_del_giudice",),
        ("ausiliario del giudice", "parte non rituale", "CTU", "commissario"),
        ("sede", "riferimento fascicolo", "qualifica depositante", "oggetto deposito"),
        ("atto o relazione", "documenti allegati"),
        AUSILIARI_MODULE_FIELDS,
        ("ausiliario", "ctu", "commissario", "parte non rituale", "relazione"),
    ),
    PatModule(
        "istanza_ante_causam",
        "Modulo PDF deposito istanza ante causam",
        "4.02",
        "https://www.giustizia-amministrativa.it/documents/20142/98875166/"
        "ModuloDepositoIstanza_4.02.pdf/b4255e4b-a881-e6e8-7a74-79d8444e054b?t=1784731395249",
        ("ante_causam",),
        ("istanza ante causam", "misura cautelare prima del ricorso"),
        ("sede", "istante", "amministrazione resistente", "oggetto", "ragioni urgenza"),
        ("istanza", "documenti", "procura se richiesta"),
        ANTE_CAUSAM_MODULE_FIELDS,
        ("ante causam", "antecausam", "cautelare", "misura", "urgenza"),
    ),
    PatModule(
        "rimborso_contributo_unificato",
        "Modulo PDF deposito richiesta rimborso",
        "4.02",
        "https://www.giustizia-amministrativa.it/documents/20142/98875166/"
        "ModuloDepositoRimborso_4.02.pdf/de35d3c1-fa02-d72a-2426-6adec5755ddc?t=1784305138029",
        ("deposito_rimborso_contributo_unificato", "successivo_contributo_unificato"),
        ("rimborso contributo unificato", "contributo unificato", "pagamento non dovuto"),
        ("sede", "riferimento ricorso", "richiedente", "dati pagamento", "IBAN o dati rimborso se richiesti"),
        ("ricevuta pagamento", "documento identità se necessario", "documenti contabili"),
        RIMBORSO_MODULE_FIELDS,
        ("rimborso", "contributo", "unificato", "f24", "pagamento"),
    ),
    PatModule(
        "foglio_excel_parti",
        "Foglio Excel per parti",
        "2025",
        "https://www.giustizia-amministrativa.it/documents/20142/80293801/"
        "Excel_Parti.xlsx/38900b77-4945-f738-fe83-175e509082d3?t=1748183957377",
        ("ricorso", "atto_successivo"),
        ("molte parti", "inserimento massivo parti", "ricorrenti o resistenti plurimi"),
        ("cognome o denominazione", "codice fiscale o partita IVA", "ruolo processuale", "PEC se prevista"),
        ("foglio parti compilato"),
        PARTI_EXCEL_FIELDS,
        ("parti", "ricorrenti", "resistenti", "excel", "massivo"),
        "IUSENTRA raccoglie le righe parte e prepara i dati per il foglio massivo ufficiale.",
    ),
)


FORMWEB_DEPOSITS: tuple[PatFormwebDeposit, ...] = (
    PatFormwebDeposit(
        "ricorso",
        "Ricorso",
        "deposito_ricorso",
        "2-4 step",
        ("sede", "tipo ricorso", "parti", "richiesta e allegati", "riepilogo"),
        ("bozza Formweb", "riepilogo deposito", "deposito firmato PAdES"),
    ),
    PatFormwebDeposit(
        "atto_successivo",
        "Atto successivo",
        "deposito_atto",
        "2-4 step",
        ("sede", "NRG", "atto", "allegati", "riepilogo"),
        ("bozza Formweb", "riepilogo deposito", "atto firmato PAdES"),
    ),
    PatFormwebDeposit(
        "documento_successivo",
        "Documento successivo",
        "deposito_atto",
        "2-3 step",
        ("sede", "NRG", "documenti", "riepilogo"),
        ("bozza Formweb", "riepilogo deposito"),
    ),
    PatFormwebDeposit(
        "istanze_al_giudice",
        "Istanze al giudice",
        "deposito_atto",
        "2-4 step",
        ("sede", "NRG", "istanza", "allegati", "riepilogo"),
        ("bozza Formweb", "istanza firmata PAdES", "riepilogo deposito"),
    ),
    PatFormwebDeposit(
        "richieste_alla_segreteria",
        "Richieste alla segreteria",
        "richieste_segreteria",
        "2-3 step",
        ("sede", "riferimento fascicolo", "richiesta", "allegati"),
        ("richiesta", "ricevuta portale"),
    ),
    PatFormwebDeposit(
        "successivo_contributo_unificato",
        "Successivo contributo unificato",
        "rimborso_contributo_unificato",
        "2-3 step",
        ("sede", "NRG", "dati pagamento", "ricevuta"),
        ("ricevuta pagamento collegata", "riepilogo deposito"),
    ),
    PatFormwebDeposit(
        "successivo_notifiche",
        "Successivo notifiche",
        "deposito_atto",
        "2-3 step",
        ("sede", "NRG", "notifica", "ricevute"),
        ("notifiche e ricevute collegate", "riepilogo deposito"),
    ),
    PatFormwebDeposit(
        "deposito_rimborso_contributo_unificato",
        "Deposito rimborso contributo unificato",
        "rimborso_contributo_unificato",
        "2-3 step",
        ("sede", "riferimento pagamento", "dati rimborso", "documenti contabili"),
        ("richiesta rimborso", "ricevuta portale"),
    ),
)


WORKFLOW_STEPS: tuple[PatWorkflowStep, ...] = (
    PatWorkflowStep(
        "classifica",
        "Classifica materia e deposito",
        "IUSENTRA usa materia, fase e oggetto del fascicolo per proporre Formweb e il modulo ufficiale corretto.",
        ("scegli sede TAR/CDS/CGARS", "seleziona tipologia deposito", "controlla PNRR, appalti, CIG e rito"),
    ),
    PatWorkflowStep(
        "prepara-pdf",
        "Compila modulo e PDF",
        "IUSENTRA apre il modulo corretto, raccoglie i dati obbligatori e produce il PDF ministeriale XFA compilato prima della sessione SIGA.",
        ("campi obbligatori", "allegati ordinati", "modello ufficiale compilato dal software"),
    ),
    PatWorkflowStep(
        "firma-pades",
        "Firma PAdES",
        "Il deposito Formweb richiede sottoscrizione digitale PAdES del riepilogo/atto prima dell'invio.",
        ("token locale o Local Signer", "verifica certificato", "nessun Atto.enc PAT"),
    ),
    PatWorkflowStep(
        "apri-portale",
        "Avvia sessione ufficiale SIGA",
        "IUSENTRA prepara fascicolo, moduli e controlli, poi avvia il Portale Avvocato nel contesto sicuro richiesto da SPID, CIE e CNS.",
        ("accesso SPID, CIE o CNS", "bozza Formweb", "caricamento atti e allegati"),
    ),
    PatWorkflowStep(
        "importa-esiti",
        "Importa ricevute e deposito originale",
        "Dopo l'invio vanno archiviati ricevuta di ricezione, ricevuta di registrazione e PDF riepilogativo del deposito.",
        ("ricevuta ricezione", "ricevuta registrazione", "deposito originale"),
    ),
)


def _module_score(module: PatModule, text: str) -> int:
    haystack = " ".join([module.id, module.title, *module.formweb_types, *module.recommended_for, *module.keywords]).lower()
    score = 0
    for word in text.split():
        if len(word) < 3:
            continue
        if word in haystack:
            score += 2 if word in module.keywords else 1
    return score


def suggest_pat_modules(*values: str, limit: int = 3) -> list[dict[str, Any]]:
    """Restituisce i moduli piu' coerenti con materia, fase o tipo deposito."""

    text = " ".join(str(value or "").lower() for value in values).strip()
    if not text:
        candidates = PAT_MODULES[:3]
    else:
        scored = sorted(
            ((_module_score(module, text), module) for module in PAT_MODULES),
            key=lambda item: (item[0], item[1].id == "deposito_ricorso"),
            reverse=True,
        )
        candidates = [module for score, module in scored if score > 0][:limit] or [PAT_MODULES[0]]
    return [asdict(module) for module in candidates[:limit]]


def _opzioni_ufficiali(module: dict[str, Any]) -> None:
    """Il tipo di ricorso si sceglie con le voci esatte della tendina del modulo (TAR e appello), lette dal
    modello ministeriale: una voce abbreviata («Appalti») può corrispondere a più voci e non si scriverebbe."""
    from pct.pat_formweb import catalogo

    for campo in module.get("fillable_fields") or []:
        if campo.get("id") == "tipo_ricorso":
            voci = [v["descrizione"] for v in catalogo.opzioni("tipoRicorsoTar") + catalogo.opzioni("tipoRicorsoCds")]
            if voci:
                campo["options"] = list(dict.fromkeys(voci))


def build_pat_siga_payload() -> dict[str, Any]:
    """Payload JSON serializzabile per la superficie React PAT/SIGA."""

    from pct.pat_xfa_schema import build_pat_xfa_schema_payload

    documents = [asdict(item) for item in OFFICIAL_DOCUMENTS]
    modules: list[dict[str, Any]] = []
    for item in PAT_MODULES:
        module = asdict(item)
        _opzioni_ufficiali(module)
        module["xfa_schema"] = (
            build_pat_xfa_schema_payload(item.id)
            if item.id != "foglio_excel_parti"
            else {
                "moduleId": item.id,
                "templateFile": "",
                "rawFieldCount": len(item.fillable_fields),
                "fieldCount": len(item.fillable_fields),
                "actionCount": 0,
                "repeatableGroups": [],
                "sections": [],
            }
        )
        modules.append(module)
    deposits = [asdict(item) for item in FORMWEB_DEPOSITS]
    steps = [asdict(item) for item in WORKFLOW_STEPS]
    return {
        "source": "fonti_ufficiali_giustizia_amministrativa",
        "updatedAt": "2026-07-18",
        "portal": {
            "label": "Portale Avvocato / SIGA",
            "officialUrl": PORTALE_AVVOCATO_URL,
            "infoUrl": PORTALE_AVVOCATO_INFO_URL,
            "faqUrl": FAQ_NUOVO_PORTALE_URL,
            "authMethods": ("SPID", "CIE", "CNS"),
            "helpdesk": "supportoportale-avv@giustizia-amministrativa.it",
            "sessionMode": "sessione ufficiale assistita dal Local Connector del PC, senza iframe o proxy delle credenziali",
        },
        "regime": {
            "currentPhase": "regime Formweb",
            "formwebPriorityFrom": "2026-02-01",
            "formwebPriorityLabel": "Formweb prioritario dal 1 febbraio 2026",
            "pecResidual": True,
            "portalUploadLegacyRemoved": True,
            "note": (
                "Dal regime definitivo il deposito avviene tramite Formweb; la PEC è residuale "
                "quando il Formweb non è utilizzabile per ragioni tecniche documentate."
            ),
        },
        "limits": {
            "formweb": {
                "maxFiles": 50,
                "maxSingleFileSizeMb": 300,
                "maxTotalSizeMb": 300,
                "signature": "PADES",
                "requiresOfficialPortal": True,
            },
            "residualPdfPec": {
                "maxModuleSizeMb": 30,
                "maxSingleAttachmentSizeMb": 10,
                "signature": "PADES",
                "note": "Limiti storici dei moduli PDF via PEC: usare solo quando il canale residuale è ammesso.",
            },
            "legacyUpload": {
                "maxModuleSizeMb": 50,
                "maxSingleAttachmentSizeMb": 30,
                "removedAtRegime": True,
            },
        },
        "workflowSteps": steps,
        "formwebDeposits": deposits,
        "modules": modules,
        "documents": documents,
        "chromePdfGuide": {
            "source": ISTRUZIONI_DOWNLOAD_PDF_URL,
            "summary": "IUSENTRA scrive i dati nel modulo ministeriale XFA senza toccarne il modello: il modulo resta abilitato in Adobe Acrobat Reader, dove si incorporano gli allegati e si salva prima della firma PAdES.",
            "steps": (
                "Compila i dati richiesti nella sezione Moduli compilabili.",
                "Genera il PDF ministeriale XFA compilato da IUSENTRA.",
                "Apri il modulo con Adobe Acrobat Reader e incorpora ricorso, procura e documenti con i pulsanti «Carica ricorso» e «Allega».",
                "Salva il modulo, firmalo in PAdES e invialo via PEC alla sede (canale residuale al Formweb).",
            ),
        },
        "suggestedModules": suggest_pat_modules("ricorso appalti pnrr atto successivo"),
    }


__all__ = [
    "DOCUMENTATION_URL",
    "PORTALE_AVVOCATO_URL",
    "PatModuleField",
    "PAT_MODULES",
    "FORMWEB_DEPOSITS",
    "build_pat_siga_payload",
    "suggest_pat_modules",
]
