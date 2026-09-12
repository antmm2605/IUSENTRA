"""Fast release guards for the Portainer handoff (no production mutations)."""

import importlib.util
import json
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


def test_portainer_error_status_is_accepted_only_with_verified_release(monkeypatch, capsys):
    sha = "a" * 40
    env = [{"name": "IUSENTRA_APP_IMAGE", "value": "'iusentra-app:" + sha + "'"}]
    real_read = deploy.Path.read_text
    monkeypatch.setattr(deploy.Path, "read_text", lambda p, *a, **kw:
                        "test-credential" if p.name == "admin-password" else real_read(p, *a, **kw))
    monkeypatch.setattr(deploy, "stack_environment", lambda *a, **kw: env)
    monkeypatch.setattr(deploy, "verify_release_containers", lambda expected: True)
    monkeypatch.setattr(deploy, "stack_services_ready", lambda repo: True)

    def output(args, **kwargs):
        if args[:2] == ["git", "rev-parse"]:
            return sha
        if args[:2] == ["git", "ls-remote"]:
            return sha + "\trefs/tags/iusentra-release-" + sha
        assert args[:3] == ["docker", "image", "inspect"]
        return json.dumps([{"Id": "image", "Config": {"Labels": {"org.opencontainers.image.revision": sha}}}])

    def request(path, token=None, payload=None, method=None):
        if path == "/auth":
            return {"jwt": "test-token"}
        if path == "/endpoints":
            return [{"Id": 1, "URL": "unix:///var/run/docker.sock", "Type": 1}]
        if path == "/stacks":
            return [{"Id": 1, "Name": "iusentra", "EndpointId": 1, "Status": 4, "Env": env,
                     "GitConfig": {"URL": deploy.REPOSITORY, "ConfigHash": sha},
                     "AdditionalFiles": [deploy.RELEASE_COMPOSE]}]
        raise AssertionError("Non deve richiedere redeploy quando la release è già verificata")

    monkeypatch.setattr(deploy.subprocess, "check_output", output)
    monkeypatch.setattr(deploy, "request", request)

    deploy.main()

    assert "stato Portainer 4 ignorato dopo verifica Docker" in capsys.readouterr().out


def test_portainer_error_status_after_redeploy_requires_verified_release(monkeypatch, capsys):
    sha = "a" * 40
    real_read = deploy.Path.read_text
    monkeypatch.setattr(deploy.Path, "read_text", lambda p, *a, **kw:
                        "test-credential" if p.name == "admin-password" else real_read(p, *a, **kw))
    monkeypatch.setattr(deploy, "stack_environment", lambda *a, **kw: [])
    monkeypatch.setattr(deploy, "verify_release_containers", lambda expected: True)
    monkeypatch.setattr(deploy, "stack_services_ready", lambda repo: True)

    def output(args, **kwargs):
        if args[:2] == ["git", "rev-parse"]:
            return sha
        if args[:2] == ["git", "ls-remote"]:
            return sha + "\trefs/tags/iusentra-release-" + sha
        assert args[:3] == ["docker", "image", "inspect"]
        return json.dumps([{"Id": "image", "Config": {"Labels": {"org.opencontainers.image.revision": sha}}}])

    def request(path, token=None, payload=None, method=None):
        if path == "/auth":
            return {"jwt": "test-token"}
        if path == "/endpoints":
            return [{"Id": 1, "URL": "unix:///var/run/docker.sock", "Type": 1}]
        if path == "/stacks":
            return [{"Id": 1, "Name": "iusentra", "EndpointId": 1, "Status": 4,
                     "GitConfig": {"URL": deploy.REPOSITORY, "ConfigHash": "0" * 40},
                     "AdditionalFiles": [deploy.RELEASE_COMPOSE]}]
        if path == "/stacks/1/git/redeploy?endpointId=1":
            return {"Id": 1}
        if path == "/stacks/1":
            return {"Id": 1, "Status": 4, "GitConfig": {"ConfigHash": sha}}
        raise AssertionError(path)

    monkeypatch.setattr(deploy.subprocess, "check_output", output)
    monkeypatch.setattr(deploy, "request", request)

    deploy.main()

    assert "healthy nonostante stato Portainer error" in capsys.readouterr().out


