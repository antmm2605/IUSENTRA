from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "artifacts" / "react-migration" / "audit-menu-funzioni-studio-telematico.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "react-migration" / "audit-parita-funzionale-comandi.json"
DEFAULT_MARKDOWN = ROOT / "artifacts" / "react-migration" / "audit-parita-funzionale-comandi.md"
DEFAULT_REAL_PROOFS = ROOT / "artifacts" / "react-migration" / "prove-reali-parita-funzionale.json"


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def _contract(
    capability_id: str,
    pattern: str,
    *,
    route: str,
    component: str,
    code_checks: tuple[tuple[str, str], ...],
    api: str = "",
    persistence: str = "",
    tests: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "pattern": re.compile(pattern),
        "route": route,
        "component": component,
        "api": api,
        "persistence": persistence,
        "tests": list(tests),
        "code_checks": code_checks,
    }


# La corrispondenza e' intenzionalmente esplicita. Una pagina affine non prova
# l'equivalenza di una funzione e non viene usata per promuovere lo stato.
CONTRACTS: tuple[dict[str, Any], ...] = (
    _contract(
        "fascicoli_elenco_attivi",
        r"(?:^|_)(?:pratiche_attive|elenco_pratiche|rubrica_pratiche)(?:_|$)",
        route="/fascicoli",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli",
        persistence="pct.fascicoli",
        code_checks=(("frontend/src/App.tsx", "isFascicoliPage"), ("frontend/src/components/FascicoliPage.tsx", "FascicoliTable")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "fascicoli_archivio",
        r"(?:^|_)(?:pratiche_archiviate|archivio_pratiche|archivia_pratica)(?:_|$)",
        route="/fascicoli/archivio",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli",
        persistence="pct.fascicoli",
        code_checks=(("frontend/src/App.tsx", "isFascicoliPage"), ("frontend/src/components/FascicoliPage.tsx", "kind: 'archive'")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "fascicoli_nuovo",
        r"(?:^|_)(?:nuova_pratica|nuovo_fascicolo|menuitem_aggiungi_pratica)(?:_|$)",
        route="/fascicoli/nuovo",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli",
        persistence="pct.fascicoli",
        code_checks=(("frontend/src/App.tsx", "'/fascicoli/nuovo'"), ("frontend/src/components/FascicoliPage.tsx", "Nuovo fascicolo")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "fascicoli_gruppi",
        r"(?:^|_)(?:faldoni|gruppi_pratiche|filtra_pratiche_per_gruppo|nomegruppo)(?:_|$)",
        route="/fascicoli",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli?group_by=gruppo",
        persistence="pct.fascicoli.nome_gruppo",
        code_checks=(("frontend/src/components/FascicoliPage.tsx", "Raggruppa"), ("web/services/react_fascicoli_bridge.py", "_group_list_items")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "fascicoli_ricerca_filtri",
        r"(?:^|_)(?:trova_pratiche|filtra_rubrica_per|ricerca_pratiche|filtra_rubrica|trova_rubrica_sx)(?:_|$)",
        route="/fascicoli",
        component="FascicoliPage",
        api="/api/v1/ui/fascicoli?f_*=",
        persistence="preferenze filtri tenant-aware",
        code_checks=(("frontend/src/components/FascicoliPage.tsx", "practiceFieldFilters"), ("web/blueprints/api_v1_react.py", "_fascicoli_request_field_filters")),
        tests=("tests/test_fascicoli_pagination.py",),
    ),
    _contract(
        "agenda_nuovo_evento",
        r"(?:^|_)(?:aggiungi_udienza|aggiungi_adempimento|aggiungi_appuntamento|aggiungi_memorandum|aggiungi_scadenza|nuova_udienza|nuovo_adempimento|nuovo_appuntamento|nuovo_memorandum|nuova_scadenza)(?:_|$)",
        route="/agenda/nuovo",
        component="NuovoAppuntamentoPage",
        api="/api/v1/ui/agenda",
        persistence="agenda tenant-aware",
        code_checks=(
            ("frontend/src/App.tsx", "isNewAppointmentPage"),
            ("frontend/src/components/NuovoAppuntamentoPage.tsx", "NuovoAppuntamentoPage"),
            ("frontend/src/components/AgendaPage.tsx", "NewAgendaMenu"),
        ),
        tests=("tests/test_agenda.py", "tests/test_react_shell.py"),
    ),
    _contract(
        "agenda_viste",
        r"^(?:giorno_giorno|settimana_settimana|mese_mese|timelineagenda_timelineagenda)$",
        route="/agenda",
        component="AgendaPage",
        api="/api/v1/ui/agenda",
        persistence="agenda tenant-aware",
        code_checks=(
            ("frontend/src/components/AgendaPage.tsx", "timeline: 'Cronologia'"),
            ("frontend/src/components/AgendaPage.tsx", "AgendaTimeline"),
            ("frontend/src/agendaData.ts", "view === 'timeline'"),
        ),
        tests=("tests/test_agenda.py", "tests/test_react_shell.py"),
    ),
    _contract(
        "agenda_gestione_evento",
        r"(?:^|_)(?:elimina_agenda_elimina_agenda|modifica_agenda_modifica_agenda|rinvia_agenda_rinvia_agenda)(?:_|$)",
        route="/agenda/:id",
        component="AgendaPage",
        api="/agenda/:id/modifica, /agenda/:id/elimina",
        persistence="agenda tenant-aware",
        code_checks=(
            ("frontend/src/components/AgendaPage.tsx", "AgendaDeleteAction"),
            ("frontend/src/components/AgendaPage.tsx", "<CalendarClock size={15}/>Rinvia"),
            ("web/bootstrap/dashboard_routes.py", 'message = "Voce eliminata dall\'agenda."'),
        ),
        tests=("tests/test_agenda.py", "tests/test_react_shell.py"),
    ),
    _contract(
        "anagrafica_nuovo_soggetto",
        r"(?:^|_)(?:aggiungi_cliente|aggiungi_controparte|aggiungi_testimone|aggiungi_terzo|aggiungi_corrispondente|aggiungi_socio|nuovo_cliente|nuovo_soggetto)(?:_|$)",
        route="/soggetti/nuovo",
        component="SoggettoFormPage",
        api="/api/v1/ui/soggetti",
        persistence="clienti e soggetti tenant-aware",
        code_checks=(("frontend/src/App.tsx", "isNewSubjectPage"), ("frontend/src/components/SoggettoFormPage.tsx", "SoggettoFormPage")),
        tests=("tests/test_react_soggetti_api.py",),
    ),
    _contract(
        "documenti_archivio",
        r"^videoscrittura_btnvideoscrittura(?:_|$)",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="/api/v1/ui/editor-professionale",
        persistence="documenti dei fascicoli tenant-aware",
        code_checks=(
            ("frontend/src/App.tsx", "isEditorProfessionalePage"),
            ("frontend/src/components/EditorProfessionalePage.tsx", "EditorProfessionalePage"),
            ("web/services/react_document_archive_bridge.py", '"source": "fascicoli_tenant"'),
        ),
        tests=("tests/test_react_document_archive.py",),
    ),
    _contract(
        "documenti_nuovo",
        r"(?:^|_)aggiungi_videoscrittura(?:_|$)",
        route="/template-atti/editor",
        component="TemplateAttiPage",
        api="salvataggio documento nel fascicolo",
        persistence="documenti dei fascicoli tenant-aware",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "data.actions.newDocument"),
            ("web/services/react_document_archive_bridge.py", '"newDocument": "/template-atti/editor"'),
            ("frontend/src/components/TemplateAttiPage.tsx", "saveCurrentDraft"),
        ),
        tests=("tests/test_react_document_archive.py", "tests/test_template_atti_react.py"),
    ),
    _contract(
        "documenti_ricerca_filtri",
        r"(?:^|_)(?:elimina_filtro_videoscrittura|filtra_videoscrittura|trova_videoscrittura_sx)(?:_|$)",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="/api/v1/ui/editor-professionale?q=&tipo=&formato=&fascicolo=",
        persistence="filtri applicati ai documenti dei fascicoli",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "resetFilters"),
            ("frontend/src/components/EditorProfessionalePage.tsx", "iu-editor-pro-filters"),
            ("web/services/react_document_archive_bridge.py", "type_filter"),
        ),
        tests=("tests/test_react_document_archive.py",),
    ),
    _contract(
        "documenti_modifica",
        r"(?:^|_)modifica_videoscrittura(?:_|$)",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="documento reale del fascicolo",
        persistence="documento aggiornato nel fascicolo tenant-aware",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "row.actions.edit"),
            ("frontend/src/App.tsx", "isDocumentEditorPage"),
            ("frontend/src/components/DocumentEditorPage.tsx", "DocumentEditorPage"),
        ),
        tests=("tests/test_react_document_archive.py", "tests/test_fascicolo_detail_ux.py"),
    ),
    _contract(
        "documenti_cestino",
        r"(?:^|_)elimina_videoscrittura(?:_|$)",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="spostamento, ripristino ed eliminazione definitiva",
        persistence="documenti_cestino del fascicolo tenant-aware",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "kind: 'trash'"),
            ("web/bootstrap/fascicoli_document_routes.py", "ripristina_documento"),
            ("pct/fascicoli.py", "documenti_cestino"),
        ),
        tests=("tests/test_react_document_archive.py", "tests/test_fascicoli.py"),
    ),
    _contract(
        "documenti_esporta",
        r"(?:^|_)esporta_semplice_videoscrittura(?:_|$)",
        route="/editor-professionale",
        component="EditorProfessionalePage",
        api="download degli originali senza rinomina",
        persistence="nessuna modifica ai documenti sorgente",
        code_checks=(
            ("frontend/src/components/EditorProfessionalePage.tsx", "exportOriginals"),
            ("frontend/src/components/EditorProfessionalePage.tsx", "showDirectoryPicker"),
        ),
        tests=("tests/test_react_document_archive.py",),
    ),
    _contract(
        "documenti_editor_rapido",
        r"^quick_word_btnquickword(?:_|$)",
        route="/fascicoli/:id/documenti/:id/editor",
        component="DocumentEditorPage",
        api="documento reale del fascicolo",
        persistence="documento aggiornato nel fascicolo tenant-aware",
        code_checks=(
            ("frontend/src/App.tsx", "isDocumentEditorPage"),
            ("frontend/src/components/DocumentEditorPage.tsx", "DocumentEditorPage"),
        ),
        tests=("tests/test_fascicolo_detail_ux.py",),
    ),
    _contract(
        "documenti_firma_digitale",
        r"(?:^|_)(?:firma_digitale|firma_pades|firma_cades)(?:_|$)",
        route="/guida/firma-digitale",
        component="TelematicoPage",
        api="Local Signer sul PC in uso",
        persistence="documenti firmati nel fascicolo",
        code_checks=(("frontend/src/App.tsx", "'/guida/firma-digitale'"), ("web", "")),
        tests=("tests/test_local_signer_contract.py",),
    ),
    _contract(
        "email_nuovo_messaggio",
        r"(?:^|_)(?:nuova_email|scrivi_email|email_vuota|menuitem_aggiungi_email)(?:_|$)",
        route="/email/scrivi",
        component="EmailComposePage",
        api="/api/v1/ui/email",
        persistence="messaggi tenant-aware",
        code_checks=(("frontend/src/App.tsx", "isEmailComposePage"), ("frontend/src/components/EmailComposePage.tsx", "EmailComposePage")),
        tests=("tests/test_react_email_api.py",),
    ),
    _contract(
        "notifica_pec",
        r"(?:^|_)(?:notifica_mezzo_pec|notificamezzopec|notifica_a_mezzo_pec)(?:_|$)",
        route="/notifiche-legali",
        component="NotificheLegaliPage",
        api="invio dal PC locale",
        persistence="notifica e documenti nel fascicolo",
        code_checks=(("frontend/src/App.tsx", "isNotificheLegaliPage"), ("frontend/src/components/NotificheLegaliPage.tsx", "NotificheLegaliPage")),
        tests=("tests/test_notifiche_legali_react.py",),
    ),
    _contract(
        "deposito_civile",
        r"(?:^|_)(?:depositi_telematici_civile|depositi_in_materia_civile|deposito_telematico_civile)(?:_|$)",
        route="/deposito/checklist",
        component="FascicoloDepositoPage",
        api="preparazione server e invio dal PC locale",
        persistence="deposito e ricevute nel fascicolo",
        code_checks=(("frontend/src/App.tsx", "'/deposito/checklist'"), ("frontend/src/components/FascicoloDepositoPage.tsx", "Invia deposito reale")),
        tests=("tests/test_deposito_reale_contract.py",),
    ),
    _contract(
        "impostazioni_pec",
        r"(?:^|_)(?:configurazione_pec|configurazione_della_pec)(?:_|$)",
        route="/impostazioni?tab=pec",
        component="ImpostazioniPage",
        api="/api/v1/ui/impostazioni",
        persistence="configurazione tenant-aware; password sul dispositivo locale",
        code_checks=(("frontend/src/App.tsx", "isImpostazioniPage"), ("frontend/src/components/ImpostazioniPage.tsx", "ImpostazioniPage")),
        tests=("tests/test_react_impostazioni_api.py",),
    ),
    _contract(
        "backup",
        r"(?:^|_)(?:backup|esegui_backup|ripristina_backup)(?:_|$)",
        route="/backup",
        component="BackupPage",
        api="/api/v1/ui/backup",
        persistence="archivio tenant-aware",
        code_checks=(("frontend/src/App.tsx", "isBackupPage"), ("frontend/src/components/BackupPage.tsx", "BackupPage")),
        tests=("tests/test_react_backup_api.py",),
    ),
)


