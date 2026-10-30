"""La ricerca normale riusa indici disponibili, senza scansioni o nuovi import."""

import hashlib
import io
import sqlite3
from contextlib import closing
from types import SimpleNamespace

import pytest

from lex.contracts import GuardVerdict, LexRequest, LexResponse, ProviderDraft
from lex.normativa import normattiva_importer as importer
from lex.retrieval import official_sources_retriever as retriever
from lex.retrieval.cache import LexRetrievalCache
from lex.retrieval.normativa import _archive_row_to_source
from lex.retrieval.orchestrator import RetrievalOrchestrator
from lex.retrieval.sources.normative import NormativeSource
from lex.ricerca_giuridica.indice_fts import sincronizza_fts


@pytest.fixture(autouse=True)
def lexical_catalogs_only(monkeypatch):
    """Questi archivi sintetici non richiedono modelli o servizi di embedding."""
    monkeypatch.setenv("LEX_RICERCA_SEMANTICA", "0")


def archive(path, *, text=None, indexed=False, article="327"):
    # closing(): «with sqlite3.connect()» fa solo commit. Una connessione lasciata al garbage collector
    # trasferisce il WAL nell'archivio a metà test e cambia la revisione su cui si basa la cache.
    with closing(sqlite3.connect(path)) as conn, conn:
        importer.ensure_schema(conn)
        if text:
            document = importer.DocumentRecord(
                collection_name="controlled", zip_path="controlled.zip", xml_entry="atto.xml",
                tipo_atto="CODICE", numero="1443", data_atto="1940-10-28",
                data_pubblicazione="1940-10-28", titolo="Codice di procedura civile",
                urn="urn:nir:stato:regio.decreto:1940-10-28;1443", redazione_id=None,
                vigenza="EDIZIONE_ACQUISITA", xml_sha256=hashlib.sha256((text + article).encode("utf-8")).hexdigest(),
                text_content="", topics=[], relevance_score=5, is_relevant=True,
                articles=[importer.ArticleRecord(article, "Decadenza", text, [], 1)],
            )
            document_id = importer.insert_document(conn, document, store_full_text=False)
            importer.insert_articles_and_chunks(
                conn, document_id, document, jsonl_file=io.StringIO(),
                max_chunk_chars=1800, only_relevant_articles=False,
            )
            conn.commit()
        if indexed:
            sincronizza_fts(conn)
    return path


