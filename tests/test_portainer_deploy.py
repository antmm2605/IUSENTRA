"""Fast release guards for the Portainer handoff (no production mutations)."""

import importlib.util
from pathlib import Path, PurePosixPath
import urllib.error

import pytest


SPEC = importlib.util.spec_from_file_location(
    "portainer_deploy", Path(__file__).parents[1] / "deploy/hetzner/portainer_deploy.py"
)
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


def test_only_compose_variables_leave_shell():
    env = {"SECRET": "dollar$VALUE", "GH_TOKEN": "private", "COMPOSE_PROFILES": "audit-worm"}
    values = {p["name"]: p["value"] for p in deploy.stack_environment(
        "${SECRET} $${GH_TOKEN}", env, PurePosixPath("/opt/iusentra/repo"), "a" * 40
    )}
    assert "GH_TOKEN" not in values
    assert values["SECRET"] == "'dollar$VALUE'"
    assert values["COMPOSE_PROFILES"] == "'audit-worm'"
    assert values["IUSENTRA_APP_IMAGE"] == "'iusentra-app:" + "a" * 40 + "'"
    assert values["IUSENTRA_CADDYFILE"] == "'/opt/iusentra/repo/deploy/hetzner/Caddyfile'"


def test_multiline_cannot_inject_another_environment_variable():
    with pytest.raises(ValueError, match="SECRET"):
        deploy.stack_environment("${SECRET}", {"SECRET": "value\nOTHER=bad"}, Path("/repo"), "a" * 40)


def test_http_failure_does_not_expose_configuration(monkeypatch):
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError("url", 500, "secret-configuration", {}, None)

    monkeypatch.setattr(deploy.urllib.request, "urlopen", fail)
    with pytest.raises(RuntimeError) as error:
        deploy.request("/stacks", "private-token", {"Env": "secret"})
    assert str(error.value) == "Portainer /stacks: HTTP 500"
    assert "secret" not in str(error.value)
