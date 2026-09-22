"""Identity checks never infer equality from a filename alone."""
import hashlib
from types import SimpleNamespace
import pytest
from web.services.portal_document_identity import (
    collega_identita_pst,
    pdf_equivalenti_privi_di_firma,
    trova_documento_importato_identico,
)
from web.services.document_edit_policy import pdf_studio_modificabile

@pytest.mark.parametrize("same,linked,expected", [(True,False,True),(False,False,False),(True,True,False)])
def test_import_reuses_only_verified_unlinked_bytes(tmp_path,same,linked,expected):
    raw=b"original PDF bytes"
    path=tmp_path/"a.pdf";path.write_bytes(raw)
    doc=SimpleNamespace(id="d",nome="a.pdf",fonte_documento="IMPORT_ESTERNO",id_documento_portale="quickorganizer:testi:1",id_cat_portale="other" if linked else "",hash_sha256=hashlib.sha256(raw).hexdigest())
    gf=SimpleNamespace(percorso_documento=lambda *_:path)
    result=trova_documento_importato_identico(gf,SimpleNamespace(id="f",documenti=[doc]),raw if same else b"different",{"id_cat":"123","nome":"a.pdf"},lambda b:b)
    assert (result is doc)==expected

def test_portal_namespaces_are_not_interchanged():
    doc=SimpleNamespace(id="d",id_documento_portale="quickorganizer:testi:1")
    gf=SimpleNamespace(aggiorna_documento_metadati=lambda *_:None)
    collega_identita_pst(gf,SimpleNamespace(id="f"),doc,{"id_documento":"doc1","id_cat":"cat2"})
    assert doc.id_documento_portale=="quickorganizer:testi:1"
    assert doc.id_cat_portale=="cat2"

# Il test diceva che nessun PDF fosse modificabile: era il comportamento di
# prima che l'editor a overlay venisse abilitato per i documenti dello studio.
# La regola di oggi distingue la provenienza, e la stringa vuota sta dalla parte
# chiusa: un documento senza provenienza registrata non risulta dello studio.
@pytest.mark.parametrize("source,portal,expected",[
    ("CARICAMENTO_STUDIO","",True),
    ("CARICAMENTO_STUDIO","123",True),
    ("PORTALE_TELEMATICO","",False),
    ("IMPORT_ESTERNO","",False),
    ("","",False),
])
def test_pdf_editing_follows_document_origin(source,portal,expected):
    doc=SimpleNamespace(nome="bozza.pdf",fonte_documento=source,id_documento_portale=portal,firmato_digitalmente=False,signature_metadata={})
    assert pdf_studio_modificabile(doc) is expected


def _pdf_con_testo(testo: str, *, secondo: str = "") -> bytes:
    import pymupdf

    documento = pymupdf.open()
    pagina = documento.new_page()
    pagina.insert_text(pymupdf.Point(60, 100), testo, fontsize=12, fontname="helv")
    if secondo:
        altra = documento.new_page()
        altra.insert_text(pymupdf.Point(60, 100), secondo, fontsize=12, fontname="helv")
    dati = documento.tobytes()
    documento.close()
    return dati


def test_due_pdf_identici_risultano_equivalenti():
    dati = _pdf_con_testo("TRIBUNALE DI PALMI")

    assert pdf_equivalenti_privi_di_firma(dati, dati) is True


def test_due_pdf_con_testo_diverso_non_sono_equivalenti():
    uno = _pdf_con_testo("TRIBUNALE DI PALMI")
    altro = _pdf_con_testo("TRIBUNALE DI REGGIO CALABRIA")

    assert pdf_equivalenti_privi_di_firma(uno, altro) is False


def test_un_numero_di_pagine_diverso_non_e_equivalenza():
    uno = _pdf_con_testo("Atto")
    altro = _pdf_con_testo("Atto", secondo="Allegato")

    assert pdf_equivalenti_privi_di_firma(uno, altro) is False


def test_il_confronto_non_dipende_piu_da_pymupdf():
    import ast
    from pathlib import Path as _P

    sorgente = (_P(__file__).resolve().parents[1] / "web" / "services" / "portal_document_identity.py").read_text(
        encoding="utf-8-sig"
    )
    importati: set[str] = set()
    for nodo in ast.walk(ast.parse(sorgente)):
        if isinstance(nodo, ast.Import):
            importati.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importati.add(nodo.module.split(".")[0])
    assert not (importati & {"fitz", "pymupdf"})
