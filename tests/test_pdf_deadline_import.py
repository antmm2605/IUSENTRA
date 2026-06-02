from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.scadenziario import GestioneScadenziario
from web.services.react_agenda_bridge import build_react_agenda_payload
from web.services import pdf_deadline_import as pdf_deadline_import_module
from web.services.pdf_deadline_import import import_pdf_deadlines, preview_pdf_deadlines


def _pdf_with_deadline_and_link() -> bytes:
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "Udienza di trattazione fissata al 20/06/2026.")
    pdf.drawString(72, 700, "Termine per deposito memoria: 10/06/2026.")
    pdf.linkURL("https://pst.giustizia.it/PST/", (72, 684, 260, 704), relative=0)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def test_import_scadenze_pdf_crea_scadenziario_e_deduplica(tmp_path: Path) -> None:
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
    )
    scadenziario = GestioneScadenziario(db_path=str(tmp_path / "scadenziario" / "scadenze.json"))
    fascicolo = fascicoli.nuovo(
        "Procedimento prova PDF",
        TipoFascicolo.CIVILE,
        nome_cliente="Rossi Mario",
        numero_rg="12345",
        anno_rg=2026,
        oggetto="Test scadenze PDF",
    )
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "ordinanza-con-link.pdf",
        TipoDocumento.ORDINANZA,
        _pdf_with_deadline_and_link(),
    )

    preview = preview_pdf_deadlines(
        gestione_fascicoli=fascicoli,
        gestione_scadenziario=scadenziario,
    )

    assert preview.scanned_documents == 1
    assert {candidate.due_date for candidate in preview.candidates} == {"2026-06-10", "2026-06-20"}
    assert any(candidate.type == "UDIENZA" for candidate in preview.candidates)
    assert any(candidate.type == "DEPOSITO_MEMORIA" for candidate in preview.candidates)
    assert any("https://pst.giustizia.it/PST/" in candidate.urls for candidate in preview.candidates)

    result = import_pdf_deadlines(
        gestione_fascicoli=fascicoli,
        gestione_scadenziario=scadenziario,
        selected_ids=[candidate.id for candidate in preview.candidates],
        user_id="admin",
    )

    assert result["ok"] is True
    assert result["created"] == 2
    imported = scadenziario.tutte(solo_aperte=False)
    assert len(imported) == 2
    assert all("pdf-deadline:" in item.note for item in imported)
    assert any("Link PDF: https://pst.giustizia.it/PST/" in item.note for item in imported)

    class _EmptyAgenda:
        def tutti(self):
            return []

    agenda_payload = build_react_agenda_payload(
        lambda: _EmptyAgenda(),
        lambda: scadenziario,
        from_value="2026-06-01",
        to_value="2026-06-30",
    )
    assert {event["kind"] for event in agenda_payload["events"]} >= {"UDIENZA", "DEPOSITO"}
    assert any("https://pst.giustizia.it/PST/" in event["notes"] for event in agenda_payload["events"])

    second_preview = preview_pdf_deadlines(
        gestione_fascicoli=fascicoli,
        gestione_scadenziario=scadenziario,
    )

    assert second_preview.candidates
    assert all(candidate.duplicate for candidate in second_preview.candidates)


def test_preview_scadenze_pdf_salta_file_fuori_soglia_senza_lettura_pesante(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
    )
    scadenziario = GestioneScadenziario(db_path=str(tmp_path / "scadenziario" / "scadenze.json"))
    fascicolo = fascicoli.nuovo(
        "Procedimento prova PDF grande",
        TipoFascicolo.CIVILE,
        nome_cliente="Verdi Anna",
        numero_rg="12346",
        anno_rg=2026,
        oggetto="Test scadenze PDF grande",
    )
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "ordinanza-grande.pdf",
        TipoDocumento.ORDINANZA,
        b"%PDF-1.4\n" + (b"0" * 512),
    )
    monkeypatch.setattr(pdf_deadline_import_module, "MAX_PREVIEW_PDF_BYTES", 32)

    preview = preview_pdf_deadlines(
        gestione_fascicoli=fascicoli,
        gestione_scadenziario=scadenziario,
        max_documents=1,
    )

    assert preview.scanned_documents == 1
    assert preview.candidates == []
