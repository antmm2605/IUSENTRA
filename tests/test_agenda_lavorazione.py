"""Scheda di lavorazione dell'impegno d'agenda (pct/agenda_lavorazione.py, web/services/react_agenda_lavorazione_bridge.py)."""

from __future__ import annotations

from types import SimpleNamespace

from pct.agenda_lavorazione import indice_proposte, proposte_aperte, proposte_collegate, voce_proposta
from web.services.react_agenda_lavorazione_bridge import build_agenda_lavorazione_payload

PEC = "pec_e4c7d1230b4b"
RICEZIONE = SimpleNamespace(
    id="APP1", note=f"PEC_RICEZIONE:{PEC}\nEvento: RIASSEGNAZIONE TERMINE PER NOTE IN SOSTITUZIONE UDIENZA\n"
                    "Attività per l'avvocato: leggere il provvedimento e aggiornare il termine.\nFascicolo: DE674F4F",
    descrizione="", id_fascicolo="", remote_hearing_url="")


def _bozza(id_, data, **extra):
    return SimpleNamespace(id=id_, stato="BOZZA", titolo=f"Termine {id_}", data_scadenza=data, perentorio=True,
                           operational_due_at=f"{data}T14:00:00", id_appuntamento="", source_message_id="",
                           note=f"PEC_TERMINE_PROPOSTO:{PEC}:NOTE_127_TER\nCalcolo: 10 giorni dal 04/11.", descrizione="", **extra)


SCADENZE = [
    _bozza("B1", "2026-11-23"),
    _bozza("B2", "2026-11-16"),
    SimpleNamespace(id="A1", stato="APERTO", titolo="Già operativa", data_scadenza="2026-11-23", note=f"PEC_AUDIT:{PEC}",
                    perentorio=False, operational_due_at="", id_appuntamento="", source_message_id="", descrizione=""),
    SimpleNamespace(id="X1", stato="BOZZA", titolo="Altra causa", data_scadenza="2026-12-01", note="PEC_TERMINE_PROPOSTO:pec_altra:X",
                    perentorio=False, operational_due_at="", id_appuntamento="", source_message_id="", descrizione=""),
]


def test_proposte_della_stessa_pec_in_ordine_di_data():
    assert [s.id for s in proposte_collegate(SCADENZE, RICEZIONE, id_impegno="APP1")] == ["B2", "B1"]


def test_sigillo_conta_le_bozze_una_volta_sola():
    # B3 è collegata sia alla PEC sia all'appuntamento: conta una volta.
    dell_udienza = SimpleNamespace(**{**vars(_bozza("B3", "2026-11-10")), "id_appuntamento": "APP1"})
    indice = indice_proposte(SCADENZE + [dell_udienza])
    assert proposte_aperte(RICEZIONE, indice, id_impegno="APP1") == 3


def test_voce_proposta_in_linguaggio_legale():
    voce = voce_proposta(SCADENZE[0])
    assert voce["dataEtichetta"] == "23 novembre 2026 ore 14:00" and voce["perentorio"] is True
    assert voce["spiegazione"] == "10 giorni dal 04/11." and voce["confermaHref"] == "/scadenziario/B1/conferma-proposta"


def test_riusa_i_due_computi_del_decreto_solo_se_coerenti_con_la_data_proposta():
    proposta = SimpleNamespace(
        id="B3", titolo="Deposito note scritte ex art. 127-ter c.p.c.", data_scadenza="2026-12-16",
        perentorio=True, operational_due_at="2026-12-16T23:59:00",
        note="Termine proposto: 16/12/2026.\nDecreto del 10/11/2026: note cinque giorni prima dell’udienza. "
             "Computo a giorni pieni 17/12/2026. Data operativa prudenziale a giorni liberi 16/12/2026.",
    )
    voce = voce_proposta(proposta)
    assert voce["dataEtichetta"] == "16 dicembre 2026"
    assert voce["dataGiorniPieni"] == "17 dicembre 2026"
    assert voce["spiegazione"] == "Decreto del 10/11/2026: note cinque giorni prima dell’udienza."
    proposta.data_scadenza = "2026-12-15"
    assert voce_proposta(proposta)["dataGiorniPieni"] == ""


