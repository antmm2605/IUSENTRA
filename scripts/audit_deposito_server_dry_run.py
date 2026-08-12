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
from pct.firma import estrai_contenuto_cades


INDICE_DOCUMENTI_FILENAME = "IndiceDocumentiDepositati.PDF"
INDICE_BUSTA_FILENAME = "IndiceBusta.xml"
INDICE_BUSTA_TIPI_ALLEGATO = frozenset({"SM", "IR", "PL", "DA", "RT", "RU", "PA", "RA", "PC", "D", "A", "IA"})


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


def _mime_part_name(part) -> str:
    name = part.get_filename() or part.get_param("name", header="Content-Type") or ""
    if not name:
        content_id = str(part.get("Content-ID") or "").strip("<> ")
        if "." in content_id:
            name = content_id
    return _clean_name(Path(str(name)).name) if name else ""


def _iter_named_mime_parts(message):
    for part in message.walk():
        if part.is_multipart():
            continue
        name = _mime_part_name(part)
        if not name:
            continue
        yield name, part.get_payload(decode=True) or b"", part.get_content_type()


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


def _xml_has_indice_busta(xml_bytes: bytes) -> bool:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return False
    for element in root.iter():
        if str(element.tag).split("}")[-1] == "IndiceBusta":
            return True
    return False


def _expected_indice_busta_tipo(name: str) -> str:
    lower = _clean_name(name).casefold()
    compact = lower.replace("-", "_").replace(" ", "_")
    if lower in {"datiatto.xml", "datiatto.xml.p7m"}:
        return "DA"
    if lower == INDICE_DOCUMENTI_FILENAME.lower():
        return "SM"
    if "procura" in lower:
        return "PL"
    if "iscrizione" in lower and "ruolo" in lower:
        return "IR"
    if "avvenuta consegna" in lower or "consegna" in lower:
        return "RA"
    if lower.endswith(".eml") and ("notifica" in lower or "notificazione" in lower or "posta certificata" in lower):
        return "PA"
    if (
        "rt_" in compact
        or "ricevuta telematica" in lower
        or "pagopa" in lower
        or ("contributo" in lower and "unificat" in lower and ("ricevut" in lower or "pagament" in lower))
        or ("ricevut" in lower and "pagament" in lower and "telematic" in lower)
    ):
        return "RT"
    return "SM"


def _parse_indice_busta_types(xml_bytes: bytes) -> tuple[dict[str, str], list[str]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        return {}, [f"{INDICE_BUSTA_FILENAME} non leggibile: {exc}"]
    if str(root.tag).split("}")[-1] != "IndiceBusta":
        return {}, [f"{INDICE_BUSTA_FILENAME} non ha radice IndiceBusta"]
    types: dict[str, str] = {}
    errors: list[str] = []
    for element in list(root):
        local = str(element.tag).split("}")[-1]
        if local != "Allegato":
            continue
        name = _clean_name(element.attrib.get("Nome") or "")
        tipo = _clean_name(element.attrib.get("Tipo") or "").upper()
        if not name or not tipo:
            errors.append("Allegato IndiceBusta senza Nome o Tipo")
            continue
        types[name] = tipo
        if tipo not in INDICE_BUSTA_TIPI_ALLEGATO:
            errors.append(f"{name}: Tipo={tipo} non ammesso dalla DTD ministeriale")
            continue
        expected = _expected_indice_busta_tipo(name)
        if expected != tipo:
            errors.append(f"{name}: Tipo={tipo}, atteso Tipo={expected}")
    return types, errors


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
        "has_indice_busta_internal": False,
        "has_indice_busta_xml": False,
        "indice_busta_mode": "",
        "indice_busta_types": {},
        "indice_busta_type_errors": [],
        "indice_busta_tipi_ok": False,
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
            if INDICE_BUSTA_FILENAME in names:
                indice_types, indice_errors = _parse_indice_busta_types(zf.read(INDICE_BUSTA_FILENAME))
                result["indice_busta_types"] = indice_types
                result["indice_busta_type_errors"] = indice_errors
                result["indice_busta_tipi_ok"] = not indice_errors
            if "DatiAtto.xml" in names:
                dati_atto = zf.read("DatiAtto.xml")
                result["document_names_from_xml"] = _parse_xml_document_names(dati_atto)
                result["has_indice_busta_internal"] = _xml_has_indice_busta(dati_atto)
            signed_name = next((name for name in names if name.lower() == "datiatto.xml.p7m"), "")
            if signed_name:
                try:
                    dati_atto_signed = estrai_contenuto_cades(zf.read(signed_name))
                    result["document_names_from_xml"] = _parse_xml_document_names(dati_atto_signed)
                    result["has_indice_busta_internal"] = _xml_has_indice_busta(dati_atto_signed)
                except Exception as exc:
                    result["dati_atto_signed_error"] = str(exc)
    except zipfile.BadZipFile:
        result["is_zip_package"] = False
        atto_msg_path = package_path.with_name("Atto.msg")
        if atto_msg_path.exists():
            result["atto_msg_path"] = str(atto_msg_path)
            message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())
            entries: list[str] = []
            attachments: dict[str, bytes] = {}
            for name, content, _content_type in _iter_named_mime_parts(message):
                entries.append(name)
                attachments[Path(name).name] = content
            result["entries"] = entries
            result["has_dati_atto_xml"] = "DatiAtto.xml" in attachments
            result["has_dati_atto_signed"] = any(name.lower() == "datiatto.xml.p7m" for name in entries)
            result["has_indice_busta_xml"] = INDICE_BUSTA_FILENAME in attachments
            result["has_indice_documenti"] = INDICE_DOCUMENTI_FILENAME in attachments
            result["has_atto_enc_inside"] = result["is_atto_enc"]
            result["atto_enc_cms_enveloped_data"] = bool(
                result["is_atto_enc"] and is_atto_enc_cms_enveloped_data(package_bytes)
            )
            if INDICE_BUSTA_FILENAME in attachments:
                indice_types, indice_errors = _parse_indice_busta_types(attachments[INDICE_BUSTA_FILENAME])
                result["indice_busta_types"] = indice_types
                result["indice_busta_type_errors"] = indice_errors
                result["indice_busta_tipi_ok"] = not indice_errors
            if "DatiAtto.xml" in attachments:
                dati_atto = attachments["DatiAtto.xml"]
                result["document_names_from_xml"] = _parse_xml_document_names(dati_atto)
                result["has_indice_busta_internal"] = _xml_has_indice_busta(dati_atto)
            signed_payload = next(
                (content for name, content in attachments.items() if name.lower() == "datiatto.xml.p7m"),
                b"",
            )
            if signed_payload:
                try:
                    dati_atto_signed = estrai_contenuto_cades(signed_payload)
                    result["document_names_from_xml"] = _parse_xml_document_names(dati_atto_signed)
                    result["has_indice_busta_internal"] = _xml_has_indice_busta(dati_atto_signed)
                except Exception as exc:
                    result["dati_atto_signed_error"] = str(exc)
    if result["has_indice_busta_internal"] and result["has_indice_busta_xml"]:
        result["indice_busta_mode"] = "ambiguo_indice_interno_e_xml"
    elif result["has_indice_busta_internal"]:
        result["indice_busta_mode"] = "interno_dati_atto"
    elif result["has_indice_busta_xml"]:
        result["indice_busta_mode"] = "indice_busta_xml"
    return result


