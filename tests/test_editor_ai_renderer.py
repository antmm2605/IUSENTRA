from __future__ import annotations

from pathlib import Path

from pct.editor_ai.editor_renderer import create_editor_document, read_editor_document_for_lex, sanitize_editor_html
from pct.fascicoli import GestioneFascicoli, TipoFascicolo


def test_sanitizer_rimuove_script_eventi_e_javascript_href():
    html = '<h1 onclick="alert(1)">Titolo</h1><script>bad()</script><a href="javascript:alert(1)">link</a>'

    cleaned = sanitize_editor_html(html)

    assert "<script" not in cleaned.lower()
    assert "onclick" not in cleaned.lower()
    assert "javascript:" not in cleaned.lower()
    assert 'href="#"' not in cleaned


def test_renderer_crea_documento_editor_reale_e_lo_rilegge(tmp_path: Path):
    fascicoli = GestioneFascicoli(
        str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fascicolo = fascicoli.nuovo("Ricorso", TipoFascicolo.CIVILE, nome_cliente="Cliente")

    created = create_editor_document(
        fascicoli_repository=fascicoli,
        fascicolo_id=fascicolo.id,
        title="Ricorso cautelare",
        html_content="<h1>Ricorso cautelare</h1><p>Testo editor reale.</p>",
        created_by="operatore",
    )
    readback = read_editor_document_for_lex(
        fascicoli_repository=fascicoli,
        fascicolo_id=fascicolo.id,
        editor_document_id=created["document_id"],
    )

    assert created["open_url"].endswith(f"/documenti/{created['document_id']}/editor")
    assert fascicoli.percorso_documento(fascicolo.id, created["document_id"]).exists()
    assert "Testo editor reale" in readback["text"]
