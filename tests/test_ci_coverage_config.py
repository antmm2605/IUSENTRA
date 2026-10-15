from pathlib import Path
from copy import deepcopy

import pytest
import yaml

from tools.check_critical_coverage_regression import collect_shards, compare_measurements, select_artifact_names


def _deploy_proof(stamp, **changes):
    from tools.check_critical_coverage_regression import DEPLOY_ACCEPTANCE_STEPS
    result = {'name': 'Deploy su Hetzner CPX42', 'conclusion': 'success',
              'steps': [{'name': name, 'status': 'completed', 'conclusion': 'success',
                         'completed_at': stamp} for name in sorted(DEPLOY_ACCEPTANCE_STEPS)]}
    result.update(changes)
    return result


def _baseline_api(monkeypatch, runs, jobs, ci=None):
    import tools.check_critical_coverage_regression as gate

    calls = []

    def response(repo, endpoint):
        calls.append(endpoint)
        if endpoint.startswith('actions/workflows/deploy-hetzner.yml/runs?'):
            return {'workflow_runs': runs}
        if endpoint.startswith('actions/workflows/ci.yml/runs?'):
            return {'workflow_runs': ci or []}
        run_id = int(endpoint.split('/')[2])
        page = int(endpoint.rsplit('page=', 1)[1])
        records = jobs[run_id]
        return {'jobs': records[(page - 1) * 100:page * 100], 'total_count': len(records)}

    monkeypatch.setattr(gate, 'github_json', response)
    return calls


def test_coverage_baseline_skips_successful_workflow_without_real_deploy(monkeypatch):
    from tools.check_critical_coverage_regression import select_baseline
    runs = [{'id': 2, 'head_sha': 'b' * 40, 'updated_at': '2026-10-14T17:00:00Z'},
            {'id': 1, 'head_sha': 'a' * 40, 'updated_at': '2026-10-14T04:32:00Z'}]
    skipped = _deploy_proof('2026-10-14T17:00:00Z')
    skipped['steps'][0]['conclusion'] = 'skipped'
    _baseline_api(monkeypatch, runs, {2: [skipped], 1: [_deploy_proof('2026-10-14T04:31:00Z')]},
                  [{'id': 10, 'head_sha': 'a' * 40, 'updated_at': '2026-10-14T04:00:00Z'}])
    deploy, ci = select_baseline('example/repo', 'c' * 40)
    assert deploy['id'] == 1 and ci['id'] == 10


def test_coverage_baseline_rerun_does_not_replace_newer_actual_acceptance(monkeypatch):
    from tools.check_critical_coverage_regression import select_baseline
    runs = [{'id': 1, 'head_sha': 'a' * 40, 'updated_at': '2026-10-14T17:00:00Z'},
            {'id': 2, 'head_sha': 'b' * 40, 'updated_at': '2026-10-14T14:01:00Z'},
            {'id': 3, 'head_sha': 'd' * 40, 'updated_at': '2026-10-14T03:00:00Z'}]
    rerun = _deploy_proof('2026-10-14T17:00:00Z')
    for step in rerun['steps']:
        step['conclusion'] = 'skipped'
    calls = _baseline_api(monkeypatch, runs, {
        1: [_deploy_proof('2026-10-14T04:31:00Z'), rerun],
        2: [_deploy_proof('2026-10-14T14:00:00Z')],
    }, [{'id': 20, 'head_sha': 'b' * 40, 'updated_at': '2026-10-14T13:00:00Z'}])
    assert select_baseline('example/repo', 'c' * 40)[0]['id'] == 2
    assert not any('/runs/3/jobs?' in call for call in calls)


@pytest.mark.parametrize('defect', ['skipped', 'failure', 'missing', 'duplicate'])
def test_coverage_baseline_requires_complete_proof_in_one_job(monkeypatch, defect):
    from tools.check_critical_coverage_regression import select_baseline
    first = _deploy_proof('2026-10-14T04:31:00Z')
    if defect == 'missing':
        first['steps'].pop()
    elif defect == 'duplicate':
        first['steps'].append(deepcopy(first['steps'][0]))
    else:
        first['steps'][0]['conclusion'] = defect
    second = _deploy_proof('2026-10-14T04:31:00Z')
    second['steps'][1]['conclusion'] = 'skipped'
    _baseline_api(monkeypatch, [{'id': 1, 'head_sha': 'a' * 40, 'updated_at': '2026-10-14T04:32:00Z'}],
                  {1: [first, second]})
    with pytest.raises(ValueError, match='verifiche reali'):
        select_baseline('example/repo', 'c' * 40)


def test_coverage_actual_deploy_without_matching_ci_still_blocks(monkeypatch):
    from tools.check_critical_coverage_regression import select_baseline
    _baseline_api(monkeypatch, [{'id': 1, 'head_sha': 'a' * 40, 'updated_at': '2026-10-14T04:32:00Z'}],
                  {1: [_deploy_proof('2026-10-14T04:31:00Z')]},
                  [{'id': 10, 'head_sha': 'b' * 40, 'updated_at': '2026-10-14T04:00:00Z'}])
    with pytest.raises(ValueError, match='CI positiva sul medesimo commit'):
        select_baseline('example/repo', 'c' * 40)