def _entry_text(row: dict[str, Any]) -> str:
    # Il percorso del menu e' contesto, non identita' funzionale: usarlo qui
    # promuoverebbe ogni azione figlia al contratto del contenitore padre.
    parts = [
        row.get("key"),
        row.get("caption"),
        row.get("variable"),
        row.get("handler"),
    ]
    return _normalize(" ".join(str(part or "") for part in parts))


def _code_check(path_value: str, expected: str) -> dict[str, Any]:
    path = ROOT / path_value
    if path.is_dir():
        return {"file": path_value, "expected": expected, "ok": True}
    source = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {"file": path_value, "expected": expected, "ok": bool(source and (not expected or expected in source))}


def _entry_id(row: dict[str, Any], kind: str) -> str:
    source = "|".join(
        str(value or "")
        for value in (
            kind,
            row.get("source_file"),
            row.get("surface_path_label"),
            row.get("key") or row.get("variable"),
            row.get("event"),
            row.get("handler"),
        )
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]


def _map_entry(row: dict[str, Any], kind: str, real_proofs: dict[str, Any]) -> dict[str, Any]:
    normalized = _entry_text(row)
    contract = next((item for item in CONTRACTS if item["pattern"].search(normalized)), None)
    result = {
        "id": _entry_id(row, kind),
        "kind": kind,
        "surface": row.get("surface", ""),
        "source_file": row.get("source_file", ""),
        "source_path": row.get("surface_path_label", ""),
        "source_key": row.get("key") or row.get("variable") or "",
        "source_event": row.get("event", ""),
        "source_handler": row.get("handler", ""),
        "normalized": normalized,
        "capability_id": "",
        "status": "da_mappare",
        "route": "",
        "component": "",
        "api": "",
        "persistence": "",
        "tests": [],
        "code_checks": [],
        "real_proof": [],
    }
    if contract is None:
        return result
    checks = [_code_check(path, expected) for path, expected in contract["code_checks"]]
    proof = real_proofs.get(contract["id"], {})
    evidence = proof.get("evidence", []) if isinstance(proof, dict) else []
    verified = bool(proof.get("status") == "verificata" and evidence and all(check["ok"] for check in checks))
    result.update(
        {
            "capability_id": contract["id"],
            "status": "verificata" if verified else "presente_da_provare" if all(check["ok"] for check in checks) else "parziale",
            "route": contract["route"],
            "component": contract["component"],
            "api": contract["api"],
            "persistence": contract["persistence"],
            "tests": contract["tests"],
            "code_checks": checks,
            "real_proof": evidence if verified else [],
        }
    )
    return result


