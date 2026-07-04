"""Test della CLI del ciclo autonomo: exit code e comportamenti governati."""

from __future__ import annotations

import json


from lex.autonomy.cli import main

_CONFIG_OK = {
    "mode": "offline",
    "allow_web": False,
    "limits": {"max_cycles": 2, "max_queries": 20, "max_sources": 6},
    "sources": {
        "require_official_sources": True,
        "source_mode": "strict",
        "allowlist": ["normattiva.it", "eur-lex.europa.eu"],
    },
    "memory": {"dir": None},
    "offline_results": {
        "art. 2043 c.c. site:normattiva.it": [
            {
                "url": "https://www.normattiva.it/uri-res/N2Ls?urn:cc-art2043",
                "title": "Art. 2043 c.c.",
                "content": "Art. 2043 c.c. Risarcimento per fatto illecito: il danno ingiusto obbliga al risarcimento.",
            }
        ]
    },
}
_SAMPLES_OK = {
    "schema_version": "iusentra.lex_legal_samples.v1",
    "samples": [
        {
            "sample_id": "civ",
            "area": "civile",
            "title": "Responsabilità",
            "text": "Ai sensi dell'art. 2043 c.c. il danno ingiusto obbliga al risarcimento del danno.",
        }
    ],
}


def _write(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_exit_0_con_config_e_campioni_validi(tmp_path, capsys):
    config = _write(tmp_path, "config.json", _CONFIG_OK)
    samples = _write(tmp_path, "samples.json", _SAMPLES_OK)
    memoria = tmp_path / "memoria"
    exit_code = main(["--config", str(config), "--samples", str(samples), "--memory-dir", str(memoria), "--report", "text"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Ciclo di apprendimento autonomo Lex" in output
    assert (memoria / "research_questions.jsonl").exists()


def test_exit_0_report_json(tmp_path, capsys):
    config = _write(tmp_path, "config.json", _CONFIG_OK)
    samples = _write(tmp_path, "samples.json", _SAMPLES_OK)
    exit_code = main(
        ["--config", str(config), "--samples", str(samples), "--memory-dir", str(tmp_path / "memoria"), "--report", "json"]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "offline"
    assert payload["queries_executed"] >= 1


def test_exit_1_config_mancante_o_rotta(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "assente.json")]) == 1
    broken = tmp_path / "rotta.json"
    broken.write_text("{non json", encoding="utf-8")
    assert main(["--config", str(broken)]) == 1
    assert "Errore" in capsys.readouterr().err


def test_exit_1_web_senza_allowlist(tmp_path, capsys):
    raw = json.loads(json.dumps(_CONFIG_OK))
    raw["mode"] = "web"
    raw["allow_web"] = True
    raw["sources"]["allowlist"] = []
    config = _write(tmp_path, "config.json", raw)
    assert main(["--config", str(config)]) == 1
    assert "allowlist" in capsys.readouterr().err


def test_exit_1_campioni_rotti(tmp_path):
    config = _write(tmp_path, "config.json", _CONFIG_OK)
    samples = _write(tmp_path, "samples.json", {"samples": []})
    assert main(["--config", str(config), "--samples", str(samples)]) == 1


def test_exit_2_provider_vuoto_su_memoria_vergine(tmp_path, capsys):
    raw = json.loads(json.dumps(_CONFIG_OK))
    raw["offline_results"] = {}
    config = _write(tmp_path, "config.json", raw)
    samples = _write(tmp_path, "samples.json", _SAMPLES_OK)
    exit_code = main(["--config", str(config), "--samples", str(samples), "--memory-dir", str(tmp_path / "memoria")])
    assert exit_code == 2
    assert "Errore fonti" in capsys.readouterr().err


def test_exit_3_errore_del_ciclo(tmp_path, capsys, monkeypatch):
    import lex.autonomy.cli as cli_module

    def _esplode(**kwargs):
        raise RuntimeError("guasto simulato")

    monkeypatch.setattr(cli_module, "run_autonomous_cycle", _esplode)
    config = _write(tmp_path, "config.json", _CONFIG_OK)
    samples = _write(tmp_path, "samples.json", _SAMPLES_OK)
    assert main(["--config", str(config), "--samples", str(samples), "--memory-dir", str(tmp_path / "memoria")]) == 3
    assert "Errore del ciclo" in capsys.readouterr().err


def test_dry_run_non_scrive(tmp_path):
    config = _write(tmp_path, "config.json", _CONFIG_OK)
    samples = _write(tmp_path, "samples.json", _SAMPLES_OK)
    memoria = tmp_path / "memoria"
    assert main(["--config", str(config), "--samples", str(samples), "--memory-dir", str(memoria), "--dry-run"]) == 0
    assert not memoria.exists()


def test_allow_web_flag_non_basta_senza_config_coerente(tmp_path, capsys):
    # --allow-web forza allow_web=true, ma mode resta offline → incoerenza → exit 1.
    config = _write(tmp_path, "config.json", _CONFIG_OK)
    assert main(["--config", str(config), "--allow-web"]) == 1
    assert "incoerente" in capsys.readouterr().err.casefold()


def test_config_web_di_esempio_valida_e_governata():
    # Guardia contro drift: la config web committata deve restare valida e con
    # domini classificati nei tier del Source Policy System (fonti certe).
    import json
    from pathlib import Path

    from lex.autonomy.safety import validate_cycle_config
    from lex.research.source_policy.inference import get_tier_for_domain

    raw = json.loads(Path("examples/lex_autonomous_config_web.json").read_text(encoding="utf-8"))
    config = validate_cycle_config(raw)
    assert config.mode == "web"
    assert config.allow_web is True
    assert config.respect_robots is True
    assert config.min_interval_seconds >= 1.0
    assert len(config.allowlist) >= 15
    aree = ("civile", "penale", "lavoro", "tributario", "amministrativo", "privacy", "ue")
    for dominio in config.allowlist:
        tiers = {get_tier_for_domain(dominio, area).value for area in aree}
        assert tiers & {"tier_1", "tier_2"}, f"dominio fuori dai tier governati: {dominio}"
