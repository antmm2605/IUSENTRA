"""Direzione del capo spese (artt. 91, 92, 93 c.p.c.; art. 133 D.P.R. 115/2002): verifica del 01/11/2026."""

from types import SimpleNamespace

import pytest

from pct.fascicolo_sentenza_economica import analyze_sentenza_tribunale_text, applica_direzione_spese
from pct.spese_liquidate_esito import ANTISTATARIO, CLIENTE, CONTROPARTE, NON_DETERMINATO, STATO, capo_spese

TESTA = ("TRIBUNALE DI LOCRI SEZIONE LAVORO REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO "
         "Sentenza n. 123/2026 pubblicata il 15/10/2026 R.G. n. 456/2025 tra ROSSI MARIO (ricorrente) "
         "e MINISTERO DELL'ISTRUZIONE (resistente). Motivi della decisione. ")
VINCE = ("P.Q.M. accoglie il ricorso e condanna il Ministero resistente alla rifusione delle spese di lite in favore del "
         "ricorrente, che liquida in euro 2.500,00 per compensi, oltre spese generali al 15%, IVA e CPA.")
PERDE = ("P.Q.M. rigetta il ricorso e condanna il ricorrente alla rifusione delle spese di lite in favore del Ministero "
         "resistente, che liquida in euro 1.800,00 per compensi, oltre spese generali.")
META = ("P.Q.M. accoglie in parte il ricorso; compensa per metà le spese di lite e condanna il Ministero al pagamento "
        "della restante metà, che liquida per l'intero in euro 3.000,00 per compensi, oltre accessori.")
STATO_133 = ("P.Q.M. accoglie il ricorso e condanna il Ministero alla rifusione delle spese di lite, che liquida in euro "
             "2.200,00 per compensi, oltre accessori, da pagarsi in favore dello Stato ex art. 133 D.P.R. 115/2002.")
DISTRAZIONE = ("P.Q.M. accoglie il ricorso e condanna il Ministero al pagamento delle spese di lite che liquida in euro "
               "2.000,00 per compensi oltre accessori, con distrazione in favore del difensore antistatario.")
FASCICOLO = SimpleNamespace(id="F1", nome_cliente="Rossi Mario", titolo="Rossi c. Ministero")


@pytest.mark.parametrize("dispositivo, condannato, beneficiario, quota", [
    (VINCE, CONTROPARTE, "parte", 1.0),
    (PERDE, CLIENTE, "parte", 1.0),
    (META, CONTROPARTE, "parte", 0.5),
    (STATO_133, CONTROPARTE, STATO, 1.0),
    (DISTRAZIONE, CONTROPARTE, ANTISTATARIO, 1.0),
    ("P.Q.M. rigetta il ricorso. Spese compensate.", NON_DETERMINATO, "parte", 1.0),
])
def test_direzione_del_capo_spese(dispositivo, condannato, beneficiario, quota):
    esito = capo_spese(TESTA + dispositivo, ["Rossi Mario"])
    assert (esito.condannato, esito.beneficiario, esito.quota_dovuta) == (condannato, beneficiario, quota)


def test_condanna_del_cliente_per_nome():
    testo = TESTA + "P.Q.M. condanna Rossi Mario al pagamento delle spese di lite che liquida in euro 900,00 per compensi."
    assert capo_spese(testo, ["Rossi Mario"]).condannato == CLIENTE


@pytest.mark.parametrize("dispositivo, atteso, avviso", [
    (VINCE, 2500.0, None),
    (DISTRAZIONE, 2000.0, None),
    (META, 1500.0, None),
    (PERDE, None, "spese_liquidate_a_carico_del_cliente"),
    (STATO_133, None, "spese_liquidate_a_favore_dello_stato"),
])
def test_solo_la_condanna_della_controparte_diventa_compenso_dello_studio(dispositivo, atteso, avviso):
    testo = TESTA + dispositivo
    estrazione = applica_direzione_spese(analyze_sentenza_tribunale_text(testo), testo, FASCICOLO)
    assert estrazione.liquidazione_importo == atteso
    if avviso:
        assert avviso in estrazione.warnings
        assert estrazione.discordanze[-1]["kind"] == "liquidazione_giudice"
    assert estrazione.liquidazione_intera is not None


