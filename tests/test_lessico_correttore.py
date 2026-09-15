"""Il correttore di lettura: corregge solo quando la parola giusta è una sola.

Un correttore che indovina è peggio di nessun correttore: in un atto una parola
cambiata a caso cambia il senso. Qui si verifica la regola dichiarata — la
parola letta non esiste, una sola parola del lessico si ottiene con le
confusioni dichiarate — e i casi in cui il correttore deve tenere le mani
ferme.
"""

from __future__ import annotations

import pytest

from legal_ocr.formulario import REGOLE_PER_ID, VERSIONE_FORMULARIO, applica_formulario
from legal_ocr.lessico import correggi_parola, correggi_testo, parole_conosciute
from legal_ocr.lessico.correttore import LUNGHEZZA_MINIMA, VERSIONE_CORRETTORE
from legal_ocr.lessico.italiano import ITALIANO_NUCLEO, dizionario_di_sistema


@pytest.mark.parametrize(
    ("letta", "corretta"),
    [
        ("cornparsa", "comparsa"),      # rn letto al posto di m
        ("CORNPARSA", "COMPARSA"),      # la forma di maiuscole si conserva
        ("Cornparsa", "Comparsa"),
        ("istan2a", "istanza"),         # 2 letto al posto di z
        ("u1teriore", "ulteriore"),     # 1 letto al posto di l
        ("ric0rso", "ricorso"),         # 0 letto al posto di o
        ("perentorìo", "perentorio"),   # accento in mezzo alla parola
        ("necessarìo", "necessario"),
        ("5entenza", "sentenza"),       # 5 letto al posto di s
    ],
)
def test_una_parola_inesistente_torna_alla_parola_del_lessico(letta, corretta):
    assert correggi_parola(letta) == corretta


@pytest.mark.parametrize(
    "parola",
    [
        "comparsa", "ricorso", "TRIBUNALE", "udienza",  # già giuste: non si toccano
        "Rossi", "Palmi", "Iusentra",                    # nomi propri sconosciuti al lessico
        "xyzkkq",                                        # nessun candidato
        "atto", "già", "città", "perché",                # accento finale: è dell'italiano
    ],
)
def test_il_correttore_tiene_le_mani_ferme(parola):
    assert correggi_parola(parola) == parola


def test_le_parole_brevi_non_si_correggono():
    assert len("i1") < LUNGHEZZA_MINIMA
    assert correggi_parola("i1") == "i1"
    assert correggi_parola("de1") == "de1"


def test_non_si_sceglie_fra_due_parole_esistenti():
    lessico = frozenset({"comparsa", "compresa"})
    # «cornparsa» darebbe «comparsa»; «cornpresa» darebbe «compresa»: una sola strada ciascuna.
    assert correggi_parola("cornparsa", lessico=lessico) == "comparsa"
    # Con due parole del lessico raggiungibili dalla stessa lettura non si corregge.
    ambiguo = frozenset({"perentorio", "perentoria"})
    assert correggi_parola("perentorìo", lessico=ambiguo) == "perentorio"
    due_strade = frozenset({"note", "nota"})
    assert correggi_parola("n0t0", lessico=due_strade) == "n0t0"


def test_un_riferimento_normativo_non_viene_corretto():
    testo = "Ai sensi della l. 69/2023 e del D.Lgs. 149/2022."
    corretto, cambiate = correggi_testo(testo)
    assert corretto == testo
    assert cambiate == 0


def test_il_testo_corretto_dichiara_quante_parole_sono_cambiate():
    corretto, cambiate = correggi_testo("La cornparsa contiene una istan2a di rinvio della udien2a.")
    assert corretto == "La comparsa contiene una istanza di rinvio della udienza."
    assert cambiate == 3


def test_un_testo_vuoto_resta_vuoto():
    assert correggi_testo("") == ("", 0)
    assert correggi_testo("   ") == ("   ", 0)


def test_la_regola_del_lessico_e_nel_formulario():
    assert "lessico.parola.v1" in REGOLE_PER_ID
    assert REGOLE_PER_ID["lessico.parola.v1"].etichetta
    assert REGOLE_PER_ID["lessico.parola.v1"].motivo
    esito = applica_formulario("La cornparsa di costituzione con istan2a di rinvio.")
    assert esito.testo == "La comparsa di costituzione con istanza di rinvio."
    assert ("lessico.parola.v1", 2) in esito.occorrenze


def test_la_regola_del_lessico_e_l_ultima_del_formulario():
    from legal_ocr.formulario import REGOLE

    assert REGOLE[-1].id == "lessico.parola.v1"


def test_la_versione_del_formulario_e_cambiata_con_la_nuova_regola():
    assert VERSIONE_FORMULARIO.endswith(".v3")
    assert VERSIONE_CORRETTORE


def test_il_lessico_funziona_anche_senza_dizionario_di_sistema():
    percorso, _parole = dizionario_di_sistema()
    assert isinstance(percorso, str)
    nucleo = frozenset(parola.casefold() for parola in ITALIANO_NUCLEO)
    assert nucleo <= parole_conosciute()
    assert correggi_parola("cornparsa", lessico=nucleo | {"comparsa"}) == "comparsa"


def test_il_nucleo_italiano_non_ha_doppioni():
    assert len(ITALIANO_NUCLEO) == len(set(parola.casefold() for parola in ITALIANO_NUCLEO))


@pytest.mark.parametrize("numero", ["2026", "1000", "1234", "0580010", "115", "44"])
def test_i_numeri_non_sono_parole_e_non_si_correggono(numero):
    assert correggi_parola(numero) == numero


def test_le_forme_gia_governate_restano_intatte():
    testo = "Udienza del 10/11/2026, R.G. 1234/2026, contributo unificato € 1.250,00, art. 163 c.p.c."
    corretto, cambiate = correggi_testo(testo)
    assert corretto == testo
    assert cambiate == 0


@pytest.mark.parametrize(
    "parola",
    [
        "Rossi", "Bianchi", "Esposito", "Palmi", "Catanzaro", "Milano",
        "IUSENTRA", "Tesseract", "PolisWeb", "Normattiva", "SICID", "DGSIA",
        "reintegrazione", "licenziamento", "rivalutazione", "rappresentante",
        "antistatario", "litisconsorte", "sovraindebitamento",
        "RSSMRA80C12G288X", "giustiziacert", "postacert",
    ],
)
def test_nomi_propri_e_termini_tecnici_non_si_toccano(parola):
    assert correggi_parola(parola) == parola


def test_un_atto_scritto_bene_non_viene_toccato():
    atto = (
        "TRIBUNALE ORDINARIO DI PALMI\n"
        "RICORSO EX ART. 414 C.P.C.\n"
        "Nell'interesse del signor Mario Rossi, nato a Palmi il 12/03/1980, codice fiscale RSSMRA80C12G288X,\n"
        "rappresentato e difeso dall'avv. Anna Bianchi, per l'accertamento della nullità del licenziamento\n"
        "intimato con lettera del 10/11/2025, ai sensi della l. 604/1966 e del D.Lgs. 23/2015."
    )
    corretto, cambiate = correggi_testo(atto)
    assert corretto == atto
    assert cambiate == 0
