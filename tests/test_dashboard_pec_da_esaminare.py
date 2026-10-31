"""Panoramica: «PEC da esaminare» esclude ricevute e comunicazioni già prese in carico dal presidio (31/10/2026)."""

from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from pct.email_client import StatoEmail
from web.blueprints import api_v1_react


def test_pec_da_esaminare_esclude_le_gia_presidiate(monkeypatch):
    posta = [
        SimpleNamespace(id="A", stato=StatoEmail.NON_LETTA, timestamp="2026-10-30T10:00:00", oggetto="ACCETTAZIONE"),
        SimpleNamespace(id="B", stato=StatoEmail.NON_LETTA, timestamp="2026-10-30T11:00:00", oggetto="Comunicazione"),
        SimpleNamespace(id="C", stato=StatoEmail.LETTA, timestamp="2026-10-30T12:00:00", oggetto="Letta"),
    ]
    monkeypatch.setattr(api_v1_react, "gestore_panoramica", lambda factory: SimpleNamespace(tutte=lambda cartella: posta))
    monkeypatch.setattr(api_v1_react, "_email_manager", lambda: None)
    monkeypatch.setattr(api_v1_react, "_ordinary_email_manager", lambda: None)
    monkeypatch.setattr(api_v1_react, "_id_email_presidiate", lambda: {"A"})
    # Archivio JSON configurato: la Panoramica usa la lettura completa del gestore.
    import web.services.email_storage_runtime as storage_runtime
    monkeypatch.setattr(storage_runtime, "create_email_mailbox", lambda *a, **k: SimpleNamespace())
    with Flask(__name__).app_context():
        _pec, _mail, da_esaminare = api_v1_react._email_rows()
    assert da_esaminare == 1
    etichette = {m["id"]: m["label"] for m in api_v1_react._metrics(
        urgent_actions=0, pec_unread=1, client_messages=0, expiring_quotes=0, missing_engagements_count=0)}
    assert etichette["pec"] == "PEC da esaminare"


def test_id_email_gia_presidiate_senza_archivio(tmp_path):
    from web.services.react_email_bridge import id_email_gia_presidiate

    assert id_email_gia_presidiate(str(tmp_path / "email" / "casella.json")) == set()


def _messaggio(chiave, data, stato="NON_LETTA", cartella="INBOX"):
    return {"id": chiave, "cartella": cartella, "stato": stato, "letta_il": "", "data": data,
            "oggetto": f"Oggetto {chiave}", "mittente": "cancelleria@giustiziacert.it", "auto_registrata": False}


def test_panoramica_legge_solo_righe_necessarie_della_casella_sql(tmp_path, monkeypatch):
    """V12: niente caricamento dell'intero catalogo (oltre 2.000 messaggi in produzione)."""
    from tests.mailbox_test_support import sql_mailbox
    from web.services.react_dashboard_email import quadro_cartella_arrivo

    casella = sql_mailbox(tmp_path / "studio" / "email" / "casella.json")
    record = {f"m{i:03d}": _messaggio(f"m{i:03d}", f"2026-10-{1 + i % 28:02d}T{8 + i % 10:02d}:00:00+01:00",
                                      stato="LETTA" if i % 3 else "NON_LETTA") for i in range(120)}
    record["cestino"] = _messaggio("cestino", "2026-10-31T23:00:00+01:00", cartella="CESTINO")
    record["naive"] = _messaggio("naive", "2026-10-31T09:30:00")
    casella.repository.save(record, actor_key="test", action="seed")
    monkeypatch.setattr(type(casella.repository), "load",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("catalogo intero caricato")))

    recenti, non_lette = quadro_cartella_arrivo(
        "ignorato", crea_casella=lambda *a, **k: casella,
        gestore_completo=lambda: (_ for _ in ()).throw(AssertionError("gestore completo")),
        parse=api_v1_react._parse_datetime, limite=5)

    assert [m.id for m in recenti][0] == "naive"  # data senza fuso letta come ora italiana, cestino escluso
    assert len(recenti) == 5 and all(m.cartella == "INBOX" for m in recenti)
    attese = {k for k, v in record.items() if v["cartella"] == "INBOX" and v["stato"] == "NON_LETTA"}
    assert non_lette == attese


def test_panoramica_con_casella_json_usa_il_gestore(monkeypatch):
    from web.services.react_dashboard_email import quadro_cartella_arrivo

    posta = [SimpleNamespace(id="X", stato=StatoEmail.NON_LETTA, timestamp="2026-10-30T10:00:00"),
             SimpleNamespace(id="Y", stato=StatoEmail.LETTA, timestamp="2026-10-31T10:00:00")]
    recenti, non_lette = quadro_cartella_arrivo(
        "casella.json", crea_casella=lambda *a, **k: SimpleNamespace(),
        gestore_completo=lambda: SimpleNamespace(tutte=lambda cartella: posta),
        parse=api_v1_react._parse_datetime, limite=5)
    assert [m.id for m in recenti] == ["Y", "X"] and non_lette == {"X"}
