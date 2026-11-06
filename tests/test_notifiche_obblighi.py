"""Obblighi di notifica che nascono dalle comunicazioni ricevute, in tutte le materie (verificati il 05/11/2026).

Date attese calcolate a mano: appello del lavoro, decreto comunicato il 05/11/2026 → 10 giorni = domenica 15/11,
prorogato a lunedì 16/11/2026 (art. 155 c.p.c.); udienza 15/03/2027 → 25 giorni liberi prima = 17/02/2027.
Semplificato, udienza 20/04/2027 → 40 giorni liberi prima = 10/03/2027. Giudice di pace penale, udienza
10/02/2027 → almeno 20 giorni prima, lettura prudenziale = 20/01/2027.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from pct.notifiche_obblighi import OBBLIGHI, come_notificare, scheda_notifica
from pct.procedura_fasi.fonti import FONTI
from pct.provvedimenti import esamina_provvedimento
from pct.provvedimenti.regole import regole as carica_regole
from pct.provvedimenti.tipi import riconosci_tipi

APPELLO_LAVORO = ("CORTE D'APPELLO DI CATANZARO Sezione lavoro. Il Presidente, letto il ricorso in appello, visto l'art. 435 "
                  "c.p.c., fissa per la discussione l'udienza del 15/03/2027 ore 10.00. Catanzaro, 04/11/2026")
SEMPLIFICATO = ("TRIBUNALE DI ROMA Il giudice, letto il ricorso ex art. 281-undecies c.p.c., fissa l'udienza di comparizione "
                "delle parti al 20/04/2027 ore 9.30. Roma, 03/11/2026")
GDP_PENALE = ("UFFICIO DEL GIUDICE DI PACE DI ROMA Il giudice di pace, visto il ricorso immediato della persona offesa, "
              "convoca le parti all'udienza del 10/02/2027 ore 9.00. Roma, 02/11/2026")


def _termini(testo: str, materia: str) -> dict[str, date]:
    esito = esamina_provvedimento(testo, oggi=date(2026, 11, 5), comunicata_il=date(2026, 11, 5), rg="10/2026", materia=materia)
    assert esito is not None
    return {voce.codice: voce.giorno for voce in esito.voci if voce.genere == "termine"}


def test_appello_del_lavoro_non_e_il_primo_grado():
    assert riconosci_tipi(APPELLO_LAVORO) == ("decreto_435",)
    assert riconosci_tipi("Ordinanza: rinvia l'udienza al 3/3/2027, richiamato l'art. 435 c.p.c.") == ("rinvio",)
    assert _termini(APPELLO_LAVORO, "lavoro") == {"LAV_435_NOTIFICA_DIECI_GIORNI": date(2026, 11, 16),
                                                   "LAV_435_NOTIFICA_VENTICINQUE_GIORNI": date(2027, 2, 17)}


def test_procedimento_semplificato():
    assert _termini(SEMPLIFICATO, "civile")["CIV_281UNDECIES_NOTIFICA"] == date(2027, 3, 10)


def test_giudice_di_pace_penale_ricorso_immediato():
    assert _termini(GDP_PENALE, "penale") == {"PEN_GDP_27_NOTIFICA": date(2027, 1, 20)}


def test_ogni_regola_di_notifica_ha_il_suo_obbligo_e_norme_registrate():
    regole = [r for r in carica_regole() if r.get("tipo_termine") == "NOTIFICA"]
    assert regole
    for regola in regole:
        assert regola["codice"] in OBBLIGHI, regola["id"]
    for obbligo in OBBLIGHI.values():
        assert all(norma in FONTI for norma in obbligo.norme)


@pytest.mark.parametrize("controparte, attesa", [
    ("Ministero della Giustizia", "rd1611_art11"),
    ("Comune di Lamezia Terme", "dl179_art16ter"),
    ("Rossi Costruzioni S.r.l.", "l53_art3bis"),
])
def test_presso_chi_si_notifica(controparte, attesa):
    passi = come_notificare(controparte, materia="civile")
    assert attesa in passi[0]["norme"]
    assert passi[-1]["norme"] == ["cpc_137"]
    assert all(norma in FONTI for passo in passi for norma in passo["norme"])


def test_impugnazione_presso_il_procuratore_costituito():
    assert come_notificare("Rossi Mario", impugnazione=True)[0]["norme"] == ["cpc_330", "cpc_170"]


def test_scheda_civile_e_penale():
    civile = scheda_notifica("CIV_DI_NOTIFICA_644", controparte="Bianchi Srl", materia="civile", fascicolo_id="F1")
    assert civile["atti"].startswith("Ricorso e decreto ingiuntivo")
    assert civile["dopo"] and "fase=notifica" in civile["preparaHref"] and "id_fascicolo=F1" in civile["preparaHref"]
    assert any("ore 21" in a for a in civile["avvertenze"])
    penale = scheda_notifica("PEN_GDP_27_NOTIFICA", materia="penale")
    assert penale["dopo"] == [] and not any("ore 21" in a for a in penale["avvertenze"]) and penale["preparaHref"] == ""


def test_termine_assegnato_dal_giudice_rimanda_al_provvedimento():
    assert scheda_notifica("PROVV_NOTIFICA")["atti"] == "Gli atti indicati nel provvedimento"


def test_lavorazione_in_agenda_porta_la_scheda_della_notifica():
    from web.services.react_agenda_lavorazione_bridge import build_agenda_lavorazione_payload

    termine = SimpleNamespace(id="S1", stato="BOZZA", titolo="Notifica di ricorso e decreto", data_scadenza="2026-11-16",
                              perentorio=False, note="PEC_TERMINE_PROPOSTO:pec_1:LAV_415_NOTIFICA_DIECI_GIORNI", id_fascicolo="F9",
                              id_appuntamento="", tipo=SimpleNamespace(value="NOTIFICA"),
                              deadline_profile_code="LAV_415_NOTIFICA_DIECI_GIORNI", descrizione="")
    scadenziario = SimpleNamespace(get=lambda i: termine if i == "S1" else None, tutte=lambda solo_aperte=False: [termine])
    payload = build_agenda_lavorazione_payload("scadenza-S1", agenda_loader=lambda: SimpleNamespace(get=lambda i: None),
                                               scadenziario_loader=lambda: scadenziario)
    assert payload["ok"]
    assert payload["notifica"]["atti"].startswith("Ricorso e decreto di fissazione")
    assert "id_fascicolo=F9" in payload["notifica"]["preparaHref"]


# ── 06/11/2026: termini assegnati dal giudice su obblighi di legge, atti penali dello studio, notifiche a cura dell'ufficio ──
# Date attese (comunicazione 05/11/2026): 15 giorni → venerdì 20/11/2026; 30 giorni → sabato 05/12, prorogato a lunedì
# 07/12/2026 (c.p.a.); 60 giorni → lunedì 04/01/2027. Parte civile, udienza mercoledì 20/01/2027: lettura prudenziale di
# «prima dell'udienza» con un giorno libero → 18/01/2027. Incidente probatorio: subito, il giorno dopo la ricevuta → 06/11/2026.

def _voci(testo: str, materia: str):
    esito = esamina_provvedimento(testo, oggi=date(2026, 11, 5), comunicata_il=date(2026, 11, 5), rg="10/2026", materia=materia)
    assert esito is not None
    return esito


@pytest.mark.parametrize("testo, materia, codice, giorno", [
    ("TRIBUNALE DI PALMI Il giudice, rilevata la nullità della citazione ex art. 164 c.p.c., P.Q.M. DISPONE la rinnovazione "
     "della citazione entro il termine perentorio del 30.12.2026; RINVIA all'udienza del 15.05.2027.", "civile",
     "CIV_164_RINNOVAZIONE", date(2026, 12, 30)),
    ("TRIBUNALE DI PALMI rilevato che il convenuto non si è costituito e che la notificazione è nulla, P.Q.M. ORDINA all'attore "
     "di rinnovare la notificazione entro il 15.12.2026; RINVIA all'udienza del 10.02.2027.", "civile",
     "CIV_291_RINNOVAZIONE", date(2026, 12, 15)),
    ("TRIBUNALE DI PALMI P.Q.M. ORDINA l'integrazione del contraddittorio nei confronti di Rossi Mario entro il termine "
     "perentorio del 10.01.2027; RINVIA all'udienza del 20.03.2027.", "civile", "CIV_102_INTEGRAZIONE", date(2027, 1, 10)),
    ("TRIBUNALE DI PALMI vista la richiesta ex art. 269 c.p.c., AUTORIZZA la chiamata in causa del terzo Alfa Spa; DIFFERISCE "
     "la prima udienza al 15.06.2027; ASSEGNA al convenuto termine fino al 10.01.2027 per la notifica della citazione al terzo.",
     "civile", "CIV_269_CHIAMATA_TERZO", date(2027, 1, 10)),
    ("TRIBUNALE DI PALMI visto il ricorso ex art. 700 c.p.c., provvede inaudita altera parte. FISSA l'udienza di comparizione "
     "al 18.11.2026; ASSEGNA al ricorrente termine perentorio fino al 12.11.2026 per la notifica del ricorso e del decreto.",
     "civile", "CIV_669SEXIES_NOTIFICA", date(2026, 11, 12)),
    ("TRIBUNALE DI PALMI Il giudice dell'esecuzione, letto il ricorso in opposizione agli atti esecutivi, FISSA l'udienza del "
     "10.12.2026 e il termine perentorio fino al 25.11.2026 per la notificazione del ricorso e del decreto.", "civile",
     "CIV_618_NOTIFICA", date(2026, 11, 25)),
    ("TRIBUNALE DI PALMI letto il ricorso in opposizione di terzo all'esecuzione ex art. 619 c.p.c., FISSA l'udienza del "
     "10.12.2026; ASSEGNA all'opponente termine perentorio di giorni 15 dalla comunicazione del presente decreto per la "
     "notifica del ricorso e del decreto.", "civile", "CIV_618_NOTIFICA", date(2026, 11, 20)),
    ("TRIBUNALE AMMINISTRATIVO REGIONALE PER LA CALABRIA P.Q.M. ORDINA l'integrazione del contraddittorio nei confronti dei "
     "controinteressati entro il termine di 30 giorni dalla comunicazione della presente ordinanza.", "amministrativo",
     "AMM_49_INTEGRAZIONE", date(2026, 12, 7)),
    ("CORTE DI GIUSTIZIA TRIBUTARIA DI PRIMO GRADO P.Q.M. ORDINA l'integrazione del contraddittorio mediante chiamata in causa "
     "dell'Agente della riscossione entro 60 giorni dalla comunicazione.", "tributario", "TRIB_58_INTEGRAZIONE", date(2027, 1, 4)),
    ("Ricevuta di avvenuto deposito. Atto: dichiarazione di costituzione di parte civile nel procedimento n. 123/2026 RGNR. "
     "Udienza del 20.01.2027", "penale", "PEN_78_NOTIFICA", date(2027, 1, 18)),
    ("Ricevuta di avvenuto deposito. Atto: richiesta di incidente probatorio, procedimento n. 55/2026 RGNR", "penale",
     "PEN_395_NOTIFICA", date(2026, 11, 6)),
])
def test_notifica_dovuta_con_la_data_del_giudice_o_della_legge(testo, materia, codice, giorno):
    termini = {v.codice: v for v in _voci(testo, materia).voci if v.genere == "termine"}
    assert termini[codice].giorno == giorno
    assert termini[codice].tipo_termine == "NOTIFICA"
    assert codice in OBBLIGHI


def test_senza_la_data_scritta_si_chiede_all_avvocato():
    esito = _voci("TRIBUNALE DI PALMI rilevata la nullità della citazione, ne dispone la rinnovazione; rinvia all'udienza "
                  "del 15.05.2027.", "civile")
    domanda = next(v for v in esito.voci if v.codice == "CIV_164_RINNOVAZIONE")
    assert domanda.genere == "da_verificare" and domanda.giorno is None and domanda.domanda


@pytest.mark.parametrize("testo, materia", [
    ("TRIBUNALE DI PALMI Ufficio GIP. Letta la richiesta di incidente probatorio, ACCOGLIE e FISSA l'udienza del 13.11.2026.",
     "penale"),
    ("TRIBUNALE DI PALMI Sezione fallimentare. Visto il ricorso per l'apertura della liquidazione giudiziale, CONVOCA le parti "
     "all'udienza del 03.12.2026.", "civile"),
])
def test_notifica_a_cura_dell_ufficio_non_crea_termini_per_lo_studio(testo, materia):
    voci = _voci(testo, materia).voci
    assert any(v.genere == "attesa" and v.chi == "cancelleria" for v in voci)
    assert not [v for v in voci if v.tipo_termine == "NOTIFICA"]


@pytest.mark.parametrize("testo", [
    "Il giudice RIGETTA l'istanza di autorizzazione alla chiamata del terzo perché tardiva; RINVIA all'udienza del 10.01.2027.",
    "All'udienza il difensore deposita atto di costituzione di parte civile; il giudice ammette la costituzione.",
    "Sentenza. In nome del popolo italiano. Ritenuto che era stata ordinata l'integrazione del contraddittorio, rigetta.",
    # PEC reale: dichiarazione del terzo pignorato (art. 547 c.p.c.), non chiamata in causa
    "Procedura esecutiva nella quale la Banca è stata chiamata a rendere la dichiarazione di terzo ex art. 547 c.p.c., il sig. "
    "Rossi, autorizzato in forza di procura speciale, dichiara.",
])
def test_nessuna_notifica_inventata(testo):
    assert not {"chiamata_terzo", "deposito_costituzione_parte_civile", "integrazione_contraddittorio"} & set(riconosci_tipi(testo))


def test_scheda_penale_della_parte_civile():
    scheda = scheda_notifica("PEN_78_NOTIFICA", materia="penale", fascicolo_id="F2")
    assert scheda["aCuraDi"] == "Parte civile"
    assert scheda["come"][0]["norme"] == ["cpp_152"]
    assert scheda["dopo"] == [] and not any("ore 21" in a for a in scheda["avvertenze"])
    assert {n["id"] for n in scheda["norme"]} >= {"cpp_78", "cpp_79", "cpp_152"}
