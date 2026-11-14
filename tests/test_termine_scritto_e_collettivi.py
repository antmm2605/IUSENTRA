"""Termine scritto dal giudice, perentorietà dichiarata, rischio di estinzione, provvedimenti collettivi.

Esempi fittizi (nomi e numeri inventati) costruiti sui casi del collaudo del 10/11/2026: verbale di
esecuzione con rinvio ex art. 631 c.p.c. sostituito da note (art. 127-ter c.p.c.), comunicazione
collettiva del G.E. con due gruppi di cause, decreti di cognizione e lavoro.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from legal_ocr.formulario.date import trova_date
from pct.archivio_letture.collaudo import Contesto
from pct.archivio_letture.motore_documenti import leggi_testo
from pct.archivio_letture.rettifica_termini import piano_rettifiche, riga_intatta
from pct.archivio_letture.riletture_mirate import REGOLE_TERMINE_SCRITTO, oggetti_da_rileggere
from pct.provvedimenti.collettivi import allegati_per_il_ruolo, clausole_di_altre_cause, gruppi_di_cause
from pct.provvedimenti.collettivi import testo_per_il_ruolo as per_il_ruolo
from pct.provvedimenti.termine_scritto import (
    DataLetta, perentorio_dichiarato, rischio_estinzione, termine_note_127_ter, udienza_tenuta_o_rinviata,
)
from pct.registro_letture.fatti_repository import Fatto
from pct.scadenziario import PrioritaTermine, Scadenza, TipoTermine

VERBALE_631 = (
    "Tribunale di Alfa - Cancelleria Esecuzioni Mobiliari Proc n. 111/2025\n"
    "All'udienza del 2.11.2026 tenuta dal G.E. dott. Rossi, viene chiamata la causa iscritta al n. 111/2025 R.G.E. "
    "tra BETA SRL contro GAMMA SPA\nIl G.E.\nPoiché nessuno è presente rinvia all'udienza del 21.12.2026 che "
    "sostituisce con il deposito di note scritte ex art. 127 ter c.p.c. entro il termine perentorio del\n\n16.12.2026. "
    "Ai sensi dell'art. 631 c.p.c.\nSi comunichi"
)
COLLETTIVO = (
    "Tribunale di Alfa Cancelleria Esecuzioni Mobiliari Proc. n. 111/2025 R.G.Es Il Giudice dell'Esecuzione comunica che "
    "l'udienza del 6.7.2026 non sarà tenuta; le cause sono rinviate come segue: I procedimenti recanti n. 10/24; 22/25; "
    "111/25; 300/26 sono rinviati all'udienza del 2.11.2026 che sarà trattata in presenza. I procedimenti recanti "
    "n. 5/21; 83/25 + sub.1; 400/25 sono rinviati all'udienza del 9.11.2026 che sostituisce con il deposito di note "
    "scritte ex art. 127 ter c.p.c. entro il termine perentorio del 4.11.2026\nAlfa 3.7.2026"
)


def _contesto(numero: str = "111", anno: str = "2025") -> Contesto:
    return Contesto(oggi=date(2026, 11, 10), anno_riferimento=2025, numero_rg=numero, anno_rg=anno,
                    ufficio_giudiziario="Tribunale di Alfa",
                    date_note={"2026-12-16": ["agenda"], "2026-12-21": ["agenda"], "2026-11-02": ["agenda"],
                               "2026-11-04": ["agenda"], "2026-11-09": ["agenda"]})


def _date(testo: str) -> list[DataLetta]:
    campi = {"2026-11-02": "udienza", "2026-12-21": "udienza", "2026-12-16": "termine"}
    return [DataLetta(d.inizio, d.fine, campi.get(d.data.isoformat(), "udienza")) for d in trova_date(testo)]


# ---- termine scritto -------------------------------------------------------------

def test_il_termine_per_le_note_e_quello_scritto_dal_giudice_non_l_udienza():
    date_lette = _date(VERBALE_631)
    indice = termine_note_127_ter(VERBALE_631, date_lette)
    assert indice is not None
    assert VERBALE_631[date_lette[indice].inizio:date_lette[indice].fine] == "16.12.2026"


def test_l_udienza_tenuta_non_e_mai_il_termine():
    prima = trova_date(VERBALE_631)[0]
    assert udienza_tenuta_o_rinviata(VERBALE_631, prima.fine)
    rinviata = "l'udienza del 6.7.2026 non sarà tenuta"
    assert udienza_tenuta_o_rinviata(rinviata, rinviata.index("2026") + 4)


def test_decreto_senza_termine_distinto_le_note_scadono_il_giorno_dell_udienza_sostituita():
    testo = "Il giudice dispone che l'udienza del 15/01/2027 sia sostituita dal deposito di note scritte ex art. 127-ter c.p.c."
    date_lette = [DataLetta(d.inizio, d.fine, "udienza") for d in trova_date(testo)]
    assert termine_note_127_ter(testo, date_lette) == 0


def test_perentorio_dichiarato_con_ogni_preposizione():
    for frase in ("entro il termine perentorio del 16.12.2026", "termine perentorio sino al 16.12.2026",
                  "assegna termine perentorio di giorni trenta, fino al 16.12.2026",
                  "da depositare entro il 16.12.2026, termine perentorio", "a pena di decadenza entro il 16.12.2026"):
        trovata = trova_date(frase)[0]
        assert perentorio_dichiarato(frase, trovata.inizio, trovata.fine), frase
    ordinario = "assegna termine sino al 16.12.2026 per il deposito di documenti"
    trovata = trova_date(ordinario)[0]
    assert not perentorio_dichiarato(ordinario, trovata.inizio, trovata.fine)


def test_rischio_di_estinzione_esecuzione_e_cognizione():
    esecuzione = rischio_estinzione(VERBALE_631)
    assert esecuzione is not None and esecuzione.norma == "art. 631 c.p.c."
    cognizione = rischio_estinzione("Nella causa civile n. 5/2026, nessuna delle parti è comparsa: il giudice rinvia ex art. 181 c.p.c.")
    assert cognizione is not None and cognizione.norma == "art. 181 c.p.c."
    assert rischio_estinzione("Il giudice rinvia all'udienza del 3/3/2027 per la precisazione delle conclusioni.") is None


# ---- provvedimenti collettivi -----------------------------------------------------

def test_collettivo_due_gruppi_e_clausola_dell_altro_gruppo():
    gruppi = gruppi_di_cause(COLLETTIVO)
    assert len(gruppi) == 2 and (111, 2025) in gruppi[0].ruoli and (83, 2025) in gruppi[1].ruoli
    altre = clausole_di_altre_cause(COLLETTIVO, "111", "2025")
    assert len(altre) == 1 and "4.11.2026" in COLLETTIVO[altre[0].inizio:altre[0].fine]
    ridotto = per_il_ruolo(COLLETTIVO, "111", "2025")
    assert len(ridotto) == len(COLLETTIVO) and "4.11.2026" not in ridotto and "2.11.2026 che sarà trattata in presenza" in ridotto
    # per una causa dell'altro gruppo vale il contrario
    assert "4.11.2026" in per_il_ruolo(COLLETTIVO, "83", "2025") and "in presenza" not in per_il_ruolo(COLLETTIVO, "83", "2025")


def test_ruolo_assente_o_testo_non_collettivo_restano_intatti():
    assert per_il_ruolo(COLLETTIVO, "999", "2025") == COLLETTIVO
    assert per_il_ruolo(VERBALE_631, "111", "2025") == VERBALE_631
    allegati = [{"ocr_text": COLLETTIVO, "filename": "comunicazione.pdf"}]
    assert "4.11.2026" not in allegati_per_il_ruolo(allegati, "111/2025/EC")[0]["ocr_text"]
    assert allegati[0]["ocr_text"] == COLLETTIVO  # l'originale non si tocca


# ---- motore delle letture ---------------------------------------------------------

def _date_lette(testo: str, contesto: Contesto) -> dict[tuple[str, str], Fatto]:
    return {(f.campo, f.valore[:10]): f for f in leggi_testo(testo, origine="indice", contesto=contesto) if f.categoria == "data"}


def test_motore_verbale_631_termine_note_perentorio_e_udienza_resta_udienza():
    fatti = _date_lette(VERBALE_631, _contesto())
    note = fatti[("termine", "2026-12-16")]
    assert note.etichetta.startswith("Deposito note scritte ex art. 127-ter c.p.c. — 16/12/2026 — perentorio, art. 631")
    assert len(note.etichetta) <= 120
    assert {p["codice"] for p in note.prove} >= {"istituto", "perentorieta_documentata", "rischio_estinzione"}
    assert ("udienza", "2026-12-21") in fatti and ("termine", "2026-12-21") not in fatti
    assert ("udienza", "2026-11-02") in fatti and ("termine", "2026-11-02") not in fatti


def test_motore_collettivo_respinge_le_date_dell_altro_gruppo():
    fatti = _date_lette(COLLETTIVO, _contesto())
    assert fatti[("udienza", "2026-11-02")].verifica != "respinta"
    assert fatti[("termine", "2026-11-04")].verifica == "respinta"
    assert any(p["codice"] == "provvedimento_collettivo" for p in fatti[("termine", "2026-11-04")].prove)
    assert fatti[("udienza", "2026-11-09")].verifica == "respinta"
    # nessuna trattazione scritta per la causa 111/2025
    assert not any("127-ter" in f.etichetta for f in fatti.values() if f.verifica != "respinta")


def test_motore_collettivo_per_la_causa_dell_altro_gruppo():
    fatti = _date_lette(COLLETTIVO, _contesto("83", "2025"))
    assert fatti[("udienza", "2026-11-02")].verifica == "respinta"
    assert fatti[("termine", "2026-11-04")].verifica != "respinta"


# ---- riletture mirate e rettifica delle scadenze ----------------------------------

def _fatto(**campi) -> Fatto:
    base = dict(categoria="data", campo="termine", valore="2026-12-16", valore_letto="16.12.2026", etichetta="Termine del 16/12/2026",
                contesto="", verifica="verificata", prove=[], tipo="documento", oggetto_id="DOC1", sha256="abc", id="fat_1")
    base.update(campi)
    fatto = Fatto(**{k: v for k, v in base.items() if k not in {"tipo", "oggetto_id", "sha256", "id"}})
    fatto.tipo, fatto.oggetto_id, fatto.sha256, fatto.id = base["tipo"], base["oggetto_id"], base["sha256"], base["id"]
    return fatto


def test_riletture_mirate_una_volta_sola():
    fatti = [_fatto(contesto="note scritte ex art. 127 ter entro il termine perentorio del 16.12.2026"),
             _fatto(campo="udienza", valore="2026-12-21", contesto="rinvia all'udienza del 21.12.2026 che sostituisce", id="fat_2")]
    assert oggetti_da_rileggere(fatti, {("documento", "DOC1"): "motore-v16"}) == {
        ("documento", "DOC1"): "trattazione scritta: il termine per le note è quello assegnato dal giudice (art. 127-ter c.p.c.)"}
    assert oggetti_da_rileggere(fatti, {("documento", "DOC1"): "motore-v16+" + REGOLE_TERMINE_SCRITTO}) == {}
    elenco = [_fatto(contesto="n. 10/24; 22/25; 111/25 sono rinviati all'udienza del 2.11.2026")]
    assert ("documento", "DOC1") in oggetti_da_rileggere(elenco, {("documento", "DOC1"): "motore-v16"})


def _riga(titolo: str, giorno: str, **campi) -> SimpleNamespace:
    base = dict(id="sc1", titolo=titolo, data_scadenza=giorno, stato="APERTO", id_utente_responsabile="", perentorio=False,
                note="Data verificata nell’archivio delle letture. Creata dalla lettura automatica dei documenti: da confermare.\n"
                     "ARCHIVIO_FATTO:fat_vecchio\nFonte: documento:DOC1")
    base.update(campi)
    return SimpleNamespace(**base)


def test_rettifica_aggiorna_il_termine_riqualificato_e_annulla_l_udienza_presa_per_termine():
    nota = _fatto(etichetta="Deposito note scritte ex art. 127-ter c.p.c. — 16/12/2026 — perentorio, art. 631: senza note si estingue",
                  prove=[{"codice": "istituto", "esito": "ok", "dettaglio": "note_127_ter"},
                         {"codice": "perentorieta_documentata", "esito": "ok", "dettaglio": "art. 127-ter"},
                         {"codice": "rischio_estinzione", "esito": "ok", "dettaglio": "art. 631 c.p.c."}])
    udienza = _fatto(campo="udienza", valore="2026-12-21", etichetta="Udienza del 21/12/2026", id="fat_2")
    righe = [_riga("Termine del 16/12/2026", "2026-12-16"),
             _riga("Deposito note scritte ex art. 127-ter c.p.c. — 21/12/2026", "2026-12-21", id="sc2")]
    piano = {r.scadenza_id: r for r in piano_rettifiche(righe, [nota, udienza], oggi=date(2026, 11, 10))}
    assert piano["sc1"].azione == "aggiorna" and piano["sc1"].campi["perentorio"] is True
    assert piano["sc1"].campi["tipo"] == "TERMINE_PERENTORIO" and piano["sc1"].campi["titolo"].startswith("Deposito note scritte")
    assert piano["sc2"].azione == "annulla"


def test_rettifica_annulla_il_termine_di_altre_cause_anche_decorso_e_rispetta_l_avvocato():
    respinto = _fatto(valore="2026-11-04", verifica="respinta",
                      prove=[{"codice": "provvedimento_collettivo", "esito": "respinta", "dettaglio": "Provvedimento collettivo: altre cause"}])
    riga = _riga("Termine del 04/11/2026", "2026-11-04")
    assert [r.azione for r in piano_rettifiche([riga], [respinto], oggi=date(2026, 11, 10))] == ["annulla"]
    toccata = _riga("Termine del 04/11/2026", "2026-11-04", id_utente_responsabile="avv1")
    assert not riga_intatta(toccata) and piano_rettifiche([toccata], [respinto], oggi=date(2026, 11, 10)) == []
    rinominata = _riga("Note per il G.E.", "2026-11-04")
    assert piano_rettifiche([rinominata], [respinto], oggi=date(2026, 11, 10)) == []


def test_termine_perentorio_e_sempre_critico():
    lontano = Scadenza(titolo="Note", tipo=TipoTermine.TERMINE_PERENTORIO, data_scadenza="2099-12-16", perentorio=True)
    lontano.aggiorna_priorita()
    assert lontano.priorita == PrioritaTermine.CRITICA
    ordinario = Scadenza(titolo="Note", tipo=TipoTermine.ADEMPIMENTO, data_scadenza="2099-12-16")
    ordinario.aggiorna_priorita()
    assert ordinario.priorita == PrioritaTermine.BASSA


def test_agenda_udienza_in_presenza_del_gruppo_della_causa():
    from pct.archivio_letture.rettifica_termini import piano_agenda

    presenza = _fatto(campo="udienza", valore="2026-11-02", etichetta="Udienza del 02/11/2026", tipo="allegato_pec",
                      contesto="111/25; 300/26 sono rinviati all'udienza del 2.11.2026 che sarà trattata in presenza.")
    automatico = SimpleNamespace(id="A1", tipo="UDIENZA", external_provider="pec_audit", hearing_mode="note_scritte",
                                 luogo="Trattazione scritta", data_ora="2026-11-02T09:30:00", tribunale="Tribunale di Alfa")
    piano = piano_agenda([automatico], [presenza])
    assert [r.campi["hearing_mode"] for r in piano] == ["presenza"] and piano[0].campi["luogo"] == "Tribunale di Alfa"
    dell_avvocato = SimpleNamespace(**{**automatico.__dict__, "luogo": "Aula 3"})
    assert piano_agenda([dell_avvocato], [presenza]) == []
    note = _fatto(valore="2026-11-02", etichetta="Deposito note scritte ex art. 127-ter c.p.c. — 02/11/2026",
                  prove=[{"codice": "istituto", "esito": "ok", "dettaglio": "note_127_ter"}], id="fat_n")
    assert piano_agenda([automatico], [presenza, note]) == []
