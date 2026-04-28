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
    allows_direct_pec: bool = False
    allows_portal_upload: bool = False
    requires_manual_final_upload: bool = False
    package_kind: str = "folder"
    xml_filename: str = ""
    accepted_signature_formats: tuple[str, ...] = ()
    receipt_types: tuple[str, ...] = ()
    validation_rules: tuple[str, ...] = ()
    signature_policy: SignaturePolicy = field(default_factory=SignaturePolicy)
    defender_channel_note: str = ""
    internal_office_system_note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


_PROFILES: dict[str, ChannelProfile] = {
    "pct_pst": ChannelProfile(
        id="pct_pst",
        name="PCT/PST civile",
        requires_xml=True,
        xml_schema_name="DatiAtto.xml",
        requires_pdfa=True,
        requires_cades=True,
        max_total_size_mb=30,
        max_single_file_size_mb=30,
        allows_direct_pec=True,
        package_kind="pct_busta_enc",
        xml_filename="DatiAtto.xml",
        accepted_signature_formats=("CADES_BES",),
        receipt_types=("accettazione", "consegna", "controlli", "cancelleria"),
        validation_rules=("pdf_readable", "pdfa", "signed", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CADES_BES"),
        defender_channel_note="Il deposito civile avviene tramite PST/PCT e canale PEC previsto dal profilo.",
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
        allows_portal_upload=True,
        package_kind="pdp_upload",
        accepted_signature_formats=("PADES", "CADES_BES"),
        receipt_types=("INVIATO", "IN_TRANSITO", "IN_FASE_DI_VERIFICA", "ACCOLTO", "RIGETTATO", "ERRORE_TECNICO"),
        validation_rules=("pdf_readable", "pdfa", "native_digital", "signed", "no_password", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CHANNEL_POLICY"),
        defender_channel_note="PDP/PST e' il canale del difensore per il deposito penale telematico.",
        internal_office_system_note="APP e' sistema interno degli uffici giudiziari: non va presentato come canale di deposito del difensore.",
        metadata={
            "channel_note": "PDP e PST sono canali del difensore; APP e' sistema interno degli uffici giudiziari.",
        },
    ),
    "pec_stragiudiziale": ChannelProfile(
        id="pec_stragiudiziale",
        name="PEC stragiudiziale",
        requires_pdfa=False,
        max_total_size_mb=100,
        max_single_file_size_mb=50,
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
        requires_pades=False,
        max_total_size_mb=500,
        max_single_file_size_mb=50,
        allows_portal_upload=True,
        requires_manual_final_upload=True,
        package_kind="portal_upload",
        xml_filename="metadati_pat.xml",
        accepted_signature_formats=("PADES", "CADES_BES"),
        receipt_types=("protocollo", "ricevuta_portale", "esito_segreteria"),
        validation_rules=("pdf_readable", "pdfa", "signed", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CHANNEL_POLICY"),
        defender_channel_note="PAT/SIGA richiede profilo dedicato: il gestionale prepara e guida, senza fingere automazione non disponibile.",
    ),
    "ptt_sigit": ChannelProfile(
        id="ptt_sigit",
        name="PTT/SIGIT tributario",
        requires_xml=True,
        xml_schema_name="PTT/SIGIT",
        requires_pdfa=True,
        max_total_size_mb=500,
        max_single_file_size_mb=50,
        allows_portal_upload=True,
        requires_manual_final_upload=True,
        package_kind="portal_upload",
        xml_filename="metadati_ptt.xml",
        accepted_signature_formats=("PADES", "CADES_BES"),
        receipt_types=("protocollo", "ricevuta_portale", "esito_segreteria"),
        validation_rules=("pdf_readable", "pdfa", "signed", "safe_filename"),
        signature_policy=SignaturePolicy(target="MAIN_ACT", format="CHANNEL_POLICY"),
        defender_channel_note="PTT/SIGIT e' trattato come canale tributario autonomo con upload guidato e riconciliazione ricevute.",
    ),
    "upload_manuale_guidato": ChannelProfile(
        id="upload_manuale_guidato",
        name="Upload manuale guidato",
        requires_manual_final_upload=True,
        allows_portal_upload=True,
        max_total_size_mb=500,
        max_single_file_size_mb=50,
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
        package_kind="portal_upload",
        accepted_signature_formats=("PADES", "CADES_BES", "NONE"),
        receipt_types=("protocollo", "ricevuta_portale"),
        validation_rules=("safe_filename", "file_exists", "hash"),
        signature_policy=SignaturePolicy(target="CUSTOM", format="CHANNEL_POLICY", required=False),
        defender_channel_note="Profilo generico per portali non pienamente automatizzabili: preparazione locale, upload manuale, riconciliazione ricevuta.",
    ),
}

_ALIASES = {
    "pct": "pct_pst",
    "pst": "pct_pst",
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


def channel_profile_for(channel: str) -> ChannelProfile:
    key = str(channel or "").strip().lower()
    key = _ALIASES.get(key, key)
    return _PROFILES.get(key) or _PROFILES["portal_upload"]


def get_channel_profile(channel: str) -> ChannelProfile:
    return channel_profile_for(channel)


def list_channel_profiles() -> list[ChannelProfile]:
    return list(_PROFILES.values())
