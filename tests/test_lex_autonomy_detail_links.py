"""Allineamento del drill-down Lex coi pattern di produzione.

Le regole di `lex/autonomy/detail_links.py` sono copie versionate della
conoscenza di produzione: questi test falliscono se le due parti divergono
(marker Cassazione) o se i pattern smettono di riconoscere le forme reali
censite nella matrice di ricerca (schede Consulta, provvedimenti G.A.).
"""

from __future__ import annotations

from lex.autonomy.detail_links import (
    CASSAZIONE_DETAIL_URL_MARKERS,
    extract_detail_links,
    rule_for,
)


def test_marker_cassazione_identici_alla_produzione():
    from pct.legal_update_source_parsers import (
        CASSAZIONE_DETAIL_URL_MARKERS as MARKER_PRODUZIONE,
    )

    assert tuple(CASSAZIONE_DETAIL_URL_MARKERS) == tuple(MARKER_PRODUZIONE)


def test_schede_consulta_reali_riconosciute():
    # URL reali censiti in pct/legal_practice_research_matrix.py.
    rule = rule_for("https://www.cortecostituzionale.it/")
    assert rule is not None and rule.source == "corte_costituzionale"
    for url in (
        "https://www.cortecostituzionale.it/scheda-pronuncia/2010/80",
        "https://www.cortecostituzionale.it/scheda-pronuncia/2016/275",
        "https://www.cortecostituzionale.it/scheda-pronuncia/2018/194",
        "https://www.cortecostituzionale.it/scheda-pronuncia/2024/128",
    ):
        assert rule.is_detail_url(url), url


def test_provvedimento_ga_reale_riconosciuto():
    # Forma censita in pct/legal_practice_research_matrix.py (Cons. St., A.P. 10/2020).
    url = (
        "https://www.giustizia-amministrativa.it/documents/20142/1717313/"
        "Cons.%2BSt.%2C%2BA.P.%2C%2Bsent.%2B02.04.2020%2C%2Bn.%2B10%28n.%2B45%2B-%2B14.04.20%29.pdf/"
        "16b7381c-9e68-35a1-b217-d9735b03b0d6"
    )
    rule = rule_for("https://www.giustizia-amministrativa.it/dcsnprr")
    assert rule is not None and rule.source == "giustizia_amministrativa"
    assert rule.is_detail_url(url)
    html = f'<a href="{url}">A.P. 10/2020</a>'
    assert extract_detail_links("https://www.giustizia-amministrativa.it/dcsnprr", html, limit=2) == [url]


def test_dettaglio_cassazione_produzione_riconosciuto_dal_drill_down():
    from pct.legal_update_source_parsers import _cassazione_detail_url

    url = "https://www.cortedicassazione.it/it/civile_dettaglio.page?contentId=SZC51228"
    assert _cassazione_detail_url(url)  # la produzione lo accetta
    rule = rule_for("https://www.cortedicassazione.it/it/giurisprudenza_civile.page")
    assert rule is not None and rule.is_detail_url(url)  # e il drill-down pure