@pytest.mark.parametrize("repository,accepted", [
    (deploy.REPOSITORY, True),
    (deploy.REPOSITORY.removesuffix(".git"), True),
    (deploy.REPOSITORY + ".untrusted", False),
    ("https://example.com/antmm2605/IUSENTRA", False),
])
def test_redeploy_accepts_only_the_canonical_repository(monkeypatch, repository, accepted):
    sha = "a" * 40
    real_read = deploy.Path.read_text
    monkeypatch.setattr(deploy.Path, "read_text", lambda p, *a, **kw:
                        "test-credential" if p.name == "admin-password" else real_read(p, *a, **kw))

    def output(args, **kwargs):
        if args[:2] == ["git", "rev-parse"]:
            return sha
        if args[:2] == ["git", "ls-remote"]:
            return sha + "\trefs/tags/iusentra-release-" + sha
        assert args[:3] == ["docker", "image", "inspect"]
        return json.dumps([{"Id": "image", "Config": {"Labels": {"org.opencontainers.image.revision": sha}}}])

    class RedeployRequested(Exception):
        pass

    def request(path, token=None, payload=None, method=None):
        if path == "/auth":
            return {"jwt": "test-token"}
        if path == "/endpoints":
            return [{"Id": 1, "URL": "unix:///var/run/docker.sock", "Type": 1}]
        if path == "/stacks":
            return [{"Id": 1, "Name": "iusentra", "EndpointId": 1,
                     "GitConfig": {"URL": repository}, "AdditionalFiles": [deploy.RELEASE_COMPOSE]}]
        assert path == "/stacks/1/git/redeploy?endpointId=1"
        assert method == "PUT"
        assert payload["RepositoryReferenceName"] == "refs/tags/iusentra-release-" + sha
        assert payload["Prune"] is False
        raise RedeployRequested

    monkeypatch.setattr(deploy.subprocess, "check_output", output)
    monkeypatch.setattr(deploy, "request", request)
    if accepted:
        with pytest.raises(RedeployRequested):
            deploy.main()
    else:
        with pytest.raises(RuntimeError, match="repository atteso"):
            deploy.main()


@pytest.mark.parametrize("health,ready", [("healthy", True), ("starting", False), ("unhealthy", False)])
def test_release_readiness_requires_healthy_workers(monkeypatch, health, ready):
    def output(args, **kwargs):
        if args[:2] == ["docker", "ps"]:
            return args[-1].split("=")[-1]
        service = args[-1]
        return json.dumps([{"Name": "/iusentra-app" if service == "app" else service,
                            "Image": "release", "State": {"Health": {"Status": health}}}])

    monkeypatch.setattr(deploy.subprocess, "check_output", output)
    assert deploy.verify_release_containers({"Id": "release"}) is ready


@pytest.mark.parametrize("caddy_present,caddy_running,init_exit,ready", [
    (True, True, 0, True),
    (True, False, 0, False),
    (False, False, 0, False),
    (True, True, 1, False),
])
def test_unchanged_release_still_restores_infrastructure(monkeypatch, caddy_present, caddy_running, init_exit, ready):
    containers = [{"Config": {"Labels": {"com.docker.compose.service": "audit-worm-init"}},
                   "State": {"Status": "exited", "ExitCode": init_exit}}]
    if caddy_present:
        containers.append({"Config": {"Labels": {"com.docker.compose.service": "caddy"}},
                           "State": {"Running": caddy_running}})

    def output(args, **kwargs):
        if args[:2] == ["docker", "compose"]:
            return "caddy\naudit-worm-init\n"
        if args[:2] == ["docker", "ps"]:
            return "containers"
        return json.dumps(containers)

    monkeypatch.setattr(deploy.subprocess, "check_output", output)
    assert deploy.stack_services_ready(PurePosixPath("/repo")) is ready
