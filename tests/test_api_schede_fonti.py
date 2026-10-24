"""API e pagina «Norme dei modelli d'atto»: riepilogo, norme di un modello, approvazione, decisione sulle proposte."""
from __future__ import annotations

import json

from lex.normativa.consultazione import importa_fonti
from pct.auth import RuoloUtente
from pct.schede_fonti.proposte import registra_esiti
from pct.schede_fonti.repository import RepositorySchedeFonti
from pct.schede_fonti.verifica import verifica_schede
from tests.test_revisione_2410_sicurezza import _app, _create_user
from tests.test_topbar_operational_api import _login

URN = "urn:nir:stato:regio.decreto:1940-10-28;1443"


def _biblioteca(tmp_path):
    cartella = tmp_path / "pacchetto" / "atti"
    cartella.mkdir(parents=True)
    righe = [{"chiave": "codice_procedura_civile", "atto": "c.p.c.", "articolo": a, "rubrica": "", "testo": f"Art. {a}. Testo vigente {a}.",
              "titolo_atto": "Codice di procedura civile", "data_atto": "1940-10-28", "urn": URN, "vigenza": "VIGENTE",
              "url": "https://www.normattiva.it/uri-res/N2Ls?" + URN, "raccolto_il": "2026-10-01"} for a in ("196", "192", "51", "125")]
    (cartella / "cpc.jsonl").write_text("\n".join(json.dumps(r) for r in righe) + "\n", encoding="utf-8")
    db = tmp_path / "normativa" / "codici_leggi.sqlite"
    importa_fonti(cartella.parent, db, "2026-10-01")
    registra_esiti(RepositorySchedeFonti(db.with_name("schede_fonti.sqlite")), verifica_schede(db, solo_scheda="CIV_ORD_023"))
    db.with_name("schede_fonti_rapporto.json").write_text(json.dumps({"eseguito_il": "2026-10-24T23:10:00", "verifica": {"norme": 5, "stati": {"presente": 4, "articolo_assente": 1}}}), encoding="utf-8")
    return db


def test_pagina_nella_shell_react():
    from web.blueprints import react_shell
    from web.bootstrap.react_route_gate import _excluded, _is_react_route

    assert _is_react_route("/ricerca-legale/schede-atti") and not _excluded("/ricerca-legale/schede-atti")
    assert react_shell._route_component_key("/ricerca-legale/schede-atti") == "src/components/SchedeFontiPage.tsx"


def test_riepilogo_norme_approvazione_e_decisione(tmp_path):
    db = _biblioteca(tmp_path)
    app = _app(tmp_path, NORMATTIVA_DB=str(db.with_name("normattiva.sqlite")))
    with app.test_client() as client:
        assert client.get("/api/v1/ui/schede-fonti").status_code == 401
        _login(client)
        dati = client.get("/api/v1/ui/schede-fonti").get_json()
        assert dati["ok"] and dati["riepilogo"]["norme"] == 5 and dati["puo_decidere"] is True
        assenti = [p for p in dati["proposte"] if p["tipo"] == "norma_assente"]
        assert assenti and assenti[0]["scheda"] == "CIV_ORD_023" and assenti[0]["titolo_scheda"]
        scheda = client.get("/api/v1/ui/schede-fonti/schede/CIV_ORD_023").get_json()["scheda"]
        assert {n["articolo"] for n in scheda["norme"] if n["stato"] == "presente"} == {"196", "192", "51", "125"}
        assert not any(n["approvata"] for n in scheda["norme"])
        assert client.get("/api/v1/ui/schede-fonti/schede/NON_ESISTE").status_code == 404
        assert client.post("/api/v1/ui/schede-fonti/schede/CIV_ORD_023/approva", json={}).status_code == 409
        r = client.post("/api/v1/ui/schede-fonti/schede/CIV_ORD_023/approva", json={"impronta": scheda["impronta"]}).get_json()
        assert r["ok"] and r["approvate"] == 4
        scheda = client.get("/api/v1/ui/schede-fonti/schede/CIV_ORD_023").get_json()["scheda"]
        assert all(n["approvata"] for n in scheda["norme"] if n["stato"] == "presente")
        pid = assenti[0]["id"]
        assert client.post(f"/api/v1/ui/schede-fonti/proposte/{pid}/decisione", json={"esito": "forse"}).status_code == 400
        assert client.post(f"/api/v1/ui/schede-fonti/proposte/{pid}/decisione", json={"esito": "respinta", "nota": "riferimento corretto", "impronta": assenti[0]["impronta"]}).get_json()["ok"]
        respinte = client.get("/api/v1/ui/schede-fonti?stato=respinta").get_json()["proposte"]
        assert respinte[0]["id"] == pid and respinte[0]["nota"] == "riferimento corretto" and respinte[0]["decisa_da"]


