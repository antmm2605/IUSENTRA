"""Ricostruzione dell'impaginazione dai token OCR e preparazione della pagina.

I dati di ingresso sono sintetici e riproducono cio' che il motore restituisce
per una pagina: parola, posizione, dimensione, confidenza e numeri di blocco,
capoverso e riga. Non serve il motore installato.
"""
from __future__ import annotations

import pytest

from legal_ocr.page_layout import (
    ELENCO,
    PARAGRAFO,
    TABELLA,
    TITOLO,
    analizza_pagina,
    righe_da_parole,
    segmenti_riga,
)
from web.services.document_ocr import parole_da_dati, punteggio_lettura


def parola(testo, sinistra, alto, larghezza=None, altezza=16, blocco=0, capoverso=0, riga=0, conf=95):
    return {
        "text": testo,
        "left": sinistra,
        "top": alto,
        "width": larghezza if larghezza is not None else len(testo) * 9,
        "height": altezza,
        "conf": conf / 100,
        "block": blocco,
        "par": capoverso,
        "line": riga,
    }


def riga_di(testi, alto, sinistra=60, passo=None, **extra):
    parole = []
    x = sinistra
    for testo in testi:
        parole.append(parola(testo, x, alto, **extra))
        x += (passo if passo is not None else len(testo) * 9 + 9)
    return parole


# ── Righe e segmenti ─────────────────────────────────────────────────────


def test_le_parole_diventano_righe_in_ordine_di_lettura():
    parole = riga_di(["seconda", "riga"], 140, riga=1) + riga_di(["prima", "riga"], 100, riga=0)
    righe = righe_da_parole(parole)
    assert [riga.testo for riga in righe] == ["prima riga", "seconda riga"]


def test_le_parole_vuote_non_producono_righe():
    assert righe_da_parole([parola("   ", 10, 10), {"text": "", "left": 0, "top": 0}]) == []


def test_i_segmenti_separano_le_celle_e_uniscono_le_parole():
    righe = righe_da_parole(
        [parola("Voce", 60, 100), parola("di", 105, 100), parola("spesa", 130, 100), parola("Importo", 400, 100)]
    )
    segmenti = segmenti_riga(righe[0], 60)
    assert [testo for _, _, testo in segmenti] == ["Voce di spesa", "Importo"]


# ── Titoli, capoversi, elenchi ───────────────────────────────────────────


def test_una_riga_breve_e_alta_e_un_titolo():
    parole = riga_di(["TRIBUNALE", "DI", "MILANO"], 40, sinistra=300, altezza=26)
    blocchi = analizza_pagina(parole)
    assert [blocco.tipo for blocco in blocchi] == [TITOLO]
    assert blocchi[0].testo == "TRIBUNALE DI MILANO"


def test_le_righe_vicine_formano_un_solo_capoverso():
    parole = riga_di(["Il", "sottoscritto", "avvocato"], 100, riga=0) + riga_di(["espone", "quanto", "segue."], 120, riga=1)
    blocchi = analizza_pagina(parole)
    assert len(blocchi) == 1
    assert blocchi[0].tipo == PARAGRAFO
    assert blocchi[0].testo == "Il sottoscritto avvocato espone quanto segue."


def test_la_sillabazione_di_fine_riga_viene_ricomposta():
    parole = riga_di(["quanto", "se-"], 100, riga=0) + riga_di(["gue", "in", "fatto."], 120, riga=1)
    assert analizza_pagina(parole)[0].testo == "quanto segue in fatto."


def test_un_salto_verticale_ampio_apre_un_nuovo_capoverso():
    parole = riga_di(["Primo", "capoverso", "del", "documento."], 100, riga=0)
    parole += riga_di(["Secondo", "capoverso", "distinto."], 180, blocco=1, riga=0)
    blocchi = analizza_pagina(parole)
    assert len(blocchi) == 2
    assert blocchi[1].testo.startswith("Secondo")


def test_il_marcatore_di_elenco_apre_una_voce_di_elenco():
    parole = riga_di(["Premessa", "del", "documento."], 100, riga=0)
    parole += riga_di(["-", "prima", "voce"], 122, blocco=1, riga=0)
    parole += riga_di(["-", "seconda", "voce"], 144, blocco=1, riga=1)
    tipi = [blocco.tipo for blocco in analizza_pagina(parole)]
    assert tipi.count(ELENCO) == 2


# ── Tabelle ──────────────────────────────────────────────────────────────


