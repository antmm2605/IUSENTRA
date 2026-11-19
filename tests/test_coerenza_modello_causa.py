"""Collaudo a vista del 19/11/2026: il modello della causa ragiona come un avvocato su definizione, notifica e parti.

Dati fittizi equivalenti ai fascicoli reali A8B49265 (Locri, lavoro), 0BAABCE0 (Vicenza, lavoro) e 82A8E2BD
(Giudice di pace, monitorio). Norme: artt. 14, 115, 156, 168, 279 c.p.c.; art. 36 disp. att. c.p.c.; art. 1 R.D.
1611/1933; artt. 13, comma 6, e 14, comma 2, D.P.R. 115/2002.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from pct.definizione_riconvalida import (
    definizione_automatica, e_automatica, fonte_citata, nota_riconvalida, verifica_definizione,
)
from pct.ragionamento import ragiona
from pct.ragionamento.parti import dichiarazione_di_valore, etichetta_valore
from tests.test_ragionamento_casi_collaudo import (
    DECRETO_415, DI, LAVORO, MONITORIO, RICORSO_DI, RICORSO_LAVORO, conclusione, doc, fonti, norme_di,
)

COMPARSA = doc("CMP", "CT 1762 2026 COMPARSA M.I.M..pdf.p7m", "atto_difensivo", "Comparsa di costituzione e risposta",
               "AVVOCATURA DISTRETTUALE DELLO STATO DI VENEZIA TRIBUNALE DI VICENZA SEZIONE LAVORO R.G. 1571/2026. Comparsa di "
               "costituzione e risposta nell'interesse del Ministero dell'Istruzione e del Merito, rappresentato e difeso ex lege "
               "dall'Avvocatura Distrettuale dello Stato. Si producono sentenze. Venezia, 30/7/2026 Procuratore dello Stato")
# Il decreto ex art. 127-ter c.p.c. che il catalogo ha preso per «Istanze e conclusioni» (A8B49265, 3298700s.pdf).
RINVIO = doc("RIN", "3298700s.pdf", "atto_difensivo", "Istanze e conclusioni",
             "TRIBUNALE DI VICENZA SEZIONE CIVILE Controversie in materia di lavoro e previdenza N. R.G. 1571/2026 Provvedimento "
             "ex art. 127 ter c.p.c. Il Giudice del lavoro, nella persona del dottor Mario Bianchi, con riferimento al "
             "procedimento in epigrafe; letti gli atti di causa; rinvia all'udienza del 14.4.2027, ore di rito. Manda alla "
             "cancelleria per le comunicazioni. Vicenza, 10/09/2026 Il Giudice Dott. Mario Bianchi *Provvedimento redatto con "
             "Consolle del Magistrato*")
PRECEDENTE = doc("PRE", "Sentenza_Tribunale_Cosenza_08-03-2023.PDF", "provvedimento", "Sentenza",
                 "TRIBUNALE DI COSENZA SEZIONE LAVORO REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO Il Tribunale ha pronunciato la "
                 "seguente SENTENZA nella causa iscritta al n. 2010/2022 R.G. P.Q.M. accoglie il ricorso. Cosenza, 08/03/2023 "
                 "Il Giudice")


# --- punto 2: la costituzione della controparte dimostra che la notifica ha raggiunto lo scopo --------------------

def test_lavoro_comparsa_della_controparte_rende_fatta_la_notifica_415():
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, COMPARSA]))
    obbligo = conclusione(causa, "notifica_ricorso_decreto_415")
    assert obbligo.stato == "fatto" and "si è costituita" in obbligo.prova_o_motivo
    assert "COMPARSA" in obbligo.prova_o_motivo and "art. 156, terzo comma, c.p.c." in norme_di(obbligo)
    assert not obbligo.dubbi and obbligo.termine is None


def test_senza_costituzione_la_notifica_415_resta_da_fare():
    obbligo = conclusione(ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415])), "notifica_ricorso_decreto_415")
    assert obbligo.stato == "da_fare"


def test_comparsa_di_altro_procedimento_non_prova_la_notifica():
    estranea = {**COMPARSA, "id": "CMP2", "etichetta": "Precedente giurisprudenziale", "natura": "precedente_giurisprudenziale"}
    obbligo = conclusione(ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, estranea])), "notifica_ricorso_decreto_415")
    assert obbligo.stato == "da_fare"


def test_ordine_di_notifica_del_giudice_in_ogni_rito_sanato_dalla_costituzione():
    ordinanza = doc("ORD", "ordinanza.pdf", "provvedimento", "Ordinanza",
                    "TRIBUNALE DI PALMI R.G. 77/2026 Il Giudice, letto l'atto di citazione, ORDINA che l'atto di citazione e il presente "
                    "provvedimento siano notificati a cura dell'attore alla parte convenuta entro il 10.12.2026. Palmi, 02/11/2026 Il Giudice")
    citazione = doc("CIT", "Atto di citazione.pdf", "atto_principale", "Atto di citazione",
                    "TRIBUNALE DI PALMI ATTO DI CITAZIONE Il sig. Verdi, rappresentato e difeso dall'Avv. Mario Rossi, cita Beta srl. " * 3)
    comparsa = doc("CMP3", "Comparsa Beta.pdf", "atto_difensivo", "Comparsa di costituzione e risposta",
                   "TRIBUNALE DI PALMI R.G. 77/2026 Comparsa di costituzione e risposta per Beta srl, Avv. Neri. Palmi 05/11/2026 Avv. Neri",
                   "2026-11-05")
    civile = {"numero_rg": "77", "anno_rg": "2026", "codice_oggetto_pst": "140999", "tipo": "CIVILE"}
    senza = [c for c in ragiona(fonti(civile, [citazione, ordinanza])).conclusioni if c.codice == "notifica_ordinata"]
    con = [c for c in ragiona(fonti(civile, [citazione, ordinanza, comparsa])).conclusioni if c.codice == "notifica_ordinata"]
    assert senza and senza[0].stato != "fatto"
    assert con and con[0].stato == "fatto" and "art. 156, terzo comma, c.p.c." in norme_di(con[0])


def test_monitorio_l_opposizione_del_debitore_prova_la_notifica_del_decreto():
    opposizione = doc("OPP", "Opposizione a decreto ingiuntivo.pdf", "atto_principale", "Atto di citazione in opposizione",
                      "GIUDICE DI PACE DI PALMI Beta srl, Avv. Neri, propone opposizione al decreto ingiuntivo n. 1109/2024. Avv. Neri")
    obbligo = conclusione(ragiona(fonti(MONITORIO, [RICORSO_DI, DI, opposizione])), "notifica_decreto_ingiuntivo")
    assert obbligo.stato == "fatto" and "si è costituita" in obbligo.prova_o_motivo
    assert conclusione(ragiona(fonti(MONITORIO, [RICORSO_DI, DI])), "notifica_decreto_ingiuntivo").stato == "da_fare"


def test_provvedimento_scambiato_per_istanza_torna_del_giudice_e_porta_l_udienza():
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, RINVIO]))
    atto = next(a for a in causa.atti if a.id == "RIN")
    assert atto.autore == "giudice" and atto.natura == "provvedimento"
    assert "2027-04-14" in [u.data for u in causa.udienze]
    # un provvedimento non è una costituzione della controparte
    assert conclusione(causa, "notifica_ricorso_decreto_415").stato != "fatto" or "RIN" not in conclusione(
        causa, "notifica_ricorso_decreto_415").prova_o_motivo
    assert next(a for a in ragiona(fonti(LAVORO, [COMPARSA])).atti).autore == "controparte"


# --- punto 1: la sentenza che non è della causa non definisce il fascicolo ----------------------------------------

def _voce(**campi):
    base = {"data": "2026-09-20T08:34:19+02:00", "descrizione": "Sentenza indicizzata da Lex AI: fascicolo definito",
            "stato_precedente": "IN_CORSO", "stato_nuovo": "DEFINITO", "note": "RG n. 1571/2026; Documento: docai-1",
            "avvocato": "Lex AI backfill"}
    return SimpleNamespace(**{**base, **campi})


def test_solo_le_definizioni_automatiche_non_toccate_dall_avvocato():
    automatica = _voce()
    assert e_automatica(automatica) and definizione_automatica("DEFINITO", [automatica]) is automatica
    assert definizione_automatica("IN_CORSO", [automatica]) is None
    decisa = _voce(avvocato="avv.rossi", descrizione="Stato cambiato da IN_CORSO a DEFINITO")
    assert definizione_automatica("DEFINITO", [decisa]) is None
    # l'avvocato ha ritoccato lo stato dopo l'automatismo: la sua decisione prevale
    ritocco = _voce(avvocato="avv.rossi", descrizione="Stato cambiato da DEFINITO a DEFINITO", stato_precedente="DEFINITO")
    assert definizione_automatica("DEFINITO", [automatica, ritocco]) is None
    # una voce automatica successiva che non cambia stato non conta
    rumore = _voce(avvocato="IUSENTRA", descrizione="Riconciliazione documenti", stato_precedente="DEFINITO")
    assert definizione_automatica("DEFINITO", [automatica, rumore]) is automatica
    assert fonte_citata("RG n. 1854/2026; Documento: docai-cc47")["documento"] == "docai-cc47"
    assert fonte_citata("documento «S.pdf», SHA-256 " + "a" * 64 + "; art. 132 c.p.c.")["sha256"] == "a" * 64


def test_precedente_allegato_e_udienza_successiva_annullano_la_definizione():
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, PRECEDENTE, RINVIO])).come_dizionario()
    precedente = next(a for a in causa["atti"] if a["id"] == "PRE")
    assert precedente["appartenenza"] == "contorno"
    esito = verifica_definizione(causa, _voce(), ["PRE"])
    assert esito.revoca and "Sentenza_Tribunale_Cosenza" in esito.motivo and "art. 115 c.p.c." in esito.motivo
    solo_udienza = verifica_definizione(causa, _voce(), [])
    assert solo_udienza.revoca and "14/04/2027" in solo_udienza.motivo and "3298700s.pdf" in solo_udienza.motivo
    nota = nota_riconvalida(esito, _voce())
    assert "torna «in corso»" in nota and "art. 279, secondo comma, c.p.c." in nota and "Lex AI backfill" in nota


def test_sentenza_della_causa_senza_udienze_dopo_resta_definita():
    sentenza = doc("SEN", "Sentenza.pdf", "provvedimento", "Sentenza",
                   "TRIBUNALE DI VICENZA R.G. 1571/2026 SENTENZA P.Q.M. accoglie il ricorso. Vicenza, 12/10/2026 Il Giudice")
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, sentenza])).come_dizionario()
    assert not verifica_definizione(causa, _voce(), ["SEN"]).revoca
    # sentenza non definitiva seguita da un'altra udienza: la causa è pendente (art. 279, secondo comma, n. 4)
    rinvio = {**RINVIO, "testo": RINVIO["testo"].replace("10/09/2026", "20/10/2026")}
    pendente = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, sentenza, rinvio])).come_dizionario()
    assert verifica_definizione(pendente, _voce(), ["SEN"]).revoca
    # un'udienza fissata per la correzione dell'errore materiale (artt. 287-288 c.p.c.) non prova la pendenza
    correzione = {**rinvio, "id": "COR", "nome": "Correzione errore materiale.pdf"}
    corretta = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, sentenza, correzione])).come_dizionario()
    assert not verifica_definizione(corretta, _voce(), ["SEN"]).revoca
    # casi reali 7EDBF3E7 e 0E7944A9: il decreto «di fissazione nuova udienza» apre il procedimento di correzione, che
    # nel fascicolo si chiude con l'ordinanza di correzione («Correzzione», con il refuso del nome del file)
    nuova = {**rinvio, "id": "NUO", "nome": "Decreto fissazione nuova udienza.pdf"}
    ordinanza = doc("ORC", "Correzzione errore materiale sentenza.PDF", "provvedimento", "Ordinanza",
                    "TRIBUNALE DI VICENZA R.G. 1571/2026 Il Giudice, rilevato l'errore materiale, corregge. Vicenza, 20/01/2027 Il Giudice")
    con_correzione = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, sentenza, nuova, ordinanza])).come_dizionario()
    assert not verifica_definizione(con_correzione, _voce(), ["SEN"]).revoca


def test_sentenza_citata_anteriore_all_iscrizione_non_definisce():
    # caso reale 256C9F82: «Sentenza n. 1021/2024; RG n. 828/2026»
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO])).come_dizionario()
    voce = _voce(note="Sentenza n. 1021/2024; RG n. 828/2026; Documento: docai-5bb")
    esito = verifica_definizione(causa, voce, [])
    assert esito.revoca and "1021/2024" in esito.motivo and "anteriore" in esito.motivo
    stessa = _voce(note="Sentenza n. 154/2026; RG n. 32/2026; Documento: docai-f40")
    assert not verifica_definizione(causa, stessa, []).revoca


def test_senza_prova_contraria_la_definizione_resta():
    assert not verifica_definizione(ragiona(fonti(LAVORO, [RICORSO_LAVORO])).come_dizionario(), _voce(), []).revoca
    # senza sentenza ma con l'udienza fissata dal decreto ancora futura la causa è pendente
    assert verifica_definizione(ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415])).come_dizionario(), _voce(), []).revoca
    # udienza già passata e fissata prima della definizione: la sentenza può mancare dal fascicolo, nessuna prova contraria
    passata = {**DECRETO_415, "testo": DECRETO_415["testo"].replace("09/02/2027", "09/10/2026").replace("Vicenza, 09/10/2026",
                                                                                                    "Vicenza, 09/06/2026")}
    assert not verifica_definizione(ragiona(fonti(LAVORO, [RICORSO_LAVORO, passata])).come_dizionario(), _voce(), []).revoca


def test_riconvalida_in_sfondo_cambia_solo_lo_stato_automatico(monkeypatch):
    from pct.fascicoli import StatoFascicolo
    from web.services import definizione_riconvalida_runtime as runtime

    chiamate = []
    fascicolo = SimpleNamespace(id="F1", stato=StatoFascicolo.DEFINITO, avanzamento=[_voce()], documenti=[], data_chiusura="2026-09-20")

    class Gestore:
        def get(self, _fid):
            return fascicolo

        def cambia_stato(self, fid, stato, note="", avvocato=""):
            chiamate.append((fid, stato, note, avvocato, fascicolo.data_chiusura))

    monkeypatch.setattr("web.helpers.get_fascicoli", lambda: Gestore())
    from pct.fascicolo_lettura.ragionamento import vista

    # la Lettura salvata porta la vista del modello: la riconvalida legge gli atti e le udienze da lì
    causa = vista(ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, PRECEDENTE, RINVIO])).come_dizionario())
    esito = runtime.riconvalida_definizione("F1", {"ragionamento": causa})
    assert esito["revocata"] and chiamate[0][1] == StatoFascicolo.IN_CORSO
    assert chiamate[0][3] == "riconvalida automatica della definizione" and chiamate[0][4] == ""
    assert "Data di definizione automatica 2026-09-20 rimossa" in chiamate[0][2]
    chiamate.clear()
    fascicolo.avanzamento = [_voce(avvocato="avv.rossi", descrizione="Stato cambiato da IN_CORSO a DEFINITO")]
    assert runtime.riconvalida_definizione("F1", {"ragionamento": causa}) is None and not chiamate
    assert runtime.riconvalida_definizione("F1", {"ragionamento": causa, "aggiornamento_pendente": True}) is None


# --- punto 5: parti e valore letti negli atti --------------------------------------------------------------------

RICORSO_MIM = doc("RIC", "Ricorso.pdf", "atto_principale", "Ricorso in materia di lavoro (art. 414 c.p.c.)",
                  "TRIBUNALE DI VICENZA RICORSO EX ART. 414 C.P.C. La prof.ssa Gialli Anna, rappresentata e difesa dall'Avv. Mario "
                  "Rossi, elettivamente domiciliata, contro ***MINISTERO DELL’ISTRUZIONE E DEL MERITO*, in persona del Ministro pro "
                  "tempore, con sede in Roma, C.F. 80185250588, difeso per legge dall’Avvocatura Distrettuale dello Stato di Venezia, "
                  "con sede in Venezia. Carta elettronica di valore pari a Euro 500,00 annui. CONCLUSIONI accogliere. Avv. Mario Rossi")


def test_controparte_dagli_atti_e_avvocatura_come_difensore():
    fascicolo = {**LAVORO, "controparte": "Avvocatura Distrettuale di Venezia", "avvocato_controparte": ""}
    parti = ragiona(fonti(fascicolo, [RICORSO_MIM, DECRETO_415])).parti
    assert parti["controparte"] == "Ministero dell’Istruzione e del Merito"
    assert parti["difensore_controparte"] == "Avvocatura Distrettuale dello Stato di Venezia"
    assert parti["norma_difensore"] == "art. 1 R.D. 1611/1933" and parti["controparte_registrata"].startswith("Avvocatura")
    # «carta di valore pari a € 500 annui» non è la dichiarazione di valore della causa
    assert parti["valore"]["tipo"] == "non_dichiarato"
    assert etichetta_valore(parti["valore"]).startswith("Valore non dichiarato nell'atto introduttivo")
    # caso reale 31344D72: l'estrazione ha perso il nome del Ministero («contro Ministro pro tempore»): resta l'anagrafica
    senza_nome = {**RICORSO_MIM, "testo": RICORSO_MIM["testo"].replace("***MINISTERO DELL’ISTRUZIONE E DEL MERITO*, in persona del ", "")}
    assert ragiona(fonti(fascicolo, [senza_nome])).parti["controparte"] == "Avvocatura Distrettuale di Venezia"
    # una controparte registrata che è davvero una parte resta (decisione dello studio)
    assert ragiona(fonti(LAVORO, [RICORSO_MIM])).parti["controparte"] == LAVORO["controparte"]


def test_dichiarazione_di_valore_importo_e_indeterminabile():
    assert dichiarazione_di_valore("Ai fini del contributo unificato si dichiara che il valore della presente controversia è "
                                   "di € 2.400,00.")["importo"] == 2400.0
    assert dichiarazione_di_valore("Valore della causa: euro 5.200,00")["importo"] == 5200.0
    assert dichiarazione_di_valore("Si dichiara che la presente causa è di valore indeterminabile.")["tipo"] == "indeterminabile"
    assert dichiarazione_di_valore("Il valore della controversia è indeterminabile ai fini del contributo")["tipo"] == "indeterminabile"
    assert dichiarazione_di_valore("la carta elettronica di valore pari a Euro 500,00 annui") is None
    assert etichetta_valore({"tipo": "importo", "importo": 2400.0}) == "Valore € 2.400,00"
    ricorso = {**RICORSO_MIM, "testo": RICORSO_MIM["testo"] + " Si dichiara che il valore della causa è indeterminabile."}
    valore = ragiona(fonti(LAVORO, [ricorso])).parti["valore"]
    assert valore["tipo"] == "indeterminabile" and "D.P.R. 115/2002" in valore["norma"]
    con_valore = ragiona(replace(fonti({**LAVORO, "valore_causa": 1000.0}, [ricorso]))).parti["valore"]
    assert con_valore == {"tipo": "importo", "importo": 1000.0, "fonte": "anagrafica del fascicolo"}
