"""Fascicolo 9A681FDF (10/11/2026): «Sentenza indicizzata da Lex AI: fascicolo definito — In corso → Definito —
Sentenza n. 679/2026» compariva due volte nell'Avanzamento pratica (22/06 e 24/07/2026): la stessa sentenza
indicizzata da due copie (identificativi docai diversi). La transizione con la stessa fonte è un fatto solo."""
from types import SimpleNamespace

from pct.avanzamento_storico import transizione_gia_registrata, voci_ripetute
from pct.fascicoli import AvanzamentoPratica

NOTA_1 = "Sentenza n. 100/2026; RG n. 50/2026; Documento: docai-4149dc33af4c4e81ac5b651bb426ca4b"
NOTA_2 = "Sentenza n. 100/2026; RG n. 50/2026; Documento: docai-5d96251bd29c4d7ead223e2b0ec6c2b5"
DESCR = "Sentenza indicizzata da Lex AI: fascicolo definito"


def _voce(data, prec, nuovo, note, descrizione=DESCR):
    return AvanzamentoPratica(data=data, descrizione=descrizione, stato_precedente=prec, stato_nuovo=nuovo, note=note)


STORICO_REALE = [
    _voce("2026-06-22T19:03:33+02:00", "IN_CORSO", "DEFINITO", NOTA_1),
    _voce("2026-07-09T08:30:11", "IN_CORSO", "IN_CORSO", "Assorbiti 1 record documento duplicati.", "Riconciliazione automatica documenti duplicati"),
    _voce("2026-07-24T07:07:10+02:00", "IN_CORSO", "DEFINITO", NOTA_2),
    _voce("2026-09-08T20:23:33+02:00", "DEFINITO", "DEFINITO", "Tipo: CIVILE → LAVORO.", "Classificazione della pratica aggiornata automaticamente"),
]


def test_lo_storico_gia_presente_nasconde_il_doppione_in_lettura():
    assert voci_ripetute(STORICO_REALE) == {2}


def test_la_stessa_transizione_con_la_stessa_sentenza_non_si_registra_due_volte():
    assert transizione_gia_registrata(STORICO_REALE[:2], "IN_CORSO", "DEFINITO", NOTA_2)


def test_dopo_una_riapertura_la_nuova_definizione_si_registra():
    storico = STORICO_REALE[:1] + [_voce("2026-07-01", "DEFINITO", "IN_CORSO", "Riaperto per impugnazione", "Stato cambiato")]
    assert not transizione_gia_registrata(storico, "IN_CORSO", "DEFINITO", NOTA_2)
    assert voci_ripetute(storico + [_voce("2026-08-01", "IN_CORSO", "DEFINITO", NOTA_2)]) == set()


def test_un_altra_sentenza_e_un_fatto_nuovo():
    assert not transizione_gia_registrata(STORICO_REALE[:1], "IN_CORSO", "DEFINITO", "Sentenza n. 200/2026; RG n. 50/2026")


def test_cambia_stato_e_idempotente_sulla_stessa_fonte():
    from pct.fascicoli import GestioneFascicoli, StatoFascicolo

    fascicolo = SimpleNamespace(stato=StatoFascicolo.IN_CORSO, data_chiusura="", avanzamento=list(STORICO_REALE[:2]), modificato_il="")
    gestore = GestioneFascicoli.__new__(GestioneFascicoli)
    gestore._get_o_errore = lambda _id: fascicolo
    esito = GestioneFascicoli.cambia_stato(gestore, "X", StatoFascicolo.DEFINITO, note=NOTA_2, avvocato="Lex AI backfill", persist=False)
    assert esito.stato == StatoFascicolo.DEFINITO and len(esito.avanzamento) == 2
    GestioneFascicoli.cambia_stato(gestore, "X", StatoFascicolo.IN_CORSO, note="Riaperto", persist=False)
    GestioneFascicoli.cambia_stato(gestore, "X", StatoFascicolo.DEFINITO, note=NOTA_2, persist=False)
    assert len(fascicolo.avanzamento) == 4


def test_pannello_avanzamento_mostra_la_sentenza_una_volta():
    from web.services.react_fascicoli_bridge import _history

    voci = _history(SimpleNamespace(avanzamento=STORICO_REALE))
    definizioni = [v for v in voci if v["to"] == "Definito" and v["from"] == "In corso"]
    assert len(definizioni) == 1 and definizioni[0]["notes"] == "Sentenza n. 100/2026; RG n. 50/2026"


def test_la_stessa_sentenza_da_un_file_con_nome_e_da_una_copia_indicizzata():
    storico = [
        _voce("2026-06-22", "IN_CORSO", "DEFINITO", "Sentenza n. 464/2026; RG n. 2154/2023; Documento: Sentenza (originale n. 464).pdf"),
        _voce("2026-07-22", "IN_CORSO", "DEFINITO", "Sentenza n. 464/2026; RG n. 2154/2023; Documento: docai-2aabc3005dfb45aa"),
    ]
    assert voci_ripetute(storico) == {1}
