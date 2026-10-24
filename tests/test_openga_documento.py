"""Documenti sintetici: nessun testo giudiziario reale nel repository."""
import pytest

from pct.openga_documento import DocumentoNonVerificato, leggi_documento

URL = ("https://mdp.giustizia-amministrativa.it/visualizza/?schema=tar_to"
       "&nrg=201900721&nomeFile=202300355_01.html&subDir=Provvedimenti")
XML = b"""<GA><Provvedimento><meta><descrittori>
<fascicolo anno="2023" n="00355"/></descrittori>
<ricorso NRG="201900721"/><rilascio>PRIVATE_PATH</rilascio>
<dataPubblicazione>24/04/2023</dataPubblicazione></meta>
<epigrafe>Tribunale sintetico</epigrafe><motivazione>Motivazione sintetica</motivazione>
<dispositivo>Dispositivo sintetico</dispositivo></Provvedimento></GA>"""


def read(raw=XML, **changes):
    options = {"url": URL, "schema": "tar_to", "anno": 2023, "numero": 355,
               "ricorso": "201900721", "acquisita_il": "24/10/2026"}
    options.update(changes)
    return leggi_documento(raw, **options)


def test_sections_and_provenance():
    result = read()
    assert "PRIVATE_PATH" not in result["testo"]
    assert result["sezioni"]["motivazione"] == "Motivazione sintetica"
    assert result["provenienza"]["testo_integrale"] is True
    assert result["approvazione_avvocato"] is False
    assert len(result["provenienza"]["sha256"]) == 64


@pytest.mark.parametrize("changes", [
    {"numero": 356}, {"anno": 2024}, {"ricorso": "201900722"},
    {"schema": "tar_rm"}, {"anno": True},
    {"url": URL.replace("mdp.giustizia-amministrativa.it", "example.org")},
    {"url": URL + "&nrg=201900721"}, {"acquisita_il": "31/02/2026"},
])
def test_mismatch_rejected(changes):
    with pytest.raises(DocumentoNonVerificato):
        read(**changes)


@pytest.mark.parametrize("raw", [
    b"<html>Ricerca ufficiale</html>",
    XML.replace(b'anno="2023"', b'anno="2022"'),
    XML.replace(b'NRG="201900721"', b'NRG="201900722"'),
    XML.replace(b"<dispositivo>Dispositivo sintetico</dispositivo>", b""),
    XML.replace(b"</GA>", b"<Provvedimento/></GA>"),
    b'<!DOCTYPE GA [<!ENTITY x "bad">]>' + XML,
    b"", b"not XML",
])
def test_incomplete_or_ambiguous_rejected(raw):
    with pytest.raises(DocumentoNonVerificato):
        read(raw)


def test_joined_cases_accept_only_a_register_explicitly_declared_in_metadata():
    # Like the public Roma 6342/2020: the catalog points to the second joined
    # case. The first register is not an exclusive document identity.
    joined = XML.replace(b'<ricorso NRG="201900721"/>',
                         b'<ricorso NRG="201800111"/><ricorso NRG="201900721"/>')
    assert read(joined)["provenienza"]["testo_integrale"]
    incidental = joined.replace(b'<ricorso NRG="201900721"/>', b'')
    incidental = incidental.replace(b"Motivazione sintetica", b"Riferimento 201900721 nei fatti")
    with pytest.raises(DocumentoNonVerificato):
        read(incidental)
    conflicting = joined.replace(b'</descrittori>',
        b'<fascicolo anno="2023" n="00356"/></descrittori>')
    with pytest.raises(DocumentoNonVerificato):
        read(conflicting)


def test_legacy_external_only_dtd_is_inert_and_original_hash_is_preserved():
    from hashlib import sha256

    from pct.openga_documento import parse_official_xml
    declared = b'<!DOCTYPE GA SYSTEM "http://192.0.2.1/unreachable.dtd">' + XML
    result = read(declared)
    assert result["testo"] == read()["testo"]
    assert result["raw_sha256"] == sha256(declared).hexdigest()
    assert not parse_official_xml(declared).getroottree().docinfo.doctype
    for unsafe in (
        b'<!DOCTYPE GA [<!ENTITY x SYSTEM "file:///etc/passwd">]>',
        b'<!DOCTYPE GA SYSTEM "https://example.invalid/x" [<!ENTITY x "boom">]>',
        b'<!DOCTYPE GA [<!ENTITY % p SYSTEM "https://example.invalid/x">%p;]>',
    ):
        with pytest.raises(DocumentoNonVerificato):
            read(unsafe + XML)


def test_quoted_doctype_in_document_text_is_never_removed():
    quoted = XML.replace(b"Motivazione sintetica",
        b'<![CDATA[Esempio tecnico: <!DOCTYPE GA SYSTEM "https://example.invalid/a"> nel testo]]>')
    assert '<!DOCTYPE GA SYSTEM "https://example.invalid/a">' in read(quoted)["testo"]