def forbid_legacy(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Una richiesta normale non avvia scansioni o letture ZIP/JSONL")

    for name in ("_search_normattiva_db", "_search_normattiva_raw_code_articles", "_search_jsonl"):
        monkeypatch.setattr(retriever, name, forbidden)


def test_native_unindexed_archive_remains_explicit_without_starting_engine(tmp_path, monkeypatch):
    from lex.ricerca_giuridica import ibrida

    path = archive(tmp_path / "unindexed.sqlite", text="Art. 327. Testo controllato.")
    before = path.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("Un archivio privo di indice non avvia motori o preparazioni")

    monkeypatch.setattr(ibrida, "motore_per_db", forbidden)
    assert ibrida.cerca_normattiva_indicizzata("art. 327 c.p.c.", path) is None
    assert path.read_bytes() == before
    with sqlite3.connect(path) as conn:
        assert not ibrida.indice_fts_presente(conn)


def test_native_missing_archive_never_creates_file_or_engine(tmp_path, monkeypatch):
    from lex.ricerca_giuridica import ibrida

    path = tmp_path / "missing.sqlite"

    def forbidden(*args, **kwargs):
        raise AssertionError("Un archivio assente non avvia motori o crea database")

    monkeypatch.setattr(ibrida, "motore_per_db", forbidden)
    assert ibrida.cerca_normattiva_indicizzata("art. 327 c.p.c.", path) is None
    assert not path.exists()


def test_runtime_uses_existing_library_if_general_archive_has_no_index(tmp_path, monkeypatch):
    general = archive(tmp_path / "normattiva.sqlite")
    archive(tmp_path / "codici_leggi.sqlite", text="L'appello non può proporsi dopo sei mesi.", indexed=True)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    monkeypatch.setenv("LEX_RICERCA_SEMANTICA", "0")
    forbid_legacy(monkeypatch)
    rows = retriever.search_normattiva("art. 327 c.p.c.")
    assert rows and "sei mesi" in rows[0]["testo"]
    assert rows[0]["vigenza"] == "EDIZIONE_ACQUISITA"


def test_runtime_keeps_the_larger_indexed_general_archive(tmp_path, monkeypatch):
    general = archive(tmp_path / "normattiva.sqlite", text="Testo acquisito nell'archivio generale.", indexed=True)
    archive(tmp_path / "codici_leggi.sqlite", text="Testo della biblioteca separata.", indexed=True)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    monkeypatch.setenv("LEX_RICERCA_SEMANTICA", "0")
    forbid_legacy(monkeypatch)
    rows = retriever.search_normattiva("art. 327 c.p.c.")
    assert rows and "archivio generale" in rows[0]["testo"]
    assert any("biblioteca separata" in row["testo"] for row in rows)
    assert {row["archive_catalog"] for row in rows} == {"archivio_generale", "biblioteca_codici_leggi"}


def test_missing_indexes_are_explicit_without_scanning(tmp_path, monkeypatch):
    general = archive(tmp_path / "normattiva.sqlite")
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    forbid_legacy(monkeypatch)
    with pytest.raises(RuntimeError, match="indic"):
        retriever.search_normattiva("art. 327 c.p.c.")


def test_acquired_edition_and_provenance_reach_the_evidence_adapter():
    source = _archive_row_to_source({
        "chunk_id": "urn:controlled:xmlsha:art327:chunk1", "chunk_rowid": 1,
        "document_id": 1, "titolo": "Codice di procedura civile", "testo": "Testo acquisito.",
        "url_origine": "urn:nir:stato:regio.decreto:1940-10-28;1443",
        "vigenza": "EDIZIONE_ACQUISITA", "hash_sha256": "a" * 64,
        "data_acquisizione": "2026-10-16T05:00:00Z",
        "archive_catalog": "biblioteca_codici_leggi",
        "articolo_o_chunk": "327",
    }, source_type="normativa_normattiva", default_title="Normattiva")
    assert source.source_id == "urn:controlled:xmlsha:art327:chunk1"
    assert source.metadata["vigenza"] == "edizione_acquisita"
    assert source.metadata["source_hash"] == "a" * 64
    assert source.metadata["acquired_at"] == "2026-10-16T05:00:00Z"
    assert source.metadata["archive_catalog"] == "biblioteca_codici_leggi"
    assert source.metadata["urn"] == "urn:nir:stato:regio.decreto:1940-10-28;1443"
    assert source.metadata["official_url"] == "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443:1~art327"


def test_catalog_revision_invalidates_cached_legal_queries(tmp_path, monkeypatch):
    general = archive(tmp_path / "normattiva.sqlite")
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    request = LexRequest(tenant_id="controlled", user_id="tester", session_id="catalog", query="art. 327 c.p.c.")
    cache = LexRetrievalCache()
    before = cache.build_key(request, {}, "normativa")
    archive(tmp_path / "codici_leggi.sqlite", text="L'appello non può proporsi dopo sei mesi.", indexed=True)
    assert cache.build_key(request, {}, "normativa") != before


def test_nonlegal_and_free_web_cache_do_not_inspect_normative_archives(monkeypatch):
    def forbidden():
        raise AssertionError("Non è una dipendenza di questa richiesta")

    monkeypatch.setattr("lex.retrieval.normativa_catalog.catalog_revision", forbidden)
    cache = LexRetrievalCache()
    for metadata, query, workflow in [({}, "La mia agenda", "studio_data_lookup"),
                                      ({"source_mode": "free_web"}, "Leggi questa pagina pubblica", "research")]:
        request = LexRequest(tenant_id="controlled", user_id="tester", session_id="scope", query=query, metadata=metadata)
        assert cache.build_key(request, {}, workflow)


def test_unavailable_index_is_a_visible_diagnostic_not_evidence_and_survives_cache(tmp_path, monkeypatch):
    from lex.orchestrator_workflow import run_workflow

    general = archive(tmp_path / "normattiva.sqlite")
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    monkeypatch.setattr("lex.retrieval.normativa._search_gazzetta", lambda *args, **kwargs: [])
    forbid_legacy(monkeypatch)
    retrieval = RetrievalOrchestrator(
        query_planner=SimpleNamespace(plan=lambda request, context, workflow: [request.query]),
        source_router=SimpleNamespace(resolve=lambda request, context, workflow: [NormativeSource()]),
        retrieval_cache=LexRetrievalCache(),
    )
    orchestrator = SimpleNamespace(
        workflow_router=SimpleNamespace(resolve_workflow=lambda request: "normativa"),
        workflow_context_builder=SimpleNamespace(build_request_context=lambda request, workflow: {}),
        retrieval_orchestrator=retrieval,
        guard_orchestrator=SimpleNamespace(run_pre=lambda *args: GuardVerdict(True), run_post=lambda *args: GuardVerdict(True)),
        provider_registry=SimpleNamespace(pick=lambda *args: SimpleNamespace(generate=lambda **kwargs: ProviderDraft("Nessuna evidenza acquisita."))),
        response_formatter=SimpleNamespace(build_response=lambda **kwargs: LexResponse(answer=kwargs["draft"].text)),
        memory=None, telemetry=None,
    )
    request = LexRequest(tenant_id="controlled", user_id="tester", session_id="missing", query="art. 327 c.p.c.", allow_external_research=False)
    first = run_workflow(orchestrator, request)
    second = run_workflow(orchestrator, request)
    assert first.warnings == second.warnings == ["Indice Normattiva non disponibile: la ricerca locale non è stata eseguita."]
    assert second.metadata["normativa_diagnostics"] == ["normativa_index_unavailable"]
    payload = retrieval.collect(request, {}, "normativa")
    assert payload["items"] == [] and payload["cache"]["hit"] is True


def test_client_cannot_supply_server_catalog_diagnostics(monkeypatch):
    retrieval = RetrievalOrchestrator(
        query_planner=SimpleNamespace(plan=lambda request, context, workflow: [request.query]),
        source_router=SimpleNamespace(resolve=lambda *args: []), retrieval_cache=LexRetrievalCache(),
    )
    request = LexRequest(tenant_id="controlled", user_id="tester", session_id="injection", query="La mia agenda",
                         allow_external_research=False, metadata={"_normativa_diagnostics": ["normativa_index_unavailable"]})
    payload = retrieval.collect(request, {}, "studio_data_lookup")
    assert payload["evidence_pack"]["metadata"]["normativa_diagnostics"] == []


def test_indexed_empty_result_never_starts_raw_inspection(tmp_path, monkeypatch):
    general = archive(tmp_path / "normattiva.sqlite", text="Testo acquisito.", indexed=True)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    monkeypatch.setattr(retriever, "_search_normattiva_indexed", lambda *args, **kwargs: [])
    forbid_legacy(monkeypatch)
    diagnostics = []
    assert retriever.search_normattiva("art. 327 c.p.c.", diagnostics=diagnostics) == []
    assert diagnostics == []


def test_library_scope_is_reported_even_without_matching_results(tmp_path, monkeypatch):
    general = archive(tmp_path / "normattiva.sqlite")
    archive(tmp_path / "codici_leggi.sqlite", text="Testo acquisito.", indexed=True)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    monkeypatch.setattr(retriever, "_search_normattiva_indexed", lambda *args, **kwargs: [])
    forbid_legacy(monkeypatch)
    diagnostics = []
    assert retriever.search_normattiva("art. 327 c.p.c.", diagnostics=diagnostics) == []
    assert diagnostics == ["normativa_library_scope"]


def test_normal_verbatim_reader_uses_same_runtime_catalog(tmp_path, monkeypatch):
    from lex.risposte_certe import risposta_certa

    general = archive(tmp_path / "normattiva.sqlite")
    archive(tmp_path / "codici_leggi.sqlite", text="L'appello non può proporsi dopo sei mesi.", indexed=True)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    result = risposta_certa("Riporta il testo dell'art. 327 c.p.c.", runtime_catalog=True)
    assert result.tipo == "testo_articolo"
    assert "sei mesi" in result.testo
    assert "biblioteca" in result.testo
    assert "vigenza attuale non attestata" in result.testo


def test_normal_verbatim_reader_distinguishes_unavailable_index_from_missing_article(tmp_path, monkeypatch):
    from lex.risposte_certe import risposta_certa

    general = archive(tmp_path / "normattiva.sqlite")
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    result = risposta_certa("Riporta il testo dell'art. 327 c.p.c.", runtime_catalog=True)
    assert result.tipo == "testo_articolo_indice_non_disponibile"
    assert "Indice Normattiva non disponibile" in result.testo
    assert "non è nell'archivio" not in result.testo


def test_http_verbatim_reader_uses_catalog_when_app_has_no_explicit_path(tmp_path, monkeypatch):
    from flask import Flask

    from lex.orchestrator_http import _risposta_certa_http

    general = archive(tmp_path / "normattiva.sqlite")
    archive(tmp_path / "codici_leggi.sqlite", text="L'appello non può proporsi dopo sei mesi.", indexed=True)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    with Flask(__name__).app_context():
        answer = _risposta_certa_http("Riporta il testo dell'art. 327 c.p.c.")
    assert "sei mesi" in answer and "biblioteca" in answer
    assert "~art327" in answer


def test_deadline_calculation_does_not_open_normative_catalog(monkeypatch):
    from lex.risposte_certe import risposta_certa

    def forbidden(*args):
        raise AssertionError("Il calcolo nativo non richiede il catalogo")

    monkeypatch.setattr("lex.retrieval.normativa_catalog.select_runtime_catalog", forbidden)
    result = risposta_certa("Qual è il termine per l'appello civile?", runtime_catalog=True)
    assert result.tipo != "testo_articolo"


def test_explicit_local_normative_query_does_not_collect_other_catalogs():
    from lex.retrieval.source_router import SourceRouter

    request = LexRequest(tenant_id="controlled", user_id="tester", session_id="local",
        query="Analizza il rapporto tra contumacia e decadenza nell'art. 327 c.p.c., basandoti esclusivamente sui testi locali acquisiti.")
    sources = SourceRouter().resolve(request, {}, "normativa")
    assert [source.source_name for source in sources] == ["normative"]


@pytest.mark.parametrize("query", [
    "Cerca anche la giurisprudenza sull'art. 327 c.p.c. nelle fonti locali acquisite.",
    "Analizza l'art. 327 c.p.c. confrontando le fonti.",
    "Non usare soltanto fonti locali per l'art. 327 c.p.c.; cerca anche sul web.",
    "Analizza l'art. 327 c.p.c. usando solo le fonti locali e la Gazzetta acquisita.",
])
def test_other_legal_research_keeps_existing_sources(query):
    from lex.retrieval.source_router import SourceRouter

    request = LexRequest(tenant_id="controlled", user_id="tester", session_id="mixed", query=query)
    names = [source.source_name for source in SourceRouter().resolve(request, {}, "normativa")]
    assert "normative" in names and "giurisprudenza" in names


def test_local_normative_request_does_not_reintroduce_studio_seed(tmp_path, monkeypatch):
    from lex.retrieval.source_router import SourceRouter

    general = archive(tmp_path / "normattiva.sqlite")
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    request = LexRequest(tenant_id="controlled", user_id="tester", session_id="seed",
        query="Analizza l'art. 327 c.p.c. usando solo le fonti locali acquisite.")
    retrieval = RetrievalOrchestrator(source_router=SourceRouter(), retrieval_cache=LexRetrievalCache())

    def forbidden(*args):
        raise AssertionError("Il contesto dello studio non è stato richiesto")

    monkeypatch.setattr(retrieval, "_studio_context_seed_results", forbidden)
    monkeypatch.setattr(NormativeSource, "search", lambda *args: [])
    result = retrieval.collect(request, {"studio": {"sources": [{"type": "giurisprudenza", "title": "Altra causa"}]}}, "normativa")
    assert result["items"] == []


def test_local_normative_scope_preserves_linked_case_requests():
    from lex.retrieval.source_router import SourceRouter

    request = LexRequest(tenant_id="controlled", user_id="tester", session_id="case", fascicolo_id="CASE",
        query="Analizza l'art. 327 c.p.c. usando solo le fonti locali acquisite.")
    names = [source.source_name for source in SourceRouter().resolve(request, {}, "normativa")]
    assert "fascicoli" in names and "documenti" in names


def test_exact_local_scope_keeps_only_the_matching_normative_reference(monkeypatch):
    from lex.retrieval.source_router import SourceRouter

    monkeypatch.setattr("lex.retrieval.normativa._search_normattiva", lambda *args, **kwargs: [
        {"titolo": "Codice di procedura civile", "testo": "Art. 327. Testo acquisito.", "riferimento_esatto": True},
        {"titolo": "Imposte e immigrazione", "testo": "Studi e ricerca sui dati acquisiti.", "riferimento_esatto": False},
    ])

    gazzetta_calls = []

    def forbidden(*args, **kwargs):
        gazzetta_calls.append(True)
        raise AssertionError("Il riferimento esatto ha già un produttore indicizzato")

    monkeypatch.setattr("lex.retrieval.normativa._search_gazzetta", forbidden)
    request = LexRequest(tenant_id="controlled", user_id="tester", session_id="reference",
        query="Analizza l'art. 327 c.p.c. usando solo le fonti locali acquisite.")
    source = SourceRouter().resolve(request, {}, "normativa")[0]
    rows = source.search([request.query], request, {})
    assert len(rows) == 1 and rows[0].title == "Codice di procedura civile"
    assert gazzetta_calls == []


def test_indexed_general_gap_uses_library_without_replacing_primary(tmp_path, monkeypatch):
    general = archive(tmp_path / "normattiva.sqlite", text="Altro articolo acquisito.", article="1", indexed=True)
    archive(tmp_path / "codici_leggi.sqlite", text="L'appello non può proporsi dopo sei mesi.", indexed=True)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    monkeypatch.setenv("LEX_RICERCA_SEMANTICA", "0")
    forbid_legacy(monkeypatch)
    diagnostics = []
    rows = retriever.search_normattiva("art. 327 c.p.c.", diagnostics=diagnostics)
    assert rows and "sei mesi" in rows[0]["testo"]
    assert rows[0]["archive_catalog"] == "biblioteca_codici_leggi"
    assert diagnostics == ["normativa_library_supplement"]


def test_verbatim_fills_indexed_general_gap_by_bound_document_ids(tmp_path, monkeypatch):
    from lex import testi_ufficiali
    from lex.risposte_certe import risposta_certa

    general = archive(tmp_path / "normattiva.sqlite", text="Altro articolo acquisito.", article="1", indexed=True)
    archive(tmp_path / "codici_leggi.sqlite", text="L'appello non può proporsi dopo sei mesi.", indexed=True)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    monkeypatch.setenv("LEX_RICERCA_SEMANTICA", "0")
    original = testi_ufficiali._documenti

    def bound_documents(conn, request, *, document_id=None):
        assert document_id is not None, "La richiesta normale non enumera il catalogo documenti"
        return original(conn, request, document_id=document_id)

    monkeypatch.setattr(testi_ufficiali, "_documenti", bound_documents)
    result = risposta_certa("Riporta il testo dell'art. 327 c.p.c.", runtime_catalog=True)
    assert result.tipo == "testo_articolo" and "sei mesi" in result.testo
    assert "Consultata anche la biblioteca" in result.testo
    assert "non è ancora indicizzato" not in result.testo


def test_library_completes_only_missing_references_of_same_act(tmp_path, monkeypatch):
    general = archive(tmp_path / "normattiva.sqlite", text="Termine breve acquisito.", article="325", indexed=True)
    archive(tmp_path / "codici_leggi.sqlite", text="Termine lungo acquisito.", article="327", indexed=True)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(general))
    monkeypatch.setenv("LEX_RICERCA_SEMANTICA", "0")
    forbid_legacy(monkeypatch)
    rows = retriever.search_normattiva("articoli 325 e 327 c.p.c.")
    assert {row["articolo_o_chunk"] for row in rows if row.get("riferimento_esatto")} == {"325", "327"}
    assert next(row for row in rows if row["articolo_o_chunk"] == "325")["archive_catalog"] == "archivio_generale"
    assert next(row for row in rows if row["articolo_o_chunk"] == "327")["archive_catalog"] == "biblioteca_codici_leggi"