def _parse_evidence_file(path: Path) -> list[EvidenceAttachment]:
    payload = path.read_bytes()
    attachments: list[EvidenceAttachment] = []
    try:
        message = BytesParser(policy=policy.default).parsebytes(payload)
    except Exception:
        message = None

    if message is not None and message.is_multipart():
        for name, content, content_type in _iter_named_mime_parts(message):
            if not name:
                name = f"allegato-{len(attachments) + 1}"
            attachments.append(
                EvidenceAttachment(
                    source=str(path),
                    name=name,
                    content_type=content_type,
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

    has_indice_internal = bool(generated.get("has_indice_busta_internal"))
    has_indice_external = bool(generated.get("has_indice_busta_xml"))
    indice_ambiguous = has_indice_internal and has_indice_external
    indice_ok = bool(
        not indice_ambiguous
        and (
            has_indice_internal
            or (has_indice_external and generated.get("indice_busta_tipi_ok") is True)
        )
    )
    control_matches = bool(
        (generated.get("has_dati_atto_xml") or generated.get("has_dati_atto_signed"))
        and indice_ok
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
                "level": "warning",
                "code": "INDICE_MISSING",
                "message": "IndiceDocumentiDepositati.PDF non presente nel pacchetto generato.",
                "action": "Rigenerare la busta includendo l'indice documenti.",
            }
        )
    if not indice_ok and not indice_ambiguous:
        differences.append(
            {
                "level": "block_control",
                "code": "INDICE_BUSTA_MISSING",
                "message": "IndiceBusta ministeriale non presente né nel DatiAtto né come XML esterno.",
                "action": "Rigenerare il DatiAtto con IndiceBusta interno oppure, per i tracciati che lo prevedono, includere IndiceBusta.xml esterno.",
            }
        )
    if indice_ambiguous:
        differences.append(
            {
                "level": "block_control",
                "code": "INDICE_BUSTA_AMBIGUOUS",
                "message": "Il pacchetto contiene sia IndiceBusta.xml sia IndiceBusta interno nel DatiAtto.",
                "action": "Usare una sola modalità IndiceBusta, secondo il tracciato ministeriale del tipo di deposito.",
            }
        )

    indice_type_errors = [
        str(item)
        for item in (generated.get("indice_busta_type_errors") or [])
        if str(item).strip()
    ]
    if indice_type_errors:
        differences.append(
            {
                "level": "block_control",
                "code": "INDICE_BUSTA_TIPI",
                "message": "IndiceBusta.xml contiene tipi allegato non conformi: " + "; ".join(indice_type_errors),
                "action": "Rigenerare IndiceBusta.xml classificando correttamente RT, PA, RA, PL, IR, DA e SM.",
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