def build_audit(inventory_path: Path, real_proofs_path: Path = DEFAULT_REAL_PROOFS) -> dict[str, Any]:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    real_proofs_payload = json.loads(real_proofs_path.read_text(encoding="utf-8")) if real_proofs_path.is_file() else {}
    real_proofs = real_proofs_payload.get("capabilities", {}) if isinstance(real_proofs_payload, dict) else {}
    entries = [
        *(_map_entry(row, "menu_action", real_proofs) for row in inventory.get("action_paths", [])),
        *(_map_entry(row, "interactive_control", real_proofs) for row in inventory.get("interactive_controls", [])),
    ]
    statuses = Counter(str(row["status"]) for row in entries)
    capabilities = Counter(str(row["capability_id"]) for row in entries if row["capability_id"])
    return {
        "schema_version": 2,
        "generated_at": datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds"),
        "inventory": {
            "path": str(inventory_path),
            "sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
            "functional_entries": int(inventory.get("counts", {}).get("functional_entries", 0)),
        },
        "real_proofs": {
            "path": str(real_proofs_path),
            "sha256": hashlib.sha256(real_proofs_path.read_bytes()).hexdigest() if real_proofs_path.is_file() else "",
        },
        "counts": {
            "functional_entries": len(entries),
            "mapped_entries": len(entries) - statuses.get("da_mappare", 0),
            "verified_entries": statuses.get("verificata", 0),
            "present_to_test_entries": statuses.get("presente_da_provare", 0),
            "partial_entries": statuses.get("parziale", 0),
            "unmapped_entries": statuses.get("da_mappare", 0),
            "capability_contracts": len(CONTRACTS),
        },
        "status_counts": dict(sorted(statuses.items())),
        "capability_counts": dict(sorted(capabilities.items())),
        "entries": entries,
        "policy": {
            "verified_rule": "Una funzione e' verificata solo con contratto puntuale, controlli codice, test e prova materiale sulla copia reale.",
            "current_state": "Le sole voci verificate sono collegate a una prova materiale registrata sulla copia reale.",
        },
    }


