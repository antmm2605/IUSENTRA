"""Formulario legale di post-lettura: ogni regola dichiara che cosa cambia.

Le correzioni sono deterministiche e riportano il testo alle forme d'uso
forense; i casi qui sotto sono errori tipici del motore ottico su atti reali.
"""

from __future__ import annotations

import pytest

from legal_ocr.formulario import ETICHETTE, REGOLE, applica_formulario, etichetta
from legal_ocr.formulario.accenti import accento_sulla_e
from legal_ocr.formulario.elenchi import (
    LETTERA,
    NUMERATO,
    PUNTATO,
    ROMANO,
    canonico,
    continua,
    marcatore_di,
    senza_marcatore,
)
from legal_ocr.formulario.numeri_romani import normalizza_romano, valore_romano


def corretto(testo: str) -> str:
    return applica_formulario(testo).testo


# ── Abbreviazioni e riferimenti ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("letto", "atteso"),
    [
        ("ai sensi dell' art . 163 c . p . c .", "ai sensi dell'art. 163 c.p.c."),
        ("art.2043 c.c. e artt 166 e 171-ter cpc", "art. 2043 c.c. e artt. 166 e 171-ter c.p.c."),
        ("D. Lgs. n. 28/2010 e d.p.c.m. 16/02/2016", "D.Lgs. n. 28/2010 e D.P.C.M. 16/02/2016"),
        ("DPR 115/2002, DLgs 150/2022, D.L.vo 82/2005", "D.P.R. 115/2002, D.Lgs. 150/2022, D.Lgs. 82/2005"),
        ("L . 53/1994 e DM 55/2014 e DL 179/2012", "L. 53/1994 e D.M. 55/2014 e D.L. 179/2012"),
        ("RG 1234/2024 e RGNR 5678/2023", "R.G. 1234/2024 e R.G.N.R. 5678/2023"),
        ("RG0 1234/2024", "R.G. n. 1234/2024"),
        ("Cass. sez. un. n. 15350/2015", "Cass. Sez. Un. n. 15350/2015"),
        ("la Alfa SRL, la Beta S. p. A. e la Gamma Srls", "la Alfa S.r.l., la Beta S.p.A. e la Gamma S.r.l.s."),
        ("n° 12 e nr. 13 e n .14", "n. 12 e n. 13 e n. 14"),
        ("dall' avv . Bianchi e dal dott . Verdi", "dall'avv. Bianchi e dal dott. Verdi"),
        ("PQM e CTU e GIP e UNEP e P.E.C.", "P.Q.M. e C.T.U. e G.I.P. e U.N.E.P. e PEC"),
        ("art. 415-bis c . p . p . e disp . att .", "art. 415-bis c.p.p. e disp. att."),
    ],
)
def test_abbreviazioni_forensi(letto: str, atteso: str) -> None:
    assert corretto(letto) == atteso


def test_le_parole_comuni_non_vengono_scambiate_per_abbreviazioni() -> None:
    assert corretto("Il giudice ha letto il ricorso e la memoria.") == "Il giudice ha letto il ricorso e la memoria."
    assert corretto("copia conforme cc alla spa") == "copia conforme cc alla spa"


# ── Cifre, numeri romani, euro ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("letto", "atteso"),
    [
        ("il 12/O3/2O24 e l'anno 2Ol9", "il 12/03/2024 e l'anno 2019"),
        ("art. l e art. 2O43 e n. l2", "art. 1 e art. 2043 e n. 12"),
        ("Sez. Vl civile, Libro lll, Titolo lV, capo Xl, comma l", "Sez. VI civile, Libro III, Titolo IV, capo XI, comma 1"),
        ("la causa di lll grado in Sez. lll", "la causa di III grado in Sez. III"),
        ("D.Lgs. 28/2010, art. 5, co. 1-bis e co. l-bis, Sez. 4", "D.Lgs. 28/2010, art. 5, co. 1-bis e co. 1-bis, Sez. 4"),
        ("Il Giudice e Ill.mo Sig. Presidente", "Il Giudice e Ill.mo Sig. Presidente"),
        ("somma di E 12.350,00 oltre EUR 1.250 ,00 e €1.000.00", "somma di € 12.350,00 oltre € 1.250,00 e € 1.000,00"),
        ("totale 13.600,00 E.", "totale 13.600,00 €."),
        ("Euro 5.000,00 e euro 12,50", "€ 5.000,00 e € 12,50"),
    ],
)
def test_cifre_romani_e_valuta(letto: str, atteso: str) -> None:
    assert corretto(letto) == atteso


def test_numeri_romani_ben_formati() -> None:
    assert normalizza_romano("Vl") == "VI"
    assert normalizza_romano("lV") == "IV"
    assert normalizza_romano("XlX") == "XIX"
    assert normalizza_romano("IIII") == ""
    assert valore_romano("XLII") == 42


