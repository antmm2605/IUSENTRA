"""Lex scrive i blocchi «scrive_lex» della scheda: messaggio, divisione, campi, revisione e API (gateway finto)."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from lex.procedura_atti.fonti_scheda import FontiScheda
from lex.procedura_atti.stesura_blocchi import (
    campi_per_blocchi,
    dividi_blocchi,
    risolvi_citazioni,
    scrivi_blocchi,
    termini_da_scadenze,
)
from pct.schede_compilazione import risolvi_scheda, scheda_per_modello
from tests.test_revisione_2410_sicurezza import _app
from tests.test_topbar_operational_api import _login

FONTI = FontiScheda(scheda="CIV_ORD_001", titolo="Citazione",
                    fonti={1: "Codice civile, art. 1218. Il debitore che non esegue esattamente la prestazione dovuta e' tenuto al risarcimento del danno."},
                    fonti_ref=[{"n": 1, "atto": "c.c.", "articolo": "1218", "url": "https://www.normattiva.it/x"}])
RISPOSTA = """### Fatto
Il sig. Mario Rossi ha consegnato la merce alla Beta s.r.l., che non ha pagato. [DATO MANCANTE: data della consegna]
### Diritto
L'inadempimento obbliga al risarcimento del danno [1].
### Istruttoria
Si producono i documenti indicati.
### Conclusioni
Voglia il Tribunale condannare Beta s.r.l. al pagamento.
"""


def _risolta():
    return risolvi_scheda(scheda_per_modello("CIV_CIT_001"), {"attore": "Mario Rossi", "convenuto": "Beta s.r.l."})


def test_divisione_e_campi():
    nomi = ["Fatto", "Diritto", "Istruttoria", "Conclusioni"]
    blocchi = dividi_blocchi(RISPOSTA, nomi)
    assert list(blocchi) == nomi and "[1]" in blocchi["Diritto"]
    campi = campi_per_blocchi(nomi, ["facts", "legal_arguments", "evidence_means", "requests_or_conclusions"])
    assert campi == {"Fatto": "facts", "Diritto": "legal_arguments", "Istruttoria": "evidence_means",
                     "Conclusioni": "requests_or_conclusions"}
    assert termini_da_scadenze([{"etichetta": "Termine", "valore": "il 12/11/2026"}])[0]["scadenza"] == "12/11/2026"


def test_scrivi_blocchi_usa_dati_fonti_e_rivede():
    visti = {}

    def chiama(sistema, messaggio):
        visti["sistema"], visti["messaggio"] = sistema, messaggio
        return RISPOSTA, "llamacpp:qwen"

    esito = scrivi_blocchi(chiama_modello=chiama, oggetto="recupero del prezzo", risolta=_risolta(), fonti=FONTI,
                           blocco_scadenze="", termini=[], fatti_testo="", oggi=date(2026, 10, 24),
                           assistito="Mario Rossi", controparte="Beta s.r.l.", ruolo_assistito="attore",
                           campi_modello=["facts", "legal_arguments", "evidence_means", "requests_or_conclusions"])
    assert "[1] Codice civile, art. 1218" in visti["messaggio"] and "Mario Rossi" in visti["messaggio"]
    assert "### Conclusioni" in visti["messaggio"] and "SOLO le Fonti" in visti["sistema"]
    assert esito.campi["Diritto"] == "legal_arguments" and esito.modello_ai == "llamacpp:qwen"
    assert esito.revisione["gravi"] == [] and esito.stato_consegna["stato"]


def test_norma_fuori_fonti_e_grave():
    esito = scrivi_blocchi(chiama_modello=lambda s, m: (RISPOSTA.replace("[1]", "ai sensi dell'art. 2043 c.c."), "x"),
                           oggetto="recupero", risolta=_risolta(), fonti=FONTI, blocco_scadenze="", termini=[],
                           fatti_testo="", oggi=date(2026, 10, 24), assistito="Mario Rossi", controparte="Beta s.r.l.",
                           ruolo_assistito="attore", campi_modello=["facts"])
    assert any(g[0] == "norma_fuori_fonti" for g in esito.revisione["gravi"])
    assert esito.stato_consegna["stato"] != "pronta_per_revisione_avvocato"


def test_api_permessi_e_validazione(tmp_path, monkeypatch):
    app = _app(tmp_path)
    with app.test_client() as client:
        assert client.post("/api/v1/ui/redazione-atti/lex/blocchi", json={}).status_code == 401
        _login(client)
        r = client.post("/api/v1/ui/redazione-atti/lex/blocchi", json={"modelCode": "CIV_CIT_001"}).get_json()
        assert r["ok"] is False and "richiesta" in r["errore"]
        r = client.post("/api/v1/ui/redazione-atti/lex/blocchi",
                        json={"modelCode": "CIV_CIT_001", "oggetto": "x", "idFascicolo": "inesistente"}).get_json()
        assert r["ok"] is False and "Fascicolo" in r["errore"]


def test_provider_solo_locale(monkeypatch):
    from web.services.redazione_lex_runtime import provider_locale

    cfg = {"openrouter": SimpleNamespace(is_local=False), "ollama": SimpleNamespace(is_local=True),
           "llamacpp": SimpleNamespace(is_local=True)}
    gw = SimpleNamespace(providers={"openrouter": 1, "ollama": 1, "llamacpp": 1}, config=SimpleNamespace(providers=cfg))
    assert provider_locale(gw) == "llamacpp"
    monkeypatch.setenv("LEX_STESURA_PROVIDER", "ollama")
    assert provider_locale(gw) == "ollama"
    gw = SimpleNamespace(providers={"openrouter": 1}, config=SimpleNamespace(providers=cfg))
    assert provider_locale(gw) == ""


def test_citazioni_risolte_nell_atto():
    ref = [{"n": 1, "articolo": "1218", "sigla": "c.c."}, {"n": 2, "articolo": "163", "sigla": "c.p.c."}]
    assert risolvi_citazioni("danno [1] e forme [1, 2]; ignoto [9]", ref) == "danno (art. 1218 c.c.) e forme (art. 1218 c.c.; art. 163 c.p.c.); ignoto [9]"
