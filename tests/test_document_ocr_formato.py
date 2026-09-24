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
        assert set(formato) == {"livello", "grassetto", "corsivo", "allineamento", "scala", "colore", "famiglia", "corpo", "sottolineato", "barrato"}
        assert formato["allineamento"] in {ALLINEAMENTO_SINISTRA, ALLINEAMENTO_CENTRO, ALLINEAMENTO_DESTRA}
        # il colore c'e' sempre come chiave, ed e' vuoto quando e' il nero del
        # documento: e' la differenza fra «non dichiarato» e «nero dichiarato»
        assert isinstance(formato["colore"], str)


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

    blocchi = (Path(__file__).resolve().parents[1] / "frontend/src/components/documentCapture/ocrHtml.ts").read_text(encoding="utf-8")
    # Stesso marcatore dell'editor, riconosciuto dall'export PDF e dalla conversione Word.
    assert 'iu-ted-page-break' in blocchi and 'data-iu-page-break="true"' in blocchi
    assert "block.page !== paginaPrecedente" in blocchi


def test_il_colore_si_dichiara_solo_quando_e_un_colore():
    """Il nero di un atto non e' un colore: e' l'assenza di colore.

    Dichiararlo vorrebbe dire scrivere «color:#000000» su ogni capoverso del
    documento — non aggiunge niente e poi qualcuno deve toglierlo. Ma un blu
    pieno lo e', ed e' proprio quello che la prima versione di questa regola
    scartava: guardava il canale piu' alto invece del piu' basso, e un
    indirizzo PEC in blu (rosso a zero, blu a 255) finiva buttato via insieme
    allo sfondo della carta.
    """
    from legal_ocr.formato import _colore_leggibile

    # colori veri, di quelli che si trovano davvero in un atto
    assert _colore_leggibile(0, 0, 255) == "#0000ff"        # il collegamento PEC
    assert _colore_leggibile(0x1f, 0x57, 0xa4) == "#1f57a4"  # la carta intestata
    assert _colore_leggibile(0xcc, 0, 0) == "#cc0000"        # un richiamo in rosso

    # non colori: il testo dell'atto e la carta sotto
    assert _colore_leggibile(0, 0, 0) == ""
    assert _colore_leggibile(20, 22, 21) == ""
    assert _colore_leggibile(245, 246, 250) == ""


def test_il_colore_del_blocco_e_quello_della_maggioranza():
    """Una parola azzurra in mezzo a venti nere non fa un blocco azzurro."""
    from legal_ocr.formato import _colore

    nere = [{"colore": ""} for _ in range(8)]
    assert _colore([*nere, {"colore": "#1f57a4"}]) == ""

    azzurre = [{"colore": "#1f57a4"} for _ in range(5)]
    assert _colore([*azzurre, {"colore": ""}]) == "#1f57a4"
    assert _colore([]) == ""


def test_il_colore_dichiarato_dal_pdf_passa_dallo_stesso_vaglio():
    """PyMuPDF consegna il colore come numero: stesse regole del misurato."""
    from web.services.document_ocr_documento import _colore_span

    assert _colore_span({"color": 0x1F57A4}) == "#1f57a4"
    assert _colore_span({"color": 0x0000FF}) == "#0000ff"
    assert _colore_span({"color": 0}) == ""
    assert _colore_span({}) == ""
    assert _colore_span({"color": "non un numero"}) == ""


def test_il_colore_si_misura_sull_inchiostro_non_sulla_carta():
    """Su una scansione il colore va guardato, e la carta non va nella media."""
    from PIL import Image

    from legal_ocr.formato import colori_parole

    # una parola azzurra su fondo bianco: il bianco intorno non deve stingere
    immagine = Image.new("RGB", (60, 20), (255, 255, 255))
    for x in range(10, 50):
        for y in range(5, 15):
            immagine.putpixel((x, y), (31, 87, 164))

    parole = [{"left": 10, "top": 5, "width": 40, "height": 10}]
    colori_parole(immagine, parole)
    assert parole[0].get("colore") == "#1f57a4"

    # testo nero: niente da dichiarare
    nera = Image.new("RGB", (60, 20), (255, 255, 255))
    for x in range(10, 50):
        for y in range(5, 15):
            nera.putpixel((x, y), (17, 17, 17))
    parole_nere = [{"left": 10, "top": 5, "width": 40, "height": 10}]
    colori_parole(nera, parole_nere)
    assert "colore" not in parole_nere[0]


def test_carattere_e_corpo_arrivano_solo_se_il_documento_li_dichiara():
    """Da una scansione il carattere non si legge: un Garamond inventato e' peggio di niente."""
    stimate = _pagina(_riga(CORPO, 100, 100, riga=1, blocco=1), _riga(CORPO, 100, 140, riga=2, blocco=1))
    formato = _blocchi(stimate)[0]["formato"]
    assert formato["famiglia"] == "" and formato["corpo"] == 0.0

    dichiarate = _pagina(
        _riga(CORPO, 100, 100, riga=1, blocco=1, corpo=12.0, famiglia="Book Antiqua"),
        _riga(CORPO, 100, 140, riga=2, blocco=1, corpo=12.0, famiglia="Book Antiqua"),
    )
    formato = _blocchi(dichiarate)[0]["formato"]
    assert formato["famiglia"] == "Book Antiqua" and formato["corpo"] == 12.0


