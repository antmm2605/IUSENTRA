"""Collaudo 10/11/2026 (G-3, G-5, G-8): la prova di notifica è dell'atto, l'obbligo è della causa.

Dati fittizi. Norme: art. 3-bis L. 53/1994; artt. 324, 325, 326, 415, 434 c.p.c.; art. 3 L. 742/1969;
art. 14 D.L. 669/1996.
"""

from __future__ import annotations

from datetime import date

from pct.atto_della_causa import provvedimento_della_causa, ruoli_in_intestazione
from pct.decreto_fissazione_lavoro import ETICHETTA, e_decreto_fissazione_lavoro, udienza_fissata
from pct.notifica_atto_l53 import e_notificazione_l53, notifiche_pec, prove_per_atto
from pct.obblighi_notifica import STATO_DA_NOTIFICARE, STATO_NOTIFICATO, DocumentoCatalogato, Parte, obblighi_del_fascicolo
from pct.sentenza_notificata import condanna_al_pagamento, termini_dalla_notifica

MESSAGGIO_SENTENZA = """Oggetto: Notificazione ai sensi della legge n. 53/1994 e succ. mod. [AB1] [Notifica_ID:Zeta1234]
Mittente: "Avv. Mario Rossi" <rossi@pec.it>
Data: 20/04/2026 10:16 (Europe/Rome)

Corpo email:
RELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994
HO NOTIFICATO A
1) - MINISTERO DELL'ISTRUZIONE E DEL MERITO  C.F: 80185250588 in persona del Ministro mediante inoltro
I seguenti atti:
A) - Sentenza (File: Sentenza.PDF)
Natura del documento: Copia estratta dal fascicolo informatico
B) - Relata di notifica.
DICHIARO
"""
CONSEGNA_SENTENZA = """Oggetto: CONSEGNA: Notificazione ai sensi della legge n. 53/1994 e succ. mod. [AB1] [Notifica_ID:Zeta1234]
Data: 20/04/2026 10:17
Ricevuta di avvenuta consegna Il giorno 20/04/2026 alle ore 10:17:24 il messaggio è stato consegnato.
"""
CONSEGNA_DIFFIDA = """Oggetto: CONSEGNA: Richiesta pagamento annualità carta del docente
Data: Tue, 17 Mar 2026 10:05:10 +0100
Ricevuta di avvenuta consegna Il giorno 17/03/2026 il messaggio è stato consegnato.
"""
DECRETO = """TRIBUNALE ORDINARIO di VICENZA DECRETO FISSAZIONE Il Giudice del Lavoro, letto il ricorso che precede,
visto l'art. 415, commi 2 e 3, c.p.c. FISSA la comparizione delle parti per l'udienza del 09/02/2027;
ORDINA che il ricorso con il pedissequo decreto sia notificato a cura dell'istante. Vicenza, 09/10/2026"""


def _spedizioni():
    testi = {"M1": MESSAGGIO_SENTENZA, "R1": CONSEGNA_SENTENZA, "D1": CONSEGNA_DIFFIDA}
    return notifiche_pec(testi, {"M1": "Notificazione...", "R1": "CONSEGNA", "D1": "CONSEGNA diffida"})


def test_ricevuta_di_una_diffida_non_e_notifica():
    assert not e_notificazione_l53(CONSEGNA_DIFFIDA)
    assert e_notificazione_l53(CONSEGNA_SENTENZA)
    spedizioni = _spedizioni()
    assert [s.spedizione for s in spedizioni] == ["Zeta1234"]
    assert spedizioni[0].perfezionata and spedizioni[0].data == "2026-04-20"


def test_la_prova_e_dell_atto_elencato_nella_relata_non_del_ricorso():
    documenti = {"S1": "Sentenza.PDF", "S2": "Sentenza (originale notificato).pdf", "RIC": "Ricorso.PDF"}
    prove = prove_per_atto(_spedizioni(), documenti)
    assert {p["atto_documento_id"] for p in prove} == {"S1", "S2"}
    assert all(p["verificata"] and p["data"] == "2026-04-20" for p in prove)
    assert prove[0]["destinatari"] == ["MINISTERO DELL'ISTRUZIONE E DEL MERITO"]


def test_la_notifica_non_precede_l_atto():
    prove = prove_per_atto(_spedizioni(), {"S1": "Sentenza.PDF"}, {"S1": "2026-05-01"})
    assert prove == []


