from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


class UnknownProcedureError(ValueError):
    """Raised when a telematic procedure is not explicitly registered."""


class ProcedureProfileMismatchError(ValueError):
    """Raised when procedure, portal or deposit engine do not match."""


@dataclass(frozen=True, slots=True)
class TelematicProcedure:
    id: str
    portal: str
    registry: str
    area: str
    subarea: str
    deposit_engine: str
    required_documents: tuple[str, ...]
    required_metadata: tuple[str, ...]
    validation_rules: tuple[str, ...]
    requires_signature: bool
    requires_pdfa: bool
    requires_payment: bool
    supports_l53_notification: bool
    human_review_required: bool
    unknown_behavior: str = "fail_closed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _procedure(
    procedure_id: str,
    *,
    portal: str,
    registry: str,
    area: str,
    subarea: str,
    deposit_engine: str,
    required_documents: tuple[str, ...] = ("atto_principale",),
    required_metadata: tuple[str, ...] = ("ufficio", "registro", "numero_rg", "anno_rg"),
    validation_rules: tuple[str, ...] = ("procedure_registered", "safe_filename", "pdf_readable"),
    requires_signature: bool = True,
    requires_pdfa: bool = True,
    requires_payment: bool = False,
    supports_l53_notification: bool = False,
    human_review_required: bool = True,
) -> TelematicProcedure:
    return TelematicProcedure(
        id=procedure_id,
        portal=portal,
        registry=registry,
        area=area,
        subarea=subarea,
        deposit_engine=deposit_engine,
        required_documents=required_documents,
        required_metadata=required_metadata,
        validation_rules=validation_rules,
        requires_signature=requires_signature,
        requires_pdfa=requires_pdfa,
        requires_payment=requires_payment,
        supports_l53_notification=supports_l53_notification,
        human_review_required=human_review_required,
    )


def _pct_sicid(procedure_id: str, subarea: str, *, payment: bool = False) -> TelematicProcedure:
    return _procedure(
        procedure_id,
        portal="PCT_PST",
        registry="SICID",
        area="PCT civile",
        subarea=subarea,
        deposit_engine="pct_sicid",
        validation_rules=("procedure_registered", "sicid_registry", "dati_atto_xml", "pdfa", "signed"),
        requires_payment=payment,
        supports_l53_notification=True,
    )


def _pct_siecic(procedure_id: str, subarea: str, *, payment: bool = False) -> TelematicProcedure:
    return _procedure(
        procedure_id,
        portal="PCT_PST",
        registry="SIECIC",
        area="PCT esecuzioni e concorsuali",
        subarea=subarea,
        deposit_engine="pct_siecic",
        validation_rules=("procedure_registered", "siecic_registry", "dati_atto_xml", "pdfa", "signed"),
        requires_payment=payment,
        supports_l53_notification=True,
    )


def _sigp(procedure_id: str, subarea: str, *, payment: bool = False) -> TelematicProcedure:
    return _procedure(
        procedure_id,
        portal="SIGP",
        registry="GDP",
        area="Giudice di Pace",
        subarea=subarea,
        deposit_engine="sigp_gdp",
        validation_rules=("procedure_registered", "sigp_registry", "pdfa", "signed", "portal_receipt"),
        requires_payment=payment,
    )


def _unep(procedure_id: str, subarea: str, *, payment: bool = False) -> TelematicProcedure:
    return _procedure(
        procedure_id,
        portal="UNEP",
        registry="UNEP",
        area="Ufficiali giudiziari",
        subarea=subarea,
        deposit_engine="unep",
        validation_rules=("procedure_registered", "unep_request", "pdfa", "signed", "payment_if_due"),
        requires_payment=payment,
        supports_l53_notification=False,
    )


