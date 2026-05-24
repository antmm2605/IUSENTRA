from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.notifiche_legali import (
    LEGAL_NOTIFICATION_SUBJECT,
    legal_notification_automation_payload,
    validate_deposit_notification_proof,
    validate_legal_notification,
)


ARTIFACT_DIR = Path("artifacts") / "notifiche-legali"
JSON_REPORT = ARTIFACT_DIR / "notifica-l53-demo-audit.json"
MARKDOWN_REPORT = ARTIFACT_DIR / "notifica-l53-demo-audit.md"
PDF_REPORT = ARTIFACT_DIR / "notifica-l53-demo-guida-avvocato.pdf"


def _demo_notification_payload() -> dict[str, Any]:
    return {
        "operazione": "notifica_pec_l53",
        "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT,
        "avvocato_nome": "Mario Rossi",
        "avvocato_cf": "RSSMRA80A01H501U",
        "avvocato_foro": "Roma",
        "studio_indirizzo": "Via Roma 1",
        "studio_citta": "Roma",
        "luogo": "Roma",
        "data_relata": "2026-05-23",
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
        "destinatario_pec": "controparte@example.pec.it",
        "fonte_pec_destinatario": "registro_imprese",
        "destinatario_pec_pubblico_elenco": True,
        "data_verifica_pec": "2026-05-23T10:30",
        "procedimento_pendente": True,
        "ufficio_giudiziario": "Tribunale di Roma",
        "sezione": "III",
        "numero_rg": "1234",
        "anno_rg": "2026",
        "ricevuta_completa": True,
        "relata_firmata": True,
        "relata_documento_separato": True,
        "approvazione_avvocato": True,
        "attestazione_multipla": True,
        "documento_ufficio_rilasciato": True,
        "acquisizione_portale_richiesta": True,
        "documento_ufficio_acquisito": True,
        "acquisizione_portale_completata": True,
        "pec_ufficio_rilascio": True,
        "pec_ufficio_eml_file": "pec-cancelleria-rilascio.eml",
        "pec_ufficio_eml_sha256": "9" * 64,
        "pec_ufficio_message_id": "<pec-cancelleria-rilascio@giustizia>",
        "portale_servizi": "PST",
        "portale_acquisizione_href": "/portali/pst/acquisizione?id_fasc=DEMO-L53&numero=1234&anno=2026&ufficio=Tribunale%20di%20Roma&focus=documenti#acquisizione-portale",
        "documenti": [
            {
                "nome_file": "ricorso.pdf",
                "descrizione": "Ricorso introduttivo",
                "origine": "nativo_digitale",
                "hash_sha256": "a" * 64,
            },
            {
                "nome_file": "procura.pdf.p7m",
                "descrizione": "Procura alle liti firmata",
                "origine": "firmato_digitalmente",
                "hash_sha256": "b" * 64,
            },
            {
                "nome_file": "ordinanza_da_notificare.pdf",
                "descrizione": "Ordinanza rilasciata dall'ufficio e acquisita dal Portale Servizi",
                "origine": "copia_fascicolo_informatico",
                "hash_sha256": "c" * 64,
                "fonte_documento": "PORTALE_TELEMATICO",
                "servizio_portale": "PST",
                "riferimento_portale": "PST-REL-2026-0001",
                "documento_ufficio": True,
                "acquisito_da_portale": True,
                "notifica_richiesta": True,
                "data_rilascio_portale": "2026-05-23",
            },
        ],
    }


def _demo_deposit_payload() -> dict[str, Any]:
    return {
        "atti_notificati": [
            {"nome_file": "ricorso.pdf", "hash_sha256": "a" * 64},
            {"nome_file": "procura.pdf.p7m", "hash_sha256": "b" * 64},
            {"nome_file": "ordinanza_da_notificare.pdf", "hash_sha256": "c" * 64},
        ],
        "relata_firmata": "relata_notifica.pdf.p7m",
        "relata_sha256": "d" * 64,
        "pec_inviata": "pec_inviata.eml",
        "pec_inviata_sha256": "e" * 64,
        "destinatario_nome": "Controparte S.p.A.",
        "rac_file": "accettazione.eml",
        "rac_sha256": "f" * 64,
        "rdac_file": "consegna_completa.eml",
        "rdac_sha256": "1" * 64,
        "ricevuta_completa": True,
        "dati_atto_ricevute": "RAC accettazione.eml e RdAC completa consegna_completa.eml associate al destinatario Controparte S.p.A.",
    }


def _status_rows(checks: list[dict[str, Any]]) -> str:
    rows = []
    for item in checks:
        rows.append(f"- {item['label']}: {item['status']} ({item['source']})")
    return "\n".join(rows)


def _step_rows(steps: list[dict[str, Any]]) -> str:
    rows = []
    for index, item in enumerate(steps, start=1):
        rows.append(f"{index}. {item['title']} - {item['body']} [{item['source']}]")
    return "\n".join(rows)


def _pdf_list(items: list[str], styles):
    return ListFlowable(
        [ListItem(Paragraph(item, styles["BodyText"])) for item in items if item],
        bulletType="bullet",
        leftIndent=16,
    )


