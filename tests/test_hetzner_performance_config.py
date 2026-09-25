from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "hetzner" / "docker-compose.hetzner.yml"
CADDYFILE = ROOT / "deploy" / "hetzner" / "Caddyfile"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-hetzner.yml"


def _compose() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def _service_block(compose: str, service: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(service)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|^networks:\n|\Z)",
        compose,
    )
    assert match is not None, f"Servizio Compose mancante: {service}"
    return match.group(1)


def test_hetzner_ruota_i_log_docker() -> None:
    compose = _compose()

    assert "x-iusentra-logging: &iusentra-logging" in compose
    assert "driver: local" in compose
    assert 'max-size: "10m"' in compose
    assert 'max-file: "3"' in compose
    for service in (
        "redis",
        "audit-worm",
        "audit-worm-init",
        "audit-postgres",
        "app",
        "scheduler-worker",
        "ocr-worker",
        "static-assets",
        "caddy",
        "ollama",
        "unlimited-ocr",
        "prometheus",
        "grafana",
    ):
        block = _service_block(compose, service)
        assert "logging: *iusentra-logging" in block


def test_hetzner_isola_worm_e_preserva_accesso_dei_worker() -> None:
    compose = _compose()

    assert "audit-internal:\n    internal: true" in compose
    for service in ("app", "scheduler-worker", "ocr-worker"):
        block = _service_block(compose, service)
        assert "- default" in block
        assert "- audit-internal" in block
    for service in ("audit-worm", "audit-worm-init", "audit-postgres"):
        block = _service_block(compose, service)
        assert "- audit-internal" in block


def test_hetzner_limita_ollama_senza_forzare_reload_continui() -> None:
    compose = _compose()
    block = _service_block(compose, "ollama")

    assert 'OLLAMA_NO_CLOUD: "1"' in block
    assert "OLLAMA_MAX_LOADED_MODELS: ${OLLAMA_MAX_LOADED_MODELS:-2}" in block
    assert "OLLAMA_NUM_PARALLEL: ${OLLAMA_NUM_PARALLEL:-1}" in block
    assert "OLLAMA_MAX_QUEUE: ${OLLAMA_MAX_QUEUE:-32}" in block
    assert "OLLAMA_CONTEXT_LENGTH: ${OLLAMA_CONTEXT_LENGTH:-8192}" in block


def test_caddy_aggiornato_e_metriche_non_pubbliche() -> None:
    compose = _compose()
    caddyfile = CADDYFILE.read_text(encoding="utf-8")

    assert "image: caddy:2.11.4-alpine" in compose
    assert "@public_metrics path /metrics" in caddyfile
    assert "respond @public_metrics 404" in caddyfile


def test_asset_statici_non_occupano_i_worker_applicativi() -> None:
    compose = _compose()
    caddyfile = CADDYFILE.read_text(encoding="utf-8")
    static_block = _service_block(compose, "static-assets")
    caddy_block = _service_block(compose, "caddy")

    assert "image: ${IUSENTRA_APP_IMAGE:-iusentra-app}" in static_block
    assert "pull_policy: never" in static_block
    assert "entrypoint: []" in static_block
    assert "user: iusentra" in static_block
    assert "read_only: true" in static_block
    assert "- http.server" in static_block
    assert "- /app/web/static" in static_block
    assert "no-new-privileges:true" in static_block
    assert "cap_drop:" in static_block
    assert "handle_path /static/*" in caddyfile
    assert "reverse_proxy static-assets:8090" in caddyfile
    assert "static-assets:" in caddy_block
    assert "condition: service_healthy" in caddy_block


def test_deploy_verifica_servizio_e_rotta_degli_asset_statici() -> None:
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    assert "static_id=$(docker compose" in workflow
    assert "Immagine asset diversa dalla applicazione" in workflow
    assert '"/static/manifest.json"' in workflow
