from __future__ import annotations

from pathlib import Path

from legal_deposit.busta.package_builder import ChannelPackageBuilder
from legal_deposit.models import DepositDocument, PreflightStatus
from legal_deposit.office_rules import resolve_office_rule
from legal_deposit.penal_rules import (
    classify_penal_deposit,
    legacy_pdp_ministry_status,
    normalize_pdp_ministry_status,
)
from legal_deposit.policies import channel_profile_for, list_channel_profiles
from legal_deposit.store import DepositRepository
from legal_deposit.validators import DocumentPreflightValidator


def _pdf(path: Path) -> Path:
    path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 0>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    return path


def test_channel_profiles_cover_required_channels() -> None:
    codes = {profile.id for profile in list_channel_profiles()}
    assert {
        "pct_pst",
        "pec_stragiudiziale",
        "notifiche_pec",
        "pat_siga",
        "ptt_sigit",
        "pdp_penale",
        "upload_manuale_guidato",
        "portal_upload",
    }.issubset(codes)


def test_palmi_cades_p7m_gets_strong_warning(tmp_path: Path) -> None:
    p7m = tmp_path / "istanza.pdf.p7m"
    p7m.write_bytes(b"PKCS7 placeholder")
    document = DepositDocument(
        path=str(p7m),
        role="MAIN_ACT",
        filename=p7m.name,
        signed=True,
        signature_format="CADES_BES",
    )

    results = DocumentPreflightValidator().validate(
        documents=[document],
        profile=channel_profile_for("pdp_penale"),
        office_name="Tribunale di Palmi",
    )

    assert any(result.code == "PALMI_PREFERS_PADES" for result in results)
    assert not any(result.status == PreflightStatus.ERROR for result in results)


def test_palmi_pades_pdf_is_allowed(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path / "istanza.pdf")
    document = DepositDocument(
        path=str(pdf),
        role="MAIN_ACT",
        filename=pdf.name,
        signed=True,
        signature_format="PADES",
    )

    results = DocumentPreflightValidator().validate(
        documents=[document],
        profile=channel_profile_for("pdp_penale"),
        office_name="Tribunale di Palmi",
    )

    assert any(result.code == "PADES_OK" for result in results)
    assert not any(result.code == "PALMI_PREFERS_PADES" for result in results)
    assert not any(result.status == PreflightStatus.ERROR for result in results)


def test_other_office_cades_p7m_allowed_without_palmi_warning(tmp_path: Path) -> None:
    p7m = tmp_path / "memoria.pdf.p7m"
    p7m.write_bytes(b"PKCS7 placeholder")
    document = DepositDocument(
        path=str(p7m),
        role="MAIN_ACT",
        filename=p7m.name,
        signed=True,
        signature_format="CADES_BES",
    )

    results = DocumentPreflightValidator().validate(
        documents=[document],
        profile=channel_profile_for("pdp_penale"),
        office_name="Tribunale di Milano",
    )

    assert not any(result.code == "PALMI_PREFERS_PADES" for result in results)
    assert not any(result.status == PreflightStatus.ERROR for result in results)


def test_verified_other_offices_do_not_inherit_palmi_rule() -> None:
    for office in ("Procura di Locri", "Procura di Taranto", "Procura di Bari"):
        rule = resolve_office_rule(office)
        assert rule["pdp_signature_preference"] == "either"
        assert rule["cades_severity"] == "info"


def test_penal_instance_art_299_uses_pdp() -> None:
    result = classify_penal_deposit("Istanza ex art. 299 c.p.p. per revoca misura cautelare")
    assert result.category == "istanza_misure_cautelari_o_sequestri"
    assert result.channel == "pdp_penale"


def test_reclamo_410_bis_has_separate_category() -> None:
    result = classify_penal_deposit("Reclamo ex art. 410-bis c.p.p.")
    assert result.category == "reclamo_410_bis_cpp"
    assert result.channel == "pdp_penale"


def test_incidente_esecuzione_requires_local_channel_review() -> None:
    result = classify_penal_deposit("Incidente di esecuzione ex artt. 666 ss. c.p.p.")
    assert result.category == "incidente_esecuzione_666_ss_cpp"
    assert result.requires_local_channel_review is True


def test_pdp_status_normalization_keeps_legacy_storage_safe() -> None:
    assert normalize_pdp_ministry_status("IN_VERIFICA") == "IN_FASE_DI_VERIFICA"
    assert legacy_pdp_ministry_status("ACCOLTO") == "ACCETTATO"


def test_package_builder_uses_channel_profile(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path / "atto.pdf")
    document = DepositDocument(
        path=str(pdf),
        role="MAIN_ACT",
        filename=pdf.name,
        signed=True,
        signature_format="PADES",
    )
    profile = channel_profile_for("pat_siga")
    results = DocumentPreflightValidator().validate(documents=[document], profile=profile)

    package = ChannelPackageBuilder().build(
        output_root=tmp_path / "out",
        job_id="DEP-TEST",
        tenant_id="tenant-1",
        fascicolo_id="FASC-1",
        channel=profile,
        documents=[document],
        preflight=results,
    )

    assert package.channel == "pat_siga"
    assert package.requires_manual_final_upload is True
    assert Path(package.manifest_path).exists()
    assert Path(package.xml_path).name == "metadati_pat.xml"
    assert Path(package.zip_path).exists()


def test_deposit_repository_creates_minimum_tables(tmp_path: Path) -> None:
    repo = DepositRepository(tmp_path / "depositi.sqlite")
    repo.save_job(
        job_id="DEP-1",
        tenant_id="tenant-1",
        fascicolo_id="FASC-1",
        channel="pdp_penale",
        status="AWAITING_USER_CONFIRMATION",
        created_by="user-1",
        metadata={"canale": "pdp_penale"},
    )
    repo.save_package(
        package_id="PKG-1",
        job_id="DEP-1",
        manifest_path="/tmp/manifest.json",
        zip_path="/tmp/package.zip",
    )
    repo.add_audit(
        tenant_id="tenant-1",
        job_id="DEP-1",
        user_id="user-1",
        action="prepare",
        before="DRAFT",
        after="AWAITING_USER_CONFIRMATION",
    )

    with repo._connect() as conn:  # noqa: SLF001 - schema smoke test mirato.
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'deposit_%'"
            )
        }

    assert {
        "deposit_jobs",
        "deposit_documents",
        "deposit_packages",
        "deposit_receipts",
        "deposit_audit_logs",
        "deposit_alerts",
    }.issubset(tables)
