from __future__ import annotations

import json
import time
from pathlib import Path

from scripts import audit_studio_telematico_menu_tree as menu_audit
from web.services.react_studio_module_bridge import _build_strumenti_operativi


ROOT = Path(__file__).resolve().parents[1]


def test_catalogo_strumenti_operativi_espone_tutte_le_funzioni_censite():
    payload = _build_strumenti_operativi()
    operation = next(row for row in payload["operations"] if row["id"] == "catalogo-funzioni")
    records = operation["records"]

    assert len(records) == 183
    assert len({row["id"] for row in records}) == 183
    assert len({row["badge"] for row in records}) == 14
    assert all(row["title"] and row["href"].startswith("/") for row in records)
    assert all("Studio Telematico" not in json.dumps(row, ensure_ascii=False) for row in records)
    assert all("QuickOrganizer" not in json.dumps(row, ensure_ascii=False) for row in records)
    assert any(row["id"] == "calcolo_interessi_legali" for row in records)
    assert any(row["id"] == "attestazione_conformita" for row in records)
    assert any(row["id"] == "fattura_elettronica_avvocati" for row in records)


def test_catalogo_react_supporta_ricerca_filtri_e_caricamento_progressivo():
    page = (ROOT / "frontend/src/components/StudioModulePage.tsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/src/components/StudioModulePage.css").read_text(encoding="utf-8")
    module_data = (ROOT / "frontend/src/studioModuleData.ts").read_text(encoding="utf-8")

    assert 'placeholder="Cerca funzione o argomento"' in page
    assert 'aria-label="Filtra per area"' in page
    assert "Mostra tutti ({filteredRecords.length})" in page
    assert "setRecordLimit((current) => current + 24)" in page
    assert "iu-sm-focus__record-tools" in styles
    assert "focus-visible" in styles
    assert "Catalogo funzioni" in module_data
    assert "scheduler e promemoria" not in module_data
    assert "displayWritesLabel" not in page


def test_audit_comandi_distingue_mappatura_e_prova_reale():
    audit = json.loads(
        (ROOT / "artifacts/react-migration/audit-parita-funzionale-comandi.json").read_text(encoding="utf-8")
    )

    assert audit["schema_version"] == 3
    assert audit["counts"]["functional_entries"] == 1428
    assert audit["counts"]["unique_source_actions"] == 1015
    assert audit["counts"]["duplicate_source_paths"] == 413
    assert len(audit["entries"]) == 1428
    assert len({row["id"] for row in audit["entries"]}) == 1428
    assert len({row["canonical_id"] for row in audit["entries"]}) == 1015
    assert audit["counts"]["mapped_entries"] == audit["counts"]["functional_entries"]
    assert audit["counts"]["verified_entries"] > 0
    assert audit["counts"]["unmapped_entries"] == 0
    assert all(row["status"] != "verificata" or row["real_proof"] for row in audit["entries"])
    assert all(row["status"] != "presente_da_provare" or all(check["ok"] for check in row["code_checks"]) for row in audit["entries"])
    verified_capabilities = {row["capability_id"] for row in audit["entries"] if row["status"] == "verificata"}
    assert verified_capabilities == {
        "agenda_gestione_evento",
        "agenda_nuovo_evento",
        "agenda_viste",
        "documenti_archivio",
        "documenti_ricerca_filtri",
        "fascicoli_elenco_attivi",
        "fascicoli_gruppi",
        "fascicoli_ricerca_filtri",
    }


def test_prove_reali_fascicoli_descrivono_copia_locale_e_verifica_responsive():
    proofs = json.loads(
        (ROOT / "artifacts/react-migration/prove-reali-parita-funzionale.json").read_text(encoding="utf-8")
    )
    assert proofs["schema_version"] == 1
    for capability in ("fascicoli_elenco_attivi", "fascicoli_gruppi", "fascicoli_ricerca_filtri"):
        proof = proofs["capabilities"][capability]
        assert proof["status"] == "verificata"
        assert proof["base_url"] == "http://127.0.0.1:8080"
        assert proof["route"] == "/fascicoli"
        assert proof["browser_console_errors"] == 0
        assert {row["width"] for row in proof["viewports"]} == {390, 768, 1146}
        assert proof["evidence"]


