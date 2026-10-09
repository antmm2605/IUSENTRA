"""Guardrails for cache invalidation; browser acceptance is separate."""
import json

from web.services.admin_database_statistics_cache import mirror_statistics


class FileStats:
    def __init__(self, path):
        self.percorsi = {"controlled": path}
        self.calls = 0

    def statistiche(self):
        self.calls += 1
        path = self.percorsi["controlled"]
        return {"moduli": [{"record_totali": len(json.loads(path.read_text())), "stato": "OK"}]}


def test_unchanged_metadata_reuses_counts_and_callers_cannot_mutate_cache(tmp_path):
    path = tmp_path / "controlled.json"
    path.write_text('[1]')
    stats = FileStats(path)
    first = mirror_statistics(stats)
    first["moduli"][0]["record_totali"] = 999
    assert mirror_statistics(stats)["moduli"][0]["record_totali"] == 1
    assert stats.calls == 1
    path.write_text('[1,2]')
    assert mirror_statistics(stats)["moduli"][0]["record_totali"] == 2
    assert stats.calls == 2


def test_tenants_do_not_share_statistics_and_errors_are_not_retained(tmp_path):
    one = tmp_path / "one.json"
    two = tmp_path / "two.json"
    one.write_text('[1]')
    two.write_text('[1,2]')
    assert mirror_statistics(FileStats(one))["moduli"][0]["record_totali"] == 1
    assert mirror_statistics(FileStats(two))["moduli"][0]["record_totali"] == 2
    failing = FileStats(tmp_path / "missing.json")
    failing.statistiche = lambda: {"moduli": [{"stato": "ERRORE"}]}
    assert mirror_statistics(failing)["moduli"][0]["stato"] == "ERRORE"
    failing.percorsi["controlled"].write_text('[3]')
    failing.statistiche = lambda: {"moduli": [{"stato": "OK", "record_totali": 1}]}
    assert mirror_statistics(failing)["moduli"][0]["stato"] == "OK"


def test_sqlite_wal_commit_invalidates_statistics_before_checkpoint(tmp_path):
    path = tmp_path / "search.sqlite"
    path.write_text('[1]')
    stats = FileStats(path)
    mirror_statistics(stats)
    mirror_statistics(stats)
    assert stats.calls == 1
    wal = tmp_path / "search.sqlite-wal"
    wal.write_bytes(b'new committed transaction')
    mirror_statistics(stats)
    assert stats.calls == 2
    wal.unlink()
    mirror_statistics(stats)
    assert stats.calls == 3


def test_expiration_reloads_even_when_metadata_has_not_changed(tmp_path, monkeypatch):
    from web.services import admin_database_statistics_cache as cache

    path = tmp_path / "controlled.json"
    path.write_text('[1]')
    stats = FileStats(path)
    clock = [100.0]
    monkeypatch.setattr(cache, "monotonic", lambda: clock[0])
    mirror_statistics(stats)
    clock[0] = 131.0
    mirror_statistics(stats)
    assert stats.calls == 2


def test_files_changed_during_read_are_never_cached(tmp_path):
    path = tmp_path / "controlled.json"
    path.write_text('[1]')
    stats = FileStats(path)
    original = stats.statistiche

    def changed_read():
        result = original()
        path.write_text('[1,2]')
        return result

    stats.statistiche = changed_read
    assert mirror_statistics(stats)["moduli"][0]["record_totali"] == 1
    stats.statistiche = original
    assert mirror_statistics(stats)["moduli"][0]["record_totali"] == 2
    assert stats.calls == 2
