from __future__ import annotations

import json
import hashlib
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from email import message_from_bytes
from email.message import EmailMessage
from html import escape
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.document_intelligence.indexer import DocumentAIIndexer, build_lex_indexing_summary
from pct.document_intelligence.models import DocumentAIRecord, utc_now
from pct.document_intelligence.sources import source_from_uploaded_document
from pct.email_client import GestioneEmailRicevute
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.notifiche_legali import (
    LEGAL_NOTIFICATION_SUBJECT,
    build_notification_attachment_manifest,
    build_notification_timing_plan,
    generate_relata_pdf_bytes,
    notification_directive_matrix,
    office_notification_evidence_from_pec,
    prepare_pst_failed_notification_workflow,
    released_office_documents_from_pec,
    validate_deposit_notification_proof,
    validate_legal_notification,
)


ARTIFACT_DIR = REPO_ROOT / "artifacts" / "notifiche-legali"
JSON_REPORT = ARTIFACT_DIR / "notifiche-legali-demo-e2e.json"
PDF_REPORT = ARTIFACT_DIR / "notifiche-legali-demo-e2e.pdf"
RUNTIME_ROOT = REPO_ROOT / ".tmp" / "notifiche-legali-demo-e2e"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _italian_generated_at(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    months = (
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    )
    return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}, ore {parsed.hour:02d}:{parsed.minute:02d}"


def _base_payload() -> dict[str, Any]:
    return {
        "operazione": "notifica_pec_l53",
        "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT,
        "avvocato_nome": "Mario Rossi",
        "avvocato_cf": "RSSMRA80A01H501U",
        "avvocato_foro": "Roma",
        "studio_indirizzo": "Via Roma 1",
        "studio_citta": "Roma",
        "luogo": "Roma",
        "data_relata": "2026-05-24",
        "mittente_pec": "studio.rossi@example.pec.it",
        "fonte_pec_mittente": "ReGIndE",
        "mittente_pec_pubblico_elenco": True,
        "mittente_avvocato_abilitato": True,
        "mittente_pec_validata": True,
        "assistito_nome": "Cliente S.r.l.",
        "assistito_cf": "01234567890",
        "ruolo_destinatario": "controparte",
        "destinatario_nome": "Controparte S.p.A.",
        "destinatario_cf": "09876543210",
        "destinatario_codice_fiscale_piva": "09876543210",
        "destinatario_pec": "controparte@example.pec.it",
        "fonte_pec_destinatario": "registro_imprese",
        "destinatario_pec_pubblico_elenco": True,
        "data_verifica_pec": "2026-05-24T10:30",
        "procedimento_pendente": False,
        "ufficio_giudiziario": "Tribunale di Roma",
        "sezione": "III",
        "numero_rg": "1234",
        "anno_rg": "2026",
        "giudice": "Dott. Verdi",
        "ricevuta_completa": True,
        "relata_firmata": True,
        "relata_documento_separato": True,
        "approvazione_avvocato": True,
        "data_ora_invio_pec": "2026-05-24T10:30",
        "documenti": [
            {
                "nome_file": "atto_da_notificare.pdf",
                "descrizione": "Atto da notificare",
                "origine": "nativo_digitale",
                "hash_sha256": "a" * 64,
            }
        ],
        "provvedimento_tipo": "sentenza",
        "provvedimento_numero": "101",
        "provvedimento_anno": "2026",
        "provvedimento_ufficio_origine": "Tribunale di Roma",
        "provvedimento_data": "2026-05-20",
        "provvedimento_data_deposito": "2026-05-20",
        "provvedimento_rinnovo_data": "2026-05-22",
        "notifica_precedente_data": "2026-05-18",
        "notifica_precedente_esito": "mancata consegna",
        "riassunzione_causa": "interruzione del processo",
        "sfratto_tipo_procedimento": "intimazione di sfratto per morosità",
        "sfratto_immobile_indirizzo": "Via Milano 20, Roma",
        "esecuzione_debitore": "Debitore S.r.l.",
        "esecuzione_terzo_pignorato": "Banca Terza S.p.A.",
        "destinatario_qualifica": "terzo destinatario",
        "destinatario_parte_rappresentata": "Controparte S.p.A.",
        "opposizione_tipo": "opposizione agli atti esecutivi",
    }


def _record(name: str, ok: bool, detail: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail, "data": data or {}}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _demo_file_bytes(label: str) -> bytes:
    safe = " ".join(str(label or "documento").split())
    if safe.lower().endswith((".pdf", ".pdf.p7m")):
        return (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R/Contents 4 0 R>>endobj\n"
            + f"4 0 obj<</Length 70>>stream\nBT /F1 12 Tf 72 760 Td ({safe[:80]}) Tj ET\nendstream endobj\n".encode("utf-8")
            + b"trailer<</Root 1 0 R>>\n%%EOF"
        )
    return f"Documento demo IUSENTRA: {safe}\n".encode("utf-8")


def _normalise_case_documents(payload: dict[str, Any], overrides: dict[str, bytes] | None = None) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    overrides = overrides or {}
    for item in payload.get("documenti") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("nome_file") or "documento.pdf")
        content = overrides.get(name) or _demo_file_bytes(name)
        item["hash_sha256"] = _sha256_bytes(content)
        files[name] = content
    return files


