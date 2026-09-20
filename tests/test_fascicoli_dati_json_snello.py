"""I documenti di un fascicolo non devono stare salvati due volte.

`dati_json` conteneva il fascicolo intero, documenti compresi, e le stesse
collezioni stavano gia' nelle loro colonne (`documenti_json`, `attivita_json`,
`scadenze_json`). Ogni archivio era scritto due volte, e ogni lettura lo
pagava due volte. Ora la colonna e' la fonte e `dati_json` non le duplica.
"""

from __future__ import annotations

import json
from pathlib import Path

from pct.fascicoli import Documento, GestioneFascicoli, TipoDocumento, TipoFascicolo


def _studio(tmp_path: Path):
    from pct.storage import StudioDB

    db = StudioDB.get(str(tmp_path / "studio.db"))
    db.ensure_schema()
    return db


def _repo(tmp_path: Path, **kwargs) -> GestioneFascicoli:
    return GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        studio_db=_studio(tmp_path),
        **kwargs,
    )


def _con_documenti(repo: GestioneFascicoli, quanti: int = 4):
    fascicolo = repo.nuovo(
        titolo="Pratica con allegati",
        tipo=TipoFascicolo.CIVILE,
        nome_cliente="Cliente Uno",
        numero_rg="1100",
        anno_rg="2026",
    )
    fascicolo.documenti = [
        Documento(
            id=f"D{i}",
            nome=f"atto-{i}.pdf",
            tipo=TipoDocumento.ALTRO,
            percorso=f"/docs/{i}.pdf",
            note="x" * 200,
        )
        for i in range(quanti)
    ]
    repo._salva()
    return fascicolo


def _scrivi_dati_json(tmp_path: Path, fid: str, payload: dict) -> None:
    """Rimette la riga nel formato grasso di prima, per provare la convivenza."""
    import sqlite3

    with sqlite3.connect(str(tmp_path / "studio.db")) as conn:
        conn.execute(
            "UPDATE fascicoli SET dati_json = ? WHERE id = ?",
            (json.dumps(payload, ensure_ascii=False), fid),
        )
        conn.commit()


def _riga(tmp_path: Path, fid: str) -> dict:
    righe = _studio(tmp_path).fetchall_readonly(
        "SELECT * FROM fascicoli WHERE id = ?", (fid,)
    )
    return dict(righe[0])


def test_dati_json_non_contiene_piu_le_collezioni_gia_in_colonna(tmp_path: Path):
    repo = _repo(tmp_path)
    fascicolo = _con_documenti(repo)

    riga = _riga(tmp_path, fascicolo.id)
    dati = json.loads(riga["dati_json"])

    assert "documenti" not in dati
    assert "attivita" not in dati
    assert "depositi_pct" not in dati
    # Ma i documenti ci sono, nella loro colonna.
    assert len(json.loads(riga["documenti_json"])) == 4


def test_il_fascicolo_riletto_e_identico(tmp_path: Path):
    repo = _repo(tmp_path)
    fascicolo = _con_documenti(repo)
    atteso = fascicolo.to_dict()

    riletto = _repo(tmp_path).get(fascicolo.id)

    assert riletto is not None
    assert riletto.to_dict() == atteso
    assert len(riletto.documenti) == 4


def test_una_riga_scritta_col_vecchio_formato_si_legge_ancora(tmp_path: Path):
    """Nessuna migrazione obbligatoria: le righe grasse restano leggibili."""

    repo = _repo(tmp_path)
    fascicolo = _con_documenti(repo)
    atteso = fascicolo.to_dict()

    # Si riscrive la riga nel formato di prima: dati_json con tutto dentro.
    _scrivi_dati_json(tmp_path, fascicolo.id, atteso)

    riletto = _repo(tmp_path).get(fascicolo.id)

    assert riletto is not None
    assert len(riletto.documenti) == 4
    assert riletto.to_dict() == atteso


def test_se_le_due_copie_divergono_vince_la_colonna(tmp_path: Path):
    """La colonna e' la fonte: una copia rimasta indietro non deve tornare a galla."""

    repo = _repo(tmp_path)
    fascicolo = _con_documenti(repo)

    vecchio = dict(fascicolo.to_dict())
    vecchio["documenti"] = []  # copia stantia dentro dati_json
    _scrivi_dati_json(tmp_path, fascicolo.id, vecchio)

    riletto = _repo(tmp_path).get(fascicolo.id)

    assert riletto is not None
    assert len(riletto.documenti) == 4  # quelli veri, dalla colonna


def test_la_riga_pesa_meno(tmp_path: Path):
    repo = _repo(tmp_path)
    fascicolo = _con_documenti(repo, quanti=30)

    riga = _riga(tmp_path, fascicolo.id)
    peso_dati = len(riga["dati_json"])
    peso_documenti = len(riga["documenti_json"])

    # I documenti non sono piu' dentro dati_json: pesano una volta sola.
    assert peso_dati < peso_documenti