def tabella_sintetica():
    parole = []
    for indice, celle in enumerate([("Voce", "Importo", "Data"),
                                    ("Capitale", "10.000", "01/2026"),
                                    ("Interessi", "560", "06/2026")]):
        alto = 200 + indice * 30
        parole.append(parola(celle[0], 60, alto, riga=indice, blocco=2))
        parole.append(parola(celle[1], 300, alto, riga=indice, blocco=2))
        parole.append(parola(celle[2], 520, alto, riga=indice, blocco=2))
    return parole


def test_le_colonne_allineate_diventano_una_tabella():
    blocchi = analizza_pagina(tabella_sintetica())
    assert [blocco.tipo for blocco in blocchi] == [TABELLA]
    assert blocchi[0].righe == [
        ["Voce", "Importo", "Data"],
        ["Capitale", "10.000", "01/2026"],
        ["Interessi", "560", "06/2026"],
    ]


def test_la_tabella_convive_con_il_testo_intorno():
    parole = riga_di(["PROSPETTO", "DELLE", "SOMME"], 140, sinistra=250, altezza=24)
    parole += tabella_sintetica()
    parole += riga_di(["Totale", "dovuto", "come", "sopra", "indicato."], 320, blocco=3, riga=0)
    tipi = [blocco.tipo for blocco in analizza_pagina(parole)]
    assert tipi == [TITOLO, TABELLA, PARAGRAFO]


def test_due_righe_con_spaziatura_larga_ma_disallineata_non_sono_tabella():
    """Un capoverso giustificato non deve diventare una tabella."""
    parole = riga_di(["Il", "credito"], 100, sinistra=60, riga=0) + [parola("residuo", 520, 100, riga=0)]
    parole += [parola("ammonta", 60, 130, riga=1), parola("a", 300, 130, riga=1), parola("euro", 610, 130, riga=1)]
    assert all(blocco.tipo != TABELLA for blocco in analizza_pagina(parole))


def test_la_tabella_riporta_le_celle_vuote():
    parole = [parola("Voce", 60, 100, riga=0), parola("Importo", 300, 100, riga=0)]
    parole += [parola("Capitale", 60, 130, riga=1)]
    parole += [parola("Spese", 60, 160, riga=2), parola("120", 300, 160, riga=2)]
    tabelle = [blocco for blocco in analizza_pagina(parole) if blocco.tipo == TABELLA]
    assert tabelle and tabelle[0].righe[1] == ["Capitale", ""]


def test_il_blocco_tabella_si_serializza_con_righe_e_colonne():
    blocco = analizza_pagina(tabella_sintetica())[0]
    voce = blocco.come_dizionario()
    assert voce["tipo"] == TABELLA
    assert voce["colonne"] == 3
    assert len(voce["righe"]) == 3
    assert "testo" not in voce


def test_il_blocco_testuale_si_serializza_con_il_testo():
    voce = analizza_pagina(riga_di(["Testo", "semplice", "del", "documento."], 100))[0].come_dizionario()
    assert voce["tipo"] == PARAGRAFO
    assert voce["testo"] == "Testo semplice del documento."
    assert len(voce["riquadro"]) == 4


def test_una_pagina_senza_parole_non_produce_blocchi():
    assert analizza_pagina([]) == []


# ── Scelta della lettura migliore ────────────────────────────────────────


def test_i_dati_del_motore_diventano_parole_con_confidenza():
    dati = {
        "text": ["Tribunale", "", "  ", "di"],
        "conf": ["96", "-1", "-1", "88"],
        "left": [10, 0, 0, 120], "top": [20, 0, 0, 20],
        "width": [90, 0, 0, 20], "height": [16, 0, 0, 16],
        "block_num": [1, 0, 0, 1], "par_num": [1, 0, 0, 1], "line_num": [1, 0, 0, 1],
    }
    parole = parole_da_dati(dati)
    assert [p["text"] for p in parole] == ["Tribunale", "di"]
    assert parole[0]["conf"] == pytest.approx(0.96)


def test_la_lettura_con_piu_testo_sicuro_vince():
    buona = [{"text": "capoverso", "conf": 0.95} for _ in range(40)]
    spazzatura = [{"text": "|~", "conf": 0.20} for _ in range(80)]
    assert punteggio_lettura(buona) > punteggio_lettura(spazzatura)


def test_una_lettura_corta_ma_sicura_non_batte_una_lunga_e_sicura():
    corta = [{"text": "Tribunale", "conf": 0.99}]
    lunga = [{"text": "Tribunale", "conf": 0.95} for _ in range(30)]
    assert punteggio_lettura(lunga) > punteggio_lettura(corta)


def test_nessuna_parola_vale_zero():
    assert punteggio_lettura([]) == 0.0
