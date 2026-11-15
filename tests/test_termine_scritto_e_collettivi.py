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
    assert note.etichetta == "Deposito note scritte ex art. 127-ter c.p.c. — 16/12/2026 — perentorio, art. 631: rischio di estinzione"
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
    assert piano["sc1"].campi["titolo"].endswith("art. 631: rischio di estinzione")
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


def test_agenda_ritira_solo_la_comparizione_sostituita_dallo_stesso_verbale():
    from pct.archivio_letture.rettifica_termini import piano_udienze_sostituite, sostituzioni_documentate

    data_rinvio = "2026-12-21T00:00:00"
    app = SimpleNamespace(id="A1", tipo="UDIENZA", stato="PROGRAMMATO", titolo="Rinvio udienza", data_ora=data_rinvio,
                          external_provider="pec_audit", external_profile_id="pec_scadenziario",
                          external_uid="PEC_AUDIT:msg1:deadline", hearing_mode="incerta",
                          durata_minuti=60, luogo="Modalità udienza da verificare",
                          external_hash=f"Rinvio udienza|{data_rinvio}|60|Modalità udienza da verificare|PEC_AUDIT:msg1|CONFIRMED|scheduler|",
                          external_source_url="",
                          note="PEC_AUDIT:msg1\nOrganizzatore: scheduler\nSincronizzato da: Pec Audit\nUID esterno: PEC_AUDIT:msg1:deadline")
    avviso = _riga("Rinvio udienza", "2026-12-21", id="UD1", tipo="UDIENZA",
                   id_appuntamento="A1", deadline_profile_code="PEC_AUTO_PRESIDIO", source_message_id="msg1",
                   id_utente_responsabile="scheduler", note="PEC_AUDIT:msg1\nEvento di cancelleria")
    termine = _riga("Deposito note", "2026-12-16", id="TN1", perentorio=True,
                    hearing_mode_source="documento:DOC1")
    prove = [
        _fatto(campo="udienza", valore="2026-12-21", valore_letto="21.12.2026",
               contesto="rinvia all’udienza del 21.12.2026 che sostituisce con il deposito di noet scritte"),
        _fatto(id="fat_2", prove=[{"codice": "istituto", "esito": "ok", "dettaglio": "note_127_ter"},
                                  {"codice": "perentorieta_documentata", "esito": "ok"}]),
    ]
    oggi = date(2026, 11, 15)
    sostituzioni = sostituzioni_documentate(prove)
    piano = piano_udienze_sostituite([avviso, termine], [app], sostituzioni, {"DOC1": "msg1"}, oggi=oggi)
    assert [(scadenza.scadenza_id, agenda.scadenza_id) for scadenza, agenda in piano] == [("UD1", "A1")]
    assert "16/12/2026" in piano[0][1].motivo and len(piano[0][1].prove) == 2
    assert piano_udienze_sostituite([avviso, termine], [app], sostituzioni, {"DOC1": "altra-pec"}, oggi=oggi) == []
    app.note += "\nNota aggiunta dallo studio"
    assert piano_udienze_sostituite([avviso, termine], [app], sostituzioni, {"DOC1": "msg1"}, oggi=oggi) == []


def test_prossima_udienza_usa_il_termine_per_le_note_con_fonte():
    from pct.procedura_fasi.udienze import prossima_udienza

    rinvio = {"data_ora": "2026-12-21T00:00:00", "tipo": "UDIENZA", "stato": "ANNULLATO"}
    note = {"data": "2026-12-16", "tipo": "TERMINE_PERENTORIO", "stato": "APERTO", "hearing_mode": "note_scritte",
            "hearing_mode_source": "documento:VERBALE", "titolo": "Deposito note scritte ex art. 127-ter c.p.c."}
    oggi = date(2026, 11, 15)
    assert prossima_udienza(scadenze=[note], appuntamenti=[rinvio], oggi=oggi) == date(2026, 12, 16)
    assert prossima_udienza(scadenze=[dict(note, hearing_mode_source="")], appuntamenti=[rinvio], oggi=oggi) is None
    assert prossima_udienza(scadenze=[dict(note, stato="BOZZA")], appuntamenti=[rinvio], oggi=oggi) is None


