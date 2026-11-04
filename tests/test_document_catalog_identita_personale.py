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
    # Dalla 2.397.0 i documenti di riconoscimento hanno la loro sezione del faldone.
    assert esito.document_section == "identita"


def test_il_nome_inequivoco_basta_finche_il_contenuto_non_e_leggibile():
    senza_testo = _cataloga("", "Carta d'identità.PDF", cliente="Anna Bianchi")
    assert senza_testo.document_nature == "documento_identita" and senza_testo.status == "proposed"
    # Senza contenuto letto non si sa di chi sia la carta: non si intesta al cliente.
    assert senza_testo.document_label == "Carta d'identità" and senza_testo.confidence == 78
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


def test_modello_condiviso_non_classifica_un_contenuto_misto_come_una_carta():
    from pct.document_intelligence.catalog_identita_personale import modello_identita_italiana
    assert modello_identita_italiana(CARTACEA) == 'carta_cartacea'
    assert modello_identita_italiana(CIE) == 'cie'
    assert modello_identita_italiana('TESSERA SANITARIA\nCOGNOME ROSSI') == 'tessera_sanitaria'
    assert modello_identita_italiana(CIE + '\nTESSERA SANITARIA') == ''
    assert modello_identita_italiana('Documento allegato senza diciture') == ''


# Revisione del 04/11/2026 sui documenti reali pseudonimizzati (esempi fittizi nello stesso formato OCR).
PATENTE = (
    "PATENTE DI GUIDA REPUBBLICA ITALIANA\n1. VERDI\n2. LUCA\n3. 05/06/1975 REGGIO DI CALABRIA (RC)\n"
    "4a. 10/01/2015 4c. MIT-UCO 4b. 05/06/2026\n5. U1AB12345X\n9. A1 B\n"
)
CARTACEA_OCR_ROVINATO = (
    "Segni particolari. Capelli.NERI.Statura.1,70 Occhi...CASTANI\nCognome..VERDI.. Nome..LUCA..\n"
    "nato il.05.06.1975 (atto n. 123 P. I S. A) a ROMA\nCittadinanza ITALIANA Residenza ROMA\n"
)
LETTERA_CON_ALLEGATO = (
    "Spett.le Ministero\nOggetto: Diffida e messa in mora\nIl sottoscritto Luca Verdi, nato a Roma il 05/06/1975, "
    "residente in Roma,\nINVITA E DIFFIDA al pagamento entro 15 giorni.\nFirma\nSi allega fotocopia della carta di identità"
)


def test_la_patente_intestata_e_documento_equipollente_anche_con_i_campi_numerati():
    # Art. 35, comma 2, D.P.R. 445/2000: la patente di guida è equipollente alla carta d'identità.
    esito = documento_identita_personale(PATENTE)
    assert esito is not None and esito["label"] == "Patente di guida" and esito["role"] == "documento_identita"


def test_la_carta_cartacea_senza_titolo_leggibile_si_riconosce_dalle_diciture_del_modello():
    esito = documento_identita_personale(CARTACEA_OCR_ROVINATO)
    assert esito is not None and esito["label"] == "Carta d'identità"


def test_la_lettera_che_allega_la_carta_d_identita_non_e_il_documento():
    assert documento_identita_personale(LETTERA_CON_ALLEGATO) is None
