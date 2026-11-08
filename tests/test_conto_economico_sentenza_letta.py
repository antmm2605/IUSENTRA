"""Conto economico: la sentenza già letta dal motore documenti, il contributo unificato incerto e le spese senza importo.

Casi fittizi costruiti sui difetti del collaudo dell'08/11/2026:
- sentenza di lavoro con condanna alle spese «che liquida in euro 250,00, oltre accessori… da distrarsi, ove
  richiesto, in favore dei procuratori dichiaratisi antistatari»: il conto diceva «Nessuna sentenza… quando arriva»;
- sentenza del giudice di pace che compensa le spese;
- ricevute di un pignoramento con € 139 di contributo e € 27 di anticipazione forfettaria (art. 30 D.P.R. 115/2002).
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.archivio_letture.spese_sentenza import beneficiario, importo_euro, spese_lette
from pct.fascicolo_conto_economico import conto_economico, riga_contributo, riga_sentenza, righe_parcella
from web.services.fascicolo_conto_economico_runtime import crediti_dalle_sentenze_lette

FRASE_CONDANNA = ("-condanna la parte convenuta al pagamento delle spese processuali in favore della parte ricorrente, che "
                  "liquida in euro 250,00, oltre accessori come per legge, da distrarsi, ove richiesto, in favore dei "
                  "procuratori dichiaratisi antistatari")


def _fatto(oggetto: str, categoria: str, campo: str, valore: str, posizione: int, contesto: str = "", verifica: str = "verificata"):
    return SimpleNamespace(oggetto_id=oggetto, categoria=categoria, campo=campo, valore=valore, posizione=posizione,
                           contesto=contesto, valore_letto=contesto[:200], verifica=verifica)


def _sentenza_lavoro(rg: str = "100/2025", oggetto: str = "SENT1"):
    return [
        _fatto(oggetto, "ruolo", "numero_ruolo", rg, 300),
        _fatto(oggetto, "evento", "esito_sentenza", "accoglimento", 25000),
        _fatto(oggetto, "evento", "spese_sentenza", "condanna;importo=250,00;distrazione", 25000, FRASE_CONDANNA),
        _fatto(oggetto, "data", "data_atto", "2026-10-07", 26000),
    ]


def test_spese_lette_dalla_sentenza_della_causa():
    lette = spese_lette(_sentenza_lavoro(), rg="100/2025")
    assert len(lette) == 1
    voce = lette[0]
    assert voce["regolazione"] == "condanna" and voce["importo"] == 250.0 and voce["distrazione"] is True
    assert voce["distrazione_condizionata"] is True and voce["accessori"] is True
    assert voce["beneficiario"] == "attivo" and voce["data"] == "2026-10-07"


def test_sentenza_di_altra_causa_o_non_verificata_non_conta():
    assert spese_lette(_sentenza_lavoro(rg="999/2020"), rg="100/2025") == []
    fatti = _sentenza_lavoro()
    fatti[2] = _fatto("SENT1", "evento", "spese_sentenza", "condanna;importo=250,00", 25000, FRASE_CONDANNA, verifica="plausibile")
    assert spese_lette(fatti, rg="100/2025") == []
    assert spese_lette(_sentenza_lavoro(), rg="") == []


def test_beneficiario_e_importo():
    assert beneficiario("condanna il Ministero al pagamento delle spese di lite") == "attivo"
    assert beneficiario("condanna parte ricorrente alla rifusione delle spese in favore della parte resistente") == "passivo"
    assert beneficiario("spese come da dispositivo") == ""
    assert importo_euro("1.234,56") == 1234.56 and importo_euro("x") is None


def _sentenze_runtime(**altro):
    voce = {**spese_lette(_sentenza_lavoro(), rg="100/2025")[0], "fonti": [
        {"label": "20708622s.pdf", "href": "/fascicoli/F1/documenti/SENT1/visualizza", "norma": "sentenza della causa"}]}
    voce.update(altro)
    return [voce]


def test_conto_mostra_la_sentenza_letta_con_fonte_cliccabile_e_accessori():
    sentenze = _sentenze_runtime(a_favore_del_cliente=True)
    crediti = crediti_dalle_sentenze_lette(sentenze)
    conto = conto_economico(voci={}, crediti=crediti, sentenze=sentenze, documenti_contributo=[], parcelle=[])
    riga = conto["righe"][0]
    assert riga["importoLabel"] == "€ 250,00" and riga["stato"] == "Distratte in favore dell'avvocato"
    assert riga["norma"] == "art. 93 c.p.c."
    assert riga["fonti"][0]["href"] == "/fascicoli/F1/documenti/SENT1/visualizza"
    assert "quando arriva" not in riga["dettaglio"].lower()
    assert "15%" in riga["dettaglio"] and "art. 2, comma 2, D.M. 55/2014" in riga["dettaglio"]
    assert "ove richiesto" in riga["dettaglio"]
    assert conto["percorso"]["passi"][0]["fatto"] is True
    assert "proforma" in conto["percorso"]["prossimoPasso"].lower()


def test_condanna_del_cliente_non_e_un_credito():
    sentenze = _sentenze_runtime(a_favore_del_cliente=False)
    assert crediti_dalle_sentenze_lette(sentenze) == []
    riga = riga_sentenza([], sentenze)
    assert riga["stato"] == "Spese a carico del cliente" and riga["tono"] == "danger" and riga["norma"] == "art. 91 c.p.c."


def test_spese_compensate_non_attendono_la_sentenza():
    sentenze = [{"regolazione": "compensazione", "importo": None, "distrazione": False, "data": "2026-05-04",
                 "fonti": [{"label": "Atto_3217226.pdf", "href": "/x", "norma": "sentenza della causa"}]}]
    conto = conto_economico(voci={}, crediti=[], sentenze=sentenze, documenti_contributo=[], parcelle=[])
    riga = conto["righe"][0]
    assert riga["stato"] == "Spese compensate" and riga["norma"] == "art. 92 c.p.c."
    assert "04/05/2026" in riga["dettaglio"] and "quando arriva" not in riga["dettaglio"].lower()
    assert conto["percorso"]["passi"][0]["fatto"] is True


def test_senza_sentenza_resta_il_messaggio_di_attesa():
    assert riga_sentenza([], [])["stato"] == "Nessuna sentenza con spese liquidate"


def test_contributo_con_anticipazione_forfettaria_non_e_versato_certo():
    voce = {"importo": 27.0, "importiLetti": ["139.00", "27.00"], "richiedeConferma": True}
    documenti = [{"etichetta": "Contributo unificato / pagamento", "nome": "rt_1.xml", "href": "/r1", "confermato": False}]
    riga = riga_contributo(voce, documenti)
    assert riga["stato"] == "Versato, da confermare" and riga["tono"] == "warning" and riga["importo"] is None
    assert "€ 139,00" in riga["dettaglio"] and "art. 30 D.P.R. 115/2002" in riga["dettaglio"]


def test_contributo_confermato_resta_versato():
    voce = {"importo": 98.0}
    documenti = [{"etichetta": "Contributo unificato / pagamento", "nome": "rt.xml", "href": "/r", "confermato": True}]
    riga = riga_contributo(voce, documenti)
    assert riga["stato"] == "Versato" and riga["importoLabel"] == "€ 98,00"


def test_spese_con_fonte_senza_importo():
    righe = righe_parcella([], {"documento_fonte": "Atto di precetto", "href": "/p"}, {})
    spese = next(r for r in righe if r["voce"] == "spese_esborsi")
    assert spese["stato"] == "Importo da riportare" and spese["tono"] == "warning"
    vuote = next(r for r in righe_parcella([], {}, {}) if r["voce"] == "spese_esborsi")
    assert vuote["stato"] == "Nessuna spesa registrata"


def test_accessori_senza_iva_nel_regime_forfetario():
    from pct.fascicolo_conto_economico import riga_sentenza
    credito = {"importo": 250.0, "distrazione": True, "accessori": True, "fonti": []}
    forfetario = riga_sentenza([credito], regime="RF19")["dettaglio"]
    ordinario = riga_sentenza([credito], regime="RF01")["dettaglio"]
    assert "senza IVA per il regime forfetario" in forfetario and "e IVA" not in forfetario
    assert "contributo previdenziale e IVA" in ordinario
