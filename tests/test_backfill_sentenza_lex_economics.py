import json
from pathlib import Path

from pct.fascicoli import Fascicolo, StatoFascicolo, TipoFascicolo
from pct.fascicolo_sentenza_economica import SENTENZA_VECTOR_SCHEMA_VERSION
from scripts.backfill_sentenza_lex_economics import _vector_relevant_excerpt, _vector_result_current, run_backfill


SENTENZA_TEXT = """
Tribunale di Palmi
Sentenza n. 230/2024 pubbl. il 07/05/2024
RG n. 1548/2023
condanna il Ministero alla rifusione delle spese di lite sostenute dai ricorrenti
liquidando la complessiva somma di € 1.100,00, oltre ad € 98,00 per spese
(sommatoria di tutti i c.u. versati dai ricorrenti), con maggiorazione di spese
generali ed accessori di legge (iva e cpa).
"""


SENTENZA_TEXT_2 = """
Tribunale di Palmi
Sentenza n. 231/2024 pubbl. il 08/05/2024
RG n. 2000/2023
condanna il Ministero alla rifusione delle spese di lite
liquidando la complessiva somma di € 900,00, oltre ad € 49,00 per spese di c.u.
e con maggiorazione di spese generali ed accessori di legge.
"""


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
    current_result = {
        "ok": True,
        "schema_version": SENTENZA_VECTOR_SCHEMA_VERSION,
        "document_id": "rag-new",
        "embedding": {"pending_remaining": 0},
    }

    assert _vector_result_current(old_result) is False
    assert _vector_result_current(pending_result) is False
    assert _vector_result_current(current_result) is True


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

    assert dry_run["totals"]["sentenze_found"] == 3
    assert dry_run["totals"]["unique_fascicoli_found"] == 2
    assert dry_run["totals"]["unique_sentenze"] == 2
    assert dry_run["totals"]["duplicates_skipped"] == 1
    assert dry_run["totals"]["applied"] == 0
    assert applied["totals"]["matrix_confirmed"] == 2
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
    assert aggiornato_2["pagamenti"]["contributo_unificato"]["importo"] == 49.0
    assert aggiornato_2["pagamenti"]["liquidazione_giudice"]["importo"] == 900.0
    parcelle = json.loads((tenant_root / "fatturazione" / "parcelle.json").read_text(encoding="utf-8"))
    assert len(parcelle) == 2