def test_normative_http_label_comes_from_actual_workflow(monkeypatch):
    from types import SimpleNamespace
    from lex.contracts import LexResponse
    from lex.http_bounded_bridge import build_bounded_http_payload

    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: SimpleNamespace(
        ask=lambda request: LexResponse(answer="Testo controllato", metadata={"workflow": "normativa"})))
    monkeypatch.setattr("lex.operational_knowledge.integration.build_operational_http_payload", lambda **kwargs: None)
    query = "Analizza l'art. 327 c.p.c. usando esclusivamente i testi locali acquisiti. Niente dati dello studio."
    payload = build_bounded_http_payload(user=SimpleNamespace(id="tester"), studio=SimpleNamespace(slug="controlled"),
        data={}, current_user_message=query, resolved_effective_question=query, attachments=[],
        studio_context={"focus_label": "configurazione studio e sincronizzazioni", "focus_topic": "studio",
                        "request_profile": {"intent": "normativa"}})
    assert payload["reference_label"] == "ricerca normativa locale"
    assert payload["focus_label"] == "ricerca normativa locale"
    assert payload["focus_topic"] == "ricerca_legale"


def test_fts_incrementale_senza_callback_non_conta_tutti_i_pendenti(tmp_path):
    path = archive(tmp_path / "incrementale.sqlite", text="Art. 327. Termine controllato.")
    queries = []
    with sqlite3.connect(path) as conn:
        conn.set_trace_callback(queries.append)
        first = sincronizza_fts(conn)
        second = sincronizza_fts(conn)
        assert first.indicizzati == 1
        assert second.indicizzati == 0 and second.gia_presenti == 1
        assert conn.execute("SELECT rowid FROM normative_fts").fetchall() == conn.execute(
            "SELECT id FROM normative_chunks ORDER BY id"
        ).fetchall()
    normalized = [" ".join(query.upper().split()) for query in queries]
    assert not any("SELECT COUNT(*) FROM NORMATIVE_CHUNKS C WHERE NOT EXISTS" in query for query in normalized)


