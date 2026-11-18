"""Esenzioni dal contributo unificato nella volontaria giurisdizione (art. 10 D.P.R. 115/2002; art. 46-bis disp. att. c.c.).

Dati fittizi. Norme: art. 10, commi 1, 2, 3 e 6, e art. 30 D.P.R. 115/2002; art. 46 e 46-bis disp. att. c.c.;
circolare DAG del 16/05/2024 sulle istanze al giudice tutelare ex artt. 320 e 374 c.c.
"""

from __future__ import annotations

from pct.contributo_dovuto import VOLONTARIA, confronta, contributo_dovuto
from pct.contributo_esenzioni import DOVUTA, NON_DOVUTA, confronto_esente, descrizione_codice, esenzione_volontaria
from pct.contributo_unificato_stato import stato_contributo

ISTANZA_320 = ("ILL.MO GIUDICE TUTELARE DEL TRIBUNALE DI ALFA. I sottoscritti Mario Rossi e Anna Bianchi, genitori esercenti "
               "la responsabilità genitoriale sul figlio minore Luca Rossi, chiedono l'autorizzazione ex art. 320 c.c. a "
               "riscuotere la somma spettante al minore. Si dichiara che il procedimento è esente dal contributo unificato "
               "ai sensi dell'art. 10 D.P.R. 115/2002.")


def test_minore_art_320_esente_e_anticipazione_dovuta():
    esenzione = esenzione_volontaria(codice_oggetto="413001", descrizione=descrizione_codice("413001"), testi=[ISTANZA_320])
    assert esenzione and esenzione.norma == "art. 10, comma 2, D.P.R. 115/2002" and esenzione.anticipazione == DOVUTA
    assert esenzione.dichiarazione is True
    confronto = confronto_esente(esenzione, [27.0])
    assert confronto["esito"] == "esente_per_legge" and not confronto["dubbio"]
    assert "anticipazione forfettaria dovuta (art. 30 D.P.R. 115/2002), corretto" in confronto["dettaglio"]


def test_minore_senza_dichiarazione_di_esenzione_e_dubbio_vero():
    senza = ISTANZA_320.split(" Si dichiara")[0]
    esenzione = esenzione_volontaria(codice_oggetto="413999", testi=[senza])  # voce generica: decide il testo
    assert esenzione and esenzione.norma == "art. 10, comma 2, D.P.R. 115/2002" and esenzione.dichiarazione is False
    confronto = confronto_esente(esenzione, [27.0])
    assert "art. 10, comma 6" in confronto["dubbio"]


def test_istanza_incidentale_nella_tutela_aperta_senza_anticipazione():
    testo = ("Al Giudice tutelare. Il tutore del minore Gino Verdi, nominato nella tutela n. 12/2024, chiede "
             "l'autorizzazione ex art. 374 c.c. alla vendita del motociclo del minore.")
    esenzione = esenzione_volontaria(codice_oggetto="413014", testi=[testo])
    assert esenzione.norma.startswith("art. 10, comma 1") and esenzione.anticipazione == NON_DOVUTA
    generica = esenzione_volontaria(codice_oggetto="413999", testi=[testo])
    assert generica.anticipazione == NON_DOVUTA
    assert "non erano dovuti" in confronto_esente(esenzione, [27.0])["dettaglio"]


def test_apertura_della_tutela_e_amministrazione_di_sostegno():
    tutela = esenzione_volontaria(codice_oggetto="413010")
    assert tutela.norma.startswith("art. 10, comma 1") and tutela.anticipazione == DOVUTA
    sostegno = esenzione_volontaria(codice_oggetto="413061")
    assert "46-bis" in sostegno.norma and sostegno.anticipazione == DOVUTA
    assert esenzione_volontaria(codice_oggetto="412601").norma == sostegno.norma
    assert esenzione_volontaria(codice_oggetto="400220").norma == "art. 10, comma 3, D.P.R. 115/2002"


def test_volontaria_non_esente_resta_98_euro():
    assert esenzione_volontaria(codice_oggetto="420300", descrizione=descrizione_codice("420300"),
                                testi=["Ricorso per l'accettazione dell'eredità con beneficio d'inventario di Carlo Neri"]) is None
    dovuto = contributo_dovuto(VOLONTARIA, None)
    assert dovuto.importo == 98.0 and confronta([27.0], dovuto, cat=VOLONTARIA)["esito"] == "insufficiente"


def test_stato_unico_del_contributo_esente_con_la_ricevuta_dell_anticipazione():
    esenzione = esenzione_volontaria(codice_oggetto="413001", testi=[ISTANZA_320])
    voce = {"status": "pagato", "importo": 27.0, "importiLetti": [27.0], "confronto": confronto_esente(esenzione, [27.0])}
    documenti = [{"id": "D1", "nome": "ricevuta_pagopa.pdf", "etichetta": "Contributo unificato / pagamento", "confermato": True}]
    stato = stato_contributo(voce, documenti)
    assert stato["codice"] == "esente" and stato["norma"] == "art. 10, comma 2, D.P.R. 115/2002"
    assert stato["ruoloFonti"].startswith("ricevuta dell'anticipazione forfettaria")


def test_genitori_per_il_figlio_minore_con_codice_della_tutela_restano_art_320():
    # Caso reale anonimizzato: istanza dei genitori iscritta con il codice 413014 (autorizzazioni nella tutela).
    testo = ("Giudice Tutelare. I sottoscritti Tizio e Caia, nella qualità di Genitori esercenti la potestà sul minore Sempronio, "
             "CHIEDONO di essere autorizzati a compiere gli atti in nome e per conto del minore. Allegati: ricevuta di "
             "versamento con PagoPA di diritti di cancelleria per €27,00")
    esenzione = esenzione_volontaria(codice_oggetto="413014", testi=[testo])
    assert esenzione.norma == "art. 10, comma 2, D.P.R. 115/2002" and esenzione.anticipazione == DOVUTA
    confronto = confronto_esente(esenzione, [27.0])
    assert "corretto" in confronto["dettaglio"] and "art. 10, comma 6" in confronto["dubbio"]
