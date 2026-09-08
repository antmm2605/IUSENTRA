#!/usr/bin/env python3
"""Deploy the canonical Git stack through the local Portainer API.

Run after CI, backup and image build. Credentials never leave the server.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request


BASE = "http://127.0.0.1:19000/api"
COMPOSE = "deploy/hetzner/docker-compose.hetzner.yml"
REPOSITORY = "https://github.com/antmm2605/IUSENTRA.git"


def stack_environment(compose_text, environment, repo, sha):
    """Only forward variables referenced by Compose, never the full shell."""
    names = set(re.findall(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)", compose_text))
    values = {name: environment[name] for name in names if name in environment}
    values.update({
        "COMPOSE_PROFILES": environment.get("COMPOSE_PROFILES", ""),
        "IUSENTRA_APP_IMAGE": f"iusentra-app:{sha}",
        "IUSENTRA_CADDYFILE": str(repo / "deploy/hetzner/Caddyfile"),
        "IUSENTRA_PROMETHEUS_CONFIG": str(repo / "prometheus.yml"),
        "IUSENTRA_MONITORING_CONFIG": str(repo / "monitoring"),
    })
    # Portainer writes these values to stack.env. Single quotes prevent Compose
    # from expanding literal dollar signs in secrets a second time.
    result = []
    for name, value in sorted(values.items()):
        if "\n" in value or "\r" in value:
            raise ValueError(f"Variabile multilinea non supportata: {name}")
        quoted = "'" + value.replace("'", "\\'") + "'"
        result.append({"name": name, "value": quoted})
    return result


def request(path, token=None, payload=None, method=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=240) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Responses can contain the submitted configuration: do not print them.
        raise RuntimeError(f"Portainer {path}: HTTP {error.code}") from None


def main():
    repo = Path(__file__).resolve().parents[2]
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Commit non valido")
    expected_image = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", f"iusentra-app:{sha}"], text=True
    ))[0]
    if expected_image["Config"].get("Labels", {}).get("org.opencontainers.image.revision") != sha:
        raise RuntimeError("Immagine priva del commit di release atteso")
    credential = Path("/opt/iusentra/portainer/admin-password")
    token = request("/auth", payload={
        "Username": "admin", "Password": credential.read_text().strip(),
    })["jwt"]
    endpoints = [e for e in request("/endpoints", token)
                 if e.get("URL") == "unix:///var/run/docker.sock" and e.get("Type") == 1]
    if len(endpoints) != 1:
        raise RuntimeError("Ambiente Docker locale non univoco")
    endpoint = endpoints[0]["Id"]
    env = stack_environment((repo / COMPOSE).read_text(), os.environ, repo, sha)
    stacks = [s for s in request("/stacks", token)
              if s["Name"] == "iusentra" and s["EndpointId"] == endpoint]
    if len(stacks) > 1:
        raise RuntimeError("Stack IUSENTRA duplicato")
    payload = {"RepositoryReferenceName": sha, "Env": env}
    if stacks:
        stack = stacks[0]
        if (stack.get("GitConfig") or {}).get("URL") != REPOSITORY:
            raise RuntimeError("Lo stack esistente non usa il repository atteso")
        payload.update({"Prune": False, "RepullImageAndRedeploy": False})
        result = request(f"/stacks/{stack['Id']}/git/redeploy?endpointId={endpoint}",
                         token, payload, "PUT")
    else:
        payload.update({"Name": "iusentra", "RepositoryURL": REPOSITORY,
                        "ComposeFile": COMPOSE, "RepositoryAuthentication": False})
        result = request(f"/stacks/create/standalone/repository?endpointId={endpoint}",
                         token, payload, "POST")
    stack_id = result.get("Id") or result.get("Stack", {}).get("Id")
    if not stack_id:
        raise RuntimeError("Portainer non ha restituito l'identificativo dello stack")
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        state = request(f"/stacks/{stack_id}", token)
        if state.get("Status") == 1:
            actual = (state.get("GitConfig") or {}).get("ConfigHash")
            if actual != sha:
                raise RuntimeError("Commit Portainer diverso dal commit richiesto")
            for service in ("app", "scheduler-worker", "ocr-worker"):
                ids = subprocess.check_output([
                    "docker", "ps", "-q", "--filter", "label=com.docker.compose.project=iusentra",
                    "--filter", f"label=com.docker.compose.service={service}",
                ], text=True).split()
                if len(ids) != 1:
                    raise RuntimeError(f"Numero container inatteso: {service}")
                container = json.loads(subprocess.check_output(
                    ["docker", "inspect", ids[0]], text=True
                ))[0]
                if container["Image"] != expected_image["Id"]:
                    raise RuntimeError(f"Immagine non aggiornata: {service}")
                if service == "app" and container["Name"] != "/iusentra-app":
                    raise RuntimeError("Nome container applicativo non canonico")
            print(f"Portainer: stack=iusentra id={stack_id} commit={sha}")
            return
        if state.get("Status") != 3:
            raise RuntimeError("Deploy Portainer non riuscito; consultare il pannello")
        time.sleep(5)
    raise RuntimeError("Timeout deploy Portainer; nessun deploy alternativo eseguito")


if __name__ == "__main__":
    main()
