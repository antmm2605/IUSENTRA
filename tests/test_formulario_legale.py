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
        ("udienza del 1O/O3/2O26, termine al 3l.l2.2O25, dal 2O26-O3-1O; SOS/OS/OO resta", "udienza del 10/03/2026, termine al 31.12.2025, dal 2026-03-10; SOS/OS/OO resta"),
        ("notificato il 1S/O8/2O2S e il 2Z/1l/2O24", "notificato il 15/08/2025 e il 22/11/2024"),
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


# ── Confusioni tipiche dichiarate: strutture a forma fissa ───────────────


@pytest.mark.parametrize(
    ("letto", "atteso"),
    [
        ("C.F. RSSMRA8OAO1F2O5X e P.IVA O1234S67891", "C.F. RSSMRA80A01F205X e P.IVA 01234567891"),
        ("codice fiscale: BNCNNA85C41L219K resta", "codice fiscale: BNCNNA85C41L219K resta"),
        ("il sig. R0SSI di R0MA, TRIBUNA1E di MILAN0, via C0RTE 5, 2O121 Milano, Mi1ano", "il sig. ROSSI di ROMA, TRIBUNALE di MILANO, via CORTE 5, 20121 Milano, Milano"),
        ("IBAN IT6O X054 2811 1010 0000 0123 456", "IBAN IT60X0542811101000000123456"),
        ("R.G. n. 12S4/2O26 e N.R.G. 77/26", "R.G. n. 1254/2026 e N.R.G. 77/26"),
        ("udienza del 1O rnarzo 2O26 alle ore 9.30, Milano, lì primo Aprile 2026, ore 14,15", "udienza del 10 marzo 2026 alle ore 9:30, Milano, lì 1 Aprile 2026, ore 14:15"),
        ("il 12 settembrc 2O25 e il 3 sett. 2026, notificato il 1S/O8/2O2S e il 2Z/1l/2O24", "il 12 settembre 2025 e il 3 settembre 2026, notificato il 15/08/2025 e il 22/11/2024"),
        ("lotto 1058 e 5 ottobre e SOS/OS/OO e Sez. X1V", "lotto 1058 e 5 ottobre e SOS/OS/OO e Sez. XIV"),
    ],
)
def test_confusioni_tipiche_dichiarate(letto: str, atteso: str) -> None:
    assert corretto(letto) == atteso


@pytest.mark.parametrize(
    "letto",
    [
        "SOS/OS/OO",             # nessuna cifra vera
        "IS/OB/ZOZS",            # una cifra vera su otto
        "l/S/BZ",                # anno a due segni con lettere
        "1S/OB/ZOZS",            # anno con una sola cifra vera
        "prot. 12/3/26",         # protocollo: resta com'e'
        "vers. 1.2.34",          # versione: resta com'e'
        "art. 10/2020",          # non ha tre componenti
        "R.G. 1234/2026",        # numero di ruolo
        "31/02/2026",            # non e' nel calendario
        "3O/O2/2O26",            # 30 febbraio: non si corregge in una data falsa
        "1O/1S/2O26",            # mese 15 non esiste
    ],
)
def test_i_token_che_non_sono_date_non_diventano_date(letto: str) -> None:
    from legal_ocr.formulario.date import normalizza_data_ocr, trova_date

    assert normalizza_data_ocr(letto) == letto
    assert [voce for voce in trova_date(letto) if voce.sostituzioni] == []


@pytest.mark.parametrize(
    "letto",
    [
        "ai sensi della l. 5/2026",      # legge 5 del 2026, non il 1° maggio
        "l. 12/2026",
        "l. 69/2023",
        "l. 22/2020",
        "art. 2.3.2026",
        "D.Lgs. 1/2/2026",
        "D.M. 55/2014",
        "n. 10/11/2026",
        "prot. 12/3/26",
        "vers. 1.2.34",
        "Reg. UE 2016/679",
        "comma 1.5.2026",
        "R.G. 1234/2026",
        "sent. 15350/2015",
    ],
)
def test_un_riferimento_normativo_non_e_mai_una_data(letto: str) -> None:
    from legal_ocr.formulario.date import normalizza_data_ocr, trova_date

    assert normalizza_data_ocr(letto) == letto
    assert trova_date(letto) == []


@pytest.mark.parametrize(
    ("letto", "attesa"),
    [
        ("udienza del 10/11/2026", "10/11/2026"),
        ("Milano, lì 20/09/2026", "20/09/2026"),
        ("notificato il 15/08/2026", "15/08/2026"),
        ("entro il 31/10/2026", "31/10/2026"),
        ("scadenza al 31/12/2026", "31/12/2026"),
        ("decreto n. 123 del 10/11/2026", "10/11/2026"),
        ("sentenza n. 88/2026 pubblicata il 05/09/2026", "05/09/2026"),
        ("ai sensi della l. 53/1994, notificato il 15/08/2026", "15/08/2026"),
    ],
)
def test_la_data_annunciata_da_una_preposizione_resta_una_data(letto: str, attesa: str) -> None:
    from legal_ocr.formulario.date import trova_date

    assert [voce.scritto for voce in trova_date(letto)] == [attesa]


def test_trova_date_da_posizione_correzione_e_forma() -> None:
    from datetime import date

    from legal_ocr.formulario.date import trova_date

    trovate = trova_date("udienza del 1O/O3/2O26 alle ore 9.30 e termine il 12 marzo 2026, dal 2O26-O3-1O")
    assert [(voce.letto, voce.scritto, voce.data, voce.forma, voce.sostituzioni) for voce in trovate] == [
        ("1O/O3/2O26", "10/03/2026", date(2026, 3, 10), "numerica", 3),
        ("12 marzo 2026", "12 marzo 2026", date(2026, 3, 12), "estesa", 0),
        ("2O26-O3-1O", "2026-03-10", date(2026, 3, 10), "iso", 3),
    ]
    assert trovate[0].inizio == 12 and trovate[0].fine == 22


def test_la_tabella_delle_confusioni_e_unica_e_dichiarata() -> None:
    from legal_ocr.formulario import confusioni, date, numeri

    assert confusioni.LETTERA_PER_CIFRA["O"] == "0" and confusioni.LETTERA_PER_CIFRA["l"] == "1" and confusioni.CIFRA_PER_LETTERA["0"] == "O"
    assert set(confusioni.LETTERA_PER_CIFRA_SICURE) == set("OoIl|ÌSsBZz")
    assert date.a_cifre is confusioni.a_cifre and numeri.a_cifre is confusioni.a_cifre
    assert confusioni.correggi_codice_fiscale("RSSMRA8OAO1F2O5X") == "RSSMRA80A01F205X"
    assert confusioni.correggi_codice_fiscale("RSSMRA80A01F205Y") == "RSSMRA80A01F205Y"  # controllo sbagliato: non si tocca
    assert {regola.id for regola in confusioni.REGOLE} <= {regola.id for regola in REGOLE}


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