def test_decisione_riservata_a_chi_configura_lo_studio(tmp_path):
    db = _biblioteca(tmp_path)
    app = _app(tmp_path, NORMATTIVA_DB=str(db.with_name("normattiva.sqlite")))
    _create_user(app, "praticante", "Praticante123!", ruolo=RuoloUtente.SEGRETERIA)
    with app.test_client() as client:
        _login(client, "praticante", "Praticante123!")
        risposta = client.post("/api/v1/ui/schede-fonti/schede/CIV_ORD_023/approva", json={})
        assert risposta.status_code == 403


def test_decisioni_e_approvazioni_non_passano_ad_altro_studio(tmp_path):
    db = _biblioteca(tmp_path / "pubblico")
    app_a = _app(tmp_path / "studio_a", NORMATTIVA_DB=str(db.with_name("normattiva.sqlite")))
    app_b = _app(tmp_path / "studio_b", NORMATTIVA_DB=str(db.with_name("normattiva.sqlite")))
    with app_a.test_client() as a:
        b = app_b.test_client()
        _login(a); _login(b)
        s = a.get("/api/v1/ui/schede-fonti/schede/CIV_ORD_023").get_json()["scheda"]
        assert a.post("/api/v1/ui/schede-fonti/schede/CIV_ORD_023/approva", json={"impronta": s["impronta"]}).status_code == 200
        assert not any(n["approvata"] for n in b.get("/api/v1/ui/schede-fonti/schede/CIV_ORD_023").get_json()["scheda"]["norme"])
        p = a.get("/api/v1/ui/schede-fonti").get_json()["proposte"][0]
        r = a.post(f"/api/v1/ui/schede-fonti/proposte/{p['id']}/decisione", json={"esito": "respinta", "nota": "riservata allo studio A", "impronta": p["impronta"]})
        assert r.status_code == 200
        assert b.get("/api/v1/ui/schede-fonti?stato=respinta").get_json()["proposte"] == []
        assert "riservata allo studio A" not in b.get("/api/v1/ui/schede-fonti").get_data(as_text=True)
    repo = RepositorySchedeFonti(db.with_name("schede_fonti.sqlite"))
    assert not any(n["sha256_approvato"] for n in repo.norme_scheda("CIV_ORD_023"))
    assert all(p["stato"] == "aperta" for p in repo.proposte())


def test_approvazione_rifiutata_se_la_versione_cambia_dopo_la_lettura(tmp_path):
    import sqlite3
    db = _biblioteca(tmp_path)
    app = _app(tmp_path, NORMATTIVA_DB=str(db.with_name("normattiva.sqlite")))
    with app.test_client() as c:
        _login(c)
        vista = c.get("/api/v1/ui/schede-fonti/schede/CIV_ORD_023").get_json()["scheda"]
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE normative_documents SET redazione_id='2026-10-25'")
        nuova = c.get("/api/v1/ui/schede-fonti/schede/CIV_ORD_023").get_json()["scheda"]
        assert [n["testo"] for n in nuova["norme"]] == [n["testo"] for n in vista["norme"]]
        assert nuova["impronta"] != vista["impronta"]
        assert c.post("/api/v1/ui/schede-fonti/schede/CIV_ORD_023/approva", json={"impronta": vista["impronta"]}).status_code == 409
        assert not any(n["approvata"] for n in c.get("/api/v1/ui/schede-fonti/schede/CIV_ORD_023").get_json()["scheda"]["norme"])


