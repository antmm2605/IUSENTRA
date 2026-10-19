import json
import sqlite3

import pytest

from pct.fatturazione import Parcella, StatoParcella, VoceParcella
from web.services.fascicolo_invoice_options import invoice_options


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            "CREATE TABLE fascicoli(id TEXT PRIMARY KEY,id_cliente TEXT DEFAULT 'controlled-client',dati_json TEXT DEFAULT '{}');CREATE TABLE parcelle(id TEXT PRIMARY KEY,id_fascicolo TEXT,stato TEXT,dati_json TEXT);CREATE INDEX by_case ON parcelle(id_fascicolo);INSERT INTO fascicoli(id) VALUES ('case'),('other');"
        )

    def fetchall_readonly(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def add(self, key, *, case="case", state="BOZZA", amount=1000, paid_date=""):
        p = Parcella(
            id=key,
            numero=key,
            id_cliente="controlled-client",
            id_fascicolo=case,
            data_emissione="2026-10-19",
            data_scadenza="",
            voci=[VoceParcella(descrizione="Controlled", quantita=1, prezzo_unitario=amount)],
            applica_iva=False,
            applica_cassa=False,
            stato=StatoParcella(state),
            data_pagamento=paid_date,
        )
        self.conn.execute("INSERT INTO parcelle VALUES (?,?,?,?)", (key, case, state, json.dumps(p.to_dict())))
        return p


def test_choices_include_open_and_paid_without_preferring_the_old_payment():
    db = Database()
    db.add("01", state="PAGATA", paid_date="2026-10-13")
    db.add("02")
    db.add("03", case="other")
    db.add("04", state="ANNULLATA")
    result = invoice_options(db, "case")
    assert [x["id"] for x in result["items"]] == ["01", "02"]
    assert result["items"][0]["dataPagamento"] == "2026-10-13"
    assert result["items"][1]["stato"] == "BOZZA"
    assert not result["items"][0]["canRegister"]
    assert result["items"][1]["canRegister"]
    assert all(len(x["revision"]) == 64 for x in result["items"])


def test_pagination_is_bounded_and_has_no_duplicates():
    db = Database()
    for n in range(123):
        db.add(f"{n:03}")
    first = invoice_options(db, "case")
    second = invoice_options(db, "case", cursor=first["nextCursor"])
    third = invoice_options(db, "case", cursor=second["nextCursor"])
    assert [len(x["items"]) for x in [first, second, third]] == [50, 50, 23]
    keys = [x["id"] for page in [first, second, third] for x in page["items"]]
    assert len(set(keys)) == 123 and not third["hasMore"] and not third["nextCursor"]


def test_paid_missing_date_is_explicit_and_not_replaced_by_today():
    db = Database()
    db.add("01", state="PAGATA")
    item = invoice_options(db, "case")["items"][0]
    assert not item["canRegister"] and "Data" in item["reason"] and item["dataPagamento"] == ""


def test_corrupt_link_is_not_silently_skipped():
    db = Database()
    p = db.add("01")
    data = p.to_dict()
    data["id_fascicolo"] = "other"
    db.conn.execute("UPDATE parcelle SET dati_json=?", (json.dumps(data),))
    with pytest.raises(ValueError, match="discordante"):
        invoice_options(db, "case")


def test_reader_never_writes_or_creates_schema():
    db = Database()
    db.add("01")
    before = "\n".join(db.conn.iterdump())
    forbidden = {
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_INDEX,
    }
    db.conn.set_authorizer(lambda op, *args: sqlite3.SQLITE_DENY if op in forbidden else sqlite3.SQLITE_OK)
    assert invoice_options(db, "case")["items"]
    assert "\n".join(db.conn.iterdump()) == before


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 101}, {"limit": True}, {"cursor": "x" * 129}])
def test_invalid_requests_fail_before_query(kwargs):
    db = Database()
    with pytest.raises(ValueError):
        invoice_options(db, "case", **kwargs)