def test_agenda_archivio_ritira_solo_la_voce_intatta_del_documento_giusto():
    from pct.archivio_letture.rettifica_termini import piano_agenda_documentale_sostituita, sostituzioni_documentate

    fatti = [
        _fatto(campo="udienza", valore="2026-12-21", valore_letto="21.12.2026",
               contesto="rinvia all’udienza del 21.12.2026 che sostituisce con il deposito di note scritte"),
        _fatto(id="fat_t", prove=[{"codice": "istituto", "esito": "ok", "dettaglio": "note_127_ter"},
                                  {"codice": "perentorieta_documentata", "esito": "ok"}]),
    ]
    sostituzioni = sostituzioni_documentate(fatti)
    automatico = SimpleNamespace(
        id="A1", stato="PROGRAMMATO", data_ora="2026-12-21T00:00:00",
        titolo="Udienza del 21/12/2026 ore 00:00",
        note="Data e ora verificate nell’archivio.\nARCHIVIO_FATTO:canon-1\nFonte: documento:DOC1",
    )
    oggi = date(2026, 11, 15)
    assert len(piano_agenda_documentale_sostituita([automatico], sostituzioni, oggi=oggi)) == 1
    assert piano_agenda_documentale_sostituita([automatico], {}, oggi=oggi) == []
    automatico.note += "\nUndici: appuntamento con il cliente."
    assert piano_agenda_documentale_sostituita([automatico], sostituzioni, oggi=oggi) == []


def test_le_date_di_una_pec_si_attribuiscono_al_ruolo_di_ogni_allegato():
    from pct.archivio_letture import Contesto, leggi_testo

    testo = (
        "Oggetto: CONSEGNA: Notificazione\nMittente: ricevute@example.test\n"
        "Destinatari: studio@example.test\nData: 18/05/2026\n\n"
        "Allegati leggibili:\n"
        "[Allegato: Decreto fissazione udienza.PDF; parte 1.5]\n"
        "Fissazione udienza discussione n. cronol. 5846/2026 del 18/05/2026 RG n. 1425/2026\n"
        "TRIBUNALE DI PALMI Sezione Lavoro\nIl giudice, letto il ricorso (RG 1425 /2026), "
        "visto l’art. 415 c.p.c.; FISSA per la comparizione personale l’udienza del 22/12/2026.\n"
        "[Allegato: Decreto fissazione udienza 2.PDF; parte 1.6]\n"
        "R.G. n. 1477 /2026 TRIBUNALE DI PALMI Sezione Lavoro\n"
        "Il giudice FISSA per la comparizione l’udienza del 17/12/2026."
    )
    contesto = Contesto(oggi=date(2026, 11, 15), numero_rg="1477", anno_rg="2026",
                        date_note={"2026-12-17": ["scadenziario"], "2026-12-22": ["agenda"]})
    fatti = [f for f in leggi_testo(testo, origine="indice", contesto=contesto) if f.campo == "udienza"]
    estranea = next(f for f in fatti if f.valore == "2026-12-22")
    pertinente = next(f for f in fatti if f.valore == "2026-12-17")
    assert estranea.verifica == "respinta"
    assert any(p["codice"] == "ruolo_allegato_pec" and "1425/2026" in p["dettaglio"] for p in estranea.prove)
    assert pertinente.verifica == "verificata"


def test_una_citazione_di_altro_ufficio_non_esclude_il_ricorso():
    from pct.archivio_letture.pertinenza_documentale import documenti_ufficio_incompatibile
    from pct.registro_letture.fatti_repository import Fatto

    prove = [{"codice": "ufficio_giudiziario", "esito": "respinta", "dettaglio": "Altro ufficio giudiziario"}]
    citazione = Fatto(categoria="ruolo", campo="numero_ruolo", valore="4593/2022", tipo="documento",
                     oggetto_id="RICORSO", posizione=4830, verifica="respinta", prove=prove)
    intestazione = Fatto(categoria="ruolo", campo="numero_ruolo", valore="1425/2026", tipo="documento",
                         oggetto_id="DECRETO", posizione=98, verifica="respinta", prove=prove)
    assert documenti_ufficio_incompatibile([citazione, intestazione]) == {"DECRETO"}
