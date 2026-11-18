"""I passi del fascicolo come li chiede l'avvocato (18/11/2026): urgenza giuridica, fascicoli collegati, fatti già provati.

Dati fittizi. Norme: artt. 127-ter, 152, 153, 154, 415, 474, 480, 647 c.p.c.; art. 13 L. 247/2012; artt. 10, 13, 30
D.P.R. 115/2002.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from pct.fascicolo_lettura.modello import Passo
from pct.fascicolo_lettura.prossimi_passi import _ordina, _passi_conformita, _passi_economico, _passi_pec, _passi_regia
from pct.fascicolo_lettura.prossimi_passi import _passi_udienze_senza_esito
from pct.fascicolo_lettura.termini_certi import bozze_certe
from pct.fascicolo_quadro import obblighi_dal_modello, riga_notifiche, riga_prossimo_passo
from pct.ragionamento import ragiona
from tests.test_ragionamento_casi_collaudo import (
    DI, ESECUZIONE, ISTANZA_647, LAVORO, MONITORIO, PIGNORAMENTO, RICORSO_DI, conclusione, doc, fonti,
)

OGGI = date(2026, 11, 18)


# --- 1. ordine di urgenza giuridica ------------------------------------------------------------------------------

def test_processuali_per_scadenza_poi_economici_e_amministrativi():
    passi = [
        Passo(0, "Completa l'anagrafica cliente.", "blocco della regia operativa", "", "presidio del fascicolo"),
        Passo(3, "Formalizzare preventivo e conferimento d'incarico", "", "", "presidio economico", ambito="amministrativo"),
        Passo(2, "Riscuotere le spese liquidate dal giudice: € 376,00", "", "", "ragionamento sul fascicolo", ambito="economico"),
        Passo(2, "Depositare le note scritte entro il 16/12/2026", "art. 631 c.p.c.", "16/12/2026", "ragionamento sul fascicolo",
              natura="perentorio"),
        Passo(1, "Completare la notifica ordinata entro il 20/11/2026", "", "20/11/2026", "presidio notifiche", natura=""),
        Passo(1, "Notificare ricorso e decreto", "", "08/01/2027", "ragionamento sul fascicolo", natura=""),
        Passo(0, "Notificare il provvedimento al terzo", "", "24/04/2026", "ragionamento sul fascicolo"),
        Passo(2, "Indicare che cosa comunica la PEC del 12/01/2026", "", "", "presidio PEC"),
    ]
    ordinati = [p["azione"] for p in _ordina(passi, OGGI)]
    assert ordinati == [
        "Notificare il provvedimento al terzo",                # scaduto senza prova: in testa
        "Completare la notifica ordinata entro il 20/11/2026",  # scade prima del perentorio: viene prima
        "Depositare le note scritte entro il 16/12/2026",       # perentorio
        "Notificare ricorso e decreto",                         # processuale che scade dopo
        "Indicare che cosa comunica la PEC del 12/01/2026",      # processuale senza scadenza
        "Riscuotere le spese liquidate dal giudice: € 376,00",   # economico
        "Completa l'anagrafica cliente.",                        # amministrativo
        "Formalizzare preventivo e conferimento d'incarico",     # amministrativo, urgenza minore
    ]
    dati = _ordina(passi, OGGI)
    assert dati[2]["natura"] == "perentorio" and dati[2]["ambito"] == "processuale" and dati[0]["stato"] == "termine scaduto"
    # a parità di data prima il perentorio
    stesso_giorno = [Passo(1, "Ordinatorio del 16/12/2026", "", "16/12/2026", "scadenziario"),
                     Passo(2, "Perentorio del 16/12/2026", "", "16/12/2026", "scadenziario", natura="perentorio")]
    assert [p["azione"] for p in _ordina(stesso_giorno, OGGI)] == ["Perentorio del 16/12/2026", "Ordinatorio del 16/12/2026"]
    senza_scaduti = [p for p in passi if p.azione != "Notificare il provvedimento al terzo"]
    assert riga_prossimo_passo(_ordina(senza_scaduti, OGGI))["testo"].startswith("Completare la notifica ordinata entro il 20/11/2026")


# --- 2. fascicoli collegati: titolo esecutivo e precetto ----------------------------------------------------------

DI_ESECUTIVO = doc("ESEC", "decretoGenerico.pdf", "provvedimento", "Provvedimento del giudice",
                   "Decreto di esecutorieta' RG n. 4202/2024 UFFICIO DEL GIUDICE DI PACE DI PALMI Il Giudice di Pace Visto il "
                   "decreto ingiuntivo n. 1109/2024, emesso in data 20-12-2024, notificato in data 23-12-2024; atteso che avverso "
                   "il suddetto decreto non è stata proposta opposizione; visto l'art. 647 c.p.c.; DICHIARA esecutivo il decreto "
                   "ingiuntivo n. 1109/2024. PALMI, 10-03-2025", data="2025-03-10")
PRECETTO = doc("PRE", "Precetto.PDF", "atto_principale", "Atto di precetto",
               "Atto di Precetto L'Associazione Alfa, rappresentata e difesa dall'Avv. Mario Rossi con procura in atti, premesso che "
               "con ricorso per decreto ingiuntivo n. 1109/2024 del 20.12.2024, il Giudice di Pace di Palmi ha ingiunto alla Beta "
               "s.r.l. di pagare € 2.400,00; che in data 10.03.2025 il Giudice di Pace di Palmi ha dichiarato l'esecutorietà del "
               "decreto ingiuntivo n. 1109/2024; INTIMA alla Beta s.r.l. di pagare entro dieci giorni.", data="2025-09-04")


def _collegato(fid, rg, ufficio, documenti):
    return {"id": fid, "rg": rg, "ufficio": ufficio, "codice_oggetto": "",
            "documenti": [{"id": d["id"], "nome": d["nome"], "data": d.get("data_documento", ""), "testo": d["testo"]} for d in documenti]}


def test_esecuzione_trova_il_titolo_nel_fascicolo_del_monitorio():
    monitorio = _collegato("MON", "4202/2024", "GIUDICE DI PACE DI PALMI", [DI, DI_ESECUTIVO])
    causa = ragiona(fonti(ESECUZIONE, [PIGNORAMENTO, PRECETTO], collegati=[monitorio]))
    titolo = conclusione(causa, "titolo_esecutivo")
    assert titolo.stato == "fatto" and "1109/2024" in titolo.cosa and "RG 4202/2024" in titolo.prova_o_motivo
    assert "art. 474 c.p.c." in {n["norma"] for n in titolo.norme} and titolo.letto.oggetto_id == "PRE"
    assert causa.collegati and causa.collegati[0]["fascicolo_id"] == "MON"
    conformita = {"missing_documents": [{"label": "Titolo esecutivo (art. 474 c.p.c.)"}, {"label": "Procura alle liti"}]}
    vista = {"conclusioni": [{"codice": "titolo_esecutivo", "stato": "fatto"}]}
    assert [p.azione for p in _passi_conformita(conformita, vista)] == ["Acquisire il documento mancante: Procura alle liti"]
    # un decreto con altro numero, o di un altro ufficio, non è il titolo
    altro = _collegato("MON", "4202/2024", "GIUDICE DI PACE DI LOCRI", [DI, DI_ESECUTIVO])
    assert not [c for c in ragiona(fonti(ESECUZIONE, [PIGNORAMENTO, PRECETTO], collegati=[altro])).conclusioni
                if c.codice == "titolo_esecutivo"]


def test_monitorio_vede_il_precetto_gia_notificato_nel_fascicolo_dell_esecuzione():
    esecuzione = _collegato("ESE", "792/2025", "TRIBUNALE DI PALMI", [PRECETTO])
    documenti = [RICORSO_DI, DI, ISTANZA_647, DI_ESECUTIVO]
    causa = ragiona(fonti(MONITORIO, documenti, collegati=[esecuzione]))
    precetto = conclusione(causa, "precetto")
    assert precetto.stato == "fatto" and "Precetto.PDF" in precetto.prova_o_motivo and "RG 792/2025" in precetto.prova_o_motivo
    senza = ragiona(fonti(MONITORIO, documenti))
    assert conclusione(senza, "precetto").stato == "da_fare"


def test_notifica_del_decreto_attestata_dal_provvedimento_di_esecutorieta():
    consegna = doc("RDAC", "CONSEGNA: Notificazione ai sensi della legge n. 53 - 1994.eml", "comunicazione", "Ricevuta PEC di avvenuta consegna",
                   "Oggetto: CONSEGNA: Notificazione ai sensi della legge n. 53/1994 Data: 23/12/2024 17:58 Il giorno 23/12/2024 il "
                   "messaggio è stato correttamente consegnato al destinatario.")
    causa = ragiona(fonti(MONITORIO, [RICORSO_DI, DI, ISTANZA_647, DI_ESECUTIVO, consegna]))
    notifica = conclusione(causa, "notifica_decreto_ingiuntivo")
    assert notifica.stato == "fatto" and notifica.cosa == "Notifica di ricorso e decreto ingiuntivo eseguita"
    assert "23/12/2024" in notifica.prova_o_motivo and "art. 647 c.p.c." in notifica.prova_o_motivo
    assert "ricevuta di avvenuta consegna" in notifica.prova_o_motivo


# --- 4. termini del giudice: adempimento attestato, termine riassegnato, esito dell'udienza ------------------------

ORD_1 = doc("ORD1", "3584262s.pdf", "provvedimento", "Ordinanza",
            "TRIBUNALE DI VICENZA ORDINANZA Il Giudice, Visto l'art. 421 c.p.c., P.Q.M. Assegna a parte ricorrente termine fino al "
            "23/10/2026 per depositare le graduatorie aggiornate o ulteriore prova della permanenza nel sistema scolastico; "
            "Rinvia per discussione all'udienza del 03/11/2026; Dispone che la trattazione dell'udienza sia sostituita dallo "
            "scambio di note scritte da depositarsi nel termine perentorio del giorno dell'udienza fissata ex art. 127 ter c.p.c. "
            "Vicenza, 12/10/2026", data="2026-10-12")
ORD_2 = doc("ORD2", "2276942s.pdf", "provvedimento", "Ordinanza",
            "TRIBUNALE DI VICENZA ORDINANZA Il Giudice, Rilevato che la parte ricorrente con le note del 21.10.2026 ha depositato "
            "esclusivamente griglie di nomine nelle quali la stessa non risulta inserita, Visto l'art. 421 c.p.c., P.Q.M. Assegna "
            "a parte ricorrente termine fino al 16/11/2026 per depositare le graduatorie aggiornate nelle quali risulti il proprio "
            "nominativo o ulteriore prova della permanenza nel sistema scolastico; Rinvia per discussione all'udienza del "
            "23/11/2026; Dispone che la trattazione dell'udienza sia sostituita dallo scambio di note scritte da depositarsi nel "
            "termine perentorio del giorno dell'udienza fissata ex art. 127 ter c.p.c. Vicenza, 04/11/2026", data="2026-11-04")
RICORSO_LAV = doc("RL", "Ricorso.pdf", "atto_principale", "Ricorso in materia di lavoro",
                  "TRIBUNALE DI VICENZA RICORSO EX ART. 414 c.p.c. La ricorrente, rappresentata e difesa dall'Avv. Mario Rossi. " * 3)


def test_deposito_attestato_dal_giudice_e_termine_scaduto_con_rimedi():
    causa = ragiona(replace(fonti({**LAVORO, "numero_rg": "901"}, [RICORSO_LAV, ORD_1, ORD_2]), oggi=OGGI))
    depositi = [c for c in causa.conclusioni if c.codice == "deposito_ordinato"]
    primo = next(c for c in depositi if c.termine and c.termine.scadenza == "2026-10-23")
    assert primo.stato == "fatto" and "21/10/2026" in primo.prova_o_motivo and "2276942s.pdf" in primo.prova_o_motivo
    secondo = next(c for c in depositi if c.termine and c.termine.scadenza == "2026-11-16")
    assert secondo.stato == "da_fare" and secondo.termine.scaduto and secondo.termine.perentorio is False
    assert "art. 154 c.p.c." in secondo.termine.rimedi and "art. 153, secondo comma" in secondo.termine.rimedi
    note_03 = next(c for c in causa.conclusioni if c.codice == "note_127ter" and c.termine.scadenza == "2026-11-03")
    assert note_03.stato == "fatto"
    # l'udienza del 03/11 sostituita dalle note ha l'esito nell'ordinanza del 04/11 (art. 127-ter, terzo comma)
    assert [e["data"] for e in causa.esiti_udienze] == ["2026-11-03"] and causa.esiti_udienze[0]["oggetto_id"] == "ORD2"
    appuntamenti = [{"tipo": "UDIENZA", "stato": "PROGRAMMATO", "data_ora": "2026-11-03T09:00:00"}]
    assert _passi_udienze_senza_esito(appuntamenti, OGGI, "lavoro", frozenset({date(2026, 11, 3)})) == []
    assert _passi_udienze_senza_esito(appuntamenti, OGGI, "lavoro")


def test_stesso_adempimento_riassegnato_resta_un_solo_passo():
    ord_1 = {**ORD_1, "testo": ORD_1["testo"].replace("Visto l'art. 421", "Visto l'art. 421")}
    ord_2 = {**ORD_2, "testo": ORD_2["testo"].replace("con le note del 21.10.2026 ha depositato esclusivamente",
                                                      "non ha depositato")}
    causa = ragiona(replace(fonti({**LAVORO, "numero_rg": "901"}, [RICORSO_LAV, ord_1, ord_2]), oggi=OGGI))
    depositi = [c for c in causa.conclusioni if c.codice == "deposito_ordinato"]
    assert [c.stato for c in depositi if c.termine.scadenza == "2026-10-23"] == ["non_dovuto"]
    assert "superato" in next(c for c in depositi if c.termine.scadenza == "2026-10-23").prova_o_motivo


# --- 5. contributo e profilo procedurale ---------------------------------------------------------------------------

def test_profilo_procedurale_non_chiesto_se_il_rito_viene_dal_codice_oggetto():
    regia = {"operational_state": "profilo_da_confermare", "next_action": "Conferma il profilo procedurale"}
    certo = {"rito": {"codice": "volontaria_giurisdizione", "fonte": "codice oggetto PST 413014 – Autorizzazioni"}}
    assert _passi_regia(regia, [], certo) == []
    assert _passi_regia(regia, [], {"rito": {"codice": "ignoto", "fonte": ""}})


# --- 6. quadro: notifiche dal modello -------------------------------------------------------------------------------

def test_riga_notifiche_calcolata_dal_modello_senza_rinvio():
    conclusioni = [
        {"codice": "notifica_decreto_ingiuntivo", "stato": "fatto", "onerato_codice": "noi"},
        {"codice": "notifica_ricorso_decreto_415", "stato": "da_fare", "onerato_codice": "noi",
         "termine": {"scadenza_iso": "2027-01-08", "natura": "perentorio"}},
        {"codice": "costituzione_convenuto", "stato": "non_dovuto", "onerato_codice": "controparte"},
    ]
    riga = riga_notifiche(obblighi_dal_modello(conclusioni), oggi=OGGI)
    assert "Ricorso e decreto ingiuntivo (art. 644 c.p.c.): notificato" in riga["testo"]
    assert "da notificare entro il 08/01/2027" in riga["testo"] and "da calcolare" not in riga["testo"]
    assert riga_notifiche(obblighi_dal_modello([]), oggi=OGGI)["livello"] == "ok"


# --- 7. conferme inutili: PEC e bozze --------------------------------------------------------------------------------

def test_pec_con_dubbio_vero_scritto_in_chiaro():
    pec = {"da_controllare": [{"id": "pec_1", "data": "12/01/2026", "oggetto": "Fw: Notificazione L. 53/1994",
                               "mittente": "Per conto di: reclami@pec.banca.example", "motivi_controllo": ["evento da confermare"],
                               "eventi": [{"evento": "udienza in presenza", "da_rivedere": True}]}]}
    [passo] = _passi_pec(pec)
    assert passo.azione.startswith("Indicare che cosa comunica la PEC del 12/01/2026")
    assert "udienza in presenza" in passo.motivo and "non è un ufficio giudiziario" in passo.motivo


def test_pec_letta_dal_modello_non_si_conferma():
    from pct.fascicolo_lettura import pec_lette_dal_modello

    documenti = [{"id": "D1", "pec_origine": "pec_abc"}, {"id": "D2", "pec_origine": "pec_def"}]
    modello = {"atti": [{"id": "D1", "copie": [], "autore": "giudice", "appartenenza": "causa", "natura": "provvedimento"},
                        {"id": "D2", "copie": [], "autore": "studio", "appartenenza": "causa", "natura": "da_verificare"}]}
    assert pec_lette_dal_modello(documenti, modello) == frozenset({"pec_abc"})


def test_bozze_lette_nel_provvedimento_sono_certe():
    scadenze = [
        {"id": "S1", "titolo": "Deposito note scritte ex art. 127-ter c.p.c. - RG 1571/2026", "data": "2027-02-09", "stato": "BOZZA",
         "note": "PEC_TERMINE_PROPOSTO:pec_x:NOTE_127_TER"},
        {"id": "S2", "titolo": "Notifica di ricorso e decreto - almeno 30 giorni prima dell'udienza", "data": "2027-01-08",
         "stato": "BOZZA", "note": "PEC_TERMINE_PROPOSTO:pec_x:LAV_415_NOTIFICA_TRENTA_GIORNI"},
        {"id": "S3", "titolo": "Costituzione del convenuto", "data": "2027-01-29", "stato": "BOZZA",
         "note": "PEC_TERMINE_PROPOSTO:pec_x:LAV_416_COSTITUZIONE"},
    ]
    conclusioni = [
        {"codice": "note_127ter", "termine": {"scadenza_iso": "2027-02-09"}, "letto": {"documento_id": "P", "documento": "decreto.pdf", "data": "11/09/2026"}, "dubbi": []},
        {"codice": "notifica_ricorso_decreto_415", "termine": {"scadenza_iso": "2027-01-08"}, "letto": {"documento_id": "P", "documento": "decreto.pdf"},
         "dubbi": [{"codice": "destinazione_notifica_ignota"}]},
    ]
    certe = bozze_certe(scadenze, conclusioni)
    assert set(certe) == {"S1"} and "decreto.pdf" in certe["S1"] and "11/09/2026" in certe["S1"]


# --- 10. conferimento dell'incarico -----------------------------------------------------------------------------------

def test_incarico_provato_dalla_procura_non_chiede_il_preventivo():
    economico = {"presente": True, "ha_incarico": False}
    assert not _passi_economico(economico, incarico={"nome": "Procura alle liti.pdf"})
    [passo] = _passi_economico(economico)
    assert passo.azione == "Formalizzare preventivo e conferimento d'incarico" and passo.ambito == "amministrativo"
    causa = ragiona(fonti(MONITORIO, [RICORSO_DI, DI]))
    assert causa.economia["incarico"] is None or causa.economia["incarico"]["oggetto_id"]
    con_procura = ragiona(fonti(MONITORIO, [RICORSO_DI, DI, doc("PRO", "Procura.pdf", "procura", "Procura alle liti", "Procura alle liti")]))
    assert con_procura.economia["incarico"]["oggetto_id"] == "PRO"


def test_termine_della_controparte_non_e_un_dubbio_ne_si_conferma():
    from pct.fascicolo_lettura.termini_certi import bozze_della_controparte

    scadenze = [{"id": "S3", "titolo": "Costituzione del convenuto", "data": "2027-01-29", "stato": "BOZZA",
                 "note": "PEC_TERMINE_PROPOSTO:pec_x:LAV_416_COSTITUZIONE"}]
    conclusioni = [{"codice": "costituzione_convenuto", "onerato_codice": "controparte", "termine": {"scadenza_iso": "2027-01-29"},
                    "letto": {"documento_id": "P", "documento": "decreto.pdf"}, "dubbi": []}]
    assert bozze_certe(scadenze, conclusioni) == {}
    assert bozze_della_controparte(scadenze, conclusioni) == {"S3"}


def test_conferma_in_sfondo_solo_delle_bozze_automatiche_certe(monkeypatch):
    from types import SimpleNamespace

    import web.helpers as helpers
    from pct.scadenziario import StatoTermine
    from web.services.termini_certi_runtime import conferma_termini_certi

    def bozza(sid, titolo, note, data, responsabile=""):
        return SimpleNamespace(id=sid, titolo=titolo, note=note, data_scadenza=data, stato=StatoTermine.BOZZA,
                               id_utente_responsabile=responsabile)

    righe = [
        bozza("S1", "Deposito note scritte ex art. 127-ter c.p.c. - RG 1/2026", "PEC_TERMINE_PROPOSTO:pec_x:NOTE_127_TER", "2027-02-09"),
        bozza("S2", "Deposito note scritte ex art. 127-ter c.p.c. - RG 1/2026", "PEC_TERMINE_PROPOSTO:pec_y:NOTE_127_TER", "2027-02-09"),
        bozza("S3", "Deposito note scritte ex art. 127-ter c.p.c.", "scritta dall'avvocato", "2027-02-09"),
        bozza("S4", "Deposito note scritte ex art. 127-ter c.p.c.", "PEC_TERMINE_PROPOSTO:pec_z:NOTE_127_TER", "2027-02-09", "avv1"),
    ]
    azioni = []

    class Scadenziario:
        def tutte(self, **_):
            return righe

        def conferma_bozza(self, sid, attore=""):
            azioni.append(("conferma", sid, attore))

        def scarta_bozza(self, sid, motivo="", attore=""):
            azioni.append(("scarta", sid, motivo))

    monkeypatch.setattr(helpers, "get_scadenziario", lambda: Scadenziario())
    lettura = {"ragionamento": {"conclusioni": [{"codice": "note_127ter", "termine": {"scadenza_iso": "2027-02-09"},
                                                 "letto": {"documento_id": "P", "documento": "decreto.pdf"}, "dubbi": []}]}}
    assert conferma_termini_certi("F1", lettura) == 1
    assert [a[:2] for a in azioni] == [("conferma", "S1"), ("scarta", "S2")]
    assert "decreto.pdf" in azioni[0][2] and "doppione" in azioni[1][2]


def test_dopo_la_sentenza_i_termini_istruttori_e_gli_esiti_delle_udienze_non_sono_piu_passi():
    sentenza = doc("SEN", "sentenza.pdf", "provvedimento", "Sentenza",
                   "REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO Il Tribunale di Vicenza in funzione di giudice del lavoro ha "
                   "pronunciato la seguente SENTENZA P.Q.M. rigetta il ricorso. Vicenza, 10/11/2026", data="2026-11-10")
    causa = ragiona(replace(fonti({**LAVORO, "numero_rg": "901"}, [RICORSO_LAV, ORD_2, sentenza]), oggi=OGGI))
    assert next(a for a in causa.atti if a.id == "SEN").sentenza
    deposito = next(c for c in causa.conclusioni if c.codice == "deposito_ordinato")
    assert deposito.stato == "non_dovuto" and "sentenza.pdf" in deposito.prova_o_motivo
    from pct.ragionamento.udienze_esito import esito_udienza
    assert esito_udienza(date(2026, 11, 5), causa.atti, causa.udienze).oggetto_id == "SEN"


def test_termine_pec_perentorio_entra_fra_i_perentori():
    pec = {"termini_da_registrare": [{"da_rivedere": True, "scadenza": "18/11/2026", "norma": "Art. 127-ter c.p.c.",
                                      "tipo": "opposizione", "data_pec": "13/11/2026", "perentorio": True}]}
    [passo] = _passi_pec(pec, OGGI)
    assert passo.natura == "perentorio" and passo.entro == "18/11/2026"


def test_anticipazione_dell_udienza_non_e_un_adempimento_economico():
    from pct.fascicolo_lettura.prossimi_passi import ambito_del_passo

    assert ambito_del_passo(Passo(2, "Pianificare «Decreto anticipazione udienza n. r.g. 805/2026»", "", "15/12/2026",
                                  "scadenziario")) == "processuale"
    assert ambito_del_passo(Passo(3, "Recuperare le anticipazioni (€ 27,00)", "", "", "presidio economico")) == "economico"


def test_contributo_da_verificare_diventa_il_dubbio_concreto_con_dovuto_e_versato():
    presidio = {"codice": "da_verificare", "etichetta": "Da verificare", "dettaglio": "Manca la ricevuta.", "documento": None}
    causa = ragiona(fonti({**LAVORO, "valore_causa": 1000}, [RICORSO_LAV], contributo=presidio))
    cu = conclusione(causa, "contributo_unificato")
    assert cu.stato == "dubbio" and "dovuti € 21,50" in cu.cosa and "non c'è la ricevuta" in cu.cosa
    assert "art. 9, comma 1-bis" in cu.cosa and {"dpr115_art16", "dpr115_art248"} <= {n["id"] for n in cu.norme}


def test_blocchi_anagrafici_della_regia_sono_amministrativi():
    from pct.fascicolo_lettura.prossimi_passi import ambito_del_passo

    for azione in ("Completa l'anagrafica cliente.", "Collega un cliente reale al fascicolo.", "Compila tribunale o ufficio competente."):
        assert ambito_del_passo(Passo(0, azione, "blocco della regia operativa", "", "presidio del fascicolo")) == "amministrativo"
