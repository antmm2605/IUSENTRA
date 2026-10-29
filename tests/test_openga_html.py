"""HTML ufficiale: contratti con testo interamente sintetico, mai decisioni pubblicate in test."""
from hashlib import sha256
from urllib.parse import urlencode

import pytest

from pct.openga_documento import DocumentoNonVerificato, leggi_documento
from pct.openga_html import is_official_html, leggi_html
from pct.openga_organi import verifica_organo, verifica_tipo


def fixture_html(*, extra_appeal="", signatures="", header="", closing=""):
    header = header or "Il Tribunale Amministrativo Regionale per il Lazio"
    closing = closing or "Così deciso in Roma nella camera di consiglio del 4 gennaio 2027."
    signatures = signatures or "<table><tr><td>L'ESTENSORE</td><td>IL PRESIDENTE</td></tr><tr><td>Giudice Alfa</td><td>Giudice Beta</td></tr></table>"
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'>Pubblicato il 05/01/2027"
        "<style>p {font-size: 12pt}</style></head><body>"
        "<p>N. 00061/2027 REG.PROV.COLL.</p><p>N. 00123/2026 REG.RIC.</p>" + extra_appeal +
        "<p>REPUBBLICA ITALIANA</p><p>IN NOME DEL POPOLO ITALIANO</p><p>" + header +
        "</p><p>(Sezione di prova)</p><p>ha pronunciato la seguente</p><p>SENTENZA</p>"
        "<p>TESTO SINTETICO DI COLLAUDO. Nessuna decisione reale e nessuna parte reale.</p>"
        "<p>La richiesta di prova viene esaminata conservando integralmente condizioni, eccezioni e riferimenti. "
        "Il riferimento a Latina nei fatti non identifica la sede del tribunale.</p>"
        "<p>P.Q.M.</p><p>Il tribunale dispone il risultato sintetico di collaudo, senza alcun effetto giuridico.</p>"
        "<p>" + closing + "</p>" + signatures + "<p>IL SEGRETARIO</p><br></body></html>").encode()


def read(raw, *, appeal="202600123", **overrides):
    args = {"schema": "tar_rm", "anno": 2027, "numero": 61, "ricorso": appeal, "acquisita_il": "06/01/2027"}
    args.update(overrides)
    url = "https://mdp.giustizia-amministrativa.it/visualizza/?" + urlencode({
        "nodeRef": "", "schema": "tar_rm", "nrg": appeal,
        "nomeFile": "202700061_20.html", "subDir": "Provvedimenti"})
    return leggi_documento(raw, url=url, **args)


def test_official_html_preserves_original_complete_body_and_signature_cells():
    raw = fixture_html()
    result = read(raw)
    assert result["raw_sha256"] == sha256(raw).hexdigest()
    assert result["provenienza"]["sha256"] == sha256(result["testo"].encode()).hexdigest()
    assert result["provenienza"]["versione"] == "05/01/2027"
    assert result["provenienza"]["testo_integrale"] is True
    assert result["approvazione_avvocato"] is False
    assert result["formato_originale"] == "html"
    for marker in ("TESTO SINTETICO", "P.Q.M.", "Giudice Alfa", "Giudice Beta", "IL SEGRETARIO"):
        assert marker in result["testo"]
    assert "Giudice Alfa" in result["sezioni"]["sottoscrizioni"]
    assert "font-size" not in result["testo"]
    assert raw == fixture_html()


def test_signature_cells_with_paragraphs_are_not_read_twice():
    result = read(fixture_html(signatures="<table><tr><td><p>Firma Alfa</p></td><td>Firma Beta</td></tr></table>"))
    assert result["testo"].count("Firma Alfa") == result["testo"].count("Firma Beta") == 1


def test_joined_proceedings_accept_only_an_appeal_in_the_header():
    raw = fixture_html(extra_appeal="<p>N. 00124/2026 REG.RIC.</p>")
    assert read(raw, appeal="202600124")["provenienza"]["testo_integrale"]
    with pytest.raises(DocumentoNonVerificato):
        read(raw, appeal="202600125")


@pytest.mark.parametrize("old,new", [
    (b"00061/2027 REG.PROV.COLL.", b"00062/2027 REG.PROV.COLL."),
    (b"00123/2026 REG.RIC.", b"00125/2026 REG.RIC."),
    (b"</html>", b""),
    (b"<p>P.Q.M.</p>", b""),
    (b"05/01/2027", b"31/02/2027"),
    (b"<body>", b"<body>Contenuto che non deve essere ignorato"),
    (b"<body>", b"<body><script>alert('not executed')</script>"),
    (b"<body>", b"<body><iframe src='https://example.invalid/'></iframe>"),
    (b"<!DOCTYPE html>", b"<!DOCTYPE html SYSTEM 'https://example.invalid/external.dtd'>"),
    (b"<!DOCTYPE html>", b"<!DOCTYPE html [<!ENTITY payload SYSTEM 'file:///etc/passwd'>]>"),
    (b"<p>N. 00061/2027 REG.PROV.COLL.</p>", b"<p>N. 00061/2027 REG.PROV.COLL.</p><p>N. 00062/2027 REG.PROV.COLL.</p>"),
    (b"Pubblicato il 05/01/2027", b"Pubblicato il 05/01/2027 Pubblicato il 06/01/2027"),
])
def test_invalid_incomplete_active_or_mismatched_html_is_not_attested(old, new):
    with pytest.raises(DocumentoNonVerificato):
        read(fixture_html().replace(old, new))


@pytest.mark.parametrize("raw", [b"<html><body><p>Pagina non trovata</p></body></html>", b"", b"x" * 2_000_001])
def test_generic_and_oversized_responses_are_rejected(raw):
    with pytest.raises(DocumentoNonVerificato):
        read(raw)


def test_header_court_and_closing_city_are_independent_of_places_in_facts():
    raw = fixture_html()
    row = {"sede": "003", "tipo": "SENTENZA BREVE"}
    assert verifica_organo(raw, row) and verifica_tipo(raw, row)
    assert not verifica_organo(raw, dict(row, sede="001"))
    assert not verifica_organo(fixture_html(closing="Così deciso in Napoli nella camera di consiglio."), row)
    assert not verifica_organo(fixture_html(header="Il Tribunale Amministrativo Regionale per la Lombardia"), row)
    assert not verifica_tipo(raw, dict(row, tipo="DECRETO"))


def test_metadata_in_facts_cannot_replace_missing_header():
    raw = fixture_html().replace(b"<p>N. 00123/2026 REG.RIC.</p>", b"")
    raw = raw.replace(b"<p>P.Q.M.</p>", b"<p>N. 00123/2026 REG.RIC.</p><p>P.Q.M.</p>")
    with pytest.raises(DocumentoNonVerificato):
        read(raw)


def test_html_detection_does_not_convert_an_xml_decision_or_arbitrary_value():
    assert is_official_html(fixture_html())
    assert not is_official_html(b"<GA><Provvedimento/></GA>")
    assert not is_official_html(None)
    with pytest.raises(DocumentoNonVerificato):
        leggi_html("not bytes")