def _pat(procedure_id: str, subarea: str, *, payment: bool = False) -> TelematicProcedure:
    return _procedure(
        procedure_id,
        portal="PAT",
        registry="PAT",
        area="Giustizia amministrativa",
        subarea=subarea,
        deposit_engine="pat_siga",
        validation_rules=("procedure_registered", "pat_metadata", "pdfa", "signed", "portal_receipt"),
        requires_payment=payment,
    )


def _ptt(procedure_id: str, subarea: str, *, payment: bool = False) -> TelematicProcedure:
    return _procedure(
        procedure_id,
        portal="PTT",
        registry="SIGIT",
        area="Giustizia tributaria",
        subarea=subarea,
        deposit_engine="ptt_sigit",
        validation_rules=("procedure_registered", "ptt_metadata", "ptt_limits", "pdfa", "signed"),
        requires_payment=payment,
    )


def _pdp(procedure_id: str, subarea: str) -> TelematicProcedure:
    return _procedure(
        procedure_id,
        portal="PDP",
        registry="PENALE",
        area="Deposito penale",
        subarea=subarea,
        deposit_engine="pdp_penale",
        required_metadata=("ufficio", "registro_penale", "numero", "anno"),
        validation_rules=("procedure_registered", "pdp_metadata", "pdfa", "signed", "no_app_channel"),
    )


def _pst_area_web(procedure_id: str, subarea: str) -> TelematicProcedure:
    return _procedure(
        procedure_id,
        portal="PST_AREA_WEB",
        registry="NOTIFICHE",
        area="Perfezionamento notifiche",
        subarea=subarea,
        deposit_engine="pst_area_web",
        required_documents=("atto_notificato", "relata_firmata", "rac", "avviso_mancata_consegna"),
        required_metadata=("valutazione_avvocato", "causa_mancata_consegna", "data_notifica"),
        validation_rules=("procedure_registered", "lawyer_assessment", "evidence_pack", "manual_final_upload"),
        supports_l53_notification=True,
    )


def _manual_portal(procedure_id: str, *, portal: str, registry: str, area: str, subarea: str, payment: bool = False) -> TelematicProcedure:
    return _procedure(
        procedure_id,
        portal=portal,
        registry=registry,
        area=area,
        subarea=subarea,
        deposit_engine="upload_manuale_guidato",
        validation_rules=("procedure_registered", "manual_upload_confirmed", "pdfa", "signed"),
        requires_payment=payment,
    )


