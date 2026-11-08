"""Decreto di trattazione scritta che sostituisce «l'udienza già fissata» senza scriverne la data.

Caso reale del 02/11/2026: cinque PEC della cancelleria di un Tribunale, sezione lavoro, con lo
stesso «DECRETO PER IL DEPOSITO DI NOTE SCRITTE IN SOSTITUZIONE DELL'UDIENZA» (art. 127-ter
c.p.c.): termine perentorio «sino alla data della predetta udienza», nessuna data nel decreto,
invito al deposito «entro le ore 9.30 del giorno di scadenza». Il software non proponeva nulla.

Il testo di prova è il decreto reale estratto con pdftotext, con numero di ruolo, giudice e
città sostituiti da valori inventati (tests/fixtures/pec/decreto_note_scritte_127_ter.txt).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from email import message_from_bytes, policy
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from pct.agenda import Agenda, TipoAppuntamento
from pct.fascicolo_document_presidio import analyze_fascicolo_document_texts
from pct.fascicolo_lettura.prossimi_passi import prossimi_passi
from pct.note_127_ter import riconosci_decreto, udienza_riferita
from pct.note_127_ter.esame_pec import esamina_decreto_pec
from pct.note_127_ter.udienza_cartolare import segna_udienza_cartolare, tipo_udienza_iniziale
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine

ROME_TZ = ZoneInfo("Europe/Rome")
DECRETO = (Path(__file__).parent / "fixtures" / "pec" / "decreto_note_scritte_127_ter.txt").read_text(encoding="utf-8")
OGGI = date(2026, 11, 2)


def _udienza(giorno: str, *, fascicolo: str = "F1", ident: str = "A1", stato: str = "PROGRAMMATO") -> dict:
    return {"id": ident, "tipo": "UDIENZA", "stato": stato, "data_ora": giorno, "id_fascicolo": fascicolo}


# ── Riconoscimento del decreto ─────────────────────────────────────────


def test_il_decreto_reale_e_riconosciuto_senza_data_propria_con_le_09_30():
    decreto = riconosci_decreto(DECRETO)
    assert decreto is not None and decreto.senza_data
    assert decreto.ora_limite == "09:30"
    assert decreto.solo_istanze_conclusioni and decreto.indicazioni_richieste
    assert decreto.invito_prova_notifica and decreto.prova_telematica and decreto.prova_cartacea
    assert decreto.giorni_decisione == 30
    assert decreto.data_pronuncia == date(2026, 10, 31)
    # La copia senza data in calce è lo stesso decreto.
    assert riconosci_decreto(DECRETO.replace("Lontano, 31/10/2026", "")).senza_data
    # Una sentenza resa all'esito della trattazione scritta non apre termini per le note.
    assert riconosci_decreto("In nome del popolo italiano, all'esito della trattazione scritta ex art. 127-ter c.p.c. "
                             "in sostituzione dell'udienza, definitivamente pronunciando") is None


#: Materie con rito del c.p.c. (l'art. 127-ter vale per ogni rito civile): stesso decreto, sezione diversa.
_MATERIE_CPC = ("SEZIONE LAVORO", "SEZIONE CIVILE", "SEZIONE FAMIGLIA E MINORI", "SEZIONE IMPRESE")
#: Riti con una trattazione scritta propria, che non è l'art. 127-ter c.p.c.: il decreto non va preso.
#: Formule sintetiche dal testo delle norme (scritte il 02/11/2026, nessun dato dello studio):
#: - penale: art. 598-bis c.p.p., https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1988-09-22;447~art598bis
#: - amministrativo: art. 73 c.p.a., https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010-07-02;104~art73
_ALTRI_RITI = (
    "CORTE D'APPELLO, SEZIONE PENALE. Visto l'art. 598-bis c.p.p., la Corte procede in camera di consiglio senza la "
    "partecipazione delle parti, in sostituzione dell'udienza pubblica; il procuratore generale presenta le sue "
    "richieste e le parti possono presentare memorie scritte entro il termine di legge.",
    "TRIBUNALE AMMINISTRATIVO REGIONALE. Fissata l'udienza pubblica, le parti possono produrre documenti, memorie e "
    "note scritte di replica nei termini dell'art. 73 c.p.a. prima della predetta udienza.",
)


def test_riconoscimento_per_materia_preso_nei_riti_civili_e_non_negli_altri():
    for sezione in _MATERIE_CPC:
        assert riconosci_decreto(DECRETO.replace("SEZIONE LAVORO", sezione)).senza_data, sezione
    for testo in _ALTRI_RITI:
        assert riconosci_decreto(testo) is None, testo[:40]


def test_udienza_riferita_normalizza_date_con_e_senza_fuso_in_ora_italiana():
    agenda = [
        _udienza("2026-12-15T09:00:00+01:00"),
        _udienza("2026-10-20T09:00:00", ident="A0"),  # passata: non è l'udienza sostituita
        _udienza("2026-11-01T23:30:00+00:00", ident="A2"),  # 02/11 00:30 a Roma: oggi, quindi candidata
    ]
    ambigua = udienza_riferita(appuntamenti=agenda, fascicolo_id="F1", oggi=OGGI)
    assert ambigua.esito == "ambigua" and ambigua.candidate == (date(2026, 11, 2), date(2026, 12, 15))
    unica = udienza_riferita(appuntamenti=agenda[:2], fascicolo_id="F1", oggi=OGGI, prossima_udienza="2026-12-15")
    assert (unica.giorno, unica.ora, unica.id_appuntamento) == (date(2026, 12, 15), "09:00", "A1")


# ── 1-2. Termine alle 09:30 sulla data dell'udienza, o «da verificare» ─────


def test_decreto_senza_data_e_udienza_futura_propone_il_termine_alle_09_30():
    esito = esamina_decreto_pec(DECRETO, oggi=OGGI, comunicata_il=OGGI, fascicolo_id="F1", rg="4711/2025",
                                appuntamenti=[_udienza("2026-12-15T09:00:00")])
    assert esito is not None and not esito.da_verificare
    [proposta] = esito.proposte
    assert proposta.due_date == "2026-12-15" and proposta.perentorio
    assert proposta.campi_scadenza["operational_due_at"] == "2026-12-15T09:30:00"
    assert proposta.campi_scadenza["hearing_mode"] == "note_scritte"
    assert proposta.campi_scadenza["id_appuntamento"] == "A1"
    assert proposta.dies_a_quo == OGGI.isoformat()
    # Senza l'invito delle 9.30 vale la fine del giorno di scadenza (art. 196-sexies disp. att. c.p.c.).
    senza_ora = esamina_decreto_pec(DECRETO.replace("entro le ore 9.30 del giorno di scadenza", "nel termine"),
                                    oggi=OGGI, fascicolo_id="F1", appuntamenti=[_udienza("2026-12-15")])
    assert senza_ora.proposte[0].campi_scadenza["operational_due_at"] == "2026-12-15T23:59:00"


def test_senza_udienza_futura_o_con_piu_udienze_nessuna_data_indovinata():
    nessuna = esamina_decreto_pec(DECRETO, oggi=OGGI, fascicolo_id="F1", appuntamenti=[_udienza("2026-10-01T09:00:00")])
    assert nessuna.proposte == [] and "non c'è un'udienza futura" in nessuna.da_verificare
    assert any(riga.startswith("Da verificare (art. 127-ter c.p.c.):") for riga in nessuna.righe_descrizione())
    due = esamina_decreto_pec(DECRETO, oggi=OGGI, fascicolo_id="F1",
                              appuntamenti=[_udienza("2026-12-15T09:00:00"), _udienza("2027-01-20T09:00:00", ident="A2")])
    assert due.proposte == [] and "15/12/2026, 20/01/2027" in due.da_verificare
    scollegata = esamina_decreto_pec(DECRETO, oggi=OGGI, appuntamenti=[_udienza("2026-12-15T09:00:00")])
    assert scollegata.proposte == [] and "non è ancora collegata" in scollegata.da_verificare


def test_termine_equivalente_gia_presente_nessuna_nuova_proposta():
    manuale = SimpleNamespace(id="S9", id_fascicolo="F1", data_scadenza="2026-12-15", deadline_profile_code="",
                              stato="APERTO", titolo="Termine per note in sostituzione udienza")
    esito = esamina_decreto_pec(DECRETO, oggi=OGGI, fascicolo_id="F1", appuntamenti=[_udienza("2026-12-15T09:00:00")],
                                scadenze=[manuale])
    assert esito.proposte == [] and esito.equivalente_id == "S9"


# ── 4. Checklist: prova della notifica per il ricorrente ───────────────


def _passi(*, parti: dict, documenti: list[dict] | None = None, pec_tutte: list[dict] | None = None, stato: str = "BOZZA"):
    scadenza = {
        "titolo": "Deposito note scritte ex art. 127-ter c.p.c. - RG 4711/2025", "data": "2026-12-15", "stato": stato,
        "note": "PEC_TERMINE_PROPOSTO:msg1:NOTE_127_TER", "descrizione": "deposito entro le ore 09:30, come invita il decreto",
    }
    passi, _ = prossimi_passi(
        intestazione={"stato_codice": "IN_CORSO", "cliente": "Mario Rossi", "parti": parti, "rg": "4711/2025",
                      "ufficio": "Tribunale di Lontano", "giudice": "Mario Bianchi", "avvocato": "Avv. Anna Verdi"},
        fase_letta={}, depositi_letti={"falliti": [], "in_corso": [], "tutti": []},
        notifiche_lette={"fallite": [], "aperte": [], "tutte": []},
        documenti_letti={"tutti": documenti or [], "da_verificare": [], "non_indicizzati": [], "totale": 0, "procura": True},
        scadenze=[scadenza], conformita={}, regia={}, economico_letto={}, pec_letto={"tutte": pec_tutte or []}, oggi=OGGI,
    )
    return passi


def test_ricorrente_con_resistente_non_costituita_ha_la_voce_della_prova_della_notifica():
    passi = _passi(parti={"ricorrente": ["Mario Rossi"], "resistente": ["Beta S.r.l."]},
                   documenti=[{"nome": "ricevuta_avvenuta_consegna_completa.eml", "etichetta": "Ricevuta"}])
    azioni = {passo["azione"]: passo for passo in passi}
    prova = next(passo for azione, passo in azioni.items() if "prova della notifica" in azione)
    assert ".eml" in prova["motivo"] and "ricevuta_avvenuta_consegna_completa.eml" in prova["motivo"]
    assert "attestazione di conformità" in prova["motivo"]
    assert prova["urgenza"] == 2  # scadenza fra 43 giorni: non «entro pochi giorni» (collaudo 08/11/2026)
    indicazioni = azioni["Riportare nelle note i dati che identificano la causa e l'udienza sostituita"]["motivo"]
    assert "verificare nel decreto le indicazioni specifiche" in indicazioni
    for voce in ("«Note per la trattazione scritta»", "15/12/2026", "R.G. 4711/2025", "Mario Bianchi", "Avv. Anna Verdi per Mario Rossi"):
        assert voce in indicazioni
    contenuto = next(p for p in passi if p["azione"].startswith("Preparare le note scritte per l'udienza del 15/12/2026"))
    assert "09:30" in contenuto["motivo"] and "bozza" in contenuto["motivo"]
    assert any("Attendere il provvedimento" in p["azione"] and "14/01/2027" in p["motivo"] for p in passi)


def test_cliente_resistente_o_resistente_costituita_niente_prova_della_notifica():
    resistente = _passi(parti={"ricorrente": ["Beta S.r.l."], "resistente": ["Mario Rossi"]}, stato="APERTO")
    assert not any("prova della notifica" in p["azione"] for p in resistente)
    costituita = _passi(parti={"ricorrente": ["Mario Rossi"]}, pec_tutte=[{"oggetto": "COSTITUZIONE PARTI", "evento": ""}])
    assert not any("prova della notifica" in p["azione"] for p in costituita)


# ── Presidio documentale: il decreto nel fascicolo ─────────────────────


def test_presidio_documentale_usa_la_prossima_udienza_o_chiede_quale():
    fascicolo = SimpleNamespace(numero_rg="4711", anno_rg="2025", nome_cliente="Mario Rossi", titolo="Rossi / Beta",
                                data_prossima_udienza="2026-12-15", id="F1")
    esito = analyze_fascicolo_document_texts(fascicolo, {"D1": DECRETO}, today=OGGI)
    note = [a for a in esito["actions"] if a["type"] == "note_127_ter"]
    assert [(a["dateIso"], a["time"], a["peremptory"]) for a in note] == [("2026-12-15", "09:30", True)]
    fascicolo.data_prossima_udienza = "2026-10-01"
    esito = analyze_fascicolo_document_texts(fascicolo, {"D1": DECRETO}, today=OGGI)
    assert [a["type"] for a in esito["actions"]] == ["verifica_udienza_127_ter"]
    assert esito["status"] == "da_verificare"


# ── 3. Udienza cartolare alla conferma ─────────────────────────────────


def test_conferma_del_termine_rende_cartolare_l_udienza(tmp_path):
    agenda = Agenda(str(tmp_path / "agenda.json"))
    udienza = agenda.aggiungi("Udienza di discussione", TipoAppuntamento.UDIENZA, "2026-12-15T09:00:00", allow_overlap=True)
    scadenza = SimpleNamespace(id="S1", deadline_profile_code="NOTE_127_TER", id_appuntamento=udienza.id)
    assert tipo_udienza_iniziale(udienza) == ""
    assert segna_udienza_cartolare(scadenza, gestione_agenda=agenda) is True
    aggiornata = agenda.get(udienza.id)
    assert aggiornata.hearing_mode == "note_scritte" and "127-ter" in aggiornata.note
    assert tipo_udienza_iniziale(aggiornata) == "cartolare"
    assert segna_udienza_cartolare(scadenza, gestione_agenda=agenda) is False  # già cartolare


# ── Pipeline PEC end to end: bozza unica anche con due copie del decreto ──


def _decreto_mime(tag: str, oggi: date) -> bytes:
    from tests.test_pec_change_receipt import _cancelleria_mime

    mime = message_from_bytes(_cancelleria_mime(
        "ATTO NON CODIFICATO", "DECRETO", rg="4711/2025/LAV", ufficio="TRIBUNALE ORDINARIO DI VICENZA",
        when=oggi.strftime("%a, %d %b %Y") + " 09:10:00 +0100", tag=tag, ricorrente="BARILARO FRANCESCO",
    ), policy=policy.SMTP)
    mime.add_attachment(DECRETO.encode(), maintype="text", subtype="plain", filename="decreto.txt")
    return mime.as_bytes(policy=policy.SMTP)


def _bozze_note(tmp_path: Path) -> list:
    return [s for s in GestioneScadenziario(str(tmp_path / "scadenze.json")).tutte(solo_aperte=False)
            if s.deadline_profile_code == "NOTE_127_TER"]


def test_pec_con_decreto_senza_data_propone_una_sola_bozza_alle_09_30(tmp_path):
    from pct.fascicoli import GestioneFascicoli
    from tests.test_pec_change_receipt import _run_cancelleria
    from tests.test_pec_audit_pipeline import _repo_con_fascicolo

    repo, fascicolo = _repo_con_fascicolo(tmp_path)
    GestioneFascicoli(db_path=str(tmp_path / "fascicoli.json"), documents_dir=str(tmp_path / "docs")).aggiorna(
        fascicolo.id, numero_rg="4711", anno_rg="2025")
    oggi = datetime.now(ROME_TZ).date()
    giorno = oggi + timedelta(days=40)
    udienza = Agenda(str(tmp_path / "agenda.json")).aggiungi(
        "Udienza di discussione", TipoAppuntamento.UDIENZA, f"{giorno.isoformat()}T09:00:00", allow_overlap=True,
        note=f"Fascicolo: {fascicolo.id}", procedimento="RG 4711/2025", id_fascicolo=fascicolo.id,
    )
    primo = _run_cancelleria(repo, _decreto_mime("note-1", oggi), "INBOX:UID:1271")
    repo.link_fascicolo(primo, threshold=0.5, actor="pytest")
    [bozza] = _bozze_note(tmp_path)
    assert bozza.stato == StatoTermine.BOZZA and bozza.tipo == TipoTermine.TERMINE_PERENTORIO and bozza.perentorio
    assert bozza.data_scadenza == giorno.isoformat() and bozza.operational_due_at == f"{giorno.isoformat()}T09:30:00"
    assert bozza.id_fascicolo == fascicolo.id and bozza.id_appuntamento == udienza.id
    assert bozza.hearing_mode == "note_scritte"
    ricezione = next(a for a in Agenda(str(tmp_path / "agenda.json")).tutti() if primo in a.external_uid)
    assert "udienza cartolare" in ricezione.note and "prova della notifica" in ricezione.note
    # La stessa comunicazione rielaborata e una seconda copia del decreto: nessun doppione.
    repo.record_pec_schedule_change_receipts(since="2026-01-01T00:00:00Z", actor="pytest")
    secondo = _run_cancelleria(repo, _decreto_mime("note-2", oggi), "INBOX:UID:1272")
    repo.link_fascicolo(secondo, threshold=0.5, actor="pytest")
    assert len(_bozze_note(tmp_path)) == 1
