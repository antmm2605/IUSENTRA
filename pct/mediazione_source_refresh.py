"""Bounded refresh of public mediation sources, independent of page loading.

One durable job per active registry number; conditional SQL leases coordinate
manual and scheduled runs. Network errors never erase previous observations.
"""
from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pct.mediazione_channel_research import RESEARCH_VERSION, inspect_channels
from pct.mediazione_source_history import digest, record


def seed_jobs(repo, *, now=None):
    now = now or datetime.now(timezone.utc)
    with repo.connection() as conn:
        rows = conn.execute("SELECT * FROM mediazione_organismi WHERE active=1 ORDER BY registration_number").fetchall()
        for row in rows:
            input_hash = digest({k: row[k] for k in ("website", "record_json")})
            conn.execute(
                "INSERT INTO mediazione_source_jobs(registration_number, input_sha256, research_version, due_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(registration_number) DO UPDATE SET "
                "input_sha256=excluded.input_sha256, research_version=excluded.research_version, "
                "due_at=excluded.due_at, lease_token='', lease_until='' "
                "WHERE mediazione_source_jobs.input_sha256<>excluded.input_sha256 "
                "OR mediazione_source_jobs.research_version<>excluded.research_version",
                (row["registration_number"], input_hash, RESEARCH_VERSION, now.isoformat()))
    return len(rows)


def claim_jobs(repo, *, limit=6, now=None):
    now = now or datetime.now(timezone.utc)
    if not 1 <= limit <= 20:
        raise ValueError("La verifica lavora da 1 a 20 organismi per ciclo.")
    claimed = []
    with repo.connection() as conn:
        rows = conn.execute(
            "SELECT j.*, o.record_json, c.result_json, h.result_json AS channel_json FROM mediazione_source_jobs j "
            "JOIN mediazione_organismi o ON o.registration_number=j.registration_number "
            "LEFT JOIN mediazione_site_checks c ON c.registration_number=o.registration_number "
            "LEFT JOIN mediazione_channel_checks h ON h.registration_number=o.registration_number "
            "WHERE o.active=1 AND j.due_at<=? AND j.lease_until<=? "
            "ORDER BY j.due_at, j.registration_number LIMIT ?",
            (now.isoformat(), now.isoformat(), limit)).fetchall()
        for row in rows:
            token = uuid4().hex
            acquired = conn.execute(
                "UPDATE mediazione_source_jobs SET lease_token=?, lease_until=? "
                "WHERE registration_number=? AND lease_until<=? AND due_at<=? "
                "RETURNING registration_number",
                (token, (now + timedelta(minutes=15)).isoformat(), row["registration_number"],
                 now.isoformat(), now.isoformat())).fetchone()
            if acquired:
                claimed.append(dict(row, token=token, organism=dict(json.loads(row["record_json"]),
                                    directory_check=json.loads(row["result_json"] or "{}"),
                                    channel_check=json.loads(row["channel_json"] or "{}"))))
    return claimed


def finish_job(repo, job, result, *, now=None):
    now = now or datetime.now(timezone.utc)
    number = job["registration_number"]
    if result.get("registration_number") != number:
        raise ValueError("Esito non associato all'organismo in verifica.")
    with repo.connection() as conn:
        # Lock/claim condition is also checked on completion: an expired worker
        # cannot overwrite a newer acquisition or a changed ministerial record.
        owned = conn.execute(
            "UPDATE mediazione_source_jobs SET lease_token=lease_token WHERE registration_number=? "
            "AND lease_token=? AND lease_until>? AND input_sha256=? AND research_version=? "
            "RETURNING failures",
            (number, job["token"], now.isoformat(), job["input_sha256"], job["research_version"])).fetchone()
        if not owned:
            return "esito_superato"
        current = conn.execute("SELECT active, website, record_json FROM mediazione_organismi WHERE registration_number=?", (number,)).fetchone()
        if not current or not current["active"]:
            conn.execute("UPDATE mediazione_source_jobs SET lease_token='', lease_until='' "
                         "WHERE registration_number=?", (number,))
            return "organismo_non_attivo"
        if digest({k: current[k] for k in ("website", "record_json")}) != job["input_sha256"]:
            conn.execute("UPDATE mediazione_source_jobs SET lease_token='', lease_until='', due_at=? "
                         "WHERE registration_number=?", (now.isoformat(), number))
            return "esito_superato"
        outcome = record(conn, number, result)
        failures = 0 if outcome == "acquisita" else min(owned["failures"] + 1, 12)
        continuation = bool(result.get("remaining_urls"))
        hours = 24 * 7 if not failures else min(24 * 7, 2 ** failures)
        delay = timedelta(minutes=10) if continuation else timedelta(hours=hours)
        conn.execute("UPDATE mediazione_source_jobs SET due_at=?, lease_token='', lease_until='', failures=?, "
                     "last_error=? WHERE registration_number=?",
                     ((now + delay).isoformat(), failures,
                      "" if not failures else outcome, number))
        return outcome


def refresh_sources(repo, *, limit=6, workers=2):
    if not 1 <= workers <= 6:
        raise ValueError("Usare al massimo sei verifiche pubbliche contemporanee.")
    active = seed_jobs(repo)
    jobs = claim_jobs(repo, limit=limit)
    outcomes = Counter()
    # No nested app/tenant context; only public registry input reaches workers.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(inspect_channels, job["organism"]): job for job in jobs}
        for future in as_completed(pending):
            job = pending[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"registration_number": job["registration_number"], "checked_at": datetime.now(timezone.utc).isoformat(),
                          "research_version": RESEARCH_VERSION, "status": "fonte_non_raggiunta",
                          "errors": [{"error": type(exc).__name__}], "pages": []}
            outcomes[finish_job(repo, job, result)] += 1
    with repo.connection() as conn:
        pending_count = conn.execute(
            "SELECT COUNT(*) AS n FROM mediazione_source_jobs j JOIN mediazione_organismi o "
            "ON o.registration_number=j.registration_number WHERE o.active=1 AND j.due_at<=?",
            (datetime.now(timezone.utc).isoformat(),)).fetchone()["n"]
    return {"ok": True, "source_of_truth": repo.source_of_truth, "organismi_attivi": active,
            "controllati": len(jobs), "in_attesa": pending_count, "esiti": dict(outcomes),
            "summary": f"Controllati {len(jobs)} organismi; {pending_count} verifiche ancora in coda. Nessun invio eseguito."}