def test_missing_case_and_empty_case_are_distinct():
    db = Database()
    with pytest.raises(KeyError):
        invoice_options(db, "absent")
    assert invoice_options(db, "case")["items"] == []


def test_paid_receipt_keeps_registered_amount_when_document_total_changed():
    db = Database()
    db.add("01", state="PAGATA", amount=1200, paid_date="2026-10-13")
    payment = {"status": "pagato", "proforma_id": "01", "incasso_importo": 1000, "data_pagamento": "2026-10-13"}
    db.conn.execute(
        "UPDATE fascicoli SET dati_json=? WHERE id=?", (json.dumps({"pagamenti": {"parcella": payment}}), "case")
    )
    item = invoice_options(db, "case")["items"][0]
    assert item["totale"] == 1200 and item["registeredAmount"] == 1000
    assert item["canRegister"]


def test_conflicting_registered_receipts_are_not_merged():
    db = Database()
    db.add("01", state="PAGATA", paid_date="2026-10-13")
    first = {"status": "pagato", "proforma_id": "01", "incasso_importo": 1000}
    second = dict(first, incasso_importo=999)
    db.conn.execute(
        "UPDATE fascicoli SET dati_json=? WHERE id=?",
        (json.dumps({"pagamenti": {"parcella": first, "liquidazione_giudice": second}}), "case"),
    )
    item = invoice_options(db, "case")["items"][0]
    assert item["registeredAmount"] is None and not item["canRegister"]
    assert "discordante" in item["reason"]


def test_native_postgres_selection_is_readonly_and_paginated():
    import os
    from tests.test_condivisioni_sql_repository import SQLFactory

    if not os.getenv("AUDIT_POSTGRES_PASSWORD"):
        pytest.skip("PostgreSQL controllato non configurato.")
    factory = SQLFactory("postgresql")
    try:
        storage = factory.new()
        db = Database.__new__(Database)
        db.conn = storage.conn
        db.conn.execute(
            "CREATE TABLE fascicoli(id TEXT PRIMARY KEY,id_cliente TEXT DEFAULT 'controlled-client',dati_json TEXT DEFAULT '{}')"
        )
        db.conn.execute("CREATE TABLE parcelle(id TEXT PRIMARY KEY,id_fascicolo TEXT,stato TEXT,dati_json TEXT)")
        db.conn.execute("CREATE INDEX by_case ON parcelle(id_fascicolo)")
        db.conn.execute("INSERT INTO fascicoli(id) VALUES (?)", ("case",))
        for number in range(123):
            db.add(f"{number:03}")
        factory.commit(storage)
        db.conn.execute("SET TRANSACTION READ ONLY")
        first = invoice_options(db, "case")
        second = invoice_options(db, "case", cursor=first["nextCursor"])
        third = invoice_options(db, "case", cursor=second["nextCursor"])
        keys = [item["id"] for page in (first, second, third) for item in page["items"]]
        assert len(keys) == len(set(keys)) == 123
        assert [len(page["items"]) for page in (first, second, third)] == [50, 50, 23]
        assert not third["hasMore"]
    finally:
        factory.close()


def test_foreign_client_invoice_is_explicit_and_cannot_be_selected():
    db = Database()
    db.add("01")
    db.conn.execute("UPDATE fascicoli SET id_cliente=? WHERE id=?", ("another-client", "case"))
    item = invoice_options(db, "case")["items"][0]
    assert not item["canRegister"] and "Cliente" in item["reason"]


