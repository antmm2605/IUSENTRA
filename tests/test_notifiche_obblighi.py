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
