from pct.calendar_providers.demo import DemoCalendarProvider


def test_demo_provider_persists_push_pull_update_delete_with_cursor(tmp_path):
    provider = DemoCalendarProvider(tmp_path / "provider_events.json")
    account = {"id": "account-demo"}
    calendar = {"provider_calendar_id": "calendar-demo"}

    created = provider.push_event(
        account,
        calendar,
        {
            "title": "Udienza demo",
            "description": "Prima versione",
            "start": "2026-06-01T09:00:00",
            "end": "2026-06-01T10:00:00",
            "categories": ["IUSENTRA-AGENDA"],
        },
    )["event"]
    first_pull = provider.pull_changes(account, calendar)
    assert len(first_pull["events"]) == 1
    assert first_pull["events"][0]["id"] == created["id"]

    updated = provider.update_remote_event(created["id"], {"title": "Udienza aggiornata"})
    second_pull = provider.pull_changes(account, calendar, cursor=first_pull["cursor"])
    assert [item["id"] for item in second_pull["events"]] == [created["id"]]
    assert second_pull["events"][0]["title"] == "Udienza aggiornata"
    assert updated["etag"] != created["etag"]

    deleted = provider.delete_remote_event(created["id"])
    third_pull = provider.pull_changes(account, calendar, cursor=second_pull["cursor"])
    assert third_pull["events"][0]["deleted"] is True
    assert third_pull["events"][0]["id"] == deleted["id"]

    provider_reloaded = DemoCalendarProvider(tmp_path / "provider_events.json")
    assert provider_reloaded.get_event(created["id"])["deleted"] is True