def test_lettura_non_crea_registro_pubblico_e_decisione_non_ripetibile(tmp_path):
    db = _biblioteca(tmp_path)
    app = _app(tmp_path, NORMATTIVA_DB=str(db.with_name("normattiva.sqlite")))
    with app.test_client() as c:
        _login(c)
        dati = c.get("/api/v1/ui/schede-fonti").get_json()
        assert dati["modelli"] and dati["paginazione"]["pagine"] >= 1
        p = dati["proposte"][0]
        url = f"/api/v1/ui/schede-fonti/proposte/{p['id']}/decisione"
        assert c.post(url, json={"esito": "respinta"}).status_code == 409
        payload = {"esito": "respinta", "impronta": p["impronta"]}
        assert c.post(url, json=payload).status_code == 200
        assert "già registrata" in c.post(url, json=payload).get_json()["message"]
        assert c.post(url, json={**payload, "esito": "approvata"}).status_code == 409
        assert c.get("/api/v1/ui/schede-fonti/schede/..invalid").status_code == 404


def test_primo_controllo_assente_non_crea_file_in_get(tmp_path):
    db = _biblioteca(tmp_path)
    path = db.with_name("schede_fonti.sqlite")
    path.unlink()
    db.with_name("schede_fonti_rapporto.json").unlink()
    app = _app(tmp_path, NORMATTIVA_DB=str(db.with_name("normattiva.sqlite")))
    with app.test_client() as c:
        _login(c)
        r = c.get("/api/v1/ui/schede-fonti")
        assert r.status_code == 200 and r.get_json()["riepilogo"]["eseguito_il"] == ""
        assert r.get_json()["modelli"]
    assert not path.exists()


def test_paginazione_non_tronca_proposte_e_catalogo_completo(tmp_path):
    db = _biblioteca(tmp_path)
    repo = RepositorySchedeFonti(db.with_name("schede_fonti.sqlite"))
    for i in range(75):
        repo.apri_proposta("CIV_ORD_023", "c.p.c.", str(10000+i), tipo="fonte_suggerita", motivo="Fonte da esaminare")
    app = _app(tmp_path, NORMATTIVA_DB=str(db.with_name("normattiva.sqlite")))
    with app.test_client() as c:
        _login(c)
        a = c.get("/api/v1/ui/schede-fonti?tipo=fonte_suggerita").get_json()
        b = c.get("/api/v1/ui/schede-fonti?tipo=fonte_suggerita&pagina=2").get_json()
        assert a["paginazione"]["totale"] == 75
        assert len(a["proposte"]) == 50 and len(b["proposte"]) == 25
        assert not ({p["id"] for p in a["proposte"]} & {p["id"] for p in b["proposte"]})
        assert len(a["modelli"]) >= 190
        assert len(a["riepilogo"]["per_tipo"]) == 4


def test_fonte_cambiata_dopo_approvazione_richiede_nuova_verifica(tmp_path):
    import sqlite3
    db = _biblioteca(tmp_path)
    app = _app(tmp_path, NORMATTIVA_DB=str(db.with_name("normattiva.sqlite")))
    with app.test_client() as c:
        _login(c)
        url = "/api/v1/ui/schede-fonti/schede/CIV_ORD_023"
        prima = c.get(url).get_json()["scheda"]
        assert c.post(url+"/approva", json={"impronta": prima["impronta"]}).status_code == 200
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE normative_documents SET redazione_id='2026-10-26'")
        dopo = c.get(url).get_json()["scheda"]
        presenti = [n for n in dopo["norme"] if n["stato"] == "presente"]
        assert presenti and all(not n["approvata"] and "Testo identico" in n["differenze"] for n in presenti)
        registra_esiti(RepositorySchedeFonti(db.with_name("schede_fonti.sqlite")), verifica_schede(db, solo_scheda="CIV_ORD_023"))
        assert any(p["tipo"] == "norma_cambiata" for p in c.get("/api/v1/ui/schede-fonti").get_json()["proposte"])
        assert c.post(url+"/approva", json={"impronta": dopo["impronta"]}).status_code == 200
        assert not any(p["tipo"] == "norma_cambiata" for p in c.get("/api/v1/ui/schede-fonti").get_json()["proposte"])
