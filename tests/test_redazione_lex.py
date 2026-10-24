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


def test_ponte_fonti_usa_solo_approvazioni_sql_del_proprio_studio(tmp_path):
    from lex.procedura_atti.fonti_scheda import fonti_per_scheda
    from pct.storage import StudioDB
    from tests.test_api_schede_fonti import _biblioteca
    from web.services.schede_fonti_runtime import RepositoryFontiStudio, approva, scheda
    db=_biblioteca(tmp_path)
    a=StudioDB(tmp_path/'a.sqlite'); b=StudioDB(tmp_path/'b.sqlite')
    vista=scheda(db,'CIV_ORD_023',studio_db=a)
    approva(db,'CIV_ORD_023','avvocato A',vista['impronta'],studio_db=a)
    fa=fonti_per_scheda('CIV_ORD_023',db,repository=RepositoryFontiStudio(db,a))
    fb=fonti_per_scheda('CIV_ORD_023',db,repository=RepositoryFontiStudio(db,b))
    assert fa.fonti==fb.fonti
    assert not any('non ancora approvato' in p for p in fa.pendenze)
    assert any('non ancora approvato' in p for p in fb.pendenze)


def test_chiamata_gateway_non_ammette_provider_esterni():
    from web.services.redazione_lex_runtime import chiamata_gateway
    class Gateway:
        def ask(self, **kwargs):
            assert kwargs['allow_external'] is False
            assert kwargs['requested_provider']=='llamacpp'
            return SimpleNamespace(content='bozza',provider='llamacpp',model='locale')
    assert chiamata_gateway(Gateway(),'fixture','llamacpp')('sistema','messaggio')==('bozza','llamacpp:locale')


def test_risposta_vuota_o_blocchi_mancanti_non_sono_consegna_pronta():
    import pytest
    args=dict(oggetto='recupero',risolta=_risolta(),fonti=FONTI,blocco_scadenze='',termini=[],fatti_testo='',oggi=date(2026,10,24),assistito='Mario Rossi',controparte='Beta s.r.l.',campi_modello=['facts'])
    with pytest.raises(ValueError,match='non ha restituito'):
        scrivi_blocchi(chiama_modello=lambda s,m: ('','locale'),**args)
    esito=scrivi_blocchi(chiama_modello=lambda s,m: ('### Fatto\nIl prezzo non è pagato.','locale'),**args)
    assert esito.stato_consegna['stato']=='bozza_incompleta'
    assert any('Blocco non restituito' in m for m in esito.stato_consegna['motivi'])


def test_limiti_fonti_campi_e_stati_pendenti():
    import pytest

    from lex.procedura_atti.stesura_blocchi import _fonte_per_messaggio, messaggio
    assert _fonte_per_messaggio("breve") == "breve"
    assert "accorciato" in _fonte_per_messaggio("riga\n" * 1000)
    assert "accorciato" in _fonte_per_messaggio("a" * 4000)
    assert campi_per_blocchi(["Corpo unico"], ["facts"]) == {"Corpo unico": "facts"}
    assert campi_per_blocchi(["Corpo unico"], []) == {}
    assert termini_da_scadenze([{"etichetta":"Primo giorno utile", "valore":"25/10/2026"}, {"etichetta":"Nessuna data", "valore":"da verificare"}]) == [{"descrizione":"Primo giorno utile", "scadenza":"25/10/2026", "per_agire":False}]
    risolta={"scrive_lex":[{"blocco":"Fatto","compito":"Esporre i fatti"}],"campi":[{"stato":"da_confermare","valore":"dato letto","etichetta":"Evento"}]}
    fonti=FontiScheda("fixture","fixture",fonti={1:"a"*4000},pendenze=["versione da verificare"])
    args=dict(oggetto="fixture",risolta=risolta,fonti=fonti,blocco_scadenze="termine calcolato",termini=[],fatti_testo="dato letto",oggi=date(2026,10,24),assistito="",controparte="",campi_modello=[])
    esito=scrivi_blocchi(chiama_modello=lambda s,m: ("### Fatto\nIl dato letto richiede conferma.","fixture"),**args)
    assert esito.stato_consegna["stato"] != "pronta_per_revisione_avvocato"
    assert any("accorciate" in m for m in esito.stato_consegna["motivi"])
    assert any("confermare" in m for m in esito.stato_consegna["motivi"])
    with pytest.raises(ValueError,match="non contiene"):
        scrivi_blocchi(chiama_modello=lambda s,m: ("", "fixture"),**{**args,"risolta":{}})
    msg=messaggio("fixture",{},FontiScheda("x","x"),blocco_scadenze="",oggi=date(2026,10,24),assistito="",controparte="")
    assert "Nessuna Fonte disponibile" in msg


