from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.giurisprudenza import GestioneGiurisprudenza
from web.app import create_app


class DummyResponse:
    def __init__(self, content: bytes, status_code: int = 200, url: str = "https://example.test"):
        self.content = content
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}


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

        page = client.get("/giurisprudenza/", follow_redirects=True)
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
        page = client.get("/giurisprudenza/", follow_redirects=True)
        html = page.get_data(as_text=True)

    assert 'Archivio Sentenze' in html
    assert 'url_for(\'giurisprudenza.index\')' not in html


def test_template_giurisprudenza_usa_layout_responsive():
    index_html = Path("web/templates/giurisprudenza/index.html").read_text(encoding="utf-8")
    form_html = Path("web/templates/giurisprudenza/form.html").read_text(encoding="utf-8")
    detail_html = Path("web/templates/giurisprudenza/dettaglio.html").read_text(encoding="utf-8")

    assert ".jud-actions .btn { width:100%; }" in index_html
    assert "Import assistito da materiale cliente" in index_html
    assert "Importa materiale cliente" in index_html
    assert ".jf-layout { display: grid;" in form_html
    assert "@media (max-width: 1199.98px)" in form_html
    assert "@media (max-width: 767.98px)" in detail_html