def test_opposizione_in_agenda_mantiene_il_titolo_dello_scadenziario():
    from web.services.react_agenda_bridge import _deadline_event

    termine = SimpleNamespace(
        id="SC1", stato="APERTO", tipo="DEPOSITO_ATTO", titolo="Opposizione",
        data_scadenza="2026-11-16", deadline_profile_code="CIV_OPPOSIZIONE_127_TER",
        note="Termine proposto: Eventuale opposizione alla trattazione scritta",
    )
    evento = _deadline_event(termine, control_tower_source={"displayTitle": "Udienza"})
    assert evento["legalLabel"] == "Opposizione alla trattazione scritta"
    assert evento["originTitle"].startswith("Eventuale opposizione alla trattazione scritta")
    assert evento["kind"] == "SCADENZA"


def test_agenda_mostra_l_ora_delle_note_scritte_gia_salvata_nello_scadenziario():
    from web.services.react_agenda_bridge import _deadline_event

    termine = SimpleNamespace(
        id="SC2", stato="APERTO", tipo="TERMINE_PERENTORIO",
        titolo="Deposito note scritte ex art. 127-ter c.p.c.",
        data_scadenza="2026-12-16", operational_due_at="2026-12-16T13:00:00Z",
    )
    evento = _deadline_event(termine)
    assert evento["kind"] == "DEPOSITO"
    assert evento["timeLabel"] == "14:00"
    assert evento["start"] == "2026-12-16T14:00"
    termine.operational_due_at = "2026-12-16T23:59:00"
    assert _deadline_event(termine)["timeLabel"] == "Entro giornata"


def test_scheda_di_lavorazione_completa():
    agenda = SimpleNamespace(get=lambda i: RICEZIONE if i == "APP1" else None)
    scadenziario = SimpleNamespace(get=lambda i: None, tutte=lambda solo_aperte=False: SCADENZE)
    scheda = build_agenda_lavorazione_payload("APP1", agenda_loader=lambda: agenda, scadenziario_loader=lambda: scadenziario)
    assert scheda["ok"] and [p["id"] for p in scheda["proposte"]] == ["B2", "B1"]
    assert scheda["arrivo"].startswith("Riassegnazione termine per note in sostituzione udienza") and scheda["fascicoloHref"] == "/fascicoli/DE674F4F"
    assert scheda["prossimo"] == "Leggere il provvedimento e aggiornare il termine."
    assert build_agenda_lavorazione_payload("NO", agenda_loader=lambda: agenda, scadenziario_loader=lambda: scadenziario)["ok"] is False


def test_date_in_formato_italiano_e_ora_di_roma():
    from web.services.react_agenda_lavorazione_bridge import date_italiane

    assert date_italiane("Decorrenza letta: 2026-11-02T09:30:00") == "Decorrenza letta: 02/11/2026 ore 09:30"
    assert date_italiane("dal 2026-12-10T00:00:00") == "dal 10/12/2026"
    assert date_italiane("consegna 2026-11-05T09:20:06Z") == "consegna 05/11/2026 ore 10:20"  # UTC → Roma (ora solare)
    assert date_italiane("udienza 2026-07-01T07:15:00+00:00") == "udienza 01/07/2026 ore 09:15"  # ora legale
    assert date_italiane("termine 2026-11-23") == "termine 23/11/2026"


def test_cosa_e_arrivato_con_decorrenza_in_italiano():
    from web.services.react_agenda_lavorazione_bridge import _arrivo

    testo = _arrivo("Evento: FISSAZIONE TERMINE PER NOTE IN SOSTITUZIONE UDIENZA\nDecorrenza letta: 2026-11-03T14:00:00")
    assert testo == "Fissazione termine per note in sostituzione udienza."
    assert _arrivo("Evento: COMUNICAZIONE SENTENZA\nDecorrenza letta: 2026-11-03T14:00:00") == (
        "Comunicazione sentenza. Decorrenza: 03/11/2026 ore 14:00."
    )


def test_proposta_di_collegamento_della_pec_al_fascicolo():
    from web.services.react_agenda_lavorazione_bridge import _fascicolo_da_proporre

    assert _fascicolo_da_proporre("F1", "F2", []) == ("F1", "indicato sull'impegno")
    assert _fascicolo_da_proporre("", "F2", [("F3", 1.0)])[0] == "F2"
    assert _fascicolo_da_proporre("", "", [("F3", 0.95), ("F4", 0.3)])[0] == "F3"
    assert _fascicolo_da_proporre("", "", [("F3", 1.0), ("F4", 1.0)]) == ("", "")  # pari merito: sceglie l'avvocato
    assert _fascicolo_da_proporre("", "", [("F3", 0.7)]) == ("", "")


