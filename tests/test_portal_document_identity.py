"""Identity checks never infer equality from a filename alone."""
import hashlib
from types import SimpleNamespace
import pytest
from web.services.portal_document_identity import trova_documento_importato_identico, collega_identita_pst
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

@pytest.mark.parametrize("source,portal,allowed",[("CARICAMENTO_STUDIO","",True),("PORTALE_TELEMATICO","",False),("IMPORT_ESTERNO","",False),("CARICAMENTO_STUDIO","123",False),("","",False)])
def test_pdf_editing_requires_explicit_studio_origin(source,portal,allowed):
    doc=SimpleNamespace(nome="bozza.pdf",fonte_documento=source,id_documento_portale=portal,firmato_digitalmente=False,signature_metadata={})
    assert pdf_studio_modificabile(doc)==allowed
