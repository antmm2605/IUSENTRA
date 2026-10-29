"""Biblioteca autoalimentata e presidio delle norme delle schede: acquisizione, verifica, proposte, fonti per Lex.

Archivio e schede temporanei; nessun accesso alla rete (download sostituiti da funzioni di prova).
"""
from __future__ import annotations

import datetime as dt
import json
import hashlib
from pathlib import Path

import pytest

from lex.normativa.biblioteca.acquisizione import acquisisci
from lex.normativa.biblioteca.fabbisogno import calcola_fabbisogno
from lex.normativa.biblioteca.normattiva_akn import AttoScaricato, converti
from lex.normativa.biblioteca.riferimenti import fonte_per_chiave
from lex.normativa.consultazione import importa_fonti
from lex.procedura_atti.fonti_scheda import fonti_per_scheda
from lex.procedura_atti.provenienza import verifica_provenienza
from pct.schede_fonti.proposte import approva_scheda, registra_esiti
from pct.schede_fonti.repository import RepositorySchedeFonti
from pct.schede_fonti.verifica import verifica_schede

URL = "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.dataPubblicazioneGazzetta=1942-04-04&atto.codiceRedazionale=042U0262"


def _riga(chiave, art, testo, urn="urn:nir:stato:regio.decreto:1942-03-16;262"):
    return {"chiave": chiave, "atto": chiave, "articolo": art, "rubrica": "", "testo": testo, "titolo_atto": "Codice civile",
            "data_atto": "1942-03-16", "urn": urn, "vigenza": "VIGENTE", "url": URL, "raccolto_il": "2026-10-01"}


def _pacchetto(cartella: Path, righe: list[dict]) -> Path:
    (cartella / "atti").mkdir(parents=True, exist_ok=True)
    (cartella / "atti" / f"{righe[0]['chiave']}.jsonl").write_text("\n".join(json.dumps(r) for r in righe) + "\n", encoding="utf-8")
    return cartella


@pytest.fixture()
def ambiente(tmp_path):
    db = tmp_path / "codici_leggi.sqlite"
    importa_fonti(_pacchetto(tmp_path / "p1", [
        _riga("codice_civile", "1219", "Art. 1219. (Costituzione in mora) Il debitore e' costituito in mora mediante intimazione."),
        _riga("codice_civile", "2409", "Art. 2409. ((ARTICOLO ABROGATO DAL D.LGS. 27 MARZO 2026, N. 47))"),
    ]), db, "2026-10-01")
    schede = tmp_path / "schede"
    schede.mkdir()
    (schede / "PRO_001.json").write_text(json.dumps({
        "id": "PRO_001", "titolo": "Diffida ad adempiere", "template": ["PRO_001"],
        "base_normativa": [{"atto": "codice_civile", "articolo": "1219", "perche": "messa in mora"},
                           {"atto": "legge_53_1994", "articolo": "3bis", "perche": "notifica via PEC"}],
        "campi": [{"campo": "denuncia", "obbligatorio": True, "norma": [{"atto": "codice_civile", "articolo": "2409", "perche": "x"}]}],
    }), encoding="utf-8")
    return db, schede, tmp_path


def test_chiavi_e_fonti_ufficiali():
    assert fonte_per_chiave("dpr_396_2000").urn == "urn:nir:stato:decreto.del.presidente.della.repubblica:2000;396"
    assert fonte_per_chiave("legge_53_1994").urn == "urn:nir:stato:legge:1994;53"
    assert fonte_per_chiave("reg_ue_2022_2065").celex == "32022R2065"
    assert fonte_per_chiave("codice_civile").urn == "urn:nir:stato:regio.decreto:1942-03-16;262"


