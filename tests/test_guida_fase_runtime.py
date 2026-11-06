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
