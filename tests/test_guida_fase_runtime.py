"""La guida segue la fase reale letta nel fascicolo e, dopo la sentenza, il percorso secondo l'esito."""

from web.services.guida_fase_runtime import applica_fase_reale

LETTURA_DECISA = {
    "fase": {"codice": "decisa", "descrizione": "causa decisa: Sentenza del 07/10/2026", "prove": ["Sentenza (sentenza.pdf)"]},
    "percorso": {"strada": "realizzazione", "per_il_cliente": "favorevole",
                 "passi": [{"passo": "Notificare la sentenza alla controparte: fa decorrere il termine breve", "norme": ["art. 285 c.p.c."]}]},
    "prossimi_passi": [{"azione": "Confermare le proposte di catalogazione"}],
}


def test_causa_decisa_fase_e_prima_cosa_dal_percorso():
    payload = {"guida": {"quick_help": {"prima_cosa_da_fare": "Verificare la competenza"}}, "checklist": {"nota_fase": "Atto introduttivo già depositato"}}
    risultato = applica_fase_reale(payload, LETTURA_DECISA)
    assert risultato["checklist"]["nota_fase"].startswith("Causa decisa: Sentenza del 07/10/2026.")
    assert risultato["guida"]["quick_help"]["prima_cosa_da_fare"].startswith("Notificare la sentenza")
    assert risultato["percorso"]["strada"] == "realizzazione"


def test_senza_lettura_la_guida_resta_quella_della_scheda():
    payload = {"guida": {"quick_help": {"prima_cosa_da_fare": "Verificare la competenza"}}, "checklist": {}}
    assert applica_fase_reale(payload, None) == payload


def test_la_guida_usa_i_passi_persistiti_e_limita_la_bozza_agli_atti_da_fare(monkeypatch):
    from web.services import guida_fase_runtime, riscontri_processuali_runtime

    lettura = {
        **LETTURA_DECISA,
        "prossimi_passi": [
            {"azione": "Verificare la consegna", "fonti": [{"id": "cpc_326"}]},
            {"azione": "Depositare le note", "entro": "17/12/2026"},
        ],
        "ragionamento": {"conclusioni": [
            {"cosa": "Verificare la consegna", "stato": "dubbio", "template": "builtin-tmp-not-003",
             "letto": {"documento_id": "ricevuta", "documento": "ricevuta.eml"},
             "come": "Confrontare la relata con la ricevuta",
             "dubbi": [{"manca": "la ricevuta di avvenuta consegna"}]},
            {"cosa": "Depositare le note", "stato": "da_fare", "onerato_codice": "tutte_le_parti",
             "template": "builtin-tmp-civ-012", "termine": {"scadenza": "17/12/2026"}, "letto": {"documento_id": "decreto", "documento": "decreto.pdf"}},
        ]},
    }
    risultato = applica_fase_reale({}, lettura)
    assert risultato["guida"]["quick_help"]["prima_cosa_da_fare"] == "Verificare la consegna"
    ricevuta, note = risultato["passi_operativi"]
    assert ricevuta["documento"]["documento_id"] == "ricevuta"
    assert not ricevuta["modello_atto"]
    assert ricevuta["come"] == "Confrontare la relata con la ricevuta"
    assert ricevuta["riscontri_mancanti"] == ["la ricevuta di avvenuta consegna"]
    assert note["modello_atto"] == "builtin-tmp-civ-012"
    assert note["entro"] == "17/12/2026"
    assert "documento" not in lettura["prossimi_passi"][0]
    precedente = applica_fase_reale({}, {**lettura, "aggiornamento_pendente": True})
    assert precedente["passi_operativi"][1]["documento"]["documento_id"] == "decreto"
    assert precedente["passi_operativi"][1]["modello_atto"] == ""
    bozze = {"corrente": {"documento_id": "decreto", "termine": "2026-12-17"},
             "altro_decreto": {"documento_id": "diverso", "termine": "2026-12-17"},
             "altro_termine": {"documento_id": "decreto", "termine": "2026-12-18"}}
    monkeypatch.setattr(guida_fase_runtime, "lettura_pronta", lambda _id: lettura)
    monkeypatch.setattr(riscontri_processuali_runtime, "risultato_materializzato",
                        lambda _id, _pannello: {"bozzeNote": bozze})
    operativi = guida_fase_runtime.fase_per_la_guida("F1")["passi_operativi"]
    assert operativi[1]["bozza_note"] == {"chiave": "corrente", "documento_id": "decreto"}
    bozze["duplicata"] = dict(bozze["corrente"])
    assert "bozza_note" not in guida_fase_runtime.fase_per_la_guida("F1")["passi_operativi"][1]


def test_bozza_note_usa_solo_il_passaggio_corrente_e_univoco(monkeypatch):
    from web.services import guida_fase_runtime
    from web.services.react_template_studio_bridge import _campi_bozza_note

    passo = {"modello_atto": "builtin-tmp-civ-012", "entro": "17/12/2026",
             "documento": {"documento": "Decreto.pdf"}}
    fase = {"passi_operativi": [passo]}
    monkeypatch.setattr(guida_fase_runtime, "fase_per_la_guida", lambda _fid: fase)
    testo = _campi_bozza_note("F1", passo["modello_atto"], passo["entro"])["contenuto_istanza"]
    assert all(x in testo for x in ("127-ter", "Decreto.pdf", "17/12/2026", "sole istanze e conclusioni"))
    assert not _campi_bozza_note("F1", passo["modello_atto"], "18/12/2026")
    fase["passi_operativi"].append(passo)
    assert not _campi_bozza_note("F1", passo["modello_atto"], passo["entro"])
