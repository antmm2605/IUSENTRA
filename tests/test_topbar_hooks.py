from pathlib import Path


def test_topbar_notifications_e_scadenze_non_pollano_a_pannelli_chiusi():
    notifications = Path("frontend/src/hooks/useNotifications.ts").read_text(encoding="utf-8")
    deadlines = Path("frontend/src/hooks/useQuickDeadlines.ts").read_text(encoding="utf-8")

    assert "if (!open) return" in notifications
    assert "window.setInterval(load, 30000)" in notifications
    assert "const interval = open ? 30000 : 60000" not in notifications
    assert "iusentra:notifications-updated" in notifications

    assert "if (!open) return" in deadlines
    assert "window.setInterval(load, 120000)" in deadlines
    assert "Pre-fetch al mount" not in deadlines