def test_fts_callback_conserva_totale_esatto_e_avanzamento(tmp_path):
    path = archive(tmp_path / "avanzamento.sqlite", text="Art. 327. Primo termine controllato.")
    archive(path, text="Art. 328. Secondo termine controllato.", article="328")
    progress = []
    with sqlite3.connect(path) as conn:
        result = sincronizza_fts(conn, blocco=1, progresso=lambda done, total: progress.append((done, total)))
        assert result.indicizzati == 2
        assert progress == [(1, 2), (2, 2)]
        assert conn.execute("SELECT rowid FROM normative_fts ORDER BY rowid").fetchall() == conn.execute(
            "SELECT id FROM normative_chunks ORDER BY id"
        ).fetchall()


def test_fts_riscontro_id_con_buchi_e_orfano_non_legge_testi_gia_indicizzati(tmp_path):
    path = archive(tmp_path / "buchi.sqlite", text="Primo termine.", article="327", indexed=True)
    archive(path, text="Articolo rimosso prima della sincronizzazione.", article="328")
    archive(path, text="Terzo termine da indicizzare.", article="329")
    queries = []
    progress = []
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM normative_chunks WHERE id=2")
        conn.execute("INSERT INTO normative_fts_info(chunk_id,document_id) VALUES (999,1)")
        conn.commit()
        conn.set_trace_callback(queries.append)
        result = sincronizza_fts(conn, blocco=1, progresso=lambda done, total: progress.append((done,total)))
        assert result.indicizzati == 1 and result.orfani == 1
        assert progress == [(1,1)]
        assert conn.execute("SELECT rowid FROM normative_fts ORDER BY rowid").fetchall() == [(1,),(3,)]
        assert not conn.execute("SELECT 1 FROM sqlite_temp_master WHERE name='_iusentra_fts_pending'").fetchone()
    text_reads = [q for q in queries if "c.chunk_text" in q]
    assert text_reads and all("WHERE c.id IN (SELECT chunk_id FROM temp._iusentra_fts_pending" in q for q in text_reads)


