from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from web.services.react_document_archive_bridge import build_react_document_archive_payload


def _documento(*, doc_id: str, nome: str, tipo: str, eliminato_il: str = ""):
    return SimpleNamespace(
        id=doc_id,
        nome=nome,
        nome_originale=nome,
        tipo=tipo,
        dimensione_bytes=2048,
        data_caricamento="2026-08-14T10:30:00",
        data_documento="2026-08-13",
        note="Documento di prova controllato",
        tags=["prova"],
        fonte_documento="CARICAMENTO_STUDIO",
        eliminato_il=eliminato_il,
        eliminato_da="Avv. Test" if eliminato_il else "",
    )


def _payload(query=None):
    fascicolo = SimpleNamespace(
        id="FASC-1",
        numero="2026/001",
        numero_rg="1025",
        anno_rg="2026",
        titolo="Ricorso lavoro",
        stato="APERTO",
        documenti=[_documento(doc_id="DOC-1", nome="Ricorso.pdf", tipo="RICORSO")],
        documenti_cestino=[
            _documento(
                doc_id="DOC-2",
                nome="Procura.pdf.p7m",
                tipo="PROCURA",
                eliminato_il="2026-08-14T11:45:00",
            )
        ],
    )
    gestore = SimpleNamespace(tutti=lambda archiviati=True: [fascicolo])
    return build_react_document_archive_payload(
        get_fascicoli=lambda: gestore,
        query=query or {},
    )


def test_archivio_documenti_aggrega_attivi_e_cestino_tenant_aware():
    payload = _payload()

    assert payload["source"] == "fascicoli_tenant"
    assert payload["summary"] == {"active": 1, "trash": 1, "matters": 1, "formats": 1}
    assert payload["items"][0]["name"] == "Ricorso.pdf"
    assert payload["items"][0]["documentDate"] == "13/08/2026"
    assert payload["items"][0]["actions"]["delete"].endswith("/elimina")

    cestino = _payload({"scope": "cestino"})
    assert cestino["items"][0]["name"] == "Procura.pdf.p7m"
    assert cestino["items"][0]["format"] == "PDF.P7M"
    assert cestino["items"][0]["deletedAt"].startswith("14/08/2026")
    assert cestino["items"][0]["actions"]["restore"].endswith("/ripristina")
    assert cestino["items"][0]["actions"]["permanentDelete"].endswith("/elimina-definitivamente")
    assert cestino["items"][0]["actions"]["download"] == ""


def test_archivio_documenti_filtra_senza_modificare_i_dati():
    payload = _payload({"q": "ricorso", "tipo": "RICORSO", "formato": "PDF", "fascicolo": "FASC-1"})

    assert payload["pagination"]["total"] == 1
    assert payload["items"][0]["id"] == "DOC-1"
    assert _payload({"q": "inesistente"})["items"] == []


def test_archivio_documenti_react_espone_comandi_e_layout_operativi():
    source = Path("frontend/src/components/EditorProfessionalePage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/EditorProfessionalePage.css").read_text(encoding="utf-8")

    assert "Archivio documenti" in source
    assert "Sposta nel cestino" in source
    assert "Ripristina documento" in source
    assert "Esporta originali" in source
    assert "window.location.assign" not in source
    assert ".iu-editor-pro-table" in css
    assert ".iu-editor-pro-filters" in css
    assert "@media(max-width:640px)" in css
