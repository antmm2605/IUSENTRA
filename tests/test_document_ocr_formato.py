"""Formato del testo riconosciuto: misurato sulla pagina, non indovinato.

Un atto restituito come capoversi tutti uguali costringe l'avvocato a
riformattare a mano prima di poterlo usare. Qui si verifica che intestazioni,
rubriche, formule centrate e sottoscrizioni a destra tornino con la forma che
avevano sul foglio — e, altrettanto importante, che quello che non si puo'
misurare non venga dichiarato lo stesso.
"""

from __future__ import annotations

import pytest

from legal_ocr.page_layout import analizza_pagina, righe_da_parole
from web.services.document_ocr_formato import (
    ALLINEAMENTO_CENTRO,
    ALLINEAMENTO_DESTRA,
    ALLINEAMENTO_SINISTRA,
    blocchi_con_formato,
    misure_pagina,
)


def _parola(testo, sinistra, alto, *, larghezza=None, altezza=20, riga=1, blocco=1, **extra):
    voce = {
        "text": testo,
        "left": sinistra,
        "top": alto,
        "width": larghezza if larghezza is not None else len(testo) * 11,
        "height": altezza,
        "conf": 0.95,
        "block": blocco,
        "par": blocco,
        "line": riga,
    }
    voce.update(extra)
    return voce


def _riga(testo, sinistra, alto, *, altezza=20, riga=1, blocco=1, **extra):
    """Una riga di testo come parole affiancate, con la larghezza reale."""
    parole = []
    cursore = sinistra
    for indice, pezzo in enumerate(testo.split()):
        larghezza = len(pezzo) * (altezza * 0.55)
        parole.append(_parola(pezzo, round(cursore), alto, larghezza=round(larghezza), altezza=altezza, riga=riga, blocco=blocco, **extra))
        cursore += larghezza + altezza * 0.35
    return parole


def _pagina(*gruppi):
    parole = []
    for gruppo in gruppi:
        parole.extend(gruppo)
    return parole


CORPO = (
    "Il sottoscritto avvocato chiede che il Tribunale voglia fissare l udienza di comparizione delle parti"
)


def _blocchi(parole):
    return blocchi_con_formato(analizza_pagina(parole), parole)


def test_una_riga_piu_grande_del_corpo_e_un_titolo():
    parole = _pagina(
        _riga("TRIBUNALE ORDINARIO DI BARI", 320, 60, altezza=32, riga=1, blocco=1),
        _riga(CORPO, 100, 140, altezza=20, riga=1, blocco=2),
        _riga(CORPO, 100, 180, altezza=20, riga=2, blocco=2),
    )
    blocchi = _blocchi(parole)
    assert blocchi[0]["formato"]["livello"] == 1
    assert blocchi[0]["formato"]["scala"] > 1.45
    assert blocchi[1]["formato"]["livello"] == 0, "il corpo del testo non e' un titolo"


@pytest.mark.parametrize(
    ("altezza", "livello"),
    [(32, 1), (26, 2), (23, 3), (20, 0)],
)
def test_il_livello_del_titolo_segue_la_dimensione(altezza, livello):
    parole = _pagina(
        _riga("INTESTAZIONE DELL ATTO", 150, 60, altezza=altezza, riga=1, blocco=1),
        _riga(CORPO, 100, 140, altezza=20, riga=1, blocco=2),
        _riga(CORPO, 100, 180, altezza=20, riga=2, blocco=2),
        _riga(CORPO, 100, 220, altezza=20, riga=3, blocco=2),
    )
    assert _blocchi(parole)[0]["formato"]["livello"] == livello


def test_una_formula_fra_i_due_margini_e_centrata():
    """«P.Q.M.» sta in mezzo alla pagina: e' centrato, non rientrato."""
    parole = _pagina(
        _riga(CORPO, 100, 100, riga=1, blocco=1),
        _riga(CORPO, 100, 140, riga=2, blocco=1),
        _riga("P. Q. M.", 480, 200, riga=1, blocco=2),
    )
    blocchi = _blocchi(parole)
    formula = next(blocco for blocco in blocchi if "Q." in (blocco.get("testo") or ""))
    assert formula["formato"]["allineamento"] == ALLINEAMENTO_CENTRO


def test_la_sottoscrizione_a_filo_del_margine_destro_e_a_destra():
    parole = _pagina(
        _riga(CORPO, 100, 100, riga=1, blocco=1),
        _riga(CORPO, 100, 140, riga=2, blocco=1),
        # La sottoscrizione finisce a filo del margine destro del corpo.
        _riga("Avv. Mario Rossi", 1122, 220, riga=1, blocco=2),
    )
    blocchi = _blocchi(parole)
    firma = next(blocco for blocco in blocchi if "Rossi" in (blocco.get("testo") or ""))
    assert firma["formato"]["allineamento"] == ALLINEAMENTO_DESTRA


def test_il_corpo_del_testo_resta_a_sinistra():
    parole = _pagina(_riga(CORPO, 100, 100, riga=1, blocco=1), _riga(CORPO, 100, 140, riga=2, blocco=1))
    assert _blocchi(parole)[0]["formato"]["allineamento"] == ALLINEAMENTO_SINISTRA


def test_il_grassetto_si_misura_dall_inchiostro():
    """Il grassetto e' letteralmente piu' inchiostro sulla stessa area."""
    parole = _pagina(
        _riga(CORPO, 100, 100, riga=1, blocco=1, densita=0.20),
        _riga(CORPO, 100, 140, riga=2, blocco=1, densita=0.20),
        _riga("MOTIVI DELLA OPPOSIZIONE", 100, 220, riga=1, blocco=2, densita=0.34),
    )
    blocchi = _blocchi(parole)
    rubrica = next(blocco for blocco in blocchi if "MOTIVI" in (blocco.get("testo") or ""))
    assert rubrica["formato"]["grassetto"] is True
    assert blocchi[0]["formato"]["grassetto"] is False


