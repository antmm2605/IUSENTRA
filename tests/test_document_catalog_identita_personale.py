"""Il documento d'identità del cliente si riconosce dalla scansione, non da un titolo.

Il 16/09/2026 «Carta d'identità.PDF» restava «da verificare»: l'OCR di una
carta non ha una riga d'intestazione che combaci con il titolo, e il nome del
file non cataloga. Qui la scansione si riconosce dai suoi campi, il cliente del
fascicolo la intesta, e il nome inequivoco basta finché il contenuto non è
leggibile; un atto che allega la carta d'identità resta un atto.
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.document_intelligence.catalog_context import fascicolo_catalog_context
from pct.document_intelligence.catalog_identita_personale import documento_identita_dal_nome, documento_identita_personale
from pct.document_intelligence.catalog_resolver import resolve_document_catalog
from tests.dati_catalogo_titoli import CTX_CIVILE

CIE = (
    "REPUBBLICA ITALIANA MINISTERO DELL'INTERNO\nCARTA DI IDENTITA' / IDENTITY CARD\nCOMUNE DI TORINO\n"
    "COGNOME / SURNAME BIANCHI\nNOME / NAME ANNA\nLUOGO E DATA DI NASCITA TORINO 12.03.1980\n"
    "SESSO F STATURA 165 CITTADINANZA ITA\nSCADENZA 12.03.2031\nCA12345AB\nIDITABIANCHI<<ANNA<<<<<<<<<<<<<<<<<<\n"
)
CARTACEA = "COMUNE DI ROMA\nCARTA D'IDENTITÀ N. AR 1234567\nCognome ROSSI Nome MARIO\nnato il 01/01/1970 a ROMA\nCittadinanza ITALIANA Residenza ROMA via X\nStatura 1,80 Capelli castani Occhi marroni\nIl Sindaco"


def _cataloga(testo: str, nome: str = "documento.pdf", cliente: str = ""):
    return resolve_document_catalog(
        tenant_id="t", fascicolo_id="F", document_id=nome, document_sha256="", filename=nome,
        extracted_text=testo, document_metadata={}, fascicolo_context={**CTX_CIVILE, "cliente": cliente},
    )


def test_la_scansione_della_carta_si_riconosce_dai_campi_e_dal_cliente():
    esito = documento_identita_personale(CIE, cliente="Anna Bianchi")
    assert esito["role"] == "documento_identita" and esito["label"] == "Carta d'identità di Anna Bianchi" and esito["confidence"] == 99
    assert "cognome e nome coincidono con il cliente" in esito["evidence"] and "art. 35 D.P.R. 445/2000" in esito["evidence"]
    altro = documento_identita_personale(CIE, cliente="Mario Rossi")
    assert altro["label"] == "Carta d'identità" and altro["confidence"] == 96 and "non riscontrato" in altro["evidence"]
    assert documento_identita_personale(CARTACEA, cliente="Rossi Mario")["label"] == "Carta d'identità di Rossi Mario"
    assert documento_identita_personale("PASSAPORTO / PASSPORT\nREPUBBLICA ITALIANA\nCognome VERDI Nome LUCA\nNazionalità ITALIANA\nData di scadenza 01/01/2030", cliente="")["label"] == "Passaporto"


def test_un_atto_che_allega_la_carta_non_e_la_carta():
    assert documento_identita_personale("PROCURA ALLE LITI. Io sottoscritto Mario Rossi nato a Roma il 01/01/1970, cognome e nome, allego copia della carta d'identità", cliente="Mario Rossi") is None
    assert documento_identita_personale("La sentenza cita una carta d'identità.", cliente="") is None
    assert documento_identita_personale("Cognome Nome nato il", cliente="") is None  # nessun tipo di documento


def test_il_catalogo_propone_il_documento_d_identita_del_cliente():
    esito = _cataloga(CIE, "Carta d'identità.PDF", cliente="Anna Bianchi")
    assert esito.document_nature == "documento_identita"
    assert esito.document_label == "Carta d'identità di Anna Bianchi"
    assert esito.status == "proposed" and esito.confidence == 99
    assert esito.document_section == "allegati"


def test_il_nome_inequivoco_basta_finche_il_contenuto_non_e_leggibile():
    senza_testo = _cataloga("", "Carta d'identità.PDF", cliente="Anna Bianchi")
    assert senza_testo.document_nature == "documento_identita" and senza_testo.status == "proposed"
    assert senza_testo.document_label == "Carta d'identità di Anna Bianchi" and senza_testo.confidence == 78
    assert any("nome del file inequivoco" in voce.reason for voce in senza_testo.candidates), [voce.reason for voce in senza_testo.candidates]
    # Un nome generico senza testo resta da verificare: il nome non cataloga.
    generico = _cataloga("", "allegato 3.pdf")
    assert generico.status == "review_required" and generico.document_nature != "documento_identita"
    # Un nome che contiene «carta d'identità» dentro un atto non è la carta.
    assert _cataloga("", "ricorso con carta d'identità allegata.pdf").document_nature != "documento_identita"
    for nome, atteso in (("carta identita fronte retro.pdf", "Carta d'identità"), ("CIE.pdf", "Carta d'identità"), ("Passaporto Rossi.pdf", "Passaporto"), ("patente.jpg", "Patente di guida"), ("Documento di identità (2).pdf", "Carta d'identità"), ("memoria.pdf", "")):
        assert documento_identita_dal_nome(nome) == atteso, nome


def test_il_contesto_del_catalogo_porta_il_cliente():
    fascicolo = SimpleNamespace(profilo_deposito={}, tipo="CIVILE", nome_cliente="Anna Bianchi", tribunale="Tribunale di Torino", oggetto="")
    assert fascicolo_catalog_context(fascicolo)["cliente"] == "Anna Bianchi"
