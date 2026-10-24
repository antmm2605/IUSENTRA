"""Biblioteca autoalimentata e presidio delle norme delle schede: acquisizione, verifica, proposte, fonti per Lex.

Archivio e schede temporanei; nessun accesso alla rete (download sostituiti da funzioni di prova).
"""
from __future__ import annotations

import datetime as dt
import json
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
    assert fonte_per_chiave("codice_civile").tipo == "non_deducibile"


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
    <meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:1994-01-21;53"/></FRBRWork></identification></meta>
    <preface><docTitle>Facolta' di notificazioni</docTitle></preface><body>
    <article><num>Art. 3-bis.</num><heading>(Notifica PEC)</heading><paragraph>1. La notificazione puo' eseguirsi a mezzo PEC.</paragraph></article>
    <article><num>Art. 4</num><mod><article><num>Art. 99</num><paragraph>testo modificato</paragraph></article></mod></article>
    </body><attachments><attachment><article><num>Art. 1</num><paragraph>allegato</paragraph></article></attachment></attachments></act></akomaNtoso>"""
    righe = converti(AttoScaricato("urn:nir:stato:legge:1994;53", xml, "t", "19940131", "094G0053", "20261024", URL, "abc"), "legge_53_1994", "2026-10-24")
    assert [r["articolo"] for r in righe] == ["3bis", "4"]
    assert righe[0]["rubrica"] == "Notifica PEC" and righe[0]["provenienza_integrazione"]["sha256_akn"] == "abc"


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
    xml = b'<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act><meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:1994-01-21;53"/></FRBRWork></identification></meta><body><article><num>Art. 3-bis.</num><paragraph>Testo</paragraph></article></body></act></akomaNtoso>'
    with pytest.raises(ValueError, match="discordante"):
        converti(AttoScaricato(urn, xml, "t", "19940131", "094G0053", "20261024", URL, "abc"),
                 "legge_53_1994", "2026-10-24")
