"""Linguaggio legale delle voci d'agenda scritte dal software (pct/agenda_linguaggio.py)."""

from pct.agenda_linguaggio import evento_registro, modalita_legale, nome_proprio, titolo_cancelleria


def test_eventi_del_registro_senza_ripetizioni():
    assert evento_registro("RIGETTO ISTANZA", "ISTANZA RIGETTATA") == "rigetto dell'istanza"
    assert evento_registro("DEPOSITO ISTANZE GENERICHE", "DEPOSITATE ISTANZE GENERICHE") == "deposito di istanza"
    assert evento_registro("ANNOTAZIONE", "inserita annotazione (oggetto: verbale di udienza)").startswith("annotazione di cancelleria: ")


def test_modalita_d_udienza_in_italiano_con_la_norma():
    assert modalita_legale("note_scritte") == "cartolare con note scritte ex art. 127-ter c.p.c."
    assert modalita_legale("videoconferenza") == "da remoto (art. 127-bis c.p.c.)"


def test_titolo_con_rg_e_ufficio():
    assert nome_proprio("MINISTERO DELL'ISTRUZIONE E DEL MERITO") == "Ministero dell'Istruzione e del Merito"
    assert titolo_cancelleria("rigetto dell'istanza", rg="1263/2026", ufficio="TRIBUNALE DI BRESCIA") == (
        "Comunicazione di cancelleria: rigetto dell'istanza – RG 1263/2026 – Tribunale di Brescia")


def test_riga_di_contesto_sotto_il_titolo():
    from pct.agenda_linguaggio import riga_contesto

    assert riga_contesto(client="GRAMUGLIA CATERINA", numero_fascicolo="2026/327", rg="RG 901/2026",
                         ufficio="Tribunale di Vicenza") == "Gramuglia Caterina · Fascicolo 2026/327 · RG 901/2026 · Tribunale di Vicenza"
    assert riga_contesto(rg="901/2026") == "RG 901/2026"


def test_titoli_storici_in_linguaggio_legale_solo_in_lettura():
    from pct.agenda_linguaggio import titolo_storico

    assert titolo_storico("PEC ricevuta: udienza revocata: note scritte entro il 24/11/2026 ore 09:30 - RG 3384/2025") == (
        "Comunicazione di cancelleria: udienza sostituita da note scritte (art. 127-ter c.p.c.), termine al 24/11/2026 ore 09:30")
    assert titolo_storico("PEC ricevuta: designazione del giudice COPPOLA LUCA - RG 3128/2026") == (
        "Comunicazione di cancelleria: designazione del giudice dott. Coppola Luca")
    assert titolo_storico("PEC ricevuta: iscrizione ruolo generale: iscritto a ruolo generale - RG 2691/2026") == (
        "Comunicazione di cancelleria: iscrizione della causa a ruolo")
    assert titolo_storico("Udienza da comunicazione di cancelleria - RG 792/2025") == "Udienza"
    assert titolo_storico("Udienza di discussione") == "Udienza di discussione"


def test_deposito_di_atto_senza_ripetizioni_e_con_il_nome_intero():
    from pct.agenda_linguaggio import titolo_storico

    assert titolo_storico("PEC ricevuta: deposito atto non codificato: DEPOSITATO ATTO ricorso notificato DA PARTE DI avv. "
                          "Montagnese Giuseppe - RG 2477/2026") == (
        "Comunicazione di cancelleria: deposito di atto: ricorso notificato da parte di avv. Montagnese Giuseppe")


def test_titolo_troncato_ricostruito_dalla_descrizione_completa():
    from pct.agenda_linguaggio import titolo_storico

    assert titolo_storico("PEC ricevuta: deposito atto non codificato: depositato atto ricorso notificato da parte di avv. montagne - RG 2477/2026",
                          "DEPOSITATO ATTO ricorso notificato DA PARTE DI avv. Montagnese Giuseppe") == (
        "Comunicazione di cancelleria: deposito di atto: ricorso notificato da parte di avv. Montagnese Giuseppe")
