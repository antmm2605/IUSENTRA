"""Revisioni SQL confermate durante una lettura, senza acquisire fonti."""
from __future__ import annotations

import hashlib
import json

from flask import current_app, g, has_app_context

DOMAIN_PERMISSIONS = {
    "clienti": "clienti.leggi", "soggetti": "clienti.leggi",
    "fascicoli": "fascicoli.leggi", "agenda": "agenda.leggi",
    "scadenze": "scadenziario.leggi", "timesheet": "fatturazione.leggi",
    "preventivi": "fatturazione.leggi", "fatturazione": "fatturazione.leggi",
    "incassi": "fatturazione.leggi", "comunicazioni": "messaggi.leggi",
    "privacy": "utenti.leggi",
}


def mark_projection_read_failure(label="", error_code=""):
    if has_app_context():
        failures = getattr(g, "_confirmed_projection_failures", None)
        if failures is not None:
            failures.append(True)
            current_app.logger.warning("Lettura della proiezione non riuscita: ambito=%r codice=%s", label, error_code)


def read_authorized_revisions(user, *, requested_domains=None):
    from pct.operational_live import read_live_revisions
    from web.services.storage_runtime import get_request_studio_db
    from web.services.tenant_paths import tenant_data_path
    from web.services.operational_live_sources import read_vertical_revisions

    if user is None:
        raise PermissionError("Contesto utente non disponibile per le revisioni.")
    domains = {domain for domain, permission in DOMAIN_PERMISSIONS.items()
               if user.ha_permesso(permission)
               and (requested_domains is None or domain in requested_domains)}
    backend = get_request_studio_db(tenant_data_path("CLIENTI_DB", require_tenant=True))
    if backend is None:
        raise RuntimeError("Sincronizzazione SQL non disponibile.")
    revisions = read_live_revisions(backend, domains)
    for domain, revision in read_vertical_revisions(domains).items():
        if domain in domains:
            revisions[domain] = revisions.get(domain, 0) + revision
    return revisions


def read_authorized_revision_snapshot(user, *, requested_domains=None):
    revisions = read_authorized_revisions(user, requested_domains=requested_domains)
    owner = (
        str(getattr(getattr(g, "tenant", None), "slug", "") or getattr(g, "tenant_context_slug", "") or ""),
        str(getattr(user, "id", "") or ""),
        str(getattr(user, "username", "") or ""),
        getattr(g, "_runtime_studio_db_key", None),
    )
    context = hashlib.sha256(json.dumps(owner, ensure_ascii=False).encode()).hexdigest()
    return {"context": context, "revisions": revisions}


def with_confirmed_read_revision(build, read_revisions):
    """Conferma solo contatori uguali prima e dopo l'intera proiezione."""
    before = None
    try:
        snapshot = read_revisions()
        before = {"context": snapshot["context"], "revisions": dict(snapshot["revisions"])}
    except Exception:
        current_app.logger.warning("Revisione iniziale della vista non confermata", exc_info=True)
    failures = []
    previous = getattr(g, "_confirmed_projection_failures", None)
    g._confirmed_projection_failures = failures
    try:
        payload = build()
    finally:
        g._confirmed_projection_failures = previous
        if previous is not None:
            previous.extend(failures)
    confirmed = None
    if not failures and before and before.get("context") and before.get("revisions"):
        try:
            after = read_revisions()
            if before == after:
                confirmed = after
        except Exception:
            current_app.logger.warning("Revisione finale della vista non confermata", exc_info=True)
    return {**payload,
            "readRevision": dict(confirmed["revisions"]) if confirmed else None,
            "readRevisionContext": confirmed["context"] if confirmed else None,
            "readFailed": bool(failures)}
