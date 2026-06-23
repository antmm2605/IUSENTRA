"""Audit dry-run della busta deposito contro campioni reali.

Lo script non invia PEC e non registra depositi: legge un pacchetto generato
dal server e lo confronta con EML/file reali usati come modello.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from xml.etree import ElementTree as ET

from pct.atto_enc_validation import is_atto_enc_cms_enveloped_data


INDICE_DOCUMENTI_FILENAME = "IndiceDocumentiDepositati.PDF"
INDICE_BUSTA_FILENAME = "IndiceBusta.xml"


@dataclass(frozen=True)
class EvidenceAttachment:
    source: str
    name: str
    content_type: str
    size: int
    sha256: str
    cms_enveloped_data: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "name": self.name,
            "content_type": self.content_type,
            "size": self.size,
            "sha256": self.sha256,
            "cms_enveloped_data": self.cms_enveloped_data,
        }


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _clean_name(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _parse_xml_document_names(xml_bytes: bytes) -> list[str]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    names: list[str] = []
    for element in root.iter():
        if element.tag.endswith("NomeFile") and element.text:
            names.append(_clean_name(element.text))
    return names


def inspect_generated_package(package_path: Path) -> dict[str, object]:
    if not package_path.exists():
        raise FileNotFoundError(str(package_path))
    package_bytes = package_path.read_bytes()
    result: dict[str, object] = {
        "path": str(package_path),
        "filename": package_path.name,
        "size": len(package_bytes),
        "sha256": _sha256(package_bytes),
        "is_zip_package": False,
        "is_atto_enc": package_path.name.lower() == "atto.enc",
        "atto_msg_path": "",
        "entries": [],
        "document_names_from_xml": [],
        "has_dati_atto_xml": False,
        "has_dati_atto_signed": False,
        "has_indice_busta_xml": False,
        "has_indice_documenti": False,
        "has_atto_enc_inside": False,
        "atto_enc_cms_enveloped_data": False,
    }
    try:
        with zipfile.ZipFile(package_path, "r") as zf:
            names = zf.namelist()
            result["is_zip_package"] = True
            result["entries"] = names
            result["has_dati_atto_xml"] = "DatiAtto.xml" in names
            result["has_dati_atto_signed"] = any(name.lower() == "datiatto.xml.p7m" for name in names)
            result["has_indice_busta_xml"] = INDICE_BUSTA_FILENAME in names
            result["has_indice_documenti"] = INDICE_DOCUMENTI_FILENAME in names
            result["has_atto_enc_inside"] = any(Path(name).name.lower() == "atto.enc" for name in names)
            if "DatiAtto.xml" in names:
                result["document_names_from_xml"] = _parse_xml_document_names(zf.read("DatiAtto.xml"))
    except zipfile.BadZipFile:
        result["is_zip_package"] = False
        atto_msg_path = package_path.with_name("Atto.msg")
        if atto_msg_path.exists():
            result["atto_msg_path"] = str(atto_msg_path)
            message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())
            entries: list[str] = []
            attachments: dict[str, bytes] = {}
            for part in message.iter_attachments():
                name = _clean_name(part.get_filename() or "")
                if not name:
                    continue
                entries.append(name)
                attachments[Path(name).name] = part.get_payload(decode=True) or b""
            result["entries"] = entries
            result["has_dati_atto_xml"] = "DatiAtto.xml" in attachments
            result["has_dati_atto_signed"] = any(name.lower() == "datiatto.xml.p7m" for name in entries)
            result["has_indice_busta_xml"] = INDICE_BUSTA_FILENAME in attachments
            result["has_indice_documenti"] = INDICE_DOCUMENTI_FILENAME in attachments
            result["has_atto_enc_inside"] = result["is_atto_enc"]
            result["atto_enc_cms_enveloped_data"] = bool(
                result["is_atto_enc"] and is_atto_enc_cms_enveloped_data(package_bytes)
            )
            if "DatiAtto.xml" in attachments:
                result["document_names_from_xml"] = _parse_xml_document_names(attachments["DatiAtto.xml"])
    return result


def _parse_evidence_file(path: Path) -> list[EvidenceAttachment]:
    payload = path.read_bytes()
    attachments: list[EvidenceAttachment] = []
    try:
        message = BytesParser(policy=policy.default).parsebytes(payload)
    except Exception:
        message = None

    if message is not None and message.is_multipart():
        for part in message.iter_attachments():
            content = part.get_payload(decode=True) or b""
            name = _clean_name(part.get_filename() or "")
            if not name:
                name = f"allegato-{len(attachments) + 1}"
            attachments.append(
                EvidenceAttachment(
                    source=str(path),
                    name=name,
                    content_type=part.get_content_type(),
                    size=len(content),
                    sha256=_sha256(content),
                    cms_enveloped_data=name.lower() == "atto.enc" and is_atto_enc_cms_enveloped_data(content),
                )
            )
    if attachments:
        return attachments
    return [
        EvidenceAttachment(
            source=str(path),
            name=path.name,
            content_type="application/octet-stream",
            size=len(payload),
            sha256=_sha256(payload),
            cms_enveloped_data=path.name.lower() == "atto.enc" and is_atto_enc_cms_enveloped_data(payload),
        )
    ]


def inspect_evidence(paths: list[Path]) -> dict[str, object]:
    attachments: list[EvidenceAttachment] = []
    for path in paths:
        if path.exists():
            attachments.extend(_parse_evidence_file(path))
    names = [item.name for item in attachments]
    lower_names = [name.lower() for name in names]
    return {
        "sources": [str(path) for path in paths],
        "attachments": [item.to_dict() for item in attachments],
        "attachment_names": names,
        "has_real_atto_enc": any(name == "atto.enc" for name in lower_names),
        "has_real_atto_enc_cms": any(item.name.lower() == "atto.enc" and item.cms_enveloped_data for item in attachments),
        "has_copy_dati_atto": any(name in {"datiatto.xml", "datiatto.xml.p7m"} for name in lower_names),
        "has_copy_indice": any(name == INDICE_DOCUMENTI_FILENAME.lower() for name in lower_names),
        "has_notification_receipts": any(
            "accettazione" in name or "consegna" in name or "ricevuta" in name for name in lower_names
        ),
    }


def audit_deposito_package(package_path: Path, evidence_paths: list[Path]) -> dict[str, object]:
    generated = inspect_generated_package(package_path)
    evidence = inspect_evidence(evidence_paths)
    entries = list(generated.get("entries") or [])
    generated_names = {Path(str(name)).name.lower() for name in entries}

    control_matches = bool(
        (generated.get("has_dati_atto_xml") or generated.get("has_dati_atto_signed"))
        and generated.get("has_indice_busta_xml")
        and generated.get("has_indice_documenti")
        and evidence.get("has_copy_dati_atto")
        and evidence.get("has_copy_indice")
    )
    real_transport_matches = bool(
        generated.get("is_atto_enc")
        and generated.get("has_atto_enc_inside")
        and generated.get("atto_enc_cms_enveloped_data")
        and evidence.get("has_real_atto_enc_cms")
        and not generated.get("is_zip_package")
    )
    differences: list[dict[str, str]] = []
    if generated.get("has_dati_atto_xml") and evidence.get("has_copy_dati_atto"):
        differences.append(
            {
                "level": "warning",
                "code": "DATI_ATTO_UNSIGNED",
                "message": "Il pacchetto generato contiene DatiAtto.xml non firmato; nei campioni reali compare DatiAtto.xml.p7m.",
                "action": "Firmare DatiAtto.xml o usare adapter ministeriale prima del deposito valido.",
            }
        )
    if not real_transport_matches:
        differences.append(
            {
                "level": "block_real_send",
                "code": "ATTO_ENC_AES256_MISSING",
                "message": "Il pacchetto generato non coincide con l'invio reale: nei campioni l'invio PEC trasporta Atto.enc.",
                "action": "Generare o collegare Atto.enc ministeriale cifrato AES256 prima di qualunque invio reale.",
            }
        )
    if INDICE_DOCUMENTI_FILENAME.lower() not in generated_names:
        differences.append(
            {
                "level": "block_control",
                "code": "INDICE_MISSING",
                "message": "IndiceDocumentiDepositati.PDF non presente nel pacchetto generato.",
                "action": "Rigenerare la busta includendo l'indice documenti.",
            }
        )
    if INDICE_BUSTA_FILENAME.lower() not in generated_names:
        differences.append(
            {
                "level": "block_control",
                "code": "INDICE_BUSTA_XML_MISSING",
                "message": "IndiceBusta.xml ministeriale non presente nel pacchetto generato.",
                "action": "Rigenerare Atto.msg includendo IndiceBusta.xml prima della cifratura in Atto.enc.",
            }
        )

    return {
        "ok_control_package": control_matches,
        "ok_real_transport": real_transport_matches,
        "must_not_send_real_pec": True,
        "server_dry_run": True,
        "generated": generated,
        "evidence": evidence,
        "comparison": {
            "control_package_matches_non_encrypted_copy": control_matches,
            "ministerial_transport_matches_real_send": real_transport_matches,
            "generated_has_only_selected_documents": True,
            "differences": differences,
        },
    }


def write_markdown_report(report: dict[str, object], target: Path) -> None:
    comparison = report.get("comparison") if isinstance(report.get("comparison"), dict) else {}
    generated = report.get("generated") if isinstance(report.get("generated"), dict) else {}
    evidence = report.get("evidence") if isinstance(report.get("evidence"), dict) else {}
    lines = [
        "# Audit dry-run deposito server",
        "",
        f"- Pacchetto di controllo coerente con copia non crittografata: {comparison.get('control_package_matches_non_encrypted_copy')}",
        f"- Trasporto ministeriale identico a invio reale: {comparison.get('ministerial_transport_matches_real_send')}",
        "- Invio PEC reale: disattivato nella prova",
        f"- Pacchetto: `{generated.get('filename', '')}`",
        f"- Voci pacchetto: {len(generated.get('entries') or [])}",
        f"- Evidenze reali lette: {len(evidence.get('attachments') or [])} allegati",
        "",
        "## Differenze",
        "",
    ]
    differences = comparison.get("differences") if isinstance(comparison.get("differences"), list) else []
    if not differences:
        lines.append("- Nessuna differenza rilevata.")
    else:
        for item in differences:
            if not isinstance(item, dict):
                continue
            lines.append(f"- `{item.get('code')}` ({item.get('level')}): {item.get('message')} Azione: {item.get('action')}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit dry-run busta deposito contro campioni reali.")
    parser.add_argument("--package", required=True, help="Percorso pacchetto/busta generata in dry-run.")
    parser.add_argument("--evidence", action="append", default=[], help="EML o file reale allegato dall'utente.")
    parser.add_argument("--report-json", default="", help="Percorso report JSON.")
    parser.add_argument("--report-md", default="", help="Percorso report Markdown.")
    parser.add_argument("--strict-real-transport", action="store_true", help="Esce con errore se manca Atto.enc ministeriale.")
    args = parser.parse_args(argv)

    report = audit_deposito_package(Path(args.package), [Path(item) for item in args.evidence])
    if args.report_json:
        Path(args.report_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.report_md:
        write_markdown_report(report, Path(args.report_md))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict_real_transport and not report["ok_real_transport"]:
        return 2
    return 0 if report["ok_control_package"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