def test_acquisisce_solo_se_il_testo_ufficiale_contiene_gli_articoli_richiesti(ambiente, monkeypatch):
    db, schede, tmp = ambiente
    monkeypatch.setattr("lex.normativa.biblioteca.fabbisogno.CARTELLA_SCHEDE", schede)
    monkeypatch.setattr("lex.normativa.biblioteca.acquisizione.calcola_fabbisogno",
                        lambda d: calcola_fabbisogno(d, __import__("lex.normativa.biblioteca.fabbisogno", fromlist=["x"]).riferimenti_schede(schede)))
    assert "legge_53_1994" in calcola_fabbisogno(db, __import__("lex.normativa.biblioteca.fabbisogno", fromlist=["x"]).riferimenti_schede(schede)).atti_mancanti
    senza = acquisisci(db, tmp / "auto", oggi=dt.date(2026, 10, 24),
                       scarica_normattiva=lambda k, u, o: [_riga(k, "1", "Art. 1. altro", "urn:nir:stato:legge:1994-01-21;53")])
    assert senza.esiti[0].stato == "articoli_assenti" and senza.importazione is None
    con = acquisisci(db, tmp / "auto", oggi=dt.date(2026, 10, 24),
                     scarica_normattiva=lambda k, u, o: [_riga(k, "3bis", "Art. 3-bis. La notificazione ... a mezzo PEC.",
                                                               "urn:nir:stato:legge:1994-01-21;53")])
    assert con.esiti[0].stato == "importato" and con.importazione["new_articles"] == 1
    assert not calcola_fabbisogno(db, __import__("lex.normativa.biblioteca.fabbisogno", fromlist=["x"]).riferimenti_schede(schede)).atti_mancanti


