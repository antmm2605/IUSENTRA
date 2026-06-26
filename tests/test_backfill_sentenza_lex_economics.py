import json
import os
from pathlib import Path

from pct.fascicoli import Fascicolo, StatoFascicolo, TipoFascicolo
from pct.fascicolo_sentenza_economica import AUTOMATION_KEY, ORIGIN, SENTENZA_VECTOR_SCHEMA_VERSION
from pct.fatturazione import GestioneFatturazione, VoceParcella
from scripts.backfill_sentenza_lex_economics import (
    TenantBackfillTarget,
    _looks_like_contributo_evidence,
    _metadata_for_text,
    _vector_relevant_excerpt,
    _vector_result_current,
    run_backfill,
)


SENTENZA_TEXT = """
Tribunale di Palmi
Sentenza n. 230/2024 pubbl. il 07/05/2024
RG n. 1548/2023
nel procedimento promosso da Spagnolo Sara contro Ministero dell'Istruzione e del Merito
condanna il Ministero alla rifusione delle spese di lite sostenute dai ricorrenti
liquidando la complessiva somma di € 1.100,00, oltre ad € 98,00 per spese
(sommatoria di tutti i c.u. versati dai ricorrenti), con maggiorazione di spese
generali ed accessori di legge (iva e cpa).
"""


SENTENZA_TEXT_2 = """
Tribunale di Palmi
Sentenza n. 231/2024 pubbl. il 08/05/2024
RG n. 2000/2023
nel procedimento promosso da Betti Alice contro Ministero dell'Istruzione e del Merito
condanna il Ministero alla rifusione delle spese di lite
liquidando la complessiva somma di € 900,00, oltre ad € 49,00 per spese di c.u.
e con maggiorazione di spese generali ed accessori di legge.
"""

MONTAGNESE_TEXT = """
N. R.G 697/2025
REPUBBLICA ITALIANA
IN NOME DEL POPOLO ITALIANO
TRIBUNALE ORDINARIO di VICENZA
SENTENZA
nella causa di lavoro di I Grado iscritta al n. r.g. 697/2025 promossa da:
ROBERTA MONTAGNESE, con il patrocinio dell'avv. MONTAGNESE GIUSEPPE
P.Q.M.
Il Giudice del Lavoro, definitivamente pronunciando:
- condanna il Ministero a costituire in favore di parte ricorrente la Carta elettronica
con accredito/assegnazione della somma pari a complessivi euro 500,00;
- condanna parte resistente alla rifusione delle spese di lite sostenute dalla parte ricorrente
a tale titolo liquidando la complessiva somma di € 321,50, di cui € 21,50 per esborsi,
oltre a spese generali ed accessori di legge (iva e cpa), con distrazione in favore
del difensore antistatario.
Sentenza resa ex art. 127 ter c.p.c.
Vicenza, 23 settembre 2025
Sentenza n. 465/2025 pubbl. il 23/09/2025
RG n. 697/2025
"""


def test_backfill_contributo_evidence_non_scambia_iniziali_cu_per_pagamento():
    assert _looks_like_contributo_evidence(
        "La signora C.U. chiede la carta docente per un importo di euro 500,00.",
        {"filename": "sentenza-carta-docente.pdf"},
    ) is False
    assert _looks_like_contributo_evidence(
        "Ricevuta pagamento PagoPA contributo unificato. Importo versato euro 21,50.",
        {"filename": "CU.pdf"},
    ) is True


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_vector_relevant_excerpt_limita_testo_ma_preserva_importi():
    filler = " motivazione molto lunga" * 2000
    text = (
        "Sentenza n. 230/2024 pubbl. il 07/05/2024 RG n. 1548/2023 "
        + filler
        + " condanna il Ministero liquidando la complessiva somma di € 1.100,00, "
        "oltre ad € 98,00 per spese di c.u. e spese generali con antistatario."
        + filler
    )

    excerpt = _vector_relevant_excerpt(text, max_chars=6000)

    assert len(excerpt) <= 6000
    assert "Sentenza n. 230/2024" in excerpt
    assert "€ 1.100,00" in excerpt
    assert "€ 98,00" in excerpt
    assert "spese generali" in excerpt


