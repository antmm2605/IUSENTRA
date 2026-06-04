from __future__ import annotations

import json
import re
import time
import zipfile
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE = "http://127.0.0.1:8080"
VERSION = "2.249.15"
FASCICOLO_ID = "2DE106E6"
ROUTE = f"/template-atti/compila/CIV_COM_001?id_fascicolo={FASCICOLO_ID}"
URL = f"{BASE}{ROUTE}"
ARTIFACT_DIR = Path("artifacts/react-migration")
REPORT_PATH = ARTIFACT_DIR / "template-editor-browser-2.249.15.json"
DOWNLOAD_DIR = ARTIFACT_DIR / "template-editor-downloads-2.249.15"
SCREENSHOTS = {
    "desktop": ARTIFACT_DIR / "template-editor-2.249.15-desktop.png",
    "tablet": ARTIFACT_DIR / "template-editor-2.249.15-tablet.png",
    "mobile": ARTIFACT_DIR / "template-editor-2.249.15-mobile.png",
}


class BrowserCheck:
    def __init__(self) -> None:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.results: list[dict[str, object]] = []
        self.console_errors: list[dict[str, str]] = []
        self.page_errors: list[str] = []
        self.failed_requests: list[dict[str, object]] = []
        self.download_records: list[dict[str, object]] = []
        self.pdf_responses: list[dict[str, object]] = []

    def record(self, name: str, ok: bool = True, detail: object = "") -> None:
        self.results.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            raise AssertionError(f"{name}: {detail}")

    @staticmethod
    def editor_raw(page) -> str:
        return page.locator('[data-testid="professional-template-editor"]').evaluate(
            "el => el.innerText || el.textContent || ''",
            timeout=15000,
        )

    @staticmethod
    def editor_preview(page) -> str:
        return page.locator('[data-testid="professional-template-editor"]').inner_text(timeout=15000)

    @staticmethod
    def editor_html(page) -> str:
        return page.locator('[data-testid="professional-template-editor"]').evaluate(
            "el => el.innerHTML || ''",
            timeout=15000,
        )

    @staticmethod
    def visible_text(page) -> str:
        return page.locator("body").inner_text(timeout=15000)

    def check_visible_language(self, page, name: str) -> None:
        text = self.visible_text(page)
        forbidden = [
            "Template Builder",
            "Final Check",
            "Export",
            "built-in",
            "backend",
            "frontend",
            "payload",
            "runtime",
            "json_api",
            "provider",
            "webhook",
            "legacy",
            "undefined",
            "null",
            "demo",
            "sample",
            "repository",
            "endpoint",
            "server-side",
            "bridge",
            "\u00c3",
            "\u00c2",
            "\ufffd",
            "mostrera",
            "e'",
        ]
        found = [item for item in forbidden if item.casefold() in text.casefold()]
        self.record(name, not found, {"vietati": found[:10]})
        iso_dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", text)
        self.record(f"{name} - date italiane", not iso_dates, {"date_iso": iso_dates[:10]})

    def check_overflow(self, page, name: str) -> None:
        metrics = page.evaluate(
            """() => ({
                innerWidth: window.innerWidth,
                scrollWidth: document.documentElement.scrollWidth,
                bodyScrollWidth: document.body.scrollWidth,
                clientWidth: document.documentElement.clientWidth,
            })"""
        )
        ok = (
            metrics["scrollWidth"] <= metrics["innerWidth"] + 2
            and metrics["bodyScrollWidth"] <= metrics["innerWidth"] + 2
        )
        self.record(name, ok, metrics)

    @staticmethod
    def scroll_everything(page) -> None:
        page.evaluate(
            """() => {
                const nodes = [document.scrollingElement, document.documentElement, document.body,
                  ...Array.from(document.querySelectorAll('.iu-template-pro-sidebar,.iu-template-pro-fields,.iu-template-pro-panel,.iu-template-pro-canvas'))];
                for (const node of nodes) {
                  if (!node) continue;
                  node.scrollTop = 0;
                  node.scrollTop = Math.max(0, node.scrollHeight - node.clientHeight);
                  node.scrollTop = 0;
                }
                window.scrollTo(0, document.body.scrollHeight);
                window.scrollTo(0, 0);
            }"""
        )
        page.wait_for_timeout(250)

    def login_and_open(self, page) -> None:
        page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        page.locator('input[name="username"]').fill("admin")
        page.locator('input[name="password"]').fill("admin")
        page.locator('button[type="submit"]').click()
        page.wait_for_url("**/admin/**", timeout=15000)
        self.record("login admin", True, page.url)
        page.goto(f"{BASE}/admin/studi/antonella-mammola", wait_until="domcontentloaded")
        page.locator('form[action$="/impersona"] button').click(force=True, no_wait_after=True)
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        page.wait_for_function("() => location.pathname === '/' || !location.pathname.startsWith('/admin/studi/')", timeout=30000)
        self.record("impersonificazione studio", True, page.url)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="professional-template-editor"]', timeout=30000)
        self.record("apertura editor template reale", True, page.url)

    def save_download(self, download) -> tuple[Path, int]:
        target = DOWNLOAD_DIR / download.suggested_filename
        if target.exists():
            stem, suffix = target.stem, target.suffix
            index = 2
            while (DOWNLOAD_DIR / f"{stem}-{index}{suffix}").exists():
                index += 1
            target = DOWNLOAD_DIR / f"{stem}-{index}{suffix}"
        download.save_as(str(target))
        size = target.stat().st_size
        self.download_records.append({"file": str(target), "size": size})
        return target, size

    def click_and_download(self, page, button_name: str, min_size: int = 100) -> Path:
        with page.expect_download(timeout=30000) as info:
            page.get_by_role("button", name=button_name, exact=True).click()
        path, size = self.save_download(info.value)
        self.record(f"download {button_name}", size >= min_size, {"file": str(path), "size": size})
        return path

    def run(self) -> None:
        with sync_playwright() as p:
            request_context = p.request.new_context()
            ready = request_context.get(f"{BASE}/api/pronto", timeout=10000).json()
            request_context.dispose()
            self.record("readiness 8080", ready.get("ok") and ready.get("versione") == VERSION, ready)

            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
            context.on(
                "response",
                lambda response: self.pdf_responses.append({"url": response.url, "status": response.status})
                if "/template-atti/compila/CIV_COM_001/pdf" in response.url
                else None,
            )
            page = context.new_page()

            page.on(
                "console",
                lambda msg: self.console_errors.append({"type": msg.type, "text": msg.text})
                if msg.type in {"error"}
                else None,
            )
            page.on("pageerror", lambda exc: self.page_errors.append(str(exc)))

            def on_request_failed(req) -> None:
                failure = str(req.failure or "")
                if "favicon" in req.url or "net::ERR_ABORTED" in failure:
                    return
                self.failed_requests.append({"url": req.url, "failure": req.failure})

            page.on("requestfailed", on_request_failed)
            self.login_and_open(page)
            page.screenshot(path=str(SCREENSHOTS["desktop"]), full_page=True)
            self.check_visible_language(page, "testi visibili iniziali")
            self.scroll_everything(page)
            self.record("scroll iniziale desktop", True, "pagina e pannelli scrollati")
            self.check_overflow(page, "overflow iniziale desktop")

            workflow_text = page.locator(".iu-template-pro-flow").inner_text(timeout=10000)
            for label in [
                "Template selezionato",
                "Autocompilazione dati studio/cliente/fascicolo",
                "Editor documento",
                "Lex Correttore",
                "Lex Revisore stile legale",
                "Lex Revisore placeholder",
                "Lex Revisore normativa/privacy",
                "Controllo finale",
                "Versione finale",
                "Esporta DOCX / PDF / RTF",
            ]:
                self.record(f"workflow italiano {label}", label in workflow_text, workflow_text)

            expected_fields = {
                "recipient_or_court": "Ufficio del Giudice di Pace di Palmi",
                "client_or_sender": "Moscato Marco",
                "counterparty_or_recipient": "nn nn",
                "practice_reference": "Moscato Marco c/ nn nn - 12/2026",
                "practice_number": "12/2026",
                "practice_subject": "Moscato Marco c/ nn nn",
                "matter": "Civile",
            }
            got_fields: dict[str, str] = {}
            for key, expected in expected_fields.items():
                locator = page.locator(f'[data-testid="template-field-input-{key}"]')
                locator.wait_for(timeout=10000)
                value = locator.input_value()
                got_fields[key] = value
                self.record(f"campo fascicolo {key}", expected in value, {"atteso": expected, "ottenuto": value})
            self.record("connessione fisica fascicolo completa", True, got_fields)

            facts = page.locator('[data-testid="template-field-input-facts"]')
            facts.wait_for(timeout=10000)
            accented = "Fatto aggiornato con accenti italiani: à è é ì ò ù. Termine del 4 giugno 2026."
            facts.fill(accented)
            self.record("campo avvocato non tronca primo carattere", facts.input_value() == accented, facts.input_value())
            self.record("campo avvocato entra nel template", accented in self.editor_preview(page), self.editor_preview(page))

            page.locator('[data-testid="template-switch-STR_ATR_001"]').click()
            page.wait_for_url("**/template-atti/compila/STR_ATR_001**", timeout=15000)
            self.record("cambio modello dal pannello sinistro", "STR_ATR_001" in page.url, page.url)
            page.goto(URL, wait_until="networkidle")
            page.wait_for_selector('[data-testid="professional-template-editor"]', timeout=30000)

            font_select = page.locator('select[aria-label="Font documento"]').first
            font_value = font_select.evaluate(
                """(select) => {
                    const options = Array.from(select.options);
                    const preferred = options.find((option) => /Times New Roman/i.test(option.textContent || ''));
                    return (preferred || options.find((option) => option.value && option.value !== select.value) || options[0]).value;
                }"""
            )
            font_select.select_option(value=str(font_value))
            page.wait_for_timeout(300)
            font_family = page.locator(".iu-template-pro-paper").evaluate("el => getComputedStyle(el).fontFamily")
            self.record("cambio font documento", "Times New Roman" in font_family, font_family)
            page.evaluate(
                """() => {
                    const editor = document.querySelector('[data-testid="professional-template-editor"]');
                    const target = editor && (editor.querySelector('h1,h2,p,div,li,blockquote') || editor);
                    const range = document.createRange();
                    range.selectNodeContents(target);
                    const selection = window.getSelection();
                    selection.removeAllRanges();
                    selection.addRange(range);
                }"""
            )
            page.get_by_role("button", name="Centra", exact=True).click()
            page.wait_for_timeout(250)
            alignment_state = page.locator('[data-testid="professional-template-editor"]').evaluate(
                """(editor) => {
                    const target = editor.querySelector('h1,h2,p,div,li,blockquote') || editor;
                    const paper = document.querySelector('.iu-template-pro-paper');
                    return {
                        blockAlign: getComputedStyle(target).textAlign,
                        inlineStyle: target.getAttribute('style') || '',
                        paperClass: paper ? paper.getAttribute('class') : '',
                    };
                }"""
            )
            self.record(
                "comando allineamento centra",
                str(alignment_state.get("blockAlign", "")).lower() in {"center", "-webkit-center"}
                and "iu-template-align--center" not in str(alignment_state.get("paperClass", "")),
                alignment_state,
            )
            page.locator('[data-testid="professional-template-editor"]').click()
            page.keyboard.press("Control+A")
            page.get_by_role("button", name="Grassetto", exact=True).click()
            page.wait_for_timeout(250)
            bold_text = self.editor_raw(page)
            bold_html = self.editor_html(page).lower()
            self.record(
                "grassetto non inserisce markdown",
                "**" not in bold_text and ("<b" in bold_html or "<strong" in bold_html),
                {"text": bold_text[:200], "html": bold_html[:300]},
            )

            page.get_by_role("button", name="Stile", exact=True).click()
            before = page.locator(".iu-template-pro-paper__stamp").bounding_box()
            page.get_by_role("button", name="Centro destra", exact=True).click()
            page.wait_for_timeout(300)
            after = page.locator(".iu-template-pro-paper__stamp").bounding_box()
            paper_class = page.locator(".iu-template-pro-paper").get_attribute("class") or ""
            before_right = (before or {}).get("x", 0) + (before or {}).get("width", 0)
            after_right = (after or {}).get("x", 0) + (after or {}).get("width", 0)
            moved = bool(before and after and (after_right > before_right or abs(after["y"] - before["y"]) > 10))
            self.record(
                "timbro studio spostabile",
                moved and "iu-template-stamp-position--middle-right" in paper_class,
                {"prima": before, "dopo": after, "classi": paper_class},
            )
            stamp_text = page.locator(".iu-template-pro-paper__stamp").inner_text(timeout=10000)
            self.record("timbro studio completo visibile", len([line for line in stamp_text.splitlines() if line.strip()]) >= 3, stamp_text)

            page.get_by_role("button", name="Fonti", exact=True).click()
            page.get_by_role("button", name="Inserisci guida nel template", exact=True).click()
            page.wait_for_timeout(300)
            raw = self.editor_raw(page)
            self.record(
                "Guida pratica inserita nel template",
                "comparsa di costituzione e risposta" in raw.casefold() or "bozza integrata" in raw.casefold(),
                raw[-500:],
            )
            page.get_by_role("button", name="Inserisci riferimento", exact=True).first.click()
            page.wait_for_timeout(300)
            self.record("fonte normativa inserita nel template", "Riferimento normativo:" in self.editor_raw(page), self.editor_raw(page)[-500:])

            page.get_by_role("button", name="Lex", exact=True).click()
            page.get_by_text("Istruzioni personalizzate per Lex").locator("xpath=ancestor::label").locator("textarea").fill(
                "Mantieni tono professionale, chiaro e adatto al cliente."
            )
            proposal_count_before = page.locator(".iu-template-pro-diff-card").count()
            page.get_by_role("button", name="Genera clausola", exact=True).click()
            page.wait_for_function(
                """(count) => document.querySelectorAll('.iu-template-pro-diff-card').length > count""",
                arg=proposal_count_before,
                timeout=15000,
            )
            first_card = page.locator(".iu-template-pro-diff-card").first
            first_proposal_text = first_card.locator("textarea").input_value(timeout=10000)
            self.record("Lex genera proposta in diff", "Clausola proposta:" in first_proposal_text, first_proposal_text[:600])
            first_card.get_by_role("button", name="Accetta", exact=True).click()
            page.wait_for_timeout(300)
            self.record("Lex accetta diff e modifica documento", "Clausola proposta:" in self.editor_raw(page), self.editor_raw(page)[-600:])
            page.get_by_role("button", name="Controlla privacy", exact=True).click()
            page.wait_for_timeout(300)
            page.locator(".iu-template-pro-diff-card").first.get_by_role("button", name="Rifiuta", exact=True).click()
            page.wait_for_timeout(300)
            lex_text = page.locator(".iu-template-pro-proposals").inner_text(timeout=10000)
            self.record("Lex rifiuta diff senza applicazione automatica", "Rifiutata" in lex_text, lex_text[:1000])
            self.record("Lex mode visibili in italiano", "Template Builder" not in lex_text and "Final Check" not in lex_text, lex_text[:1000])

            page.get_by_role("button", name="Controlli", exact=True).click()
            controls = page.locator(".iu-template-pro-checks").inner_text(timeout=10000)
            for label in ["Controllo placeholder", "Controllo legal_basis", "Controllo privacy/PII"]:
                self.record(f"{label} visibile", label in controls, controls)

            slash = chr(92)
            rtf = (
                "{"
                + slash
                + "rtf1"
                + slash
                + "ansi{"
                + slash
                + "fonttbl{"
                + slash
                + "f0 Merriweather;}}"
                + slash
                + "f0 Documento importato con accenti "
                + slash
                + "'e0 "
                + slash
                + "'e8 "
                + slash
                + "'e9 "
                + slash
                + "'ec "
                + slash
                + "'f2 "
                + slash
                + "'f9 e dati fascicolo.}"
            )
            import_file = ARTIFACT_DIR / "template-import-smoke.rtf"
            import_file.write_text(rtf, encoding="utf-8")
            page.get_by_role("button", name="Campi", exact=True).click()
            page.locator(".iu-template-guide-file-input").set_input_files(str(import_file))
            page.wait_for_selector(".iu-template-pro-import-card", timeout=20000)
            import_card = page.locator(".iu-template-pro-import-card").inner_text(timeout=10000)
            self.record("import documento riconosce font", "Merriweather" in import_card, import_card)
            page.get_by_role("button", name="Pagina vuota", exact=True).click()
            page.wait_for_timeout(300)
            self.record("import pagina vuota per template personalizzato", self.editor_raw(page).strip() == "", "pagina svuotata")
            page.get_by_role("button", name="Inserisci testo importato", exact=True).click()
            page.wait_for_timeout(300)
            imported_text = self.editor_raw(page)
            for char in ["à", "è", "é", "ì", "ò", "ù"]:
                self.record(f"import preserva accento {char}", char in imported_text, imported_text)
            field_label = page.locator('[data-testid="template-field-input-practice_reference"]').locator("xpath=ancestor::label")
            field_label.get_by_role("button", name="Inserisci campo", exact=True).click()
            page.wait_for_timeout(300)
            self.record("associazione campo fascicolo in documento importato", "[PRACTICE_REFERENCE]" in self.editor_raw(page), self.editor_raw(page))

            page.get_by_role("button", name="Esporta", exact=True).click()
            self.click_and_download(page, "RTF")
            self.click_and_download(page, "DOCX")
            page.get_by_role("button", name="Copia", exact=True).click()
            page.wait_for_timeout(500)
            status_text = page.locator(".iu-template-pro-status").inner_text(timeout=10000)
            clipboard_text = page.evaluate("() => navigator.clipboard.readText()")
            self.record(
                "comando copia eseguito",
                "Documento copiato" in status_text and len(str(clipboard_text or "").strip()) > 80,
                {"status": status_text, "clipboard_preview": str(clipboard_text or "")[:300]},
            )
            page.get_by_role("button", name="Rigenera dal template", exact=True).click()
            page.wait_for_timeout(1500)
            self.record("rigenera dal template eseguito", self.editor_raw(page).strip() != "", "documento rigenerato")
            with page.expect_response(
                lambda response: "/guida-pratica/salva" in response.url and response.status < 400,
                timeout=60000,
            ):
                page.get_by_role("button", name="Salva nel fascicolo", exact=True).click()
            page.wait_for_function(
                """() => document.body.innerText.includes('Documento salvato nel fascicolo')""",
                timeout=15000,
            )
            status_text = page.locator(".iu-template-pro-status").inner_text(timeout=10000)
            self.record("salva nel fascicolo eseguito", "Documento salvato nel fascicolo" in status_text or "Bozza creata" in status_text, status_text)

            before_pdf = len(self.pdf_responses)
            page.get_by_role("button", name="PDF", exact=True).click()
            deadline = time.time() + 30
            while time.time() < deadline and len(self.pdf_responses) <= before_pdf:
                page.wait_for_timeout(300)
            pdf_detail = self.pdf_responses[-1] if len(self.pdf_responses) > before_pdf else {"url": page.url, "status": 0}
            self.record("anteprima PDF eseguita", int(pdf_detail.get("status") or 0) < 400 and int(pdf_detail.get("status") or 0) >= 200, pdf_detail)
            for extra_page in list(context.pages):
                if extra_page != page:
                    extra_page.close()
            page.bring_to_front()

            page.get_by_role("button", name="Compilazione multipla", exact=True).click()
            page.wait_for_selector(".iu-template-pro-multiple", timeout=10000)
            boxes = page.locator('.iu-template-pro-multiple input[type="checkbox"]')
            count = boxes.count()
            page.get_by_role("button", name="Seleziona visibili", exact=True).click()
            page.wait_for_timeout(300)
            with page.expect_download(timeout=30000) as multiple_download:
                page.get_by_role("button", name="Genera RTF selezionati", exact=True).click()
            path, size = self.save_download(multiple_download.value)
            with zipfile.ZipFile(path) as archive:
                entries = archive.namelist()
                rtf_entries = [entry for entry in entries if entry.lower().endswith(".rtf")]
                entry_sizes = {entry: archive.getinfo(entry).file_size for entry in rtf_entries}
            self.record(
                "compilazione multipla genera RTF selezionati",
                size >= 100 and len(rtf_entries) == count and all(value >= 100 for value in entry_sizes.values()),
                {"file": str(path), "size": size, "rtf": rtf_entries, "dimensioni": entry_sizes},
            )

            page.get_by_role("button", name="Firma documento", exact=True).click()
            page.wait_for_url(re.compile(r".*/fascicoli/2DE106E6/documenti/.*/firma.*"), timeout=30000)
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_function(
                "() => !document.body.innerText.includes('Caricamento modulo') || document.body.innerText.toLowerCase().includes('firma')",
                timeout=30000,
            )
            signature_text = self.visible_text(page)
            self.record("firma documento apre flusso firma", "Firma" in signature_text or "firma" in signature_text, {"url": page.url, "estratto": signature_text[:600]})

            for name, viewport in [("tablet", {"width": 820, "height": 920}), ("mobile", {"width": 390, "height": 844})]:
                page.set_viewport_size(viewport)
                page.goto(URL, wait_until="networkidle")
                page.wait_for_selector('[data-testid="professional-template-editor"]', timeout=30000)
                self.scroll_everything(page)
                self.check_visible_language(page, f"testi visibili {name}")
                self.check_overflow(page, f"overflow {name}")
                page.screenshot(path=str(SCREENSHOTS[name]), full_page=True)
                self.record(f"responsive {name} editor operativo", page.locator('[data-testid="professional-template-editor"]').is_visible(), viewport)

            page.set_viewport_size({"width": 1440, "height": 1000})
            page.goto(URL, wait_until="networkidle")
            page.wait_for_selector('[data-testid="professional-template-editor"]', timeout=30000)
            page.screenshot(path=str(SCREENSHOTS["desktop"]), full_page=True)
            self.check_visible_language(page, "testi visibili finali desktop")
            self.check_overflow(page, "overflow finale desktop")

            self.record("console senza errori applicativi", not self.console_errors, self.console_errors[:10])
            self.record("page errors assenti", not self.page_errors, self.page_errors[:10])
            self.record("richieste fallite assenti", not self.failed_requests, self.failed_requests[:10])
            browser.close()

    def write_report(self, ok: bool, failed_at: str = "", detail: str = "") -> None:
        report = {
            "ok": ok,
            "route": ROUTE,
            "base": BASE,
            "version": VERSION,
            "browser_path": "Playwright Python su Docker locale 127.0.0.1:8080",
            "results": self.results,
            "console_errors": self.console_errors,
            "page_errors": self.page_errors,
            "failed_requests": self.failed_requests,
            "downloads": self.download_records,
            "screenshots": {key: str(value) for key, value in SCREENSHOTS.items()},
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "failed_at": failed_at,
            "detail": detail,
        }
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    check = BrowserCheck()
    ok = False
    failed_at = ""
    detail = ""
    try:
        check.run()
        ok = True
    except Exception as exc:  # noqa: BLE001 - il report deve conservare qualsiasi blocco browser.
        failed_at = str(check.results[-1]["name"]) if check.results else "avvio"
        detail = str(exc)
    check.write_report(ok=ok, failed_at=failed_at, detail=detail)
    print(
        json.dumps(
            {
                "ok": ok,
                "failed_at": failed_at,
                "detail": detail,
                "report": str(REPORT_PATH),
                "passed": sum(1 for row in check.results if row["ok"]),
                "total": len(check.results),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
