from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from pct.impostazioni_config_repository import (
    load_settings_config_section,
    save_settings_config_section,
)
from pct.legal_update_web_verification import fetch_official_reader_content
from tests.test_web_bootstrap import _cfg_web
from web.app import create_app


class _NewsRepository:
    row = {
        "id": 7,
        "slug": "aggiornamento-istituzionale",
        "title": "Aggiornamento istituzionale",
        "short_summary": "Sintesi pubblicata.",
        "content": "Testo pubblicato dalla fonte.",
        "news_type": "normativa",
        "published_at": "2026-08-15T09:30:00+02:00",
        "source_name": "Gazzetta Ufficiale",
        "source_code": "gazzetta_ufficiale",
        "source_category": "normativa",
        "source_url": "https://www.gazzettaufficiale.it/eli/id/2026/08/15/test/sg",
        "matter_name": "Diritto civile",
        "submatter_name": "Procedura civile",
        "publication_status": "published",
    }

    def list_news(self, *, limit: int):
        assert limit == 120
        return [dict(self.row)]

    def get_news_detail(self, news_id: int):
        return dict(self.row) if news_id == 7 else None


def _client(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "notiziario-test-key"
    return app.test_client(), {"X-API-Key": "notiziario-test-key"}


def test_interazioni_notiziario_restano_nel_database_tenant(tmp_path: Path):
    conn = sqlite3.connect(tmp_path / "studio.db")
    conn.row_factory = sqlite3.Row
    studio_db = SimpleNamespace(conn=conn, backend_kind="sqlite")

    timestamp = save_settings_config_section(
        studio_db,
        "notiziario_utente",
        {"interactions": {"7": {"read": True, "favorite": True}}},
        source="react_notiziario",
        updated_at="2026-08-15T10:00:00Z",
    )

    assert timestamp == "2026-08-15T10:00:00Z"
    assert load_settings_config_section(studio_db, "notiziario_utente") == {
        "interactions": {"7": {"read": True, "favorite": True}}
    }
    row = conn.execute("SELECT source FROM settings_config WHERE section = ?", ("notiziario_utente",)).fetchone()
    assert row["source"] == "react_notiziario"


def test_lettore_accetta_solo_fonti_istituzionali_e_restituisce_blocchi(monkeypatch):
    html = b"""
    <html><head><title>Gazzetta Ufficiale</title></head><body>
      <nav>Voce da escludere</nav>
      <main><h1>Ultime pubblicazioni</h1><p>Contenuto istituzionale pubblicato e leggibile nel pannello interno.</p></main>
    </body></html>
    """
    monkeypatch.setattr(
        "pct.legal_update_web_verification._download_limited",
        lambda *_args, **_kwargs: (html, "text/html; charset=utf-8"),
    )

    result = fetch_official_reader_content("https://www.gazzettaufficiale.it/")

    assert result["ok"] is True
    assert result["title"] == "Gazzetta Ufficiale"
    assert result["source_name"] == "Gazzetta Ufficiale"
    assert any("Contenuto istituzionale" in block for block in result["blocks"])
    assert all("Voce da escludere" not in block for block in result["blocks"])


def test_lettore_rifiuta_url_non_istituzionale(monkeypatch):
    called = False

    def _unexpected(*_args, **_kwargs):
        nonlocal called
        called = True
        return b"", ""

    monkeypatch.setattr("pct.legal_update_web_verification._download_limited", _unexpected)
    result = fetch_official_reader_content("https://example.invalid/notizia")

    assert result["ok"] is False
    assert called is False


def test_lettore_accetta_cf_news_come_fonte_editoriale_della_cassa(monkeypatch):
    html = b"""
    <html><head><title>CF News</title></head><body>
      <main><h1>Notizie dalla Cassa Forense</h1><p>Scadenza del Modello 5 e indicazioni operative per gli iscritti.</p></main>
    </body></html>
    """
    monkeypatch.setattr(
        "pct.legal_update_web_verification._download_limited",
        lambda *_args, **_kwargs: (html, "text/html; charset=utf-8"),
    )

    result = fetch_official_reader_content("https://www.cfnews.it/")

    assert result["ok"] is True
    assert result["source_name"] == "Cassa Forense"
    assert any("Modello 5" in block for block in result["blocks"])


def test_api_notiziario_espone_solo_dati_reali_e_stato_tenant(tmp_path: Path, monkeypatch):
    import web.blueprints.api_v1_react as api

    repository = _NewsRepository()
    monkeypatch.setattr(api, "get_legal_update_pipeline", lambda: SimpleNamespace(repository=repository))
    monkeypatch.setattr(api, "_notiziario_load_interactions", lambda: {
        "7": {"read": True, "favorite": True, "linkedCaseId": "CASE-1"}
    })
    monkeypatch.setattr(api, "_notiziario_case_options", lambda: [
        {"id": "CASE-1", "label": "RG 10/2026 - Fascicolo di prova"}
    ])
    client, headers = _client(tmp_path)

    response = client.get("/api/v1/ui/notiziario", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["contracts"]["mockFallback"] is False
    assert payload["items"] == [
        {
            "id": "7",
            "slug": "aggiornamento-istituzionale",
            "title": "Aggiornamento istituzionale",
            "summary": "Sintesi pubblicata.",
            "content": "Testo pubblicato dalla fonte.",
            "newsType": "normativa",
            "publishedAt": "2026-08-15T09:30:00+02:00",
            "sourceName": "Gazzetta Ufficiale",
            "sourceCode": "gazzetta_ufficiale",
            "sourceGroup": "gazzetta_ufficiale",
            "sourceUrl": "https://www.gazzettaufficiale.it/eli/id/2026/08/15/test/sg",
            "matterName": "Diritto civile",
            "submatterName": "Procedura civile",
            "read": True,
            "readAt": "",
            "favorite": True,
            "linkedCaseId": "CASE-1",
            "linkedCaseLabel": "RG 10/2026 - Fascicolo di prova",
        }
    ]
    assert payload["unreadCount"] == 0


def test_api_notiziario_espone_la_fonte_editoriale_ufficiale_della_cassa(tmp_path: Path, monkeypatch):
    import web.blueprints.api_v1_react as api

    monkeypatch.setattr(api, "get_legal_update_pipeline", lambda: SimpleNamespace(repository=_NewsRepository()))
    monkeypatch.setattr(api, "_notiziario_load_interactions", lambda: {})
    monkeypatch.setattr(api, "_notiziario_case_options", lambda: [])
    client, headers = _client(tmp_path)

    response = client.get("/api/v1/ui/notiziario", headers=headers)

    assert response.status_code == 200
    source = next(item for item in response.get_json()["quickSources"] if item["id"] == "cassa_forense")
    assert source == {
        "id": "cassa_forense",
        "label": "Cassa Forense",
        "url": "https://www.cfnews.it/",
        "requiresAuthentication": False,
    }


def test_api_interazione_salva_preferito_e_lettura(tmp_path: Path, monkeypatch):
    import web.blueprints.api_v1_react as api

    repository = _NewsRepository()
    saved: dict[str, object] = {}
    monkeypatch.setattr(api, "get_legal_update_pipeline", lambda: SimpleNamespace(repository=repository))
    monkeypatch.setattr(api, "_notiziario_load_interactions", lambda: {})
    monkeypatch.setattr(api, "_notiziario_save_interactions", lambda interactions: saved.update(interactions) or "2026-08-15T10:00:00Z")
    monkeypatch.setattr(api, "_notiziario_case_options", lambda: [])
    monkeypatch.setattr(api, "_audit_event", lambda *_args, **_kwargs: None)
    client, headers = _client(tmp_path)

    response = client.patch(
        "/api/v1/ui/notiziario/7/interazione",
        headers=headers,
        json={"read": True, "favorite": True},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["item"]["read"] is True
    assert payload["item"]["favorite"] is True
    assert saved["7"]["read"] is True
    assert saved["7"]["favorite"] is True




def _official_news_row() -> dict[str, object]:
    return {
        "id": "official_0123456789abcdef01234567",
        "slug": "pst-0123456789ab",
        "title": "Aggiornamento PST",
        "short_summary": "Indicazioni operative pubblicate dal Portale dei servizi telematici.",
        "content": "Indicazioni operative pubblicate dal Portale dei servizi telematici.",
        "news_type": "informazione_professionale",
        "published_at": "2026-08-17",
        "source_name": "PST Giustizia",
        "source_code": "pst_giustizia",
        "source_category": "informazione_professionale",
        "source_url": "https://pst.giustizia.it/PST/it/news.page",
        "matter_name": "",
        "submatter_name": "",
        "publication_status": "published",
    }


def test_api_aggiorna_sei_fonti_ufficiali_e_salva_la_cache_tenant(tmp_path: Path, monkeypatch):
    import web.blueprints.api_v1_react as api

    saved: dict[str, object] = {}
    source_states = [
        {
            "id": row["id"],
            "label": row["label"],
            "url": row["url"],
            "ok": True,
            "count": 1 if row["id"] == "pst_giustizia" else 0,
            "latestPublishedAt": "2026-08-17" if row["id"] == "pst_giustizia" else "",
            "message": "",
        }
        for row in api.SOURCE_DEFINITIONS
    ]
    monkeypatch.setattr(api, "_notiziario_load_cache", lambda: {"items": [], "sources": [], "refreshedAt": ""})
    monkeypatch.setattr(api, "refresh_notizie_utili", lambda **_kwargs: {
        "items": [_official_news_row()],
        "sources": source_states,
        "refreshedAt": "2026-08-17T10:00:00Z",
    })
    monkeypatch.setattr(api, "_notiziario_save_cache", lambda cache: saved.update(cache) or "2026-08-17T10:00:00Z")
    monkeypatch.setattr(api, "_notiziario_load_interactions", lambda: {})
    monkeypatch.setattr(api, "_notiziario_case_options", lambda: [])
    monkeypatch.setattr(api, "_audit_event", lambda *_args, **_kwargs: None)
    client, headers = _client(tmp_path)

    response = client.post("/api/v1/ui/notiziario/aggiorna", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["items"][0]["sourceGroup"] == "pst_giustizia"
    assert [row["id"] for row in payload["quickSources"]] == [
        "giustizia",
        "pst_giustizia",
        "cnf",
        "cassa_forense",
        "gazzetta_ufficiale",
        "cassazione",
    ]
    assert "fatture_corrispettivi" not in {row["id"] for row in payload["quickSources"]}
    assert saved["items"][0]["id"] == "official_0123456789abcdef01234567"


def test_api_interazione_supporta_notizie_ufficiali_della_cache(tmp_path: Path, monkeypatch):
    import web.blueprints.api_v1_react as api

    saved: dict[str, object] = {}
    monkeypatch.setattr(api, "_notiziario_cache_item", lambda _news_id: _official_news_row())
    monkeypatch.setattr(api, "_notiziario_load_interactions", lambda: {})
    monkeypatch.setattr(api, "_notiziario_save_interactions", lambda interactions: saved.update(interactions) or "2026-08-17T10:00:00Z")
    monkeypatch.setattr(api, "_notiziario_case_options", lambda: [])
    monkeypatch.setattr(api, "_audit_event", lambda *_args, **_kwargs: None)
    client, headers = _client(tmp_path)

    response = client.patch(
        "/api/v1/ui/notiziario/official_0123456789abcdef01234567/interazione",
        headers=headers,
        json={"read": True, "favorite": True},
    )

    assert response.status_code == 200
    assert response.get_json()["item"]["read"] is True
    assert saved["official_0123456789abcdef01234567"]["favorite"] is True

def test_api_fonte_rapida_usa_il_lettore_governato(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "pct.legal_update_web_verification.fetch_official_reader_content",
        lambda *_args, **_kwargs: {
            "ok": True,
            "title": "CNF",
            "source_name": "Consiglio Nazionale Forense",
            "blocks": ["Aggiornamento pubblicato dal Consiglio Nazionale Forense."],
            "message": "",
        },
    )
    client, headers = _client(tmp_path)

    response = client.get("/api/v1/ui/notiziario/fonti/cnf", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["title"] == "CNF"
    assert payload["blocks"] == ["Aggiornamento pubblicato dal Consiglio Nazionale Forense."]