def test_vector_result_current_richiede_schema_compatto_e_pending_zero():
    old_result = {"ok": True, "document_id": "rag-old", "embedding": {"pending_remaining": 0}}
    pending_result = {
        "ok": True,
        "schema_version": SENTENZA_VECTOR_SCHEMA_VERSION,
        "document_id": "rag-new",
        "embedding": {"pending_remaining": 1},
    }
    error_result = {
        "ok": True,
        "schema_version": SENTENZA_VECTOR_SCHEMA_VERSION,
        "document_id": "rag-new",
        "embedding": {"status": "error"},
    }
    current_result = {
        "ok": True,
        "schema_version": SENTENZA_VECTOR_SCHEMA_VERSION,
        "document_id": "rag-new",
        "embedding": {"pending_remaining": 0},
    }

    assert _vector_result_current(old_result) is False
    assert _vector_result_current(pending_result) is False
    assert _vector_result_current(error_result) is False
    assert _vector_result_current(current_result) is True


def test_metadata_senza_classificazione_non_inventa_sentenza(tmp_path: Path):
    path = tmp_path / "fascicoli" / "documenti_ai" / "tenant" / "fascicoli" / "FASC-1" / "documenti_ai" / "DOC-1" / "v1" / "extracted_text.json"
    tenant = TenantBackfillTarget(tenant="tenant", storage_key="tenant", root=tmp_path)

    metadata = _metadata_for_text(
        {"tenant_id": "tenant", "fascicolo_id": "FASC-1", "document_id": "DOC-1", "text": "Memoria difensiva"},
        path,
        tenant,
    )

    assert metadata["tipo_documento"] == ""


def test_backfill_sentenza_incrementale_salta_documenti_invariati(tmp_path: Path):
    data_root = tmp_path / "data"
    tenant_root = data_root / "tenants" / "tenant-test"
    registry = data_root / "tenants.json"
    _write_json(
        registry,
        {"tenant-test": {"slug": "tenant-test", "storage_key": "tenant-test", "nome": "Studio Test"}},
    )
    first_doc = (
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-1"
        / "documenti_ai"
        / "DOC-1"
        / "v1"
        / "extracted_text.json"
    )
    _write_json(
        first_doc,
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-1",
            "document_id": "DOC-1",
            "text": "Memoria istruttoria senza intestazione di sentenza.",
        },
    )

    first = run_backfill(
        data_root=data_root,
        registry=registry,
        repo_root=Path(__file__).resolve().parents[1],
        tenants={"tenant-test"},
        apply=False,
        skip_lex=True,
    )
    cursor = int(first["incremental"]["newest_mtime_ns"])
    second = run_backfill(
        data_root=data_root,
        registry=registry,
        repo_root=Path(__file__).resolve().parents[1],
        tenants={"tenant-test"},
        apply=False,
        skip_lex=True,
        modified_after_ns=cursor,
    )

    assert second["scan_mode"] == "incremental"
    assert second["totals"]["documents_catalogued"] == 1
    assert second["totals"]["documents_seen"] == 0
    assert second["totals"]["skipped_by_cursor"] == 1

    second_doc = (
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-1"
        / "documenti_ai"
        / "DOC-2"
        / "v1"
        / "extracted_text.json"
    )
    _write_json(
        second_doc,
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-1",
            "document_id": "DOC-2",
            "text": "Nuovo documento arrivato dopo il cursore.",
        },
    )
    os.utime(second_doc, ns=(cursor + 1_000_000, cursor + 1_000_000))

    third = run_backfill(
        data_root=data_root,
        registry=registry,
        repo_root=Path(__file__).resolve().parents[1],
        tenants={"tenant-test"},
        apply=False,
        skip_lex=True,
        modified_after_ns=cursor,
    )

    assert third["totals"]["documents_catalogued"] == 2
    assert third["totals"]["documents_seen"] == 1
    assert third["totals"]["skipped_by_cursor"] == 1


