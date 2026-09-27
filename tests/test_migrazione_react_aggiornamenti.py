"""Migrazione React: «Aggiornamenti legali» e «Copertura AI» nel pannello di piattaforma.

Le viste storiche `/admin/aggiornamenti-legali/*` e `/admin/copertura-ai/*` si
aprono nell'applicazione React di piattaforma; pagine e azioni
(`/api/v1/ui/piattaforma/<pagina>[/azioni/<azione>]`) chiamano gli stessi
servizi delle rotte storiche, con gli stessi argomenti. Le operazioni lente o
di rete (ricerca nelle fonti, acquisizione, analisi, pubblicazione) sono
sostituite da registratori che verificano gli argomenti.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_migrazione_react_piattaforma import _app, _login_superadmin

PAGINE = {
    "/admin/aggiornamenti-legali": "aggiornamenti-legali",
    "/admin/aggiornamenti-legali/": "aggiornamenti-legali",
    "/admin/aggiornamenti-legali/fonti": "aggiornamenti-fonti",
    "/admin/aggiornamenti-legali/staging": "aggiornamenti-staging",
    "/admin/aggiornamenti-legali/analisi": "aggiornamenti-analisi",
    "/admin/aggiornamenti-legali/archivio": "aggiornamenti-archivio",
    "/admin/aggiornamenti-legali/review": "aggiornamenti-revisione",
    "/admin/copertura-ai": "copertura-ai",
    "/admin/copertura-ai/": "copertura-ai",
    "/admin/copertura-ai/review": "copertura-ai-revisione",
}
SPEC = {
    "subbranch_profile": {"subbranch_code": "CIVILE_LOCAZIONI"},
    "procedure": {"code": "SFRATTO_MOROSITA", "subbranch_code": "CIVILE_LOCAZIONI", "name": "Sfratto per morosità"},
}
KIND = {"metrics", "status", "table", "facts", "notes", "shortcuts", "actions", "form"}


@pytest.fixture()
def app(tmp_path: Path):
    applicazione = _app(tmp_path)
    # Archivi condivisi del motore e della copertura nella cartella del test.
    applicazione.config["LEGAL_INTELLIGENCE_DB"] = str(tmp_path / "intelligence" / "motori.json")
    applicazione.config["GIURISPRUDENZA_DB"] = str(tmp_path / "intelligence" / "giurisprudenza.json")
    applicazione.config["LEGAL_COVERAGE_SQLITE_DB"] = str(tmp_path / "intelligence" / "legal_coverage.db")
    return applicazione


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        _login_superadmin(c)
        yield c


def _pagina(client, chiave: str, query: str = "") -> dict:
    risposta = client.get(f"/api/v1/ui/piattaforma/{chiave}{query}")
    corpo = risposta.get_json()
    assert risposta.status_code == 200 and corpo["ok"] is True, (chiave, corpo)
    return corpo


def _azione(client, chiave: str, azione: str, params: dict | None = None, values: dict | None = None) -> dict:
    corpo = {"params": params or {}, "values": values or {}}
    assert "tenant_slug" not in json.dumps(corpo)
    risposta = client.post(f"/api/v1/ui/piattaforma/{chiave}/azioni/{azione}", json=corpo)
    assert risposta.status_code == 200, risposta.get_data(as_text=True)
    return risposta.get_json()


def _sezione(corpo: dict, titolo: str) -> dict:
    return next(s for s in corpo["sections"] if s["title"].startswith(titolo))


def _seed_motore(app) -> dict:
    """Un ciclo reale del motore sulla Gazzetta, con la risposta di rete simulata."""
    from tests.test_legal_updates_pipeline import DummyResponse, _normativa_html
    from web.services.legal_update_surface import build_legal_update_pipeline_runtime

    with app.app_context():
        pipeline = build_legal_update_pipeline_runtime(tenant_slug="")
        pipeline.run_cycle(
            source_codes=["gazzetta_ufficiale"],
            request_get=lambda *a, **k: DummyResponse(_normativa_html(), url="https://www.gazzettaufficiale.it/"),
            auto_publish=False,
        )
        return {"review": pipeline.repository.list_review_queue(limit=10)[0], "raw": pipeline.repository.list_raw_documents(limit=10)[0]}


def _seed_bozza(app, spec: dict | None = None) -> int:
    from web.services.legal_coverage_surface import build_repository

    with app.app_context():
        repo = build_repository(tenant_slug="")
        repo.ensure_schema()
        return repo.create_draft({
            "subbranch_code": "CIVILE_LOCAZIONI",
            "procedure_code": "SFRATTO_MOROSITA",
            "spec_json": spec or SPEC,
            "validation_report_json": {"score": 40, "errors": [], "warnings": ["Blocco mancante o vuoto: templates"]},
            "status": "needs_review",
            "risk_level": "MEDIUM",
        })


# ------------------------------------------------------------------ pagine


def test_pagine_nella_applicazione_react(client):
    for percorso, chiave in PAGINE.items():
        html = client.get(percorso).get_data(as_text=True)
        assert 'id="piattaforma-react-root"' in html and f'data-pagina="{chiave}"' in html, percorso
    html = client.get("/admin/aggiornamenti-legali/staging/7").get_data(as_text=True)
    assert 'data-pagina="aggiornamenti-staging-scheda"' in html and "&#34;id&#34;: &#34;7&#34;" in html


def test_vista_classica_ancora_raggiungibile(client, app):
    _seed_motore(app)
    for percorso in [*PAGINE, "/admin/aggiornamenti-legali/archivio?tab=news"]:
        separatore = "&" if "?" in percorso else "?"
        risposta = client.get(f"{percorso}{separatore}_legacy=1")
        assert risposta.status_code == 200, percorso
        assert "piattaforma-react-root" not in risposta.get_data(as_text=True), percorso


def test_dati_delle_pagine_dal_servizio(client, app):
    semi = _seed_motore(app)
    bozza = _seed_bozza(app)
    query = {"aggiornamenti-staging-scheda": f"?id={semi['raw']['id']}", "copertura-ai-revisione": f"?draft={bozza}"}
    for chiave in [*set(PAGINE.values()), "aggiornamenti-staging-scheda"]:
        corpo = _pagina(client, chiave, query.get(chiave, ""))
        assert corpo["title"] and corpo["sections"], chiave
        assert all(s["kind"] in KIND for s in corpo["sections"]), chiave
    menu = {v["key"] for v in _pagina(client, "aggiornamenti-legali")["menu"]}
    assert {"aggiornamenti-legali", "copertura-ai", "copertura-ai-revisione"} <= menu
    assert "aggiornamenti-staging-scheda" not in menu


def test_scheda_acquisizione_e_documento_assente(client, app):
    semi = _seed_motore(app)
    corpo = _pagina(client, "aggiornamenti-staging-scheda", f"?id={semi['raw']['id']}")
    assert corpo["title"] == semi["raw"]["title"]
    fatti = {f["label"]: f["value"] for f in _sezione(corpo, "Analisi e decisione")["items"]}
    assert fatti["Classificazione"] and fatti["Lavorazione"]
    assente = _pagina(client, "aggiornamenti-staging-scheda", "?id=999999")
    assert assente["sections"][0]["title"] == "Documento non trovato"


def test_archivio_con_filtro_delle_schede(client, app):
    _seed_motore(app)
    corpo = _pagina(client, "aggiornamenti-archivio", "?tab=audit")
    assert corpo["filter"]["name"] == "tab" and corpo["filter"]["value"] == "audit"
    assert _sezione(corpo, "Registro delle attività")["rows"]
    assert _pagina(client, "aggiornamenti-archivio", "?tab=sconosciuta")["filter"]["value"] == "normative"


# ------------------------------------------------------------------ azioni del motore


@pytest.mark.parametrize("pagina,azione", [
    ("aggiornamenti-legali", "scan"),
    ("aggiornamenti-legali", "autopublish"),
    ("aggiornamenti-legali", "cleanup"),
    ("aggiornamenti-fonti", "scan"),
    ("aggiornamenti-analisi", "autopublish"),
    ("aggiornamenti-revisione", "autopublish"),
    ("aggiornamenti-archivio", "cleanup"),
])
def test_azioni_del_motore_come_la_rotta_storica(client, monkeypatch, pagina, azione):
    import web.services.legal_update_surface as superficie

    chiamate = []
    monkeypatch.setattr(superficie, "run_legal_update_action", lambda action, **kw: chiamate.append((action, kw)) or {"ok": True})
    esito = _azione(client, pagina, azione)
    assert esito["ok"] is True and esito["tone"] == "success"
    assert chiamate == [(azione, {"tenant_slug": ""})]


def test_errore_del_motore_in_rosso(client, monkeypatch):
    import web.services.legal_update_surface as superficie

    def guasto(action, **kw):
        raise RuntimeError("fonte non raggiungibile")

    monkeypatch.setattr(superficie, "run_legal_update_action", guasto)
    esito = _azione(client, "aggiornamenti-legali", "scan")
    assert esito["ok"] is False and esito["tone"] == "danger" and "fonte non raggiungibile" in esito["message"]


# ------------------------------------------------------------------ fonti


def test_fonti_crea_modifica_acquisisci_e_agente(client, app, monkeypatch):
    from pct.legal_update_pipeline import LegalUpdatePipeline

    creata = _azione(client, "aggiornamenti-fonti", "crea", values={
        "name": "Fonte di prova", "code": "fonte_prova", "base_url": "https://example.gov.it", "category": "prassi",
        "parser_type": "html", "trust_class": "B", "polling_minutes": "720", "source_type": "web", "notes": "", "is_official": True, "enabled": True,
    })
    assert creata == {**creata, "ok": True, "message": "Fonte salvata correttamente."}
    with app.app_context():
        from web.services.legal_update_surface import build_legal_update_pipeline_runtime

        fonte = build_legal_update_pipeline_runtime(tenant_slug="").repository.get_source_by_code("fonte_prova")
    assert fonte and fonte["enabled"]

    modificata = _azione(client, "aggiornamenti-fonti", "modifica", params={"source_id": fonte["id"], "code": "fonte_prova"}, values={"name": "Fonte rinominata", "enabled": False, "is_official": True})
    assert modificata["ok"] is True and modificata["message"] == "Fonte aggiornata."
    with app.app_context():
        aggiornata = build_legal_update_pipeline_runtime(tenant_slug="").repository.get_source_by_code("fonte_prova")
    assert aggiornata["name"] == "Fonte rinominata" and not aggiornata["enabled"]
    assert _azione(client, "aggiornamenti-fonti", "modifica", params={"source_id": 999999, "code": "x"})["message"] == "Fonte non trovata."

    acquisizioni = []
    monkeypatch.setattr(LegalUpdatePipeline, "fetch_source_by_id", lambda self, source_id, **kw: acquisizioni.append((source_id, kw)) or {"documents_found": 3, "processed": 2})
    esito = _azione(client, "aggiornamenti-fonti", "acquisisci", params={"source_id": fonte["id"]})
    assert acquisizioni == [(fonte["id"], {"auto_publish": True})]
    assert esito["message"] == "Acquisizione completata: 3 documenti trovati e 2 processati."

    import web.services.scheduler_admin_surface as pianificazioni

    richieste = []
    monkeypatch.setattr(pianificazioni, "request_scheduler_run", lambda job_id, **kw: richieste.append((job_id, kw)) or {})
    assert _azione(client, "aggiornamenti-fonti", "esegui-agente", params={"job_id": "legal_source_fonte_prova"})["ok"] is True
    assert richieste == [("legal_source_fonte_prova", {"username": "superadmin-operativo"})]


# ------------------------------------------------------------------ acquisizione e catalogazione


def test_filtri_riaprono_la_pagina_con_la_query(client):
    esito = _azione(client, "aggiornamenti-staging", "filtra", values={"source": "gazzetta_ufficiale", "classification": "", "status": "pending"})
    assert esito["navigate"] == "/admin/aggiornamenti-legali/staging?source=gazzetta_ufficiale&status=pending"
    esito = _azione(client, "aggiornamenti-analisi", "filtra", values={"classification": "PRASSI", "materia": "lavoro"})
    assert esito["navigate"] == "/admin/aggiornamenti-legali/analisi?classification=PRASSI&materia=lavoro"
    assert _azione(client, "aggiornamenti-staging", "filtra", values={})["navigate"] == "/admin/aggiornamenti-legali/staging"


@pytest.mark.parametrize("pagina", ["aggiornamenti-staging", "aggiornamenti-staging-scheda"])
def test_rianalisi_con_pubblicazione_automatica(client, monkeypatch, pagina):
    from pct.legal_update_pipeline import LegalUpdatePipeline

    chiamate = []
    monkeypatch.setattr(LegalUpdatePipeline, "analyze_raw_document", lambda self, raw_id, **kw: chiamate.append((raw_id, kw)) or {"autopublished": {"count": 1}})
    esito = _azione(client, pagina, "analizza", params={"id": "12"})
    assert chiamate == [(12, {"auto_publish": True})]
    assert esito["message"] == "Documento analizzato e pubblicato automaticamente negli archivi operativi."
    assert _azione(client, pagina, "analizza", params={"id": "abc"})["ok"] is False


# ------------------------------------------------------------------ coda revisioni


def test_revisioni_con_il_revisore_collegato(client, monkeypatch):
    from pct.legal_update_pipeline import LegalUpdatePipeline

    chiamate = []
    for nome in ("approve_review", "edit_and_approve_review", "reject_review", "publish_review"):
        monkeypatch.setattr(LegalUpdatePipeline, nome, lambda self, review_id, _n=nome, **kw: chiamate.append((_n, review_id, kw)) or {})
    pagina = "aggiornamenti-revisione"
    assert _azione(client, pagina, "approva", {"review_id": 5}, {"review_notes": "ok"})["message"] == "Proposta approvata."
    assert _azione(client, pagina, "modifica-approva", {"review_id": 5}, {"review_notes": "n", "summary_short": "s", "what_changes": "w"})["ok"] is True
    rifiuto = _azione(client, pagina, "rifiuta", {"review_id": 5}, {"review_notes": "fuori tema"})
    assert rifiuto["ok"] is True and rifiuto["tone"] == "warning"
    assert _azione(client, pagina, "pubblica", {"review_id": 5})["message"] == "Contenuto pubblicato correttamente."
    assert chiamate == [
        ("approve_review", 5, {"reviewer": "superadmin-operativo", "notes": "ok"}),
        ("edit_and_approve_review", 5, {"reviewer": "superadmin-operativo", "review_notes": "n", "summary_short": "s", "what_changes": "w"}),
        ("reject_review", 5, {"reviewer": "superadmin-operativo", "notes": "fuori tema"}),
        ("publish_review", 5, {"reviewer": "superadmin-operativo"}),
    ]


def test_coda_revisioni_reale(client, app):
    semi = _seed_motore(app)
    tabella = _sezione(_pagina(client, "aggiornamenti-revisione"), "Proposte in revisione")
    riga = next(r for r in tabella["rows"] if r["cells"]["title"] == semi["review"]["title"])
    assert {a["key"] for a in riga["actions"]} >= {"approva", "rifiuta", "modifica-approva"}
    assert _azione(client, "aggiornamenti-revisione", "approva", {"review_id": semi["review"]["id"]}, {"review_notes": "verificata"})["ok"] is True


# ------------------------------------------------------------------ copertura AI


def test_copertura_azioni_con_limite(client, monkeypatch):
    import web.services.legal_coverage_surface as copertura

    chiamate = []
    risultati = {"audit": {"ok": 1}, "gaps": {}, "drafts": {"draft_total": 0, "skipped_pending_review_total": 2}, "publish": {"published_total": 0}}
    monkeypatch.setattr(copertura, "run_action", lambda action, **kw: chiamate.append((action, kw)) or risultati[action])
    assert _azione(client, "copertura-ai", "audit")["message"] == "Verifica della copertura aggiornata."
    assert _azione(client, "copertura-ai", "gaps")["tone"] == "success"
    assert _azione(client, "copertura-ai", "drafts", values={"limit": "5"})["tone"] == "warning"
    assert _azione(client, "copertura-ai", "publish", values={"limit": ""})["tone"] == "warning"
    assert chiamate == [
        ("audit", {"limit": 20, "tenant_slug": ""}),
        ("gaps", {"limit": 20, "tenant_slug": ""}),
        ("drafts", {"limit": 5, "tenant_slug": ""}),
        ("publish", {"limit": 20, "tenant_slug": ""}),
    ]
    assert _azione(client, "copertura-ai", "drafts", values={"limit": "molti"})["ok"] is False


def test_revisione_bozza_salva_approva_rifiuta_pubblica(client, app, monkeypatch):
    import pct.legal_coverage_pipeline as pipeline_copertura

    bozza = _seed_bozza(app)
    corpo = _pagina(client, "copertura-ai-revisione", f"?draft={bozza}")
    modulo = _sezione(corpo, "Specifica JSON")
    assert modulo["kind"] == "form" and modulo["action"]["params"] == {"draft": str(bozza)}
    assert json.loads(next(c for c in modulo["fields"] if c["name"] == "spec_json")["value"])["procedure"]["code"] == "SFRATTO_MOROSITA"
    riga = _sezione(corpo, "Coda delle bozze")["rows"][0]
    assert riga["href"] == f"/admin/copertura-ai/review?draft={bozza}"
    assert _azione(client, "copertura-ai-revisione", "apri", {"draft": bozza})["navigate"] == f"/admin/copertura-ai/review?draft={bozza}"

    pagina = "copertura-ai-revisione"
    assert _azione(client, pagina, "salva", {"draft": bozza}, {"spec_json": "{non json"})["ok"] is False
    assert _azione(client, pagina, "salva", {"draft": bozza}, {"spec_json": "[1, 2]"})["ok"] is False
    salvata = _azione(client, pagina, "salva", {"draft": bozza}, {"spec_json": json.dumps({**SPEC, "phase_map": []}), "review_signature": "Avv. Rossi"})
    assert salvata["ok"] is True and salvata["sections"]
    sql = _sezione(_pagina(client, pagina, f"?draft={bozza}"), "Anteprima SQL")
    assert sql["tone"] == "info" and any("SFRATTO_MOROSITA" in voce for voce in sql["items"])

    assert _azione(client, pagina, "approva", {"draft": bozza}, {"review_signature": "Avv. Rossi"})["message"].startswith("Inserisci il motivo")
    assert _azione(client, pagina, "approva", {"draft": bozza}, {"review_reason": "Corretta"})["message"].startswith("Inserisci la firma")
    assert _azione(client, pagina, "approva", {"draft": bozza}, {"review_reason": "Corretta", "review_signature": "Avv. Rossi"})["ok"] is True
    with app.app_context():
        from web.services.legal_coverage_surface import build_repository

        approvata = build_repository(tenant_slug="").get_draft(bozza)
    assert approvata["status"] == "approved" and approvata["reviewer"] == "review-ui" and approvata["review_signature"] == "Avv. Rossi"

    pubblicazioni = []
    monkeypatch.setattr(pipeline_copertura, "publish_single_draft", lambda repo, draft_id, **kw: pubblicazioni.append((draft_id, kw)) or {"published_total": 1})
    assert _azione(client, pagina, "pubblica", {"draft": bozza}, {})["message"].startswith("Inserisci la firma")
    assert _azione(client, pagina, "pubblica", {"draft": bozza}, {"review_signature": "Avv. Rossi"})["ok"] is True
    assert pubblicazioni == [(bozza, {"apply_to_db": True})]

    rifiuto = _azione(client, pagina, "rifiuta", {"draft": bozza}, {"review_reason": "Dati mancanti", "review_signature": "Avv. Rossi"})
    assert rifiuto["ok"] is True and rifiuto["tone"] == "warning"


def test_bozza_con_specifica_senza_sql_resta_correggibile(client, app):
    """La rotta JSON storica falliva per intero: qui la scheda si apre e l'errore resta nell'anteprima."""
    bozza = _seed_bozza(app, {"procedure": {"code": "SENZA_PROFILO"}})
    corpo = _pagina(client, "copertura-ai-revisione", f"?draft={bozza}")
    assert _sezione(corpo, "Specifica JSON")["kind"] == "form"
    assert _sezione(corpo, "Anteprima SQL")["tone"] == "danger"


def test_revisione_filtrata_e_archivio_vuoto(client, app):
    _seed_bozza(app)
    corpo = _pagina(client, "copertura-ai-revisione", "?q=inesistente")
    tabella = _sezione(corpo, "Coda delle bozze")
    assert not tabella["rows"] and tabella["empty"] == "Nessuna bozza corrisponde al filtro inserito."
    assert _pagina(client, "copertura-ai-revisione", "?q=locazioni")["sections"][1]["rows"]


# ------------------------------------------------------------------ etichette


def test_etichette_come_i_filtri_jinja_storici():
    from web.blueprints import legal_updates_admin as storico
    from web.services import react_piattaforma_aggiornamenti_comune as comune

    def normalizza(testo: str) -> str:
        return testo.replace("Gia'", "Già")

    for codice in [*storico.ACTION_LABELS, "", "altro_valore"]:
        assert comune.etichetta_azione(codice) == normalizza(storico.legal_update_action_label(codice))
    for codice in [*storico.CLASSIFICATION_LABELS, "", "nuova_classe"]:
        assert comune.etichetta_classificazione(codice) == storico.legal_update_classification_label(codice)
    for codice in [*storico.STATUS_LABELS, "", "sospesa"]:
        assert comune.etichetta_stato(codice) == storico.legal_update_status_label(codice)
    righe = [{}, {"analysis_id": 1}]
    for stato in ("published", "closed", "approved", "rejected", "pending", ""):
        for proposta in ("DUPLICATE", "OUT_OF_SCOPE", "NEEDS_REVIEW", "NEW_NORMATIVE"):
            righe.append({"analysis_id": 1, "review_status": stato, "proposed_action": proposta})
    for riga in righe:
        assert comune.etichetta_lavorazione(riga) == normalizza(storico.legal_update_staging_status_label(riga))
        assert comune.classe_lavorazione(riga) == storico.legal_update_staging_status_class(riga)
    assert comune.accenti("Prassi e autorita'") == "Prassi e autorità"
    assert comune.accenti("perche' e' gia' un po' dell'atto") == "perché è già un po' dell'atto"
    assert comune.lessico("Fonti RAG-only e in osservazione, modalità guarded") == "Fonti solo ricerca (RAG) e in osservazione, pubblicazione presidiata"
