from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .procedure_registry import TelematicProcedure, get_procedure


@dataclass(frozen=True, slots=True)
class PaymentPolicy:
    id: str
    label: str
    channels: tuple[str, ...]
    source_checked_at: str
    official_sources: tuple[str, ...]
    required_inputs: tuple[str, ...] = ()
    proof_documents: tuple[str, ...] = ()
    accepted_statuses: tuple[str, ...] = ()
    collection_codes: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()
    missing_payment_action: str = ""
    amount_strategy: str = "manual_professional_review"
    allows_split_payments: bool = False
    forbids_continuous_polling: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PST_PAGOPA_PAYMENT = PaymentPolicy(
    id="pst_pagopa_cu_diritti_spese",
    label="PST pagoPA per contributo unificato, diritti e spese",
    channels=("PCT_TELEMATICO", "pct_sicid", "pct_siecic", "sigp_gdp", "unep"),
    source_checked_at="2026-06-02",
    official_sources=(
        "https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC433&modelId=12",
        "https://pst.giustizia.it/PST/resources/cms/documents/PagTel_Vademecum_unico.pdf",
        "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3099",
        "https://pst.giustizia.it/PST/resources/cms/documents/PDA__Flussi_pagamento_telematico_tramite_PST_vers._6.3.pdf",
        "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3076",
        "https://servizipst.giustizia.it/PST/it/pagopa.wp",
    ),
    required_inputs=(
        "ufficio_giudiziario",
        "tipologia_pagamento",
        "importo",
        "soggetto_debitore",
    ),
    proof_documents=("RT.xml", "ricevuta_telematica_xml", "promemoria_pdf_non_sostitutivo"),
    accepted_statuses=("DISPONIBILE", "USATO", "OK_PSP", "RIMBORSATO"),
    collection_codes=("CONTRIB", "DIRCANC", "DIRCOPIA", "CONTRBENI", "UNPIG", "UNNOT"),
    warning_codes=("pagamento_mancante", "rt_xml_mancante", "rt_gia_usata", "pagamento_in_attesa_rt"),
    missing_payment_action=(
        "Se il contributo, i diritti o le spese sono dovuti, genera o recupera la ricevuta telematica "
        "PST pagoPA. Nel deposito telematico allega la RT.xml; il promemoria PDF non sostituisce la RT."
    ),
    allows_split_payments=True,
    forbids_continuous_polling=True,
    notes=(
        "La fonte PST consente area riservata, area pubblica pagoPA per utenti non registrati e Punto di Accesso.",
        "Con pagamento frazionato devono essere inoltrate tutte le ricevute telematiche riferite ai versamenti.",
        "Per gli uffici UNEP i pagamenti vanno resi disponibili solo per uffici abilitati al servizio PAGAM_TEL.",
    ),
    metadata={
        "public_payment_url": "https://servizipst.giustizia.it/PST/it/pagopa.wp",
        "rt_xml_is_telematic_proof": True,
        "max_payment_requests_per_cart_legacy_wisp": 5,
        "status_with_positive_rt": "DISPONIBILE",
    },
)

