"""Passaggi spiegabili e regole dello studio: modello, persistenza, ambiti, vincoli di legge, caso successivo.

Dati di prova costruiti a mano (nessun dato di clienti); il decreto 127-ter è la
fixture pubblica di ``tests/fixtures/pec/decreto_note_scritte_127_ter.txt``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pct.note_127_ter.esame_pec import esamina_decreto_pec
from pct.passaggi import (
    AZIONI,
    Contesto,
    CorrezioneRifiutata,
    STATO_ESCLUSO,
    applica_regole,
    regola_da_correzione,
)
from pct.passaggi.fascicolo import passaggi_del_fascicolo
from pct.passaggi.modello import passaggio_da_dizionario
from pct.passaggi.produttori import passaggi_da_esame, passaggi_termini_pec
from pct.passaggi.produttori.note_127_ter import REGOLA_BOZZA, REGOLA_TERMINE, REGOLA_UDIENZA
from pct.passaggi.repository import RegoleStudioError, RegoleStudioRepository

OGGI = date(2026, 11, 2)
DECRETO = (Path(__file__).parent / "fixtures" / "pec" / "decreto_note_scritte_127_ter.txt").read_text(encoding="utf-8")


def _fascicolo(ident: str, *, ufficio: str = "Tribunale di Milano", giudice: str = "dott.ssa Bianchi", materia: str = "civile") -> dict:
    return {"id": ident, "tribunale": ufficio, "giudice": giudice, "area_pratica": materia, "numero_rg": "4711", "anno_rg": "2025"}


def _note(ident: str, giorno: str = "2027-01-12", stato: str = "BOZZA") -> dict:
    return {"id": ident, "stato": stato, "data": giorno, "titolo": "Deposito note scritte ex art. 127-ter c.p.c. - RG 4711/2025",
            "note": f"PEC_TERMINE_PROPOSTO:m-{ident}:NOTE_127_TER", "deadline_profile_code": "NOTE_127_TER",
            "operational_due_at": f"{giorno}T09:30:00"}


def _termine_pec(ident: str, *, perentorio: bool = False, norma: str = "art. 127-ter c.p.c.") -> dict:
    return {"id": ident, "tipo": "opposizione trattazione scritta", "norma": norma, "decorrenza": "02/11/2026",
            "scadenza": "09/11/2026", "perentorio": perentorio, "da_rivedere": True, "oggetto": "Comunicazione di cancelleria",
            "data_pec": "02/11/2026", "messaggio_id": f"msg-{ident}"}


def _passaggi(fascicolo: dict, *, scadenze=(), termini=()) -> list:
    return passaggi_del_fascicolo(fascicolo, scadenze=list(scadenze), termini_pec=list(termini), oggi=OGGI)


def _uno(passaggi: list, regola_id: str):
    return next(passaggio for passaggio in passaggi if passaggio.regola_id == regola_id)


@pytest.fixture()
def repo(tmp_path):
    return RegoleStudioRepository(tmp_path / "regole.db", tenant_id="studio-a")


# ── Modello ────────────────────────────────────────────────────────────


def test_passaggio_spiega_regola_norma_prove_dati_e_vincoli():
    termine = _uno(_passaggi(_fascicolo("F1"), scadenze=[_note("S1")]), REGOLA_TERMINE)
    dati = termine.come_dizionario()
    json.dumps(dati)  # serializzabile
    assert dati["stato"] == "da_confermare" and dati["statoEtichetta"] == "da confermare"
    assert dati["regola"]["id"] == REGOLA_TERMINE and dati["regola"]["descrizione"]
    assert [norma["id"] for norma in dati["norme"]] == ["cpc_127ter", "dispatt_196sexies"]
    assert all(norma["url"].startswith("https://www.normattiva.it/") for norma in dati["norme"])
    assert dati["campi"]["data"] == {**dati["campi"]["data"], "valore": "2027-01-12", "vincolato": True}
    assert dati["campi"]["ora"]["valore"] == "09:30" and not dati["campi"]["ora"]["vincolato"]
    assert dati["vincoli"] == ["termine_perentorio"] and dati["prove"] and dati["dati"]
    ricostruito = passaggio_da_dizionario(dati)
    assert ricostruito.regola_id == REGOLA_TERMINE and ricostruito.campi["data"].vincolato


def test_passaggio_senza_regola_o_con_stato_ignoto_non_esiste():
    termine = _uno(_passaggi(_fascicolo("F1"), scadenze=[_note("S1")]), REGOLA_TERMINE)
    with pytest.raises(ValueError):
        termine.con(stato="inventato")
    with pytest.raises(ValueError):
        termine.con(regola_id="")


def test_127_ter_dall_esame_reale_del_decreto_tutta_la_sequenza():
    esito = esamina_decreto_pec(DECRETO, oggi=OGGI, comunicata_il=OGGI, fascicolo_id="F1", rg="4711/2025", ufficio="Tribunale di Milano",
                                appuntamenti=[{"id": "A1", "tipo": "UDIENZA", "stato": "PROGRAMMATO", "data_ora": "2026-12-15T09:00:00", "id_fascicolo": "F1"}])
    passaggi = passaggi_da_esame(esito, Contesto("F1", "Tribunale di Milano"), pec_id="msg1", oggetto_pec="Comunicazione", rg="4711/2025")
    regole = [passaggio.regola_id for passaggio in passaggi]
    assert regole[:4] == ["127ter.riconoscimento_decreto", "127ter.collegamento_rg_ufficio", REGOLA_UDIENZA, REGOLA_TERMINE]
    assert "127ter.udienza_cartolare" in regole and REGOLA_BOZZA in regole
    assert any(regola.startswith("127ter.adempimento.") for regola in regole)
    termine = _uno(passaggi, REGOLA_TERMINE)
    assert termine.campi["data"].valore == "2026-12-15" and termine.campi["ora"].valore == "09:30"
    assert "deposito_non_autonomo" in _uno(passaggi, REGOLA_BOZZA).vincoli


def test_127_ter_udienza_ambigua_diventa_domanda_all_avvocato():
    esito = esamina_decreto_pec(DECRETO, oggi=OGGI, fascicolo_id="F1", appuntamenti=[
        {"id": "A1", "tipo": "UDIENZA", "stato": "PROGRAMMATO", "data_ora": "2026-12-15T09:00:00", "id_fascicolo": "F1"},
        {"id": "A2", "tipo": "UDIENZA", "stato": "PROGRAMMATO", "data_ora": "2027-01-20T09:00:00", "id_fascicolo": "F1"}])
    passaggi = passaggi_da_esame(esito, Contesto("F1", "Tribunale di Milano"), pec_id="msg1")
    udienza = _uno(passaggi, REGOLA_UDIENZA)
    assert udienza.stato == "da_chiedere" and "conferma_avvocato" in udienza.vincoli
    assert not any(passaggio.regola_id == REGOLA_TERMINE for passaggio in passaggi)
    with pytest.raises(CorrezioneRifiutata):
        regola_da_correzione(udienza, azione="non_chiedere_conferma", ambito="tipo", autore_id="avv")


# ── Persistenza e audit ────────────────────────────────────────────────


def test_repository_crea_modifica_disattiva_con_diario(repo):
    termine = _uno(_passaggi(_fascicolo("F1"), scadenze=[_note("S1")]), REGOLA_TERMINE)
    regola = repo.crea(regola_da_correzione(termine, azione="modifica_valore", ambito="ufficio", campo="ora", valore="12:00",
                                            autore_id="avv1", autore_nome="Avv. Prova", motivo="Prassi della cancelleria"))
    letta = repo.leggi(regola.id)
    assert letta.ufficio == "Tribunale di Milano" and letta.valore == "12:00" and letta.passaggio_originale["regola"]["id"] == REGOLA_TERMINE
    repo.aggiorna(regola.id, autore_id="avv1", valore="11:00")
    repo.aggiorna(regola.id, autore_id="avv1", attiva=False)
    assert repo.elenco(solo_attive=True) == []
    repo.aggiorna(regola.id, autore_id="avv1", attiva=True)
    assert [evento["evento"] for evento in repo.eventi(regola.id)] == ["creata", "modificata", "disattivata", "riattivata"]
    with pytest.raises(RegoleStudioError):
        repo.leggi("inesistente")


def test_repository_isola_gli_studi(tmp_path):
    a = RegoleStudioRepository(tmp_path / "regole.db", tenant_id="studio-a")
    b = RegoleStudioRepository(tmp_path / "regole.db", tenant_id="studio-b")
    termine = _uno(_passaggi(_fascicolo("F1"), scadenze=[_note("S1")]), REGOLA_TERMINE)
    regola = a.crea(regola_da_correzione(termine, azione="chiedi_sempre", ambito="tipo", autore_id="avv1"))
    assert b.elenco() == [] and b.attive_per({REGOLA_TERMINE}) == []
    with pytest.raises(RegoleStudioError):
        b.leggi(regola.id)
    with pytest.raises(RegoleStudioError):
        b.aggiorna(regola.id, autore_id="intruso", attiva=False)
    assert a.leggi(regola.id).attiva


def test_applicazione_registrata_una_volta_per_caso(repo):
    termine = _uno(_passaggi(_fascicolo("F1"), scadenze=[_note("S1")]), REGOLA_TERMINE)
    regola = repo.crea(regola_da_correzione(termine, azione="chiedi_sempre", ambito="tipo", autore_id="avv1"))
    for _ in range(3):
        _corretti, applicazioni = applica_regole([termine], repo.attive_per({REGOLA_TERMINE}))
        repo.registra_applicazioni(applicazioni)
    assert [(voce["chiave_passaggio"], voce["esito"]) for voce in repo.applicazioni(regola.id)] == [(termine.chiave, "applicata")]


# ── Ambiti ─────────────────────────────────────────────────────────────


def _regola_ora(repo, ambito: str, *, da="F1", valore="12:00", **contesto):
    termine = _uno(_passaggi(_fascicolo(da, **contesto), scadenze=[_note("S-" + da)]), REGOLA_TERMINE)
    return repo.crea(regola_da_correzione(termine, azione="modifica_valore", ambito=ambito, campo="ora", valore=valore, autore_id="avv1"))


def _ora_in(repo, fascicolo: dict) -> str:
    termine = _uno(_passaggi(fascicolo, scadenze=[_note("S-" + fascicolo["id"])]), REGOLA_TERMINE)
    [corretto], _ = applica_regole([termine], repo.attive_per({REGOLA_TERMINE}))
    return corretto.campi["ora"].valore


def test_ambito_fascicolo_vale_solo_per_quel_fascicolo(repo):
    _regola_ora(repo, "fascicolo")
    assert _ora_in(repo, _fascicolo("F1")) == "12:00"
    assert _ora_in(repo, _fascicolo("F2")) == "09:30"


def test_ambito_giudice_vale_per_lo_stesso_giudice_dello_stesso_ufficio(repo):
    _regola_ora(repo, "giudice")
    assert _ora_in(repo, _fascicolo("F2", giudice="Dott.ssa BIANCHI")) == "12:00"
    assert _ora_in(repo, _fascicolo("F3", giudice="dott. Verdi")) == "09:30"
    assert _ora_in(repo, _fascicolo("F4", ufficio="Tribunale di Torino")) == "09:30"


def test_ambito_ufficio_vale_per_tutto_l_ufficio(repo):
    _regola_ora(repo, "ufficio")
    assert _ora_in(repo, _fascicolo("F2", giudice="dott. Verdi")) == "12:00"
    assert _ora_in(repo, _fascicolo("F3", ufficio="Tribunale di Torino")) == "09:30"


def test_ambito_tipo_vale_ovunque_e_la_regola_piu_specifica_vince(repo):
    _regola_ora(repo, "tipo", valore="11:00")
    _regola_ora(repo, "ufficio", da="F9", valore="12:00", ufficio="Tribunale di Napoli")
    assert _ora_in(repo, _fascicolo("F2", ufficio="Tribunale di Torino")) == "11:00"
    assert _ora_in(repo, _fascicolo("F3", ufficio="Tribunale di Napoli")) == "12:00"


def test_ambito_giudice_senza_giudice_noto_non_si_salva():
    termine = _uno(_passaggi(_fascicolo("F1", giudice=""), scadenze=[_note("S1")]), REGOLA_TERMINE)
    with pytest.raises(ValueError, match="giudice"):
        regola_da_correzione(termine, azione="chiedi_sempre", ambito="giudice", autore_id="avv1")


# ── Vincoli di legge ───────────────────────────────────────────────────


def test_un_termine_perentorio_non_si_toglie_ne_si_sposta():
    termine = _uno(_passaggi(_fascicolo("F1"), scadenze=[_note("S1")]), REGOLA_TERMINE)
    with pytest.raises(CorrezioneRifiutata) as rifiuto:
        regola_da_correzione(termine, azione="non_proporre", ambito="ufficio", autore_id="avv1")
    assert rifiuto.value.rifiuto.vincolo == "termine_perentorio"
    assert [norma["id"] for norma in rifiuto.value.rifiuto.come_dizionario()["norme"]] == ["cpc_153"]
    with pytest.raises(CorrezioneRifiutata, match="art. 153"):
        regola_da_correzione(termine, azione="modifica_valore", ambito="fascicolo", campo="data", valore="2027-01-20", autore_id="avv1")


def test_il_deposito_non_diventa_autonomo(repo):
    bozza = _uno(_passaggi(_fascicolo("F1"), scadenze=[_note("S1")]), REGOLA_BOZZA)
    with pytest.raises(CorrezioneRifiutata, match="196-quater"):
        regola_da_correzione(bozza, azione="non_chiedere_conferma", ambito="tipo", autore_id="avv1")
    with pytest.raises(CorrezioneRifiutata):
        regola_da_correzione(bozza, azione="modifica_valore", ambito="tipo", campo="deposito", valore="automatico", autore_id="avv1")


def test_regola_valida_altrove_rifiutata_su_un_termine_perentorio(repo):
    """«Non proporre» è legittimo per un termine facoltativo; sullo stesso tipo perentorio il passaggio mostra il rifiuto."""
    facoltativo = passaggi_termini_pec([_termine_pec("T1")], Contesto("F1", "Tribunale di Milano"))[0]
    regola = repo.crea(regola_da_correzione(facoltativo, azione="non_proporre", ambito="tipo", autore_id="avv1"))
    perentorio = passaggi_termini_pec([_termine_pec("T2", perentorio=True)], Contesto("F2", "Tribunale di Roma"))[0]
    [corretto], applicazioni = applica_regole([perentorio], repo.attive_per({perentorio.regola_id}))
    assert corretto.stato == "da_confermare"
    assert corretto.regole_rifiutate[0]["id"] == regola.id and corretto.regole_rifiutate[0]["rifiuto"]["vincolo"] == "termine_perentorio"
    assert applicazioni[0].esito == "rifiutata"


# ── La correzione cambia il caso successivo ───────────────────────────


def test_la_correzione_si_applica_al_prossimo_caso_simile(repo):
    """L'avvocato corregge l'ora delle note per il giudice; il decreto successivo dello stesso giudice la usa già."""
    primo = _uno(_passaggi(_fascicolo("F1"), scadenze=[_note("S1")]), REGOLA_TERMINE)
    repo.crea(regola_da_correzione(primo, azione="modifica_valore", ambito="giudice", campo="ora", valore="12:00",
                                   autore_id="avv1", motivo="Il giudice chiede il deposito entro mezzogiorno"))
    successivo = _passaggi(_fascicolo("F7"), scadenze=[_note("S7", giorno="2027-03-03")])
    corretti, _ = applica_regole(successivo, repo.attive_per({passaggio.regola_id for passaggio in successivo}))
    termine = _uno(corretti, REGOLA_TERMINE)
    assert termine.campi["ora"].valore == "12:00" and termine.campi["ora"].valore_software == "09:30"
    assert termine.titolo.endswith("ore 12:00")
    assert termine.regole_applicate[0]["etichetta"].startswith("regola dello studio del ")
    assert termine.campi["data"].valore == "2027-03-03"  # la data resta quella del decreto


def test_non_proporre_un_termine_facoltativo_per_un_ufficio(repo):
    primo = passaggi_termini_pec([_termine_pec("T1")], Contesto("F1", "Tribunale di Milano"))[0]
    repo.crea(regola_da_correzione(primo, azione="non_proporre", ambito="ufficio", autore_id="avv1"))
    stesso_ufficio = passaggi_termini_pec([_termine_pec("T2")], Contesto("F2", "Tribunale di Milano"))
    altro_ufficio = passaggi_termini_pec([_termine_pec("T3")], Contesto("F3", "Tribunale di Bari"))
    [escluso], _ = applica_regole(stesso_ufficio, repo.attive_per({primo.regola_id}))
    [invariato], _ = applica_regole(altro_ufficio, repo.attive_per({primo.regola_id}))
    assert escluso.stato == STATO_ESCLUSO and escluso.stato_software == "da_confermare"
    assert invariato.stato == "da_confermare"


def test_chiedi_sempre_prevale_a_pari_ambito_e_le_azioni_hanno_etichette_italiane(repo):
    facoltativo = passaggi_termini_pec([_termine_pec("T1")], Contesto("F1", "Tribunale di Milano"))[0]
    repo.crea(regola_da_correzione(facoltativo, azione="non_chiedere_conferma", ambito="tipo", autore_id="avv1"))
    repo.crea(regola_da_correzione(facoltativo, azione="chiedi_sempre", ambito="tipo", autore_id="avv2"))
    [corretto], _ = applica_regole([facoltativo], repo.attive_per({facoltativo.regola_id}))
    assert corretto.stato == "da_chiedere"
    assert all(etichetta and etichetta[0].islower() for etichetta in AZIONI.values())