def test_sentenza_notificata_termine_breve_giudicato_e_120_giorni_contro_la_pa():
    sentenza = DocumentoCatalogato(id="S1", nome="Sentenza.PDF", etichetta="Sentenza", nostro=True)
    parti = [Parte(nome="MINISTERO DELL’ISTRUZIONE E DEL MERITO", ruolo="controparte", documenti=("S1",))]
    prove = prove_per_atto(_spedizioni(), {"S1": "Sentenza.PDF"})
    contesto = {"prove_notifica": prove, "rito_lavoro": True, "condanne_al_pagamento": {"S1": True}}
    obbligo = obblighi_del_fascicolo([sentenza], parti, ufficio="Tribunale di Reggio Calabria", contesto=contesto,
                                     oggi=date(2026, 11, 10))[0]
    assert obbligo.stato == STATO_NOTIFICATO  # l'apostrofo tipografico non impedisce il riscontro dei destinatari
    calcoli = {c["codice"]: c["deadline"] for c in obbligo.calcoli}
    assert calcoli == {"termine_breve_impugnazione": "2026-05-20", "passaggio_in_giudicato": "2026-05-21",
                       "esecuzione_pa_120_giorni": "2026-08-18"}
    assert "20/04/2026" in obbligo.motivo and "19/08/2026" in obbligo.motivo

    contesto["termini_sentenza_nei_riscontri"] = True
    obbligo = obblighi_del_fascicolo([sentenza], parti, ufficio="Tribunale di Reggio Calabria", contesto=contesto,
                                     oggi=date(2026, 11, 10))[0]
    assert obbligo.stato == STATO_NOTIFICATO
    assert obbligo.calcoli == []
    assert "20/04/2026" in obbligo.motivo and "Riscontri del fascicolo" in obbligo.motivo
    assert "19/08/2026" not in obbligo.motivo


def test_termine_breve_fuori_dal_lavoro_con_sospensione_feriale():
    calcoli = termini_dalla_notifica("2026-07-20", lavoro=False, contro_pa=False, condanna=True)
    assert calcoli[0]["deadline"] == "2026-09-21"  # 30 giorni + 31 di agosto, primo giorno non festivo
    assert [c["codice"] for c in calcoli] == ["termine_breve_impugnazione", "passaggio_in_giudicato"]


def test_condanna_al_pagamento_dal_dispositivo():
    assert condanna_al_pagamento("motivi... P.Q.M. condanna il Ministero al pagamento delle spese legali")
    assert not condanna_al_pagamento("P.Q.M. rigetta il ricorso e compensa le spese")


def test_decreto_di_fissazione_del_lavoro_crea_l_obbligo_ricorso_e_decreto():
    assert e_decreto_fissazione_lavoro(DECRETO) and udienza_fissata(DECRETO) == "2027-02-09"
    assert not e_decreto_fissazione_lavoro("Ricorso ex art. 414 c.p.c. ... voglia l'Ill.mo Giudice FISSARE l'udienza del 01/02/2027")
    decreto = DocumentoCatalogato(id="DEC", nome="4194926s.pdf", etichetta=ETICHETTA, data="2026-10-09", nostro=True,
                                  udienze=("2027-02-09",))
    parti = [Parte(nome="MINISTERO DELL'ISTRUZIONE E DEL MERITO", ruolo="controparte")]
    obbligo = obblighi_del_fascicolo([decreto], parti, ufficio="Tribunale di Vicenza",
                                     contesto={"decreti_collegati": {"DEC": "2026-10-09"}}, oggi=date(2026, 11, 10))[0]
    assert obbligo.regola.id == "lavoro_415" and obbligo.stato == STATO_DA_NOTIFICARE
    # Il termine ordinatorio di 10 giorni (19/10/2026) è decorso: resta quello a difesa, 30 giorni prima dell'udienza
    # (10/01/2027 è domenica: a ritroso si anticipa al venerdì).
    assert obbligo.scadenza == "2027-01-08" and not obbligo.dati_mancanti
    assert "19/10/2026" in obbligo.motivo


def test_sentenza_di_altro_procedimento_non_e_della_causa():
    assert ruoli_in_intestazione("n. XXX/2022 R.G. REPUBBLICA ITALIANA") == [("XXX", "2022")]
    assert provvedimento_della_causa(ruoli=[("XXX", "2022")], date_atto=[], numero_rg="1571", anno_rg="2026")[0] is False
    assert provvedimento_della_causa(ruoli=[("161", "2026")], date_atto=[], numero_rg="161", anno_rg="2026")[0] is True
    assert provvedimento_della_causa(ruoli=[], date_atto=["2023-04-20"], numero_rg="1571", anno_rg="2026")[0] is False
    assert provvedimento_della_causa(ruoli=[], date_atto=["2026-04-20"], numero_rg="1571", anno_rg="2026")[0] is None