def test_coverage_deploy_proofs_paginate_all_attempts(monkeypatch):
    from tools.check_critical_coverage_regression import verified_deployment_time
    records = [{'name': 'other', 'conclusion': 'success'} for _ in range(100)]
    records.append(_deploy_proof('2026-10-14T04:31:00Z'))
    calls = _baseline_api(monkeypatch, [], {1: records})
    assert verified_deployment_time('example/repo', 1).isoformat() == '2026-10-14T04:31:00+00:00'
    assert len(calls) == 2 and all('filter=all' in call for call in calls)


def _synthetic_measurement(covered=80):
    return {"shards": list(range(1, 13)), "environment": {
        "python": "3.12.15", "coverage": "7.16.2", "config_sha256": "config",
        "requirements_sha256": "requirements", "scope": ["lex"],
        "distributions_sha256": "frozen-packages",
    }, "files": {"lex/example.py": {"covered": covered, "statements": 100, "source_sha256": "a" * 64}}}


def test_coverage_regression_blocks_even_a_small_actual_drop():
    report = compare_measurements(_synthetic_measurement(80), _synthetic_measurement(79))
    assert report["blocking"] is True
    assert report["status"] == "regression"


def test_coverage_improvement_and_new_tests_preserve_the_same_perimeter():
    candidate = _synthetic_measurement(81)
    candidate["test_suite_sha256"] = "added-tests"
    report = compare_measurements(_synthetic_measurement(), candidate)
    assert report["blocking"] is False
    assert report["test_suite_changed"] is True


@pytest.mark.parametrize("key,value", [("python", "3.13.0"), ("config_sha256", "changed"),
                                      ("requirements_sha256", "changed"), ("scope", ["other"])])
def test_coverage_non_homogeneous_environment_is_explicitly_blocked(key, value):
    candidate = _synthetic_measurement(90)
    candidate["environment"][key] = value
    report = compare_measurements(_synthetic_measurement(), candidate)
    assert report["status"] == "non_homogeneous"
    assert report["blocking"] is True


def test_coverage_changed_source_keeps_the_same_perimeter_and_reports_the_drop():
    candidate = deepcopy(_synthetic_measurement(70))
    candidate["files"]["lex/example.py"]["source_sha256"] = "b" * 64
    report = compare_measurements(_synthetic_measurement(), candidate)
    assert report["status"] == "regression"
    assert report["changed_sources"] == ["lex/example.py"]


def test_coverage_added_module_is_reported_as_a_perimeter_change():
    candidate = _synthetic_measurement(80)
    candidate["files"]["lex/new.py"] = {"covered": 100, "statements": 100, "source_sha256": "b" * 64}
    report = compare_measurements(_synthetic_measurement(), candidate)
    assert report["status"] == "non_homogeneous"
    assert report["added_files"] == ["lex/new.py"]


@pytest.mark.parametrize("common,new_covered,expected", [(80, 80, False), (79, 100, True),
                                                       (90, 79, True), (81, 90, False)])
def test_declared_scope_addition_cannot_mask_regressions(common, new_covered, expected):
    candidate = _synthetic_measurement(common)
    candidate["files"]["lex/new.py"] = {"covered": new_covered, "statements": 100,
                                          "source_sha256": "b" * 64}
    declaration = {"reason": "Nuovo modulo con prove dedicate", "files": {"lex/new.py": "b" * 64}}
    report = compare_measurements(_synthetic_measurement(), candidate, declaration)
    assert report["blocking"] is expected
    assert report["common_candidate"]["covered"] == common
    assert report["added_measurements"]["lex/new.py"]["covered"] == new_covered


@pytest.mark.parametrize("mutation", ["hash", "extra", "environment", "removed", "reason"])
def test_declared_scope_addition_fails_closed(mutation):
    baseline = _synthetic_measurement()
    candidate = _synthetic_measurement(90)
    candidate["files"]["lex/new.py"] = {"covered": 100, "statements": 100,
                                          "source_sha256": "b" * 64}
    declaration = {"reason": "Nuovo modulo", "files": {"lex/new.py": "b" * 64}}
    if mutation == "hash":
        declaration["files"]["lex/new.py"] = "c" * 64
    elif mutation == "extra":
        candidate["files"]["lex/extra.py"] = dict(candidate["files"]["lex/new.py"])
    elif mutation == "environment":
        candidate["environment"]["python"] = "3.13.0"
    elif mutation == "removed":
        del candidate["files"]["lex/example.py"]
    else:
        declaration["reason"] = ""
    report = compare_measurements(baseline, candidate, declaration)
    assert report["blocking"] is True
    assert report["status"] == "non_homogeneous"