def test_native_postgres_state_transition_checks_revision_before_writing():
    import os
    import re
    from types import MethodType
    from pct.database import SCHEMA_SQL
    from pct.fatturazione import GestioneFatturazione, ParcellaConcurrentUpdate, parcella_revision
    from pct.storage_postgres import PostgresStudioDB
    from tests.test_condivisioni_sql_repository import SQLFactory

    if not os.getenv("AUDIT_POSTGRES_PASSWORD"):
        pytest.skip("PostgreSQL controllato non configurato.")
    factory = SQLFactory("postgresql")
    try:
        storage = factory.new()
        storage.backend_kind = "postgresql"
        storage.salva_tabella = MethodType(PostgresStudioDB.salva_tabella, storage)
        storage.conn.execute("CREATE TABLE clienti(id TEXT PRIMARY KEY)")
        storage.conn.execute("CREATE TABLE fascicoli(id TEXT PRIMARY KEY)")
        ddl = re.search(r"CREATE TABLE IF NOT EXISTS parcelle \(.*?\);", SCHEMA_SQL, re.S).group()
        storage.conn.execute(ddl)
        storage.conn.execute("INSERT INTO clienti VALUES (?)", ("client",))
        storage.conn.execute("INSERT INTO fascicoli VALUES (?)", ("case",))
        factory.commit(storage)
        invoice = Parcella(
            id="invoice",
            numero="2026/001",
            id_cliente="client",
            id_fascicolo="case",
            data_emissione="2026-10-19",
            data_scadenza="",
            voci=[VoceParcella(descrizione="Controlled", quantita=1, prezzo_unitario=1000)],
            applica_iva=False,
            applica_cassa=False,
            stato=StatoParcella.EMESSA,
        )
        manager = GestioneFatturazione.__new__(GestioneFatturazione)
        manager._studio_db = storage
        manager._parcelle = {invoice.id: invoice}
        manager._salva_parcella(invoice)
        revision = parcella_revision(invoice)
        newer = Parcella.from_dict(invoice.to_dict())
        newer.note = "Aggiornamento concorrente persistito"
        manager._salva_parcella(newer)
        with pytest.raises(ParcellaConcurrentUpdate):
            manager.cambia_stato(invoice.id, StatoParcella.PAGATA, expected_revision=revision)
        assert manager.get(invoice.id).to_dict() == invoice.to_dict()
        persisted = json.loads(
            storage.conn.execute("SELECT dati_json FROM parcelle WHERE id=?", (invoice.id,)).fetchone()[0]
        )
        assert persisted["stato"] == "EMESSA" and persisted["note"] == newer.note
        manager._parcelle[invoice.id] = newer
        manager.cambia_stato(
            invoice.id, StatoParcella.PAGATA, data_pagamento="2026-10-19", expected_revision=parcella_revision(newer)
        )
        persisted = json.loads(
            storage.conn.execute("SELECT dati_json FROM parcelle WHERE id=?", (invoice.id,)).fetchone()[0]
        )
        assert persisted["stato"] == "PAGATA" and persisted["data_pagamento"] == "2026-10-19"
    finally:
        factory.close()


@pytest.mark.parametrize("status", [{"status": "PAGATA"}, {"stato": "saldata"}, {"pagato": True}])
def test_legacy_receipt_formats_use_shared_normalization(status):
    db = Database()
    db.add("01", state="PAGATA", paid_date="2026-10-13")
    payment = dict(status, proforma_id="01", incasso_importo="1.000,00", data_pagamento="2026-10-13")
    db.conn.execute(
        "UPDATE fascicoli SET dati_json=? WHERE id=?", (json.dumps({"pagamenti": {"parcella": payment}}), "case")
    )
    item = invoice_options(db, "case")["items"][0]
    assert item["canRegister"] and item["registeredAmount"] == 1000


def test_conflicting_historical_payment_date_is_not_overwritten():
    db = Database()
    db.add("01", state="PAGATA", paid_date="2026-10-13")
    payment = {"status": "pagato", "proforma_id": "01", "incasso_importo": 1000, "data_pagamento": "2026-10-12"}
    db.conn.execute(
        "UPDATE fascicoli SET dati_json=? WHERE id=?", (json.dumps({"pagamenti": {"parcella": payment}}), "case")
    )
    item = invoice_options(db, "case")["items"][0]
    assert not item["canRegister"] and "Data" in item["reason"]
    assert item["dataPagamento"] == "2026-10-13"