def test_exact_download_resolves_existing_chunk_and_preserves_parent_checks(tmp_path, monkeypatch):
    from lex.retrieval.normativa_catalog import leggi_chunk_archiviato, NormativaIndexUnavailable
    path = archive(tmp_path / "normattiva.sqlite", text="Art. 327. Testo conservato.", indexed=True)
    with sqlite3.connect(path) as connection:
        key = connection.execute("SELECT chunk_key FROM normative_chunks LIMIT 1").fetchone()[0]
    before = path.read_bytes()
    result = leggi_chunk_archiviato(key, path)
    assert "Testo conservato" in result["normative_full_text"]
    assert path.read_bytes() == before
    assert leggi_chunk_archiviato("normattiva:absent", path) is None
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE normative_documents SET xml_sha256='changed'")
    with pytest.raises(NormativaIndexUnavailable):
        leggi_chunk_archiviato(key, path)


def test_archive_fixture_is_stable_after_garbage_collection(tmp_path, monkeypatch):
    """Il GC non deve cambiare la revisione di una fixture gia completata."""
    import gc
    from lex.retrieval.normativa_catalog import catalog_revision

    gc.collect()
    path = archive(tmp_path / "fixture-completed.sqlite")
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(path))
    before = catalog_revision()
    gc.collect()
    assert catalog_revision() == before
