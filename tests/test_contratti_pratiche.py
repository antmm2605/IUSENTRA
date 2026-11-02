"""Pratiche contrattuali: archivio, bozza, Word, API e salvataggio nel fascicolo."""
import io
from types import SimpleNamespace

import pytest
from docx import Document
from flask import Flask, g

from pct.contratti.archivio import ArchivioContratti
from pct.contratti.bozza import campi_richiesti, componi
from pct.contratti.catalogo import _indice, clausole_della_famiglia, libreria_clausole
from pct.contratti.esporta_docx import bozza_docx, nota_docx


def test_ogni_famiglia_genera_bozza_senza_errori():
    for cid in _indice():
        bozza = componi(cid, {}, {})
        assert bozza["articoli"] and bozza["comparenti"]
        assert all(k in libreria_clausole()["clausole"] for k in clausole_della_famiglia(_indice()[cid]))


def test_bozza_non_inventa_dati_mancanti_e_compila_quelli_forniti():
    bozza = componi("incarico_avvocato", {"parti": [{"nome": "Alfa S.r.l.", "rappresentante": "Luca Verdi"}],
                                          "campi": {"corrispettivo": "euro 3.000", "foro": "Milano"}}, {})
    testi = " ".join(a["testo"] for a in bozza["articoli"])
    assert "euro 3.000" in testi and "Foro di Milano" in testi
    assert "[DA COMPLETARE: oggetto del contratto]" in testi
    assert "dati dell'avvocato" in bozza["comparenti"][1]["testo"].lower() or "DA COMPLETARE" in bozza["comparenti"][1]["testo"]
    assert not bozza["pronta"]


def test_approvazione_specifica_elenca_solo_clausole_presenti():
    testo = componi("locazione_abitativa", {}, {})["articoli"][-1]["testo"]
    assert "recesso del conduttore" in testo and "limitazione di responsabilità" not in testo


def test_campi_richiesti_per_famiglia():
    ids = [c["id"] for c in campi_richiesti("sviluppo_software")]
    assert {"oggetto", "corrispettivo", "termine_collaudo", "foro"} <= set(ids)


def test_word_bozza_e_nota():
    bozza = componi("locazione_abitativa", {"parti": [{"nome": "Mario Rossi"}]}, {"deposito_mensilita": 4})
    testo = "\n".join(p.text for p in Document(io.BytesIO(bozza_docx(bozza))).paragraphs)
    assert "Art. 1 – Oggetto" in testo and "Mario Rossi" in testo and "1341" in testo
    nota = "\n".join(p.text for p in Document(io.BytesIO(nota_docx(bozza))).paragraphs)
    assert "Deposito cauzionale oltre tre mensilità" in nota


