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


from web.services import react_legal_intelligence_bridge as bridge

def _article_identity_record(number,text,*,edition='a'*64,article_id=1,chunk='first'):
 return bridge._safe_official_archive_record({'chunk_id':chunk,'hash_sha256':edition,'normative_article_id':article_id,'titolo':'c.c. — Codice civile','articolo_o_chunk':number,'testo':text,'url_origine':'urn:nir:stato:regio.decreto:1942-03-16;262','normative_scope':'articolo','normative_full_text':text,'normative_full_text_sha256':hashlib.sha256(text.encode()).hexdigest()},1,archive='normattiva')
def test_same_act_url_keeps_article_identity_and_text():
 a=_article_identity_record('2043','Art. 2043. Testo breve.',article_id=10,chunk='art2043')
 b=_article_identity_record('2343','Art. 2343. Testo diverso molto piu lungo. '*40,article_id=11,chunk='art2343')
 rows=bridge._dedupe_records([a,b]);assert len(rows)==2
 selected=bridge._filter_records_for_exact_reference(rows,'codice civile articolo 2043')
 assert len(selected)==1 and selected[0]['officialContext']==a['officialContext']
 assert selected[0]['sourceExcerpt']==a['sourceExcerpt']
 assert bridge._dedupe_records([b,a])==[b,a]
def test_versions_same_number_remain_distinct():
 a=_article_identity_record('2043','Art.2043. Edizione precedente.',edition='a'*64)
 b=_article_identity_record('2043','Art.2043. Edizione successiva modificata.',edition='b'*64)
 assert len(bridge._dedupe_records([a,b]))==2
def test_multiple_chunks_same_verified_article_deduplicated():
 a=_article_identity_record('2043','Art.2043. Testo completo.',chunk='chunk1')
 b=_article_identity_record('2043','Art.2043. Testo completo.',chunk='chunk2')
 assert bridge._dedupe_records([a,b])==[a]
def test_generic_act_card_cannot_replace_verified_article():
 a=_article_identity_record('2043','Art.2043. Testo completo.')
 generic={'id':'generic','title':'Codice civile','sourceHref':a['sourceHref'],'sourceExcerpt':'Descrizione atto '*500,'contextCompleted':True}
 rows=bridge._dedupe_records([a,generic]);assert len(rows)==2 and rows[0]==a
def test_unverified_records_keep_existing_url_deduplication():
 a={'id':'one','sourceHref':'https://example.org/act','subtitle':'breve'}
 b={'id':'two','sourceHref':'https://example.org/act','subtitle':'testo lungo '*30}
 assert len(bridge._dedupe_records([a,b]))==1


def test_direct_verified_native_article_does_not_need_public_fallback():
    record = _article_identity_record('2043', 'Art. 2043. Testo breve verificato.')
    for query in ('codice civile articolo 2043', 'art. 2043 c.c.', 'testo integrale art.2043 codice civile'):
        assert bridge._needs_public_fallback([record], query) is False


def test_native_article_fallback_preserves_missing_identity_and_current_law_checks():
    record = _article_identity_record('2043', 'Art. 2043. Testo breve verificato.')
    for query in ('codice civile articolo 2044', 'art.2043 codice procedura civile',
                  'testo vigente art.2043 codice civile', 'giurisprudenza relativa art.2043 codice civile'):
        assert bridge._needs_public_fallback([record], query) is True
    invalid = dict(record, nativeArticleTextVerified=False)
    assert bridge._needs_public_fallback([invalid], 'codice civile articolo 2043') is True
    assert bridge._needs_public_fallback([], 'codice civile articolo 2043') is True