def test_rimedio_deciso_intercetta_risposta_reale_contraddittoria():
    from lex.procedura_atti.stesura_blocchi import verifica_rimedio_deciso
    richiesta="Rimedio deciso: esclusivamente recesso con doppio della caparra. Non chiedere risoluzione."
    errata="Il contratto deve essere risolto per inadempimento. Si richiede il doppio della caparra."
    assert verifica_rimedio_deciso(errata,richiesta)[0][0]=="rimedio_diverso_da_quello_deciso"
    assert verifica_rimedio_deciso("Si chiede il recesso con doppio della caparra.",richiesta)==[]
    assert verifica_rimedio_deciso("Si esclude espressamente ogni richiesta di risoluzione del contratto.",richiesta)==[]
    assert verifica_rimedio_deciso("Non si chiede la risoluzione. Si esercita il recesso.",richiesta)==[]
    assert verifica_rimedio_deciso("Si chiede la risoluzione.","Valutare i rimedi della caparra")==[]
    assert verifica_rimedio_deciso("Si chiede la risoluzione.","Solo recesso da contratto senza altre indicazioni")==[]


def test_provider_privato_non_anonimizza_il_fascicolo_come_un_provider_esterno():
    from lex.gateway.config import GatewayConfig
    from lex.gateway.service import LexGateway
    from lex.gateway.messages import ProviderResponse
    cfg=GatewayConfig.from_env()
    cfg.providers["llamacpp"].enabled=True
    cfg.providers["llamacpp"].default_model="fixture-local"
    gateway=LexGateway(cfg)
    prompt="Fascicolo cliente Mario Rossi, codice fiscale RSSMRA80A01H501U: non alterare i fatti nel modello locale."
    class Provider:
        def chat(self, messages, **kwargs):
            assert messages[1].content == prompt
            return ProviderResponse(content="bozza",provider="llamacpp",model="fixture-local")
    gateway.providers["llamacpp"]=Provider()
    response=gateway.ask(user_id="fixture",prompt=prompt,requested_provider="llamacpp",allow_external=False)
    assert response.raw["lex_route"]["external_allowed"] is False
    assert response.raw["lex_route"]["provider_order"]==["llamacpp"]


def test_natura_del_contratto_e_rilascio_non_possono_essere_inventati():
    from lex.procedura_atti.stesura_blocchi import verifica_fatti_nuovi
    richiesta="Alfa esercita esclusivamente il recesso con doppio della caparra: 4000 euro."
    bozza="Recesso dal contratto di locazione. Si chiede il rilascio dell’immobile."
    errori=verifica_fatti_nuovi(bozza,richiesta)
    assert {x[0] for x in errori}=={"natura_contratto_non_fornita","domanda_non_decisa"}
    assert any(g[0]=="domanda_non_decisa" for g in verifica_fatti_nuovi("Si chiede il rilascio dell’immobile.",richiesta+" Non aggiungere rilascio di beni."))
    assert verifica_fatti_nuovi("Contratto di compravendita.","Le parti hanno stipulato una vendita.")==[]
    assert verifica_fatti_nuovi("Contratto di appalto.","Un appalto è documentato.")==[]
    assert verifica_fatti_nuovi("Si chiede il rilascio dell’immobile.","Si esercita esclusivamente il recesso con caparra e si chiede il rilascio.")==[]
    assert verifica_fatti_nuovi("Si chiede il rilascio dell’immobile.","Si chiede il rilascio.")==[]


def test_conclusioni_esclusive_non_aggiungono_accessori():
    from lex.procedura_atti.stesura_blocchi import verifica_fatti_nuovi, verifica_rimedio_deciso
    richiesta="Si chiede esclusivamente il recesso con doppio della caparra, 4000 euro."
    assert any(g[0]=="accessorio_non_deciso" for g in verifica_fatti_nuovi("4000 euro oltre interessi legali e spese.",richiesta))
    assert verifica_fatti_nuovi("4000 euro senza interessi.",richiesta)==[]
    assert verifica_fatti_nuovi("4000 euro oltre interessi.",richiesta+" Non aggiungere interessi.")
    assert verifica_fatti_nuovi("4000 euro e interessi.",richiesta+" Si chiedono interessi.")==[]
    assert verifica_rimedio_deciso("Senza che sia possibile chiedere la risoluzione.",richiesta)==[]


def test_una_sola_correzione_conserva_prima_bozza_e_controlli():
    errore=RISPOSTA.replace("[1]","ai sensi dell'art. 2043 c.c.")
    calls=[]
    def call(system,message):
        calls.append(message)
        return (errore if len(calls)==1 else RISPOSTA), "fixture"
    args=dict(oggetto="recupero",risolta=_risolta(),fonti=FONTI,blocco_scadenze="",termini=[],fatti_testo="",oggi=date(2026,10,24),assistito="Mario Rossi",controparte="Beta s.r.l.",campi_modello=["facts"])
    result=scrivi_blocchi(chiama_modello=call,**args)
    assert len(calls)==2 and "ERRORI DA CORREGGERE" in calls[1]
    assert result.prima_stesura==errore and result.testo==RISPOSTA
    assert result.revisione_prima_stesura["gravi"] and not result.revisione["gravi"]
    assert result.numero_stesure==2
    calls.clear()
    def failing(system,message):
        calls.append(message)
        if len(calls)==2:raise OSError("fixture offline")
        return errore,"fixture"
    failed=scrivi_blocchi(chiama_modello=failing,**args)
    assert len(calls)==2 and failed.revisione["gravi"]
    assert any(item[0]=="correzione_non_disponibile" for item in failed.revisione["pendenti"])