def test_compensazione_parziale_senza_indicazione_resta_da_verificare():
    testo = TESTA + ("P.Q.M. compensa per metà le spese e condanna il Ministero al pagamento delle spese "
                     "che liquida in euro 1.000,00 per compensi.")
    estrazione = applica_direzione_spese(analyze_sentenza_tribunale_text(testo), testo, FASCICOLO)
    assert estrazione.liquidazione_importo == 1000.0
    assert "compensazione_parziale_quota_da_verificare" in estrazione.warnings


def test_esborsi_e_compensi_nella_stessa_frase():
    testo = TESTA + ("P.Q.M. condanna il Ministero alla rifusione delle spese di lite che liquida in euro 98,00 per esborsi "
                     "ed euro 1.500,00 per compensi, oltre spese generali, IVA e CPA.")
    estrazione = analyze_sentenza_tribunale_text(testo)
    assert estrazione.spese_esborsi_importo == 98.0
    assert estrazione.liquidazione_importo == 1500.0


@pytest.mark.parametrize("dispositivo, atteso", [
    ("P.Q.M. accoglie il ricorso; condanna al pagamento delle spese che liquida in euro 900,00.", CONTROPARTE),
    ("P.Q.M. rigetta il ricorso; condanna al pagamento delle spese che liquida in euro 900,00.", CLIENTE),
])
def test_condanna_senza_parte_nominata_segue_l_esito(dispositivo, atteso):
    assert capo_spese(TESTA + dispositivo, ["Rossi Mario"]).condannato == atteso


# Tutte le materie (direttiva del 01/11/2026): formule dei dispositivi amministrativi (art. 26 c.p.a.), tributari
# (art. 15 D.Lgs. 546/1992) e penali (art. 541 c.p.p.), con «depositata il» al posto di «pubbl. il».
MATERIE = {
    "amministrativo": ("TRIBUNALE AMMINISTRATIVO REGIONALE PER LA CALABRIA REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO "
                       "Sentenza n. 345/2026 pubblicata il 10/09/2026 sul ricorso proposto da ROSSI MARIO contro COMUNE DI LOCRI. "
                       "P.Q.M. accoglie il ricorso. Condanna il Comune di Locri al pagamento delle spese di giudizio in favore del "
                       "ricorrente, che liquida in euro 2.000,00, oltre accessori di legge.", 2000.0, CONTROPARTE),
    "tributario": ("CORTE DI GIUSTIZIA TRIBUTARIA DI PRIMO GRADO DI REGGIO CALABRIA REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO "
                   "Sentenza n. 1200/2026 depositata il 05/10/2026 R.G.R. n. 450/2025 sul ricorso proposto da ROSSI MARIO, ricorrente, "
                   "contro AGENZIA DELLE ENTRATE, resistente. P.Q.M. accoglie il ricorso. Condanna l'Ufficio alla rifusione delle spese "
                   "di giudizio che liquida in euro 1.500,00 oltre accessori.", 1500.0, CONTROPARTE),
    "tributario_rigetto": ("CORTE DI GIUSTIZIA TRIBUTARIA DI PRIMO GRADO DI REGGIO CALABRIA Sentenza n. 1201/2026 depositata il "
                           "05/10/2026 R.G.R. n. 451/2025 sul ricorso proposto da ROSSI MARIO, ricorrente, contro AGENZIA DELLE ENTRATE, "
                           "resistente. P.Q.M. rigetta il ricorso. Condanna il ricorrente al pagamento delle spese di giudizio in favore "
                           "dell'Ufficio, liquidate in euro 800,00.", 800.0, CLIENTE),
    "penale": ("TRIBUNALE DI LOCRI REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO Sentenza n. 77/2026 depositata il 01/09/2026 "
               "R.G. n. 300/2024 nel procedimento a carico di BIANCHI LUIGI, imputato, con la costituzione di ROSSI MARIO, parte "
               "civile. P.Q.M. dichiara l'imputato colpevole; condanna l'imputato alla rifusione delle spese di costituzione e "
               "difesa sostenute dalla parte civile, che liquida in euro 2.500,00 oltre accessori.", 2500.0, CONTROPARTE),
}


@pytest.mark.parametrize("materia", sorted(MATERIE))
def test_liquidazione_in_tutte_le_materie(materia):
    testo, importo, condannato = MATERIE[materia]
    estrazione = analyze_sentenza_tribunale_text(testo)
    assert estrazione.found, materia
    assert estrazione.liquidazione_importo == importo
    assert capo_spese(testo, ["Rossi Mario"]).condannato == condannato
