"""Dopo la sentenza: il mezzo d'impugnazione segue giurisdizione e grado (esempi fittizi costruiti sulle norme vigenti).

Norme lette l'08/11/2026 nell'archivio Normattiva del software: artt. 325, 327, 360, 391-bis c.p.c.; artt. 92, 94, 100,
106, 110, 119 c.p.a.; artt. 38, 51, 52, 62, 64 D.Lgs. 546/1992 (il D.Lgs. 175/2024 si applica dal 1° gennaio 2027,
art. 131); artt. 585, 593, 606 c.p.p.
"""

from pct.fascicolo_lettura.percorso import identificativi, impugnazione_del_grado, percorso_dopo_sentenza
from pct.percorso_pratica.giurisdizioni import giurisdizione_e_grado
from pct.procedura_fasi.fonti import FONTI
from pct.procedura_fasi.riti import rito_per_fascicolo


def _documenti(esito, etichetta="Sentenza"):
    return {"sentenza": {"etichetta": etichetta, "data_it": "07/10/2026", "esito": esito}}


def _percorso(ufficio, tipo="CIVILE", esito="rigetto", etichetta="Sentenza", rito=""):
    intestazione = {"tipo": tipo, "ufficio": ufficio, "rito": rito, "parti": {"ricorrente": ["Rossi Mario"], "resistente": ["Bianchi spa"]}}
    return percorso_dopo_sentenza(intestazione, _documenti({"esito_sentenza": esito}, etichetta))


def test_sentenza_della_corte_d_appello_si_impugna_in_cassazione():
    percorso = _percorso("Corte d'Appello di Roma")
    primo = percorso["rimedi"][0]
    assert (percorso["giurisdizione"], percorso["grado"]) == ("civile", "appello")
    assert primo["rimedio"] == "Ricorso per cassazione" and primo["termine"].startswith("60 giorni")
    assert "art. 360 c.p.c." in primo["norme"] and primo["template"] == "CIV_CASSAZIONE_BREVE"
    assert all(r["rimedio"] != "Appello" for r in percorso["rimedi"])


def test_tribunale_in_grado_d_appello_dall_intestazione_della_sentenza():
    percorso = _percorso("Tribunale di Napoli", etichetta="Sentenza pronunciata in grado di appello avverso la sentenza del Giudice di pace")
    assert percorso["grado"] == "appello" and percorso["rimedi"][0]["rimedio"] == "Ricorso per cassazione"


def test_sentenza_del_tar_appello_al_consiglio_di_stato_con_termini_cpa():
    percorso = _percorso("TAR Lazio", tipo="AMMINISTRATIVO")
    primo = percorso["rimedi"][0]
    assert (percorso["giurisdizione"], percorso["grado"]) == ("amministrativo", "primo")
    assert primo["rimedio"].startswith("Appello al Consiglio di Stato")
    assert {"art. 100 c.p.a.", "art. 92 c.p.a.", "art. 94 c.p.a."} <= set(primo["norme"])
    assert "60 giorni" in primo["termine"] and "sei mesi" in primo["termine"] and "dimezzati" in primo["termine"]
    assert not [n for r in percorso["rimedi"] for n in r["norme"] if n.endswith("c.p.c.")]


def test_sentenza_del_consiglio_di_stato_solo_cassazione_per_giurisdizione():
    percorso = _percorso("Consiglio di Stato, sez. VI", tipo="AMMINISTRATIVO")
    assert percorso["rimedi"][0]["norme"][0] == "art. 110 c.p.a."


