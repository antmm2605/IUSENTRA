"""Ripristino delle udienze annullate dalla rettifica del 17/09/2026 solo con prova della cancelleria."""
from pct.udienze.ripristino_cancelleria import pianifica, prove_da_comunicazione

XML = ("<Comunicazione><NumeroRuolo>1234/2025</NumeroRuolo><Oggetto>DIFFERIMENTO UDIENZA</Oggetto>"
       "<Contenuto>Si comunica: DIFFERIMENTO ALLA UDIENZA DEL 12/03/2026 ore 09:30</Contenuto></Comunicazione>")
UFFICIO = "<mittente>tribunale.bari@civile.ptel.giustiziacert.it</mittente>"
NOTA = "Creata dalla lettura automatica dei documenti: da confermare.\nRettifica automatica: la lettura corrente esclude questa data come udienza. Fonti: x"


def _app(**k):
    base = {"id": "a1", "id_fascicolo": "f1", "tipo": "UDIENZA", "stato": "ANNULLATO", "data_ora": "2026-03-12T09:30:00", "procedimento": "RG 1234/2025", "note": NOTA}
    return {**base, **k}


def test_ripristina_solo_con_prova_di_un_ufficio_stesso_rg_e_data():
    prove = prove_da_comunicazione(XML, daticert=UFFICIO, pec_id="pec1", fascicolo_id="f1")
    assert [(p.rg, p.data) for p in prove] == [("1234/2025", "2026-03-12")]
    piano = pianifica([_app(), _app(id="a2", data_ora="2026-03-13T09:30:00"), _app(id="a3", procedimento="RG 99/2025"),
                       _app(id="a4", note="Annullata dall'avvocato"), _app(id="a5", stato="PROGRAMMATO")], prove)
    assert [v["id"] for v in piano.ripristinare] == ["a1"] and piano.senza_prova == 2
    assert piano.ripristinare[0]["prova"]["pec_id"] == "pec1"


def test_busta_non_di_un_ufficio_non_prova_nulla():
    assert prove_da_comunicazione(XML, daticert="<mittente>avv@pec.it</mittente>", pec_id="p") == []


def test_data_dell_udienza_revocata_non_e_una_prova():
    xml = XML.replace("DIFFERIMENTO ALLA UDIENZA DEL 12/03/2026 ore 09:30",
                      "REVOCA UDIENZA DEL 12/03/2026 E FISSATO TERMINE PER NOTE IN SOST. UDIENZA il 20/03/2026")
    assert [p.data for p in prove_da_comunicazione(xml, daticert=UFFICIO, pec_id="p")] == ["2026-03-20"]


def test_script_dry_run_e_apply_su_database_di_prova(tmp_path):
    import json
    import sqlite3
    import subprocess
    import sys
    import zipfile
    db = tmp_path / "studio.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE appuntamenti(id TEXT, tipo TEXT, stato TEXT, note TEXT, modificato_il TEXT, dati_json TEXT)")
        c.execute("CREATE TABLE email_mailbox_records(message_key TEXT, mailbox_kind TEXT, payload_json TEXT)")
        c.execute("CREATE TABLE audit_log(id TEXT, timestamp TEXT, id_utente TEXT, username TEXT, azione TEXT, risorsa_tipo TEXT, risorsa_id TEXT, dettagli TEXT, ip TEXT, esito TEXT)")
        a = _app()
        c.execute("INSERT INTO appuntamenti VALUES(?,?,?,?,?,?)", (a["id"], "UDIENZA", "ANNULLATO", NOTA, "", json.dumps(a)))
        c.execute("INSERT INTO email_mailbox_records VALUES(?,?,?)", ("pec1", "pec", json.dumps({"linked_fascicolo_id": "f1", "allegati": [
            {"nome": "Comunicazione.xml", "archivio_membro": "c"}, {"nome": "daticert.xml", "archivio_membro": "d"}]})))
    arc = tmp_path / "archivio.zip"
    with zipfile.ZipFile(arc, "w") as z:
        z.writestr("c", XML)
        z.writestr("d", UFFICIO)
    cmd = [sys.executable, "scripts/ripristina_udienze_cancelleria.py", "--studio-db", str(db), "--archivio", str(arc)]
    dry = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    assert dry["dry_run"] and dry["da_ripristinare"] == 1
    out = json.loads(subprocess.run(cmd + ["--apply", "--backup-dir", str(tmp_path / "bk")], capture_output=True, text=True, check=True).stdout)
    assert out["ripristinate"] == 1 and (tmp_path / "bk").exists()
    with sqlite3.connect(out["backup"]) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert backup.execute("SELECT stato FROM appuntamenti").fetchone()[0] == "ANNULLATO"
        assert backup.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 0
    with sqlite3.connect(db) as c:
        stato, dati = c.execute("SELECT stato, dati_json FROM appuntamenti").fetchone()
        assert stato == "PROGRAMMATO" and json.loads(dati)["stato"] == "PROGRAMMATO" and "Ripristinata" in json.loads(dati)["note"]
        assert c.execute("SELECT count(*) FROM audit_log WHERE azione='RIPRISTINO_UDIENZA'").fetchone()[0] == 1


def test_stesso_rg_e_data_non_autorizzano_un_altro_fascicolo():
    prove = prove_da_comunicazione(XML, daticert=UFFICIO, pec_id="p", fascicolo_id="f2")
    assert not pianifica([_app()], prove).ripristinare
    prove = prove_da_comunicazione(XML, daticert=UFFICIO, pec_id="p")
    assert not pianifica([_app()], prove).ripristinare


def test_mittente_simile_e_data_impossibile_non_sono_prove():
    assert not prove_da_comunicazione(XML, daticert=UFFICIO.replace("giustiziacert.it", "giustiziacert.it.evil.invalid"), pec_id="p")
    assert not prove_da_comunicazione(XML.replace("12/03/2026", "31/02/2026"), daticert=UFFICIO, pec_id="p")