def test_backfill_sentenza_dry_run_e_apply_su_tutti_i_documenti_tenant(tmp_path: Path):
    data_root = tmp_path / "data"
    tenant_root = data_root / "tenants" / "tenant-test"
    registry = data_root / "tenants.json"
    _write_json(
        registry,
        {
            "tenant-test": {
                "slug": "tenant-test",
                "storage_key": "tenant-test",
                "nome": "Studio Test",
            }
        },
    )
    fascicolo = Fascicolo(
        id="FASC-1",
        numero="2026/001",
        titolo="Spagnolo Sara c. MIM",
        tipo=TipoFascicolo.CIVILE,
        stato=StatoFascicolo.IN_CORSO,
        id_cliente="CLI-1",
        nome_cliente="Spagnolo Sara",
        numero_rg="1548",
        anno_rg=2023,
        data_prossima_udienza="n.d.",
    )
    fascicolo_2 = Fascicolo(
        id="FASC-2",
        numero="2026/002",
        titolo="Betti Alice c. MIM",
        tipo=TipoFascicolo.CIVILE,
        stato=StatoFascicolo.IN_CORSO,
        id_cliente="CLI-2",
        nome_cliente="Betti Alice",
        numero_rg="2000",
        anno_rg=2023,
        data_prossima_udienza="n.d.",
    )
    _write_json(
        tenant_root / "fascicoli" / "fascicoli.json",
        {fascicolo.id: fascicolo.to_dict(), fascicolo_2.id: fascicolo_2.to_dict()},
    )
    _write_json(
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-1"
        / "documenti_ai"
        / "DOC-1"
        / "v1"
        / "extracted_text.json",
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-1",
            "document_id": "DOC-1",
            "text": SENTENZA_TEXT,
        },
    )
    _write_json(
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-1"
        / "documenti_ai"
        / "DOC-CU-1"
        / "v1"
        / "extracted_text.json",
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-1",
            "document_id": "DOC-CU-1",
            "filename": "CU.pdf",
            "text": "Ricevuta pagamento PagoPA contributo unificato. Importo versato euro 98,00.",
        },
    )
    _write_json(
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-1"
        / "documenti_ai"
        / "DOC-1-DUP"
        / "v1"
        / "extracted_text.json",
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-1",
            "document_id": "DOC-1-DUP",
            "text": SENTENZA_TEXT,
        },
    )
    _write_json(
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-2"
        / "documenti_ai"
        / "DOC-2"
        / "v1"
        / "extracted_text.json",
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-2",
            "document_id": "DOC-2",
            "text": SENTENZA_TEXT_2,
        },
    )
    _write_json(
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-1"
        / "documenti_ai"
        / "DOC-VICENZA-STRATEGIA"
        / "v1"
        / "extracted_text.json",
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-1",
            "document_id": "DOC-VICENZA-STRATEGIA",
            "filename": "Sentenza Tribunale Vicenza.pdf",
            "text": """
            Tribunale di Vicenza
            Sentenza n. 99/2024 pubbl. il 10/04/2024
            RG n. 1548/2023
            Pronuncia prodotta solo come precedente utile alla strategia difensiva.
            Liquidando la complessiva somma di € 2.500,00 oltre accessori.
            """,
        },
    )

    dry_run = run_backfill(
        data_root=data_root,
        registry=registry,
        repo_root=Path(__file__).resolve().parents[1],
        tenants={"tenant-test"},
        apply=False,
        skip_lex=True,
    )
    applied = run_backfill(
        data_root=data_root,
        registry=registry,
        repo_root=Path(__file__).resolve().parents[1],
        tenants={"tenant-test"},
        apply=True,
        skip_lex=True,
    )

    assert dry_run["totals"]["raw_sentenze_found"] == 4
    assert dry_run["totals"]["sentenze_found"] == 3
    assert dry_run["totals"]["context_mismatch_skipped"] == 1
    assert dry_run["totals"]["unique_fascicoli_found"] == 2
    assert dry_run["totals"]["unique_sentenze"] == 2
    assert dry_run["totals"]["duplicates_skipped"] == 1
    assert dry_run["totals"]["applied"] == 0
    assert applied["totals"]["matrix_confirmed"] == 2
    assert applied["totals"]["context_mismatch_skipped"] == 1
    assert applied["totals"]["duplicates_skipped"] == 1
    assert applied["totals"]["unique_fascicoli_applied"] == 2
    fascicoli = json.loads((tenant_root / "fascicoli" / "fascicoli.json").read_text(encoding="utf-8"))
    aggiornato = fascicoli["FASC-1"]
    aggiornato_2 = fascicoli["FASC-2"]
    assert aggiornato["stato"] == StatoFascicolo.DEFINITO.value
    assert aggiornato["data_prossima_udienza"] == "2024-05-07"
    assert aggiornato["pagamenti"]["contributo_unificato"]["status"] == "pagato"
    assert aggiornato["pagamenti"]["contributo_unificato"]["importo"] == 98.0
    assert aggiornato["pagamenti"]["liquidazione_giudice"]["importo"] == 1100.0
    assert aggiornato["pagamenti"]["parcella"]["status"] == "da_emettere"
    assert aggiornato_2["stato"] == StatoFascicolo.DEFINITO.value
    assert aggiornato_2["data_prossima_udienza"] == "2024-05-08"
    assert aggiornato_2["pagamenti"]["liquidazione_giudice"]["importo"] == 900.0
    assert "contributo_unificato" not in aggiornato_2["pagamenti"]
    parcelle = json.loads((tenant_root / "fatturazione" / "parcelle.json").read_text(encoding="utf-8"))
    assert len(parcelle) == 2


