import io
import json
import zipfile
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.giurisprudenza import GIURISPRUDENZA_STORAGE_VERSION, GestioneGiurisprudenza
from web.app import create_app


class DummyResponse:
    def __init__(
        self,
        content: bytes,
        status_code: int = 200,
        url: str = "https://example.test",
        content_type: str = "text/html; charset=utf-8",
    ):
        self.content = content
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": content_type}


def _dummy_get_factory(mapping):
    def _get(url, *args, **kwargs):
        payload = mapping.get(url)
        if payload is None:
            raise AssertionError(f"URL non atteso nel test: {url}")
        if isinstance(payload, DummyResponse):
            return payload
        content = payload.get("content", b"")
        if isinstance(content, str):
            content = content.encode("utf-8")
        return DummyResponse(
            content,
            status_code=payload.get("status_code", 200),
            url=payload.get("url", url),
            content_type=payload.get("content_type", "text/html; charset=utf-8"),
        )

    return _get


def _build_corte_cost_zip(records: list[dict]) -> bytes:
    inner_buffer = io.BytesIO()
    with zipfile.ZipFile(inner_buffer, "w", compression=zipfile.ZIP_DEFLATED) as inner_zip:
        inner_zip.writestr(
            "pronunce_2026.json",
            json.dumps({"elenco_pronunce": records}, ensure_ascii=False).encode("cp1252", errors="ignore"),
        )
    outer_buffer = io.BytesIO()
    with zipfile.ZipFile(outer_buffer, "w", compression=zipfile.ZIP_DEFLATED) as outer_zip:
        outer_zip.writestr("P_json_2026.zip", inner_buffer.getvalue())
    return outer_buffer.getvalue()


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
        "LEGAL_INTELLIGENCE_DB": str(tmp_path / "intelligence.json"),
        "NORMATIVE_TABLES_DB": str(tmp_path / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(tmp_path / "giurisprudenza.json"),
    }


def _login_admin(cfg: dict) -> None:
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    ).crea(
        username="admin-giurisprudenza",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )


def test_giurisprudenza_salva_e_cerca_per_classificazione(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))

    saved = gestore.salva(
        {
            "titolo": "Cassazione su consenso informato in responsabilita medica",
            "source_system": "cassazione",
            "area": "Civile",
            "branca": "Responsabilita civile",
            "sottobranca": "Responsabilita medica",
            "microtema": "consenso informato",
            "numero_provvedimento": "1234/2026",
            "data_deposito": "2026-04-10",
            "massima": "La prova del consenso informato deve essere specifica e documentata.",
            "uso_nel_software": "citabile in atto",
        }
    )

    found = gestore.cerca(area="Civile", branca="Responsabilita civile", q="consenso")

    assert saved["id"]
    assert len(found) == 1
    assert found[0]["microtema"] == "consenso informato"
    assert found[0]["anno"] == "2026"


