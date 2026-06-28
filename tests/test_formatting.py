from pct.formatting import (
    format_date_it,
    format_datetime_it,
    format_decimal_it,
    format_euro_it,
    format_signed_euro_it,
    format_time_it,
    parse_datetime_rome,
)


def test_format_euro_it_usa_formato_italiano_con_simbolo():
    assert format_euro_it(1234.5) == "€ 1.234,50"
    assert format_euro_it("1.234,56") == "€ 1.234,56"
    assert format_euro_it("EUR 500,00") == "€ 500,00"


def test_format_decimal_it_e_signed_euro_it():
    assert format_decimal_it("500.0") == "500,00"
    assert format_signed_euro_it(12.3) == "+ € 12,30"
    assert format_signed_euro_it(-12.3) == "- € 12,30"


def test_format_datetime_it_converte_utc_in_ora_italiana():
    parsed = parse_datetime_rome("2026-06-28T19:30:19Z")

    assert parsed is not None
    assert parsed.strftime("%Y-%m-%d %H:%M:%S %Z") == "2026-06-28 21:30:19 CEST"
    assert format_date_it("2026-06-28T19:30:19Z") == "28/06/2026"
    assert format_time_it("2026-06-28T19:30:19Z") == "21:30"
    assert format_datetime_it("2026-06-28T19:30:19Z") == "28/06/2026 21:30"
    assert format_datetime_it("2026-06-28T19:30:19Z", include_timezone=True) == "28/06/2026 21:30 (Europe/Rome)"
