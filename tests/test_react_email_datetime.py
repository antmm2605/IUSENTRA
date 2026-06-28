from web.services.react_email_bridge import _parse_datetime


def test_react_email_bridge_converte_arrivo_utc_in_ora_italiana():
    parsed = _parse_datetime("2026-06-28T19:30:19Z")

    assert parsed is not None
    assert parsed.strftime("%Y-%m-%d %H:%M:%S") == "2026-06-28 21:30:19"
