"""Test del Compliance Cockpit: conflitti, KYC e registro decisioni firmato."""

from __future__ import annotations

from datetime import date

from pct.compliance import (
    ComplianceDecisionLog,
    ExistingParty,
    IdentityDocument,
    KycFactors,
    KycRecord,
    Party,
    RiskLevel,
    assess_risk,
    build_conflict_report,
    document_expiry_status,
)


# ---------------------------------------------------------------- Conflitti

def test_conflitto_diretto_quando_nuovo_cliente_e_gia_controparte():
    existing = [ExistingParty(name="Beta S.r.l.", codice_fiscale="01234567890", role="controparte", matter_id="F-1")]
    report = build_conflict_report(
        Party(name="Beta S.r.l.", codice_fiscale="01234567890", role="cliente"),
        None,
        existing,
    )
    assert report.has_direct is True
    assert report.clear is False
    assert report.findings[0].matter_id == "F-1"


def test_conflitto_diretto_quando_controparte_e_gia_nostro_cliente():
    existing = [ExistingParty(name="Mario Rossi", codice_fiscale="RSSMRA80A01H501U", role="cliente", matter_id="F-2")]
    report = build_conflict_report(
        Party(name="Acme S.p.A.", codice_fiscale="99999999999", role="cliente"),
        Party(name="Mario Rossi", codice_fiscale="RSSMRA80A01H501U", role="controparte"),
        existing,
    )
    assert report.has_direct is True


def test_conflitto_potenziale_per_stesso_gruppo():
    existing = [ExistingParty(name="Gamma Srl", group="Gruppo Delta", role="controparte", matter_id="F-3")]
    report = build_conflict_report(
        Party(name="Epsilon Srl", group="Gruppo Delta", role="cliente"),
        None,
        existing,
    )
    assert report.has_direct is False
    assert report.has_potential is True


def test_nessun_conflitto():
    existing = [ExistingParty(name="Tizio", codice_fiscale="TZITZI80A01H501U", role="controparte", matter_id="F-4")]
    report = build_conflict_report(Party(name="Caio", codice_fiscale="CAICAI80A01H501U"), None, existing)
    assert report.clear is True
    assert report.to_public()["findings"] == []


def test_match_solo_per_nome_e_potenziale_non_diretto():
    existing = [ExistingParty(name="Mario Rossi", role="controparte", matter_id="F-5")]  # senza CF
    report = build_conflict_report(Party(name="mario  rossi"), None, existing)
    assert report.has_potential is True
    assert report.has_direct is False


# ---------------------------------------------------------------- KYC / AML

def test_assess_risk_livelli():
    assert assess_risk(KycFactors())[0] == RiskLevel.BASSO
    medio = assess_risk(KycFactors(paese_alto_rischio=True))
    assert medio[0] == RiskLevel.MEDIO
    alto = assess_risk(KycFactors(pep=True, uso_contante_elevato=True))
    assert alto[0] == RiskLevel.ALTO
    assert any("PEP" in r for r in alto[2])


def test_documento_scaduto_in_scadenza_valido():
    today = date(2026, 6, 11)
    assert document_expiry_status(IdentityDocument(numero="X", scadenza="2025-01-01"), today=today)["stato"] == "scaduto"
    assert document_expiry_status(IdentityDocument(numero="X", scadenza="2026-06-20"), today=today)["stato"] == "in_scadenza"
    assert document_expiry_status(IdentityDocument(numero="X", scadenza="2030-01-01"), today=today)["stato"] == "valido"
    assert document_expiry_status(IdentityDocument())["stato"] == "non_indicato"


def test_kyc_record_adeguata_verifica_e_rafforzata():
    rec = KycRecord(
        cliente_id="CLI-1",
        factors=KycFactors(persona_giuridica=True, titolare_effettivo_identificato=False, pep=True, uso_contante_elevato=True),
        document=IdentityDocument(tipo="passaporto", numero="P1", scadenza="2030-01-01"),
    )
    out = rec.assess(today=date(2026, 6, 11))
    assert out["livelloRischio"] == "alto"
    assert out["verificaRafforzataRichiesta"] is True
    # Titolare effettivo non identificato per persona giuridica -> verifica non completa.
    assert out["adeguataVerificaCompleta"] is False


def test_kyc_documento_scaduto_blocca_adeguata_verifica():
    rec = KycRecord(
        cliente_id="CLI-2",
        factors=KycFactors(),
        document=IdentityDocument(tipo="carta_identita", numero="C1", scadenza="2020-01-01"),
    )
    out = rec.assess(today=date(2026, 6, 11))
    assert out["documento"]["stato"] == "scaduto"
    assert out["adeguataVerificaCompleta"] is False


# ---------------------------------------------------------------- Registro decisioni

def test_registro_decisioni_append_only_e_catena_integra(tmp_path):
    log = ComplianceDecisionLog(tmp_path / "decisioni.jsonl")
    log.record_decision(tenant_id="studio-a", actor_id="avv1", kind="conflict_waiver", subject_ref="F-1", decision="approvato", rationale="Consenso informato acquisito.")
    log.record_decision(tenant_id="studio-a", actor_id="avv1", kind="kyc_outcome", subject_ref="CLI-1", decision="rinviato", rationale="In attesa titolare effettivo.")
    log.record_decision(tenant_id="studio-b", actor_id="avv2", kind="gdpr", subject_ref="CLI-9", decision="approvato", rationale="Conservazione 10 anni.")

    assert len(log.list_decisions()) == 3
    assert len(log.list_decisions(tenant_id="studio-a")) == 2
    assert log.verify_chain() is True


def test_registro_decisioni_rileva_manomissione(tmp_path):
    path = tmp_path / "decisioni.jsonl"
    log = ComplianceDecisionLog(path)
    log.record_decision(tenant_id="studio-a", actor_id="avv1", kind="kyc_outcome", subject_ref="CLI-1", decision="approvato", rationale="OK")
    log.record_decision(tenant_id="studio-a", actor_id="avv1", kind="kyc_outcome", subject_ref="CLI-2", decision="approvato", rationale="OK2")
    assert log.verify_chain() is True

    # Manomissione: cambio l'esito di una voce mantenendo il vecchio hash.
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = lines[0].replace('"approvato"', '"rifiutato"')
    path.write_text("\n".join([tampered, lines[1]]) + "\n", encoding="utf-8")
    assert log.verify_chain() is False