PROCEDURE_REGISTRY: dict[str, TelematicProcedure] = {
    item.id: item
    for item in (
        _pct_sicid("PCT_SICID_CIVILE_ORDINARIO", "Civile ordinario"),
        _pct_sicid("PCT_SICID_LAVORO", "Lavoro"),
        _pct_sicid("PCT_SICID_PREVIDENZA", "Previdenza"),
        _pct_sicid("PCT_SICID_FAMIGLIA", "Famiglia"),
        _pct_sicid("PCT_SICID_MINORI", "Minori"),
        _pct_sicid("PCT_SICID_VOLONTARIA_GIURISDIZIONE", "Volontaria giurisdizione"),
        _pct_sicid("PCT_SICID_IMMIGRAZIONE", "Immigrazione"),
        _pct_sicid("PCT_SICID_DECRETO_INGIUNTIVO", "Decreto ingiuntivo", payment=True),
        _pct_sicid("PCT_SICID_OPPOSIZIONE_DI", "Opposizione a decreto ingiuntivo"),
        _pct_sicid("PCT_SICID_APPELLO", "Appello"),
        _pct_sicid("PCT_SICID_RECLAMO", "Reclamo"),
        _pct_sicid("PCT_SICID_CAUTELARE", "Cautelare"),
        _pct_siecic("PCT_SIECIC_ESECUZIONE_MOBILIARE", "Esecuzione mobiliare", payment=True),
        _pct_siecic("PCT_SIECIC_ESECUZIONE_IMMOBILIARE", "Esecuzione immobiliare", payment=True),
        _pct_siecic("PCT_SIECIC_PIGNORAMENTO_PRESSO_TERZI", "Pignoramento presso terzi", payment=True),
        _pct_siecic("PCT_SIECIC_INTERVENTO_CREDITORE", "Intervento del creditore"),
        _pct_siecic("PCT_SIECIC_OPPOSIZIONE_ESECUTIVA", "Opposizione esecutiva"),
        _pct_siecic("PCT_SIECIC_PROCEDURE_CONCORSUALI", "Procedure concorsuali"),
        _pct_siecic("PCT_SIECIC_CRISI_IMPRESA", "Crisi d'impresa"),
        _sigp("SIGP_GDP_ATTO_INTRODUTTIVO", "Atto introduttivo", payment=True),
        _sigp("SIGP_GDP_ATTO_SUCCESSIVO", "Atto successivo"),
        _sigp("SIGP_GDP_OPPOSIZIONE_SANZIONE", "Opposizione a sanzione", payment=True),
        _sigp("SIGP_GDP_DECRETO_INGIUNTIVO", "Decreto ingiuntivo", payment=True),
        _sigp("SIGP_GDP_SINCRONIZZAZIONE_FASCICOLO", "Sincronizzazione fascicolo", payment=False),
        _unep("UNEP_RICHIESTA_NOTIFICA", "Richiesta notifica", payment=True),
        _unep("UNEP_RICHIESTA_ESECUZIONE", "Richiesta esecuzione", payment=True),
        _unep("UNEP_RICHIESTA_492_BIS", "Richiesta ex art. 492-bis c.p.c.", payment=True),
        _unep("UNEP_RESTITUZIONE_SOMME", "Restituzione somme"),
        _unep("UNEP_INTEGRAZIONE_PAGAMENTO", "Integrazione pagamento", payment=True),
        _unep("UNEP_PAGAMENTO_RICHIESTA", "Pagamento richiesta", payment=True),
        _pat("PAT_RICORSO_INTRODUTTIVO", "Ricorso introduttivo", payment=True),
        _pat("PAT_ATTO_SUCCESSIVO", "Atto successivo"),
        _pat("PAT_MOTIVI_AGGIUNTI", "Motivi aggiunti", payment=True),
        _pat("PAT_ISTANZA_CAUTELARE", "Istanza cautelare"),
        _pat("PAT_MEMORIA", "Memoria"),
        _pat("PAT_DOCUMENTI", "Documenti"),
        _pat("PAT_RICHIESTA_SEGRETERIA", "Richiesta segreteria"),
        _pat("PAT_AUSILIARIO_GIUDICE", "Ausiliario del giudice"),
        _pat("PAT_PARTE_NON_RITUALE", "Parte non rituale"),
        _pat("PAT_ISTANZA_ANTE_CAUSAM", "Istanza ante causam"),
        _pat("PAT_RICHIESTA_RIMBORSO", "Richiesta rimborso"),
        _ptt("PTT_RICORSO", "Ricorso", payment=True),
        _ptt("PTT_APPELLO", "Appello", payment=True),
        _ptt("PTT_CONTRODEDUZIONI", "Controdeduzioni"),
        _ptt("PTT_MEMORIA", "Memoria"),
        _ptt("PTT_DOCUMENTI", "Documenti"),
        _ptt("PTT_ISTANZA", "Istanza"),
        _ptt("PTT_DEPOSITO_SUCCESSIVO", "Deposito successivo"),
        _ptt("PTT_CUT_PAGOPA", "CUT PagoPA", payment=True),
        _ptt("PTT_CONSULTAZIONE_FASCICOLO", "Consultazione fascicolo", payment=False),
        _ptt("PTT_TELECONTENZIOSO", "Telecontenzioso"),
        _ptt("PTT_UDIENZA_A_DISTANZA", "Udienza a distanza"),
        _pdp("PDP_DEPOSITO_ATTO_PENALE", "Deposito atto penale"),
        _pdp("PDP_ATTO_SUCCESSIVO", "Atto successivo"),
        _pdp("PDP_RICHIESTA_ACCESSO_ATTI", "Richiesta accesso atti"),
        _pdp("PDP_CONSULTAZIONE_FASCICOLO_PM", "Consultazione fascicolo PM"),
        _pdp("PDP_AVVISI_ATTI_CANCELLERIA", "Avvisi e atti di cancelleria"),
        _pst_area_web("PST_AREA_WEB_NOTIFICA_MANCATA_CAUSA_DESTINATARIO", "Notifica non consegnata per causa destinatario"),
        _pst_area_web("PST_AREA_WEB_DEPOSITO_ATTO_NOTIFICATO", "Deposito atto notificato"),
        _pst_area_web("PST_AREA_WEB_PERFEZIONAMENTO_NOTIFICA", "Perfezionamento notifica"),
        _manual_portal(
            "TRIBUNALE_ONLINE_VOLONTARIA_GIURISDIZIONE",
            portal="TRIBUNALE_ONLINE",
            registry="VOLONTARIA_GIURISDIZIONE",
            area="Tribunale online",
            subarea="Volontaria giurisdizione",
        ),
        _manual_portal("LSG_PATROCINIO_SPESE_STATO", portal="LSG", registry="PATROCINIO", area="Liquidazioni spese giustizia", subarea="Patrocinio a spese dello Stato"),
        _manual_portal("LSG_DIFENSORE_UFFICIO", portal="LSG", registry="DIFENSORE_UFFICIO", area="Liquidazioni spese giustizia", subarea="Difensore d'ufficio"),
        _manual_portal("LSG_ISTANZA_LIQUIDAZIONE", portal="LSG", registry="LIQUIDAZIONI", area="Liquidazioni spese giustizia", subarea="Istanza liquidazione"),
        _manual_portal("PVP_PUBBLICAZIONE_AVVISO", portal="PVP", registry="VENDITE_PUBBLICHE", area="Portale vendite pubbliche", subarea="Pubblicazione avviso", payment=True),
        _manual_portal("CLASS_ACTION_AZIONE_CLASSE", portal="CLASS_ACTION", registry="AZIONI_CLASSE", area="Class action", subarea="Azione di classe"),
        _manual_portal("CLASS_ACTION_ADESIONE", portal="CLASS_ACTION", registry="AZIONI_CLASSE", area="Class action", subarea="Adesione"),
    )
}


