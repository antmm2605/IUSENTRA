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

from pct.procedura_fasi.lacune import articoli_citati, lacune_conoscenza

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
    """Il punto di tutta la correzione: il 325 c'e', e non va dichiarato mancante."""

    lacune = lacune_conoscenza(riferimenti=["Visti gli artt. 325-326 c.p.c."])
    chiavi = [voce["chiave"] for voce in lacune]

    assert "art. 325 c.p.c." not in chiavi
    assert "art. 326 c.p.c." in chiavi


def test_restano_dichiarate_solo_le_norme_che_mancano_davvero():
    testo = "Visti gli artt. 325-326 c.p.c., l'art. 133 c.p.c. e l'art. 429 c.p.c."

    chiavi = [voce["chiave"] for voce in lacune_conoscenza(riferimenti=[testo])]

    assert chiavi == ["art. 326 c.p.c.", "art. 133 c.p.c.", "art. 429 c.p.c."]


def test_una_norma_registrata_da_sola_non_produce_lacune():
    assert lacune_conoscenza(riferimenti=["si veda l'art. 415 c.p.c."]) == []


def test_lo_stesso_articolo_citato_due_volte_si_dichiara_una_volta_sola():
    testo = "art. 133 c.p.c. e poi ancora artt. 133,133 c.p.c."

    chiavi = [voce["chiave"] for voce in lacune_conoscenza(riferimenti=[testo])]

    assert chiavi == ["art. 133 c.p.c."]
