"""Test accesso sicuro Portale Cliente: magic-link monouso + OTP a tentativi limitati."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pct.client_portal_access import (
    InMemoryAccessStore,
    PortalAccessManager,
    constant_time_match,
    generate_otp,
    hash_secret,
)

NOW = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)


def _manager(**kwargs) -> PortalAccessManager:
    return PortalAccessManager(InMemoryAccessStore(), pepper="test-pepper", **kwargs)


def test_hash_e_confronto_tempo_costante():
    h = hash_secret("segreto", pepper="p")
    assert h and "segreto" not in h
    assert constant_time_match("segreto", h, pepper="p") is True
    assert constant_time_match("altro", h, pepper="p") is False
    assert constant_time_match("", h, pepper="p") is False


def test_otp_ha_lunghezza_attesa_ed_e_numerico():
    code = generate_otp(6)
    assert len(code) == 6 and code.isdigit()


def test_flusso_completo_magic_link_poi_otp_concede_accesso():
    mgr = _manager()
    grant_id, token = mgr.issue_magic_link(tenant_id="studio-a", client_id="C-1", matter_id="F-1", now=NOW)

    started = mgr.start_otp(grant_id, token, now=NOW)
    assert started.ok is True
    assert started.otp_code and started.otp_code.isdigit()

    granted = mgr.verify_otp(grant_id, started.otp_code, now=NOW)
    assert granted.ok is True
    assert granted.reason == "accesso_concesso"


def test_magic_link_e_monouso():
    mgr = _manager()
    grant_id, token = mgr.issue_magic_link(tenant_id="t", client_id="C", now=NOW)
    assert mgr.start_otp(grant_id, token, now=NOW).ok is True
    # secondo uso dello stesso magic-link: rifiutato
    second = mgr.start_otp(grant_id, token, now=NOW)
    assert second.ok is False
    assert second.reason == "magic_link_gia_usato"


def test_magic_link_scaduto():
    mgr = _manager(magic_ttl_minutes=15)
    grant_id, token = mgr.issue_magic_link(tenant_id="t", client_id="C", now=NOW)
    later = NOW + timedelta(minutes=16)
    res = mgr.start_otp(grant_id, token, now=later)
    assert res.ok is False and res.reason == "magic_link_scaduto"


def test_token_errato_rifiutato():
    mgr = _manager()
    grant_id, _token = mgr.issue_magic_link(tenant_id="t", client_id="C", now=NOW)
    res = mgr.start_otp(grant_id, "token-sbagliato", now=NOW)
    assert res.ok is False and res.reason == "token_non_valido"


def test_otp_errato_incrementa_e_blocca_dopo_soglia():
    mgr = _manager(max_otp_attempts=3)
    grant_id, token = mgr.issue_magic_link(tenant_id="t", client_id="C", now=NOW)
    started = mgr.start_otp(grant_id, token, now=NOW)
    real = started.otp_code

    # 3 tentativi errati -> blocco
    r1 = mgr.verify_otp(grant_id, "000000" if real != "000000" else "111111", now=NOW)
    r2 = mgr.verify_otp(grant_id, "000001" if real != "000001" else "111112", now=NOW)
    assert r1.ok is False and r1.locked is False
    assert r2.ok is False and r2.locked is False
    r3 = mgr.verify_otp(grant_id, "000002" if real != "000002" else "111113", now=NOW)
    assert r3.ok is False and r3.locked is True

    # Anche l'OTP corretto ora è respinto: la sfida è bloccata.
    blocked = mgr.verify_otp(grant_id, real, now=NOW)
    assert blocked.ok is False and blocked.locked is True


def test_otp_scaduto_rifiutato():
    mgr = _manager(otp_ttl_minutes=10)
    grant_id, token = mgr.issue_magic_link(tenant_id="t", client_id="C", now=NOW)
    started = mgr.start_otp(grant_id, token, now=NOW)
    later = NOW + timedelta(minutes=11)
    res = mgr.verify_otp(grant_id, started.otp_code, now=later)
    assert res.ok is False and res.reason == "otp_scaduto"


def test_grant_inesistente_e_revoca():
    mgr = _manager()
    assert mgr.start_otp("inesistente", "x", now=NOW).reason == "grant_non_trovato"
    grant_id, token = mgr.issue_magic_link(tenant_id="t", client_id="C", now=NOW)
    assert mgr.revoke(grant_id) is True
    assert mgr.start_otp(grant_id, token, now=NOW).reason == "grant_revocato"


def test_nessun_segreto_in_chiaro_nello_store():
    store = InMemoryAccessStore()
    mgr = PortalAccessManager(store, pepper="p")
    grant_id, token = mgr.issue_magic_link(tenant_id="t", client_id="C", now=NOW)
    started = mgr.start_otp(grant_id, token, now=NOW)
    record = store.load_grant(grant_id)
    # né il token né l'OTP compaiono in chiaro nel record persistito
    assert token not in str(record)
    assert started.otp_code not in str(record)
    assert record["magic_hash"] and record["otp_hash"]