PAT_F24_ELIDE_PAYMENT = PaymentPolicy(
    id="pat_f24_elide_contributo_unificato",
    label="PAT/SIGA contributo unificato con quietanza F24 Elide",
    channels=("PAT_AMMINISTRATIVO", "pat_siga"),
    source_checked_at="2026-06-02",
    official_sources=(
        "https://www.giustizia-amministrativa.it/faq-nuovo-portale",
        "https://www.giustizia-amministrativa.it/documents/20142/0/nsiga_4464814.pdf/c42a271a-c265-a3e1-d248-59c7be3d5f58?t=1611836199000",
    ),
    required_inputs=(
        "data_versamento",
        "estremi_versamento",
        "importo_versato",
        "codice_tributo",
        "numero_riga",
        "elementi_identificativi",
        "copia_quietanza",
    ),
    proof_documents=("quietanza_f24_elide", "copia_informatica_quietanza"),
    collection_codes=("GA01", "GA02", "GA03", "GA04", "GA05"),
    warning_codes=("quietanza_pat_mancante", "codice_tributo_pat_mancante", "numero_riga_pat_mancante"),
    missing_payment_action=(
        "Nel deposito PAT compila la sezione Contributo unificato con data, estremi, importo, codice tributo, "
        "numero riga ed elementi identificativi, allegando la copia informatica della quietanza F24 Elide."
    ),
    allows_split_payments=True,
    notes=(
        "La FAQ del nuovo portale indica che il contributo unificato può essere aggiunto prima dell'invio definitivo.",
        "Le istruzioni PAT raccomandano un singolo pagamento per volta; con F24 a più righe va indicato il numero riga.",
    ),
    metadata={
        "payment_method": "F24_ELIDE",
        "other_office_flag": "solo se il versamento non riguarda il deposito attuale",
    },
)

PTT_CUT_PAGOPA_PAYMENT = PaymentPolicy(
    id="ptt_cut_pagopa",
    label="PTT/SIGIT contributo unificato tributario con pagoPA",
    channels=("PTT_TRIBUTARIO", "ptt_sigit"),
    source_checked_at="2026-06-02",
    official_sources=(
        "https://www.mef.gov.it/ufficio-stampa/comunicati/2019/documenti/prot._5764-19_Circolare_PTT_4-7-2019.pdf",
        "https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/most-viewed",
        "https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3016",
        "https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3059",
        "https://sigit.giustiziatributaria.gov.it/Sigit/index.do",
    ),
    required_inputs=("RGR_RGA", "importo_cut", "area_personale_ptt_o_link_pec_pagopa"),
    proof_documents=("associazione_automatica_cut_rgr_rga", "ricevuta_pagopa_ptt_se_disponibile"),
    warning_codes=("cut_ptt_non_associato", "rgr_rga_pagamento_mancante", "ricevuta_ptt_da_verificare"),
    missing_payment_action=(
        "Per ricorsi e appelli PTT usa il pagamento CUT pagoPA dall'area riservata PTT o dal link comunicato "
        "con il numero RGR/RGA; la fonte MEF indica l'abbinamento automatico al ricorso/appello."
    ),
    notes=(
        "La circolare MEF 4 luglio 2019 distingue pagamento contestuale al messaggio PEC RGR/RGA e pagamento successivo da Area personale.",
        "Quando il pagamento è associato dal SIGIT non va inventato un allegato sostitutivo nel gestionale.",
    ),
    metadata={
        "auto_association_to_rgr_rga": True,
        "receipt_deposit_required_when_auto_associated": False,
        "active_from": "2019-06-24",
    },
)


_POLICIES: dict[str, PaymentPolicy] = {
    policy.id: policy
    for policy in (
        PST_PAGOPA_PAYMENT,
        PAT_F24_ELIDE_PAYMENT,
        PTT_CUT_PAGOPA_PAYMENT,
    )
}


_CHANNEL_TO_POLICY: dict[str, str] = {
    channel.upper(): policy.id
    for policy in _POLICIES.values()
    for channel in policy.channels
}


def list_payment_policies() -> list[PaymentPolicy]:
    return list(_POLICIES.values())


def payment_policy_for_channel(channel: str) -> PaymentPolicy | None:
    key = str(channel or "").strip()
    if not key:
        return None
    return _POLICIES.get(_CHANNEL_TO_POLICY.get(key.upper(), ""))


def payment_policy_for_procedure(procedure: str | TelematicProcedure) -> PaymentPolicy | None:
    item = get_procedure(procedure) if isinstance(procedure, str) else procedure
    if not item.requires_payment:
        return None
    return payment_policy_for_channel(item.deposit_engine) or payment_policy_for_channel(item.portal)