def test_scope_addition_is_bound_to_the_accepted_baseline(tmp_path):
    import json
    from tools.check_critical_coverage_regression import load_scope_addition

    assert load_scope_addition(tmp_path, "a" * 40) is None
    (tmp_path / "config").mkdir()
    path = tmp_path / "config/critical-coverage-scope-addition.json"
    declaration = {"baseline_sha": "a" * 40, "reason": "Nuovo modulo",
                   "files": {"lex/new.py": "b" * 64}}
    path.write_text(json.dumps(declaration), encoding="utf-8")
    assert load_scope_addition(tmp_path, "a" * 40) == declaration
    assert load_scope_addition(tmp_path, "c" * 40) is None
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="non valida"):
        load_scope_addition(tmp_path, "a" * 40)


def test_coverage_missing_shard_and_duplicate_artifacts_fail(tmp_path):
    for number in range(1, 12):
        (tmp_path / f".coverage.critical.{number}").touch()
    with pytest.raises(ValueError, match="mancanti"):
        collect_shards(tmp_path)
    (tmp_path / ".coverage.critical.12").touch()
    assert len(collect_shards(tmp_path)) == 12
    (tmp_path / "duplicate").mkdir()
    (tmp_path / "duplicate/.coverage.critical.1").touch()
    with pytest.raises(ValueError, match="duplicati"):
        collect_shards(tmp_path)


def test_coverage_previously_covered_lines_are_preserved_even_if_total_improves():
    baseline = _synthetic_measurement(80)
    candidate = _synthetic_measurement(81)
    baseline["files"]["lex/example.py"]["executed_lines"] = [1, 2]
    candidate["files"]["lex/example.py"]["executed_lines"] = [2, 3]
    report = compare_measurements(baseline, candidate)
    assert report["blocking"] is True
    assert report["previously_covered_lines_lost"] == {"lex/example.py": [1]}


def test_coverage_gate_is_required_and_baseline_uses_the_same_frozen_environment():
    import json

    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    names = [item["name"] for item in json.loads(Path(".github/required-checks.json").read_text())["required_checks"]]
    assert "Regressioni della copertura critica" in names
    jobs = workflow["jobs"]
    assert jobs["critical-coverage-regression"]["needs"] == ["coverage-critical-shards", "coverage-baseline-shards", "critical-coverage-environment"]
    for name in ("coverage-critical-shards", "coverage-baseline-shards"):
        job = jobs[name]
        assert job["strategy"]["matrix"]["shard"] == list(range(1, 13))
        assert any("critical-env-freeze.txt" in step.get("run", "") for step in job["steps"])
        python = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python@"))
        assert python["with"]["python-version"] == "3.12.15"


def test_coverage_artifact_retry_selects_one_version_per_shard_without_deleting_history():
    artifacts = [{"name": f"coverage-critical-{number}-attempt-1", "expired": False}
                 for number in range(1, 13)]
    artifacts.append({"name": "coverage-critical-4-attempt-2", "expired": False})
    names = select_artifact_names(artifacts, "coverage-critical", 2)
    assert len(names) == 12
    assert names[3] == "coverage-critical-4-attempt-2"
    assert len(artifacts) == 13
    assert select_artifact_names(artifacts, "coverage-critical", 1)[3].endswith("attempt-1")


def test_coverage_original_artifacts_and_missing_or_ambiguous_records():
    artifacts = [{"name": f"coverage-critical-{number}", "expired": False}
                 for number in range(1, 13)]
    assert len(select_artifact_names(artifacts, "coverage-critical", 1)) == 12
    with pytest.raises(ValueError, match="mancanti"):
        select_artifact_names(artifacts[:-1], "coverage-critical", 1)
    with pytest.raises(ValueError, match="ambigui"):
        select_artifact_names(artifacts + [artifacts[0]], "coverage-critical", 1)


def test_critical_coverage_gate_uses_governed_config():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "tests/test_lex_docling_parser.py" in workflow
    assert "--cov-config=config/coverage-critical.ini" in workflow
    assert "--suite coverage-critical" in workflow
    assert "coverage-critical-shards:" in workflow
    assert "name: Coverage moduli critici parte" in workflow
    assert "name: Coverage moduli critici\n" not in workflow
    assert "\n  coverage-critical:\n" not in workflow
    assert "--fail-under=71" not in workflow


def test_critical_coverage_config_excludes_optional_lex_adapters():
    config = Path("config/coverage-critical.ini").read_text(encoding="utf-8")
    expected_omits = [
        "lex/image_providers/*",
        "lex/normativa/*",
        "lex/retrieval/official_sources_retriever.py",
        "lex/sources/*",
        "lex/tools/*",
    ]

    for pattern in expected_omits:
        assert pattern in config


@pytest.mark.parametrize("job", ["tests-core-shards", "coverage-critical-shards"])
def test_shards_checkout_history_for_lex_source_benchmark(job):
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    checkout = next(step for step in workflow["jobs"][job]["steps"]
                    if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"].get("fetch-depth") == 0, (
        "Il banco fonti deve poter caricare il retriever storico 2.435.0 tramite git show"
    )
