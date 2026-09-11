from __future__ import annotations

from types import SimpleNamespace

from scripts import backfill_fascicolo_document_texts as backfill


def _doc(document_id: str) -> SimpleNamespace:
    return SimpleNamespace(id=document_id)


def _source(document_id: str, sha256: str) -> SimpleNamespace:
    return SimpleNamespace(
        source_id=document_id,
        filename=f"{document_id}.pdf",
        safe_filename=f"{document_id}.pdf",
        sha256=sha256,
        supported=True,
        content_bytes=b"testo",
        content_path=None,
    )


def test_select_missing_sources_salta_i_documenti_gia_tentati_nel_run(monkeypatch):
    fascicolo = SimpleNamespace(id="F1", documenti=[_doc("D1"), _doc("D2"), _doc("D3")])
    sources = [_source("D1", "1" * 64), _source("D2", "2" * 64), _source("D3", "3" * 64)]

    class FakeManager:
        _studio_db = object()

        def tutti(self, archiviati: bool):
            assert archiviati is False
            return [fascicolo]

    class FakeRepo:
        tenant_id = "tenant-test"

        def _fascicoli_manager(self):
            return FakeManager()

    monkeypatch.setattr(
        backfill,
        "_texts_for_fascicolo",
        lambda **_kwargs: {"D1": "testo gia indicizzato"},
    )
    monkeypatch.setattr(
        backfill,
        "collect_fascicolo_document_sources",
        lambda **_kwargs: sources,
    )

    attempted = {backfill._source_key("F1", sources[1])}
    groups, stats = backfill._select_missing_sources(
        repo=FakeRepo(),
        paths={"FASCICOLI_DB": "fascicoli.json", "FASCICOLI_DOCS": "documenti"},
        limit=10,
        include_archived=False,
        exclude_source_keys=attempted,
    )

    assert stats["documents_seen"] == 3
    assert stats["documents_with_text"] == 1
    assert stats["documents_missing_text"] == 2
    assert stats["processable_missing_text"] == 2
    assert stats["skipped_attempted_this_run"] == 1
    assert stats["selected"] == 1
    assert [source.source_id for source in groups[0]["sources"]] == ["D3"]
