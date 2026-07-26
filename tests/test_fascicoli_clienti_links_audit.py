import json
from pathlib import Path

from pct.clienti import GestioneClienti
from pct.fascicoli import Fascicolo, TipoFascicolo
from pct.storage import StudioDB
from scripts.audit_fascicoli_clienti_links import audit_fascicoli_clienti_links


def _seed_orphan_fascicolo(studio_db: StudioDB) -> None:
    fascicolo = Fascicolo(
        id="B494AAB9",
        numero="2026/344",
        titolo="Martorano Mara c. MIM",
        tipo=TipoFascicolo.LAVORO,
        id_cliente="BA82D89F",
        nome_cliente="Martorano Mara",
        avvocato_referente="Avv. Giuseppe Montagnese",
    )
    payload = fascicolo.to_dict()
    conn = studio_db.conn
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        """
        INSERT INTO fascicoli
        (id, numero, titolo, tipo, stato, id_cliente, nome_cliente,
         tribunale, sezione, giudice, numero_rg, anno_rg,
         controparte, avvocato_referente, avvocato_dominus,
         data_apertura, data_chiusura, oggetto, note, creato_il,
         attivita_json, documenti_json, scadenze_json,
         profilo_deposito_json, dati_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            fascicolo.id,
            fascicolo.numero,
            fascicolo.titolo,
            fascicolo.tipo.value,
            fascicolo.stato.value,
            fascicolo.id_cliente,
            fascicolo.nome_cliente,
            fascicolo.tribunale,
            fascicolo.sezione,
            fascicolo.giudice,
            fascicolo.numero_rg,
            str(fascicolo.anno_rg) if fascicolo.anno_rg else "",
            fascicolo.controparte,
            fascicolo.avvocato_referente,
            fascicolo.avvocato_dominus,
            fascicolo.data_apertura,
            fascicolo.data_chiusura,
            fascicolo.oggetto,
            fascicolo.note,
            fascicolo.creato_il,
            json.dumps(payload.get("attivita", []), ensure_ascii=False),
            json.dumps(payload.get("documenti", []), ensure_ascii=False),
            json.dumps(payload.get("depositi_pct", []), ensure_ascii=False),
            json.dumps(payload.get("profilo_deposito", {}), ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")


def test_audit_fascicoli_clienti_links_ripara_cliente_orfano(tmp_path: Path):
    studio_db_path = tmp_path / "studio.db"
    studio_db = StudioDB(str(studio_db_path))
    clienti_json = tmp_path / "clienti" / "anagrafica.json"
    _seed_orphan_fascicolo(studio_db)

    audit = audit_fascicoli_clienti_links(studio_db_path, clienti_json=clienti_json)

    assert audit["ok"] is False
    assert audit["source_of_truth"] == "sqlite"
    assert audit["json_authoritative"] is False
    assert audit["orphans"][0]["numero"] == "2026/344"
    assert audit["orphans"][0]["id_cliente"] == "BA82D89F"

    repaired = audit_fascicoli_clienti_links(
        studio_db_path,
        clienti_json=clienti_json,
        repair=True,
    )

    assert repaired["ok"] is True
    assert repaired["repaired"] == ["BA82D89F"]
    row = studio_db.conn.execute(
        "SELECT cognome, nome FROM clienti WHERE id = ?",
        ("BA82D89F",),
    ).fetchone()
    assert dict(row) == {"cognome": "Martorano", "nome": "Mara"}
    mirror = json.loads(clienti_json.read_text(encoding="utf-8"))
    assert mirror["BA82D89F"]["cognome"] == "Martorano"
    assert mirror["BA82D89F"]["nome"] == "Mara"

    clienti_repo = GestioneClienti(db_path=str(clienti_json), studio_db=studio_db)
    cliente = clienti_repo.get("BA82D89F")
    assert cliente is not None
    assert cliente.nome_completo == "Martorano Mara"


def test_cliente_riparato_resta_visibile_con_documento_storico_extra(tmp_path: Path):
    studio_db_path = tmp_path / "studio.db"
    studio_db = StudioDB(str(studio_db_path))
    clienti_json = tmp_path / "clienti" / "anagrafica.json"
    _seed_orphan_fascicolo(studio_db)
    repaired = audit_fascicoli_clienti_links(
        studio_db_path,
        clienti_json=clienti_json,
        repair=True,
    )
    assert repaired["ok"] is True

    row = studio_db.conn.execute(
        "SELECT dati_json FROM clienti WHERE id = ?",
        ("BA82D89F",),
    ).fetchone()
    payload = json.loads(row["dati_json"])
    payload["documento"]["file_path"] = "documenti/storici/carta-identita.pdf"
    studio_db.conn.execute(
        "UPDATE clienti SET dati_json = ? WHERE id = ?",
        (json.dumps(payload, ensure_ascii=False), "BA82D89F"),
    )
    studio_db.conn.commit()

    clienti_repo = GestioneClienti(db_path=str(clienti_json), studio_db=studio_db)
    cliente = clienti_repo.get("BA82D89F")
    assert cliente is not None
    assert cliente.nome_completo == "Martorano Mara"
