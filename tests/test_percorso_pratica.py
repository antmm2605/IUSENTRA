"""Esito della sentenza letto dal dispositivo e rimedi conseguenti (esempi fittizi)."""

from pct.percorso_pratica.esito import dispositivo, esito_sentenza
from pct.percorso_pratica.rimedi import rimedi

ACCOLTA_CONTRO_PA = (
    "TRIBUNALE DI VELLETRI – Sezione lavoro. Il giudice, all'udienza del 7 ottobre 2026, ha pronunciato in pari data la seguente "
    "SENTENZA ex art. 429 c.p.c. ... Il ricorso è fondato e va accolto. P.Q.M. accoglie il ricorso e, per l'effetto, condanna il "
    "Ministero convenuto al pagamento in favore della ricorrente della somma di euro 500,00; condanna il Ministero al pagamento delle "
    "spese di lite, che liquida in € 250,00 oltre rimborso forfettario, IVA e CPA, con distrazione in favore del procuratore antistatario.\n"
    "Il giudice\nRossi"
)
RIGETTATA_PER_PRESCRIZIONE = (
    "Il credito azionato è prescritto, in mancanza di atti interruttivi anteriori al decorso del quinquennio. "
    "PER QUESTI MOTIVI rigetta il ricorso; compensa le spese di lite.\nCosì deciso"
)
INCOMPETENZA = "... P.Q.M. dichiara la propria incompetenza per territorio e indica come competente il Tribunale di Roma."


def test_dispositivo_si_legge_dopo_pqm_senza_la_firma():
    assert dispositivo(ACCOLTA_CONTRO_PA).startswith("accoglie il ricorso")
    assert "Rossi" not in dispositivo(ACCOLTA_CONTRO_PA)
    assert dispositivo("nessun dispositivo") == ""


def test_accoglimento_contro_la_pa_con_spese_e_distrazione():
    esito = esito_sentenza(ACCOLTA_CONTRO_PA, nostra_parte="ricorrente")
    assert esito["esito"] == "accoglimento" and esito["per_il_cliente"] == "favorevole"
    assert esito["spese"] == {"regolazione": "condanna", "importo": "250,00", "distrazione": True, "frase": esito["spese"]["frase"]}
    percorso = rimedi(esito, rito="lavoro", controparte_pa=True)
    assert percorso["strada"] == "realizzazione"
    norme = [n for passo in percorso["passi"] for n in passo["norme"]]
    assert "art. 14 D.L. 669/1996" in norme and "art. 93 c.p.c." in norme and "art. 112 c.p.a." in norme


def test_rigetto_per_prescrizione_propone_appello_lavoro_e_atti_interruttivi():
    esito = esito_sentenza(RIGETTATA_PER_PRESCRIZIONE, nostra_parte="ricorrente")
    assert esito["esito"] == "rigetto" and esito["per_il_cliente"] == "sfavorevole"
    assert esito["spese"]["regolazione"] == "compensazione"
    assert [r["ragione"] for r in esito["ragioni"]] == ["prescrizione"]
    percorso = rimedi(esito, rito="lavoro")
    assert percorso["strada"] == "impugnazione"
    assert "art. 434 c.p.c." in percorso["rimedi"][0]["norme"]
    assert percorso["ipotesi"][0]["norme"] == ["art. 2943 c.c."]


def test_rigetto_e_favorevole_per_il_convenuto():
    assert esito_sentenza(RIGETTATA_PER_PRESCRIZIONE, nostra_parte="convenuto")["per_il_cliente"] == "favorevole"


def test_incompetenza_indica_la_riassunzione_entro_tre_mesi():
    esito = esito_sentenza(INCOMPETENZA, nostra_parte="attore")
    assert esito["esito"] == "incompetenza"
    percorso = rimedi(esito)
    assert percorso["ipotesi"][0]["norme"] == ["art. 50 c.p.c."]


def test_sentenza_d_appello_porta_alla_cassazione():
    esito = esito_sentenza("P.Q.M. rigetta l'appello.", nostra_parte="appellante")
    assert rimedi(esito, grado="appello")["rimedi"][0]["rimedio"] == "Ricorso per cassazione"


def test_dispositivo_che_inizia_con_il_giudice_del_lavoro_e_spese_seguite_da_accessori():
    testo = ("... possono essere liquidate come da dispositivo.\nP.Q.M.\n\nIl Giudice del Lavoro, definitivamente pronunciando: "
             "-condanna la parte convenuta a emettere i buoni di spesa per euro 500,00; -condanna la parte convenuta al pagamento delle "
             "spese processuali, che liquida in euro 250,00, oltre accessori di legge, da distrarsi in favore dei procuratori antistatari. "
             "Velletri, 7 ottobre 2026 Il giudice dott. Bianchi")
    esito = esito_sentenza(testo, nostra_parte="ricorrente")
    assert esito["esito"] == "accoglimento"
    assert esito["spese"]["importo"] == "250,00" and esito["spese"]["distrazione"] is True


def test_importo_illeggibile_resta_vuoto():
    esito = esito_sentenza("P.Q.M. accoglie; condanna il convenuto alla rifusione delle spese, che liquida in euro 9,0esborsi.", nostra_parte="attore")
    assert esito["spese"]["importo"] == ""


def test_dispositivo_anomalo_senza_firma_non_blocca_la_lettura():
    """Regressione 08/11/2026: un documento lungo senza firma dopo il P.Q.M. bloccava lo scheduler (espressione non lineare)."""
    import time

    from pct.percorso_pratica.esito import esito_sentenza

    testo = "P.Q.M. il Tribunale condanna " + ("parte 1.234,00 abc " * 200000) + " spese"
    inizio = time.monotonic()
    esito_sentenza(testo)
    assert time.monotonic() - inizio < 2.0