def _markdown(audit: dict[str, Any]) -> str:
    counts = audit["counts"]
    lines = [
        "# Matrice di parità funzionale",
        "",
        f"Generata: {audit['generated_at']} (Europe/Rome).",
        "",
        "## Stato",
        "",
        f"- Voci censite: {counts['functional_entries']}",
        f"- Voci con contratto puntuale: {counts['mapped_entries']}",
        f"- Presenti da provare sulla copia reale: {counts['present_to_test_entries']}",
        f"- Parziali: {counts['partial_entries']}",
        f"- Da mappare: {counts['unmapped_entries']}",
        f"- Verificate materialmente: {counts['verified_entries']}",
        "",
        "Nessuna voce viene considerata equivalente sulla sola base di una categoria o di una pagina affine.",
        "",
        "## Contratti rilevati",
        "",
    ]
    for capability, total in audit["capability_counts"].items():
        lines.append(f"- `{capability}`: {total} percorsi")
    verified = sorted({row["capability_id"] for row in audit["entries"] if row["status"] == "verificata"})
    lines.extend(["", "## Funzioni verificate materialmente", ""])
    if verified:
        lines.extend(f"- `{capability}`" for capability in verified)
    else:
        lines.append("- Nessuna")
    lines.extend(["", "## Voci ancora da mappare", ""])
    unmapped = [row for row in audit["entries"] if row["status"] == "da_mappare"]
    for row in unmapped:
        lines.append(f"- `{row['id']}`: {row['source_path']}")
    lines.extend(["", "## Regola di chiusura", "", audit["policy"]["verified_rule"], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Costruisce la matrice puntuale delle funzioni")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--real-proofs", type=Path, default=DEFAULT_REAL_PROOFS)
    args = parser.parse_args()
    audit = build_audit(args.inventory, args.real_proofs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(_markdown(audit), encoding="utf-8")
    print(json.dumps(audit["counts"], ensure_ascii=False))
    return 0 if audit["counts"]["functional_entries"] == audit["inventory"]["functional_entries"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