def test_una_differenza_minima_di_inchiostro_non_e_grassetto():
    parole = _pagina(
        _riga(CORPO, 100, 100, riga=1, blocco=1, densita=0.20),
        _riga(CORPO, 100, 140, riga=2, blocco=1, densita=0.20),
        _riga("Seconda parte del testo del documento", 100, 220, riga=1, blocco=2, densita=0.22),
    )
    seconda = _blocchi(parole)[1]
    assert seconda["formato"]["grassetto"] is False


def test_una_rubrica_in_grassetto_diventa_titolo_di_quarto_livello():
    parole = _pagina(
        _riga(CORPO, 100, 100, riga=1, blocco=1, densita=0.20),
        _riga(CORPO, 100, 140, riga=2, blocco=1, densita=0.20),
        _riga("IN FATTO", 100, 220, riga=1, blocco=2, densita=0.36),
    )
    rubrica = next(blocco for blocco in _blocchi(parole) if "FATTO" in (blocco.get("testo") or ""))
    assert rubrica["formato"]["livello"] == 4


def test_il_corsivo_non_si_inventa_dall_immagine():
    """Dall'immagine il corsivo non e' misurabile: dichiararlo sarebbe inventare."""
    parole = _pagina(_riga(CORPO, 100, 100, riga=1, blocco=1), _riga(CORPO, 100, 140, riga=2, blocco=1))
    assert _blocchi(parole)[0]["formato"]["corsivo"] is False


def test_il_formato_dichiarato_dal_documento_prevale_sulla_stima():
    """Un PDF nativo dichiara carattere e stile: quel dato vale piu' di una misura."""
    parole = _pagina(
        _riga(CORPO, 100, 100, riga=1, blocco=1, corpo=11.0, grassetto=False, corsivo=False, densita=0.30),
        _riga(CORPO, 100, 140, riga=2, blocco=1, corpo=11.0, grassetto=False, corsivo=False, densita=0.30),
        _riga("Considerato in diritto", 100, 220, riga=1, blocco=2, corpo=11.0, grassetto=True, corsivo=True, densita=0.10),
    )
    blocco = _blocchi(parole)[1]
    assert blocco["formato"]["grassetto"] is True, "lo stile dichiarato dal PDF e' stato ignorato"
    assert blocco["formato"]["corsivo"] is True
    assert blocchi_con_formato(analizza_pagina(parole), parole)[0]["formato"]["grassetto"] is False


def test_i_margini_non_si_spostano_per_un_numero_di_pagina_a_bordo_foglio():
    """Un timbro o un numero di pagina non devono far sembrare rientrato l'atto."""
    parole = _pagina(
        _riga(CORPO, 100, 100, riga=1, blocco=1),
        _riga(CORPO, 100, 140, riga=2, blocco=1),
        _riga(CORPO, 100, 180, riga=3, blocco=1),
        _riga("1", 20, 1400, riga=1, blocco=9),
    )
    misure = misure_pagina(parole)
    assert misure.colonna_sinistra >= 90, "il numero di pagina ha spostato il margine della colonna"


def test_ogni_blocco_dichiara_sempre_il_proprio_formato():
    """La pagina React legge il formato di ogni blocco: non puo' mancare."""
    parole = _pagina(
        _riga("TRIBUNALE DI BARI", 300, 60, altezza=30, riga=1, blocco=1),
        _riga(CORPO, 100, 140, riga=1, blocco=2),
        _riga(CORPO, 100, 180, riga=2, blocco=2),
    )
    for blocco in _blocchi(parole):
        formato = blocco["formato"]
        assert set(formato) == {"livello", "grassetto", "corsivo", "allineamento", "scala"}
        assert formato["allineamento"] in {ALLINEAMENTO_SINISTRA, ALLINEAMENTO_CENTRO, ALLINEAMENTO_DESTRA}


def test_le_righe_tornano_nell_ordine_in_cui_si_leggono():
    """Regressione: una riga in corpo grande veniva letta prima di righe superiori.

    L'ordine si misurava con l'altezza della singola riga invece che con
    un'unita' della pagina, quindi su un atto — dove titoli e rubriche sono
    sempre piu' grandi del corpo — il testo si ricomponeva rimescolato.
    """
    parole = _pagina(
        _riga("prima riga del documento", 100, 300, altezza=20, riga=1, blocco=1),
        _riga("SECONDA", 100, 400, altezza=34, riga=1, blocco=2),
        _riga("terza riga del documento", 100, 500, altezza=20, riga=1, blocco=3),
    )
    righe = righe_da_parole(parole)
    assert [riga.testo.split()[0] for riga in righe] == ["prima", "SECONDA", "terza"]


def test_le_pagine_del_documento_restano_pagine_nel_testo_composto():
    """Il passaggio da una pagina all'altra e' impaginazione, non un capoverso."""
    from pathlib import Path

    blocchi = (Path(__file__).resolve().parents[1] / "frontend/src/components/documentCapture/ocrBlocks.ts").read_text(encoding="utf-8")
    # Stesso marcatore dell'editor, riconosciuto dall'export PDF e dalla conversione Word.
    assert 'iu-ted-page-break' in blocchi and 'data-iu-page-break="true"' in blocchi
    assert "block.page !== paginaPrecedente" in blocchi