def test_backfill_reset_elimina_importi_lex_errati_e_rigenera_compensi(tmp_path: Path):
    data_root = tmp_path / "data"
    tenant_root = data_root / "tenants" / "tenant-test"
    registry = data_root / "tenants.json"
    _write_json(
        registry,
        {"tenant-test": {"slug": "tenant-test", "storage_key": "tenant-test", "nome": "Studio Test"}},
    )
    fatturazione = GestioneFatturazione(str(tenant_root / "fatturazione" / "parcelle.json"))
    old_proforma = fatturazione.crea(
        id_cliente="CLI-RESET",
        id_fascicolo="FASC-RESET",
        data_emissione="2026-02-01",
        voci=[VoceParcella(descrizione="Compensi liquidati in sentenza", prezzo_unitario=2454.68)],
        origine=ORIGIN,
        dati_personalizzati={"lex_sentenza": {"origin": ORIGIN, "document_key": "document_id:DOC-RESET"}},
    )
    fascicolo = Fascicolo(
        id="FASC-RESET",
        numero="2026/RESET",
        titolo="Rossi Mario c. MIM",
        tipo=TipoFascicolo.CIVILE,
        stato=StatoFascicolo.IN_CORSO,
        id_cliente="CLI-RESET",
        nome_cliente="Rossi Mario",
        numero_rg="466",
        anno_rg=2023,
        data_prossima_udienza="n.d.",
        pagamenti={
            "liquidazione_giudice": {"status": "pagato", "importo": 2454.68, "origine": ORIGIN},
            "contributo_unificato": {"status": "pagato", "importo": 5200.00, "origine": ORIGIN},
            "parcella": {
                "status": "da_emettere",
                "importo": 3239.50,
                "origine": ORIGIN,
                "proforma_id": old_proforma.id,
            },
            AUTOMATION_KEY: {
                "processed_documents": ["document_id:DOC-RESET"],
                "proforme": {"document_id:DOC-RESET": old_proforma.id},
            },
        },
    )
    _write_json(tenant_root / "fascicoli" / "fascicoli.json", {fascicolo.id: fascicolo.to_dict()})
    _write_json(
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-RESET"
        / "documenti_ai"
        / "DOC-RESET"
        / "v1"
        / "extracted_text.json",
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-RESET",
            "document_id": "DOC-RESET",
            "filename": "Sentenza.pdf",
            "text": """
            Tribunale di Palmi
            Sentenza n. 10/2026 pubbl. il 01/02/2026
            RG n. 466/2023
            procedimento promosso da Rossi Mario contro Ministero dell'Istruzione.
            P.Q.M. condanna al pagamento delle spese processuali che liquida in complessivi
            Euro 2.454,68, di cui Euro 125,00 per spese ed Euro 1.500,00 per compensi
            professionali ed Euro 829,68 per spese generali e accessori.
            """,
        },
    )

    report = run_backfill(
        data_root=data_root,
        registry=registry,
        repo_root=Path(__file__).resolve().parents[1],
        tenants={"tenant-test"},
        apply=True,
        reset_lex_amounts=True,
        skip_lex=True,
    )

    assert report["totals"]["reset_fascicoli_touched"] == 1
    assert report["totals"]["reset_payment_entries_removed"] == 3
    assert report["totals"]["reset_automation_states_removed"] == 1
    assert report["totals"]["reset_proforme_removed"] == 1
    fascicoli = json.loads((tenant_root / "fascicoli" / "fascicoli.json").read_text(encoding="utf-8"))
    aggiornato = fascicoli["FASC-RESET"]
    assert aggiornato["pagamenti"]["liquidazione_giudice"]["importo"] == 1500.0
    assert "contributo_unificato" not in aggiornato["pagamenti"]
    assert aggiornato["pagamenti"]["spese_esborsi"]["importo"] == 125.0
    assert aggiornato["pagamenti"]["spese_esborsi"]["natura"] == "spese_esborsi"
    assert aggiornato["pagamenti"]["parcella"]["proforma_id"] != old_proforma.id
    parcelle = json.loads((tenant_root / "fatturazione" / "parcelle.json").read_text(encoding="utf-8"))
    assert old_proforma.id not in parcelle
    assert len(parcelle) == 1
    voci = next(iter(parcelle.values()))["voci"]
    assert any(voce["tipo"] == "ONORARIO" and voce["prezzo_unitario"] == 1500.0 for voce in voci)
    assert not any(voce["prezzo_unitario"] == 2454.68 for voce in voci)


