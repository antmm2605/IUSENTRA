"""L'esito della sentenza dal dispositivo, come fatti «evento» dell'archivio delle letture (forma della sentenza Alessi)."""

from pct.archivio_letture.estrazione_esito import estrai_esito
from pct.registro_letture.fatti_repository import CATEGORIE

SENTENZA = ("REPUBBLICA ITALIANA IL TRIBUNALE DI VELLETRI ha pronunciato la seguente S E N T E N Z A ex art. 429 c.p.c. "
            "nella causa iscritta al n. 2539, del Ruolo Generale ... P.Q.M. Il Giudice del Lavoro, definitivamente pronunciando: "
            "-condanna la parte convenuta a emettere i buoni; -condanna la parte convenuta al pagamento delle spese processuali, "
            "che liquida in euro 250,00, oltre accessori di legge, da distrarsi in favore dei procuratori antistatari. "
            "Velletri, 7 ottobre 2026 Il giudice dott. X")


def test_esito_e_spese_come_fatti_ammessi_dall_archivio():
    fatti = {f.campo: f for f in estrai_esito(SENTENZA, origine="nativo")}
    assert fatti["esito_sentenza"].valore == "accoglimento"
    assert fatti["spese_sentenza"].valore == "condanna;importo=250,00;distrazione"
    assert all(f.categoria in CATEGORIE and f.verifica == "verificata" for f in fatti.values())


def test_un_atto_che_non_e_una_sentenza_non_ha_esito():
    assert estrai_esito("RICORSO EX ART. 414 C.P.C. ... P.Q.M. si chiede che il giudice accolga", origine="nativo") == []


def test_data_in_calce_e_udienza_cartolare_richiamata_nella_sentenza():
    from pct.archivio_letture.estrazione_ruolo import estrai_ruoli

    testo = (
        "Richiamato il proprio decreto di sostituzione dell’udienza del 9.10.2026;\n"
        "SENTENZA nel procedimento iscritto al n. 2848 del R.G. dell’anno 2026.\n"
        "P.Q.M. definitivamente pronunciando, accoglie il ricorso. "
        "Pone a carico dell’Amministrazione l’onere di rifusione delle spese di lite, che si liquidano "
        "ex D.M. 55/2014 in complessivi € 350,00 oltre accessori, con distrazione in favore del difensore. "
        "*Così deciso in Reggio Calabria, in data 9.10.2026*\nIL GIUDICE DEL LAVORO"
    )
    assert [f.valore for f in estrai_ruoli(testo, origine="indice")] == ["2848/2026"]
    fatti = {f.campo: f for f in estrai_esito(testo, origine="indice")}
    decisione = fatti["data_decisione_sentenza"]
    assert decisione.valore == "2026-10-09"
    assert any(prova["codice"] == "trattazione_scritta_decisa" for prova in decisione.prove)
    assert fatti["spese_sentenza"].valore == "condanna;importo=350,00;distrazione"


def test_riconosce_compensazione_anche_se_la_formula_di_merito_non_e_classificata():
    testo = (
        "TRIBUNALE — SENTENZA — RG 123/2024\nP.Q.M.\n"
        "Attribuisce alla parte ricorrente la somma indicata in motivazione. "
        "Compensa le spese di lite.\nCosì deciso il 01.02.2024."
    )

    fatti = {f.campo: f for f in estrai_esito(testo, origine="indice")}

    assert set(fatti) == {"spese_sentenza"}
    assert fatti["spese_sentenza"].valore == "compensazione"
    assert fatti["spese_sentenza"].valore_letto == "Compensa le spese di lite"
    assert fatti["spese_sentenza"].prove[0]["esito"] == "ok"
