"""Verifica sul server che le ultime PEC arrivino davvero fino allo studio.

Non simula nulla: legge i dati reali dello studio e, per ogni PEC recente,
dice cosa ha prodotto e — quando non ha prodotto niente — perche'.

Catena controllata, nell'ordine in cui deve accadere:

    PEC acquisita -> classificata -> collegata al fascicolo -> presidio
    -> scadenza (scadenziario) -> appuntamento (agenda) -> notifica
    (centro notifiche + top bar) -> Web Push

Una riga verde significa che quel passaggio ha lasciato una traccia
verificabile nei dati; una riga rossa riporta il motivo, non un'ipotesi.

Uso tipico sul server:

    docker compose exec app python scripts/verifica_catena_pec.py
    docker compose exec app python scripts/verifica_catena_pec.py --limite 20 --json

Sola lettura: non scrive, non invia, non modifica nulla.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.pec_pipeline import PecAuditRepository  # noqa: E402
from pct.tenant import GestioneTenant  # noqa: E402

VERDE = "\033[32m"
ROSSO = "\033[31m"
GIALLO = "\033[33m"
GRIGIO = "\033[90m"
NEUTRO = "\033[0m"


def _registry_path(value: str = "") -> Path:
    raw = (
        value
        or os.environ.get("TENANTS_REGISTRY")
        or os.environ.get("IUSENTRA_TENANTS_REGISTRY")
        or os.environ.get("PCT_TENANTS_REGISTRY")
        or "data/tenants.json"
    )
    return Path(raw)


def _testo(value: Any, default: str = "") -> str:
    raw = str(value if value is not None else "").strip()
    return raw or default


def _colora(colorato: bool, colore: str, testo: str) -> str:
    return f"{colore}{testo}{NEUTRO}" if colorato else testo


# --------------------------------------------------------------------------- #
# Lettura dei singoli anelli della catena                                       #
# --------------------------------------------------------------------------- #


def _percorso_notifiche(percorsi: dict[str, Any]) -> Path:
    """Stessa regola del runtime (`web.services.notifications_runtime`).

    Il percorso esplicito vince; altrimenti il database sta accanto al log
    delle notifiche. Duplicare la regola a mano porterebbe lo strumento a
    dichiarare 'archivio assente' su uno studio perfettamente sano.
    """

    configurato = _testo(percorsi.get("NOTIFICATIONS_DB"))
    if configurato:
        return Path(configurato)
    log = Path(_testo(percorsi.get("NOTIFICHE_LOG"), "./notifiche/log.json"))
    return log.with_name("notifications.db")


def _presidi_del_messaggio(percorsi: dict[str, Any], tenant: str, message_id: str) -> list[dict[str, Any]]:
    """Presidi operativi nati da questa PEC (tabella del presidio notifiche)."""

    import sqlite3

    db = Path(percorsi["EMAIL_CASELLA_DB"]).parent / "pec_audit.sqlite"
    if not db.exists():
        return []
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            righe = conn.execute(
                """
                SELECT id, status, priority, fascicolo_id, channel, notification_case
                FROM pec_legal_notification_presidia
                WHERE tenant_id=? AND source_message_id=?
                ORDER BY created_at DESC
                """,
                (tenant, message_id),
            ).fetchall()
        return [dict(riga) for riga in righe]
    except sqlite3.Error as exc:
        return [{"id": "", "status": f"lettura non riuscita: {exc}", "priority": "", "fascicolo_id": "", "channel": ""}]


def _scadenze_del_messaggio(percorsi: dict[str, Any], message_id: str) -> list[dict[str, Any]]:
    """Scadenze generate dalla PEC: portano il marcatore `PEC_AUDIT:<id>`."""

    from pct.scadenziario import GestioneScadenziario

    try:
        gestione = GestioneScadenziario(percorsi["SCADENZIARIO_DB"])
        marcatore = f"PEC_AUDIT:{message_id}"
        trovate = []
        for scadenza in gestione.tutte(solo_aperte=False):
            testo = " ".join(
                _testo(getattr(scadenza, campo, "")) for campo in ("note", "external_uid", "titolo")
            )
            if marcatore in testo:
                trovate.append(
                    {
                        "id": _testo(getattr(scadenza, "id", "")),
                        "titolo": _testo(getattr(scadenza, "titolo", "")),
                        "data": _testo(getattr(scadenza, "data_scadenza", "")),
                        "stato": _testo(getattr(getattr(scadenza, "stato", ""), "value", getattr(scadenza, "stato", ""))),
                    }
                )
        return trovate
    except Exception as exc:
        return [{"id": "", "titolo": f"lettura scadenziario non riuscita: {exc}", "data": "", "stato": ""}]


def _appuntamenti_del_messaggio(percorsi: dict[str, Any], message_id: str) -> list[dict[str, Any]]:
    """Udienze portate in Agenda dalla PEC (stesso marcatore delle scadenze)."""

    from pct.agenda import Agenda

    try:
        agenda = Agenda(percorsi["AGENDA_DB"])
        marcatore = f"PEC_AUDIT:{message_id}"
        trovati = []
        for appuntamento in agenda.tutti():
            testo = " ".join(
                _testo(getattr(appuntamento, campo, "")) for campo in ("note", "external_uid", "titolo", "descrizione")
            )
            if marcatore in testo:
                trovati.append(
                    {
                        "id": _testo(getattr(appuntamento, "id", "")),
                        "titolo": _testo(getattr(appuntamento, "titolo", "")),
                        "data": _testo(getattr(appuntamento, "data_ora", "")),
                    }
                )
        return trovati
    except Exception as exc:
        return [{"id": "", "titolo": f"lettura agenda non riuscita: {exc}", "data": ""}]


def _notifiche_del_messaggio(
    percorsi: dict[str, Any], tenant: str, message_id: str, presidi: list[dict[str, Any]]
) -> dict[str, Any]:
    """Voci del centro notifiche (le stesse che alimentano la top bar).

    La notifica non cita la PEC: cita il presidio che la PEC ha generato
    (`legal-notification-presidio:<id>:<stato>`). Il collegamento passa quindi
    dagli id dei presidi, non dall'id del messaggio.
    """

    import sqlite3

    db = _percorso_notifiche(percorsi)
    if not db.exists():
        return {"totale": 0, "motivo": f"archivio notifiche assente ({db})", "esempi": []}
    chiavi = [f"%{_testo(p.get('id'))}%" for p in presidi if _testo(p.get("id"))]
    chiavi.append(f"%{message_id}%")
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            condizioni = " OR ".join(["dedupe_key LIKE ? OR source_id LIKE ?"] * len(chiavi))
            parametri: list[Any] = [tenant]
            for chiave in chiavi:
                parametri.extend([chiave, chiave])
            righe = conn.execute(
                f"SELECT title, type, source_type, read_at FROM notifications WHERE tenant_id=? AND ({condizioni}) LIMIT 10",
                tuple(parametri),
            ).fetchall()
        if righe:
            return {"totale": len(righe), "motivo": "", "esempi": [dict(riga) for riga in righe]}
        # Zero voci puo' voler dire due cose molto diverse: il presidio non ha
        # prodotto nulla, oppure non c'e' nessuno a cui notificare. Senza
        # questa distinzione lo strumento darebbe un falso allarme su uno
        # studio senza utenti abilitati alla lettura dei fascicoli.
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            destinatari = conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM notifications WHERE tenant_id=?", (tenant,)
            ).fetchone()[0]
        motivo = "nessuna voce" if destinatari else "nessun destinatario: nessun utente abilitato a leggere i fascicoli"
        return {"totale": 0, "motivo": motivo, "esempi": []}
    except sqlite3.Error as exc:
        return {"totale": 0, "motivo": f"lettura notifiche non riuscita: {exc}", "esempi": []}


def _stato_web_push(percorsi: dict[str, Any], tenant: str) -> str:
    """Web Push non e' verificabile per singola PEC: si controlla il canale.

    Senza iscrizioni attive nessuna notifica puo' partire, e questa e' la
    causa piu' frequente di 'non mi arriva niente sul telefono'.
    """

    import sqlite3

    db = _percorso_notifiche(percorsi)
    if not db.exists():
        return "archivio notifiche assente"
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            attive = conn.execute(
                "SELECT COUNT(*) FROM push_subscriptions WHERE tenant_id=?", (tenant,)
            ).fetchone()[0]
    except sqlite3.Error as exc:
        return f"lettura iscrizioni non riuscita: {exc}"
    chiavi = bool(os.environ.get("VAPID_PRIVATE_KEY") or os.environ.get("WEB_PUSH_VAPID_PRIVATE_KEY"))
    if not attive:
        return "nessuna iscrizione: il browser dello studio non ha mai concesso il permesso"
    if not chiavi:
        return f"{attive} iscrizioni ma chiavi VAPID non configurate"
    return f"{attive} iscrizioni attive, chiavi VAPID presenti"


# --------------------------------------------------------------------------- #
# Esame di uno studio                                                           #
# --------------------------------------------------------------------------- #


def _battito_presidi() -> dict[str, Any]:
    """I job che alimentano la catena hanno davvero girato?

    E' il controllo che deve venire per primo: se lo scheduler e' fermo, ogni
    riga rossa qui sotto e' una conseguenza e non una causa, e cercare il
    guasto nelle singole PEC fa perdere tempo.
    """

    try:
        from pct.scheduler_health import presidio_heartbeat_for_config

        return presidio_heartbeat_for_config()
    except Exception as exc:
        return {"ok": False, "error": f"battito non leggibile: {exc}", "presidi": []}


def esamina_studio(
    percorsi: dict[str, Any], tenant: str, *, limite: int, tenant_notifiche: str = ""
) -> dict[str, Any]:
    """`tenant` identifica presidi e archivio PEC (slug); `tenant_notifiche` il
    centro notifiche, che il runtime scrive con l'id dello studio e non con lo
    slug. Confonderli fa dire allo strumento «nessuna notifica» su uno studio
    in cui le notifiche ci sono: il falso allarme che questo controllo esiste
    proprio per evitare."""

    email_db = Path(percorsi["EMAIL_CASELLA_DB"])
    pec_db = email_db.parent / "pec_audit.sqlite"
    if not pec_db.exists():
        return {"ok": False, "motivo": "Archivio PEC audit non presente: nessuna PEC e' mai stata acquisita.", "pec": []}

    repo = PecAuditRepository(
        pec_db,
        tenant_id=tenant,
        clienti_db_path=percorsi["CLIENTI_DB"],
        fascicoli_db_path=percorsi["FASCICOLI_DB"],
        fascicoli_docs_path=percorsi["FASCICOLI_DOCS"],
        scadenziario_db_path=percorsi["SCADENZIARIO_DB"],
        agenda_db_path=percorsi["AGENDA_DB"],
    )
    messaggi = repo.list_messages(limit=limite, include_details=True)
    esito: list[dict[str, Any]] = []
    for messaggio in messaggi:
        message_id = _testo(messaggio.get("id"))
        intestazioni = (messaggio.get("metadata") or {}).get("headers") or {}
        collegamento = messaggio.get("fascicolo_link") or {}
        fascicolo_id = _testo(collegamento.get("fascicolo_id"))

        try:
            dettaglio = repo.get_message_detail(message_id)
            analizzato = dettaglio.get("parsed") or {}
            classificazione = analizzato.get("legal_workflow") or {}
        except Exception as exc:
            classificazione = {"event_type": f"lettura non riuscita: {exc}"}

        presidi = _presidi_del_messaggio(percorsi, tenant, message_id)
        scadenze = _scadenze_del_messaggio(percorsi, message_id)
        appuntamenti = _appuntamenti_del_messaggio(percorsi, message_id)
        notifiche = _notifiche_del_messaggio(percorsi, tenant_notifiche or tenant, message_id, presidi)

        esito.append(
            {
                "id": message_id,
                "ricevuta": _testo(messaggio.get("received_at")),
                "mittente": _testo(intestazioni.get("from")),
                "oggetto": _testo(intestazioni.get("subject"))[:90],
                "evento": _testo(classificazione.get("event_type"), "non classificata"),
                "fascicolo": {
                    "id": fascicolo_id,
                    "stato": _testo(collegamento.get("status"), "non collegata"),
                    "motivo": _testo(collegamento.get("reason") or collegamento.get("motivo")),
                },
                "presidi": presidi,
                "scadenze": scadenze,
                "appuntamenti": appuntamenti,
                "notifiche": notifiche,
            }
        )
    return {"ok": True, "motivo": "", "pec": esito, "web_push": _stato_web_push(percorsi, tenant_notifiche or tenant)}


# --------------------------------------------------------------------------- #
# Stampa                                                                        #
# --------------------------------------------------------------------------- #


def _riga_anello(colorato: bool, etichetta: str, quante: int, dettaglio: str, atteso: bool) -> str:
    if quante:
        segno = _colora(colorato, VERDE, "OK  ")
    elif atteso:
        segno = _colora(colorato, ROSSO, "MANCA")
    else:
        segno = _colora(colorato, GRIGIO, "--  ")
    return f"      {segno} {etichetta:<14} {dettaglio}"


def stampa(report: dict[str, Any], *, colorato: bool) -> None:
    battito = report.get("presidi_scheduler") or {}
    print(_colora(colorato, GIALLO, "### Presidi pianificati"))
    if battito.get("error"):
        print(f"    {_colora(colorato, ROSSO, 'BLOCCO')} {battito['error']}")
    else:
        for voce in battito.get("presidi") or []:
            problema = _testo(voce.get("problem"))
            segno = _colora(colorato, ROSSO, "FERMO") if problema else _colora(colorato, VERDE, "OK   ")
            print(f"    {segno} {_testo(voce.get('job')):<38} {problema or _testo(voce.get('last_run'), 'ultimo giro regolare')}")
    for slug, studio in report["studi"].items():
        print()
        print(_colora(colorato, GIALLO, f"### Studio {slug}"))
        if not studio.get("ok"):
            print(f"    {_colora(colorato, ROSSO, 'BLOCCO')} {studio.get('motivo')}")
            continue
        print(f"    Web Push: {studio.get('web_push')}")
        if not studio["pec"]:
            print(f"    {_colora(colorato, ROSSO, 'Nessuna PEC in archivio.')}")
            continue
        for pec in studio["pec"]:
            print()
            print(f"    {pec['ricevuta']}  {pec['oggetto'] or '(senza oggetto)'}")
            print(f"      {_colora(colorato, GRIGIO, 'da ' + (pec['mittente'] or 'mittente ignoto'))}")
            evento = pec["evento"]
            print(f"      classificazione: {evento}")
            fascicolo = pec["fascicolo"]
            if fascicolo["id"]:
                print(f"      {_colora(colorato, VERDE, 'OK  ')} fascicolo       {fascicolo['id']} ({fascicolo['stato']})")
            else:
                motivo = fascicolo["motivo"] or "nessun fascicolo compatibile"
                print(f"      {_colora(colorato, ROSSO, 'MANCA')} fascicolo       {motivo}")
            # Senza fascicolo collegato il presidio non nasce per progetto:
            # segnalarlo come guasto sarebbe un falso allarme.
            atteso = bool(fascicolo["id"])
            print(_riga_anello(colorato, "presidio", len(pec["presidi"]), ", ".join(
                f"{p.get('status')}/{p.get('priority')}" for p in pec["presidi"]) or "nessun presidio", atteso))
            print(_riga_anello(colorato, "scadenziario", len(pec["scadenze"]), ", ".join(
                f"{s.get('data')} {s.get('titolo')}" for s in pec["scadenze"])[:110] or "nessuna scadenza", False))
            print(_riga_anello(colorato, "agenda", len(pec["appuntamenti"]), ", ".join(
                f"{a.get('data')} {a.get('titolo')}" for a in pec["appuntamenti"])[:110] or "nessun appuntamento", False))
            notifiche = pec["notifiche"]
            dettaglio = notifiche.get("motivo") or ", ".join(
                _testo(n.get("title"))[:60] for n in notifiche.get("esempi") or []
            ) or "nessuna voce"
            print(_riga_anello(colorato, "notifiche", int(notifiche.get("totale") or 0), dettaglio, atteso))


def esegui(*, registry: Path, tenant: str, limite: int) -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studi = [s for s in manager.lista() if not tenant or s.slug.lower() == tenant.lower()]
    report: dict[str, Any] = {
        "registry": str(registry),
        "limite": limite,
        "presidi_scheduler": _battito_presidi(),
        "studi": {},
    }
    for studio in studi:
        percorsi = manager.percorsi_dati(studio.slug, reconcile_aliases=False)
        try:
            report["studi"][studio.slug] = esamina_studio(
                percorsi,
                studio.slug,
                limite=limite,
                # Stessa regola dello scheduler (`_TENANT_NOTIFICATION_ID`) e
                # della lettura in UI (`current_tenant_id`): prima l'id.
                tenant_notifiche=_testo(getattr(studio, "id", "")) or studio.slug,
            )
        except Exception as exc:
            report["studi"][studio.slug] = {"ok": False, "motivo": f"esame non riuscito: {exc}", "pec": []}
    if tenant and not studi:
        report["studi"][tenant] = {"ok": False, "motivo": "Studio non presente nel registry.", "pec": []}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica che le ultime PEC arrivino in fascicolo, presidio, scadenziario, agenda, notifiche e Web Push."
    )
    parser.add_argument("--registry", default="", help="Percorso registry tenant; default da ambiente o data/tenants.json.")
    parser.add_argument("--tenant", default="", help="Slug studio; vuoto = tutti gli studi.")
    parser.add_argument("--limite", type=int, default=20, help="Quante PEC recenti esaminare per studio (default 20).")
    parser.add_argument("--json", action="store_true", help="Stampa il report in JSON invece che a schermo.")
    args = parser.parse_args()

    report = esegui(registry=_registry_path(args.registry), tenant=args.tenant, limite=max(1, args.limite))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0
    stampa(report, colorato=sys.stdout.isatty())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
