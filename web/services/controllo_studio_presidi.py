"""Proiezione completa dei presidi: date espresse, identità e prossima azione."""

from urllib.parse import urlencode

from web.services.notification_presidia_runtime import (
    build_notification_presidio_repository, legal_notification_presidia_rollout, presidio_permissions,
)
from web.services.notification_presidia_payloads import NOTIFICATION_CASE_LABELS, NEXT_ACTIONS, STATUS_LABELS

TERMINALI = {"CLOSED", "NOT_REQUIRED", "CANCELLED", "LEGACY_ASSUMED_HANDLED"}


def righe_presidi() -> list[dict]:
    if not presidio_permissions()["can_read"]:
        return []
    if not legal_notification_presidia_rollout(fail_closed_on_error=False).get("enabled"):
        return []
    repo = build_notification_presidio_repository()
    righe, cursor = [], None
    while True:
        page = repo.list_presidia(cursor=cursor, limit=100)
        for item in page.items:
            riga = item.to_public_dict()
            stato = riga["status"]
            if stato in TERMINALI:
                continue
            progresso = riga["recipientProgress"]
            termine = str(riga.get("explicitDueAt") or "")
            righe.append({
                "id": f"presidio-{riga['id']}", "fascicolo_id": riga["fascicoloId"],
                "title": NOTIFICATION_CASE_LABELS.get(riga["notificationCase"].casefold(), "Notifica da verificare"),
                "subtitle": " · ".join(p for p in (
                    NEXT_ACTIONS.get(stato, "Esamina il presidio"),
                    f"Destinatari: {progresso['delivered']}/{progresso['total']} consegnati",
                    "Termine espresso nel documento" if termine else "Termine non determinato: verifica l'atto e il rito",
                ) if p),
                "due_at": termine, "badge": STATUS_LABELS.get(stato, "Da verificare"),
                "tone": "danger" if stato in {"DELIVERY_FAILED", "PARTIAL_DELIVERY"} else "warning",
                "href": "/notifiche-legali?" + urlencode({"section": "presidi", "presidio": riga["id"]}),
            })
        if not page.next_cursor:
            return righe
        cursor = page.next_cursor