def test_corte_di_giustizia_tributaria_di_primo_grado_appello_dlgs_546():
    percorso = _percorso("Corte di giustizia tributaria di primo grado di Milano", tipo="TRIBUTARIO")
    primo = percorso["rimedi"][0]
    assert (percorso["giurisdizione"], percorso["grado"]) == ("tributario", "primo")
    assert primo["rimedio"] == "Appello alla corte di giustizia tributaria di secondo grado"
    assert "art. 51 D.Lgs. 546/1992" in primo["norme"] and "60 giorni" in primo["termine"] and "sei mesi" in primo["termine"]
    secondo = _percorso("Corte di giustizia tributaria di secondo grado della Lombardia", tipo="TRIBUTARIO")
    assert secondo["grado"] == "appello" and secondo["rimedi"][0]["rimedio"] == "Ricorso per cassazione"
    assert "art. 62 D.Lgs. 546/1992" in secondo["rimedi"][0]["norme"]


def test_penale_termini_dell_art_585_cpp():
    percorso = _percorso("Tribunale di Bari", tipo="PENALE")
    primo = percorso["rimedi"][0]
    assert (percorso["giurisdizione"], primo["rimedio"]) == ("penale", "Appello")
    assert "art. 585 c.p.p." in primo["norme"] and "15 giorni" in primo["termine"] and "45" in primo["termine"]
    assert "30 giorni dalla notificazione" not in primo["termine"]
    appello = _percorso("Corte d'Appello di Bari", tipo="PENALE")
    assert appello["rimedi"][0]["rimedio"] == "Ricorso per cassazione" and "art. 606 c.p.p." in appello["rimedi"][0]["norme"]


def test_primo_grado_civile_resta_l_appello():
    percorso = _percorso("Tribunale di Milano")
    assert percorso["rimedi"][0]["rimedio"] == "Appello" and percorso["rimedi"][0]["template"] == "CIV_APPELLO_BREVE"


def test_senza_esito_letto_il_grado_decide_il_mezzo():
    intestazione = {"tipo": "CIVILE", "ufficio": "Corte d'Appello di Torino"}
    assert impugnazione_del_grado(intestazione, {"sentenza": {"etichetta": "Sentenza"}})["rimedio"] == "Ricorso per cassazione"
    assert impugnazione_del_grado({"tipo": "CIVILE", "ufficio": "Tribunale di Torino"}, {}) is None


def test_ogni_norma_dei_rimedi_e_nel_registro_delle_fonti():
    for ufficio, tipo in (("TAR Lazio", "AMMINISTRATIVO"), ("Consiglio di Stato", "AMMINISTRATIVO"),
                          ("Corte di giustizia tributaria di primo grado di Roma", "TRIBUTARIO"),
                          ("Corte di giustizia tributaria di secondo grado del Lazio", "TRIBUTARIO"),
                          ("Tribunale di Roma", "PENALE"), ("Corte d'Appello di Roma", "PENALE"), ("Corte di cassazione", "CIVILE")):
        for rimedio in _percorso(ufficio, tipo=tipo)["rimedi"]:
            for chiave in identificativi(rimedio["norme"]):
                assert chiave in FONTI, (ufficio, chiave)


def test_riconoscimento_giurisdizione_senza_falsi_positivi():
    assert giurisdizione_e_grado(tipo="famiglia", ufficio="Tribunale di Roma", rito="volontaria giurisdizione") == ("civile", "primo")
    assert giurisdizione_e_grado(tipo="civile", ufficio="Corte di cassazione") == ("civile", "cassazione")


def test_rito_non_riconosciuto_per_sottostringa():
    assert rito_per_fascicolo("FAMIGLIA", "volontaria giurisdizione") == "ordinario"
    assert rito_per_fascicolo("SUCCESSIONI", "successione testamentaria") == "ordinario"
    assert rito_per_fascicolo("CIVILE", "atto notarile") == "ordinario"
    assert rito_per_fascicolo("FAMIGLIA", "amministrazione di sostegno") == "ordinario"
    assert rito_per_fascicolo("CIVILE", "ricorso al TAR") == "amministrativo"
    assert rito_per_fascicolo("CIVILE", "giudizio amministrativo") == "amministrativo"
    assert rito_per_fascicolo("CIVILE", "rito semplificato di cognizione") == "semplificato"
