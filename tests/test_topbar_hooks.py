from pathlib import Path


def test_topbar_notifications_e_scadenze_non_pollano_a_pannelli_chiusi():
    notifications = Path("frontend/src/hooks/useNotifications.ts").read_text(encoding="utf-8")
    deadlines = Path("frontend/src/hooks/useQuickDeadlines.ts").read_text(encoding="utf-8")

    assert "if (!open) return" in notifications
    # Il polling a pannello aperto non ricarica durante un salvataggio in corso.
    assert "window.setInterval(() => { if (!saving.current) void load({ silent: true }) }, 30000)" in notifications
    assert "const interval = open ? 30000 : 60000" not in notifications
    assert "iusentra:notifications-updated" in notifications

    assert "if (!open) return" in deadlines
    assert "window.setInterval(() => load({ silent: true }), 120000)" in deadlines
    assert "Pre-fetch al mount" not in deadlines
    # Gli aggiornamenti operativi arrivano dal bus condiviso, ma ricaricano
    # solo a pannello aperto.
    assert "useOperationalRefresh(['agenda', 'scadenze', 'comunicazioni'], () => { if (open && !saving.current)" in notifications
    assert "useOperationalRefresh(['agenda', 'scadenze'], () => { if (open) load({ silent: true }) })" in deadlines


def test_topbar_notifiche_legge_solo_il_repository_persistente():
    operational = Path("web/services/topbar_operational.py").read_text(encoding="utf-8")
    persistent_section = operational.split("def _persistent_notification_items", 1)[1].split("def _record_to_topbar_item", 1)[0]

    assert "service.repository.list_notifications" in persistent_section
    assert "_notification_items(user)" not in persistent_section
    assert "sync_operational_items" not in persistent_section
    assert 'raise TopbarApiError("Centro notifiche non disponibile.", 503)' in persistent_section
