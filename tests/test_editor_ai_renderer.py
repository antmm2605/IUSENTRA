from __future__ import annotations

from pathlib import Path

from lex.formatting.legal_draft_layout import normalize_legal_draft_layout
from pct.editor_ai.edit_proposals import build_edit_proposals
from pct.editor_ai.editor_renderer import (
    create_editor_document,
    legal_markdown_to_editor_html,
    read_editor_document_for_lex,
    sanitize_editor_html,
)
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


def test_renderer_converte_bozza_lex_in_html_editor():
    markdown = """**BOZZA — DIFFIDA E MESSA IN MORA**

---

17/05/2026

**Spett.le**
Mario Rossi

**Fatto**

Il debitore non ha adempiuto.

1. Pagare il dovuto
2. Consegnare i documenti

**Dati da completare prima dell'invio**

- Codice fiscale cliente
- Indirizzo controparte
"""

    html = legal_markdown_to_editor_html(markdown)

    assert "<h1>BOZZA — DIFFIDA E MESSA IN MORA</h1>" in html
    assert "<hr>" in html
    assert "<h2>Fatto</h2>" in html
    assert "<ol><li>Pagare il dovuto</li><li>Consegnare i documenti</li></ol>" in html
    assert "<ul><li>Codice fiscale cliente</li><li>Indirizzo controparte</li></ul>" in html
    assert "<blockquote" not in html


def test_normalize_legal_draft_layout_impagina_bozza_piatta_senza_regex_costose():
    text = (
        "**BOZZA - DIFFIDA E MESSA IN MORA** --- 17/05/2026 Spett.le Mario Rossi "
        "[Indirizzo controparte] Oggetto: Sollecito pagamento Fatto Il debitore non ha adempiuto. "
        "Diritto Art. 1219 c.c. Richiesta formale Si diffida al pagamento. "
        "1. Pagare il dovuto 2. Consegnare i documenti Avvertenza Verificare dati. "
        "Con osservanza, Avv. Bianchi Fonti consultate: archivio interno"
    )

    normalized = normalize_legal_draft_layout(text)

    assert normalized.startswith("**BOZZA - DIFFIDA E MESSA IN MORA**")
    assert "**Spett.le**" in normalized
    assert "[Indirizzo controparte]" in normalized
    assert "**Oggetto:**" in normalized
    assert "**Fatto**" in normalized
    assert "\n1. Pagare il dovuto" in normalized
    assert "Fonti consultate" not in normalized


def test_build_edit_proposals_sostituzione_conserva_testi_quotati():
    proposals = build_edit_proposals(
        atto_ai_id="atto-ai-1",
        version_id="v1",
        instructions='sostituisci "vecchio importo" con "nuovo importo"',
        current_html="<p>vecchio importo</p>",
        created_by="utente",
    )

    assert len(proposals) == 1
    assert proposals[0].operation_type == "replace"
    assert proposals[0].find_text == "vecchio importo"
    assert proposals[0].replace_text == "nuovo importo"