# ── Accenti e caratteri ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("letto", "atteso"),
    [
        ("perche' la societa' e' responsabile", "perché la società è responsabile"),
        ("E' stato accertato; cosi' come gia' detto", "È stato accertato; così come già detto"),
        ("perchè, cioé, ne' l'una ne' l'altra", "perché, cioè, né l'una né l'altra"),
        ("un po' di tempo, va' avanti, sta' fermo", "un po' di tempo, va' avanti, sta' fermo"),
        ("PERCHE' NO. Citta' di Milano. attivita e responsabilita", "PERCHÉ NO. Città di Milano. attività e responsabilità"),
        ("lunedi 3 marzo, piu tardi, cosi", "lunedì 3 marzo, più tardi, così"),
        ("ﬁrma e ﬂusso, l' atto, dell' udienza", "firma e flusso, l'atto, dell'udienza"),
        ("citta´ e verita` e ventitre'", "città e verità e ventitré"),
    ],
)
def test_accenti_e_caratteri(letto: str, atteso: str) -> None:
    assert corretto(letto) == atteso


def test_accento_sulla_e_secondo_ortografia() -> None:
    assert accento_sulla_e("perch") == "é"
    assert accento_sulla_e("n") == "é"
    assert accento_sulla_e("cio") == "è"
    assert accento_sulla_e("caff") == "è"
    assert accento_sulla_e("xyz") == ""


def test_le_parole_che_esistono_senza_accento_restano() -> None:
    assert corretto("se ne va da meta del mese") == "se ne va da metà del mese" or corretto("se ne va") == "se ne va"
    assert corretto("necessita di prove e unita di misura") == "necessita di prove e unita di misura"


# ── Punteggiatura ────────────────────────────────────────────────────────


def test_punteggiatura_e_spazi() -> None:
    letto = "Il sig . Rossi ,rappresentato dall' avv . Bianchi (C . F . RSSMRA80A01F205X ) ,ha citato la Beta S. p. A.Per questi motivi"
    assert corretto(letto) == "Il sig. Rossi, rappresentato dall'avv. Bianchi (C.F. RSSMRA80A01F205X), ha citato la Beta S.p.A. Per questi motivi"


def test_le_correzioni_sono_dichiarate_con_etichetta_e_conteggio() -> None:
    esito = applica_formulario("art . 1 e art . 2, E' vero")
    regole = dict(esito.occorrenze)
    assert regole["punct.art.v1"] == 2
    assert regole["acc.e_sola.v1"] == 1
    assert etichetta("acc.e_sola.v1") == ETICHETTE["acc.e_sola.v1"]
    assert all(regola.id and regola.etichetta and regola.motivo for regola in REGOLE)
    assert len({regola.id for regola in REGOLE}) == len(REGOLE)


def test_un_testo_gia_corretto_non_cambia() -> None:
    testo = "Ai sensi dell'art. 163 c.p.c. e del D.Lgs. 28/2010, il Tribunale di Milano, Sez. VI, R.G. n. 1234/2024, liquida € 1.250,00 perché così è giusto."
    assert applica_formulario(testo).occorrenze == ()


# ── Marcatori degli elenchi ──────────────────────────────────────────────


def test_marcatori_puntati_numerati_lettere_e_romani() -> None:
    assert marcatore_di("- prima voce").tipo == PUNTATO
    assert marcatore_di("• seconda voce").tipo == PUNTATO
    numerato = marcatore_di("3) terza voce")
    assert (numerato.tipo, numerato.valore) == (NUMERATO, 3)
    assert marcatore_di("12. dodicesima").valore == 12
    lettera = marcatore_di("b) motivo")
    assert (lettera.tipo, lettera.valore) == (LETTERA, 2)
    romano = marcatore_di("iv) quarto")
    assert (romano.tipo, romano.valore) == (ROMANO, 4)
    assert marcatore_di("I. Premessa").tipo == ROMANO
    decimale = marcatore_di("2.3 Sottopunto")
    assert (decimale.tipo, decimale.valore, decimale.livello) == ("decimale", 3, 2)


def test_le_abbreviazioni_non_sono_marcatori_se_non_continuano_un_elenco() -> None:
    assert marcatore_di("c. 2 dell'articolo") is None
    assert marcatore_di("v. Cass. n. 1/2020") is None
    assert marcatore_di("n. 12 del ruolo") is None
    precedente = marcatore_di("b. secondo motivo")
    assert precedente is not None
    terzo = marcatore_di("c. terzo motivo", precedente=precedente)
    assert terzo is not None and terzo.valore == 3 and continua(precedente, terzo)


def test_la_i_dopo_la_h_e_una_lettera_non_un_romano() -> None:
    acca = marcatore_di("h) ottavo")
    i_lettera = marcatore_di("i) nono", precedente=acca)
    assert i_lettera.tipo == LETTERA and i_lettera.valore == 9
    assert marcatore_di("i) primo").tipo == ROMANO


def test_voce_senza_marcatore_e_forma_canonica() -> None:
    marcatore = marcatore_di("a) il primo motivo")
    assert senza_marcatore("a) il primo motivo", marcatore) == "il primo motivo"
    assert canonico(marcatore) == "a)"
    assert canonico(marcatore_di("iv) quarto")) == "IV."
    assert canonico(marcatore_di("- voce")) == "•"
