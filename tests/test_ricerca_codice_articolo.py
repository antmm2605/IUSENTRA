import hashlib

from web.services.react_legal_intelligence_bridge import (
    _filter_records_for_exact_reference,
    _record_reliability_note,
    _safe_official_archive_record,
)


def test_numbered_article_excludes_generic_cards_and_other_codes():
    exact = {"id": "cc-2043", "title": "c.c. — Codice civile", "registryNumber": "2043"}
    wrong_code = {"id": "cpc-2043", "title": "Codice di procedura civile", "registryNumber": "2043"}
    wrong_number = {"id": "cc-2044", "title": "Codice civile", "registryNumber": "2044"}
    generic = {"id": "card", "title": "Codice civile e articolo 2043", "registryNumber": ""}
    assert _filter_records_for_exact_reference([generic, wrong_code, exact, wrong_number],
                                               "codice civile articolo 2043") == [exact]
    assert _filter_records_for_exact_reference([generic, wrong_code, wrong_number],
                                               "art. 2043 c.c.") == []


def test_native_full_article_keeps_text_and_requires_matching_digest():
    text = "Art. 2043. Testo sintetico di prova. " * 40
    row = {"titolo": "c.c. — Codice civile", "articolo_o_chunk": "2043", "testo": text,
           "normative_scope": "articolo", "normative_full_text": text,
           "normative_full_text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    record = _safe_official_archive_record(row, 1, archive="normattiva")
    assert record["officialContext"] == text
    assert record["title"].endswith("Art. 2043")
    assert record["nativeArticleTextVerified"] is True
    row["normative_full_text"] += " altered"
    changed = _safe_official_archive_record(row, 1, archive="normattiva")
    assert changed["officialContext"] == ""
    assert changed["nativeArticleTextVerified"] is False


def test_completed_internal_context_is_not_attested_as_official_reading():
    note = _record_reliability_note({"contextCompleted": True, "sourceKind": "fonte ufficiale"})
    assert "Scheda interna" in note
    assert "letto" not in note


def test_document_search_citing_an_article_remains_document_search():
    document = {"id": "decision", "title": "PDF ufficiale Cassazione", "registryNumber": "",
                "sourceExcerpt": "Testo OCR: art. 606 c.p.p."}
    assert _filter_records_for_exact_reference([document], "PDF allegato art. 606 c.p.p.") == [document]


def test_existing_nir_identity_keeps_official_link_without_guessing():
    row = {"titolo": "Codice civile", "url_origine": "urn:nir:stato:regio.decreto:1942-03-16;262"}
    record = _safe_official_archive_record(row, 1, archive="normattiva")
    assert record["sourceHref"] == "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262"
    row["url_origine"] = "urn:"
    assert _safe_official_archive_record(row, 1, archive="normattiva")["sourceHref"] == ""


def test_verified_short_native_article_is_not_read_again_for_context(monkeypatch):
    from web.services import react_legal_intelligence_bridge as bridge
    def forbidden_read(*args, **kwargs):
        raise AssertionError("unchanged native article must not be read again")
    monkeypatch.setattr(bridge, "_build_official_context", forbidden_read)
    text = "Art. 2043. Testo sintetico breve."
    record = _safe_official_archive_record({
        "titolo": "Codice civile", "articolo_o_chunk": "2043", "testo": text,
        "url_origine": "urn:nir:stato:regio.decreto:1942-03-16;262",
        "normative_scope": "articolo", "normative_full_text": text,
        "normative_full_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }, 1, archive="normattiva")
    assert bridge._complete_record_context_from_official_source(record, "art.2043 codice civile") == record
