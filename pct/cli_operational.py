"""Comandi CLI per crash test operativo e backup blindato."""

from __future__ import annotations

import json
from pathlib import Path

import click


def _app_overrides(registry: str, studio_config: str) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if str(registry or "").strip():
        overrides["TENANTS_REGISTRY"] = str(registry).strip()
    if str(studio_config or "").strip():
        overrides["STUDIO_CONFIG"] = str(studio_config).strip()
    return overrides


def _with_runtime_app(registry: str, studio_config: str):
    from web.app import create_app

    return create_app(_app_overrides(registry, studio_config))


@click.command("crash-test-operativo")
@click.option("--tenant", "tenant_slug", default="", help="Slug tenant da testare")
@click.option("--registry", default="", help="Registry tenant alternativo")
@click.option("--studio-config", default="", help="Config studio alternativo per single-studio")
@click.option("--max-attempts", default=3, show_default=True, type=int, help="Numero massimo di tentativi con autotest di riparazione")
@click.option("--no-auto-repair", is_flag=True, default=False, help="Disattiva il repair loop tra un tentativo e il successivo")
def cmd_crash_test_operativo(tenant_slug: str, registry: str, studio_config: str, max_attempts: int, no_auto_repair: bool):
    """Esegue il crash test operativo completo sul tenant selezionato."""
    from web.services.operational_resilience_surface import execute_operational_crash_surface

    app = _with_runtime_app(registry, studio_config)
    with app.app_context():
        report = execute_operational_crash_surface(
            selected_slug=str(tenant_slug or "").strip().lower(),
            trigger_source="cli",
            schedule_code="manual-cli",
            auto_repair=not bool(no_auto_repair),
            max_attempts=max(int(max_attempts or 1), 1),
        )
    click.echo(json.dumps(report, ensure_ascii=False, indent=2))


@click.command("backup-blindato")
@click.option("--tenant", "tenant_slug", default="", help="Slug tenant da salvare")
@click.option("--registry", default="", help="Registry tenant alternativo")
@click.option("--studio-config", default="", help="Config studio alternativo per single-studio")
def cmd_backup_blindato(tenant_slug: str, registry: str, studio_config: str):
    """Esegue backup completo e incrementale con report blindato."""
    from web.services.operational_resilience_surface import execute_operational_backup_surface

    app = _with_runtime_app(registry, studio_config)
    with app.app_context():
        report = execute_operational_backup_surface(
            selected_slug=str(tenant_slug or "").strip().lower(),
            trigger_source="cli",
            schedule_code="manual-cli",
        )
    click.echo(json.dumps(report, ensure_ascii=False, indent=2))
