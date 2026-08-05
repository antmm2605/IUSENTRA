"""Regressioni della coda «Da lavorare adesso» della Regia Operativa.

Invarianti coperte:
- l'ordinamento e' deterministico per urgenza reale (scadute > oggi >
  critiche > udienze di oggi > PEC non lette > conferimenti > azioni);
- il conto alla rovescia e' aritmetica di calendario in italiano;
- ogni voce conserva il deep link verso l'evento e i duplicati per href
  vengono fusi.
"""

from datetime import date, timedelta
from types import SimpleNamespace

from web.services.react_regia_worklist import build_regia_worklist, countdown_scadenza

OGGI = date(2026, 8, 5)


def _parse_date(value):
    return value if isinstance(value, date) else None


def _enum_value(value):
    return str(getattr(value, "value", value) or "")


def _short_text(value, limit):
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _scadenza(id_, titolo, due, priorita="critica"):
    return SimpleNamespace(id=id_, titolo=titolo, descrizione="", data_scadenza=due, priorita=priorita)


def _build(**overrides):
    kwargs = dict(
        oggi=OGGI,
        scadenze=[],
        parse_date=_parse_date,
        enum_value=_enum_value,
        short_text=_short_text,
        priorita_urgenti={"critica", "alta"},
        agenda_rows=[],
        pec_rows=[],
        engagement_rows=[],
        operations=[],
    )
    kwargs.update(overrides)
    return build_regia_worklist(**kwargs)


def test_countdown_in_italiano_e_deterministico():
    assert countdown_scadenza(OGGI - timedelta(days=3), OGGI)[0] == "SCADUTA DA 3 GG"
    assert countdown_scadenza(OGGI - timedelta(days=1), OGGI)[0] == "SCADUTA IERI"
    assert countdown_scadenza(OGGI, OGGI)[0] == "SCADE OGGI"
    assert countdown_scadenza(OGGI + timedelta(days=1), OGGI)[0] == "SCADE DOMANI"
    assert countdown_scadenza(OGGI + timedelta(days=5), OGGI)[0] == "SCADE TRA 5 GG"
    assert countdown_scadenza(OGGI + timedelta(days=20), OGGI)[0] == "TRA 20 GG"
    assert countdown_scadenza(None, OGGI)[0] == ""


def test_ordinamento_per_urgenza_reale():
    rows = _build(
        scadenze=[
            _scadenza("s-futura", "Memoria 183", OGGI + timedelta(days=5)),
            _scadenza("s-scaduta", "Comparsa conclusionale", OGGI - timedelta(days=2)),
            _scadenza("s-oggi", "Deposito note", OGGI),
        ],
        agenda_rows=[
            {"id": "a1", "title": "Udienza Trib. Milano", "subtitle": "", "badge": "OGGI", "tone": "warning", "href": "/agenda/a1"},
            {"id": "a2", "title": "Appuntamento domani", "subtitle": "", "badge": "DOMANI", "tone": "primary", "href": "/agenda/a2"},
        ],
        pec_rows=[
            {"id": "p1", "title": "Tribunale", "subtitle": "Verbale", "unread": True, "href": "/email/messaggio/p1"},
            {"id": "p2", "title": "Controparte", "subtitle": "Letta", "unread": False, "href": "/email/messaggio/p2"},
        ],
        engagement_rows=[{"id": "e1", "title": "Cliente Rossi", "subtitle": "", "badge": "URGENTE", "tone": "danger", "href": "/preventivi?preventivo=e1"}],
        operations=[{"id": "op1", "title": "Azione regia", "subtitle": "", "badge": "Apri", "tone": "primary", "href": "/workspace-intelligente"}],
    )
    hrefs = [row["href"] for row in rows]
    assert hrefs == [
        "/scadenziario/s-scaduta",
        "/scadenziario/s-oggi",
        "/scadenziario/s-futura",
        "/agenda/a1",
        "/email/messaggio/p1",
        "/preventivi?preventivo=e1",
        "/workspace-intelligente",
    ]
    # L'appuntamento di domani e la PEC gia' letta non entrano in coda.
    assert "/agenda/a2" not in hrefs
    assert "/email/messaggio/p2" not in hrefs


def test_badge_conto_alla_rovescia_sulle_scadenze():
    rows = _build(scadenze=[_scadenza("s1", "Deposito", OGGI)])
    assert rows[0]["badge"] == "SCADE OGGI"
    assert rows[0]["tone"] == "danger"
    assert rows[0]["href"] == "/scadenziario/s1"


def test_scadenza_scaduta_entra_anche_senza_priorita_urgente():
    rows = _build(scadenze=[_scadenza("s1", "Deposito", OGGI - timedelta(days=1), priorita="media")])
    assert rows and rows[0]["badge"] == "SCADUTA IERI"


def test_dedup_per_href_e_limite():
    rows = _build(
        scadenze=[_scadenza("s1", "Deposito", OGGI)],
        operations=[
            {"id": "op1", "title": "Stessa scadenza", "subtitle": "", "href": "/scadenziario/s1"},
            {"id": "op2", "title": "Altra azione", "subtitle": "", "href": "/workspace-intelligente"},
        ],
    )
    assert [row["href"] for row in rows] == ["/scadenziario/s1", "/workspace-intelligente"]
    molti = _build(scadenze=[_scadenza(f"s{i}", f"Scadenza {i}", OGGI) for i in range(15)])
    assert len(molti) == 10
