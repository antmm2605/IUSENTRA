"""Correzioni del 08/11/2026 su PEC, scadenziario, catalogo e letture (casi reali anonimizzati).

Ogni caso riproduce la forma di un dato reale dello studio con nomi, numeri e date di fantasia:
- comunicazione «REVOCATA UDIENZA E FISSATO TERMINE PER NOTE IN SOST. UDIENZA» (art. 127-ter c.p.c.);
- udienza anticipata e poi sostituita da note nello stesso fascicolo;
- ricevute di deposito con «Note in sostituzione udienza» nel nome dell'atto;
- notifiche L. 53/1994 con oggetto «legge n. 53/1994»;
- decreto ex art. 415 c.p.c. con lo studio che difende il ricorrente;
- memoria di costituzione della P.A. che cita il «pedissequo decreto di fissazione dell'udienza».
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from pct import pec_pipeline as pp
from pct.document_intelligence.catalog_resolver import _classify_indexed_content
from pct.document_intelligence.pdf_inspector_engine import plain_markdown
from pct.note_127_ter.comunicazione import (
    CODICE_OPPOSIZIONE_127_TER,
    apre_opposizione,
    evento_note_127_ter,
    proposta_opposizione,
)
from pct.notifiche_ricevute import oggetto_di_notifica_l53
from pct.pec_change_receipt import detect_schedule_change, select_rescheduled_appointments
from pct.pec_legal_deadline_proposer import propose_from_parsed
from pct.pec_legal_event_understanding import build_legal_event_understanding
from pct.provvedimenti import esamina_provvedimento
from pct.provvedimenti.parte_assistita import ruolo_cliente, spetta_al_cliente
from pct.registro_letture.modello import Anomalia
from pct.registro_letture.riconvalida import regola_superata
from pct.udienze_superate import ANTICIPATA, NOTE_127_TER, RINVIATA, riga_traccia, udienze_superate

ROME = ZoneInfo("Europe/Rome")
OGGI = datetime.now(ROME).date()
FIXTURE_415 = (Path(__file__).parent / "fixtures" / "provvedimenti" / "lavoro_415.txt").read_text(encoding="utf-8")


def _it(day: date) -> str:
    return f"{day:%d/%m/%Y}"


def _comunicazione(descrizione: str, oggetto: str, giorno: date, ora: str = "09:30", *, rg: str = "731/2026") -> dict:
    contesto = f"Oggetto: {oggetto} Descrizione: {descrizione}"
    return {
        "headers": {"subject": f"POSTA CERTIFICATA: COMUNICAZIONE {rg}/LAV", "date": "Tue, 03 Nov 2026 08:28:38 +0100"},
        "body": {"text": f"Comunicazione di cancelleria Numero di Ruolo generale: {rg} {contesto}"},
        "procedural_profile": {
            "numero_rg": rg,
            "udienza_data_ora": f"{_it(giorno)} {ora}",
            "oggetto_evento": oggetto,
            "descrizione_evento": descrizione,
            "fonte_certa": True,
            "documenti_letti": ["Comunicazione.xml"],
        },
        "procedural_dates": [{"date": giorno.isoformat(), "label": "termine", "context": contesto, "confidence": 0.8}],
    }


# ── 1. Note in sostituzione dell'udienza: termine perentorio, non udienza ─────────────


def test_comunicazione_note_in_sostituzione_diventa_termine_perentorio_127_ter():
    giorno = OGGI + timedelta(days=40)
    parsed = _comunicazione(
        f"REVOCATA UDIENZA E FISSATO TERMINE PER NOTE IN SOST. UDIENZA il {_it(giorno)} 09:30, ADEMPIMENTI",
        "REVOCA UDIENZA E FISSAZIONE TERMINE PER NOTE IN SOST. UDIENZA", giorno,
    )
    proposta = pp.build_deadline_proposal(parsed, event_type="comunicazione_cancelleria", issues=[], deposit_lifecycle={})
    assert proposta["deadline_kind"] == "termine" and proposta["note_127_ter"] is True
    assert proposta["due_date"] == giorno.isoformat() and proposta["event_time"] == ""
    assert proposta["title"].startswith("Deposito note scritte ex art. 127-ter c.p.c.")
    campi = pp._legal_deadline_scadenza_fields(proposta)
    assert campi["perentorio"] is True and campi["profile_code"] == "NOTE_127_TER"
    assert pp._pec_deadline_tipo(proposta, pp._remote_hearing_deadline_extra({}, proposta), proposta["title"]) == "TERMINE_PERENTORIO"
    assert pp._remote_hearing_deadline_extra({}, proposta)["hearing_mode"] == "note_scritte"


def test_termine_perentorio_scritto_nell_annotazione_prevale_sull_udienza_sostituita():
    udienza, termine = OGGI + timedelta(days=45), OGGI + timedelta(days=40)
    descrizione = (f"RINVIATA UDIENZA PER MANCATA COMPARIZIONE PARTI AL {_it(udienza)} ORE 00:00 Annotazioni: il GE rinvia "
                   f"all'udienza del {udienza:%d.%m.%Y} che sostituisce con il deposito di note scritte ex art.127 ter c.p.c. "
                   f"entro il termine perentorio del {termine:%d.%m.%Y}")
    parsed = _comunicazione(descrizione, "RINVIO DI UDIENZA PER MANCATA COMPARIZIONE PARTI", udienza, "00:00")
    parsed["procedural_dates"] = [
        {"date": termine.isoformat(), "label": "termine", "context": descrizione, "confidence": 0.8},
        {"date": udienza.isoformat(), "label": "UDIENZA", "context": descrizione, "confidence": 0.8},
    ]
    proposta = pp.build_deadline_proposal(parsed, event_type="comunicazione_cancelleria", issues=[], deposit_lifecycle={})
    assert proposta["note_127_ter"] and proposta["due_date"] == termine.isoformat()
    assert proposta["udienza_sostituita"] == udienza.isoformat()


def test_richiamo_storico_del_127_ter_e_l_udienza_ordinaria_restano_udienze():
    giorno = OGGI + timedelta(days=60)
    rinvio = _comunicazione(f"RINVIATO AD ALTRA UDIENZA DI DISCUSSIONE IL {_it(giorno)} 09:00 in presenza "
                            "Già disposta la trattazione scritta ex art. 127-ter c.p.c. per la precedente udienza.",
                            "RINVIO AD ALTRA UDIENZA DI DISCUSSIONE", giorno, "09:00")
    assert not evento_note_127_ter(rinvio["procedural_profile"])
    fissazione = _comunicazione(f"FISSATA UDIENZA DI COMPARIZIONE PARTI IL {_it(giorno)} 09:30 in presenza",
                                "FISSAZIONE UDIENZA", giorno)
    proposta = pp.build_deadline_proposal(fissazione, event_type="comunicazione_cancelleria", issues=[], deposit_lifecycle={})
    assert proposta["deadline_kind"] == "udienza" and not proposta.get("note_127_ter")


def test_opposizione_cinque_giorni_dalla_comunicazione_e_non_dalla_riassegnazione():
    profilo = {"descrizione_evento": "FISSATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il 20/05/2027 00:00, ADEMPIMENTI"}
    assert apre_opposizione(profilo)
    assert not apre_opposizione({"descrizione_evento": "RIASSEGNATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il 23/11/2026"})
    # 03/11/2026 + 5 = domenica 08/11: proroga al lunedì 09/11 (art. 155 c.p.c.); lavoro senza sospensione feriale.
    voce = proposta_opposizione(date(2026, 11, 3), lavoro=True, oggi=date(2026, 11, 3))
    assert voce is not None and voce.code == CODICE_OPPOSIZIONE_127_TER and voce.due_date == "2026-11-09"
    assert voce.perentorio and "127-ter, comma 2" in voce.norm
    assert proposta_opposizione(date(2026, 11, 3), lavoro=True, oggi=date(2026, 11, 10)) is None


def test_proponente_legale_riconosce_l_evento_di_cancelleria_come_127_ter():
    parsed = _comunicazione("REVOCATA UDIENZA E FISSATO TERMINE PER NOTE IN SOST. UDIENZA il 02/12/2026 09:30, ADEMPIMENTI",
                            "REVOCA UDIENZA E FISSAZIONE TERMINE PER NOTE IN SOST. UDIENZA", date(2026, 12, 2))
    legale = propose_from_parsed(parsed, event_type="comunicazione_cancelleria", comunicazione_date="2026-11-03")
    assert legale and legale["template_code"] == "CIV_OPPOSIZIONE_127_TER" and legale["deadline"] == "2026-11-09"
    riassegnato = _comunicazione("RIASSEGNATO TERMINE PER NOTE IN SOSTITUZIONE UDIENZA il 23/11/2026 14:00",
                                 "RIASSEGNAZIONE TERMINE PER NOTE IN SOSTITUZIONE UDIENZA", date(2026, 11, 23))
    assert propose_from_parsed(riassegnato, event_type="comunicazione_cancelleria", comunicazione_date="2026-11-03") is None


# ── 2. Udienze superate: chiuse con traccia, mai doppioni ─────────────────────────────


def _voce(id_: str, giorno: date, *, tipo: str = "UDIENZA", stato: str = "APERTO", note: str = "PEC_AUDIT:pec_x", fascicolo: str = "F1"):
    return SimpleNamespace(id=id_, tipo=tipo, stato=stato, data_scadenza=giorno.isoformat(), note=note, id_fascicolo=fascicolo)


def test_anticipazione_chiude_l_udienza_successiva_e_le_note_quella_dello_stesso_giorno():
    vecchia, nuova = OGGI + timedelta(days=300), OGGI + timedelta(days=37)
    voci = [_voce("A", vecchia), _voce("B", nuova), _voce("M", vecchia, note="inserita a mano"), _voce("X", vecchia, fascicolo="F2")]
    esito = udienze_superate(voci, fascicolo_id="F1", nuova_data=nuova, cambio=ANTICIPATA, oggi=OGGI, escludi={"B"})
    assert [v.id for v in esito.voci] == ["A"] and "anticipata" in esito.motivo
    note = udienze_superate(voci, fascicolo_id="F1", nuova_data=nuova, cambio=NOTE_127_TER, oggi=OGGI, escludi={"N"})
    assert [v.id for v in note.voci] == ["B"]
    riga = riga_traccia(origine="pec_y", cambio=NOTE_127_TER, nuova_data=nuova, nuova_voce="N")
    assert riga.startswith("UDIENZA_SUPERATA:pec_y") and "127-ter" in riga


def test_rinvio_con_piu_udienze_candidate_non_sceglie():
    voci = [_voce("A", OGGI + timedelta(days=10)), _voce("B", OGGI + timedelta(days=20))]
    esito = udienze_superate(voci, fascicolo_id="F1", nuova_data=OGGI + timedelta(days=90), cambio=RINVIATA, oggi=OGGI)
    assert esito.voci == () and "più udienze" in esito.motivo


def test_agenda_anticipazione_seleziona_l_udienza_successiva():
    nuova, vecchia = OGGI + timedelta(days=37), OGGI + timedelta(days=300)
    change = detect_schedule_change({"oggetto_evento": "ANTICIPAZIONE UDIENZA",
                                     "descrizione_evento": f"UDIENZA ANTICIPATA AL {_it(nuova)} 09:30"})
    assert change is not None and change.kind == "udienza_anticipata"
    item = SimpleNamespace(id="AP1", titolo=f"Fissazione udienza di discussione - {_it(vecchia)}", tipo="UDIENZA", stato="PROGRAMMATO",
                           data_ora=f"{vecchia.isoformat()}T09:30:00", note="Fascicolo: F1", procedimento="RG 731/2026",
                           external_uid="")
    selected, _ = select_rescheduled_appointments([item], fascicolo_id="F1", rg="731/2026", change=change,
                                                  received_on=OGGI, message_id="pec_new")
    assert selected == [item]


# ── 3. Le ricevute non creano udienze ─────────────────────────────────────────────────


def test_ricevuta_di_deposito_note_in_sostituzione_non_crea_udienze():
    parsed = {
        "headers": {"subject": "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO: Note in sostituzione udienza 23.11.2026.pdf RG: 731/2026"},
        "body": {"text": "Ricevuta di accettazione del deposito telematico. Note in sostituzione udienza https://pst.giustizia.it"},
        "pec_receipt": {"type": ""},
    }
    capito = build_legal_event_understanding(parsed, {"event_type": "pct_deposito"})
    assert capito.get("hearings") == []
    consegna = dict(parsed, headers={"subject": "CONSEGNA: DEPOSITO TELEMATICO: Note.pdf"}, pec_receipt={"type": "avvenuta_consegna"})
    assert build_legal_event_understanding(consegna, {}).get("hearings") == []


# ── 4. Notifiche L. 53/1994: tutte le forme reali dell'oggetto ─────────────────────────


def test_oggetti_reali_della_notifica_l53():
    for oggetto in (
        "Notificazione ai sensi della legge n. 53/1994 e succ. mod.",
        "notificazione ai sensi della legge n. 53 del 1994",
        "Notificazione ai sensi dell' articolo 3-bis della legge 53/94-",
        "NOTIFICAZIONE AI SENSI DELLA L. 53/1994",
    ):
        assert oggetto_di_notifica_l53(oggetto), oggetto
    for oggetto in ("POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO: ricorso (originale notificato).pdf",
                    "Notifica avvenuta registrazione protocollo n. 25379", "Notificazione ai sensi della legge n. 531/1994"):
        assert not oggetto_di_notifica_l53(oggetto), oggetto


# ── 5. Solo i termini della parte assistita ────────────────────────────────────────────


def test_studio_del_ricorrente_non_riceve_la_costituzione_del_convenuto():
    assert ruolo_cliente("Rossi Maria", attore="ROSSI MARIA", convenuto="MINISTERO DELL'ISTRUZIONE E DEL MERITO") == "ricorrente"
    assert ruolo_cliente("Ministero", attore="ROSSI MARIA", convenuto="MINISTERO DELL'ISTRUZIONE") == "resistente"
    assert ruolo_cliente("Bianchi Luca", attore="ROSSI MARIA", convenuto="VERDI SRL") == ""
    assert spetta_al_cliente("parti", "ricorrente") and not spetta_al_cliente("convenuto", "ricorrente")
    def codici(ruolo: str) -> list[str]:
        esito = esamina_provvedimento(FIXTURE_415, oggi=date(2026, 11, 2), ruolo_cliente=ruolo)
        return sorted(v.codice for v in esito.voci if v.codice)

    assert "LAV_416_COSTITUZIONE" in codici("")
    assert "LAV_416_COSTITUZIONE" not in codici("ricorrente") and "LAV_415_NOTIFICA_DIECI_GIORNI" in codici("ricorrente")
    assert "LAV_416_COSTITUZIONE" in codici("resistente") and "LAV_415_NOTIFICA_DIECI_GIORNI" not in codici("resistente")


# ── 6. Catalogo: la memoria della P.A. non è il decreto che cita ───────────────────────

MEMORIA_PA = """Ministero dell'Istruzione e del merito Nr. 123/2023 R.G.L. Ufficio territoriale Ud. 22/03/2024-h.9.20

