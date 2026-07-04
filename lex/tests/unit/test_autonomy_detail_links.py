from __future__ import annotations

from lex.autonomy.detail_links import RULES, extract_detail_links, rule_for

_LISTA_CASSAZIONE = "https://www.cortedicassazione.it/it/giurisprudenza_civile.page"
_HTML_CASSAZIONE = """
<a href="/it/civile_dettaglio.page?contentId=SZC51228">Cass. civ. 12345/2026</a>
<a href="/it/civile_dettaglio.page?contentId=SZC51228">duplicato</a>
<a href="/it/civile_dettaglio.page">senza contentId: navigazione</a>
<a href="/it/su_dettaglio.page?contentId=SZU00042&amp;lang=it">Sezioni Unite</a>
<a href="https://www.facebook.com/it/civile_dettaglio.page?contentId=EVIL">dominio esterno</a>
<a href="/it/servizi.page?contentId=NAV1">altra pagina</a>
"""

_HOME_CONSULTA = "https://www.cortecostituzionale.it/"
_HTML_CONSULTA = """
<a href="/scheda-pronuncia/2024/128">Sentenza n. 128/2024</a>
<a href="https://www.cortecostituzionale.it/scheda-pronuncia/2016/275">Sentenza n. 275/2016</a>
<a href="/scheda-pronuncia/">indice senza estremi</a>
<a href="/comunicati">navigazione</a>
"""

_LISTA_GA = "https://www.giustizia-amministrativa.it/dcsnprr"
_HTML_GA = """
<a href="/documents/20142/1717313/Cons.%2BSt.%2C%2BA.P.%2C%2Bsent.%2B02.04.2020%2C%2Bn.%2B10.pdf/16b7381c-9e68-35a1-b217-d9735b03b0d6">A.P. 10/2020</a>
<a href="/documents/20142/999/relazione.docx">non è un PDF</a>
<a href="/web/guest/dcsnprr">navigazione</a>
"""


def test_cassazione_dettagli_estratti_assoluti_con_contentid_e_dedup():
    links = extract_detail_links(_LISTA_CASSAZIONE, _HTML_CASSAZIONE, limit=5)
    assert links == [
        "https://www.cortedicassazione.it/it/civile_dettaglio.page?contentId=SZC51228",
        "https://www.cortedicassazione.it/it/su_dettaglio.page?contentId=SZU00042&lang=it",
    ]


def test_cassazione_rispetta_il_tetto_limit():
    assert len(extract_detail_links(_LISTA_CASSAZIONE, _HTML_CASSAZIONE, limit=1)) == 1
    assert extract_detail_links(_LISTA_CASSAZIONE, _HTML_CASSAZIONE, limit=0) == []


def test_consulta_solo_schede_pronuncia_con_anno_e_numero():
    links = extract_detail_links(_HOME_CONSULTA, _HTML_CONSULTA, limit=5)
    assert links == [
        "https://www.cortecostituzionale.it/scheda-pronuncia/2024/128",
        "https://www.cortecostituzionale.it/scheda-pronuncia/2016/275",
    ]


def test_giustizia_amministrativa_solo_pdf_sotto_documents():
    links = extract_detail_links(_LISTA_GA, _HTML_GA, limit=5)
    assert len(links) == 1
    assert links[0].startswith("https://www.giustizia-amministrativa.it/documents/")
    assert ".pdf/16b7381c" in links[0]


def test_pagina_senza_regola_fail_closed():
    assert rule_for("https://www.garanteprivacy.it/") is None
    assert extract_detail_links("https://www.garanteprivacy.it/", _HTML_CONSULTA, limit=5) == []


def test_href_fuori_dominio_o_schema_scartati():
    html = '<a href="javascript:void(0)">x</a><a href="ftp://www.cortecostituzionale.it/scheda-pronuncia/2024/1">y</a>'
    assert extract_detail_links(_HOME_CONSULTA, html, limit=5) == []


def test_ogni_regola_ha_dominio_e_etichetta():
    for rule in RULES:
        assert rule.host_suffix and "." in rule.host_suffix
        assert rule.detail_label
        assert rule.matches_list(f"https://www.{rule.host_suffix}/" + rule.list_url_markers[0].split("/", 1)[-1])
