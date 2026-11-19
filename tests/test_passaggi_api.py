"""API dei passaggi e delle regole dello studio: autenticazione, permessi, isolamento fra studi, ciclo completo.

I dati del fascicolo arrivano da una fixture (``dati_del_fascicolo`` sostituito):
nessun dato di clienti. Il tenant è quello della richiesta, simulato sostituendo
``tenant_corrente`` del runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app

HEADERS = {"X-API-Key": "passaggi-test-key"}
FASCICOLI = {
    "F1": {"id": "F1", "tribunale": "Tribunale di Milano", "giudice": "dott.ssa Bianchi", "area_pratica": "civile"},
    "F2": {"id": "F2", "tribunale": "Tribunale di Milano", "giudice": "dott.ssa Bianchi", "area_pratica": "civile"},
}


def _dati(fascicolo_id: str):
    fascicolo = FASCICOLI.get(fascicolo_id)
    if fascicolo is None:
        return None
    scadenza = {"id": f"S-{fascicolo_id}", "stato": "BOZZA", "data": "2027-01-12", "deadline_profile_code": "NOTE_127_TER",
                "titolo": "Deposito note scritte ex art. 127-ter c.p.c.", "operational_due_at": "2027-01-12T09:30:00"}
    return {"fascicolo": fascicolo, "scadenze": [scadenza], "termini_pec": []}


@pytest.fixture()
def app(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["REGOLE_STUDIO_DB"] = str(tmp_path / "intelligence" / "regole_studio.db")
    applicazione = create_app(cfg)
    applicazione.config["API_KEY"] = HEADERS["X-API-Key"]
    applicazione.config["REGOLE_STUDIO_DB"] = cfg["REGOLE_STUDIO_DB"]
    import web.services.passaggi_runtime as runtime

    monkeypatch.setattr(runtime, "dati_del_fascicolo", _dati)
    monkeypatch.setattr(runtime, "percorso_regole", lambda paths=None: cfg["REGOLE_STUDIO_DB"])
    studio = {"tenant": "studio-a"}
    monkeypatch.setattr(runtime, "tenant_corrente", lambda: studio["tenant"])
    applicazione.studio_di_prova = studio
    return applicazione


def _termine(passaggi: list[dict]) -> dict:
    return next(voce for voce in passaggi if voce["regola"]["id"] == "127ter.termine_note")


def test_senza_autenticazione_401(app):
    with app.test_client() as client:
        assert client.get("/api/v1/ui/fascicoli/F1/passaggi").status_code == 401
        assert client.post("/api/v1/ui/fascicoli/F1/passaggi/correzioni", json={}).status_code == 401
        assert client.get("/api/v1/ui/regole-studio").status_code == 401
        assert client.post("/api/v1/ui/regole-studio/x", json={"attiva": False}).status_code == 401


def test_utente_senza_permesso_di_scrittura_403(app):
    from web.blueprints.api_v1_passaggi import fascicolo_passaggi_correzione, regole_studio_aggiorna

    class SoloLettura:
        id = "u9"
        nome_completo = "Solo Lettura"

        def ha_permesso(self, permesso):
            return permesso == "fascicoli.leggi"

    with app.test_request_context("/api/v1/ui/fascicoli/F1/passaggi/correzioni", method="POST", json={}):
        from flask import g

        g.utente_corrente = SoloLettura()
        risposta, stato = fascicolo_passaggi_correzione("F1")
        assert stato == 403 and risposta.get_json()["code"] == "forbidden"
        _risposta, stato = regole_studio_aggiorna("x")
        assert stato == 403


def test_sessione_reale_legge_i_passaggi(app):
    _crea_operatore(app)
    with app.test_client() as client:
        _login(client)
        risposta = client.get("/api/v1/ui/fascicoli/F1/passaggi")
        assert risposta.status_code == 200 and risposta.get_json()["ok"]
        assert client.get("/api/v1/ui/fascicoli/ignoto/passaggi").status_code == 404


def test_ciclo_correzione_caso_successivo_modifica_e_disattivazione(app):
    with app.test_client() as client:
        passaggi = client.get("/api/v1/ui/fascicoli/F1/passaggi", headers=HEADERS).get_json()["passaggi"]
        termine = _termine(passaggi)
        assert termine["campi"]["ora"]["valore"] == "09:30" and termine["norme"][0]["id"] == "cpc_127ter"
        creata = client.post("/api/v1/ui/fascicoli/F1/passaggi/correzioni", headers=HEADERS, json={
            "chiave": termine["chiave"], "azione": "modifica_valore", "campo": "ora", "valore": "12:00", "ambito": "giudice",
            "motivo": "Prassi del giudice", "ufficio": "Altro ufficio iniettato"}).get_json()
        assert creata["ok"] and creata["regola"]["ufficio"] == "Tribunale di Milano"
        successivo = _termine(client.get("/api/v1/ui/fascicoli/F2/passaggi", headers=HEADERS).get_json()["passaggi"])
        assert successivo["campi"]["ora"] == {**successivo["campi"]["ora"], "valore": "12:00", "valoreSoftware": "09:30"}
        assert successivo["regoleStudioApplicate"][0]["etichetta"].startswith("regola dello studio del ")
        regola_id = creata["regola"]["id"]
        elenco = client.get("/api/v1/ui/regole-studio", headers=HEADERS).get_json()["regole"]
        assert [voce["id"] for voce in elenco] == [regola_id] and elenco[0]["applicazioni"] >= 1
        assert client.post(f"/api/v1/ui/regole-studio/{regola_id}", headers=HEADERS, json={"valore": "11:00"}).get_json()["regola"]["valore"] == "11:00"
        assert client.post(f"/api/v1/ui/regole-studio/{regola_id}", headers=HEADERS, json={"attiva": False}).get_json()["ok"]
        tornato = _termine(client.get("/api/v1/ui/fascicoli/F2/passaggi", headers=HEADERS).get_json()["passaggi"])
        assert tornato["campi"]["ora"]["valore"] == "09:30" and tornato["regoleStudioApplicate"] == []
        diario = client.get(f"/api/v1/ui/regole-studio/{regola_id}/diario", headers=HEADERS).get_json()
        assert [evento["evento"] for evento in diario["eventi"]] == ["creata", "modificata", "disattivata"]
        assert diario["applicazioni"][0]["fascicolo_id"] in {"F1", "F2"}


def test_vincolo_di_legge_rifiuta_la_correzione_e_resta_nel_diario(app):
    with app.test_client() as client:
        termine = _termine(client.get("/api/v1/ui/fascicoli/F1/passaggi", headers=HEADERS).get_json()["passaggi"])
        esito = client.post("/api/v1/ui/fascicoli/F1/passaggi/correzioni", headers=HEADERS,
                            json={"chiave": termine["chiave"], "azione": "non_proporre", "ambito": "tipo"}).get_json()
        assert not esito["ok"] and esito["rifiutata"] and "art. 153" in esito["errore"]
        assert esito["rifiuto"]["norme"][0]["id"] == "cpc_153"
        assert client.get("/api/v1/ui/regole-studio", headers=HEADERS).get_json()["regole"] == []
    from web.services.passaggi_runtime import RegoleStudioRepository

    eventi = RegoleStudioRepository(app.config["REGOLE_STUDIO_DB"], tenant_id="studio-a").eventi()
    assert [evento["evento"] for evento in eventi] == ["rifiutata"]


def test_le_regole_di_uno_studio_non_valgono_per_un_altro(app):
    with app.test_client() as client:
        termine = _termine(client.get("/api/v1/ui/fascicoli/F1/passaggi", headers=HEADERS).get_json()["passaggi"])
        regola = client.post("/api/v1/ui/fascicoli/F1/passaggi/correzioni", headers=HEADERS, json={
            "chiave": termine["chiave"], "azione": "chiedi_sempre", "ambito": "tipo"}).get_json()["regola"]
        app.studio_di_prova["tenant"] = "studio-b"
        assert client.get("/api/v1/ui/regole-studio", headers=HEADERS).get_json()["regole"] == []
        altro = _termine(client.get("/api/v1/ui/fascicoli/F2/passaggi", headers=HEADERS).get_json()["passaggi"])
        assert altro["stato"] == "da_confermare" and altro["regoleStudioApplicate"] == []
        esito = client.post(f"/api/v1/ui/regole-studio/{regola['id']}", headers=HEADERS, json={"attiva": False}).get_json()
        assert not esito["ok"]
        assert client.get(f"/api/v1/ui/regole-studio/{regola['id']}/diario", headers=HEADERS).status_code == 404
        app.studio_di_prova["tenant"] = "studio-a"
        assert client.get("/api/v1/ui/regole-studio", headers=HEADERS).get_json()["regole"][0]["attiva"]


def test_worker_attende_la_lettura_prima_di_pubblicare_i_passaggi(app, monkeypatch):
    from web.services import pannelli_pronti_runtime, passaggi_runtime

    dati = {**_dati("F1"), "conclusioni": None}
    monkeypatch.setattr(passaggi_runtime, "dati_del_fascicolo", lambda _id: dati)
    monkeypatch.setattr(pannelli_pronti_runtime, "calcolo_in_corso", lambda: True)
    with app.test_client() as client:
        url = "/api/v1/ui/fascicoli/F1/passaggi"
        attesa = client.get(url, headers=HEADERS)
        assert attesa.status_code == 202
        assert attesa.headers["X-Iusentra-Pannello"] == "in-preparazione"
        dati["conclusioni"] = []
        risposta = client.get(url, headers=HEADERS)
        assert risposta.status_code == 200
        assert risposta.get_json()["lettura_in_preparazione"] is False


def test_note_preparate_dalla_stessa_fonte_con_le_due_date(app, monkeypatch):
    from datetime import date
    from types import SimpleNamespace
    from web.services import archivio_letture_runtime
    from web.services import passaggi_runtime

    monkeypatch.setattr(passaggi_runtime, "oggi_roma", lambda: date(2026, 11, 15))
    dati = _dati("F1")
    dati["fascicolo"]["sezione"] = "Lavoro"
    dati["fascicolo_originale"] = SimpleNamespace(id="F1")
    monkeypatch.setattr(archivio_letture_runtime, "testi_indice_archivio", lambda _fascicolo, documento_ids: {
        "D1": "TRIBUNALE ORDINARIO DI VICENZA SEZIONE PRIMA DECRETO FISSAZIONE",
    } if documento_ids == {"D1"} else {})
    nota = {
        "codice": "note_127ter", "stato": "da_fare", "onerato_codice": "tutte_le_parti",
        "termine": {"scadenza_iso": "2027-01-12"},
        "letto": {"tipo": "documento", "documento_id": "D1", "documento": "Decreto.pdf"},
    }
    dati["conclusioni"] = [nota]
    dati["lettura"] = {
        "intestazione": {"rg": "632/2026"},
        "ragionamento": {
            "impronta": "lettura-preparata",
            "conclusioni": dati["conclusioni"],
            "udienze": [
                {"documento_id": "D1", "data": "18/01/2027",
                 "modalita": "sostituita da note scritte (art. 127-ter c.p.c.)"},
                {"documento_id": "D2", "data": "21/01/2027",
                 "modalita": "sostituita da note scritte (art. 127-ter c.p.c.)"},
            ],
        },
    }
    monkeypatch.setattr(passaggi_runtime, "dati_del_fascicolo", lambda _id: dati)
    with app.test_client() as client:
        payload = client.get("/api/v1/ui/fascicoli/F1/passaggi", headers=HEADERS).get_json()
        (bozza,) = payload["bozzeNote"].values()
        assert bozza["documento_id"] == "D1"
        assert "18/01/2027" in bozza["testo"] and "12/01/2027" in bozza["testo"]
        assert "21/01/2027" not in bozza["testo"]
        assert "R.G. 632/2026" in bozza["testo"]
        assert "## Sezione Prima" in bozza["testo"]
        assert bozza["sezione_provvedimento"] == "Sezione Prima"
        assert "istanze e conclusioni" in bozza["campi_da_completare"]
        assert "data dell’atto" in bozza["campi_da_completare"]
        nota["dubbi"] = [{"codice": "note_in_attesa_cancelleria"}]
        payload = client.get("/api/v1/ui/fascicoli/F1/passaggi", headers=HEADERS).get_json()
        assert payload["bozzeNote"] == {}


def test_sezione_della_bozza_richiede_l_intestazione_del_provvedimento():
    from pct.note_127_ter.bozza import sezione_del_provvedimento

    assert sezione_del_provvedimento("Corte di appello di Venezia\nSEZIONE III\nORDINANZA") == "Sezione III"
    assert sezione_del_provvedimento("Tribunale di Vicenza DECRETO. Si trasmette alla sezione prima.") == ""
    assert sezione_del_provvedimento("SEZIONE PRIMA DECRETO") == ""


def test_bozza_distingue_l_accettazione_del_ricorso_dalla_copia_nel_fascicolo():
    from web.services.passaggi_runtime import _ricorso_citato_senza_allegato

    ricevuta = {"portale": "PEC_PCT", "stato": "ACCETTATO_CANCELLERIA", "identificativo_busta": "B123",
                "atto": "Ricorso (originale notificato).pdf", "documenti": 0, "data_accettazione": "10/11/2026"}
    lettura = {"depositi": {"perfezionati": [ricevuta]}, "ragionamento": {"atti": []}}
    assert _ricorso_citato_senza_allegato(lettura) == {
        "atto": ricevuta["atto"], "busta": "B123", "data": "10/11/2026",
    }

    altri = [ricevuta, {**ricevuta, "identificativo_busta": "B456"}]
    assert _ricorso_citato_senza_allegato({**lettura, "depositi": {"perfezionati": altri}}) is None
    lettura["ragionamento"]["atti"].append(
        {"appartenenza": "causa", "natura": "atto_principale", "etichetta": "Ricorso in materia di lavoro"}
    )
    assert _ricorso_citato_senza_allegato(lettura) is None


def test_apertura_bozza_riusa_il_documento_editor(app, tmp_path, monkeypatch):
    from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
    from web import helpers
    from web.services import document_crypto, editor_studio_context, riscontri_processuali_runtime

    archivio = GestioneFascicoli(
        db_path=str(tmp_path / "bozze" / "fascicoli.json"),
        documents_dir=str(tmp_path / "bozze" / "documenti"),
    )
    fascicolo = archivio.nuovo(titolo="Note scritte", tipo=TipoFascicolo.CIVILE, giudice="Caterina Neri")
    fonte = archivio.aggiungi_documento(fascicolo.id, "Decreto.pdf", TipoDocumento.DECRETO, b"%PDF-1.4")
    chiave = f"127ter.bozza_note:{fascicolo.id}:S1"
    monkeypatch.setattr(helpers, "get_fascicoli", lambda: archivio)
    monkeypatch.setattr(editor_studio_context, "studio_context_for_editor", lambda: {})
    monkeypatch.setattr(document_crypto, "encrypt_doc", lambda raw: raw)

    def salvata(fascicolo_id, pannello):
        assert (fascicolo_id, pannello) == (fascicolo.id, "passaggi")
        return {"bozzeNote": {chiave: {
            "titolo": "Note per la trattazione scritta", "termine": "2027-01-12",
            "documento_id": fonte.id, "documento": fonte.nome,
            "testo": "## Note per la trattazione scritta\n\n[Istanze e conclusioni]",
            "udienza_sostituita": "18/01/2027", "ora": "14.00",
            "dati_modello": {"rg": "632/2026", "sezione": "Sezione Prima"},
        }}}

    monkeypatch.setattr(riscontri_processuali_runtime, "risultato_materializzato", salvata)
    url = f"/api/v1/ui/fascicoli/{fascicolo.id}/passaggi/bozza-note"
    with app.test_client() as client:
        assert client.post(url, json={"chiave": chiave, "documentoId": fonte.id}).status_code == 401
        prima = client.post(url, headers=HEADERS, json={"chiave": chiave, "documentoId": fonte.id})
        seconda = client.post(url, headers=HEADERS, json={"chiave": chiave, "documentoId": fonte.id})
        assert prima.status_code == 200 and prima.get_json() == seconda.get_json()
        data = prima.get_json()
        assert data["openUrl"] == f"/fascicoli/{fascicolo.id}/documenti/{data['documentId']}/editor"
        doc = next(d for d in archivio.get(fascicolo.id).documenti if d.id == data["documentId"])
        assert doc.fonte_documento == "BOZZA_NOTE_127_TER"
        assert doc.nome.endswith("12-01-2027.docx")
        assert fonte.id in doc.note
        assert len(archivio.get(fascicolo.id).documenti) == 2
        from docx import Document
        from pct.documento_fedele.da_docx import converti_docx
        from lxml import html
        percorso = archivio.percorso_documento(fascicolo.id, doc.id)
        corpo = html.fragment_fromstring(
            converti_docx(percorso).html, create_parent=True,
        )
        titolo_note = next(p for p in Document(percorso).paragraphs if p.text == "Trattazione scritta")
        assert all(str(run.font.color.rgb) == "000000" for run in titolo_note.runs if run.text)
        for key, valore in {
            "fascicolo.giudice": "Caterina Neri",
            "note_127ter.udienza": "18.01.2027",
            "note_127ter.termine": "12/01/2027 entro le ore 14:00",
            "note_127ter.sezione": "Sezione Prima",
        }.items():
            (campo,) = corpo.xpath(".//*[@data-iu-linked-field=$key]", key=key)
            assert campo.text_content() == valore
            assert campo.get("data-iu-linked-matter") == fascicolo.id


def test_note_espone_ora_del_provvedimento_e_stile_nativo(tmp_path):
    from pct.note_127_ter.bozza import testo_note
    from pct.documento_fedele.da_docx import converti_docx
    from pct.editor import html_to_docx
    from pct.editor_linked_fields import template_linked_html
    from lxml import html as parser
    from web.services.passaggi_runtime import _impagina_bozza_note

    proposta = {"termine": "2026-12-22", "ora": "14.00", "udienza_sostituita": "22/12/2026"}
    dati = dict(ufficio="Tribunale di Vicenza", sezione="Lavoro", rg="1851/2026",
                giudice="Caterina Neri", parte="Parte A", controparte="", difensore="",
                difensore_controparte="Avvocatura distrettuale di Venezia")
    testo = testo_note(proposta, **dati)
    assert "22/12/2026 entro le ore 14:00" in testo
    assert "Controparte: Avvocatura" not in testo
    assert "Difesa indicata nel fascicolo: Avvocatura distrettuale di Venezia." in testo
    html = _impagina_bozza_note(testo, proposta={**proposta, "dati_modello": dati}, fascicolo_id="F1", cliente_id="C1")
    assert "data-margine-sinistro" in html and 'data-interlinea="24.0000"' in html
    assert "Times New Roman" in html and "text-align:center;font-size:18pt" in html
    assert "*Giudice:" not in html and "*Udienza del" not in html
    assert "text-align:center;font-style:italic;text-decoration:underline" in html
    corpo = parser.fragment_fromstring(html, create_parent=True)
    termine = corpo.xpath(".//*[@data-iu-linked-field='note_127ter.termine']")[0]
    assert termine.text_content() == "22/12/2026 entro le ore 14:00"
    assert termine.get("data-iu-linked-matter") == "F1"
    assert corpo.xpath(".//a[contains(@href,'127ter')]")
    word = tmp_path / "note-trattazione-scritta.docx"
    word.write_bytes(html_to_docx(html))
    riaperto = converti_docx(word).html
    assert "data-iu-linked-field=\"note_127ter.termine\"" in riaperto and "127ter" in riaperto
    modello, _ = template_linked_html(riaperto)
    for dato in ("22/12/2026", "1851/2026", "Parte A", "Caterina Neri"):
        assert dato not in modello
    altro, mancanti = template_linked_html(modello, matter_id="F2", client_id="C2", context=[
        {"id": "note_127ter.termine", "value": "15/01/2027 entro le ore 12:00", "available": True},
    ])
    assert "15/01/2027 entro le ore 12:00" in altro
    assert "Difensore costituito" in mancanti
