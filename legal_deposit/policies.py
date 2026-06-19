from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SignaturePolicy:
    target: str = "MAIN_ACT"
    format: str = "CADES_BES"
    required: bool = True
    verify_after_sign: bool = True


@dataclass(frozen=True, slots=True)
class ChannelProfile:
    id: str
    name: str
    requires_main_act: bool = True
    requires_attachments: bool = False
    requires_xml: bool = False
    xml_schema_name: str = ""
    requires_pdfa: bool = False
    requires_cades: bool = False
    requires_pades: bool = False
    requires_encryption: bool = False
    max_total_size_mb: int = 500
    max_single_file_size_mb: int = 50
    max_files: int = 0
    max_filename_length: int = 255
    allows_direct_pec: bool = False
    allows_portal_upload: bool = False
    requires_manual_final_upload: bool = False
    package_kind: str = "folder"
    xml_filename: str = ""
    accepted_pdfa: tuple[str, ...] = ()
    accepted_signature_formats: tuple[str, ...] = ()
    receipt_types: tuple[str, ...] = ()
    validation_rules: tuple[str, ...] = ()
    signature_policy: SignaturePolicy = field(default_factory=SignaturePolicy)
    defender_channel_note: str = ""
    internal_office_system_note: str = ""
    unknown_behavior: str = "fail_closed"
    metadata: dict[str, Any] = field(default_factory=dict)


class UnknownChannelError(ValueError):
    """Raised when a deposit channel is not explicitly registered."""


class AmbiguousChannelError(UnknownChannelError):
    """Raised when a generic channel would hide the actual legal registry."""


