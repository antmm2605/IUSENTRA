"""Il cambio lettore conserva il dataset e le prove precedenti, senza ricopiare i corpi."""
import json
import sqlite3
import pytest
from tools.riconvalida_cache_akn import riqualifica_metadati


def test_cambio_lettore_azzera_solo_attestati_e_conserva_storico(tmp_path):
    conn=sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE normative_akn_chains(id TEXT,riscontro_lettore_sha256 TEXT NOT NULL DEFAULT '',riscontro_contenuti_sha256 TEXT NOT NULL DEFAULT '')")
    conn.execute("CREATE TABLE normative_akn_articles(testo TEXT)")
    conn.execute("INSERT INTO normative_akn_chains VALUES('atto',?,?)",('a'*64,'b'*64))
    conn.execute("INSERT INTO normative_akn_articles VALUES('Testo originale immutato')");conn.commit()
    old={"lettore_runtime":"a"*64,"originale_sha256":"c"*64,"qualificate":1,"errori":{}}
    (tmp_path/"stato.json").write_text(json.dumps(old))
    original_journal=json.dumps({"chain_id":"atto","lettore_runtime":"a"*64})+"\n"
    (tmp_path/"qualificate.jsonl").write_text(original_journal)
    result=riqualifica_metadati(conn,tmp_path,old,"d"*64)
    assert conn.execute("SELECT testo FROM normative_akn_articles").fetchone()[0]=="Testo originale immutato"
    assert conn.execute("SELECT riscontro_lettore_sha256,riscontro_contenuti_sha256 FROM normative_akn_chains").fetchone()==('','')
    from pathlib import Path
    history=Path(result["prove_precedenti"])
    assert (history/"qualificate.jsonl").read_text()==original_journal
    assert json.loads((history/"stato.json").read_text())==old
    assert not (tmp_path/"qualificate.jsonl").exists()
    assert result["qualificate"]==0 and result["ricontrollo_integrale_richiesto"] is True


def test_sigillo_assente_non_modifica_copia(tmp_path):
    conn=sqlite3.connect(":memory:")
    with pytest.raises(ValueError,match="Sigillo originale"):
        riqualifica_metadati(conn,tmp_path,{"lettore_runtime":"a"*64},"d"*64)
    assert list(tmp_path.iterdir())==[]