def test_archivio_storico_e_approvazione_vincolata(tmp_path):
    arch = ArchivioContratti(tmp_path / "pratiche.json")
    p = arch.crea("locazione_abitativa", {"titolo": "Loc. Rossi"}, "avv")
    arch.aggiorna(p["id"], {"fatti": {"deposito_mensilita": 4}})
    with pytest.raises(ValueError, match="bloccanti"):
        arch.aggiorna(p["id"], {"stato": "approvato"})
    fatti = {"regime_canone": "libero", "durata_transitoria": False, "conduttore_studente": False, "deposito_mensilita": 2}
    with pytest.raises(ValueError, match="valutazione"):
        arch.aggiorna(p["id"], {"fatti": {**fatti, "parte_consumatore": True}, "stato": "approvato"})
    with pytest.raises(ValueError, match="domande"):
        arch.aggiorna(p["id"], {"fatti": fatti, "stato": "approvato"})
    comuni = {d: False for d in ("parte_consumatore", "parte_estera", "firmatario_rappresentante", "condizioni_generali",
                                 "riguarda_immobili", "dati_personali", "penale_o_caparra", "limitazione_responsabilita",
                                 "clausola_arbitrale", "firma_digitale")}
    completi = {**fatti, **comuni, "comune_accordo_territoriale": True, "cedolare_secca": False}
    with pytest.raises(ValueError, match="elementi evidenziati"):
        arch.aggiorna(p["id"], {"fatti": completi, "stato": "approvato"})
    campi = {k: "x" for k in ("oggetto", "corrispettivo", "durata", "decorrenza", "foro", "luogo", "data",
                              "giorno_pagamento", "parte_spese")}
    dati = {"parti": [{"nome": "Mario Rossi"}, {"nome": "Giulia Bianchi"}], "campi": campi}
    finale = arch.aggiorna(p["id"], {"fatti": completi, "dati": dati, "stato": "approvato"})
    assert finale["stato"] == "approvato" and len(finale["storico"]) >= 2
    with pytest.raises(ValueError):
        arch.aggiorna(p["id"], {"stato": "inventato"})
    assert arch.elenco()[0]["id"] == p["id"]
    arch.elimina(p["id"])
    with pytest.raises(LookupError):
        arch.pratica(p["id"])


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from web.blueprints import api_v1_contratti as modulo
    from web.services import contratti_runtime

    documenti = []

    class Fascicoli:
        def get(self, fid):
            return SimpleNamespace(id=fid) if fid == "F1" else None

        def tutti(self):
            return [SimpleNamespace(id="F1", numero="2026/001", titolo="Rossi c. Bianchi", nome_cliente="Rossi")]

        def cerca(self, testo):
            return self.tutti()

        def aggiungi_documento(self, fid, nome, tipo, contenuto, **kw):
            documenti.append((fid, nome, tipo, len(contenuto)))
            return SimpleNamespace(id="D1")

    arch = ArchivioContratti(tmp_path / "p.json")
    monkeypatch.setattr(contratti_runtime, "archivio", lambda: arch)
    monkeypatch.setattr(contratti_runtime, "_runtime", lambda nome: Fascicoli())
    monkeypatch.setattr(modulo, "_audit_event", lambda *a, **k: None)
    monkeypatch.setattr(modulo, "_session_user_can", lambda perm: True)
    app = Flask("t")
    app.register_blueprint(modulo.api_v1_contratti, url_prefix="/api/v1/ui/contratti")

    @app.before_request
    def _utente():
        g.utente_corrente = SimpleNamespace(username="avv", ha_permesso=lambda p: True)

    c = app.test_client()
    c.documenti = documenti
    return c


def test_api_percorso_completo(client):
    base = "/api/v1/ui/contratti"
    assert client.get(f"{base}/catalogo").get_json()["totale"] >= 190
    det = client.get(f"{base}/famiglie/agenzia").get_json()
    assert det["ruoli"] == ["Preponente", "Agente"] and det["domande_comuni"]
    assert client.get(f"{base}/famiglie/nessuno").status_code == 404
    r = client.post(f"{base}/pratiche", json={"contratto_id": "agenzia", "titolo": "Agenzia Nord", "fascicolo_id": "F1"})
    assert r.status_code == 201
    pid = r.get_json()["pratica"]["id"]
    agg = client.put(f"{base}/pratiche/{pid}", json={"fatti": {"patto_non_concorrenza": True}}).get_json()
    assert any(b["id"] == "ncc_agenzia" for b in agg["valutazione"]["bloccanti"])
    assert client.put(f"{base}/pratiche/{pid}", json={"stato": "approvato", "forza_approvazione": True}).status_code == 400
    docx = client.get(f"{base}/pratiche/{pid}/bozza.docx")
    assert docx.status_code == 200 and docx.data[:2] == b"PK"
    assert client.get(f"{base}/pratiche/{pid}/nota.docx").status_code == 200
    salvato = client.post(f"{base}/pratiche/{pid}/fascicolo").get_json()
    assert salvato["ok"] and client.documenti[0][0] == "F1" and client.documenti[0][2].value == "CONTRATTO"
    assert client.get(f"{base}/pratiche/{pid}").get_json()["pratica"]["documenti"][0]["documento_id"] == "D1"
    assert client.get(f"{base}/fascicoli?q=rossi").get_json()["fascicoli"][0]["numero"] == "2026/001"
    assert client.delete(f"{base}/pratiche/{pid}").get_json()["ok"]
