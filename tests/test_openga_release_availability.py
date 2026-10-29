"""L'indisponibilità autorizzata non è lettura e non copre altre fonti o errori."""
import copy
import json
from types import SimpleNamespace

import pytest

from deploy.openga import update_worker as worker
from deploy.openga.verify_reading import (
    MISSING_PAGE_SHA256, UNAVAILABLE_IDENTITY, UNAVAILABLE_REFERENCE,
    expected_unavailability,
)


def unavailable():
    return {"stato": "non_trovato", "fonte_indisponibile_verificata": True,
            "lettura_confermata": False, "caratteri": 0,
            "approvazione_automatica": False, "scritture_dati_studio": False,
            "coda_persistente_verificata": True, "html_consultabile_verificato": False,
            "diagnostica": [{"variante": s, "stato_http": 200, "trasporto": "ok",
                "byte": 1535, "sha256": MISSING_PAGE_SHA256,
                "rifiuto": "Data di pubblicazione HTML assente o ambigua."}
                for s in ("01", "20", "11")]}


def read_proof():
    return {"stato": "acquisito", "lettura_confermata": True, "caratteri": 1000,
            "coda_persistente_verificata": True, "html_consultabile_verificato": True,
            "approvazione_automatica": False, "scritture_dati_studio": False}


def test_only_the_authorized_reference_and_official_error_fingerprint_are_accepted():
    result = unavailable()
    before = copy.deepcopy(result)
    assert expected_unavailability(UNAVAILABLE_IDENTITY, UNAVAILABLE_REFERENCE, result)
    assert result == before and result["lettura_confermata"] is False
    for key in UNAVAILABLE_REFERENCE:
        reference = dict(UNAVAILABLE_REFERENCE, **{key: "different"})
        assert not expected_unavailability(UNAVAILABLE_IDENTITY, reference, result)
    for key in UNAVAILABLE_IDENTITY:
        identity = dict(UNAVAILABLE_IDENTITY, **{key: "different"})
        assert not expected_unavailability(identity, UNAVAILABLE_REFERENCE, result)


@pytest.mark.parametrize("field,value", [
    ("stato_http", 403), ("stato_http", 429), ("stato_http", 503),
    ("trasporto", "network_error"), ("trasporto", "robots_blocked"),
    ("sha256", "a" * 64), ("byte", 1534), ("variante", "02"), ("rifiuto", ""),
])
def test_other_pages_transport_failures_and_access_limits_are_never_waived(field, value):
    result = unavailable()
    result["diagnostica"][0][field] = value
    assert not expected_unavailability(UNAVAILABLE_IDENTITY, UNAVAILABLE_REFERENCE, result)


@pytest.mark.parametrize("field,value", [
    ("stato", "intervento_necessario"), ("stato", "in_corso"), ("stato", "acquisito"),
    ("documento", {"testo": "fake"}), ("approvazione_automatica", True),
    ("approvazione_avvocato", True), ("lettura_confermata", True),
    ("diagnostica", []), ("diagnostica", None), ("diagnostica", [{"sha256": MISSING_PAGE_SHA256}]),
])
def test_no_document_no_approval_and_all_three_observations_are_required(field, value):
    result = unavailable()
    result[field] = value
    assert not expected_unavailability(UNAVAILABLE_IDENTITY, UNAVAILABLE_REFERENCE, result)


def release_case(tmp_path, monkeypatch, *, duplicate=False, missing=None, positive=None):
    refs = [{"relazione_id": "roma-one", "resource_id": "r1", "resource_sha256": "a" * 64},
            {"relazione_id": "roma-two", "resource_id": "r2", "resource_sha256": "b" * 64},
            dict(UNAVAILABLE_REFERENCE)]
    if duplicate:
        refs[1] = dict(refs[0])
    monkeypatch.setattr(worker, "command", lambda *args: json.dumps(refs))
    monkeypatch.setattr(worker, "request", lambda *args: {
        "ok": True, "identita": dict(UNAVAILABLE_IDENTITY) if args[-1] == refs[-1] else {"sede": "003"}})
    p = tmp_path / "deploy/openga/verify_reading.py"
    p.parent.mkdir(parents=True)
    p.write_text("public verification")
    responses = iter([positive or read_proof(), read_proof(), missing or unavailable()])
    monkeypatch.setattr(worker.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(next(responses))))
    return worker.verify_reading(tmp_path, "candidate")


def test_release_counts_two_reads_and_one_unavailable_source_separately(tmp_path, monkeypatch, capsys):
    proofs = release_case(tmp_path, monkeypatch)
    assert [p["lettura_confermata"] for p in proofs] == [True, True, False]
    output = capsys.readouterr().out
    assert output.count("LETTURA_UFFICIALE_SERVER_JSON=") == 2
    assert output.count("FONTE_INDISPONIBILE_SERVER_JSON=") == 1


@pytest.mark.parametrize("field,value", [
    ("lettura_confermata", True), ("html_consultabile_verificato", True),
    ("coda_persistente_verificata", False), ("caratteri", 1000),
    ("approvazione_automatica", True), ("scritture_dati_studio", True),
])
def test_release_rejects_a_fake_read_or_false_unavailability_proof(tmp_path, monkeypatch, field, value):
    missing = unavailable()
    missing[field] = value
    with pytest.raises(ValueError, match="coda"):
        release_case(tmp_path, monkeypatch, missing=missing)


def test_release_requires_two_distinct_real_reads(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="due letture"):
        release_case(tmp_path, monkeypatch, duplicate=True)


def test_a_restored_official_source_must_pass_the_normal_reading_checks(tmp_path, monkeypatch, capsys):
    proofs = release_case(tmp_path, monkeypatch, missing=read_proof())
    assert all(p["lettura_confermata"] for p in proofs)
    assert "FONTE_INDISPONIBILE_SERVER_JSON=" not in capsys.readouterr().out


def test_an_incomplete_other_read_still_blocks_release(tmp_path, monkeypatch):
    positive = read_proof()
    positive["caratteri"] = 1
    with pytest.raises(ValueError, match="coda"):
        release_case(tmp_path, monkeypatch, positive=positive)