def test_storage_v2_migra_giudizi_esistenti_e_seed_fonti(tmp_path: Path):
    db_path = tmp_path / "giurisprudenza.json"
    db_path.write_text(
        json.dumps(
            {
                "judgments": [
                    {
                        "id": "j-1",
                        "titolo": "Sentenza di merito su appalto",
                        "source_system": "manuale_interno",
                        "massima": "Il collaudo non esclude l'inadempimento.",
                        "fascicoli_collegati": ["FASC-001"],
                        "created_at": "2026-04-10T10:00:00",
                        "updated_at": "2026-04-10T10:00:00",
                    }
                ],
                "sync_runs": [
                    {
                        "id": "run-1",
                        "source_id": "manuale_interno",
                        "checked_at": "2026-04-10T10:30:00",
                        "status": "manuale",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    gestore = GestioneGiurisprudenza(str(db_path))
    record = gestore.get("j-1")
    stats = gestore.storage_stats()

    assert stats["storage_version"] == GIURISPRUDENZA_STORAGE_VERSION
    assert stats["legal_sources"] >= 8
    assert stats["ingestion_runs"] == 1
    assert stats["judgment_texts"] == 1
    assert stats["practice_judgments"] == 1
    assert record is not None
    assert record["text_versions_count"] == 1
    assert record["practice_links_count"] == 1
    assert record["testo_normalizzato"] == "Il collaudo non esclude l'inadempimento."


def test_sync_openga_importa_e_aggiorna_dataset_ufficiale(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    search_url = "https://openga.giustizia-amministrativa.it/api/3/action/package_search?q=sentenze&rows=100"
    resource_url = "https://openga.giustizia-amministrativa.it/dataset/tar-lazio-2026.json"
    search_payload = {
        "result": {
            "results": [
                {
                    "metadata_modified": "2026-04-12T12:00:00",
                    "resources": [
                        {
                            "format": "JSON",
                            "name": "Sentenze TAR Lazio 2026",
                            "url": resource_url,
                        }
                    ],
                }
            ]
        }
    }
    first_rows = [
        {
            "TIPO_PROVVEDIMENTO": "sentenza",
            "NOME_SEDE": "TAR Lazio - Roma",
            "NOME_SEZIONE": "Sezione III",
            "NUMERO_PROVVEDIMENTO": "1001",
            "DATA_PUBBLICAZIONE": "2026-04-12",
            "TIPO_RICORSO": "Appalti pubblici",
            "TIPO_UDIENZA": "Pubblica",
            "ESITO_PROVVEDIMENTO": "Accoglimento",
            "OGGETTO_RICORSO": "Revisione prezzi e riequilibrio contrattuale negli appalti pubblici.",
            "CODICE_SEDE": "TAR-LAZIO",
        }
    ]

    report = gestore.sync_sources(
        source_ids=["openga"],
        request_get=_dummy_get_factory(
            {
                search_url: {
                    "content": json.dumps(search_payload, ensure_ascii=False),
                    "content_type": "application/json",
                },
                resource_url: {
                    "content": json.dumps(first_rows, ensure_ascii=False),
                    "content_type": "application/json",
                },
            }
        ),
    )

    rows = gestore.cerca(source_system="openga")
    record = gestore.get(rows[0]["id"])

    assert report["ok"] is True
    assert report["imported_total"] == 1
    assert report["updated_total"] == 0
    assert report["changed_total"] == 1
    assert len(rows) == 1
    assert rows[0]["grado"] == "TAR"
    assert rows[0]["organo_giudicante"] == "TAR Lazio - Roma"
    assert rows[0]["area"] == "Amministrativo"
    assert rows[0]["branca"] == "Appalti pubblici"
    assert rows[0]["sottobranca"] == "Revisione prezzi"
    assert rows[0]["materia"] == "Appalti pubblici"
    assert record["raw_documents_count"] == 1
    assert record["text_versions_count"] == 1

    second_rows = [dict(first_rows[0], OGGETTO_RICORSO="Revisione prezzi, compensazione e riequilibrio del contratto pubblico.")]
    report_update = gestore.sync_sources(
        source_ids=["openga"],
        request_get=_dummy_get_factory(
            {
                search_url: {
                    "content": json.dumps(search_payload, ensure_ascii=False),
                    "content_type": "application/json",
                },
                resource_url: {
                    "content": json.dumps(second_rows, ensure_ascii=False),
                    "content_type": "application/json",
                },
            }
        ),
    )

    rows_after = gestore.cerca(source_system="openga")
    updated_record = gestore.get(rows_after[0]["id"])

    assert report_update["imported_total"] == 0
    assert report_update["updated_total"] == 1
    assert report_update["changed_total"] == 1
    assert len(rows_after) == 1
    assert updated_record["text_versions_count"] == 2
    assert "compensazione" in updated_record["testo_normalizzato"].lower()


def test_sync_corte_costituzionale_importa_dataset_open_data(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    page_url = "https://dati.cortecostituzionale.it/Scarica_i_dati/Scarica_i_dati"
    zip_url = "https://dati.cortecostituzionale.it/opendata/distribuzione/pronunce/P_json2001_oggi.zip"
    page_html = f"""
    <html><body>
      <a href="{zip_url}">Scarica pronunce JSON</a>
    </body></html>
    """
    zip_bytes = _build_corte_cost_zip(
        [
            {
                "numero_pronuncia": "77",
                "anno_pronuncia": "2026",
                "data_decisione": "2026-04-01",
                "data_deposito": "2026-04-09",
                "epigrafe": "Giudizio di legittimita costituzionale in via incidentale.",
                "testo": "La Corte dichiara l'illegittimita costituzionale della norma nei limiti indicati.",
                "dispositivo": "Illegittimita costituzionale parziale.",
                "ecli": "ECLI:IT:COST:2026:77",
                "tipologia_pronuncia": "S",
                "presidente": "Rossi",
                "relatore_pronuncia": "Bianchi",
            }
        ]
    )

    report = gestore.sync_sources(
        source_ids=["corte_costituzionale"],
        request_get=_dummy_get_factory(
            {
                page_url: {"content": page_html},
                zip_url: {"content": zip_bytes, "content_type": "application/zip"},
            }
        ),
    )

    rows = gestore.cerca(source_system="corte_costituzionale")
    record = gestore.get(rows[0]["id"])

    assert report["ok"] is True
    assert report["imported_total"] == 1
    assert len(rows) == 1
    assert rows[0]["ecli"] == "ECLI:IT:COST:2026:77"
    assert rows[0]["grado"] == "Corte costituzionale"
    assert rows[0]["tipo_provvedimento"] == "Sentenza"
    assert record["raw_documents_count"] == 1
    assert record["text_versions_count"] == 1
    assert "illegittimita costituzionale" in record["testo_normalizzato"].lower()


def test_sync_fonte_pubblica_importa_candidati(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    html = b"""
    <html><head><title>Massimario Cassazione</title></head>
    <body>
      <main>
        <a href="/sentenze/123">Sentenza n. 1234/2026 su consenso informato</a>
        <p>Depositata il 10/04/2026 ECLI:IT:CASS:2026:1234</p>
      </main>
    </body></html>
    """

    report = gestore.sync_sources(
        source_ids=["cassazione"],
        request_get=lambda *args, **kwargs: DummyResponse(
            html,
            url="https://www.cortedicassazione.it/it/massimario.page",
        ),
    )

    rows = gestore.cerca(source_system="cassazione")

    assert report["ok"] is True
    assert report["imported_total"] == 1
    assert len(rows) == 1
    assert rows[0]["ecli"] == "ECLI:IT:CASS:2026:1234"
    assert rows[0]["source_label"] == "Corte di Cassazione"


def test_sync_curia_importa_homepage_pubblica(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    html = b"""
    <html><body>
      <a href="/site/jcms/p1_1000082060/en/recent-judgment-joined-cases-c-696/23-p">
        Recent judgment: Joined cases C-696/23 P Pumpyanskiy and C-704/23 P Khudaverdyan v Council
      </a>
      <a href="/site/upload/docs/application/pdf/2026-03/cp260049en.pdf">
        Judgment of the Court in Case C-412/24 Faure Le Page
      </a>
      <a href="/site/upload/docs/application/pdf/2026-03/cp260049it.pdf">IT</a>
    </body></html>
    """

    report = gestore.sync_sources(
        source_ids=["curia"],
        request_get=lambda *args, **kwargs: DummyResponse(
            html,
            url="https://curia.europa.eu/site/",
        ),
    )

    rows = gestore.cerca(source_system="curia")

    assert report["ok"] is True
    assert report["imported_total"] == 2
    assert len(rows) == 2
    assert any("C-696/23 P" in (row.get("numero_provvedimento") or "") for row in rows)
    assert any("C-412/24" in (row.get("numero_provvedimento") or "") for row in rows)


def test_sync_hudoc_importa_feed_rss(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    rss = b"""
    <rss version="2.0">
      <channel>
        <title>ECHR HUDOC Search Feed</title>
        <item>
          <title>CASE OF H.D. v. ITALY</title>
          <pubDate>Thu, 09 Apr 2026 00:00:00 GMT</pubDate>
          <description>41645/23 - Chamber Judgment</description>
          <link>http://hudoc.echr.coe.int/eng#{&quot;itemid&quot;:[&quot;001-249529&quot;]}</link>
        </item>
      </channel>
    </rss>
    """

    report = gestore.sync_sources(
        source_ids=["hudoc"],
        request_get=lambda *args, **kwargs: DummyResponse(
            rss,
            url="https://hudoc.echr.coe.int/app/transform/rss",
            content_type="text/xml; charset=utf-8",
        ),
    )

    rows = gestore.cerca(source_system="hudoc")

    assert report["ok"] is True
    assert report["imported_total"] == 1
    assert len(rows) == 1
    assert rows[0]["numero_provvedimento"] == "41645/23"
    assert rows[0]["url_origine"] == "https://hudoc.echr.coe.int/?i=001-249529"
    assert rows[0]["data_deposito"] == "2026-04-09"


def test_sync_fonte_protetta_restituisce_handoff(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))

    report = gestore.sync_sources(source_ids=["merito_civile_bdp"])

    assert report["ok"] is True
    assert report["imported_total"] == 0
    assert report["runs"][0]["status"] == "handoff_richiesto"


def test_importa_da_url_pubblico_compila_metadati(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    html = b"""
    <html><head><title>Sentenza n. 77 del 09/04/2026</title></head>
    <body><main>ECLI:IT:COST:2026:77 Massima di prova.</main></body></html>
    """

    record = gestore.importa_da_url(
        "https://www.cortecostituzionale.it/actionSchedaPronuncia.do?anno=2026&numero=77",
        request_get=lambda *args, **kwargs: DummyResponse(
            html,
            url="https://www.cortecostituzionale.it/actionSchedaPronuncia.do?anno=2026&numero=77",
        ),
    )

    assert record["source_system"] == "corte_costituzionale"
    assert record["ecli"] == "ECLI:IT:COST:2026:77"
    assert record["data_deposito"] == "2026-04-09"
    assert gestore.get(record["id"])["raw_documents_count"] == 1


def test_importa_da_materiale_simpliciter_crea_e_aggiorna_schede(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    sample = """
    Sentenza n. 123/2026 Corte di Cassazione
    ECLI:IT:CASS:2026:123
    Massima: Il consenso informato va provato in modo specifico.

    Ordinanza n. 77/2026 TAR Lazio
    Accesso agli atti negli appalti pubblici.
    """

    first = gestore.importa_da_materiale(
        source_id="simpliciter_cliente",
        source_url="https://simpliciter.ai/ricerca/",
        pasted_text=sample,
        hints={"area": "Amministrativo", "uso_nel_software": "precedente forte"},
    )
    second = gestore.importa_da_materiale(
        source_id="simpliciter_cliente",
        source_url="https://simpliciter.ai/ricerca/",
        pasted_text=sample,
    )

    rows = gestore.cerca(source_system="simpliciter_cliente")

    assert first["imported"] == 2
    assert second["updated"] == 2
    assert len(rows) == 2
    assert any(row["ecli"] == "ECLI:IT:CASS:2026:123" for row in rows)
    assert any(row["source_label"] == "Simpliciter (materiale cliente)" for row in rows)


def test_importa_da_materiale_autoclassifica_tassonomia(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))

    report = gestore.importa_da_materiale(
        source_id="simpliciter_cliente",
        source_url="https://simpliciter.ai/ricerca/",
        pasted_text=(
            "Ordinanza n. 77/2026 TAR Lazio\n"
            "Accesso agli atti negli appalti pubblici e accesso difensivo del concorrente escluso."
        ),
    )

    record = report["records"][0]

    assert record["area"] == "Amministrativo"
    assert record["branca"] == "Appalti pubblici"
    assert record["sottobranca"] == "Accesso agli atti"


def test_importa_da_materiale_html_file(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    html = b"""
    <html><body><main>
      <h1>Sentenza n. 456/2026 Consiglio di Stato</h1>
      <p>Massima: il soccorso istruttorio non sana l'offerta tecnica.</p>
    </main></body></html>
    """

    report = gestore.importa_da_materiale(
        source_id="simpliciter_cliente",
        source_url="https://simpliciter.ai/ricerca/",
        file_name="simpliciter-export.html",
        file_bytes=html,
    )

    assert report["imported"] == 1
    record = report["records"][0]
    assert record["titolo"]
    assert "soccorso istruttorio" in record["massima"].lower()


def test_statistiche_sync_pubblici_include_fonti_europee(tmp_path: Path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))

    stats = gestore.statistiche()

    assert stats["sync_pubblici"] >= 5


def test_blueprint_archivio_sentenze_renderizza_indice_e_salvataggio(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _login_admin(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-giurisprudenza", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        page = client.get("/giurisprudenza/?_legacy=1", follow_redirects=True)
        html = page.get_data(as_text=True)
        assert page.status_code == 200
        assert "Archivio Sentenze" in html
        assert "Nuova scheda sentenza" in html

        save = client.post(
            "/giurisprudenza/nuova",
            data={
                "source_system": "manuale_interno",
                "titolo": "TAR su accesso agli atti negli appalti",
                "giurisdizione": "Amministrativa",
                "area": "Amministrativo",
                "branca": "Appalti pubblici",
                "sottobranca": "Accesso agli atti",
                "numero_provvedimento": "456/2026",
                "data_deposito": "2026-04-11",
                "massima": "L'accesso difensivo prevale nei limiti di stretta pertinenza.",
                "uso_nel_software": "precedente forte",
            },
            follow_redirects=True,
        )
        detail_html = save.get_data(as_text=True)

    assert save.status_code == 200
    assert "Scheda Sentenza" in detail_html
    assert "TAR su accesso agli atti negli appalti" in detail_html
    assert "precedente forte" in detail_html
    assert "Archivio tecnico" in detail_html
    assert "Testo normalizzato e archivio redazionale" in detail_html


def test_blueprint_importa_materiale_cliente(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _login_admin(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "admin-giurisprudenza", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            "/giurisprudenza/importa-materiale",
            data={
                "source_system": "simpliciter_cliente",
                "source_url": "https://simpliciter.ai/ricerca/",
                "materiale_text": "Sentenza n. 321/2026 Corte di Cassazione\nMassima: la prescrizione va eccepita.",
                "area_hint": "Civile",
                "uso_nel_software_hint": "citabile in atto",
            },
            follow_redirects=True,
        )
        html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Aggiorna scheda sentenza" in html
    assert "Simpliciter (materiale cliente)" in html


def test_blueprint_classificazione_suggerita_api_compila_tassonomia(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _login_admin(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "admin-giurisprudenza", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            "/giurisprudenza/api/classificazione-suggerita",
            data={
                "source_system": "simpliciter_cliente",
                "source_url": "https://simpliciter.ai/ricerca/",
                "materiale_text": "Sentenza TAR Lazio su accesso agli atti negli appalti pubblici.",
            },
        )
        payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["suggestion"]["area"] == "Amministrativo"
    assert payload["suggestion"]["branca"] == "Appalti pubblici"
    assert payload["suggestion"]["sottobranca"] == "Accesso agli atti"


def test_blueprint_sync_avvia_job_in_background(tmp_path: Path, monkeypatch):
    cfg = _cfg_web(tmp_path)
    _login_admin(cfg)
    app = create_app(cfg)
    captured = {}

    def fake_start(app_obj, *, giurisprudenza_db_path: str, source_ids=None):
        captured["db_path"] = giurisprudenza_db_path
        captured["source_ids"] = list(source_ids or [])
        return {"started": True, "already_running": False, "source_ids": captured["source_ids"]}

    monkeypatch.setattr("web.blueprints.giurisprudenza.start_giurisprudenza_sync_job", fake_start)

    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "admin-giurisprudenza", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post("/giurisprudenza/sync?_legacy=1", follow_redirects=True)
        html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Recupero automatico da fonti ufficiali avviato in background" in html
    assert captured["db_path"].endswith("giurisprudenza.json")
    assert "openga" in captured["source_ids"]
    assert "cassazione" in captured["source_ids"]
    assert "simpliciter_cliente" not in captured["source_ids"]


def test_sidebar_studio_espone_archivio_sentente(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _login_admin(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "admin-giurisprudenza", "password": "Admin1234!"},
            follow_redirects=True,
        )
        page = client.get("/giurisprudenza/?_legacy=1", follow_redirects=True)
        html = page.get_data(as_text=True)

    assert 'Archivio Sentenze' in html
    assert 'url_for(\'giurisprudenza.index\')' not in html


def test_template_giurisprudenza_usa_layout_responsive():
    index_html = Path("web/templates/giurisprudenza/index.html").read_text(encoding="utf-8")
    form_html = Path("web/templates/giurisprudenza/form.html").read_text(encoding="utf-8")
    detail_html = Path("web/templates/giurisprudenza/dettaglio.html").read_text(encoding="utf-8")
    theme_css = Path("web/static/css/theme.css").read_text(encoding="utf-8")

    assert ".jud-actions .btn" in theme_css
    assert "width: 100%;" in theme_css or "width:100%" in theme_css
    assert "Import assistito da materiale cliente" in index_html
    assert "Importa materiale cliente" in index_html
    assert "Recupero automatico da fonti ufficiali" in index_html
    assert "Suggerimenti tassonomici automatici" in index_html
    assert "Documenti raw" in index_html
    assert "Licenza / note" in index_html
    assert ".jf-layout { display: grid;" in form_html
    assert "@media (max-width: 1199.98px)" in form_html
    assert "@media (max-width: 767.98px)" in form_html
    assert "Testo normalizzato e archivio redazionale" in detail_html
    assert "Archivio tecnico" in detail_html
