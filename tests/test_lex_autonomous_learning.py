"""E2E offline del ciclo di apprendimento autonomo di Lex (zero rete garantito)."""

from __future__ import annotations

import json
import socket

import pytest

from lex.autonomy import StaticSearchProvider, run_autonomous_cycle, validate_cycle_config
from lex.learning.models import LegalSourceSample

_OFFLINE_RESULTS = {
    "art. 2043 c.c. site:normattiva.it": [
        {
            "url": "https://www.normattiva.it/uri-res/N2Ls?urn:cc-art2043",
            "title": "Art. 2043 c.c.",
            "source_id": "normattiva",
            "content": (
                "Art. 2043 c.c. Risarcimento per fatto illecito. Qualunque fatto doloso o colposo che "
                "cagiona ad altri un danno ingiusto obbliga al risarcimento. La responsabilità civile "
                "richiede il nesso causale."
            ),
        }
    ],
    "art. 6 Regolamento (UE) 2016/679 site:eur-lex.europa.eu": [
        {
            "url": "https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679",
            "title": "Regolamento (UE) 2016/679 — Articolo 6",
            "source_id": "eurlex",
            "content": (
                "Articolo 6 Regolamento (UE) 2016/679: liceità del trattamento dati. Consenso "
                "dell'interessato o legittimo interesse del titolare del trattamento."
            ),
        }
    ],
}


@pytest.fixture()
def _niente_rete(monkeypatch):
    """Qualsiasi tentativo di rete fa fallire il test (l'offline è offline davvero)."""

    def _bloccato(*args, **kwargs):
        raise AssertionError("Chiamata di rete vietata nel ciclo offline")

    monkeypatch.setattr(socket, "getaddrinfo", _bloccato)
    monkeypatch.setattr(socket, "create_connection", _bloccato)


def _config(tmp_path, **limit_overrides):
    limits = {"max_cycles": 3, "max_queries": 30, "max_sources": 6, "max_runtime_seconds": 300}
    limits.update(limit_overrides)
    return validate_cycle_config(
        {
            "mode": "offline",
            "allow_web": False,
            "limits": limits,
            "sources": {
                "require_official_sources": True,
                "source_mode": "strict",
                "allowlist": ["normattiva.it", "eur-lex.europa.eu", "garanteprivacy.it"],
            },
            "memory": {"dir": str(tmp_path / "lex_memory")},
            "offline_results": _OFFLINE_RESULTS,
        }
    )


def _samples():
    return [
        LegalSourceSample(
            sample_id="civile_art_2043",
            title="Responsabilità extracontrattuale",
            area="civile",
            text=(
                "Ai sensi dell'art. 2043 c.c. qualunque fatto doloso o colposo che cagiona ad altri un "
                "danno ingiusto obbliga al risarcimento del danno. L'accesso civico non c'entra qui, ma "
                "l'accesso civico ricorre tre volte: accesso civico."
            ),
        ),
        LegalSourceSample(
            sample_id="privacy_gdpr_art_6",
            title="Basi giuridiche",
            area="privacy",
            text="L'art. 6 GDPR disciplina il consenso e il legittimo interesse del titolare per il trattamento dati.",
        ),
    ]


def test_ciclo_offline_completo(tmp_path, _niente_rete):
    config = _config(tmp_path)
    result = run_autonomous_cycle(
        config=config,
        samples=_samples(),
        search_provider=StaticSearchProvider(config.offline_results),
        now_fn=lambda: 0.0,
        iso_now=lambda: "2026-07-02T10:00:00+00:00",
    )

    memoria = tmp_path / "lex_memory"
    # Memoria scritta e non vuota per le collezioni chiave.
    for name in ("research_questions", "legal_terms", "citations", "unknown_concepts", "source_readings", "improvement_proposals"):
        path = memoria / f"{name}.jsonl"
        assert path.exists() and path.read_text(encoding="utf-8").strip(), f"collezione vuota: {name}"
    assert (memoria / "concept_graph.json").exists()
    assert list((memoria / "cycle_reports").glob("cycle_*.json"))

    # Budget e contatori coerenti con i limiti.
    assert result.cycles_run <= config.max_cycles
    assert result.queries_executed <= config.max_queries
    assert result.sources_fetched <= config.max_sources
    assert result.questions_generated > 0
    assert result.new_citations > 0
    assert result.new_readings >= 2  # normattiva + eur-lex letti offline

    # Ogni proposta resta in revisione umana; P4 scatta su "accesso civico".
    proposte = [
        json.loads(line)["payload"]
        for line in (memoria / "improvement_proposals.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert proposte
    assert all(p["requires_human_review"] is True for p in proposte)
    assert any("accesso civico" in p["title"] for p in proposte)

    # Le letture hanno registrato le norme: le lacune R1 corrispondenti si chiudono.
    letture = [
        json.loads(line)["payload"]
        for line in (memoria / "source_readings.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    norme_lette = {norma.casefold() for lettura in letture for norma in lettura["citations_normalized"]}
    assert "art. 2043 c.c." in norme_lette  # confronto casefold: come fa il gap detector (R1)


def test_seconda_run_converge_senza_nuove_informazioni(tmp_path, _niente_rete):
    config = _config(tmp_path)
    provider = StaticSearchProvider(config.offline_results)
    first = run_autonomous_cycle(
        config=config, samples=_samples(), search_provider=provider, now_fn=lambda: 0.0, iso_now=lambda: "2026-07-02T10:00:00+00:00"
    )
    assert first.new_citations > 0
    second = run_autonomous_cycle(
        config=config, samples=_samples(), search_provider=provider, now_fn=lambda: 0.0, iso_now=lambda: "2026-07-02T11:00:00+00:00"
    )
    # Dedup totale: la memoria non cresce e il ciclo dichiara la convergenza.
    assert second.stop_reason == "no_new_information"
    assert second.new_terms == 0
    assert second.new_citations == 0
    assert second.new_readings == 0


def test_max_runtime_ferma_il_ciclo(tmp_path, _niente_rete):
    config = _config(tmp_path, max_runtime_seconds=5)
    clock = {"value": 0.0}

    def _now():
        clock["value"] += 3.0  # ogni controllo di runtime avanza il clock finto
        return clock["value"]

    result = run_autonomous_cycle(
        config=config,
        samples=_samples(),
        search_provider=StaticSearchProvider(config.offline_results),
        now_fn=_now,
        iso_now=lambda: "2026-07-02T10:00:00+00:00",
    )
    assert result.stop_reason == "max_runtime"


def test_dry_run_non_scrive_nulla(tmp_path, _niente_rete):
    config = _config(tmp_path)
    config.dry_run = True
    result = run_autonomous_cycle(
        config=config,
        samples=_samples(),
        search_provider=StaticSearchProvider(config.offline_results),
        now_fn=lambda: 0.0,
        iso_now=lambda: "2026-07-02T10:00:00+00:00",
    )
    assert result.questions_generated > 0
    assert not (tmp_path / "lex_memory").exists()
