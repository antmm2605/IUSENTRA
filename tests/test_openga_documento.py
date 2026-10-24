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