def test_il_carattere_del_blocco_e_quello_della_maggioranza_e_il_corpo_va_al_mezzo_punto():
    """Una sigla in Arial dentro un capoverso in Times non cambia il capoverso."""
    from legal_ocr.formato import _corpo, _famiglia

    times = [{"famiglia": "Times New Roman"} for _ in range(6)]
    assert _famiglia([*times, {"famiglia": "Arial"}]) == "Times New Roman"
    assert _famiglia([{"famiglia": ""}, {"famiglia": ""}, {"famiglia": "Arial"}]) == ""
    # Word scrive i corpi al mezzo punto: 11,96 dichiarato e' un 12
    assert _corpo([11.96, 12.02, 11.98]) == 12.0
    assert _corpo([10.4]) == 10.5
    assert _corpo([]) == 0.0


def test_il_nome_del_font_nel_pdf_diventa_una_famiglia_dell_editor():
    """Stessa corrispondenza dell'importazione fedele: stesso PDF, stesso carattere."""
    from web.services.document_ocr_documento import _famiglia_span

    assert _famiglia_span({"font": "ABCDEF+TimesNewRomanPS-BoldMT"}) == "Times New Roman"
    assert _famiglia_span({"font": "BookAntiqua,Bold"}) == "Book Antiqua"
    assert _famiglia_span({"font": ""}) == ""
    assert _famiglia_span({}) == ""


def test_sottolineato_e_barrato_si_dichiarano_solo_se_misurati():
    """Dall'immagine non si misurano: il blocco li dichiara solo se le parole li portano."""
    stimate = _pagina(_riga(CORPO, 100, 100, riga=1, blocco=1))
    formato = _blocchi(stimate)[0]["formato"]
    assert formato["sottolineato"] is False and formato["barrato"] is False

    misurate = _pagina(_riga(CORPO, 100, 100, riga=1, blocco=1, sottolineato=True, barrato=False))
    formato = _blocchi(misurate)[0]["formato"]
    assert formato["sottolineato"] is True and formato["barrato"] is False


# ── I tratti: il formato dentro la riga ────────────────────────────────────


def _p(testo, indice, **stile):
    return {"text": testo, "word": indice, **stile}


def test_i_tratti_ridanno_il_testo_e_segnano_dove_cambia_il_formato():
    from legal_ocr.tratti import tratti_del_testo

    parole = [_p("Il", 1), _p("Tribunale", 2), _p("rigetta", 3, grassetto=True, sottolineato=True), _p("la", 4), _p("domanda", 5, colore="#0000ff")]
    tratti = tratti_del_testo("Il Tribunale rigetta la domanda", parole)
    assert "".join(tratto["testo"] for tratto in tratti) == "Il Tribunale rigetta la domanda"
    assert [(tratto["testo"], tratto["grassetto"], tratto["sottolineato"], tratto["colore"]) for tratto in tratti] == [
        ("Il Tribunale ", False, False, ""),
        ("rigetta", True, True, ""),
        # lo spazio dopo una parola sottolineata non e' sottolineato
        (" la ", False, False, ""),
        ("domanda", False, False, "#0000ff"),
    ]


def test_un_formato_uniforme_non_fa_tratti():
    """Basta il formato del blocco: il documento non si riempie di etichette inutili."""
    from legal_ocr.tratti import tratti_del_testo

    assert tratti_del_testo("tutto uguale qui", [_p("tutto", 1), _p("uguale", 2), _p("qui", 3)]) == []
    assert tratti_del_testo("", [_p("x", 1)]) == [] and tratti_del_testo("x", []) == []


def test_i_tratti_seguono_le_parole_anche_dopo_una_correzione_forense():
    """«art . 183» diventato «art. 183»: le parole si riabbinano per contenuto."""
    from legal_ocr.tratti import tratti_del_testo

    parole = [_p("art", 1), _p(".", 2), _p("183", 3, corsivo=True), _p("c.p.c.", 4, corsivo=True), _p("rigetta", 5, grassetto=True)]
    tratti = tratti_del_testo("art. 183 c.p.c. rigetta", parole)
    assert [(tratto["testo"], tratto["corsivo"], tratto["grassetto"]) for tratto in tratti] == [
        ("art. ", False, False),
        ("183 c.p.c.", True, False),
        (" ", False, False),
        ("rigetta", False, True),
    ]


def test_le_tabelle_non_hanno_tratti():
    from legal_ocr.tratti import con_tratti

    blocchi = [{"tipo": "tabella", "riquadro": [0, 0, 100, 100], "righe": [["a"]]}]
    assert "tratti" not in con_tratti(blocchi, [_p("a", 1, grassetto=True, left=10, top=10, width=5, height=5)])[0]