def test_backfill_sentenza_carta_docente_compila_esborsi_e_parcella(tmp_path: Path):
    data_root = tmp_path / "data"
    tenant_root = data_root / "tenants" / "tenant-test"
    registry = data_root / "tenants.json"
    _write_json(
        registry,
        {"tenant-test": {"slug": "tenant-test", "storage_key": "tenant-test", "nome": "Studio Test"}},
    )
    fascicolo = Fascicolo(
        id="FASC-MONT",
        numero="2025/697",
        titolo="Montagnese Roberta c. MIM",
        tipo=TipoFascicolo.CIVILE,
        stato=StatoFascicolo.IN_CORSO,
        id_cliente="CLI-MONT",
        nome_cliente="Montagnese Roberta",
        numero_rg="697",
        anno_rg=2025,
        data_prossima_udienza="n.d.",
    )
    _write_json(tenant_root / "fascicoli" / "fascicoli.json", {fascicolo.id: fascicolo.to_dict()})
    _write_json(
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-MONT"
        / "documenti_ai"
        / "DOC-MONT"
        / "v1"
        / "extracted_text.json",
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-MONT",
            "document_id": "DOC-MONT",
            "filename": "Sentenza.pdf",
            "text": MONTAGNESE_TEXT,
        },
    )
    _write_json(
        tenant_root
        / "fascicoli"
        / "documenti_ai"
        / "tenant-test"
        / "fascicoli"
        / "FASC-MONT"
        / "documenti_ai"
        / "DOC-CU"
        / "v1"
        / "extracted_text.json",
        {
            "tenant_id": "tenant-test",
            "fascicolo_id": "FASC-MONT",
            "document_id": "DOC-CU",
            "filename": "CU.pdf",
            "text": "Ricevuta PagoPA contributo unificato. Importo versato euro 21,50.",
        },
    )

    applied = run_backfill(
        data_root=data_root,
        registry=registry,
        repo_root=Path(__file__).resolve().parents[1],
        tenants={"tenant-test"},
        apply=True,
        skip_lex=True,
    )

    assert applied["totals"]["raw_sentenze_found"] == 1
    assert applied["totals"]["sentenze_found"] == 1
    assert applied["totals"]["matrix_confirmed"] == 1
    fascicoli = json.loads((tenant_root / "fascicoli" / "fascicoli.json").read_text(encoding="utf-8"))
    aggiornato = fascicoli["FASC-MONT"]
    assert aggiornato["data_prossima_udienza"] == "2025-09-23"
    assert aggiornato["pagamenti"]["liquidazione_giudice"]["importo"] == 321.5
    assert aggiornato["pagamenti"]["contributo_unificato"]["status"] == "pagato"
    assert aggiornato["pagamenti"]["contributo_unificato"]["importo"] == 21.5
    assert aggiornato["pagamenti"]["contributo_unificato"]["natura"] == "pdf_contributo_unificato"
    assert aggiornato["pagamenti"]["contributo_unificato"]["label"] == "Contributo unificato da PDF"
    assert "spese_esborsi" not in aggiornato["pagamenti"]
    last_extraction = aggiornato["pagamenti"]["_sentenza_tribunale_lex_ai"]["last_extraction"]
    assert last_extraction["beneficio_cliente_importo"] == 500.0
    assert "spese_esborsi_riclassificate_cu_pdf" in last_extraction["warnings"]
    assert aggiornato["pagamenti"]["parcella"]["status"] == "da_emettere"
    assert aggiornato["pagamenti"]["parcella"]["importo"] > 321.5
    parcelle = json.loads((tenant_root / "fatturazione" / "parcelle.json").read_text(encoding="utf-8"))
    assert len(parcelle) == 1
    voci = next(iter(parcelle.values()))["voci"]
    assert any(
        voce["tipo"] == "ANTICIPO"
        and voce["prezzo_unitario"] == 21.5
        and "Contributo unificato" in voce["descrizione"]
        for voce in voci
    )
    assert not any("Spese ed esborsi" in voce["descrizione"] and voce["prezzo_unitario"] == 21.5 for voce in voci)
