import json
import sqlite3
from types import SimpleNamespace

import pytest

from pct.archivio_letture.estrazione_giudice import estrai_giudice
from pct.giudice_fascicolo_repository import GiudiceFascicoloRepository


def case(**changes):
    values = dict(numero_rg="123", anno_rg="2025", nome_cliente="Rossi Maria", tribunale="TRIBUNALE DI VELLETRI")
    values.update(changes)
    return SimpleNamespace(**values)


TEXT = """TRIBUNALE DI VELLETRI
SENTENZA
Il Giudice del Lavoro del Tribunale di Velletri, dott.ssa Veronica Vaccaro, ha emesso
nella causa iscritta al n. 123/2025 R.G.
PROMOSSA DA ROSSI MARIA
"""


def test_native_judge_from_issuing_header():
    facts = estrai_giudice(TEXT, fascicolo=case())
    assert [(f.campo, f.valore, f.verifica) for f in facts] == [("giudice", "Veronica Vaccaro", "verificata")]


@pytest.mark.parametrize("source", [TEXT.replace("123/2025", "124/2025"), TEXT.replace("VELLETRI", "ROMA").replace("Velletri", "Roma"), TEXT.replace("ROSSI MARIA", "VERDI ANNA"), TEXT.replace("SENTENZA", "RICORSO"), TEXT.replace("PROMOSSA DA ROSSI MARIA", "PROMOSSA DA ROSSI MARIA, c.f. RSSMRA80A01H501X")])
def test_wrong_proceeding_or_party_is_not_written(source):
    assert estrai_giudice(source, fascicolo=case()) == []


def test_ocr_without_independent_proof_remains_plausible():
    assert estrai_giudice(TEXT, fascicolo=case(), origine="ocr")[0].verifica == "plausibile"


def test_quoted_judge_in_reasons_is_not_the_issuing_judge():
    text = TEXT.replace("Il Giudice del Lavoro del Tribunale di Velletri, dott.ssa Veronica Vaccaro, ha emesso", "Il Tribunale ha emesso")
    text += "\nMOTIVAZIONE\nIl Giudice Mario Verdi, letto il ricorso"
    assert estrai_giudice(text, fascicolo=case()) == []


@pytest.fixture
def backend():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript("CREATE TABLE fascicoli(id TEXT PRIMARY KEY,giudice TEXT,dati_json TEXT,modificato_il TEXT); CREATE TABLE audit_log(id TEXT,timestamp TEXT,id_utente TEXT,username TEXT,azione TEXT,risorsa_tipo TEXT,risorsa_id TEXT,dettagli TEXT,ip TEXT,esito TEXT);")
    connection.execute("INSERT INTO fascicoli VALUES ('f','',?, '')", (json.dumps({"giudice":"", "stato":"DEFINITO", "documenti":[{"id":"source"}]}),))
    connection.commit()
    return SimpleNamespace(conn=connection)


def test_sql_persistence_repeat_and_manual_value_preserved(backend):
    writer = GiudiceFascicoloRepository(backend)
    sources = [{"documento_id":"source", "sha256":"a"*64}]
    assert writer.consegna("f", "Veronica Vaccaro", sources)["stato"] == "consegnato"
    stored = backend.conn.execute("SELECT * FROM fascicoli").fetchone()
    payload = json.loads(stored["dati_json"])
    assert stored["giudice"] == payload["giudice"] == "Veronica Vaccaro"
    assert payload["stato"] == "DEFINITO" and payload["documenti"] == [{"id":"source"}]
    assert writer.consegna("f", "Veronica Vaccaro", sources)["stato"] == "gia_presente"
    assert writer.consegna("f", "Mario Verdi", sources)["stato"] == "discordante"
    assert backend.conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
    assert backend.conn.execute("SELECT giudice FROM fascicoli").fetchone()[0] == "Veronica Vaccaro"


def test_audit_failure_rolls_back_field(backend):
    backend.conn.execute("DROP TABLE audit_log")
    backend.conn.commit()
    with pytest.raises(sqlite3.OperationalError):
        GiudiceFascicoloRepository(backend).consegna("f", "Veronica Vaccaro", [{"documento_id":"source"}])
    assert backend.conn.execute("SELECT giudice FROM fascicoli").fetchone()[0] == ""


