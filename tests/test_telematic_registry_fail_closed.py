from __future__ import annotations

from pathlib import Path

import pytest

from legal_deposit.models import DepositDocument, PreflightStatus
from legal_deposit.policies import AmbiguousChannelError, UnknownChannelError, channel_profile_for
from legal_deposit.procedure_registry import (
    ProcedureProfileMismatchError,
    UnknownProcedureError,
    get_procedure,
    validate_procedure_profile,
)
from legal_deposit.validators import DocumentPreflightValidator
from pct.notifica import LegacyNotificaTelematicaDeprecata, NotificaTelematica, RelataDiNotifica
from pct.notifiche_legali import (
    LEGAL_NOTIFICATION_SUBJECT,
    build_notification_evidence_pack,
    prepare_pst_failed_notification_workflow,
    validate_legal_notification,
)
from pct.pec import ConfigPEC


def _pdf(path: Path, *, pdfa: bool = True, size_mb: int = 0) -> Path:
    marker = b"%pdfaid:part 1 pdfaid:conformance B\n" if pdfa else b""
    data = (
        b"%PDF-1.4\n"
        + marker
        + b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        + b"2 0 obj<</Type/Pages/Count 0>>endobj\n"
        + b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    if size_mb:
        data += b"0" * (size_mb * 1024 * 1024)
    path.write_bytes(data)
    return path


def _l53_payload() -> dict[str, object]:
    return {
        "operazione": "notifica_pec_l53",
        "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT,
        "mittente_avvocato_abilitato": True,
        "mittente_pec_validata": True,
        "avvocato_nome": "Mario Rossi",
        "avvocato_cf": "RSSMRA80A01H501U",
        "avvocato_foro": "Roma",
        "mittente_pec": "studio@example.pec.it",
        "fonte_pec_mittente": "ReGIndE",
        "mittente_pec_pubblico_elenco": True,
        "assistito_nome": "Cliente S.r.l.",
        "assistito_cf": "01234567890",
        "ruolo_destinatario": "controparte",
        "destinatario_nome": "Controparte S.p.A.",
        "destinatario_pec": "controparte@example.pec.it",
        "fonte_pec_destinatario": "registro_imprese",
        "destinatario_pec_pubblico_elenco": True,
        "data_verifica_pec": "2026-05-12T10:30",
        "luogo": "Roma",
        "data_relata": "2026-05-12",
        "ricevuta_completa": True,
        "relata_firmata": True,
        "relata_documento_separato": True,
        "documenti": [{"nome_file": "atto.pdf", "descrizione": "Atto nativo", "origine": "nativo_digitale"}],
    }


def test_unknown_channel_fails_closed() -> None:
    with pytest.raises(UnknownChannelError):
        channel_profile_for("canale_non_censito")
    with pytest.raises(AmbiguousChannelError):
        channel_profile_for("pct")


def test_unknown_procedure_fails_closed() -> None:
    with pytest.raises(UnknownProcedureError):
        get_procedure("PCT_GENERICO")


def test_registry_separates_pct_sigp_unep_pat_ptt_pdp_profiles() -> None:
    assert validate_procedure_profile("PCT_SICID_CIVILE_ORDINARIO", deposit_engine="pct_sicid").registry == "SICID"
    assert validate_procedure_profile("PCT_SIECIC_ESECUZIONE_MOBILIARE", deposit_engine="pct_siecic").registry == "SIECIC"
    assert validate_procedure_profile("SIGP_GDP_ATTO_INTRODUTTIVO", deposit_engine="sigp_gdp").portal == "SIGP"
    assert validate_procedure_profile("UNEP_RICHIESTA_NOTIFICA", deposit_engine="unep").supports_l53_notification is False
    assert validate_procedure_profile("PAT_RICORSO_INTRODUTTIVO", deposit_engine="pat_siga").portal == "PAT"
    assert validate_procedure_profile("PDP_DEPOSITO_ATTO_PENALE", deposit_engine="pdp_penale").registry == "PENALE"
    with pytest.raises(ProcedureProfileMismatchError):
        validate_procedure_profile("PCT_SICID_CIVILE_ORDINARIO", deposit_engine="pct_siecic")
    with pytest.raises(ProcedureProfileMismatchError):
        validate_procedure_profile("PCT_SIECIC_ESECUZIONE_MOBILIARE", deposit_engine="pct_sicid")
    with pytest.raises(ProcedureProfileMismatchError):
        validate_procedure_profile("PAT_RICORSO_INTRODUTTIVO", deposit_engine="pct_sicid")
    with pytest.raises(ProcedureProfileMismatchError):
        validate_procedure_profile("PDP_DEPOSITO_ATTO_PENALE", deposit_engine="pct_sicid")


def test_ptt_limits_10mb_50mb_50_files_100_chars(tmp_path: Path) -> None:
    profile = channel_profile_for("ptt_sigit")
    assert profile.max_single_file_size_mb == 10
    assert profile.max_total_size_mb == 50
    assert profile.max_files == 50
    assert profile.max_filename_length == 100

    large = _pdf(tmp_path / "atto.pdf", size_mb=11)
    long_name = _pdf(tmp_path / ("a" * 101 + ".pdf"))
    docs = [
        DepositDocument(path=str(large), role="MAIN_ACT", filename=large.name, signed=True, signature_format="PADES"),
        DepositDocument(path=str(long_name), role="ATTACHMENT", filename=long_name.name, signed=True, signature_format="PADES"),
    ]
    docs.extend(
        DepositDocument(path=str(_pdf(tmp_path / f"allegato_{index}.pdf")), role="ATTACHMENT", filename=f"allegato_{index}.pdf", signed=True, signature_format="PADES")
        for index in range(51)
    )

    results = DocumentPreflightValidator().validate(documents=docs, profile=profile)

    assert any(item.code == "SINGLE_SIZE_EXCEEDED" for item in results)
    assert any(item.code == "FILENAME_TOO_LONG" for item in results)
    assert any(item.code == "MAX_FILES_EXCEEDED" for item in results)


def test_pdfa_required_blocks_or_requires_manual_review(tmp_path: Path) -> None:
    invalid_pdf = _pdf(tmp_path / "atto_non_pdfa.pdf", pdfa=False)
    p7m = tmp_path / "atto.pdf.p7m"
    p7m.write_bytes(b"PKCS7 placeholder")
    profile = channel_profile_for("pat_siga")

    blocked = DocumentPreflightValidator().validate(
        documents=[DepositDocument(path=str(invalid_pdf), role="MAIN_ACT", filename=invalid_pdf.name, signed=True, signature_format="PADES")],
        profile=profile,
    )
    manual = DocumentPreflightValidator().validate(
        documents=[DepositDocument(path=str(p7m), role="MAIN_ACT", filename=p7m.name, signed=True, signature_format="CADES_BES")],
        profile=profile,
    )

    assert any(item.status == PreflightStatus.ERROR and item.code == "PDFA_REQUIRED" for item in blocked)
    assert any(item.code == "PDFA_NOT_VERIFIABLE_MANUAL_REVIEW" and item.manual_review_required for item in manual)


def test_l53_subject_and_receipt_complete_are_blocking() -> None:
    subject = _l53_payload()
    subject["oggetto_pec"] = "Notifica telematica - ricorso"
    receipt = _l53_payload()
    receipt["ricevuta_completa"] = False

    subject_result = validate_legal_notification(subject)
    receipt_result = validate_legal_notification(receipt)

    assert any("L53_SUBJECT_REQUIRED" in item for item in subject_result.blockers)
    assert any("RICEVUTA_COMPLETA_REQUIRED" in item for item in receipt_result.blockers)


def test_legacy_pct_notifica_rejects_wrong_subject_path() -> None:
    legacy = NotificaTelematica(ConfigPEC("studio@example.pec.it", "secret", "smtp.example.test"))
    relata = RelataDiNotifica(
        notificante="Avv. Mario Rossi",
        cf_notificante="RSSMRA80A01H501U",
        pec_notificante="studio@example.pec.it",
        destinatario="Controparte",
        cf_destinatario="01234567890",
        pec_destinatario="controparte@example.pec.it",
        atto_notificato="ricorso.pdf",
        data_ora="2026-05-12T10:30",
    )

    with pytest.raises(LegacyNotificaTelematicaDeprecata):
        legacy.notifica("ricorso.pdf", "controparte@example.pec.it", relata)


def test_pst_area_web_failed_notification_requires_lawyer_assessment() -> None:
    blocked = prepare_pst_failed_notification_workflow({"pec_non_consegnata": True})
    alternative = prepare_pst_failed_notification_workflow({
        "pec_non_consegnata": True,
        "valutazione_avvocato": "Errore casella mittente",
        "causa_imputabile_destinatario": False,
    })

    assert any("LAWYER_ASSESSMENT_REQUIRED" in item for item in blocked.blockers)
    assert alternative.ok is True
    assert "Non dichiarare perfezionata" in alternative.body


def test_evidence_pack_contains_required_files_and_hashes() -> None:
    payload = {
        "atto_notificato": "atto.pdf",
        "atto_sha256": "a" * 64,
        "relata_firmata": "relata.pdf.p7m",
        "relata_sha256": "b" * 64,
        "pec_inviata": "pec_inviata.eml",
        "pec_inviata_sha256": "c" * 64,
        "destinatario_nome": "Controparte",
        "rac_file": "accettazione.eml",
        "rac_sha256": "d" * 64,
        "rdac_file": "consegna.eml",
        "rdac_sha256": "e" * 64,
    }

    pack = build_notification_evidence_pack(payload)

    assert pack["missing"] == []
    assert {"atto", "relata_firmata", "pec_inviata", "rac", "rdac_completa", "log_json", "distinta_prova_notifica", "scheda_esito"}.issubset(pack["hashes"])
