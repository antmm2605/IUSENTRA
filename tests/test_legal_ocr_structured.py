"""Test engine-independent per ALTO-XML, tabelle e NER legale del legal_ocr."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from legal_ocr.alto import build_alto_xml
from legal_ocr.engines import EasyOcrEngine, PaddleOcrEngine, build_engine
from legal_ocr.models import PageArtifact
from legal_ocr.ner_legal import extract_legal_entities
from legal_ocr.tables import reconstruct_tables, table_to_csv, table_to_html


def _tok(token, left, top, width=40, height=12, conf=0.95, page=1, line="p1-l1"):
    return {"token": token, "start": 0, "end": len(token), "confidence": conf, "bbox": [left, top, width, height], "line_id": line, "page": page}


# ---------------------------------------------------------------- ALTO-XML

def test_alto_xml_e_ben_formato_e_riporta_contenuto_coord_e_confidenza():
    tokens = [
        _tok("TRIBUNALE", 50, 40, line="p1-l1"),
        _tok("DI", 160, 40, line="p1-l1"),
        _tok("MILANO", 190, 40, line="p1-l1"),
        _tok("Sentenza", 50, 80, line="p1-l2", conf=0.61),
    ]
    pages = [PageArtifact(page=1, image_path="p1.png", sha256="x", width=1240, height=1750)]
    xml = build_alto_xml(tokens, pages, source_file="atto.pdf")

    root = ET.fromstring(xml)  # ben formato
    ns = {"a": "http://www.loc.gov/standards/alto/ns-v4#"}
    page_els = root.findall(".//a:Page", ns)
    assert len(page_els) == 1
    assert page_els[0].get("WIDTH") == "1240"
    strings = root.findall(".//a:String", ns)
    contents = [s.get("CONTENT") for s in strings]
    assert contents == ["TRIBUNALE", "DI", "MILANO", "Sentenza"]
    # coordinate e confidenza presenti
    assert strings[0].get("HPOS") == "50" and strings[0].get("VPOS") == "40"
    assert strings[3].get("WC") == "0.61"
    lines = root.findall(".//a:TextLine", ns)
    assert len(lines) == 2


def test_alto_xml_gestisce_token_vuoti():
    xml = build_alto_xml([], [], source_file="vuoto.pdf")
    root = ET.fromstring(xml)
    assert root.tag.endswith("}alto")


# ---------------------------------------------------------------- Tabelle

def test_ricostruzione_tabella_da_griglia_token_produce_righe_e_colonne():
    # Griglia 3x3: tre righe (y 100/140/180), tre colonne (x 60/260/460).
    rows_y = [100, 140, 180]
    cols_x = [60, 260, 460]
    grid = [
        ["Voce", "Importo", "Data"],
        ["Contributo unificato", "518", "01/03/2026"],
        ["Marca", "27", "01/03/2026"],
    ]
    tokens = []
    for r, y in enumerate(rows_y):
        for c, x in enumerate(cols_x):
            for w, word in enumerate(grid[r][c].split(" ")):
                tokens.append(_tok(word, x + w * 70, y, width=60, height=14, line=f"p1-r{r}"))
    tables = reconstruct_tables(tokens)
    assert len(tables) == 1
    table = tables[0]
    assert table["n_cols"] == 3
    assert table["rows"][0] == ["Voce", "Importo", "Data"]
    assert table["rows"][1][0] == "Contributo unificato"
    assert table["rows"][1][1] == "518"

    csv_text = table_to_csv(table)
    assert "Voce,Importo,Data" in csv_text.splitlines()[0]
    html = table_to_html(table)
    assert "<table" in html and "<th>Voce</th>" in html and "Contributo unificato" in html


def test_nessuna_tabella_se_struttura_insufficiente():
    assert reconstruct_tables([_tok("solo", 10, 10), _tok("testo", 60, 10)]) == []


# ---------------------------------------------------------------- NER legale

def test_ner_estrae_numero_ruolo_ufficio_parti_date_riferimenti():
    testo = (
        "TRIBUNALE DI MILANO - Sezione Civile\n"
        "R.G. n. 12345/2024\n"
        "Mario Rossi contro Condominio Via Verdi 10\n"
        "Udienza del 15 marzo 2026, deposito entro il 01/03/2026.\n"
        "Visti gli artt. 163 c.p.c. e l'art. 91 c.p.c.; D.Lgs. 28/2010 sulla mediazione."
    )
    ent = extract_legal_entities(testo)

    assert ent["numero_ruolo"][0]["numero"] == "12345"
    assert ent["numero_ruolo"][0]["anno"] == "2024"
    assert any("Tribunale di Milano" == u or u.startswith("Tribunale di Milano") for u in ent["uffici"])
    assert ent["parti"][0]["attore"].startswith("Mario Rossi")
    assert "Condominio" in ent["parti"][0]["convenuto"]
    assert "15 marzo 2026" in ent["date"]
    assert "01/03/2026" in ent["date"]
    rif = " | ".join(ent["riferimenti"])
    assert "163" in rif and "c.p.c." in rif
    assert any("28/2010" in r for r in ent["riferimenti"])
    assert ent["counts"]["numero_ruolo"] == 1


def test_ner_non_inventa_su_testo_non_legale():
    ent = extract_legal_entities("Promemoria della spesa al supermercato di sabato.")
    assert ent["numero_ruolo"] == []
    assert ent["parti"] == []
    # niente R.G., nessun riferimento normativo
    assert ent["counts"]["riferimenti"] == 0


def test_ner_anno_a_due_cifre_normalizzato():
    ent = extract_legal_entities("Iscritto a R.G. 88/24 presso il Tribunale di Roma.")
    assert ent["numero_ruolo"][0]["anno"] == "2024"


# ---------------------------------------------------------------- Adapter motori esterni

def test_build_engine_riconosce_easyocr_e_paddleocr():
    assert isinstance(build_engine("easyocr"), EasyOcrEngine)
    assert isinstance(build_engine("paddleocr"), PaddleOcrEngine)
    assert isinstance(build_engine("pp-ocr"), PaddleOcrEngine)


def test_pipeline_e2e_produce_alto_tabelle_ed_entita_legali(tmp_path):
    """E2E con motore disponibile in sandbox (native-text-fallback): l'evidenza
    contiene ALTO-XML scritto su disco, la lista tabelle e le entità legali."""
    from legal_ocr import LegalOcrConfig, LegalOcrEvidenceStore, LegalOcrPipeline

    source = tmp_path / "atto.txt"
    source.write_text(
        "Tribunale di Milano\n"
        "R.G. n. 12345/2024\n"
        "Mario Rossi contro Beta S.r.l.\n"
        "Visti gli artt. 163 c.p.c.; D.Lgs. 28/2010. Udienza del 10/10/2026.\n",
        encoding="utf-8",
    )
    store = LegalOcrEvidenceStore(tmp_path / "store", "tenant-a")
    pipeline = LegalOcrPipeline(
        LegalOcrConfig(tenant_id="tenant-a", primary_engine="native-text-fallback", fallback_engine="static-low-confidence"),
        store,
    )

    evidence = pipeline.run_path(source, tenant_id="tenant-a", document_id="D-OCR")[0]

    assert evidence["alto_xml_path"].endswith("alto.xml")
    assert (tmp_path / "store" / evidence["alto_xml_path"]).exists()
    assert isinstance(evidence["tables"], list)
    entities = evidence["legal_entities"]
    assert entities["numero_ruolo"][0]["numero"] == "12345"
    assert any(u.startswith("Tribunale di Milano") for u in entities["uffici"])
    assert any("28/2010" in r for r in entities["riferimenti"])
    # L'evento di export strutturato è tracciato nell'audit-chain.
    audit_files = list((tmp_path / "store").rglob("*.jsonl"))
    assert any("ocr.structured_export" in f.read_text(encoding="utf-8") for f in audit_files)


def test_adapter_esterni_degradano_senza_crash_se_non_installati():
    # In assenza della libreria, l'engine NON solleva: ritorna errori e nessun
    # token, così la pipeline passa al fallback successivo (nessun silenzio).
    pages = [PageArtifact(page=1, image_path="p1.png", sha256="x", width=100, height=100, text_hint="")]
    for engine in (EasyOcrEngine(), PaddleOcrEngine()):
        run = engine.run(pages, language="ita")
        if "installed" not in run.version:  # libreria non presente nel sandbox
            assert run.tokens == []
            assert run.errors and "non disponibile" in run.errors[0].lower()