_PROFILES: dict[str, ChannelProfile] = {
    "pct_sicid": ChannelProfile(
        id="pct_sicid",
        name="PCT SICID civile",
        requires_xml=True,
        xml_schema_name="DatiAtto.xml",
        requires_pdfa=True,
        requires_cades=True,
        max_total_size_mb=30,
        max_single_file_size_mb=30,
        max_filename_length=100,
        allows_direct_pec=True,
        package_kind="pct_busta_enc",
        xml_filename="DatiAtto.xml",
        accepted_pdfa=("PDF/A-1A", "PDF/A-1B"),
        accepted_signature_formats=("CADES_BES",),
        receipt_types=("accettazione", "consegna", "controlli", "cancelleria"),
        validation_rules=("pdf_readable", "pdfa", "procedure_registry", "signed", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CADES_BES"),
        defender_channel_note="Profilo PCT civile SICID: non usare per esecuzioni SIECIC o Giudice di Pace.",
        metadata={
            "portal": "PCT_PST",
            "registry": "SICID",
            "deposit_engine": "pct_sicid",
            "payment_policy": "pst_pagopa_cu_diritti_spese",
        },
    ),
    "pct_siecic": ChannelProfile(
        id="pct_siecic",
        name="PCT SIECIC esecuzioni e concorsuali",
        requires_xml=True,
        xml_schema_name="DatiAtto.xml",
        requires_pdfa=True,
        requires_cades=True,
        max_total_size_mb=30,
        max_single_file_size_mb=30,
        max_filename_length=100,
        allows_direct_pec=True,
        package_kind="pct_busta_enc",
        xml_filename="DatiAtto.xml",
        accepted_pdfa=("PDF/A-1A", "PDF/A-1B"),
        accepted_signature_formats=("CADES_BES",),
        receipt_types=("accettazione", "consegna", "controlli", "cancelleria"),
        validation_rules=("pdf_readable", "pdfa", "procedure_registry", "signed", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CADES_BES"),
        defender_channel_note="Profilo PCT SIECIC: esecuzioni, pignoramenti e procedure concorsuali non usano SICID.",
        metadata={
            "portal": "PCT_PST",
            "registry": "SIECIC",
            "deposit_engine": "pct_siecic",
            "payment_policy": "pst_pagopa_cu_diritti_spese",
        },
    ),
    "sigp_gdp": ChannelProfile(
        id="sigp_gdp",
        name="SIGP Giudice di Pace",
        requires_xml=True,
        xml_schema_name="SIGP",
        requires_pdfa=True,
        requires_cades=True,
        max_total_size_mb=30,
        max_single_file_size_mb=30,
        max_filename_length=100,
        allows_portal_upload=True,
        requires_manual_final_upload=True,
        package_kind="sigp_upload",
        xml_filename="metadati_sigp.xml",
        accepted_pdfa=("PDF/A-1A", "PDF/A-1B"),
        accepted_signature_formats=("CADES_BES", "PADES"),
        receipt_types=("protocollo", "ricevuta_portale", "esito_cancelleria"),
        validation_rules=("pdf_readable", "pdfa", "procedure_registry", "signed", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CHANNEL_POLICY"),
        defender_channel_note="SIGP/GDP e' un profilo autonomo: non usare il PCT civile generico.",
        metadata={
            "portal": "SIGP",
            "registry": "GDP",
            "deposit_engine": "sigp_gdp",
            "payment_policy": "pst_pagopa_cu_diritti_spese",
        },
    ),
    "unep": ChannelProfile(
        id="unep",
        name="UNEP richieste notifiche ed esecuzioni",
        requires_pdfa=True,
        max_total_size_mb=100,
        max_single_file_size_mb=30,
        max_filename_length=100,
        allows_portal_upload=True,
        requires_manual_final_upload=True,
        package_kind="unep_request",
        accepted_pdfa=("PDF/A-1A", "PDF/A-1B"),
        accepted_signature_formats=("PADES", "CADES_BES"),
        receipt_types=("ricevuta_portale", "presa_in_carico", "esito_unep"),
        validation_rules=("pdf_readable", "pdfa", "procedure_registry", "signed", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CHANNEL_POLICY"),
        defender_channel_note="UNEP prepara richiesta o istanza: non genera automaticamente una relata L. 53/1994.",
        metadata={
            "portal": "UNEP",
            "registry": "UNEP",
            "deposit_engine": "unep",
            "payment_policy": "pst_pagopa_cu_diritti_spese",
            "requires_pagopa_enabled_office": True,
        },
    ),
    "pdp_penale": ChannelProfile(
        id="pdp_penale",
        name="PDP Penale",
        requires_xml=False,
        requires_pdfa=True,
        requires_cades=False,
        requires_pades=False,
        max_total_size_mb=500,
        max_single_file_size_mb=50,
        max_filename_length=100,
        allows_portal_upload=True,
        package_kind="pdp_upload",
        accepted_pdfa=("PDF/A-1A", "PDF/A-1B"),
        accepted_signature_formats=("PADES", "CADES_BES"),
        receipt_types=("INVIATO", "IN_TRANSITO", "IN_FASE_DI_VERIFICA", "ACCOLTO", "RIGETTATO", "ERRORE_TECNICO"),
        validation_rules=("pdf_readable", "pdfa", "procedure_registry", "native_digital", "signed", "no_password", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CHANNEL_POLICY"),
        defender_channel_note="PDP/PST e' il canale del difensore per il deposito penale telematico.",
        internal_office_system_note="APP e' sistema interno degli uffici giudiziari: non va presentato come canale di deposito del difensore.",
        metadata={
            "portal": "PDP",
            "registry": "PENALE",
            "deposit_engine": "pdp_penale",
            "channel_note": "PDP e PST sono canali del difensore; APP e' sistema interno degli uffici giudiziari.",
        },
    ),
    "pec_stragiudiziale": ChannelProfile(
        id="pec_stragiudiziale",
        name="PEC stragiudiziale",
        requires_pdfa=False,
        max_total_size_mb=100,
        max_single_file_size_mb=50,
        max_filename_length=100,
        allows_direct_pec=True,
        package_kind="pec_message",
        accepted_signature_formats=("PADES", "CADES_BES", "NONE"),
        receipt_types=("accettazione", "consegna", "mancata_consegna"),
        validation_rules=("safe_filename", "file_exists", "hash"),
        signature_policy=SignaturePolicy(target="CUSTOM", format="NONE", required=False),
        defender_channel_note="Invio PEC stragiudiziale con ricevute di accettazione e consegna conservate nel fascicolo.",
    ),
    "notifiche_pec": ChannelProfile(
        id="notifiche_pec",
        name="Notifiche PEC",
        requires_pdfa=False,
        max_total_size_mb=100,
        max_single_file_size_mb=50,
        max_filename_length=100,
        allows_direct_pec=True,
        package_kind="pec_notification",
        accepted_signature_formats=("PADES", "CADES_BES"),
        receipt_types=("accettazione", "consegna", "mancata_consegna"),
        validation_rules=("safe_filename", "file_exists", "hash", "notification_recipients"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CHANNEL_POLICY"),
        defender_channel_note="Notifica via PEC gestita come canale distinto dall'invio stragiudiziale ordinario.",
    ),
    "pat_siga": ChannelProfile(
        id="pat_siga",
        name="PAT/SIGA amministrativo",
        requires_xml=True,
        xml_schema_name="SIGA/PAT",
        requires_pdfa=True,
        requires_cades=False,
        requires_pades=True,
        max_total_size_mb=300,
        max_single_file_size_mb=300,
        max_files=50,
        max_filename_length=100,
        allows_portal_upload=True,
        requires_manual_final_upload=True,
        package_kind="portal_upload",
        xml_filename="metadati_pat.xml",
        accepted_pdfa=("PDF/A-1A", "PDF/A-1B"),
        accepted_signature_formats=("PADES",),
        receipt_types=("protocollo", "ricevuta_portale", "esito_segreteria"),
        validation_rules=("pdf_readable", "pdfa", "procedure_registry", "signed", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="PADES"),
        defender_channel_note=(
            "PAT/SIGA richiede profilo dedicato: il gestionale prepara e guida, senza fingere "
            "automazione non disponibile. Il modulo/atto principale deve essere PAdES secondo fonte ufficiale."
        ),
        metadata={
            "portal": "PAT",
            "registry": "PAT",
            "deposit_engine": "pat_siga",
            "official_source": "https://www.giustizia-amministrativa.it/web/guest/portale-avvocato",
            "official_operational_portal": "https://pe.prod.cloud.giustizia-amministrativa.it",
            "main_act_signature_format": "PADES",
            "pec_registry": "RegIndE",
            "payment_policy": "pat_f24_elide_contributo_unificato",
            "formweb_priority_from": "2026-02-01",
            "formweb_max_files": 50,
            "formweb_max_total_size_mb": 300,
            "formweb_max_single_file_size_mb": 300,
            "portal_upload_removed_at_regime": True,
            "residual_pec_only_on_documented_formweb_issue": True,
        },
    ),
    "ptt_sigit": ChannelProfile(
        id="ptt_sigit",
        name="PTT/SIGIT tributario",
        requires_xml=True,
        xml_schema_name="PTT/SIGIT",
        requires_pdfa=True,
        max_total_size_mb=50,
        max_single_file_size_mb=10,
        max_files=50,
        max_filename_length=100,
        allows_portal_upload=True,
        requires_manual_final_upload=True,
        package_kind="portal_upload",
        xml_filename="metadati_ptt.xml",
        accepted_pdfa=("PDF/A-1A", "PDF/A-1B"),
        accepted_signature_formats=("PADES", "CADES_BES"),
        receipt_types=("protocollo", "ricevuta_portale", "esito_segreteria"),
        validation_rules=("pdf_readable", "pdfa", "procedure_registry", "signed", "safe_filename", "ptt_limits"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CHANNEL_POLICY"),
        defender_channel_note="PTT/SIGIT e' trattato come canale tributario autonomo con upload guidato e riconciliazione ricevute.",
        metadata={
            "portal": "PTT",
            "registry": "SIGIT",
            "deposit_engine": "ptt_sigit",
            "payment_policy": "ptt_cut_pagopa",
        },
    ),
    "upload_manuale_guidato": ChannelProfile(
        id="upload_manuale_guidato",
        name="Upload manuale guidato",
        requires_manual_final_upload=True,
        allows_portal_upload=True,
        max_total_size_mb=500,
        max_single_file_size_mb=50,
        max_filename_length=100,
        package_kind="manual_upload",
        accepted_signature_formats=("PADES", "CADES_BES", "NONE"),
        receipt_types=("protocollo", "ricevuta_portale", "esito_manuale"),
        validation_rules=("safe_filename", "file_exists", "hash"),
        signature_policy=SignaturePolicy(target="CUSTOM", format="CHANNEL_POLICY", required=False),
        defender_channel_note="Il sistema prepara il pacchetto e la checklist, ma l'upload finale resta manuale e consapevole.",
    ),
    "portal_upload": ChannelProfile(
        id="portal_upload",
        name="Canale generico portal upload",
        requires_manual_final_upload=True,
        allows_portal_upload=True,
        max_total_size_mb=500,
        max_single_file_size_mb=50,
        max_filename_length=100,
        package_kind="portal_upload",
        accepted_signature_formats=("PADES", "CADES_BES", "NONE"),
        receipt_types=("protocollo", "ricevuta_portale"),
        validation_rules=("safe_filename", "file_exists", "hash"),
        signature_policy=SignaturePolicy(target="CUSTOM", format="CHANNEL_POLICY", required=False),
        defender_channel_note="Profilo generico ammesso solo se richiesto e confermato manualmente.",
        metadata={"manual_confirmation_required": True},
    ),
}

_ALIASES = {
    "sicid": "pct_sicid",
    "pct_sicid": "pct_sicid",
    "siecic": "pct_siecic",
    "pct_siecic": "pct_siecic",
    "sigp": "sigp_gdp",
    "gdp": "sigp_gdp",
    "giudice_di_pace": "sigp_gdp",
    "ufficiale_giudiziario": "unep",
    "pdp": "pdp_penale",
    "penale": "pdp_penale",
    "pec": "pec_stragiudiziale",
    "notifica_pec": "notifiche_pec",
    "notifiche": "notifiche_pec",
    "pat": "pat_siga",
    "siga": "pat_siga",
    "ptt": "ptt_sigit",
    "sigit": "ptt_sigit",
    "manual_upload": "upload_manuale_guidato",
}

_AMBIGUOUS_CHANNELS = {"", "pct", "pst", "pct_pst", "pct_civile", "pct_telematico", "portale", "portale_telematico"}


def channel_profile_for(channel: str) -> ChannelProfile:
    key = str(channel or "").strip().lower()
    if key in _AMBIGUOUS_CHANNELS:
        raise AmbiguousChannelError(
            "Canale telematico non determinato: scegli un profilo esplicito tra "
            "pct_sicid, pct_siecic, sigp_gdp, unep, pat_siga, ptt_sigit o pdp_penale."
        )
    key = _ALIASES.get(key, key)
    profile = _PROFILES.get(key)
    if profile is None:
        raise UnknownChannelError(f"Canale telematico non registrato: {channel}.")
    return profile


def get_channel_profile(channel: str) -> ChannelProfile:
    return channel_profile_for(channel)


def list_channel_profiles() -> list[ChannelProfile]:
    return list(_PROFILES.values())