TRIBUNALE DI ROVIGO

Sezione Lavoro

Nel procedimento R.G. Lav. nr. 123/2023 promosso da:
1) ROSSI MARIA, rappresentata e difesa dall'avv. Mario Bianchi
RICORRENTE

contro MINISTERO DELL'ISTRUZIONE E DEL MERITO, rappresentato e difeso ai sensi dell'art. 417 bis c.p.c.
RESISTENTE

Nel procedimento promosso con ricorso ex art. 414 c.p.c. depositato e notificato unitamente al pedissequo decreto di
fissazione dell'udienza, l'Amministrazione resistente si costituisce depositando l'odierna
MEMORIA DIFENSIVA ex art. 416 c.p.c.

La ricorrente ha chiesto il riconoscimento del preteso diritto alla Carta del docente. Si chiede il rigetto.
"""


def test_memoria_di_costituzione_della_pa_non_e_un_decreto_di_fissazione():
    esito = _classify_indexed_content(MEMORIA_PA)
    assert esito.label == "Memoria difensiva ex art. 416 c.p.c." and esito.section == "atti"
    decreto = ("TRIBUNALE DI ROVIGO\nSezione lavoro\nDECRETO DI FISSAZIONE DELL'UDIENZA\nIl giudice, letto il ricorso ex art. 414 "
               "c.p.c., fissa l'udienza di discussione del 15/01/2027 ore 9.30 e dispone la notifica.\n")
    assert _classify_indexed_content(decreto).label == "Decreto di fissazione udienza"


# ── 7. Letture: date passate, eventi, specifiche DGSIA, marcatori ─────────────────────


def _anomalia(valore: str, *, proposto: str = "", campo: str = "termine") -> Anomalia:
    return Anomalia(id="A1", tipo="documento", oggetto_id="D1", sha256="0" * 64, lettore="documenti", campo=campo,
                    valore_letto=valore, valore_proposto=proposto, contesto="Cass. civ., sez. lav., 15/10/2020, n. 22401",
                    motivo="", codice="data_sospetta", gravita="media")


def test_riconvalida_chiude_le_date_passate_e_lascia_le_future():
    contesto = {"oggi": date(2026, 11, 8), "anno_riferimento": 2026, "data_minima": None}
    assert "è passata" in regola_superata(_anomalia("15/10/2020"), contesto=contesto)
    assert "è passata" not in regola_superata(_anomalia("15/12/2026"), contesto=contesto)
    # giorno e mese invertiti: la lettura è passata ma la correzione è futura, decide l'avvocato
    assert "è passata" not in regola_superata(_anomalia("12/01/2026", proposto="01/12/2026"), contesto=contesto)


def test_evento_del_registro_letture_non_riuscito_resta_nel_log(caplog):
    with caplog.at_level(logging.WARNING, logger="pct.pec_pipeline"):
        pp._registra_evento_letture_fallito("pec_collegata", "F1", RuntimeError("archivio non raggiungibile"))
    assert "pec_collegata" in caplog.text and "F1" in caplog.text
    assert pp.EVENTI_LETTURE_FALLITI[-1]["evento"] == "pec_collegata"


def test_specifiche_dgsia_vigenti_e_testo_senza_marcatori():
    sorgente = Path(pp.__file__).read_text(encoding="utf-8")
    assert "Provvedimento DGSIA 16 aprile 2014" not in sorgente
    assert "Provvedimento DGSIA 7 agosto 2024 (in vigore dal 30/09/2024)" in sorgente
    testo = plain_markdown("||STUDIO LEGALE ROSSI||\n*Avv. Mario Rossi*\n| Data | Importo |\n|---|---:|\n| 12/03/2026 | 5*3 |")
    assert testo == "STUDIO LEGALE ROSSI\nAvv. Mario Rossi\nData  Importo\n12/03/2026  5*3"