def get_procedure(procedure_id: str) -> TelematicProcedure:
    key = str(procedure_id or "").strip().upper()
    if not key:
        raise UnknownProcedureError("Procedimento telematico non indicato.")
    procedure = PROCEDURE_REGISTRY.get(key)
    if procedure is None:
        raise UnknownProcedureError(f"Procedimento telematico non registrato: {procedure_id}.")
    return procedure


def list_procedures() -> list[TelematicProcedure]:
    return list(PROCEDURE_REGISTRY.values())


def validate_procedure_profile(
    procedure_id: str,
    *,
    portal: str = "",
    registry: str = "",
    deposit_engine: str = "",
) -> TelematicProcedure:
    procedure = get_procedure(procedure_id)
    if portal and str(portal).strip().upper() != procedure.portal:
        raise ProcedureProfileMismatchError(f"Il portale {portal} non corrisponde al procedimento {procedure.id}.")
    if registry and str(registry).strip().upper() != procedure.registry:
        raise ProcedureProfileMismatchError(f"Il registro {registry} non corrisponde al procedimento {procedure.id}.")
    if deposit_engine and str(deposit_engine).strip().lower() != procedure.deposit_engine:
        raise ProcedureProfileMismatchError(
            f"Il motore {deposit_engine} non corrisponde al procedimento {procedure.id}."
        )
    return procedure