def test_testo_del_registro_in_carattere_normale():
    from web.services.react_agenda_lavorazione_bridge import _frase

    assert _frase("DEPOSITATO ATTO ricorso notificato DA PARTE DI avv. Montagnese Giuseppe") == (
        "Depositato atto ricorso notificato da parte di avv. Montagnese Giuseppe")
    assert _frase("FISSATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA RG 901/2026") == "Fissato termine per note in sostituzione udienza RG 901/2026"


def test_fascicoli_dello_stesso_cliente_prima_stesso_ufficio_e_senza_rg():
    from types import SimpleNamespace as N

    from web.services.react_agenda_lavorazione_bridge import _fascicoli_del_cliente

    archivio = N(tutti=lambda archiviati=False: [
        N(id="A", nome_cliente="Rossi Maria", tribunale="Tribunale di Palmi", numero_rg="12", stato="APERTO"),
        N(id="B", nome_cliente="ROSSI MARIA", tribunale="Tribunale di Brescia", numero_rg="", stato="APERTO"),
        N(id="C", nome_cliente="Rossi Mario", tribunale="Tribunale di Brescia", numero_rg="", stato="APERTO"),
        N(id="D", nome_cliente="Rossi Maria", tribunale="Tribunale di Brescia", numero_rg="", stato="ARCHIVIATO"),
    ])
    assert [f.id for f in _fascicoli_del_cliente(archivio, "ROSSI MARIA", "Tribunale Ordinario di Brescia")] == ["B", "A"]
    assert _fascicoli_del_cliente(archivio, "Rossi", "Tribunale di Brescia") == []  # una sola parola: troppo incerto


def test_identificazione_certa_per_rg_anno_e_ufficio():
    from types import SimpleNamespace as N

    from web.services.react_agenda_lavorazione_bridge import _fascicolo_per_rg

    archivio = N(tutti=lambda archiviati=True: [
        N(id="A", numero_rg="2477", anno_rg=2026, tribunale="Tribunale di Brescia"),
        N(id="B", numero_rg="2477", anno_rg=2025, tribunale="Tribunale di Brescia"),
        N(id="C", numero_rg="2477", anno_rg=2026, tribunale="Tribunale di Palmi"),
    ])
    assert _fascicolo_per_rg(archivio, "2477/2026/LAV", "Tribunale Ordinario di Brescia").id == "A"
    assert _fascicolo_per_rg(archivio, "2477/2026", "") is None  # stesso RG in due uffici: non si indovina


def test_mezzanotte_del_registro_non_si_scrive():
    from web.services.react_agenda_lavorazione_bridge import date_italiane

    assert date_italiane("termine per note il 10/12/2026 00:00, adempimenti") == "termine per note il 10/12/2026, adempimenti"
    assert date_italiane("udienza il 10/12/2026 09:30") == "udienza il 10/12/2026 09:30"

def test_stessa_pec_le_copie_confluiscono_senza_assorbire_altri_adempimenti():
    def proposta(id_, codice="NOTE_127_TER", **extra):
        return SimpleNamespace(**{
            **vars(_bozza(id_, "2026-12-16")),
            "id_fascicolo": "DE674F4F", "source_message_id": PEC,
            "deadline_profile_code": codice, "note": f"PEC_TERMINE_PROPOSTO:{PEC}:{codice}",
            **extra,
        })

    copia = proposta("copia", id_appuntamento="APP1")
    originale = proposta("originale", id_utente_responsabile="avvocato")
    notifica = proposta("notifica", "LAV_415_NOTIFICA_TRENTA_GIORNI")
    altro_fascicolo = proposta("distinto", id_fascicolo="ALTRO")
    altro_orario = proposta("altro-orario", operational_due_at="2026-12-16T23:59:00")
    scadenze = [copia, originale, notifica, altro_fascicolo, altro_orario]
    assert {s.id for s in proposte_collegate(scadenze, RICEZIONE, id_impegno="APP1")} == {
        "originale", "notifica", "distinto", "altro-orario",
    }
    assert proposte_aperte(copia, indice_proposte(scadenze)) == 4

    copia.stato = "ANNULLATO"
    copia.note += "\nPEC_PROPOSTA_DUPLICATA_DI:originale"
    assert "originale" in {s.id for s in proposte_collegate(scadenze, RICEZIONE, id_impegno="APP1")}

    originale.stato = "APERTO"
    assert {s.id for s in proposte_collegate(scadenze, RICEZIONE, id_impegno="APP1")} == {
        "notifica", "distinto", "altro-orario",
    }
    assert proposte_aperte(RICEZIONE, indice_proposte(scadenze), id_impegno="APP1") == 3