def _receipt_eml_bytes(*, kind: str, recipient: str, pec_message_id: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = "gestore.pec@example.test"
    msg["To"] = "studio.rossi@example.pec.it"
    msg["Subject"] = f"{kind} - notifica L. 53/1994"
    msg["Message-ID"] = f"<{kind.lower().replace(' ', '-')}-{hashlib.sha1((recipient + pec_message_id + kind).encode('utf-8')).hexdigest()[:16]}@pec.example.test>"
    msg.set_content(
        "\n".join(
            [
                f"Ricevuta {kind}",
                f"Destinatario: {recipient}",
                f"Messaggio notificato: {pec_message_id}",
                "Ricevuta completa conservata in originale digitale.",
            ]
        )
    )
    return msg.as_bytes()


def _compose_demo_notification_pec(
    *,
    payload: dict[str, Any],
    body: str,
    relata_signed: bytes,
    document_files: dict[str, bytes],
    recipient: dict[str, Any],
) -> bytes:
    msg = EmailMessage()
    msg["From"] = payload.get("mittente_pec") or "studio.rossi@example.pec.it"
    msg["To"] = recipient.get("pec") or payload.get("destinatario_pec") or "destinatario@example.pec.it"
    msg["Subject"] = LEGAL_NOTIFICATION_SUBJECT
    msg["Message-ID"] = f"<notifica-l53-{hashlib.sha1((str(recipient) + str(payload.get('caso_notifica'))).encode('utf-8')).hexdigest()[:18]}@iusentra.example.test>"
    msg.set_content(body or "Notificazione ai sensi della legge n. 53 del 1994.")
    msg.add_attachment(relata_signed, maintype="application", subtype="octet-stream", filename="relata_notifica.pdf.p7m")
    for filename, content in document_files.items():
        msg.add_attachment(content, maintype="application", subtype="pdf", filename=filename)
    return msg.as_bytes()


def _simulate_complete_delivery_and_deposit(
    *,
    payload: dict[str, Any],
    case_id: str,
    role: str,
    runtime_dir: Path,
    file_contents: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    document_files = _normalise_case_documents(payload, file_contents)
    notification = validate_legal_notification(payload)
    if not notification.ok:
        return {
            "ok": False,
            "detail": "; ".join(notification.blockers[:3]),
            "notification": notification.to_dict(),
        }
    case_dir = runtime_dir / case_id / role
    case_dir.mkdir(parents=True, exist_ok=True)
    relata_pdf = generate_relata_pdf_bytes(payload)
    relata_signed = relata_pdf + b"\n%% IUSENTRA demo firma digitale controllata\n"
    relata_path = case_dir / "relata_notifica.pdf.p7m"
    relata_path.write_bytes(relata_signed)

    delivery = dict((notification.output_plan or {}).get("deliveryPlan") or {})
    recipients = list(delivery.get("recipients") or [])
    if not recipients:
        recipients = [{"name": payload.get("destinatario_nome"), "pec": payload.get("destinatario_pec"), "role": role}]

    deposit_recipients: list[dict[str, str]] = []
    pec_files: list[dict[str, str]] = []
    for index, recipient in enumerate(recipients, start=1):
        pec_bytes = _compose_demo_notification_pec(
            payload=payload,
            body=notification.body,
            relata_signed=relata_signed,
            document_files=document_files,
            recipient=recipient,
        )
        pec_path = case_dir / f"pec_inviata_{index}.eml"
        pec_path.write_bytes(pec_bytes)
        parsed_pec = message_from_bytes(pec_bytes)
        message_id = str(parsed_pec.get("Message-ID") or f"<pec-{index}@iusentra.example.test>")
        rac_bytes = _receipt_eml_bytes(kind="RAC", recipient=str(recipient.get("pec") or ""), pec_message_id=message_id)
        rdac_bytes = _receipt_eml_bytes(kind="RdAC completa", recipient=str(recipient.get("pec") or ""), pec_message_id=message_id)
        rac_path = case_dir / f"rac_{index}.eml"
        rdac_path = case_dir / f"rdac_completa_{index}.eml"
        rac_path.write_bytes(rac_bytes)
        rdac_path.write_bytes(rdac_bytes)
        deposit_recipients.append(
            {
                "nome": str(recipient.get("name") or payload.get("destinatario_nome") or f"Destinatario {index}"),
                "rac_file": rac_path.name,
                "rac_sha256": _sha256_bytes(rac_bytes),
                "rdac_file": rdac_path.name,
                "rdac_sha256": _sha256_bytes(rdac_bytes),
            }
        )
        pec_files.append({"file": pec_path.name, "sha256": _sha256_bytes(pec_bytes), "messageId": message_id})

    first_pec = pec_files[0]
    deposit_payload = {
        "atti_notificati": [
            {
                "nome_file": item.get("nome_file"),
                "hash_sha256": item.get("hash_sha256"),
            }
            for item in payload.get("documenti", [])
            if isinstance(item, dict)
        ],
        "relata_firmata": relata_path.name,
        "relata_sha256": _sha256_bytes(relata_signed),
        "pec_inviata": first_pec["file"],
        "pec_inviata_sha256": first_pec["sha256"],
        "destinatari": deposit_recipients,
        "ricevuta_completa": True,
        "dati_atto_ricevute": "; ".join(
            f"{item['nome']}: {item['rac_file']} e {item['rdac_file']}" for item in deposit_recipients
        ),
        "pec_ufficio_rilascio": payload.get("pec_ufficio_rilascio"),
        "pec_ufficio_eml_file": payload.get("pec_ufficio_eml_file"),
        "pec_ufficio_eml_sha256": payload.get("pec_ufficio_eml_sha256"),
    }
    deposit = validate_deposit_notification_proof(deposit_payload)
    return {
        "ok": bool(notification.ok and delivery.get("ready") and deposit.ok),
        "detail": (
            f"Relata PDF generata, PEC demo {len(pec_files)}, allegati {len(document_files) + 1}, "
            f"ricevute {len(deposit_recipients) * 2}, deposito prova {'OK' if deposit.ok else 'KO'}."
        ),
        "templateId": notification.template_id,
        "delivery": delivery,
        "deposit": deposit.to_dict(),
        "pecFiles": pec_files,
        "relataSha256": _sha256_bytes(relata_signed),
    }


def _apply_role(payload: dict[str, Any], role: str) -> None:
    payload["ruolo_destinatario"] = role
    if role == "difensore":
        payload.update(
            {
                "destinatario_nome": "Avv. Laura Bianchi",
                "destinatario_cf": "BNCLRA80A41H501M",
                "destinatario_codice_fiscale_piva": "BNCLRA80A41H501M",
                "destinatario_pec": "laura.bianchi@example.pec.it",
                "fonte_pec_destinatario": "reginde",
                "destinatario_parte_rappresentata": "Controparte S.p.A.",
                "destinatario_qualifica": "difensore costituito",
            }
        )
    elif role == "pa":
        payload.update(
            {
                "destinatario_nome": "Comune di Roma",
                "destinatario_cf": "02438750586",
                "destinatario_codice_fiscale_piva": "02438750586",
                "destinatario_pec": "protocollo.comune.roma@example.pec.it",
                "fonte_pec_destinatario": "registro_ppaa",
                "destinatario_qualifica": "pubblica amministrazione",
            }
        )
    elif role == "professionista":
        payload.update(
            {
                "destinatario_nome": "Dott. Paolo Verdi",
                "destinatario_cf": "VRDPLA79B10H501X",
                "destinatario_codice_fiscale_piva": "VRDPLA79B10H501X",
                "destinatario_pec": "paolo.verdi@example.pec.it",
                "fonte_pec_destinatario": "ini_pec",
                "destinatario_qualifica": "professionista",
            }
        )
    elif role == "terzo":
        payload.update(
            {
                "destinatario_nome": "Terzo Chiamato S.r.l.",
                "destinatario_cf": "11223344556",
                "destinatario_codice_fiscale_piva": "11223344556",
                "destinatario_pec": "terzo.chiamato@example.pec.it",
                "fonte_pec_destinatario": "registro_imprese",
                "destinatario_qualifica": "terzo destinatario",
            }
        )
    else:
        payload.update(
            {
                "destinatario_nome": "Controparte S.p.A.",
                "destinatario_cf": "09876543210",
                "destinatario_codice_fiscale_piva": "09876543210",
                "destinatario_pec": "controparte@example.pec.it",
                "fonte_pec_destinatario": "registro_imprese",
                "destinatario_qualifica": "controparte",
            }
        )


def _case_payload(case_id: str, directive: dict[str, Any]) -> dict[str, Any]:
    payload = _base_payload()
    payload["caso_notifica"] = case_id
    payload["procedimento_pendente"] = bool(directive.get("proceedingRequired"))
    allowed_roles = [item for item in (directive.get("allowedRecipientRoles") or []) if item]
    _apply_role(payload, allowed_roles[0] if allowed_roles else "controparte")
    if case_id in {"provvedimento_giudice", "sentenza_termine_breve", "decreto_ingiuntivo", "provvedimento_urgente"}:
        payload["documenti"] = [
            {
                "nome_file": "ordinanza_da_notificare.pdf",
                "descrizione": "Provvedimento comunicato dall'ufficio",
                "origine": "comunicazione_cancelleria",
                "data_comunicazione_cancelleria": "2026-05-23",
                "hash_sha256": "b" * 64,
                "documento_ufficio": True,
                "notifica_richiesta": True,
                "acquisito_da_portale": True,
                "fonte_documento": "PORTALE_TELEMATICO",
                "servizio_portale": "PST",
                "riferimento_portale": "PST-DOC-ORD-1",
            }
        ]
        payload["attestazione_multipla"] = True
        payload["pec_ufficio_rilascio"] = True
        payload["pec_ufficio_eml_file"] = "pec-cancelleria-provvedimento.eml"
        payload["pec_ufficio_eml_sha256"] = "e" * 64
        payload["pec_ufficio_message_id"] = "<pec-cancelleria-provvedimento@giustizia>"
    return payload


def _run_matrix_cases() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    matrix = notification_directive_matrix()
    for case in matrix["cases"]:
        payload = _case_payload(case["value"], case)
        outcome = validate_legal_notification(payload)
        detail = outcome.template_label if outcome.ok else "; ".join(outcome.blockers[:3])
        results.append(_record(f"Caso notifica: {case['label']}", outcome.ok, detail, {"templateId": outcome.template_id}))
    for role in matrix["roles"]:
        payload = _base_payload()
        _apply_role(payload, role["value"])
        payload["caso_notifica"] = "ordinaria"
        payload["fonte_pec_destinatario"] = (role.get("allowedRegisters") or ["altro_pubblico_elenco"])[0]
        payload["destinatario_parte_rappresentata"] = "Controparte S.p.A."
        payload["destinatario_codice_fiscale_piva"] = "09876543210"
        outcome = validate_legal_notification(payload)
        detail = outcome.template_label if outcome.ok else "; ".join(outcome.blockers[:3])
        results.append(_record(f"Destinatario: {role['label']}", outcome.ok, detail, {"templateId": outcome.template_id}))
    mismatch = _base_payload()
    mismatch.update(
        {
            "ruolo_destinatario": "difensore",
            "destinatario_parte_rappresentata": "Controparte S.p.A.",
            "fonte_pec_destinatario": "registro_imprese",
        }
    )
    mismatch_result = validate_legal_notification(mismatch)
    results.append(
        _record(
            "Blocco registro incoerente",
            not mismatch_result.ok and any("PEC_DESTINATARIO_REGISTRO_INCOERENTE" in item for item in mismatch_result.blockers),
            "; ".join(mismatch_result.blockers[:2]),
        )
    )
    wrong_case = _case_payload("chiamata_terzo", next(item for item in matrix["cases"] if item["value"] == "chiamata_terzo"))
    _apply_role(wrong_case, "controparte")
    wrong_case_result = validate_legal_notification(wrong_case)
    results.append(
        _record(
            "Blocco destinatario incoerente con la casistica",
            not wrong_case_result.ok and any("DESTINATARIO_CASO_INCOERENTE" in item for item in wrong_case_result.blockers),
            "; ".join(wrong_case_result.blockers[:2]),
        )
    )
    results.append(
        _record(
            "Fonti normative esposte su tutta la matrice",
            all(case.get("legalBasis") and case.get("allowedRecipientRoles") and case.get("recipientRule") for case in matrix["cases"])
            and all(role.get("legalBasis") for role in matrix["roles"]),
            "Ogni caso espone fonti, regola destinatario e ruoli ammessi; ogni ruolo espone registri e fonti.",
            {"cases": len(matrix["cases"]), "roles": len(matrix["roles"])},
        )
    )
    office_payload = _case_payload("provvedimento_giudice", next(item for item in matrix["cases"] if item["value"] == "provvedimento_giudice"))
    manifest = build_notification_attachment_manifest(office_payload)
    results.append(
        _record(
            "Allegati ed EML PEC ufficio governati",
            all(item["present"] for item in manifest if item["required"]),
            "; ".join(f"{item['label']}: {'presente' if item['present'] else 'mancante'}" for item in manifest if item["required"]),
            {"manifest": manifest},
        )
    )
    missing_eml = _case_payload("provvedimento_giudice", next(item for item in matrix["cases"] if item["value"] == "provvedimento_giudice"))
    missing_eml.pop("pec_ufficio_eml_file", None)
    missing_eml.pop("pec_ufficio_eml_sha256", None)
    missing_eml.pop("pec_ufficio_message_id", None)
    missing_eml_result = validate_legal_notification(missing_eml)
    results.append(
        _record(
            "Blocco EML PEC ufficio mancante",
            not missing_eml_result.ok and any("PEC_UFFICIO_EML_REQUIRED" in item for item in missing_eml_result.blockers),
            "; ".join(missing_eml_result.blockers[:2]),
        )
    )
    client = _base_payload()
    client["ruolo_destinatario"] = "cliente"
    client_result = validate_legal_notification(client)
    results.append(
        _record(
            "Blocco cliente nel percorso notifica",
            not client_result.ok and any("CLIENTE_NON_NOTIFICA" in item for item in client_result.blockers),
            "; ".join(client_result.blockers[:2]),
        )
    )
    return results


def _run_full_case_recipient_delivery_matrix() -> list[dict[str, Any]]:
    runtime_dir = RUNTIME_ROOT / "casistiche-complete"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for case in notification_directive_matrix()["cases"]:
        case_id = case["value"]
        allowed_roles = [item for item in (case.get("allowedRecipientRoles") or []) if item]
        for role in allowed_roles:
            payload = _case_payload(case_id, case)
            _apply_role(payload, role)
            payload["fonte_pec_destinatario"] = next(
                (
                    item.get("allowedRegisters", ["altro_pubblico_elenco"])[0]
                    for item in notification_directive_matrix()["roles"]
                    if item["value"] == role and item.get("allowedRegisters")
                ),
                payload.get("fonte_pec_destinatario") or "altro_pubblico_elenco",
            )
            evidence = _simulate_complete_delivery_and_deposit(
                payload=payload,
                case_id=case_id,
                role=role,
                runtime_dir=runtime_dir,
            )
            results.append(
                _record(
                    f"Flusso completo: {case['label']} verso {role}",
                    bool(evidence["ok"]),
                    evidence["detail"],
                    {
                        "caseId": case_id,
                        "role": role,
                        "templateId": evidence.get("templateId", ""),
                        "pecFiles": evidence.get("pecFiles", []),
                        "relataSha256": evidence.get("relataSha256", ""),
                    },
                )
            )
    invalid_checks = [item for item in _run_matrix_cases() if item["name"].startswith("Blocco")]
    results.extend(invalid_checks)
    return results


def _demo_fascicolo(documenti: list[Any] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id="fasc-demo-relata",
        numero="2026/001",
        titolo="Cliente S.r.l. / Controparte S.p.A.",
        tribunale="Tribunale di Roma",
        numero_rg="1234",
        anno_rg="2026",
        documenti=documenti or [],
        depositi_pct=[
            SimpleNamespace(
                id="dep-portal-1",
                id_deposito_esterno="PST-REL-2026-0001",
                fonte="PST",
                servizio_portale="ConsultazioneFascicolo",
                tipo_atto="Ordinanza da notificare",
                documenti_portale=[
                    {
                        "id_documento": "pst-doc-ordinanza",
                        "nome": "ordinanza_da_notificare.pdf",
                        "tipo": "Ordinanza da notificare",
                    }
                ],
            )
        ],
    )


def _demo_pec() -> SimpleNamespace:
    return SimpleNamespace(
        id="pec-cancelleria-1234",
        mittente="cancelleria.tribunale.roma@giustiziacert.it",
        oggetto="Tribunale di Roma R.G. 1234/2026 - provvedimento da notificare",
        data="2026-05-23T10:15:00",
        corpo_testo="Si comunica il provvedimento ordinanza_da_notificare.pdf da notificare nel procedimento R.G. 1234/2026.",
        allegati=[{"nome": "ordinanza_da_notificare.pdf", "sha256": "c" * 64}],
        message_id="<pec-cancelleria-1234@giustizia>",
    )


def _run_office_pec_flow() -> list[dict[str, Any]]:
    fascicolo = _demo_fascicolo()
    portal_only = released_office_documents_from_pec(fascicolo, [])
    pec = _demo_pec()
    pending = released_office_documents_from_pec(fascicolo, [pec])
    href = pending[0].get("acquisitionHref", "") if pending else ""
    local_doc = SimpleNamespace(id="doc-local-1", nome="ordinanza_da_notificare.pdf", nome_originale="", nome_portale="", percorso="", hash_sha256="c" * 64)
    acquired_evidence = office_notification_evidence_from_pec(_demo_fascicolo([local_doc]), [pec])
    acquired_pending = released_office_documents_from_pec(_demo_fascicolo([local_doc]), [pec])
    return [
        _record(
            "Portale senza PEC non decide la notifica",
            portal_only == [],
            "Nessun provvedimento da notificare viene creato partendo solo dai metadati del portale.",
        ),
        _record(
            "PEC cancelleria genera avviso e link mirato",
            len(pending) == 1 and "single_document=1" in href and "documento=ordinanza_da_notificare.pdf" in href,
            href,
            {"release": pending[0] if pending else {}},
        ),
        _record(
            "Documento già presente non viene duplicato",
            bool(acquired_evidence and acquired_evidence[0].get("acquisito") and not acquired_pending),
            "Il documento locale con stesso nome/hash chiude la pendenza e non genera nuovo download.",
        ),
    ]


def _run_real_pec_portal_fascicolo_relata_flow() -> list[dict[str, Any]]:
    if RUNTIME_ROOT.exists():
        shutil.rmtree(RUNTIME_ROOT)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        portal_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length 91>>stream\nBT /F1 12 Tf 72 760 Td (Ordinanza da notificare - R.G. 1234/2026) Tj ET\nendstream endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF"
        )
        portal_hash = __import__("hashlib").sha256(portal_pdf).hexdigest()
        fascicoli = GestioneFascicoli(
            db_path=str(RUNTIME_ROOT / "fascicoli" / "fascicoli.json"),
            documents_dir=str(RUNTIME_ROOT / "fascicoli" / "documenti"),
            archive_dir=str(RUNTIME_ROOT / "fascicoli" / "archivio"),
        )
        fascicolo = fascicoli.nuovo(
            "Cliente S.r.l. / Controparte S.p.A. - provvedimento da notificare",
            TipoFascicolo.CIVILE,
            nome_cliente="Cliente S.r.l.",
            controparte="Controparte S.p.A.",
            tribunale="Tribunale di Roma",
            numero_rg="1234",
            anno_rg=2026,
            giudice="Dott. Verdi",
            sezione="III",
            oggetto="Opposizione a decreto ingiuntivo",
        )
        fascicoli.aggiungi_documento(
            fascicolo.id,
            "atto_gia_presente.pdf",
            TipoDocumento.ATTO_GIUDIZIARIO,
            b"%PDF-1.4\natto gia presente nel fascicolo",
            caricato_da="demo-e2e",
            fonte_documento="CARICAMENTO_STUDIO",
        )
        deposito = fascicoli.sincronizza_deposito_portale(
            fascicolo.id,
            fonte="PST",
            id_deposito_esterno="PST-DEMO-1234",
            tipo_atto="Documenti del fascicolo",
            data_deposito="2026-05-23",
            mittente="Tribunale di Roma",
            servizio_portale="ConsultazioneFascicolo",
            documenti_portale=[
                {
                    "id_documento": "pst-doc-ordinanza",
                    "nome": "ordinanza_da_notificare.pdf",
                    "tipo": "Ordinanza da notificare",
                    "data_deposito": "2026-05-23",
                    "mittente": "Tribunale di Roma",
                    "sha256": portal_hash,
                }
            ],
            registrato_da="demo-e2e",
            note="Metadati portale disponibili: non bastano per generare la relata senza PEC dell'ufficio.",
        )
        casella = GestioneEmailRicevute(str(RUNTIME_ROOT / "email" / "casella.json"))
        raw_pec = EmailMessage()
        raw_pec["From"] = "Cancelleria Tribunale di Roma <cancelleria.tribunale.roma@giustiziacert.it>"
        raw_pec["To"] = "studio.verifica@pec.example.it"
        raw_pec["Subject"] = "Tribunale di Roma R.G. 1234/2026 - provvedimento da notificare"
        raw_pec["Date"] = "Sat, 23 May 2026 10:15:00 +0200"
        raw_pec["Message-ID"] = "<pec-cancelleria-1234@giustizia>"
        raw_pec.set_content(
            "Si comunica il rilascio del provvedimento ordinanza_da_notificare.pdf "
            "da notificare nel procedimento R.G. 1234/2026."
        )
        raw_pec.add_attachment(portal_pdf, maintype="application", subtype="pdf", filename="ordinanza_da_notificare.pdf")
        raw_bytes = raw_pec.as_bytes()
        parsed_pec = message_from_bytes(raw_bytes)
        parsed_email = casella._parse_message(
            parsed_pec,
            "UID-DEMO-PEC-1",
            "INBOX",
            email_id="pec-cancelleria-1234",
            raw_bytes=raw_bytes,
        )
        if parsed_email is None:
            raise RuntimeError("Parsing PEC demo non riuscito.")
        db = casella._carica()
        db[parsed_email.id] = parsed_email
        casella._salva()
        pec_lette = casella.tutte(con_allegati=True)
        before = office_notification_evidence_from_pec(fascicoli.get(fascicolo.id), pec_lette)
        release = before[0] if before else {}
        docs_before = len(fascicoli.get(fascicolo.id).documenti)
        downloaded_name = str(release.get("nome") or "ordinanza_da_notificare.pdf")
        downloaded_bytes = portal_pdf
        doc = fascicoli.aggiungi_documento(
            fascicolo.id,
            downloaded_name,
            TipoDocumento.ORDINANZA,
            downloaded_bytes,
            note="Provvedimento scaricato dal Portale Servizi dopo PEC dell'ufficio.",
            tags=["provvedimento ufficio", "notifica richiesta", "relata notifica"],
            data_documento="2026-05-23",
            caricato_da="demo-e2e",
            fonte_documento="PORTALE_TELEMATICO",
            nome_originale=downloaded_name,
            nome_portale=downloaded_name,
            classificazione_portale="comunicazione_cancelleria",
            tipo_atto_portale="Ordinanza da notificare",
            servizio_portale="PST",
            mittente_portale="Tribunale di Roma",
            data_deposito_portale="2026-05-23",
            id_documento_portale="pst-doc-ordinanza",
        )
        fascicoli.collega_documenti_a_deposito_portale(
            fascicolo.id,
            deposito.id,
            [doc.id],
            note="File binario acquisito dal Portale Servizi dopo PEC dell'ufficio.",
            registrato_da="demo-e2e",
        )
        fascicolo_after = fascicoli.get(fascicolo.id)
        stored_bytes = (fascicoli.documents_dir / doc.percorso).read_bytes()
        after = office_notification_evidence_from_pec(fascicolo_after, pec_lette)
        pending_after = released_office_documents_from_pec(fascicolo_after, pec_lette)

        source = source_from_uploaded_document(
            tenant_id="tenant-demo",
            fascicolo_id=fascicolo.id,
            document_id=doc.id,
            filename=doc.nome,
            content=stored_bytes,
            source_type="documenti_fascicolo",
        )
        service = _MemoryAIService()
        indexer = DocumentAIIndexer(service)
        lex_result = indexer.process(tenant_id="tenant-demo", fascicolo_id=fascicolo.id, sources=[source], user_context={"user": "demo"}, retry_errors=True)
        directive = next(item for item in notification_directive_matrix()["cases"] if item["value"] == "provvedimento_giudice")
        payload = _case_payload("provvedimento_giudice", directive)
        payload["documenti"] = [
            {
                "nome_file": doc.nome,
                "descrizione": "Provvedimento scaricato dal Portale Servizi dopo PEC dell'ufficio",
                "origine": "comunicazione_cancelleria",
                "data_comunicazione_cancelleria": "2026-05-23",
                "hash_sha256": doc.hash_sha256,
                "documento_ufficio": True,
                "notifica_richiesta": True,
                "acquisito_da_portale": True,
                "fonte_documento": "PORTALE_TELEMATICO",
                "servizio_portale": "PST",
                "riferimento_portale": "pst-doc-ordinanza",
            }
        ]
        payload["pec_ufficio_eml_file"] = release.get("pecEmlFile") or getattr(pec_lette[0], "eml_file", "")
        payload["pec_ufficio_eml_sha256"] = release.get("pecEmlSha256") or getattr(pec_lette[0], "eml_sha256", "")
        payload["pec_ufficio_message_id"] = release.get("pecMessageId") or getattr(pec_lette[0], "message_id", "")
        outcome = validate_legal_notification(payload)
        completed_delivery = _simulate_complete_delivery_and_deposit(
            payload=payload,
            case_id="provvedimento_giudice_portale",
            role="controparte",
            runtime_dir=RUNTIME_ROOT / "flusso-portale-completo",
            file_contents={doc.nome: stored_bytes},
        )
        delivery_attachments = [
            str(item.get("filename") or "")
            for item in ((completed_delivery.get("delivery") or {}).get("attachments") or [])
            if isinstance(item, dict)
        ]
        docs_after = len(fascicolo_after.documenti)
        duplicate_names = [item.nome for item in fascicolo_after.documenti if item.nome == downloaded_name]
        return [
            _record(
                "Lettura reale PEC dal database casella",
                len(pec_lette) == 1 and pec_lette[0].id == "pec-cancelleria-1234" and bool(getattr(pec_lette[0], "eml_file", "")),
                "La PEC dell'ufficio è stata letta da GestioneEmailRicevute e l'EML originale è stato salvato automaticamente.",
                {"emlFile": getattr(pec_lette[0], "eml_file", ""), "emlSha256": getattr(pec_lette[0], "eml_sha256", "")},
            ),
            _record(
                "PEC abilita il provvedimento da scaricare",
                len(before) == 1 and not before[0].get("acquisito") and "single_document=1" in str(before[0].get("acquisitionHref")),
                str(before[0].get("acquisitionHref") if before else ""),
                {"evidence": before[0] if before else {}},
            ),
            _record(
                "Download portale e import nel fascicolo",
                docs_before == 1 and docs_after == 2 and doc.hash_sha256 == portal_hash,
                f"Scaricato {downloaded_name}, SHA-256 {doc.hash_sha256[:12]}..., documenti fascicolo {docs_before}->{docs_after}.",
            ),
            _record(
                "Nessun duplicato dopo acquisizione",
                len(duplicate_names) == 1 and after and after[0].get("acquisito") and not pending_after,
                "Il documento scaricato risulta collegato; la pendenza PEC si chiude e non viene richiesto un secondo download.",
            ),
            _record(
                "Lex legge il provvedimento appena acquisito",
                source.supported and lex_result.indexed == 1 and service.records and service.records[0].sha256 == portal_hash,
                f"Indice Lex salvato per {doc.nome}, file_type={source.file_type}, indexed={lex_result.indexed}.",
            ),
            _record(
                "Casistica relata determinata dopo acquisizione",
                outcome.ok and outcome.template_id == "relata_provvedimento_giudice",
                outcome.template_label if outcome.ok else "; ".join(outcome.blockers[:3]),
                {"templateId": outcome.template_id, "case": "provvedimento_giudice"},
            ),
            _record(
                "Provvedimento scaricato incluso negli allegati PEC",
                completed_delivery.get("ok") is True and downloaded_name in delivery_attachments,
                completed_delivery.get("detail", ""),
                {
                    "downloadedDocument": downloaded_name,
                    "portalSha256": portal_hash,
                    "deliveryAttachments": delivery_attachments,
                    "pecFiles": completed_delivery.get("pecFiles", []),
                },
            ),
            _record(
                "Relata, invio demo e deposito prova completati",
                completed_delivery.get("ok") is True
                and bool((completed_delivery.get("deposit") or {}).get("ok"))
                and bool(completed_delivery.get("pecFiles")),
                completed_delivery.get("detail", ""),
                {"deposit": completed_delivery.get("deposit", {})},
            ),
        ]
    finally:
        if RUNTIME_ROOT.exists():
            shutil.rmtree(RUNTIME_ROOT)


class _MemoryAIService:
    def __init__(self) -> None:
        self.records: list[DocumentAIRecord] = []

    def list_fascicolo_documents(self, tenant_id: str, fascicolo_id: str, user_context: object) -> list[DocumentAIRecord]:
        return list(self.records)

    def upload_document_bytes_for_fascicolo(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        filename: str,
        content: bytes,
        mime_type: str | None,
        user_context: object,
        source_metadata: dict[str, Any] | None = None,
    ) -> DocumentAIRecord:
        source = source_from_uploaded_document(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            document_id=filename,
            filename=filename,
            content=content,
            mime_type=mime_type,
        )
        existing = next((record for record in self.records if record.sha256 == source.sha256), None)
        if existing:
            return existing
        record = DocumentAIRecord(
            id=f"doc-ai-{len(self.records) + 1}",
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            original_filename=filename,
            safe_filename=source.safe_filename,
            file_type=source.file_type,
            mime_type=source.mime_type,
            size_bytes=source.size_bytes,
            sha256=source.sha256,
            status="ready",
            current_version_id=f"ver-{len(self.records) + 1}",
            page_count=1,
            created_by="demo",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.records.append(record)
        return record


def _run_lex_flow() -> list[dict[str, Any]]:
    content = b"%PDF-1.4\nprovvedimento firmato"
    source = source_from_uploaded_document(
        tenant_id="tenant-demo",
        fascicolo_id="fasc-demo-relata",
        document_id="doc-p7m",
        filename="Documento_33584995.pdf.p7m",
        content=content,
        source_type="documenti_fascicolo",
    )
    service = _MemoryAIService()
    indexer = DocumentAIIndexer(service)
    first = indexer.process(tenant_id="tenant-demo", fascicolo_id="fasc-demo-relata", sources=[source], user_context={"user": "demo"}, retry_errors=True)
    second = indexer.process(tenant_id="tenant-demo", fascicolo_id="fasc-demo-relata", sources=[source], user_context={"user": "demo"}, retry_errors=True)
    old_error = DocumentAIRecord(
        id="old-error",
        tenant_id="tenant-demo",
        fascicolo_id="fasc-demo-relata",
        original_filename=source.filename,
        safe_filename=source.safe_filename,
        file_type=source.file_type,
        mime_type=source.mime_type,
        size_bytes=source.size_bytes,
        sha256=source.sha256,
        status="error",
        current_version_id="old-ver",
        page_count=None,
        created_by="demo",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    summary = build_lex_indexing_summary(sources=[source], records=[old_error, *service.records])
    return [
        _record(
            "Lex legge .pdf.p7m come PDF indicizzabile",
            source.supported and source.file_type == "pdf",
            f"file_type={source.file_type}, safe_filename={source.safe_filename}",
        ),
        _record(
            "Indicizzazione automatica una sola volta",
            first.indexed == 1 and second.indexed == 0 and second.skipped == 1 and len(service.records) == 1,
            f"prima indicizzati={first.indexed}; seconda indicizzati={second.indexed}, saltati={second.skipped}",
        ),
        _record(
            "Indice pronto prevale su vecchio errore stesso hash",
            summary.ready == 1 and summary.errors == 0 and summary.warnings == [],
            f"ready={summary.ready}, errors={summary.errors}, warnings={len(summary.warnings)}",
        ),
    ]


def _run_pagination_guard() -> list[dict[str, Any]]:
    source = (REPO_ROOT / "frontend" / "src" / "components" / "FascicoliPage.tsx").read_text(encoding="utf-8")
    ok = all(token in source for token in ("Prima", "Precedente", "Pagina", "Successiva", "Ultima", "pageNumbers"))
    return [_record("Lista fascicoli con pagine ulteriori visibili", ok, "Controlli Prima/Precedente/pagine/Successiva/Ultima presenti nella tabella React.")]


def _run_pst_area_web_and_timing() -> list[dict[str, Any]]:
    failed_payload = {
        "pec_non_consegnata": True,
        "causa_imputabile_destinatario": True,
        "valutazione_avvocato": "Casella PEC satura da avviso di mancata consegna.",
        "avviso_mancata_consegna": "mancata-consegna.eml",
        "atto_notificato": "atto.pdf",
        "atto_notificato_sha256": "a" * 64,
        "relata_firmata": "relata_notifica.pdf.p7m",
        "relata_sha256": "b" * 64,
        "pec_inviata": "notifica-inviata.eml",
        "pec_inviata_sha256": "c" * 64,
        "rac_file": "rac.eml",
        "rac_sha256": "d" * 64,
        "rdac_file": "rdac-completa.eml",
        "rdac_sha256": "e" * 64,
    }
    failed = prepare_pst_failed_notification_workflow(failed_payload)
    evening = build_notification_timing_plan({"data_ora_invio_pec": "2026-05-24T21:30"})
    night = build_notification_timing_plan({"data_ora_invio_pec": "2026-05-24T06:30"})
    return [
        _record(
            "Area web PST ex art. 3-ter con avviso EML",
            failed.ok and failed.output_plan["legalBasis"][0]["id"] == "l53_art3ter",
            "Workflow predisposto con atto/PEC, relata firmata, avviso di mancata consegna EML, RAC/RdAC e certificazione PST.",
            failed.output_plan,
        ),
        _record(
            "Orario PEC: scissione 21:00-24:00 e blocco notturno",
            evening["ready"] is True and evening["status"] == "fascia_serale_con_scissione" and night["ready"] is False,
            f"Serale={evening['status']} notificante={evening['senderEffect']}; notturno={night['status']}.",
            {"evening": evening, "night": night},
        ),
    ]


def _table(rows: list[list[str]], widths: list[int], styles: Any) -> Table:
    data = [[Paragraph(escape(cell), styles["Small"]) for cell in row] for row in rows]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173a67")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8dee9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fbfcfe")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _write_pdf(report: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8.2, leading=10.5))
    styles.add(ParagraphStyle(name="Muted", parent=styles["BodyText"], fontSize=9, leading=12, textColor=colors.HexColor("#526173")))
    story = [
        Paragraph("Relata notifica: test demo end-to-end", styles["Title"]),
        Paragraph(f"Generato il {_italian_generated_at(report['generatedAt'])}. Ambiente demo: nessun invio PEC reale e nessun accesso a portali esterni.", styles["Muted"]),
        Spacer(1, 10),
        Paragraph("Comportamento implementato", styles["Heading2"]),
        Paragraph(
            "La PEC dell'ufficio è il segnale che abilita il flusso: IUSENTRA avvisa l'avvocato, genera un link al Portale Servizi già compilato con fascicolo, R.G., ufficio e documento, scarica/importa solo quel provvedimento con assistenza dell'avvocato e blocca la relata finché il documento non è nei Documenti e atti. Gli atti già presenti non vengono duplicati. Il test copre anche firma della sola relata, RAC/RdAC complete, DatiAtto.xml, area web PST ex art. 3-ter e controllo orario PEC.",
            styles["BodyText"],
        ),
    ]
    for section in report["sections"]:
        story.extend([Spacer(1, 10), Paragraph(section["title"], styles["Heading2"])])
        rows = [["Esito", "Caso", "Dettaglio"]]
        rows.extend([["OK" if item["ok"] else "KO", item["name"], item["detail"][:420]] for item in section["results"]])
        story.append(_table(rows, [38, 170, 315], styles))
    story.extend(
        [
            Spacer(1, 10),
            Paragraph("File prodotti", styles["Heading2"]),
            Paragraph(f"Report JSON: {JSON_REPORT}", styles["Small"]),
            Paragraph(f"Report PDF: {PDF_REPORT}", styles["Small"]),
        ]
    )
    doc = SimpleDocTemplate(str(PDF_REPORT), pagesize=A4, rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
    doc.build(story)


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    sections = [
        {"title": "Matrice casi e destinatari", "results": _run_matrix_cases()},
        {"title": "Flusso reale PEC, portale, fascicolo e relata", "results": _run_real_pec_portal_fascicolo_relata_flow()},
        {"title": "Casistiche complete: relata, allegati, invio e deposito prova", "results": _run_full_case_recipient_delivery_matrix()},
        {"title": "Area web PST e orari PEC", "results": _run_pst_area_web_and_timing()},
        {"title": "PEC ufficio e acquisizione mirata", "results": _run_office_pec_flow()},
        {"title": "Indicizzazione Lex .pdf.p7m", "results": _run_lex_flow()},
        {"title": "Paginazione fascicoli", "results": _run_pagination_guard()},
    ]
    all_results = [item for section in sections for item in section["results"]]
    report = {
        "generatedAt": _now(),
        "ok": all(item["ok"] for item in all_results),
        "summary": {
            "total": len(all_results),
            "passed": sum(1 for item in all_results if item["ok"]),
            "failed": sum(1 for item in all_results if not item["ok"]),
        },
        "sections": sections,
        "artifacts": {"json": str(JSON_REPORT), "pdf": str(PDF_REPORT)},
        "directiveMatrix": notification_directive_matrix(),
    }
    JSON_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_pdf(report)
    print(json.dumps({"ok": report["ok"], **report["summary"], "json": str(JSON_REPORT), "pdf": str(PDF_REPORT)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
