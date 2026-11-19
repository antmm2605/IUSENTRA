"""Casi di accettazione del motore del ragionamento: i difetti del collaudo da avvocato del 10/11/2026.

Dati fittizi equivalenti ai sei fascicoli reali (G-1 … G-16). Ogni caso verifica il contratto di uscita:
che cosa si è letto, norma, che cosa fare, come, perché, stato e termine calcolato secondo la norma.
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit

from pct.ragionamento import FontiCausa, ragiona

OGGI = date(2026, 11, 10)
STUDIO = {"avvocati": ["Avv. Mario Rossi"]}


def doc(oid, nome, natura, etichetta, testo, data=""):
    return {"id": oid, "nome": nome, "natura": natura, "etichetta": etichetta, "testo": testo, "data_documento": data}


def fatto(oid, campo, valore, categoria="evento", verifica="verificata"):
    return {"oggetto_id": oid, "campo": campo, "valore": valore, "categoria": categoria, "verifica": verifica, "tipo": "documento"}


def fonti(fascicolo, documenti, **altro):
    base = {"id": "F1", "tribunale": "Tribunale di Palmi", "avvocato_referente": ""}
    return FontiCausa(fascicolo={**base, **fascicolo}, studio=STUDIO, documenti=documenti, oggi=OGGI, **altro)


def conclusione(causa, codice):
    trovate = [c for c in causa.conclusioni if c.codice == codice]
    assert trovate, f"manca la conclusione {codice}: {[c.codice for c in causa.conclusioni]}"
    return trovate[0]


def norme_di(c):
    return {n["norma"] for n in c.norme}


# --- esecuzione: art. 631 e provvedimento collettivo ---------------------------------------------------------

PIGNORAMENTO = doc("PIG", "Atto di pignoramento.pdf", "atto_esecutivo", "Atto di pignoramento",
                   "ATTO DI PIGNORAMENTO PRESSO TERZI. L'Associazione Alfa, rappresentata e difesa dall'Avv. Mario Rossi, "
                   "creditrice in forza di decreto ingiuntivo, pignora i crediti della debitrice Beta s.r.l. " * 3)
VERBALE_631 = doc("V631", "12631033s.pdf", "provvedimento", "Provvedimento dell'ufficio giudiziario",
                  "Tribunale Civile di Palmi\nCancelleria Esecuzioni Mobiliari Proc n.792/2025\n"
                  "All'udienza del 2.11.2026 tenuta dal G.E. dott. Bianchi, viene chiamata la causa iscritta al n.792/2025 R.G.E. "
                  "tra ASSOCIAZIONE ALFA contro BETA Srl\nIl G.E\nPoiché nessuno è presente rinvia all'udienza del 21.12.2026 che "
                  "sostituisce con il deposito di note scritte ex art.127 ter c.p.c. entro il termine perentorio del\n16.12.2026. "
                  "Ai sensi dell'art.631 c.p.c.\nSi comunichi\nIl Giudice O.T.")
COLLETTIVO = doc("COL", "6640888s.pdf", "provvedimento", "Provvedimento dell'ufficio giudiziario",
                 "Tribunale Civile di Palmi Cancelleria Esecuzioni Mobiliari\nProc.n. 792/2025 R.G.Es\nIl Giudice dell'Esecuzione\n"
                 "Comunica che, causa personale impedimento, l'udienza del 6.7.2026 non sarà tenuta; le cause inserite sul ruolo "
                 "della predetta udienza sono rinviate per i medesimi incombenti come di seguito: I procedimenti recanti n. 340/24; "
                 "565/25; 792/25; 319/26 sono rinviati all'udienza del 2.11.2026 che sarà trattata in presenza. I procedimenti "
                 "recanti n.344/21; 83/25+ sub.1; 330/25; 451/25 sono rinviati all'udienza del 9.11.2026 che sostituisce con il "
                 "deposito di note scritte ex art.127 ter c.p.c. entro il termine perentorio del 4.11.2026\n\nPalmi 3.7.2026\n\n"
                 "Il Giudice O.T.")
ESECUZIONE = {"numero_rg": "792", "anno_rg": "2025", "codice_oggetto_pst": "510002", "tipo": "CIVILE"}


def test_g1_termine_perentorio_631_e_non_il_giorno_dell_udienza():
    causa = ragiona(fonti(ESECUZIONE, [PIGNORAMENTO, VERBALE_631]))
    assert causa.rito.codice == "esecuzione_presso_terzi" and causa.ruolo_cliente == "attiva"
    note = conclusione(causa, "note_127ter")
    assert note.termine.scadenza == "2026-12-16" and note.termine.perentorio is True
    assert note.termine.giorni_residui == 36 and not note.termine.scaduto
    assert {"art. 631 c.p.c.", "art. 127-ter c.p.c."} <= norme_di(note)
    assert "estinzione del processo esecutivo" in note.perche and note.stato == "da_fare"
    assert "deposito telematico" in note.come and note.letto.oggetto_id == "V631" and "16.12.2026" in note.letto.brano
    assert [(u.data, u.modalita) for u in causa.udienze] == [("2026-12-21", "note_scritte")]
    assert any(x.controllo == "termine_non_udienza" and x.sciolta for x in causa.contraddizioni)


def test_g2_provvedimento_collettivo_vale_solo_il_gruppo_del_nostro_ruolo():
    causa = ragiona(fonti(ESECUZIONE, [PIGNORAMENTO, COLLETTIVO]))
    assert [(u.data, u.modalita) for u in causa.udienze] == [("2026-11-02", "presenza")]
    assert not [t for t in causa.termini if t.scadenza in {"2026-11-04", "2026-11-09"}]
    assert not [c for c in causa.conclusioni if c.codice == "note_127ter"]


# --- lavoro: art. 415, diffida, termini della controparte ----------------------------------------------------

RICORSO_LAVORO = doc("RIC", "Ricorso.pdf", "atto_principale", "Ricorso in materia di lavoro (art. 414 c.p.c.)",
                     "TRIBUNALE DI VICENZA RICORSO EX ART. 414 C.P.C. La prof.ssa Gialli Anna, rappresentata e difesa dall'Avv. "
                     "Mario Rossi, ricorre contro il MINISTERO DELL'ISTRUZIONE E DEL MERITO. " * 3)
DECRETO_415 = doc("DEC", "4194926s.pdf", "provvedimento", "Decreto di fissazione udienza",
                  "TRIBUNALE ORDINARIO di VICENZA SEZIONE PRIMA DECRETO FISSAZIONE Il Giudice del Lavoro, letto il ricorso che "
                  "precede, visto l'art. 415, commi 2 e 3, c.p.c. FISSA la comparizione delle parti dinanzi a sé per l'udienza del "
                  "09/02/2027; Dispone che la trattazione dell'udienza sia sostituita dallo scambio di note scritte da depositarsi "
                  "nel termine perentorio del giorno dell'udienza fissata, entro le ore 14.00 ex art. 127 ter c.p.c.. ORDINA che il "
                  "ricorso con il pedissequo decreto sia notificato a cura dell'istante alla controparte nei termini di legge. Si "
                  "avverte che il convenuto ha l'onere di costituirsi in cancelleria, a pena di decadenza, almeno dieci giorni prima "
                  "dell'udienza come sopra fissata.\n\nVicenza, 09/10/2026 Il Giudice del Lavoro")
DIFFIDA = doc("DIF", "Lettera di diffida.pdf", "comunicazione", "Richiesta stragiudiziale di pagamento",
              "Spett.le Ministero, Oggetto: Richiesta pagamento annualità carta del docente. Avv. Mario Rossi", "2026-03-17")
CONSEGNA_DIFFIDA = doc("CDI", "Richiesta pagamento (3).eml", "comunicazione", "Ricevuta PEC di avvenuta consegna",
                       "Oggetto: CONSEGNA: Richiesta pagamento annualità carta del docente\nData: Tue, 17 Mar 2026 10:05:10 +0100\n"
                       "Ricevuta di avvenuta consegna Il giorno 17/03/2026 il messaggio è stato consegnato.")
LAVORO = {"numero_rg": "1571", "anno_rg": "2026", "codice_oggetto_pst": "222050", "tipo": "LAVORO",
          "controparte": "Ministero dell'Istruzione e del Merito", "tribunale": "Tribunale di Vicenza"}


def test_g4_pagato_senza_prova_di_incasso_e_un_dubbio():
    pagamenti = [{"voce": "liquidazione_giudice", "stato": "pagato", "importo": 515.0, "origine": "lex_ai_sentenza_tribunale",
                  "documento": "Sentenza del 17/04/2026"}]
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO], pagamenti=pagamenti))
    assert any(x.controllo == "pagato_senza_prova" and not x.sciolta for x in causa.contraddizioni)
    assert any(d.codice == "incasso_non_provato" and "515" in d.testo for d in causa.dubbi)
    incassata = [{"id": "PARCELLA-1", "tipo": "fattura", "stato": "PAGATA", "totale": 515.0, "data_pagamento": "2026-06-01"}]
    senza_collegamento = ragiona(fonti(LAVORO, [RICORSO_LAVORO], pagamenti=pagamenti, parcelle=incassata))
    assert any(x.controllo == "pagato_senza_prova" and not x.sciolta for x in senza_collegamento.contraddizioni)
    sciolto = ragiona(fonti(LAVORO, [RICORSO_LAVORO],
                           pagamenti=[{**pagamenti[0], "proforma_id": "PARCELLA-1"}], parcelle=incassata))
    assert [x.sciolta for x in sciolto.contraddizioni if x.controllo == "pagato_senza_prova"] == [True]
    assert not [d for d in sciolto.dubbi if d.codice == "incasso_non_provato"]


SENTENZA = doc("SEN", "Sentenza.PDF", "provvedimento", "Sentenza",
               "Sentenza n. 679/2026 pubbl. il 17/04/2026 RG n. 161/2026\nTRIBUNALE DI REGGIO CALABRIA Il Giudice del lavoro "
               "nella causa RG 161/2026 promossa da Gialli Anna, rappresentata e difesa dall'Avv. Mario Rossi, contro il MINISTERO "
               "DELL'ISTRUZIONE. P.Q.M. accoglie il ricorso; condanna il Ministero dell'Istruzione e del Merito al pagamento delle "
               "spese legali in favore di parte ricorrente, che liquida in € 515,00 per compenso di avvocato, oltre rimborso forfettario "
               "spese generali 15%, CPA e IVA, da distrarsi a favore dell'avv. Mario Rossi dichiaratosi antistatario. Reggio Calabria, 17/04/2026")
RICORSO_161 = {**RICORSO_LAVORO, "nome": "Ricorso Gialli.PDF"}


def test_notifica_introduttiva_storica_solo_dopo_la_sentenza_della_causa():
    from pct.fascicolo_lettura.ragionamento import passi

    decisione = {**SENTENZA, "testo": SENTENZA["testo"].replace("161/2026", "1571/2026")
                 .replace("17/04/2026", "06/11/2026")}
    decreto = {**DECRETO_415, "testo": DECRETO_415["testo"].replace("09/02/2027", "05/11/2026")}
    documenti = [RICORSO_LAVORO, decreto]
    causa = ragiona(fonti(LAVORO, [*documenti, decisione]))
    ordine = conclusione(causa, "notifica_ricorso_decreto_415")
    assert ordine.stato == "non_dovuto"
    assert ordine.letto.oggetto_id == "DEC" and "Sentenza.PDF" in ordine.prova_o_motivo
    assert all("con il decreto di fissazione" not in passo.azione
               for passo in passi(causa.come_dizionario()))
    assert conclusione(causa, "termine_impugnazione").termine.decorrenza == "2026-11-06"

    for altra in (
        {**decisione, "testo": decisione["testo"].replace("1571/2026", "161/2026")},
        {**decisione, "testo": decisione["testo"].replace("P.Q.M.", "P.Q.M. non definitivamente pronunciando,")},
        {**decisione, "testo": decisione["testo"].replace("06/11/2026", "17/04/2026")},
    ):
        causa = ragiona(fonti(LAVORO, [*documenti, altra]))
        assert conclusione(causa, "notifica_ricorso_decreto_415").stato == "da_fare"


def _notifica(oid, notifica_id, data, file, titolo):
    return doc(oid, f"Notificazione {notifica_id}.eml", "comunicazione", "Notificazione a mezzo PEC (L. 53/1994)",
               f"Oggetto: Notificazione ai sensi della legge n. 53/1994 e succ. mod. [Notifica_ID:{notifica_id}]\n"
               f"Data: {data} 10:16 (Europe/Rome)\n\nRELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994\nHO NOTIFICATO A\n"
               f"1) - MINISTERO DELL'ISTRUZIONE E DEL MERITO C.F: 80185250588 mediante inoltro\nI seguenti atti:\n"
               f"A) - {titolo} (File: {file})\nB) - Relata di notifica.\nDICHIARO\n")


def _consegna(oid, notifica_id, data):
    return doc(oid, f"CONSEGNA {notifica_id}.eml", "comunicazione", "Ricevuta PEC di avvenuta consegna",
               f"Oggetto: CONSEGNA: Notificazione ai sensi della legge n. 53/1994 e succ. mod. [Notifica_ID:{notifica_id}]\n"
               f"Data: {data} 10:17\nRicevuta di avvenuta consegna Il giorno {data} alle ore 10:17:24 il messaggio è stato consegnato.")


def test_g5_sentenza_notificata_giudicato_e_120_giorni_contro_la_pa():
    documenti = [RICORSO_161, SENTENZA, _notifica("N1", "Ric1234", "02/02/2026", "Ricorso Gialli.PDF", "Ricorso"),
                 _consegna("K1", "Ric1234", "02/02/2026"), _notifica("N2", "Sen1234", "20/04/2026", "Sentenza.PDF", "Sentenza"),
                 _consegna("K2", "Sen1234", "20/04/2026")]
    causa = ragiona(fonti({**LAVORO, "numero_rg": "161"}, documenti,
                         consegne_verificate={"SEN": {"data": "2026-04-20", "riferimento": "prova-sentenza"}}))
    notifica = conclusione(causa, "notifica_sentenza")
    assert notifica.stato == "fatto" and "20/04/2026" in notifica.prova_o_motivo  # non «facoltativa»
    appello = conclusione(causa, "termine_impugnazione")
    assert appello.termine.scadenza == "2026-05-20" and appello.termine.scaduto
    assert "art. 434 c.p.c." in norme_di(appello)
    giudicato = conclusione(causa, "giudicato")
    assert giudicato.stato == "da_fare" and "art. 324 c.p.c." in norme_di(giudicato)
    pa = conclusione(causa, "esecuzione_pa")
    assert pa.termine is None and pa.stato == "dubbio" and "D.L. 669/1996, art. 14" in norme_di(pa)
    titolo = {"data": "2026-04-20", "riferimento": "prova-titolo", "titolo_esecutivo": "verificato"}
    con_titolo = ragiona(fonti({**LAVORO, "numero_rg": "161"}, documenti, consegne_verificate={"SEN": titolo}))
    attesa = conclusione(con_titolo, "esecuzione_pa")
    assert attesa.termine.scadenza == "2026-08-18" and attesa.termine.natura == "attesa minima prima del precetto"
    assert not attesa.termine.rimedi
    assert causa.fase["codice"] == "giudicato_da_verificare"


def test_g6_termine_della_controparte_non_e_nostro():
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415]))
    costituzione = conclusione(causa, "costituzione_convenuto")
    assert costituzione.onerato == "controparte" and costituzione.stato == "non_dovuto"
    rinvio = doc("ORD", "3584262s.pdf", "ordinanza_ufficio", "Ordinanza dell'ufficio giudiziario",
                 "TRIBUNALE ORDINARIO di VICENZA ORDINANZA Il Giudice, P.Q.M. Rinvia per discussione all'udienza del 03/11/2026; "
                 "Si avverte che il convenuto ha l'onere di costituirsi almeno dieci giorni prima dell'udienza. Vicenza, 12/10/2026")
    scadenze = [{"titolo": "Costituzione del convenuto con memoria difensiva", "data": "2027-01-29", "stato": "APERTO"}]
    dopo = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, rinvio], scadenze=scadenze))
    assert any(x.controllo == "decadenze_416" and x.sciolta for x in dopo.contraddizioni)
    assert any(x.controllo == "termine_altra_parte" for x in dopo.contraddizioni)
    assert all(c.onerato != "noi" for c in dopo.conclusioni if c.codice == "costituzione_convenuto")


def test_g7_adempimento_decisivo_con_il_suo_oggetto_preciso():
    ordinanza = doc("ORD", "3584262s.pdf", "ordinanza_ufficio", "Ordinanza dell'ufficio giudiziario",
                    "TRIBUNALE ORDINARIO di VICENZA ORDINANZA Il Giudice, P.Q.M. Assegna a parte ricorrente termine di ulteriori 10 "
                    "giorni per depositare le graduatorie aggiornate o ulteriore prova della permanenza nel sistema scolastico; Rinvia "
                    "per discussione all'udienza del 03/11/2026. Vicenza, 12/10/2026 Il giudice")
    comunicazione = doc("COM", "POSTA CERTIFICATA COMUNICAZIONE.eml", "comunicazione", "Messaggio PEC",
                        "Oggetto: POSTA CERTIFICATA: COMUNICAZIONE 901/2026\nData: 13/10/2026 09:00\nComunicazione di cancelleria "
                        "Note: Notificato alla PEC / in cancelleria il 13/10/2026 09:33\n[Allegato: 3584262s.pdf; parte 1.2]")
    causa = ragiona(fonti({**LAVORO, "numero_rg": "901"}, [RICORSO_LAVORO, ordinanza, comunicazione]))
    deposito = conclusione(causa, "deposito_ordinato")
    assert deposito.cosa.startswith("Depositare le graduatorie aggiornate")
    assert deposito.onerato == "noi" and deposito.termine.decorrenza == "2026-10-13"
    assert deposito.termine.scadenza == "2026-10-23" and deposito.termine.scaduto and deposito.stato == "da_fare"
    assert "comunicazione" in deposito.termine.evento_decorrenza


def test_g8_precedente_allegato_non_e_la_sentenza_della_causa():
    precedente = doc("PRE", "Sentenza_Tribunale_Vicenza_20-04-2023.PDF", "provvedimento", "Sentenza",
                     "Sentenza n. 300/2023 pubbl. il 20/04/2023 RG n. 4544/2022\nTRIBUNALE DI VICENZA P.Q.M. accoglie. Vicenza, 20/04/2023")
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO, precedente]))
    atto = next(a for a in causa.atti if a.id == "PRE")
    assert atto.appartenenza == "contorno"
    assert not [c for c in causa.conclusioni if c.codice in {"notifica_sentenza", "termine_impugnazione", "giudicato"}]
    assert causa.fase["codice"] != "decisa"


# --- monitorio, errori materiali, rito -----------------------------------------------------------------------

DI = doc("DI", "accoglimentoDecretoIngiuntivo.pdf", "provvedimento", "Decreto ingiuntivo",
         "Decreto ingiuntivo n. 1109/2024 RG n. 4202/2024\nUFFICIO DEL GIUDICE DI PACE DI PALMI DECRETO INGIUNTIVO Il Giudice di "
         "Pace, letto il ricorso per la concessione del decreto ingiuntivo depositato da ASSOCIAZIONE ALFA-Avv. MARIO ROSSI; "
         "INGIUNGE a BETA S.R.L. di pagare entro quaranta giorni dalla notifica del presente decreto la somma di € 2.400,00. "
         "Le spese di questa procedura, liquidate in € 76,00 per spese ed € 300,00 per compensi. AVVERTE la parte ingiunta che "
         "può proporre opposizione nel termine perentorio di quaranta giorni dalla notifica. Si comunichi. PALMI, 20-12-2024")
RICORSO_DI = doc("RDI", "DI Associazione Alfa.PDF", "atto_principale", "Ricorso per decreto ingiuntivo",
                 "GIUDICE DI PACE DI PALMI RICORSO PER DECRETO INGIUNTIVO L'Associazione Alfa, rappresentata dall'Avv. Mario Rossi. " * 3)
ISTANZA_647 = doc("I647", "Istanza esecutorietà decreto ingiuntivo.PDF", "istanza",
                  "Istanza per la concessione del decreto esecutorieta' ex art.647 c.p.c", "Istanza ex art. 647 c.p.c. Avv. Mario Rossi")
MONITORIO = {"numero_rg": "4202", "anno_rg": "2024", "codice_oggetto_pst": "010001", "tipo": "CIVILE",
             "tribunale": "Giudice di Pace di Palmi"}


def test_g10_monitorio_dello_studio_con_precetto_come_prossimo_passo():
    documenti = [RICORSO_DI, DI, _notifica("N1", "Di12345", "10/01/2025", "accoglimentoDecretoIngiuntivo.pdf", "Decreto ingiuntivo"),
                 _consegna("K1", "Di12345", "10/01/2025"), ISTANZA_647]
    scadenze = [{"titolo": "Udienza", "data": "2026-12-01", "stato": "APERTO"}]
    causa = ragiona(fonti(MONITORIO, documenti, scadenze=scadenze))
    assert causa.rito.codice == "monitorio" and causa.ruolo_cliente == "attiva"
    assert next(a for a in causa.atti if a.id == "DI").dello_studio
    assert conclusione(causa, "notifica_decreto_ingiuntivo").stato == "dubbio"
    assert conclusione(causa, "esecutorieta_647").stato == "dubbio"
    precetto = conclusione(causa, "precetto")
    assert precetto.stato == "dubbio" and "art. 480 c.p.c." in norme_di(precetto) and precetto.template == "builtin-tmp-ese-001"
    assert causa.fase["codice"] == "istanza_esecutorieta"
    assert not causa.udienze
    assert any(x.controllo == "rito_coerente" and "monitorio" in x.descrizione for x in causa.contraddizioni)


def test_g11_data_anteriore_al_decreto_e_errore_materiale_non_termine():
    decreto = doc("DEC2", "decreto.pdf", "provvedimento", "Decreto di fissazione udienza",
                  "TRIBUNALE DI PALMI Il Giudice dell'esecuzione FISSA l'udienza del 26.2.2026. DISPONE che il presente provvedimento "
                  "sia notificato, a cura della creditrice, alla debitrice entro il 10.1.2025. Palmi 24.11.2025 Il G.E.")
    avviso = doc("PAGOPA", "Avviso pagoPA.pdf", "contributo_unificato", "Contributo unificato / pagamento",
                 "Avviso di pagamento pagoPA. Data di scadenza: entro il 30/11/2026. Importo € 27,00")
    causa = ragiona(fonti(ESECUZIONE, [PIGNORAMENTO, decreto, avviso]))
    assert not [t for t in causa.termini if t.scadenza == "2025-01-10"]
    assert any(x.controllo == "data_anteriore_atto" for x in causa.contraddizioni)
    assert any(d.codice == "errore_materiale" for d in causa.dubbi)
    assert not [t for t in causa.termini if t.scadenza == "2026-11-30"]  # la scadenza pagoPA non è un termine processuale


def test_g12_rito_dal_codice_oggetto_ministeriale():
    assert ragiona(fonti(ESECUZIONE, [])).rito.codice == "esecuzione_presso_terzi"
    assert ragiona(fonti(MONITORIO, [])).rito.codice == "monitorio"
    vg = ragiona(fonti({"codice_oggetto_pst": "413014", "tipo": "CIVILE"}, []))
    assert vg.rito.codice == "volontaria_giurisdizione" and "413014" in vg.rito.fonte
    lavoro = ragiona(fonti(LAVORO, []))
    assert lavoro.rito.codice == "lavoro" and not lavoro.rito.sospensione_feriale


def test_g13_due_proforma_per_lo_stesso_compenso():
    parcelle = [{"id": "P1", "numero": "PF-1", "stato": "BOZZA", "totale": 751.45, "origine": "lex_ai_sentenza_tribunale",
                 "creato_il": "2026-04-20"},
                {"id": "P2", "numero": "PF-2", "stato": "BOZZA", "totale": 751.45, "origine": "presidio_economico_fascicolo_definito",
                 "creato_il": "2026-05-02"}]
    causa = ragiona(fonti(LAVORO, [], parcelle=parcelle))
    assert any(x.controllo == "proforma_doppia" and "PF-1, PF-2" in x.descrizione and "vale la proforma PF-1" in x.come
               for x in causa.contraddizioni)
    assert any(d.codice == "proforma_doppia" for d in causa.dubbi)


def test_g15_ruolo_letto_negli_atti_quando_il_fascicolo_non_lo_ha():
    fatti = [fatto("X1", "numero_ruolo", "792/2025", "ruolo"), fatto("X2", "numero_ruolo", "792/2025", "ruolo")]
    causa = ragiona(fonti({"codice_oggetto_pst": "510002"}, [], fatti=fatti))
    assert causa.rg == "792/2025" and causa.economia["origine_rg"].startswith("letto")
    vuoto = ragiona(fonti({"codice_oggetto_pst": "510002"}, []))
    assert any(d.codice == "rg_mancante" for d in vuoto.dubbi)


def test_contratto_di_uscita_completo_per_ogni_conclusione():
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415]))
    for c in causa.conclusioni:
        assert c.cosa and c.letto and c.norme
        for norma in c.norme:
            fonte = urlsplit(norma.get("url", ""))
            assert (fonte.scheme, fonte.netloc) == ("https", "www.normattiva.it")
        assert c.come and c.perche and c.stato in {"fatto", "da_fare", "non_dovuto", "dubbio"}
        assert c.termine is None or c.termine.scadenza or c.dubbi


def test_g14_liquidazione_delle_spese_nel_decreto_ingiuntivo():
    causa = ragiona(fonti(MONITORIO, [RICORSO_DI, DI]))
    spese = conclusione(causa, "spese_liquidate")
    assert "€ 300,00 di compensi" in spese.cosa and "€ 76,00 di spese" in spese.cosa
    assert "art. 641, terzo comma, c.p.c." in norme_di(spese) and spese.stato == "da_fare"
    assert causa.economia["liquidazioni"][0]["compensi"] == 300.0
    sentenza = ragiona(fonti({**LAVORO, "numero_rg": "161"}, [RICORSO_161, SENTENZA]))
    liquidate = conclusione(sentenza, "spese_liquidate")
    assert liquidate.cosa.startswith("Riscuotere le spese liquidate dal giudice: € 515,00") and "art. 93 c.p.c." in norme_di(liquidate)
    assert liquidate.letto.data == "2026-04-17"
    assert not any(d.codice == "contratto_fonte" for d in liquidate.dubbi)


def test_contributo_dal_presidio_non_trasforma_la_nota_di_ruolo_in_ricevuta():
    dichiarazione = doc("AUTO", "Autocertificazione.pdf", "allegato", "Esenzione contributo unificato",
                         "Dichiarazione relativa ai redditi dell'anno 2022.", data="2023-05-08")
    prova = {"id": "AUTO", "nome": "Autocertificazione.pdf"}
    stato = {"codice": "esente", "etichetta": "Esente", "norma": "art. 9, comma 1-bis, D.P.R. 115/2002",
             "documento": prova, "fonti": [prova], "dettaglio": "Autocertificazione depositata per i redditi 2022."}
    importo_nir = fatto("NIR", "contributo_unificato", "49.00", "importo")
    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO, dichiarazione], fatti=[importo_nir], contributo=stato))
    cu = conclusione(causa, "contributo_unificato")
    assert cu.cosa == "Contributo unificato: esente"
    assert cu.stato == "non_dovuto" and cu.letto.oggetto_id == "AUTO"
    assert "dpr115_art9" in {norma["id"] for norma in cu.norme}
    assert causa.economia["contributo_unificato"] == stato

    ricevuta = doc("XML", "Ricevuta.xml", "allegato", "Ricevuta versamento",
                   "Ricevuta con esito positivo e importo di euro 21,50.", data="2026-02-14")
    prova = {"id": "XML", "nome": "Ricevuta.xml"}
    pagato = {"codice": "pagato", "etichetta": "Versato", "importoLabel": "€ 21,50",
              "norma": "art. 13 D.P.R. 115/2002", "documento": prova,
              "fonti": [prova], "dettaglio": "Ricevuta del contributo unificato."}
    cu = conclusione(ragiona(fonti(LAVORO, [RICORSO_LAVORO, ricevuta], contributo=pagato)), "contributo_unificato")
    assert cu.cosa == "Contributo unificato: versato (€ 21,50)"
    assert cu.stato == "fatto" and cu.letto.oggetto_id == "XML"


def test_liquidazione_resta_visibile_senza_attribuire_crediti_con_ruolo_ignoto():
    causa = ragiona(FontiCausa(fascicolo=MONITORIO, documenti=[DI], oggi=OGGI))
    assert causa.ruolo_cliente == "ignota"
    assert any((x["compensi"], x["esborsi"]) == (300, 76) for x in causa.economia["liquidazioni"])
    assert not any(c.codice == "spese_liquidate" for c in causa.conclusioni)


def test_relata_della_sentenza_senza_consegna_non_avvia_il_termine_breve():
    recente = {**SENTENZA, "testo": SENTENZA["testo"].replace("pubbl. il 17/04/2026", "pubbl. il 17/05/2026")}
    documenti = [
        RICORSO_161, recente,
        _notifica("N1", "Ric1234", "02/02/2026", "Ricorso Gialli.PDF", "Ricorso"),
        _consegna("K1", "Ric1234", "02/02/2026"),
        _notifica("N2", "Sen1234", "20/04/2026", "Sentenza.PDF", "Sentenza"),
    ]
    causa = ragiona(fonti({**LAVORO, "numero_rg": "161"}, documenti))
    assert conclusione(causa, "notifica_sentenza").stato == "dubbio"
    assert not any(c.codice in {"giudicato", "esecuzione_pa"} for c in causa.conclusioni)
    assert "pubblicazione" in conclusione(causa, "termine_impugnazione").termine.evento_decorrenza
    con_testo = ragiona(fonti({**LAVORO, "numero_rg": "161"},
                            documenti + [_consegna("K2", "Sen1234", "20/04/2026")]))
    assert conclusione(con_testo, "notifica_sentenza").stato == "dubbio"


def test_replay_dall_apertura_alla_chiusura_con_prove_distinte():
    from pct.fascicolo_lettura.ragionamento import vista

    fascicolo = {**LAVORO, "numero_rg": "161", "data_apertura": "2026-01-10"}
    aperta = ragiona(fonti(fascicolo, []))
    assert [e.tipo for e in aperta.percorso] == ["data_apertura"]
    deposito = {
        "id": "D1", "tipo_atto": "Ricorso", "stato": "ACCETTATO_PEC", "data": "2026-01-12",
    }
    avviata = ragiona(fonti(fascicolo, [RICORSO_161], depositi=[deposito]))
    assert avviata.fase["codice"] == "atto_introduttivo_presente"
    assert next(e for e in avviata.percorso if e.tipo == "esito_deposito").stato == "accettato_pec"

    esito = {**deposito, "stato": "ACCETTATO_CANCELLERIA",
             "data_accettazione": "2026-01-13", "documenti_ids": [RICORSO_161["id"]]}
    accettata = ragiona(fonti(fascicolo, [RICORSO_161], depositi=[esito]))
    assert accettata.fase["codice"] == "atto_introduttivo_depositato"
    chiusa = ragiona(fonti(
        {**fascicolo, "data_chiusura": "2026-10-08"},
        [RICORSO_161, SENTENZA],
        depositi=[esito],
        consegne_verificate={"SEN": {"data": "2026-04-20", "riferimento": "prova-sentenza"}},
    ))
    assert chiusa.fase["codice"] == "giudicato_da_verificare"
    eventi = vista(chiusa.come_dizionario())["percorso"]
    assert any(e["stato"] == "accettato_cancelleria" and e["data"] == "2026-01-13" for e in eventi)
    assert any(e["tipo"] == "consegna_notifica" and e["fonte"]["oggetto_id"] == "prova-sentenza" for e in eventi)
    assert any(e["tipo"] == "data_chiusura" and e["stato"] == "registrato" for e in eventi)
    assert [e["data"] for e in eventi if e["data"]] == sorted(e["data"] for e in eventi if e["data"])


def test_collaudo_espone_che_cosa_manca_al_contratto():
    from pct.ragionamento.collaudo import verifica_conclusione
    from pct.ragionamento.modello import Conclusione

    voce = Conclusione("esempio", "", None, [], "", "", "fatto")
    esiti = verifica_conclusione(voce)
    assert {d.codice for d in esiti} == {
        "contratto_fonte", "contratto_norma", "contratto_adempimento", "contratto_modalita",
        "contratto_conseguenza", "contratto_stato", "contratto_termine",
    }
    assert all(d.testo and d.manca for d in esiti)


def test_riscontro_per_lex_indica_la_prova_mancante_della_sentenza():
    recente = {**SENTENZA, "testo": SENTENZA["testo"].replace("pubbl. il 17/04/2026", "pubbl. il 17/05/2026")}
    from pct.fascicolo_lettura.narrativa import riscontri_processuali
    from pct.fascicolo_lettura.ragionamento import vista

    causa = ragiona(fonti(
        {**LAVORO, "numero_rg": "161"},
        [RICORSO_161, recente, _notifica("N2", "Sen1234", "20/04/2026", "Sentenza.PDF", "Sentenza")],
    ))
    righe = riscontri_processuali({"ragionamento": vista(causa.come_dizionario())})
    testo = "\n".join(righe)
    assert "Verificare la consegna" in testo
    assert "ricevuta originale riferita alla sentenza" in testo
    fonti_normative = [urlsplit(url) for url in re.findall(r"\((https?://[^)]+)\)", testo)]
    assert any((fonte.scheme, fonte.netloc) == ("https", "www.normattiva.it") for fonte in fonti_normative)


def test_termine_lungo_richiede_la_pubblicazione_e_non_la_data_della_sentenza():
    senza_pubblicazione = {**SENTENZA, "testo": SENTENZA["testo"].replace("pubbl. il 17/04/2026", "")}
    causa = ragiona(fonti({**LAVORO, "numero_rg": "161"}, [RICORSO_161, senza_pubblicazione]))
    impugnazione = conclusione(causa, "termine_impugnazione")
    assert impugnazione.stato == "dubbio"
    assert impugnazione.termine is None
    assert any(d.codice == "pubblicazione_da_verificare" for d in impugnazione.dubbi)
    assert {"art. 133 c.p.c.", "art. 327 c.p.c."} <= norme_di(impugnazione)
    assert not any(d.codice == "contratto_termine" for d in impugnazione.dubbi)

    from pct.fascicolo_lettura.ragionamento import passi

    prossimi = passi(causa.come_dizionario())
    verifica = next(p for p in prossimi if p.azione.startswith("Verificare la pubblicazione"))
    notifica = next(p for p in prossimi if p.azione.startswith("Valutare se notificare"))
    assert verifica.urgenza < notifica.urgenza
    assert not verifica.entro



def test_monitorio_usa_la_consegna_congiunta_e_il_termine_scritto_nel_decreto():
    decreto = {**DI, "testo": DI["testo"].replace("quaranta", "cinquanta")}
    prova = {"data": "2025-01-10", "riferimento": "bundle-congiunto"}
    documenti = [RICORSO_DI, decreto]
    incompleta = ragiona(fonti(MONITORIO, documenti, consegne_verificate={"DI": prova}))
    assert conclusione(incompleta, "notifica_decreto_ingiuntivo").stato == "dubbio"
    assert conclusione(incompleta, "esecutorieta_647").termine is None
    verificata = ragiona(fonti(MONITORIO, documenti, consegne_verificate={"DI": prova, "RDI": prova}))
    assert conclusione(verificata, "notifica_decreto_ingiuntivo").stato == "fatto"
    opposizione = conclusione(verificata, "esecutorieta_647")
    assert opposizione.termine.decorrenza == "2025-01-10"
    assert "50 giorni" in opposizione.termine.computo
    assert opposizione.stato == "dubbio"  # scadenza trascorsa, consultare l'esito del registro


def test_deposito_note_richiede_conferma_con_data_e_ora_italiana():
    note = doc("NOT", "Note scritte.pdf", "atto_difensivo", "Note di trattazione scritta",
               "Note scritte per il procedimento RG 1028/2026.")
    deposito = {
        "id": "B1", "tipo_atto": "Note scritte", "stato": "ACCETTATO_CANCELLERIA",
        "data": "2027-02-09", "documenti_ids": ["NOT"],
    }
    documenti = [RICORSO_LAVORO, DECRETO_415, note]

    def stato(ricevute):
        fonti_caso = fonti(LAVORO, documenti, depositi=[{**deposito, "consegne_archivio": ricevute}])
        fonti_caso.oggi = date(2027, 2, 10)
        causa = ragiona(fonti_caso)
        return conclusione(causa, "note_127ter")

    assert stato([]).stato == "da_fare"
    assert stato([("2027-02-09T13:05:00+00:00", "PEC1")]).stato == "da_fare"  # 14:05 italiane
    tempestiva = stato([("2027-02-09T12:58:00+00:00", "PEC2")])
    assert tempestiva.stato == "fatto"
    assert "13:58" in tempestiva.prova_o_motivo and "PEC2" in tempestiva.prova_o_motivo


def test_note_collegate_alla_busta_usano_la_ricevuta_gia_registrata():
    note = doc("NOT", "Note in sostituzione udienza.pdf", "atto_difensivo", "Note di trattazione scritta",
               "TRIBUNALE DI BRESCIA\nRG 1028/2026\n09.02.2027 Note di trattazione scritta")
    deposito = {
        "id": "B1", "tipo_atto": "ATTO_GENERICO", "stato": "ACCETTATO_CANCELLERIA",
        "data": "2027-02-08", "documenti_ids": ["NOT"], "nome_atto_principale": note["nome"],
        "ricevuta_consegna": "Message-ID ricevuta: pct-1\nData esito: 08/02/2027 11:27:00",
        "ricevuta_cancelleria": True,
    }

    def stato(documento, dati_deposito):
        fonti_caso = fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415, documento], depositi=[dati_deposito])
        fonti_caso.oggi = date(2027, 2, 10)
        return conclusione(ragiona(fonti_caso), "note_127ter")

    fatto = stato(note, deposito)
    assert fatto.stato == "fatto"
    assert "08/02/2027 alle 11:27" in fatto.prova_o_motivo
    assert "deposito B1" in fatto.prova_o_motivo
    assert fatto.prova_deposito["documento_id"] == "NOT"
    from pct.fascicolo_lettura.ragionamento import vista
    proiettato = vista({"conclusioni": [fatto.come_dizionario()]})["conclusioni"][0]
    assert proiettato["termine"]["situazione"] == "adempiuto"
    assert not proiettato["termine"]["rimedi"]
    assert "art. 196-sexies disp. att. c.p.c." in norme_di(fatto)
    assert stato({**note, "testo": note["testo"].replace("09.02", "16.02")}, deposito).stato != "fatto"
    assert stato(note, {**deposito, "ricevuta_cancelleria": False}).stato != "fatto"
    assert stato(note, {**deposito, "documenti_ids": ["ALTRO"]}).stato != "fatto"


def test_scadenziario_riusa_la_prova_esatta_solo_per_il_termine_automatico(monkeypatch):
    from types import SimpleNamespace

    import web.helpers
    from web.services.consegna_presidi_runtime import riconcilia_adempimenti

    automatico = SimpleNamespace(
        id="S1", titolo="Deposito note scritte ex art. 127-ter c.p.c.",
        data_scadenza="2027-02-09", stato="APERTO", deadline_profile_code="PEC_AUTO_PRESIDIO",
        note="PEC_AUDIT:msg-resoconto", perentorio=True, trace_json="[]",
    )
    manuale = SimpleNamespace(**{**vars(automatico), "id": "S2", "deadline_profile_code": "", "note": ""})
    righe = [automatico, manuale]
    completate = []
    monkeypatch.setattr(web.helpers, "get_scadenziario", lambda: SimpleNamespace(
        tutte=lambda **_: righe, aggiorna=lambda *_a, **_kw: None,
        completa=lambda sid, **_kw: completate.append(sid),
    ))
    monkeypatch.setattr(web.helpers, "get_agenda", lambda: SimpleNamespace(get=lambda _id: None))
    monkeypatch.setattr("web.services.lettura_cache.invalida_lettura", lambda _id: None)
    conclusione = {
        "codice": "note_127ter", "stato": "fatto", "termine": {"scadenza_iso": "2027-02-09"},
        "prova_deposito": {"deposito_id": "B1", "documento_id": "D1", "consegna": "2027-02-08T11:27:00+01:00"},
        "letto": {"documento_id": "ORD1"}, "prova_o_motivo": "Ricevuta e accettazione della stessa busta.",
    }
    lettura = {"ragionamento": {"conclusioni": [conclusione]}}
    fascicolo = SimpleNamespace(id="F1", depositi_pct=[])

    # Se due termini aperti competono per la prova, il motore conserva entrambi.
    assert riconcilia_adempimenti(fascicolo, None, "studio", lettura=lettura)["completate"] == []
    righe.pop()
    assert riconcilia_adempimenti(fascicolo, None, "studio", lettura=lettura)["completate"] == ["S1"]
    assert completate == ["S1"]


def test_bozza_editabile_dello_studio_non_diventa_un_atto_processuale(monkeypatch):
    from types import SimpleNamespace

    from pct.fascicolo_lettura.modello import DatiLettura
    from web.services.ragionamento_raccolta import fonti_da_lettura

    fascicolo = SimpleNamespace(id="F1", documenti=[
        SimpleNamespace(id="BOZZA", fonte_documento="BOZZA_NOTE_127_TER"),
        SimpleNamespace(id="DEPOSITATO", fonte_documento="PST"),
    ])
    dati = DatiLettura(documenti=[
        {"id": "BOZZA", "nome": "note.html"},
        {"id": "DEPOSITATO", "nome": "note.pdf"},
    ])
    monkeypatch.setattr("web.services.archivio_letture_runtime.testi_indice_archivio", lambda _: {})
    fatti = [{"tipo": "documento", "oggetto_id": oid} for oid in ("BOZZA", "DEPOSITATO")]
    raccolte = fonti_da_lettura(fascicolo, dati, fatti)
    assert [d["id"] for d in raccolte.documenti] == ["DEPOSITATO"]
    assert [f["oggetto_id"] for f in raccolte.fatti] == ["DEPOSITATO"]
    assert len(dati.documenti) == 2


def test_note_accettate_senza_atto_identificato_restano_da_correlare(monkeypatch):
    from pct.fascicolo_lettura.ragionamento import vista
    from web.services import riscontri_processuali_runtime as riscontri

    deposito = {"id": "B1", "tipo_atto": "DEPOSITO_PCT", "stato": "ACCETTATO_CANCELLERIA",
                "data": "2027-02-08", "nome_atto_principale": "Note in sostituzione udienza"}
    fonti_caso = fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415], depositi=[deposito])
    fonti_caso.oggi = date(2027, 2, 9)
    note = conclusione(ragiona(fonti_caso), "note_127ter")
    assert note.stato == "dubbio"
    assert "deposito B1" in note.prova_o_motivo
    assert note.dubbi[0].codice == "note_depositate_da_correlare"
    lettura = {"ragionamento": vista(ragiona(fonti_caso).come_dizionario())}
    monkeypatch.setattr(riscontri, "lettura_materializzata", lambda fid: lettura if fid == "F1" else None)
    titolo = "Deposito note scritte ex art. 127-ter c.p.c."
    assert riscontri.riscontro_note_scritte("F1", note.termine.scadenza, titolo=titolo) == note.prova_o_motivo
    assert riscontri.riscontro_note_scritte("F1", "2027-02-10", titolo=titolo) == ""
    assert riscontri.riscontro_note_scritte("F2", note.termine.scadenza, titolo=titolo) == ""
    deposito["nome_atto_principale"] = "Memoria"
    note = conclusione(ragiona(fonti_caso), "note_127ter")
    assert note.stato == "da_fare"


def test_g05_riscontro_pec_storica_da_sql_non_attiva_termine_breve():
    recente = {**SENTENZA, "testo": SENTENZA["testo"].replace("pubbl. il 17/04/2026", "pubbl. il 17/05/2026")}
    documenti = [{**recente, "sha256": "a" * 64},
                 {**doc("INVIO", "Invio originale.eml", "comunicazione", "PEC", ""), "sha256": "b" * 64},
                 {**doc("RAC", "RAC.eml", "comunicazione", "RAC", ""), "sha256": "c" * 64},
                 {**doc("RDAC", "RdAC.eml", "comunicazione", "RdAC", ""), "sha256": "d" * 64}]
    prova = {
        **fatto("INVIO", "riscontro_notifica_pec_storica", "b" * 64, "metadato_fascicolo", "plausibile"),
        "prove": [{"impronte_allegati": ["a" * 64],
                   "impronte_eml": {"INVIO": "b" * 64, "RAC": "c" * 64, "RDAC": "d" * 64},
                   "accettazione_id": "RAC", "consegne": [{"documento_id": "RDAC", "data": "2024-03-30T09:01:00+01:00"}]}],
    }
    caso = {**LAVORO, "numero_rg": "161"}
    causa = ragiona(fonti(caso, documenti, fatti=[prova]))
    esito = conclusione(causa, "notifica_sentenza")
    assert esito.stato == "dubbio" and "collegate le ricevute originali" in esito.prova_o_motivo
    assert esito.dubbi[0].fonte.oggetto_id == "INVIO"
    assert conclusione(causa, "termine_impugnazione").termine.scadenza != "2026-05-20"

    causa = ragiona(fonti(caso, documenti[:-1], fatti=[prova]))
    assert "collegate le ricevute originali" not in conclusione(causa, "notifica_sentenza").prova_o_motivo


def test_note_con_controlli_superati_espongono_la_busta_e_l_esito_da_attendere():
    deposito = {"id": "B2", "id_deposito_esterno": "37010854", "tipo_atto": "DEPOSITO_PCT",
                "stato": "CONTROLLI_SUPERATI", "data": "2027-02-08",
                "nome_atto_principale": "Note per la trattazione scritta 09.02.2027"}
    for nome, atteso in ((deposito["nome_atto_principale"], "dubbio"),
                         ("Note per la trattazione scritta 01.02.2027", "da_fare")):
        caso = fonti(LAVORO, [RICORSO_LAVORO, DECRETO_415], depositi=[{**deposito, "nome_atto_principale": nome}])
        caso.oggi = date(2027, 2, 9)
        nota = conclusione(ragiona(caso), "note_127ter")
        assert nota.stato == atteso
        if atteso == "dubbio":
            assert nota.dubbi[0].codice == "note_in_attesa_cancelleria"
            assert "37010854" in nota.prova_o_motivo


def test_differimento_con_assegnazione_nelle_frasi_successive():
    from pct.ragionamento.modello import Atto
    from pct.ragionamento.provvedimenti import leggi_provvedimento

    decreto = Atto(
        "D1", "decreto.pdf", "provvedimento", "Decreto", autore="giudice", data="2026-11-13",
        testo="DIFFERISCE l’udienza già fissata al giorno 01.12.2026, stesso orario. "
              "DISPONE che l’udienza sia sostituita dal deposito di note scritte. "
              "ASSEGNA alle parti termine perentorio sino alla data della predetta udienza. "
              "INVITA i difensori al deposito delle note entro le ore 9.30 del giorno di scadenza.",
    )
    lettura = leggi_provvedimento(decreto, "1234/2025")
    assert [(t.scadenza, t.ora, t.perentorio) for t in lettura.termini] == [("2026-12-01", "09:30", True)]
    assert lettura.udienze[0].modalita == "note_scritte"


def test_decreto_lavoro_usa_la_data_delle_note_per_i_termini_a_ritroso():
    decreto = doc(
        "D", "Decreto.pdf", "provvedimento", "Decreto di fissazione udienza",
        "TRIBUNALE DI VICENZA Sezione Lavoro R.G. n. 1571/2026. Il Giudice, visto l’art. 127 ter c.p.c., "
        "ASSEGNA alle parti termine del 17/12/2026 per il deposito di note scritte "
        "Dispone che a cura del ricorrente l’atto introduttivo e il presente decreto vengano notificati "
        "alla controparte entro e non oltre il termine di trenta giorni prima dell’udienza "
        "Assegna al resistente termine sino a dieci giorni prima dell’udienza per la costituzione in giudizio "
        "mediante deposito di una memoria difensiva. Il Giudice del Lavoro.", "2026-05-18",
    )

    causa = ragiona(fonti(LAVORO, [RICORSO_LAVORO, decreto, CONSEGNA_DIFFIDA]))

    assert conclusione(causa, "note_127ter").termine.scadenza == "2026-12-17"
    assert conclusione(causa, "notifica_ordinata").termine.scadenza == "2026-11-17"
    costituzione = conclusione(causa, "costituzione_convenuto")
    assert costituzione.termine.scadenza == "2026-12-07"
    assert costituzione.stato == "non_dovuto"


def test_termine_lungo_decorso_esclude_la_notifica_per_l_impugnazione_dai_prossimi_passaggi():
    from pct.fascicolo_lettura.ragionamento import passi

    decisione = {**SENTENZA, "testo": SENTENZA["testo"].split("P.Q.M.")[0] + "P.Q.M. accoglie il ricorso e compensa le spese."}
    relata = _notifica("N2", "Sen1234", "20/04/2026", "Sentenza.PDF", "Sentenza")
    causa = ragiona(fonti({**LAVORO, "numero_rg": "161", "stato": "DEFINITO"}, [RICORSO_161, decisione, relata]))
    assert conclusione(causa, "notifica_sentenza").stato == "non_dovuto"
    assert conclusione(causa, "termine_impugnazione").termine.scaduto
    assert not any("consegna della notifica della sentenza" in p.azione for p in passi(causa.come_dizionario()))


def test_tar_ottemperanza_legge_il_proprio_dispositivo_e_usa_il_cpa():
    from pct.archivio_letture.estrazione_esito import estrai_esito
    from pct.fascicolo_lettura.documenti import documenti
    from pct.percorso_pratica.esito import esito_sentenza

    testo = (
        "N. 00425/2025 REG.RIC.\nTribunale Amministrativo Regionale per la Calabria\n"
        "SENTENZA\nSul ricorso per l'ottemperanza alla sentenza di lavoro del 25.01.2024. "
        "Non è stata depositata la prova dell'accredito.\n"
        "P.Q.M.\nIl TAR dichiara il ricorso improcedibile per sopravvenuto difetto di interesse. Spese compensate.\n"
        "Così deciso in Reggio Calabria nella camera di consiglio del giorno 30 giugno 2026.\nIL PRESIDENTE"
    )
    fs = [x.to_dict() | {"oggetto_id": "TAR", "tipo": "documento"} for x in estrai_esito(testo, origine="indice")]
    fs += [fatto("TAR", "numero_rg", "425/2025", categoria="ruolo"), fatto("TAR", "provvedimento", "2024-01-25")]
    catalogo = [{"document_id": "TAR", "document_nature": "provvedimento", "document_section": "provvedimenti",
                 "document_label": "Sentenza"}]
    dal_documento = documenti([{"id": "TAR", "nome": "sentenza.pdf"}], catalogo, rg="425/2025", fonti=fs)["sentenza"]
    assert dal_documento["data"] == "2026-06-30"
    assert not dal_documento["data_pubblicazione"]
    assert dal_documento["esito"]["motivo_esito_sentenza"] == "difetto_interesse_sopravvenuto"
    assert esito_sentenza(testo, nostra_parte="ricorrente")["per_il_cliente"] == "da_valutare"

    fascicolo = {"tipo": "AMMINISTRATIVO", "tribunale": "TAR Calabria", "numero_rg": "425", "anno_rg": "2025"}
    causa = ragiona(fonti(fascicolo, [doc("TAR", "sentenza.pdf", "provvedimento", "Sentenza", testo)]))
    termine = conclusione(causa, "termine_impugnazione")
    assert termine.termine is None and termine.stato == "dubbio"
    assert "art. 92 c.p.a." in norme_di(termine)
    assert not any("c.p.c." in norma for norma in norme_di(termine))
    assert "sopravvenuto difetto di interesse" in conclusione(causa, "esito_rito").cosa

    pubblicata = "Pubblicato il 25/07/2026\nN. 00543/2026 REG.PROV.COLL.\n" + testo
    causa = ragiona(fonti(fascicolo, [doc("TAR", "sentenza.pdf", "provvedimento", "Sentenza", pubblicata)]))
    appello = conclusione(causa, "termine_impugnazione")
    assert appello.stato == "dubbio"
    assert appello.termine is not None and appello.termine.scadenza == "2026-11-25"
    assert appello.termine.decorrenza == "2026-07-25"
    assert "art. 54, comma 2, c.p.a." in norme_di(appello)
    estratto_indice = {**doc("TAR", "sentenza.pdf", "provvedimento", "Sentenza", testo), "sha256": "a" * 64}
    timbro = {**fatto("TAR", "pubblicazione_pat", "2026-07-25", categoria="data"), "sha256": "a" * 64}
    for atteso, documento in (("2026-11-25", estratto_indice), ("", dict(estratto_indice, sha256="b" * 64))):
        causa = ragiona(fonti(fascicolo, [documento], fatti=[timbro]))
        esito = conclusione(causa, "termine_impugnazione").termine
        assert (esito.scadenza if esito else "") == atteso


def test_riscontro_storico_congiunto_individua_la_notifica_gia_consegnata():
    decreto = doc("D", "Decreto.pdf", "provvedimento", "Decreto di fissazione udienza",
                  "TRIBUNALE DI VICENZA Sezione Lavoro R.G. n. 1571/2026. "
                  "ASSEGNA alle parti ai sensi dell’art. 127 ter c.p.c. il termine del 17/12/2026 per le note scritte. "
                  "Dispone che a cura del ricorrente l’atto introduttivo e il presente decreto vengano notificati "
                  "alla controparte entro e non oltre il termine di trenta giorni prima dell’udienza. Il Giudice del Lavoro.", "2026-05-18")
    atti = [{**RICORSO_LAVORO, "sha256": "a" * 64}, {**decreto, "sha256": "b" * 64},
            {**doc("INV", "Originale notifica.eml", "comunicazione", "Invio PEC", ""), "sha256": "c" * 64},
            {**doc("RAC", "Accettazione.eml", "comunicazione", "Ricevuta PEC", ""), "sha256": "d" * 64},
            {**doc("RDC", "Consegna.eml", "comunicazione", "Ricevuta PEC", ""), "sha256": "e" * 64}]
    prova = {"impronte_eml": {"INV": "c" * 64, "RAC": "d" * 64, "RDC": "e" * 64},
             "accettazione_data": "2026-05-19T10:00:00+02:00", "accettazione_id": "RAC",
             "consegne": [{"documento_id": "RDC", "data": "2026-05-19T10:01:00+02:00"}],
             "impronte_allegati": ["a" * 64, "b" * 64]}
    riscontro = {**fatto("INV", "riscontro_notifica_pec_storica", "c" * 64, "metadato_fascicolo", "plausibile"),
                 "prove": [prova]}
    dati_decreto = fatto("D", "data_atto", "2026-05-18", "data")
    causa = ragiona(fonti(LAVORO, atti, fatti=[riscontro, dati_decreto]))
    notifica = conclusione(causa, "notifica_ordinata")
    dubbio = next(d for d in notifica.dubbi if d.codice == "validita_notifica_ordinata")
    assert notifica.stato == "dubbio" and dubbio.fonte.oggetto_id == "INV"
    assert "19/05/2026" in dubbio.testo and "pubblici elenchi" in dubbio.testo
    from pct.fascicolo_lettura.ragionamento import passi
    assert any(p.href == "/fascicoli/F1/documenti/INV/visualizza" for p in passi(causa.come_dizionario()))
    prova["impronte_allegati"] = ["b" * 64]
    incompleta = conclusione(ragiona(fonti(LAVORO, atti, fatti=[riscontro, dati_decreto])), "notifica_ordinata")
    assert not any(d.codice == "validita_notifica_ordinata" for d in incompleta.dubbi)


def test_copie_della_sentenza_riconosciute_dal_dispositivo_e_dalla_data():
    from pct.ragionamento.atti import _copie_della_sentenza
    from pct.ragionamento.modello import Atto

    contenuto = (
        "P.Q.M. Il Tribunale, definitivamente pronunciando sul ricorso in atti, accoglie la domanda "
        "e condanna la parte resistente alla rifusione delle spese di lite, che liquida in euro 100,00 "
        "oltre accessori di legge e con distrazione. Vicenza, 7/11/2025. Il giudice"
    )
    a = Atto("A", "Sentenza", "sentenza", "sentenza", rg="1506/2025",
             sentenza=True, testo="Sentenza n. 605/2025 pubblicata il 10/11/2025. " + contenuto.replace(
                 "e condanna", "Firmato Da: Nome Cognome Emesso Da: CA DI FIRMA QUALIFICATA Serial#: abcdef123456"
                 " Sentenza n. 605/2025 pubbl. il 10/11/2025 R.G. n. 1506/2025 e condanna"))
    b = Atto("B", "Copia", "sentenza", "sentenza", rg="1506/2025",
             sentenza=True, testo="Sentenza del Tribunale. " + contenuto.replace("rifusione delle spese", "*rifusione delle spese*"))
    c = Atto("C", "Altro", "sentenza", "sentenza", rg="1506/2025",
             sentenza=True, testo="Sentenza n. 606/2025 pubblicata il 10/11/2025. " + contenuto)
    _copie_della_sentenza([a, b, c])
    assert not a.copie and not b.copie and not c.copie
    _copie_della_sentenza([a, b])
    assert a.copie == ["B"] and b.copie == ["A"]


def test_copie_della_sentenza_senza_data_di_decisione_richiedono_testo_integrale_identico():
    from pct.ragionamento.atti import _copie_della_sentenza
    from pct.ragionamento.modello import Atto

    intestazione = "Sentenza n. 230/2024 pubblicata il 07/05/2024. "
    motivazione = "Motivazione del provvedimento riferita alle parti e alla domanda descritta negli atti. " * 18
    dispositivo = (
        "P.Q.M. Il Tribunale, definitivamente pronunciando sul ricorso in atti, accoglie la domanda "
        "e condanna la parte resistente alla rifusione delle spese di lite, che liquida in euro 100,00 "
        "oltre accessori di legge e con distrazione in favore del difensore antistatario."
    )
    testo = intestazione + motivazione + dispositivo
    a = Atto("A", "Sentenza", "sentenza", "sentenza", rg="1548/2023", sentenza=True, testo=testo)
    b = Atto("B", "Copia", "sentenza", "sentenza", rg="1548/2023", sentenza=True, testo=testo)
    c = Atto("C", "Altro", "sentenza", "sentenza", rg="1548/2023", sentenza=True,
             testo=intestazione + "Parte diversa. " + motivazione + dispositivo)
    _copie_della_sentenza([a, b, c])
    assert a.copie == ["B"] and b.copie == ["A"] and not c.copie


def test_distrazione_condizionata_richiede_un_atto_dello_studio_dello_stesso_rg():
    from pct.ragionamento.modello import Atto
    from pct.ragionamento.regole.economia import _richiesta_antistataria
    from dataclasses import replace

    sentenza = Atto("S", "Sentenza", "sentenza", "", data="2026-10-07", rg="2539/2025")
    nota = Atto("N", "Note scritte", "atto_difensivo", "", autore="studio", data="2025-12-18", rg="2539/2025",
                testo="Spese da distrarsi al sottoscritto, il quale dichiara di aver anticipato le prime e non ancora riscosso le seconde.")
    assert _richiesta_antistataria([nota], sentenza)["id"] == "N"
    assert not _richiesta_antistataria([replace(nota, rg="2538/2025"), replace(nota, autore="controparte"),
                                       replace(nota, data="2026-10-08")], sentenza)


def test_copie_della_stessa_busta_pec_sono_un_solo_invio_senza_attribuire_accettazione():
    from pct.ragionamento.eventi import depositi_eseguiti
    from pct.ragionamento.modello import Atto

    nome = "DEPOSITO TELEMATICO: Note scritte RG: 2539/2025 [RefID_001_example].eml"
    busta = Atto("P1", nome, "comunicazione", "", testo=f"Oggetto: {nome[:-4]}\nData: 09/12/2025")
    copia = Atto("P2", "COPIA NON CRITTOGRAFATA " + nome, "comunicazione", "")
    altro_invio = Atto("P3", nome.replace("example", "altro"), "comunicazione", "")
    esiti = depositi_eseguiti([copia, altro_invio, busta], [])
    assert {(e.fonte_id, e.data, e.accettato) for e in esiti} == {
        ("P1", "2025-12-09", False), ("P3", "", False),
    }


def test_copia_in_chiaro_identifica_le_note_dell_udienza_senza_inventare_la_ricevuta():
    from pct.ragionamento.eventi import depositi_eseguiti
    from pct.ragionamento.modello import Atto

    oggetto = "DEPOSITO TELEMATICO: Note scritte RG: 54/2025 [RefID_001_prova]"
    busta = Atto("P1", oggetto + ".eml", "comunicazione", "",
                 testo=f"Oggetto: {oggetto}\nData: 09/12/2025\n[Allegato: Atto.enc]")
    copia = Atto("P2", "COPIA NON CRITTOGRAFATA " + oggetto + ".eml", "comunicazione", "",
                 testo=f"Oggetto: COPIA NON CRITTOGRAFATA {oggetto}\nData: 09/12/2025\n"
                       "[Allegato: DatiAtto.xml.p7m; parte 1.2]\nMetadati\n"
                       "[Allegato: Note scritte.PDF; parte 1.3]\nUdienza del 16.12.2025\n"
                       "[Allegato: Estratto.PDF; parte 1.4]\nUdienza del 20.12.2025")
    esito, = depositi_eseguiti([busta, copia], [])
    assert (esito.copia_in_chiaro_id, esito.udienza_note) == ("P2", "2025-12-16")
    assert not esito.accettato and not esito.prova_consegna
