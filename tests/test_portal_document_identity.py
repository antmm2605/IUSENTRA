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
