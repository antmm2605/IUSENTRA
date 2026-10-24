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
        r = client.post("/api/v1/ui/schede-fonti/schede/CIV_ORD_023/approva", json={}).get_json()
        assert r["ok"] and r["approvate"] == 4
        scheda = client.get("/api/v1/ui/schede-fonti/schede/CIV_ORD_023").get_json()["scheda"]
        assert all(n["approvata"] for n in scheda["norme"] if n["stato"] == "presente")
        pid = assenti[0]["id"]
        assert client.post(f"/api/v1/ui/schede-fonti/proposte/{pid}/decisione", json={"esito": "forse"}).status_code == 400
        assert client.post(f"/api/v1/ui/schede-fonti/proposte/{pid}/decisione", json={"esito": "respinta", "nota": "riferimento corretto"}).get_json()["ok"]
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
