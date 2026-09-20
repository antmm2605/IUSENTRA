"""Una citazione composta si confronta articolo per articolo.

Sul fascicolo 5E864356 la lettura dichiarava mancante «artt. 325-326 c.p.c.».
Ma l'art. 325 c.p.c. — termini per le impugnazioni — sta nel registro delle
fonti verificate, con il suo testo e il suo link a Normattiva. Finche' la
citazione veniva confrontata tutta intera, la chiave diventava
`art325326cpc` e non corrispondeva a niente: una lacuna dichiarata su una
fonte che c'era, accanto a una che davvero manca.

Il trattino pero' non significa sempre intervallo: «art. 171-bis c.p.c.» e'
un articolo solo. La differenza sta in cosa lo segue — una cifra o una
parola.
"""

from __future__ import annotations

import pytest

from pct.procedura_fasi.fonti import FONTI
from pct.procedura_fasi.lacune import articoli_citati, lacune_conoscenza

#: Nessun codice di rito arriva qui: serve un numero che il registro non avra'.
ARTICOLO_INESISTENTE = 9997


def _un_articolo_registrato() -> str:
    """Un articolo del c.p.c. che sta nel registro adesso, qualunque esso sia."""
    for chiave in FONTI:
        if chiave.startswith("cpc_") and chiave[4:].isdigit():
            return chiave[4:]
    raise AssertionError("il registro non contiene nessun articolo del c.p.c.")

# ------------------------------------------------------- spezzare la citazione


def test_un_intervallo_diventa_i_suoi_articoli():
    assert articoli_citati("artt. 325-326 c.p.c.") == ["art. 325 c.p.c.", "art. 326 c.p.c."]


@pytest.mark.parametrize(
    "citazione",
    ["art. 171-bis c.p.c.", "art. 171-ter c.p.c.", "art. 281-undecies c.p.c.", "art. 163-bis c.p.c."],
)
def test_un_articolo_con_suffisso_non_si_spezza(citazione):
    """Dopo il trattino c'e' una parola: e' un articolo solo, non un intervallo."""

    assert articoli_citati(citazione) == [citazione]


def test_un_elenco_con_la_congiunzione_si_spezza():
    assert articoli_citati("artt. 1 e 2 c.p.c.") == ["art. 1 c.p.c.", "art. 2 c.p.c."]


def test_un_elenco_con_le_virgole_si_spezza():
    assert articoli_citati("artt. 414,415,416 c.p.c.") == [
        "art. 414 c.p.c.",
        "art. 415 c.p.c.",
        "art. 416 c.p.c.",
    ]


def test_elenco_misto_con_suffisso_e_numero():
    assert articoli_citati("artt. 281-undecies e 183 c.p.c.") == [
        "art. 281-undecies c.p.c.",
        "art. 183 c.p.c.",
    ]


def test_un_intervallo_troppo_ampio_resta_ai_suoi_estremi():
    """«artt. 1-500» rinvia a un capo intero: non sono cinquecento citazioni."""

    assert articoli_citati("artt. 1-500 c.p.c.") == ["art. 1 c.p.c.", "art. 500 c.p.c."]


def test_una_legge_con_anno_non_viene_scambiata_per_un_elenco():
    assert articoli_citati("art. 3 l. 742/1969") == ["art. 3 l. 742/1969"]


def test_un_articolo_singolo_resta_se_stesso():
    assert articoli_citati("art. 133 c.p.c.") == ["art. 133 c.p.c."]


# ------------------------------------------------------- le lacune dichiarate


def test_l_articolo_gia_verificato_non_e_piu_una_lacuna():
    """Il punto di tutta la correzione, scritto senza dipendere dal registro.

    Si costruisce la citazione con un articolo che il registro ha davvero e
    con un numero che non avra' mai: cosi' la prova resta valida quando il
    registro cresce, invece di rompersi al primo articolo aggiunto — che e'
    esattamente quello che e' successo appena ne ho aggiunti quattro.
    """

    registrato = _un_articolo_registrato()
    lacune = lacune_conoscenza(riferimenti=[f"Visti gli artt. {registrato} e {ARTICOLO_INESISTENTE} c.p.c."])
    chiavi = [voce["chiave"] for voce in lacune]

    assert f"art. {registrato} c.p.c." not in chiavi
    assert chiavi == [f"art. {ARTICOLO_INESISTENTE} c.p.c."]


def test_un_intervallo_di_articoli_tutti_registrati_non_lascia_lacune():
    """Senza la divisione la chiave dell'intervallo non corrisponderebbe a niente."""

    assert lacune_conoscenza(riferimenti=["visti gli artt. 415-416 c.p.c."]) == []


def test_restano_dichiarate_solo_le_norme_che_mancano_davvero():
    registrato = _un_articolo_registrato()
    testo = f"Visti gli artt. {registrato}-{ARTICOLO_INESISTENTE} c.p.c. e l'art. {ARTICOLO_INESISTENTE + 1} c.p.c."

    chiavi = [voce["chiave"] for voce in lacune_conoscenza(riferimenti=[testo])]

    assert f"art. {registrato} c.p.c." not in chiavi
    assert f"art. {ARTICOLO_INESISTENTE + 1} c.p.c." in chiavi


def test_una_norma_registrata_da_sola_non_produce_lacune():
    assert lacune_conoscenza(riferimenti=["si veda l'art. 415 c.p.c."]) == []


def test_lo_stesso_articolo_citato_due_volte_si_dichiara_una_volta_sola():
    n = ARTICOLO_INESISTENTE
    testo = f"art. {n} c.p.c. e poi ancora artt. {n},{n} c.p.c."

    chiavi = [voce["chiave"] for voce in lacune_conoscenza(riferimenti=[testo])]

    assert chiavi == [f"art. {n} c.p.c."]


# ------------------------------------------------- le quattro voci aggiunte


@pytest.mark.parametrize(
    "chiave, norma, nel_titolo",
    [
        ("cpc_133", "art. 133 c.p.c.", "Pubblicazione"),
        ("cpc_326", "art. 326 c.p.c.", "Decorrenza"),
        ("cpc_429", "art. 429 c.p.c.", "lavoro"),
        ("l742_art3", "art. 3 L. 742/1969", "feriale"),
    ],
)
def test_le_norme_del_rito_del_lavoro_sono_nel_registro(chiave, norma, nel_titolo):
    """Erano le quattro lacune del fascicolo 5E864356, ora fonti verificate."""

    voce = FONTI[chiave]

    assert voce["norma"] == norma
    assert nel_titolo.lower() in voce["titolo"].lower()
    assert voce["url"].startswith("https://www.normattiva.it/uri-res/N2Ls?urn:nir:")
    assert "Normattiva" in voce["verifica"]
    assert len(voce["estratto"]) > 80


def test_l_articolo_133_dichiara_quale_testo_e_stato_verificato():
    """E' stato sostituito nel 2024: la sola data non direbbe quale testo."""

    assert "164" in FONTI["cpc_133"]["verifica"]


def test_le_quattro_norme_non_sono_piu_lacune():
    testo = (
        "Visti l'art. 133 c.p.c., gli artt. 325-326 c.p.c., l'art. 429 c.p.c. "
        "e l'art. 3 l. 742/1969, nonché l'art. 171-bis c.p.c."
    )

    assert lacune_conoscenza(riferimenti=[testo]) == []
