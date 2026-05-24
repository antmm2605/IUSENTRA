from __future__ import annotations

import json
import stat
import subprocess
import sys
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from pct.pec_ocr_pipeline import (
    PecOcrPipeline,
    PecOcrPipelineConfig,
    WormStorage,
    WormViolation,
    build_demo_eml,
)


def _zip(entries: dict[str, bytes | str]) -> bytes:
    bio = BytesIO()
    with ZipFile(bio, "w", ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value.encode("utf-8") if isinstance(value, str) else value)
    return bio.getvalue()


def test_pec_ocr_pipeline_end_to_end_worm_unzip_ocr_dedup_and_lex(tmp_path: Path):
    duplicate_text = "Tribunale di Milano\nRicorso R.G. 1234/2026\nUdienza fissata al 10/10/2026."
    eml = build_demo_eml(
        _zip(
            {
                "allegati/ricorso.txt": duplicate_text,
                "allegati/copia-ricorso.txt": duplicate_text,
                "ricevute/daticert.xml": "<?xml version='1.0'?><postacert><tipo>avvenuta_consegna</tipo></postacert>",
            }
        )
    )
    pipeline = PecOcrPipeline(PecOcrPipelineConfig(runtime_root=tmp_path, tenant_id="studio_legale_pct"))

    result = pipeline.process_eml(eml, priority="high")

    assert result["ok"] is True
    topics = result["events_by_topic"]
    assert topics["mail.ingest"] == 1
    assert topics["mail.unzip"] == 1
    assert topics["raw_blob.stored"] >= 2
    assert topics["ocr.task"] >= 2
    assert topics["ocr.result"] == topics["ocr.task"]
    assert topics["lex.ingest.doc"] == topics["ocr.result"]
    assert topics["ocr.skipped"] >= 1
    assert result["health"]["ocr_success_pct"] == 100.0
    assert result["health"]["dedup_hit_rate"] > 0

    ingest = next(event for event in result["events"] if event["topic"] == "mail.ingest")["payload"]
    worm_path = tmp_path / ingest["eml_path"]
    assert worm_path.exists()
    assert ingest["checksum"].startswith("sha256:")
    assert not bool(worm_path.stat().st_mode & stat.S_IWRITE)

    indexed = [event["payload"] for event in result["events"] if event["topic"] == "document.indexed"]
    assert any(item["fascicolo_candidate"]["rg"] == "1234" for item in indexed)


def test_pec_ocr_pipeline_blocks_unsafe_zip_and_antivirus_positive(tmp_path: Path):
    pipeline = PecOcrPipeline(PecOcrPipelineConfig(runtime_root=tmp_path, tenant_id="studio_legale_pct"))
    unsafe = pipeline.process_eml(build_demo_eml(_zip({"programma.exe": b"MZ unsafe"})))

    assert unsafe["ok"] is False
    assert unsafe["status"] == "needs_attention"
    assert unsafe["events_by_topic"]["mail.unzip.blocked"] >= 1
    assert unsafe["events_by_topic"].get("ocr.task", 0) == 0

    infected_message = EmailMessage()
    infected_message["From"] = "cancelleria@pec.giustizia.it"
    infected_message["To"] = "studio@example.pec.it"
    infected_message["Subject"] = "POSTA CERTIFICATA: controllo antivirus"
    infected_message["Date"] = "Sat, 23 May 2026 10:21:15 +0000"
    infected_message.set_content("EICAR-STANDARD-ANTIVIRUS-TEST-FILE")
    infected_pipeline = PecOcrPipeline(PecOcrPipelineConfig(runtime_root=tmp_path / "infected", tenant_id="studio_legale_pct"))
    infected = infected_pipeline.process_eml(infected_message.as_bytes())
    assert infected["status"] == "quarantined"
    assert infected["events_by_topic"]["mail.quarantine"] == 1
    assert not list((tmp_path / "infected").glob("worm/**/*.eml"))


def test_worm_storage_write_once_rejects_checksum_change(tmp_path: Path):
    worm = WormStorage(tmp_path)
    first = worm.put_original(
        mail_id="pec_forzata",
        data=b"prima versione",
        received_at="2026-05-23T10:21:15Z",
        metadata={"sender": "studio@example.pec.it"},
    )
    same = worm.put_original(
        mail_id="pec_forzata",
        data=b"prima versione",
        received_at="2026-05-23T10:21:15Z",
        metadata={"sender": "studio@example.pec.it"},
    )

    assert first["duplicate"] is False
    assert same["duplicate"] is True
    with pytest.raises(WormViolation):
        worm.put_original(
            mail_id="pec_forzata",
            data=b"seconda versione",
            received_at="2026-05-23T10:21:15Z",
            metadata={"sender": "studio@example.pec.it"},
        )


def test_script_veritiero_pec_ocr_pipeline_success(tmp_path: Path):
    completed = subprocess.run(
        [sys.executable, "scripts/test_pec_ocr_pipeline.py", "--runtime-root", str(tmp_path / "runtime")],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["events_by_topic"]["mail.ingest"] == 1
    assert payload["events_by_topic"]["ocr.result"] >= 1
    assert payload["health"]["ocr_success_pct"] == 100.0