def test_converte_akn_solo_articoli_del_corpo():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?><akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act>
    <meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:1994-01-21;53"/><FRBRdate date="1994-01-21"/><FRBRalias name="eli" value="eli/id/1994/01/31/094G0053/ORIGINAL"/></FRBRWork><FRBRExpression><FRBRdate date="2026-10-24"/></FRBRExpression></identification></meta>
    <preface><docTitle>Facolta' di notificazioni</docTitle></preface><body>
    <article><num>Art. 3-bis.</num><heading>(Notifica PEC)</heading><paragraph>1. La notificazione puo' eseguirsi a mezzo PEC.</paragraph></article>
    <article><num>Art. 4</num><mod><article><num>Art. 99</num><paragraph>testo modificato</paragraph></article></mod></article>
    </body><attachments><attachment><doc name="Allegato di prova"><mainBody><article><num>Art. 1</num><paragraph>Testo autonomo dell allegato da mantenere separato.</paragraph></article></mainBody></doc></attachment></attachments></act></akomaNtoso>"""
    righe = converti(AttoScaricato("urn:nir:stato:legge:1994;53", xml, "t", "19940131", "094G0053", "20261024", URL, hashlib.sha256(xml).hexdigest()), "legge_53_1994", "2026-10-24")
    from lex.normativa.biblioteca.fabbisogno import norm_articolo
    corpo = [r for r in righe if r["chiave"] == "legge_53_1994"]
    assert [norm_articolo(r["articolo"]) for r in corpo] == ["3bis", "4"]
    assert not any(norm_articolo(r["articolo"]) == "99" for r in righe)
    assert any(r["chiave"] != "legge_53_1994" and norm_articolo(r["articolo"]) == "1" for r in righe)
    assert righe[0]["rubrica"].strip("()") == "Notifica PEC" and righe[0]["provenienza_integrazione"]["sha256_akn"] == hashlib.sha256(xml).hexdigest()


def test_verifica_abrogazione_cambio_testo_e_proposte(ambiente):
    db, schede, tmp = ambiente
    repo = RepositorySchedeFonti(tmp / "stato.sqlite")
    esiti = verifica_schede(db, schede)
    stati = {(e.atto, e.articolo): e.stato for e in esiti}
    assert stati[("codice_civile", "2409")] == "abrogato" and stati[("legge_53_1994", "3bis")] == "atto_assente"
    registra_esiti(repo, esiti)
    tipi = {p["tipo"] for p in repo.proposte()}
    assert tipi == {"norma_abrogata", "norma_assente"}
    assert "D.LGS. 27 MARZO 2026, N. 47" in next(p for p in repo.proposte() if p["tipo"] == "norma_abrogata")["motivo"]
    assert approva_scheda(repo, esiti, "PRO_001", "Avv. Rossi") == 1
    registra_esiti(repo, verifica_schede(db, schede))
    assert not [p for p in repo.proposte() if p["tipo"] == "norma_cambiata"]
    importa_fonti(_pacchetto(tmp / "p2", [_riga("codice_civile", "1219",
                  "Art. 1219. (Costituzione in mora) Il debitore e' costituito in mora mediante intimazione scritta o PEC."),
                  _riga("codice_civile", "2409", "Art. 2409. ((ARTICOLO ABROGATO DAL D.LGS. 27 MARZO 2026, N. 47))")]), db, "2026-10-20")
    registra_esiti(repo, verifica_schede(db, schede))
    cambiate = [p for p in repo.proposte() if p["tipo"] == "norma_cambiata"]
    assert len(cambiate) == 1 and "+(Costituzione in mora) Il debitore e' costituito in mora mediante intimazione scritta o PEC." in cambiate[0]["differenze"] and "Avv. Rossi" in cambiate[0]["motivo"]
    n = len(repo.proposte())
    registra_esiti(repo, verifica_schede(db, schede))
    assert len(repo.proposte()) == n  # nessun duplicato a ogni notte
    repo.decidi_proposta(cambiate[0]["id"], "approvata", avvocato="Avv. Rossi")
    with pytest.raises(ValueError):
        repo.decidi_proposta(cambiate[0]["id"], "respinta", avvocato="Avv. Rossi")


def test_fonti_per_lex_con_provenienza_e_pendenze(ambiente):
    db, schede, tmp = ambiente
    repo = RepositorySchedeFonti(tmp / "stato.sqlite")
    registra_esiti(repo, verifica_schede(db, schede))
    f = fonti_per_scheda("PRO_001", db, repository=repo, cartella=schede, oggi=dt.date(2026, 10, 24))
    assert [r["articolo"] for r in f.fonti_ref] == ["1219"]
    assert verifica_provenienza({"fonti": f.fonti, "fonti_ref": f.fonti_ref}) == []
    assert f.fonti_ref[0]["provenienza"]["url"] == URL
    assert any("abrogato" in p for p in f.pendenze) and any("non ancora approvato" in p for p in f.pendenze)
    approva_scheda(repo, verifica_schede(db, schede), "PRO_001", "Avv. Rossi")
    f2 = fonti_per_scheda("PRO_001", db, repository=repo, cartella=schede)
    assert not any("non ancora approvato" in p for p in f2.pendenze)


@pytest.mark.parametrize("urn", ["urn:nir:stato:legge:1995;53", "urn:nir:stato:legge:1994;54",
                                  "urn:nir:stato:decreto.legge:1994;53", "urn:nir:stato:legge:1994-01-22;53"])
def test_rifiuta_akn_di_altro_atto_anche_con_articolo_richiesto(urn):
    xml = b'<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act><meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:1994-01-21;53"/><FRBRdate date="1994-01-21"/><FRBRalias name="eli" value="eli/id/1994/01/31/094G0053/ORIGINAL"/></FRBRWork><FRBRExpression><FRBRdate date="2026-10-24"/></FRBRExpression></identification></meta><body><article><num>Art. 3-bis.</num><paragraph>Testo</paragraph></article></body></act></akomaNtoso>'
    with pytest.raises(ValueError, match="discordante"):
        converti(AttoScaricato(urn, xml, "t", "19940131", "094G0053", "20261024", URL, hashlib.sha256(xml).hexdigest()),
                 "legge_53_1994", "2026-10-24")


def test_verifica_rilascio_biblioteca_e_in_sola_lettura(ambiente, monkeypatch):
    import runpy
    import pct.schede_fonti.verifica as modulo
    db, schede, tmp = ambiente
    originale = modulo.verifica_schede
    monkeypatch.setattr(modulo, "verifica_schede", lambda d: originale(d, schede))
    import sqlite3
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    prima = db.read_bytes()
    verifica = runpy.run_path(str(Path(__file__).resolve().parents[1] / "deploy/hetzner/verifica_fonti_lex.py"))["verifica_biblioteca_schede"]
    with pytest.raises(ValueError, match="riferimenti assenti"):
        verifica(db)
    assert db.read_bytes() == prima
    norma = _riga("legge_53_1994", "3bis", "Art. 3-bis. (Notificazioni a mezzo PEC) La notificazione puo' eseguirsi a mezzo posta elettronica certificata.",
                  urn="urn:nir:stato:legge:1994-01-21;53")
    norma.update(titolo_atto="Legge 21 gennaio 1994, n. 53", data_atto="1994-01-21",
                 url="https://www.normattiva.it/atto/caricaDettaglioAtto?atto.dataPubblicazioneGazzetta=1994-01-31&atto.codiceRedazionale=094G0053")
    importa_fonti(_pacchetto(tmp / "completa", [norma]), db, "2026-10-24")
    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    prima = db.read_bytes()
    esito = verifica(db)
    assert esito["norme"] == 3 and esito["stati"]["presente"] == 2
    assert esito["stati"]["abrogato"] == 1
    assert not esito["scritture"] and not esito["approvazioni_automatiche"]
    assert db.read_bytes() == prima


def test_sceglie_modello_per_pertinenza_senza_confondere_assenza_di_risultati(tmp_path):
    from lex.procedura_atti.scelta_modello import proponi_modelli
    schede = tmp_path / "scelta"
    schede.mkdir()
    for sid, titolo in [("DIFFIDA", "Diffida ad adempiere contratto"), ("RICORSO", "Ricorso controversia lavoro")]:
        (schede / (sid + ".json")).write_text(json.dumps({"id": sid, "titolo": titolo,
            "template": ["PRO_001"], "base_normativa": [{"perche": titolo}]}), encoding="utf-8")
    risultati = proponi_modelli("diffida ad adempiere contratto", "inadempimento contrattuale", cartella=schede, limite=1)
    assert len(risultati) == 1 and risultati[0]["scheda"] == "DIFFIDA"
    assert risultati[0]["punteggio"] > 0 and risultati[0]["titolo"] == "Diffida ad adempiere contratto"
    assert proponi_modelli("", "", cartella=schede) == []
    assert proponi_modelli("diffida", cartella=tmp_path / "vuota") == []


def test_norma_di_un_campo_ha_fonte_unica_anche_se_gia_nella_base(ambiente):
    db, schede, _ = ambiente
    p = schede / "CAMPO.json"
    p.write_text(json.dumps({"id": "CAMPO", "titolo": "Messa in mora", "base_normativa": [
        {"atto": "codice_civile", "articolo": "1219", "perche": "base"}], "campi": [
        {"campo": "intimazione", "obbligatorio": True, "norma": [
         {"atto": "codice_civile", "articolo": "1219", "perche": "forma della intimazione"}]}]}), encoding="utf-8")
    f = fonti_per_scheda("CAMPO", db, cartella=schede)
    assert len(f.fonti) == 1 and not f.pendenze
    assert f.requisiti == [{"campo": "intimazione", "norma": "art. 1219 c.c.",
                           "perche": "forma della intimazione", "fonte": 1}]


@pytest.mark.parametrize("atto,sigla", [("dlgs_168_2003", "d.lgs. 168/2003"),
                                      ("reg_ue_2022_2065", "Reg. UE 2022/2065"),
                                      ("atto_senza_sigla", "atto senza sigla")])
def test_etichette_fonti_non_codificate(atto, sigla):
    from lex.procedura_atti.fonti_scheda import _sigla
    assert _sigla(atto) == sigla


def test_articoli_omonimi_nello_stesso_corpo_mantengono_localizzatori_distinti():
    xml=b'''<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act>
    <meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:2020-01-01;1"/>
    <FRBRdate date="2020-01-01"/></FRBRWork><FRBRExpression><FRBRdate date="2020-01-02"/>
    </FRBRExpression></identification></meta><body>
    <article><num>Art. 1.</num><paragraph>Prima disposizione autonoma presente nella fonte primaria.</paragraph></article>
    <article><num>Art. 1.</num><paragraph>Seconda disposizione autonoma presente nella stessa fonte primaria.</paragraph></article>
    </body></act></akomaNtoso>'''
    atto=AttoScaricato("urn:nir:stato:legge:2020-01-01;1",xml,"","","","20261026",URL,hashlib.sha256(xml).hexdigest())
    rows=converti(atto,"legge_1_2020","2026-10-26")
    assert len(rows)==2 and len({r["chiave"] for r in rows})==2
    assert len({r["provenienza_integrazione"]["localizzatore_xml"] for r in rows})==2
    assert all(r["articolo"]=="1" and r["provenienza_integrazione"]["sha256_akn"]==atto.sha256_xml for r in rows)
    assert "Prima disposizione" in rows[0]["testo"]
    assert "Seconda disposizione" in rows[1]["testo"]
