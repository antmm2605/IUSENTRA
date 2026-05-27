from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    for required in (
        "local_signer_mod/security.py",
        "local_signer_mod/ai_cache.py",
        "local_signer_mod/ai_handlers.py",
        "local_signer_mod/server_bootstrap.py",
    ):
        if not (REPO_ROOT / required).exists():
            failures.append(f"Manca {required}")

    signer_paths = (
        "local_signer.py",
        "tools/local_signer.py",
    )
    existing_signer = next((path for path in signer_paths if (REPO_ROOT / path).exists()), "")
    if existing_signer:
        text = _read(existing_signer)
        expected_snippets = (
            "from local_signer_mod.security import (",
            "from local_signer_mod.ai_handlers import LocalAiHandlerFacade",
            "from local_signer_mod.server_bootstrap import print_startup_banner",
        )
        for snippet in expected_snippets:
            if snippet not in text:
                failures.append(f"{existing_signer} non integra ancora: {snippet}")

    baseline_doc = "docs/specs/ministero/PST_LOCAL_SIGNER_BASELINE_CERTIFICATO.md"
    if not (REPO_ROOT / baseline_doc).exists():
        failures.append(f"Manca {baseline_doc}")
    import_note_doc = "docs/specs/ministero/PST_FASCICOLO_IMPORT_TEST_REALE_2026-05-26.md"
    if not (REPO_ROOT / import_note_doc).exists():
        failures.append(f"Manca {import_note_doc}")
    else:
        import_note_text = _read(import_note_doc)
        for snippet in (
            "Tribunale di Palmi",
            "R.G. 274/2026",
            "`B6A03AE6`",
            "`/pst/download-documenti-batch`",
            "Dati fascicolo",
            "Documenti nel fascicolo",
            "Importazione completata con avvisi",
            "codice fiscale ricavato dal certificato selezionato",
            "barra delle applicazioni di Windows",
        ):
            if snippet not in import_note_text:
                failures.append(f"{import_note_doc} non preserva nota test reale: {snippet}")

    for signer_path in ("tools/local_signer.py", "tools/dist/local_signer.py"):
        signer_text = _read(signer_path)
        required_snippets = (
            'exact_registry_lookup = bool(str(numero_rg or "").strip() and str(anno_rg or "").strip())',
            "filtered_nome_parte = None if exact_registry_lookup else nome_parte",
            "filtered_cf_parte = None if exact_registry_lookup else cf_parte",
            "tag(\"nomeParte\", filtered_nome_parte)",
            "tag(\"codiceFiscaleParte\", filtered_cf_parte)",
            "do_preflight=False",
            "def _windows_pin_prompt_candidate_score",
            "EnumChildWindows",
            "QueryFullProcessImageNameW",
            "credentialuibroker",
            "AttachThreadInput",
            "FlashWindow",
            "def _cf_avvocato_pst",
            "if explicit:\n        return explicit",
        )
        for snippet in required_snippets:
            if snippet not in signer_text:
                failures.append(f"{signer_path} non preserva baseline PST: {snippet}")

    react_text = _read("frontend/src/components/TelematicoSurfacePage.tsx")
    react_required = (
        "const exactPstSearch = Boolean(asText(query.numero) && asText(query.anno))",
        "nome_parte: exactPstSearch ? '' : (query.assistito || query.controparte)",
        "cf_parte: exactPstSearch ? '' : query.cf",
        "pst_session_id: session?.sessionId || ''",
        "localSignerJson('/pst/ricerca-snapshot'",
        "localSignerJson('/pst/download-documenti-batch'",
        "preflight_auth: false",
        "ufficioCodice: office.codice || office.codiceMinistero",
        "exact?.codice || exact?.codiceMinistero || query.ufficio",
    )
    for snippet in react_required:
        if snippet not in react_text:
            failures.append(f"TelematicoSurfacePage non preserva baseline PST: {snippet}")
    if "office.codiceMinistero || office.codice" in react_text:
        failures.append("TelematicoSurfacePage deve inviare il codice ufficio, non preferire il codice ministeriale")
    if "localSignerJson('/pst/preflight-auth'" in react_text:
        failures.append("TelematicoSurfacePage non deve chiamare /pst/preflight-auth")
    if "localSignerJson('/pst/download-documento'" in react_text:
        failures.append("TelematicoSurfacePage non deve tornare al download documento singolo")

    wizard_text = _read("web/templates/portale/acquisizione_wizard.html")
    wizard_required = (
        "const exactByRg = !!(String(query.numero || '').trim() && String(query.anno || '').trim());",
        "nome_parte: exactByRg ? '' : (query.assistito || query.controparte || '')",
        "cf_parte: exactByRg ? '' : (query.cf || '')",
        "pst_session_id: activeSession?.session_id || ''",
        "`${AW_PST_LS_BASE}/pst/ricerca-snapshot`",
        "`${AW_PST_LS_BASE}/pst/download-documenti-batch`",
        "preflight_auth: false",
    )
    for snippet in wizard_required:
        if snippet not in wizard_text:
            failures.append(f"Wizard acquisizione non preserva baseline PST: {snippet}")
    if "`${AW_PST_LS_BASE}/pst/preflight-auth`" in wizard_text:
        failures.append("Wizard acquisizione non deve chiamare /pst/preflight-auth")

    if failures:
        print("Local Signer boundary check FAILED")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Local Signer boundary check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