def _write_pdf(report: dict[str, Any]) -> None:
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Guida digitale avvocato: notifica L. 53/1994 con documento d'ufficio", styles["Title"]),
        Spacer(1, 10),
        Paragraph("Scenario demo: nessun invio PEC reale, nessun deposito reale e nessun accesso automatico non autorizzato ai portali. Il software prepara il collegamento al Portale Servizi, registra il rilascio, richiede acquisizione e produce relata, controlli e audit prima della revisione dell'avvocato.", styles["BodyText"]),
        Spacer(1, 12),
        Paragraph("Sequenza automatizzata", styles["Heading2"]),
        _pdf_list([f"{item['title']}: {item['body']}" for item in report["notification"]["outputPlan"].get("workflowSteps", [])], styles),
        Spacer(1, 8),
        Paragraph("Controlli normativi notifica", styles["Heading2"]),
        _pdf_list([f"{item['label']}: {item['status']} ({item['source']})" for item in report["notification"]["outputPlan"].get("normativeChecks", [])], styles),
        Spacer(1, 8),
        Paragraph("Acquisizione Portale Servizi", styles["Heading2"]),
        _pdf_list([
            "Rilascio documento d'ufficio rilevato dal monitor del fascicolo.",
            "Notifica di sistema generata con collegamento precompilato a fascicolo, numero RG e ufficio giudiziario.",
            "Accesso al portale demandato all'avvocato con CNS/CIE/SPID o altro mezzo ammesso: il software non conserva PIN o credenziali.",
            "Documento importato nel fascicolo e marcato come acquisito da portale prima della generazione della relata.",
        ], styles),
        Spacer(1, 8),
        Paragraph("Deposito prova", styles["Heading2"]),
        _pdf_list([f"{item['title']}: {item['body']}" for item in report["deposit"]["outputPlan"].get("workflowSteps", [])], styles),
        Spacer(1, 8),
        Paragraph("Audit prodotto dalla demo", styles["Heading2"]),
        _pdf_list([
            f"Esito notifica: {'superato' if report['notification']['ok'] else 'da completare'}",
            f"Esito deposito prova: {'superato' if report['deposit']['ok'] else 'da completare'}",
            f"Allegati controllati: {report['notification']['outputPlan'].get('auditTrail', {}).get('documentsCount', 0)}",
            f"File prova previsti: {len(report['deposit']['outputPlan'].get('evidencePack', {}).get('items', []))}",
        ], styles),
        Spacer(1, 8),
        Paragraph("Fonti operative consultate", styles["Heading2"]),
        _pdf_list(report["officialSources"], styles),
    ]
    doc = SimpleDocTemplate(str(PDF_REPORT), pagesize=A4, title="Guida digitale notifiche legali IUSENTRA")
    doc.build(story)


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    notification = validate_legal_notification(_demo_notification_payload())
    deposit = validate_deposit_notification_proof(_demo_deposit_payload())
    payload = {
        "generatedAt": generated_at,
        "scenario": "Demo controllata: nessun invio PEC reale e nessun accesso a portali esterni.",
        "automation": legal_notification_automation_payload(),
        "notification": notification.to_dict(),
        "deposit": deposit.to_dict(),
        "artifacts": {
            "json": str(JSON_REPORT),
            "markdown": str(MARKDOWN_REPORT),
            "pdf": str(PDF_REPORT),
        },
        "officialSources": [
            "Portale Servizi Telematici, scheda Notifiche in proprio degli avvocati: https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC432&modelId=12",
            "L. 53/1994, art. 3-bis e art. 9; D.L. 179/2012, art. 16-ter; D.M. 44/2011 e specifiche tecniche art. 18 e 19-bis.",
        ],
    }
    JSON_REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    notification_plan = notification.output_plan or {}
    deposit_plan = deposit.output_plan or {}
    markdown = "\n".join([
        "# Demo notifiche legali L. 53/1994",
        "",
        f"Generato il {generated_at}.",
        "",
        "Scenario: demo controllata, nessun invio PEC reale e nessun deposito su portali esterni.",
        "",
        "## Passaggi notifica",
        _step_rows(notification_plan.get("workflowSteps", [])),
        "",
        "## Verifiche notifica",
        _status_rows(notification_plan.get("normativeChecks", [])),
        "",
        "## Audit notifica",
        f"- Esito: {'superato' if notification.ok else 'da completare'}",
        f"- Allegati controllati: {notification_plan.get('auditTrail', {}).get('documentsCount', 0)}",
        f"- Acquisizione documento ufficio: {notification_plan.get('auditTrail', {}).get('officeDocumentAcquisition', {}).get('acquired', False)}",
        f"- Cartella prova prevista: {notification_plan.get('folder', '')}",
        "",
        "## Acquisizione Portale Servizi",
        "- Il monitor fascicolo rileva il documento d'ufficio rilasciato.",
        "- La notifica di sistema apre il collegamento precompilato con fascicolo, numero RG e ufficio.",
        "- L'avvocato accede con credenziali personali e scarica/importa il documento.",
        "- Il documento acquisito viene inserito nei documenti della relata ed è tracciato nell'audit.",
        "",
        "## Passaggi deposito prova",
        _step_rows(deposit_plan.get("workflowSteps", [])),
        "",
        "## Verifiche deposito prova",
        _status_rows(deposit_plan.get("normativeChecks", [])),
        "",
        "## Audit deposito prova",
        f"- Esito: {'superato' if deposit.ok else 'da completare'}",
        f"- File pacchetto prova: {len(deposit_plan.get('evidencePack', {}).get('items', []))}",
        f"- Anomalie: {len(deposit.blockers)} blocchi, {len(deposit.warnings)} avvisi",
        "",
        "## Fonti normative operative",
        "- Portale Servizi Telematici, Notifiche in proprio degli avvocati: https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC432&modelId=12",
        "- L. 53/1994, art. 3-bis e art. 9; D.L. 179/2012, art. 16-ter; D.M. 44/2011 e specifiche tecniche art. 18 e 19-bis.",
        "",
    ])
    MARKDOWN_REPORT.write_text(markdown, encoding="utf-8")
    _write_pdf(payload)
    print(f"Demo notifiche legali generato: {MARKDOWN_REPORT}, {JSON_REPORT} e {PDF_REPORT}")
    return 0 if notification.ok and deposit.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