def test_prove_reali_agenda_coprono_creazione_viste_e_tutto_schermo():
    proofs = json.loads(
        (ROOT / "artifacts/react-migration/prove-reali-parita-funzionale.json").read_text(encoding="utf-8")
    )
    new_event = proofs["capabilities"]["agenda_nuovo_evento"]
    views = proofs["capabilities"]["agenda_viste"]

    assert new_event["status"] == "verificata"
    assert new_event["route"] == "/agenda/nuovo"
    assert any("salvata" in item for item in new_event["evidence"])
    assert any("rimossa" in item for item in new_event["evidence"])
    assert views["status"] == "verificata"
    assert views["route"] == "/agenda"
    assert {row["width"] for row in views["viewports"]} == {390, 1048, 1920}
    assert any("Tutto schermo" in item for item in views["evidence"])
    event_actions = proofs["capabilities"]["agenda_gestione_evento"]
    assert event_actions["status"] == "verificata"
    assert event_actions["route"] == "/agenda/:id"
    assert any("Rinvia" in item for item in event_actions["evidence"])
    assert any("Elimina" in item for item in event_actions["evidence"])


def test_prove_reali_archivio_documenti_coprono_dati_filtri_e_responsive():
    proofs = json.loads(
        (ROOT / "artifacts/react-migration/prove-reali-parita-funzionale.json").read_text(encoding="utf-8")
    )
    archive = proofs["capabilities"]["documenti_archivio"]
    filters = proofs["capabilities"]["documenti_ricerca_filtri"]

    assert archive["status"] == "verificata"
    assert archive["route"] == "/editor-professionale"
    assert {row["width"] for row in archive["viewports"]} == {390, 820, 1280}
    assert any("76 documenti reali" in item for item in archive["evidence"])
    assert filters["status"] == "verificata"
    assert filters["route"] == "/editor-professionale"
    assert any("PDF.P7M" in item for item in filters["evidence"])


def test_messaggi_pubblici_non_citano_il_prodotto_sorgente():
    datiatto = (ROOT / "pct/datiatto_unep.py").read_text(encoding="utf-8")
    importer = (ROOT / "web/services/quickorganizer_import.py").read_text(encoding="utf-8")

    assert "non prevista da Studio Telematico" not in datiatto
    assert "titolo Studio Telematico" not in importer
    assert "oggetto Studio Telematico" not in importer
    assert "titolo originario" in importer
    assert "oggetto originario" in importer


def test_regex_audit_menu_usano_stringhe_csharp_lineari():
    vulnerable_fragment = r"(?:\\.|[^\"])*"
    regexes = (
        menu_audit.WINFORMS_TEXT_RE,
        menu_audit.ACCESSIBLE_NAME_RE,
        menu_audit.TOOLTIP_RE,
        menu_audit.CAPTION_RE,
        menu_audit.CONTAINER_TEXT_RE,
        menu_audit.FILTER_LABEL_RE,
    )

    for regex in regexes:
        assert vulnerable_fragment not in regex.pattern
        assert r'[^\"\\]' in regex.pattern

    hostile_caption = r"\!" * 5_000
    cases = (
        (menu_audit.WINFORMS_TEXT_RE, f'this.A.Text="{hostile_caption}";'),
        (menu_audit.ACCESSIBLE_NAME_RE, f'this.A.AccessibleName="{hostile_caption}";'),
        (menu_audit.TOOLTIP_RE, f'A.SetToolTip(this.A,"{hostile_caption}");'),
        (menu_audit.CAPTION_RE, f'A.SharedPropsInternal.Caption="{hostile_caption}";'),
        (menu_audit.CONTAINER_TEXT_RE, f'ribbonGroupA.Text="{hostile_caption}";'),
        (menu_audit.FILTER_LABEL_RE, f'FilterLabel="{hostile_caption}"'),
    )

    started = time.perf_counter()
    for regex, payload in cases:
        assert regex.search(payload)
    assert time.perf_counter() - started < 2.0