def replacement_source(previous="Veronica Vaccaro", current="Mario Verdi", effective="2026-01-01"):
    return [{"documento_id": "replacement", "sha256": "b" * 64, "prove": [
        {"codice": "identita_congiunta_provvedimento", "esito": "ok", "dettaglio": {"complete_match": True}},
        {"codice": "sostituzione_giudice", "esito": "ok", "dettaglio": {
            "precedente": previous, "nuovo": current, "decorrenza": effective,
            "passaggio": "Clausola esplicita della fonte verificata",
        }},
    ]}]


def test_replacement_is_extracted_only_with_explicit_effective_date():
    text = TEXT.replace("Veronica Vaccaro", "Mario Verdi")
    text += "\nin sostituzione del giudice Veronica Vaccaro, con decorrenza dal 01/01/2026\n"
    facts = estrai_giudice(text, fascicolo=case())
    detail = next(p["dettaglio"] for p in facts[0].prove if p["codice"] == "sostituzione_giudice")
    assert detail["precedente"] == "Veronica Vaccaro" and detail["decorrenza"] == "2026-01-01"
    assert not any(p["codice"] == "sostituzione_giudice" for p in estrai_giudice(text, fascicolo=case(), origine="ocr")[0].prove)


def test_documented_replacement_preserves_history_and_replay(backend):
    writer = GiudiceFascicoloRepository(backend)
    writer.consegna("f", "Veronica Vaccaro", [{"documento_id": "initial"}])
    sources = replacement_source()
    assert writer.consegna("f", "Mario Verdi", sources)["stato"] == "consegnato"
    assert writer.consegna("f", "Mario Verdi", sources)["stato"] == "gia_presente"
    rows = backend.conn.execute("SELECT dettagli FROM audit_log ORDER BY timestamp").fetchall()
    assert len(rows) == 2
    assert json.loads(rows[1][0])["precedente"] == "Veronica Vaccaro"
    assert json.loads(rows[0][0])["giudice"] == "Veronica Vaccaro"
    assert backend.conn.execute("SELECT giudice FROM fascicoli").fetchone()[0] == "Mario Verdi"


@pytest.mark.parametrize("sources", [replacement_source(effective="2099-01-01"), replacement_source(previous="Altro Magistrato"),
                                    replacement_source(effective="non valida")])
def test_uncertain_or_future_replacement_does_not_overwrite(backend, sources):
    writer = GiudiceFascicoloRepository(backend)
    writer.consegna("f", "Veronica Vaccaro", [{"documento_id": "initial"}])
    assert writer.consegna("f", "Mario Verdi", sources)["stato"] == "discordante"
    assert backend.conn.execute("SELECT giudice FROM fascicoli").fetchone()[0] == "Veronica Vaccaro"


def test_manual_judge_is_preserved_despite_replacement_source(backend):
    backend.conn.execute("UPDATE fascicoli SET giudice='Veronica Vaccaro',dati_json=?", (json.dumps({"giudice": "Veronica Vaccaro"}),))
    backend.conn.commit()
    assert GiudiceFascicoloRepository(backend).consegna("f", "Mario Verdi", replacement_source())["stato"] == "discordante"


def test_current_sources_require_a_documented_chain_not_only_pending_name():
    from pct.registro_letture import Fatto
    from web.services.giudice_fascicolo_runtime import cronologia_concordante

    old = Fatto(categoria="metadato_fascicolo", campo="giudice", valore="Veronica Vaccaro", verifica="verificata")
    new = Fatto(categoria="metadato_fascicolo", campo="giudice", valore="Mario Verdi", verifica="verificata")
    assert not cronologia_concordante([old, new], new.valore)
    new.prove = replacement_source()[0]["prove"]
    assert cronologia_concordante([old, new], new.valore)
    unrelated = Fatto(categoria="metadato_fascicolo", campo="giudice", valore="Anna Bianchi", verifica="verificata")
    assert not cronologia_concordante([old, new, unrelated], new.valore)
    new.prove = replacement_source(effective="2099-01-01")[0]["prove"]
    assert not cronologia_concordante([old, new], new.valore)
