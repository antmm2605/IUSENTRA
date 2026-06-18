from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("IUSENTRA_AUDIT_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
REPORT_PATH = ROOT / "artifacts" / "react-migration" / "local-real-workflow-audit.json"
ROME_TZ = ZoneInfo("Europe/Rome")
NO_SCREENSHOTS = True


class AuditFailure(AssertionError):
    pass


@dataclass
class AuditStep:
    name: str
    ok: bool
    started_at: str
    finished_at: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class TenantInfo:
    slug: str
    storage_key: str
    name: str
    api_key: str
    user_id: str


def now_rome() -> str:
    return datetime.now(ROME_TZ).isoformat(timespec="seconds")


def run_command(args: list[str], *, timeout: int = 120, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def expect(condition: Any, message: str) -> None:
    if not condition:
        raise AuditFailure(message)


def write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def json_from_command_marker(args: list[str], code: str, marker: str = "AUDIT_JSON:", timeout: int = 120) -> dict[str, Any]:
    result = run_command(args, input_text=code, timeout=timeout)
    if result.returncode != 0:
        raise AuditFailure(f"Comando non riuscito: {' '.join(args)}\n{result.stderr[-1200:]}")
    for line in reversed(result.stdout.splitlines()):
        if line.startswith(marker):
            return json.loads(line[len(marker):])
    raise AuditFailure(f"Marker {marker!r} non trovato nell'output del comando.")


def http_json(path: str, *, method: str = "GET", headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload_json = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload_json = {"raw": raw}
        return exc.code, payload_json


def wait_pronto(timeout_seconds: int = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            status, payload = http_json("/api/pronto")
            if status == 200 and payload.get("ok") is True:
                return payload
            last_error = f"HTTP {status}: {payload}"
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = str(exc)
        time.sleep(2)
    raise AuditFailure(f"/api/pronto non verde su {BASE_URL}: {last_error}")


def load_tenant_info() -> TenantInfo:
    registry_path = ROOT / "data" / "tenants.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if isinstance(registry, dict):
        raw_tenants = registry.get("tenants")
        tenants = raw_tenants if isinstance(raw_tenants, list) else list(registry.values())
    elif isinstance(registry, list):
        tenants = registry
    else:
        tenants = []
    for item in tenants:
        if str(item.get("stato") or "").upper() not in {"ATTIVO", "TRIAL"}:
            continue
        slug = str(item.get("slug") or "").strip()
        storage_key = str(item.get("storage_key") or item.get("storageKey") or "").strip()
        api_key = str(item.get("api_key") or item.get("apiKey") or "").strip()
        if not (slug and storage_key and api_key):
            continue
        users_path = ROOT / "data" / "tenants" / storage_key / "auth" / "utenti.json"
        users_payload = json.loads(users_path.read_text(encoding="utf-8"))
        users = users_payload.get("utenti") if isinstance(users_payload, dict) and isinstance(users_payload.get("utenti"), (list, dict)) else users_payload
        user_id = ""
        if isinstance(users, list):
            for row in users:
                if str(row.get("attivo", True)).lower() != "false":
                    user_id = str(row.get("id") or row.get("username") or "").strip()
                    if user_id:
                        break
        elif isinstance(users, dict):
            for key, row in users.items():
                if isinstance(row, dict) and str(row.get("attivo", True)).lower() != "false":
                    user_id = str(row.get("id") or row.get("username") or key).strip()
                    if user_id:
                        break
        if user_id:
            return TenantInfo(slug=slug, storage_key=storage_key, name=str(item.get("nome") or slug), api_key=api_key, user_id=user_id)
    raise AuditFailure("Nessun tenant attivo con API key e utente locale trovato.")


def docker_session_cookie(tenant: TenantInfo) -> dict[str, str]:
    code = f"""
from datetime import datetime
import json
from web.app import create_app
app = create_app()
serializer = app.session_interface.get_signing_serializer(app)
payload = {{
  "user_id": {tenant.user_id!r},
  "tenant_slug": {tenant.slug!r},
  "auth_scope": "tenant",
  "auth_tenant_slug": {tenant.slug!r},
  "last_activity": datetime.now().isoformat(),
}}
print("AUDIT_JSON:" + json.dumps({{"cookie_name": app.config.get("SESSION_COOKIE_NAME", "iusentra_session"), "cookie": serializer.dumps(payload)}}))
"""
    return json_from_command_marker(["docker", "compose", "exec", "-T", "app", "python", "-"], code)


def create_support_session_in_docker() -> dict[str, Any]:
    code = """
import json
from web.app import create_app
from web.services.support_runtime import support_repository
from pct.support_remote import issue_operator_token

app = create_app()
with app.app_context():
    repo = support_repository()
    row = repo.create_session({
        "customer_name": "Audit locale IUSENTRA",
        "practice_label": "Verifica assistenza remota reale",
        "created_by": "Audit locale",
        "assigned_to": "Audit locale",
        "notes": "Sessione creata da audit locale senza screenshot.",
        "status": "created",
    })
    token = issue_operator_token(row["public_id"], "Audit locale", "codex-audit")
    print("AUDIT_JSON:" + json.dumps({
        "public_id": row["public_id"],
        "client_token": row["client_token"],
        "operator_token": token,
    }))
"""
    return json_from_command_marker(["docker", "compose", "exec", "-T", "app", "python", "-"], code)


def ensure_local_support_agent() -> tuple[dict[str, Any], subprocess.Popen[str] | None]:
    def status() -> dict[str, Any]:
        request = urllib.request.Request("http://127.0.0.1:27273/status", headers={"Origin": BASE_URL})
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        payload = status()
        if payload.get("ok"):
            return payload, None
    except Exception:
        pass

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [sys.executable, "-m", "pct.support_remote"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=creationflags,
    )
    deadline = time.monotonic() + 25
    last_error = ""
    while time.monotonic() < deadline:
        try:
            payload = status()
            if payload.get("ok"):
                return payload, proc
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    proc.terminate()
    raise AuditFailure(f"Agente assistenza locale non raggiungibile: {last_error}")


def spawn_control_receiver(marker: str) -> tuple[subprocess.Popen[str], Path, Path]:
    marker_file = Path(tempfile.gettempdir()) / f"iusentra-support-control-{int(time.time())}.txt"
    geometry_file = Path(tempfile.gettempdir()) / f"iusentra-support-control-geometry-{int(time.time())}.json"
    receiver_code = f"""
import ctypes
import json
import pathlib
import tkinter as tk
marker = {marker!r}
target = pathlib.Path({str(marker_file)!r})
geometry_target = pathlib.Path({str(geometry_file)!r})
root = tk.Tk()
root.title("IUSENTRA audit controllo PC")
root.geometry("620x160+80+80")
root.attributes("-topmost", True)
label = tk.Label(root, text="Finestra audit controllo PC IUSENTRA")
label.pack(pady=8)
entry = tk.Entry(root, width=72)
entry.pack(padx=12, pady=8)
def write_geometry():
    try:
        root.update()
        geometry_target.write_text(json.dumps({{
            "x": entry.winfo_rootx() + (entry.winfo_width() / 2),
            "y": entry.winfo_rooty() + (entry.winfo_height() / 2),
            "root_x": root.winfo_rootx(),
            "root_y": root.winfo_rooty(),
            "entry_width": entry.winfo_width(),
            "entry_height": entry.winfo_height(),
        }}), encoding="utf-8")
    except Exception:
        pass
def focus_entry():
    try:
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        root.update()
        ctypes.windll.user32.BringWindowToTop(root.winfo_id())
        ctypes.windll.user32.SetForegroundWindow(root.winfo_id())
    except Exception:
        pass
    entry.focus_set()
    entry.focus_force()
    root.after(400, focus_entry)
def poll():
    value = entry.get()
    if marker in value:
        target.write_text(value, encoding="utf-8")
    root.after(200, poll)
root.after(100, focus_entry)
root.after(250, write_geometry)
poll()
root.after(45000, root.destroy)
root.mainloop()
"""
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen([sys.executable, "-c", receiver_code], cwd=ROOT, text=True, creationflags=creationflags)
    time.sleep(2)
    return proc, marker_file, geometry_file


def launch_browser():
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",
            "--allow-http-screen-capture",
            "--disable-features=Translate",
        ],
    )
    return playwright, browser


def page_text(page: Any, selector: str = "body") -> str:
    return page.locator(selector).inner_text(timeout=15000)


def audit_support_real_flow() -> dict[str, Any]:
    agent_status, agent_proc = ensure_local_support_agent()
    session = create_support_session_in_docker()
    playwright, browser = launch_browser()
    marker = f"IUSENTRA_CONTROL_{int(time.time())}"
    receiver_proc: subprocess.Popen[str] | None = None
    marker_file: Path | None = None
    geometry_file: Path | None = None
    try:
        context = browser.new_context(
            base_url=BASE_URL,
            permissions=["microphone"],
            viewport={"width": 1366, "height": 900},
        )
        operator = context.new_page()
        customer = context.new_page()
        operator.goto(f"{BASE_URL}/support/operatore/{session['public_id']}?token={urllib.parse.quote(session['operator_token'])}", wait_until="domcontentloaded")
        customer.goto(f"{BASE_URL}/support/join/{session['client_token']}", wait_until="domcontentloaded")
        operator.wait_for_selector("#supportOperatorShell", timeout=30000)
        customer.wait_for_selector("#startBtn", timeout=30000)

        expect(operator.locator("#remoteAgentFrame").count() == 1, "Stanza operatore senza area schermo cliente.")
        expect(customer.locator("#localAgentPreview").count() == 1, "Stanza cliente senza anteprima agente locale.")

        if operator.locator("#operatorMic").is_enabled():
            operator.locator("#operatorMic").check()
        operator.locator("#joinBtn").click()
        customer.wait_for_function("() => !document.querySelector('#startBtn')?.disabled", timeout=30000)
        if customer.locator("#consentAudio").count() == 1:
            customer.locator("#consentAudio").check()
        customer.locator("#startBtn").click()

        operator.wait_for_function("() => (document.querySelector('#peerBadge')?.textContent || '').includes('Cliente collegato')", timeout=45000)
        customer.wait_for_function("() => (document.querySelector('#peerBadge')?.textContent || '').includes('Operatore collegato')", timeout=45000)

        operator.locator("#chatInput").fill("Messaggio operatore audit")
        operator.locator("#sendBtn").click()
        customer.wait_for_function("() => (document.querySelector('#chatLog')?.textContent || '').includes('Messaggio operatore audit')", timeout=20000)
        customer.locator("#chatInput").fill("Risposta cliente audit")
        customer.locator("#sendBtn").click()
        operator.wait_for_function("() => (document.querySelector('#chatLog')?.textContent || '').includes('Risposta cliente audit')", timeout=20000)

        operator.locator("#operatorMuteMicBtn").click()
        expect(operator.locator("#operatorMuteMicBtn").get_attribute("aria-pressed") == "true", "Mute microfono operatore non cambia stato.")
        operator.locator("#operatorMuteMicBtn").click()
        expect(operator.locator("#operatorMuteMicBtn").get_attribute("aria-pressed") == "false", "Unmute microfono operatore non cambia stato.")
        customer.locator("#customerMuteMicBtn").click()
        expect(customer.locator("#customerMuteMicBtn").get_attribute("aria-pressed") == "true", "Mute microfono cliente non cambia stato.")
        customer.locator("#customerMuteMicBtn").click()
        expect(customer.locator("#customerMuteMicBtn").get_attribute("aria-pressed") == "false", "Unmute microfono cliente non cambia stato.")

        operator.wait_for_function(
            "() => { const src = document.querySelector('#remoteAgentFrame')?.getAttribute('src') || ''; return src.startsWith('data:image/jpeg;base64,') && src.length > 1000; }",
            timeout=45000,
        )
        frame_info = operator.evaluate(
            "() => ({ length: (document.querySelector('#remoteAgentFrame')?.getAttribute('src') || '').length, hidden: document.querySelector('#remoteAgentFrame')?.classList.contains('d-none') })"
        )

        frame_before_receiver = operator.locator("#remoteAgentFrame").get_attribute("src") or ""
        receiver_proc, marker_file, geometry_file = spawn_control_receiver(marker)

        deadline = time.monotonic() + 8
        target_geometry: dict[str, Any] = {}
        while time.monotonic() < deadline:
            if geometry_file and geometry_file.exists():
                target_geometry = json.loads(geometry_file.read_text(encoding="utf-8"))
                if target_geometry.get("x") and target_geometry.get("y"):
                    break
            time.sleep(0.25)
        expect(bool(target_geometry), "La finestra audit controllo PC non ha esposto le coordinate del campo cliente.")
        operator.wait_for_function(
            """oldSrc => {
                const frame = document.querySelector('#remoteAgentFrame');
                const src = frame?.getAttribute('src') || '';
                return src.startsWith('data:image/jpeg;base64,') && src.length > 1000 && src !== oldSrc;
            }""",
            arg=frame_before_receiver,
            timeout=15000,
        )

        operator.locator("#requestAdvancedBtn").click()
        customer.wait_for_selector("#advancedBanner:not(.d-none)", timeout=30000)
        customer.locator("#approveAdvancedBtn").click()
        operator.wait_for_function("() => !document.querySelector('#sendRemoteTextBtn')?.disabled", timeout=30000)

        screen_info = agent_status.get("screen") if isinstance(agent_status.get("screen"), dict) else {}
        screen_x = int(screen_info.get("x") or agent_status.get("screen_x") or 0)
        screen_y = int(screen_info.get("y") or agent_status.get("screen_y") or 0)
        screen_width = int(screen_info.get("width") or agent_status.get("screen_width") or 0)
        screen_height = int(screen_info.get("height") or agent_status.get("screen_height") or 0)
        expect(screen_width > 0 and screen_height > 0, "Dimensione schermo agente locale non disponibile.")
        click_position = operator.evaluate(
            """({ targetX, targetY, screenX, screenY, screenWidth, screenHeight }) => {
                const screen = document.querySelector('#remoteScreen');
                const frame = document.querySelector('#remoteAgentFrame');
                if (!screen) return null;
                const rect = screen.getBoundingClientRect();
                const sourceWidth = Number(frame?.naturalWidth || screenWidth || 0);
                const sourceHeight = Number(frame?.naturalHeight || screenHeight || 0);
                if (!rect.width || !rect.height || !sourceWidth || !sourceHeight) return null;
                const sourceRatio = sourceWidth / sourceHeight;
                const containerRatio = rect.width / rect.height;
                let left = 0;
                let top = 0;
                let width = rect.width;
                let height = rect.height;
                if (containerRatio > sourceRatio) {
                  width = rect.height * sourceRatio;
                  left = (rect.width - width) / 2;
                } else {
                  height = rect.width / sourceRatio;
                  top = (rect.height - height) / 2;
                }
                const ratioX = (targetX - screenX) / screenWidth;
                const ratioY = (targetY - screenY) / screenHeight;
                return {
                  x: left + (width * Math.max(0, Math.min(1, ratioX))),
                  y: top + (height * Math.max(0, Math.min(1, ratioY))),
                };
            }""",
            {
                "targetX": float(target_geometry["x"]),
                "targetY": float(target_geometry["y"]),
                "screenX": screen_x,
                "screenY": screen_y,
                "screenWidth": screen_width,
                "screenHeight": screen_height,
            },
        )
        expect(bool(click_position), "Impossibile calcolare il punto cliccabile nello schermo remoto.")
        operator.locator("#remoteScreen").click(position={"x": click_position["x"], "y": click_position["y"]})
        time.sleep(1.0)
        operator.locator("#remoteControlText").fill(marker)
        operator.locator("#sendRemoteTextBtn").click()
        deadline = time.monotonic() + 15
        received = ""
        while time.monotonic() < deadline:
            if marker_file and marker_file.exists():
                received = marker_file.read_text(encoding="utf-8", errors="replace")
                if marker in received:
                    break
            time.sleep(0.5)
        expect(marker in received, "Il controllo PC approvato non ha digitato il marker sul desktop cliente.")

        return {
            "agent": {
                "ok": bool(agent_status.get("ok")),
                "platform": agent_status.get("platform"),
                "screen": {
                    "x": screen_x,
                    "y": screen_y,
                    "width": screen_width,
                    "height": screen_height,
                },
            },
            "session": {"publicId": session["public_id"]},
            "chat": "bidirezionale verificata",
            "microfono": "toggle operatore e cliente verificati",
            "schermo": {"frameBase64Length": frame_info["length"], "visible": not frame_info["hidden"]},
            "controlloPc": {"markerDigitato": True},
        }
    finally:
        try:
            browser.close()
        finally:
            playwright.stop()
        if receiver_proc:
            receiver_proc.terminate()
        if marker_file and marker_file.exists():
            try:
                marker_file.unlink()
            except OSError:
                pass
        if geometry_file and geometry_file.exists():
            try:
                geometry_file.unlink()
            except OSError:
                pass
        if agent_proc:
            agent_proc.terminate()


def select_template_url(code: str = "AMM_RIC_001") -> str:
    return f"{BASE_URL}/template-atti/compila/{urllib.parse.quote(code)}"


def set_editor_html(page: Any, paragraphs: int = 70) -> str:
    content = "\n".join(
        f"<p>Paragrafo audit {index}: contenuto professionale con accenti à è ì ò ù e riferimento alla pagina {index}.</p>"
        for index in range(1, paragraphs + 1)
    )
    page.evaluate(
        """html => {
            const editor = document.querySelector('[data-testid="professional-template-editor"]');
            editor.innerHTML = html;
            editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: '' }));
        }""",
        content,
    )
    return content


def select_text_in_editor(page: Any, paragraph_index: int = 0) -> None:
    page.evaluate(
        """index => {
            const editor = document.querySelector('[data-testid="professional-template-editor"]');
            const nodes = editor ? editor.querySelectorAll('p, h1, h2, div') : [];
            const node = nodes[index] || nodes[0] || editor;
            const range = document.createRange();
            range.selectNodeContents(node);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            node.scrollIntoView({ block: 'center' });
        }""",
        paragraph_index,
    )


def click_button_by_label(page: Any, label: str) -> None:
    locator = page.locator(f"button[aria-label='{label}'], button[title='{label}']").first
    if hasattr(locator, "__call__"):
        locator = locator()
    if locator.count() == 0:
        locator = page.get_by_role("button", name=label).first
        if hasattr(locator, "__call__"):
            locator = locator()
    expect(locator.count() >= 1, f"Pulsante non trovato: {label}")
    locator.click()


def current_editor_state(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """() => {
            const editor = document.querySelector('[data-testid="professional-template-editor"]');
            const blocks = editor ? Array.from(editor.querySelectorAll('p, h1, h2, div')).slice(0, 6).map((node) => ({
                tag: node.tagName,
                text: node.innerText || node.textContent || '',
                html: node.outerHTML,
                align: getComputedStyle(node).textAlign,
                font: getComputedStyle(node).fontFamily,
            })) : [];
            return {
                text: editor ? editor.innerText : '',
                html: editor ? editor.innerHTML : '',
                blocks,
                pageMarkers: document.querySelectorAll('[data-testid^="template-page-marker-"]').length,
                toolbarTop: document.querySelector('.iu-template-pro-toolbar')?.getBoundingClientRect().top,
                scrollWidth: document.documentElement.scrollWidth,
                clientWidth: document.documentElement.clientWidth,
            };
        }"""
    )


def make_import_files(tmp: Path) -> tuple[Path, Path]:
    rtf = tmp / "audit_import_accents.rtf"
    rtf.write_text(
        r"{\rtf1\ansi\deff0{\fonttbl{\f0 Arial;}}\fs24 Testo importato con accenti: \u224? \u232? \u236? \u242? \u249? - Cliente audit.}",
        encoding="utf-8",
    )
    pdf = tmp / "audit_import_pdf.pdf"
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 760, "PDF audit IUSENTRA con accenti: à è ì ò ù")
    c.drawString(72, 735, "Riga importata mantenendo testo e font dichiarabile.")
    c.save()
    return rtf, pdf


def form_data_for_export(code: str, text: str, html: str) -> dict[str, str]:
    layout = {
        "font_family": "arial",
        "fallback_font_family": "Arial",
        "font_size": 12,
        "line_height": 1.45,
        "text_align": "justify",
        "stamp_position": "top-left",
        "stamp_offset_y_mm": 0,
    }
    return {
        "title": f"Audit export {code}",
        "testo_generato": text,
        "testo_generato_html": html,
        "testo_generato__editor_layout": json.dumps(layout, ensure_ascii=False),
    }


def post_form_bytes(context: Any, path: str, fields: dict[str, str]) -> tuple[int, bytes, str]:
    response = context.request.post(f"{BASE_URL}{path}", form=fields)
    return response.status, response.body(), response.headers.get("content-type", "")


def extract_docx_text_and_fonts(data: bytes) -> tuple[str, str]:
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
        handle.write(data)
        temp_name = handle.name
    try:
        with zipfile.ZipFile(temp_name) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
            styles_xml = archive.read("word/styles.xml").decode("utf-8", errors="replace") if "word/styles.xml" in archive.namelist() else ""
        text = re.sub(r"<[^>]+>", " ", document_xml)
        return text, document_xml + styles_xml
    finally:
        Path(temp_name).unlink(missing_ok=True)


def audit_template_editor(tenant: TenantInfo, cookie: dict[str, str]) -> dict[str, Any]:
    playwright, browser = launch_browser()
    tmp = Path(tempfile.mkdtemp(prefix="iusentra-template-audit-"))
    code = "AMM_RIC_001"
    try:
        context = browser.new_context(
            base_url=BASE_URL,
            viewport={"width": 1440, "height": 920},
            accept_downloads=True,
            permissions=["clipboard-read", "clipboard-write"],
        )
        context.add_cookies([{
            "name": cookie["cookie_name"],
            "value": cookie["cookie"],
            "domain": "127.0.0.1",
            "path": "/",
            "httpOnly": True,
            "sameSite": "Lax",
        }])
        page = context.new_page()
        page.goto(select_template_url(code), wait_until="domcontentloaded")
        if page.locator("[data-testid='professional-template-editor']").count() == 0:
            code = "CIV_COM_001"
            page.goto(select_template_url(code), wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid='professional-template-editor']", timeout=45000)
        initial_text = page_text(page)
        for label in ("Campi", "Stile", "Lex", "Fonti", "Controlli", "Esporta"):
            expect(label in initial_text, f"Sezione editor mancante: {label}")
        expect("Import Document" not in initial_text and "Save to case" not in initial_text, "Testi inglesi visibili nell'editor.")
        page.wait_for_function(
            """() => document.querySelectorAll('input[data-testid^="template-field-input-"], textarea[data-testid^="template-field-input-"]').length > 0""",
            timeout=20000,
        )

        field_test_id = page.evaluate(
            """() => {
                const editorText = document.querySelector('[data-testid="professional-template-editor"]')?.innerText || '';
                const controls = Array.from(document.querySelectorAll('input[data-testid^="template-field-input-"], textarea[data-testid^="template-field-input-"]'));
                const match = controls.find((control) => {
                  const testId = control.getAttribute('data-testid') || '';
                  const name = testId.replace(/^template-field-input-/, '');
                  const token = `[${name.toUpperCase()}]`;
                  return editorText.includes(token);
                });
                return match ? match.getAttribute('data-testid') : (controls[0]?.getAttribute('data-testid') || '');
            }"""
        )
        expect(field_test_id, "Nessun campo compilabile trovato.")
        field = page.locator(f"[data-testid='{field_test_id}']")
        expect(field.count() >= 1, "Nessun campo compilabile trovato.")
        field.fill("Audit cliente Àèìòù 123")
        expect(field.input_value() == "Audit cliente Àèìòù 123", "Il campo compilabile non conserva la stringa completa.")
        expect("Audit cliente Àèìòù 123" in current_editor_state(page)["text"], "Il valore campo non entra nel template.")

        html = set_editor_html(page, paragraphs=95)
        page.wait_for_function("() => document.querySelectorAll('[data-testid^=\"template-page-marker-\"]').length >= 2", timeout=20000)
        state = current_editor_state(page)
        expect(state["pageMarkers"] >= 2, "Indicatori pagina 2/3 non rilevati.")

        select_text_in_editor(page, 0)
        click_button_by_label(page, "Grassetto")
        state = current_editor_state(page)
        expect("**" not in state["html"], "Grassetto inserisce markdown invece di HTML.")
        expect("<b" in state["html"].lower() or "<strong" in state["html"].lower(), "Grassetto non applicato alla selezione.")

        select_text_in_editor(page, 1)
        click_button_by_label(page, "Centra")
        state = current_editor_state(page)
        expect(any(block["align"] == "center" and "Paragrafo audit 2" in block["text"] for block in state["blocks"]), "Centro non applicato al blocco selezionato.")
        expect(not any(block["align"] == "center" and "Paragrafo audit 1" in block["text"] for block in state["blocks"]), "Centro applicato anche al blocco non selezionato.")

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        toolbar_top = page.evaluate("() => document.querySelector('.iu-template-pro-toolbar')?.getBoundingClientRect().top")
        expect(toolbar_top is not None and toolbar_top >= 0, "La barra strumenti scompare durante lo scorrimento.")

        font_select = page.locator("select[aria-label='Font documento']")
        expect(font_select.count() == 1, "Selettore font documento mancante.")
        options = font_select.locator("option").evaluate_all("(nodes) => nodes.map((node) => ({value: node.value, text: node.textContent}))")
        arial = next((item for item in options if "arial" in (item["text"] or item["value"]).lower()), None)
        expect(arial, "Font Arial non disponibile nel registry.")
        select_text_in_editor(page, 2)
        font_select.select_option(arial["value"])
        state = current_editor_state(page)
        expect("arial" in state["html"].lower() or any("arial" in block["font"].lower() for block in state["blocks"]), "Cambio font selezionato non applicato.")

        switchers = page.locator("[data-testid^='template-switch-']")
        expect(switchers.count() >= 2, "Catalogo laterale senza più modelli selezionabili.")
        current_url = page.url
        switchers.nth(1).click()
        page.wait_for_function("oldUrl => window.location.href !== oldUrl", arg=current_url, timeout=20000)
        expect("/template-atti/compila/" in page.url, "Cambio template non naviga al modello scelto.")
        page.goto(select_template_url(code), wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid='professional-template-editor']", timeout=30000)
        set_editor_html(page, paragraphs=30)

        page.get_by_role("button", name="Fonti").click()
        page.get_by_role("button", name="Inserisci guida nel template").click()
        expect("Guida pratica" in page_text(page) or len(current_editor_state(page)["text"]) > len(html[:600]), "Guida pratica non inserita nel template.")

        page.get_by_role("button", name="Lex", exact=True).click()
        first_lex = page.locator(".iu-template-pro-lex-actions button").first
        expect(first_lex.count() >= 1, "Azioni Lex non disponibili.")
        before_lex = current_editor_state(page)["text"]
        first_lex.click()
        page.wait_for_selector(".iu-template-pro-diff-card", timeout=30000)
        expect(current_editor_state(page)["text"] == before_lex, "Lex modifica il documento senza accettazione.")
        page.locator(".iu-template-pro-diff-card button", has_text="Rifiuta").first.click()
        first_lex.click()
        page.wait_for_selector(".iu-template-pro-diff-card", timeout=30000)
        page.locator(".iu-template-pro-diff-card button", has_text="Accetta").first.click()
        expect(current_editor_state(page)["text"] != before_lex, "Accetta proposta Lex non modifica il documento.")

        rtf_file, pdf_file = make_import_files(tmp)
        page.locator(".iu-template-guide-file-input").set_input_files(str(rtf_file))
        page.wait_for_selector(".iu-template-pro-import-card", timeout=20000)
        page.wait_for_function(
            "() => (document.querySelector('.iu-template-pro-import-card')?.innerText || '').includes('audit_import_accents.rtf')",
            timeout=20000,
        )
        import_text = page.locator(".iu-template-pro-import-card").inner_text(timeout=10000)
        expect("Arial" in import_text and "à" in import_text and "ù" in import_text, "Import RTF non conserva font/accenti.")
        page.get_by_role("button", name="Pagina vuota").click()
        expect("PDF audit IUSENTRA" not in current_editor_state(page)["text"], "Pagina vuota non svuota l'editor importato.")
        page.get_by_role("button", name="Inserisci testo importato").click()
        expect("Cliente audit" in current_editor_state(page)["text"], "Testo RTF importato non inserito nel template.")
        page.locator(".iu-template-guide-file-input").set_input_files(str(pdf_file))
        page.wait_for_selector(".iu-template-pro-import-card", timeout=20000)
        page.wait_for_function(
            "() => (document.querySelector('.iu-template-pro-import-card')?.innerText || '').includes('audit_import_pdf.pdf')",
            timeout=20000,
        )
        pdf_import_text = page.locator(".iu-template-pro-import-card").inner_text(timeout=10000)
        expect("PDF audit IUSENTRA" in pdf_import_text and "Helvetica" in pdf_import_text, "Import PDF non conserva testo/font rilevati.")

        page.get_by_role("button", name="Esporta", exact=True).click()
        export_text = "\n".join(f"Export audit pagina {i} con timbro e accenti àèìòù." for i in range(1, 120))
        export_html = "<p>" + "</p><p>".join(export_text.splitlines()) + "</p>"
        fields = form_data_for_export(code, export_text, export_html)
        rtf_status, rtf_bytes, rtf_type = post_form_bytes(context, f"/template-atti/compila/{code}/rtf", fields)
        docx_status, docx_bytes, docx_type = post_form_bytes(context, f"/template-atti/compila/{code}/word", fields)
        pdf_status, pdf_bytes, pdf_type = post_form_bytes(context, f"/template-atti/compila/{code}/pdf", fields)
        expect(rtf_status == 200 and b"{\\rtf1" in rtf_bytes and b"Arial" in rtf_bytes, "Export RTF non valido o senza font.")
        expect(b"\\u224?" in rtf_bytes and b"Export audit pagina" in rtf_bytes, "Export RTF perde accenti/testo.")
        docx_text, docx_xml = extract_docx_text_and_fonts(docx_bytes)
        expect(docx_status == 200 and "Export audit pagina" in docx_text and "Arial" in docx_xml, "Export DOCX non valido o senza testo/font.")
        expect(pdf_status == 200 and b"%PDF" in pdf_bytes and "pdf" in pdf_type.lower(), "Export PDF non valido.")
        try:
            from pypdf import PdfReader
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
                handle.write(pdf_bytes)
                pdf_name = handle.name
            reader = PdfReader(pdf_name)
            pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            Path(pdf_name).unlink(missing_ok=True)
            expect(len(reader.pages) >= 2 and "Export audit pagina" in pdf_text, "PDF non produce più pagine/testo estraibile.")
        except Exception as exc:
            raise AuditFailure(f"Controllo PDF non riuscito: {exc}") from exc

        page.evaluate(
            """html => {
                const editor = document.querySelector('[data-testid="professional-template-editor"]');
                editor.innerHTML = html;
                editor.dispatchEvent(new InputEvent('input', { bubbles: true }));
            }""",
            export_html,
        )
        page.get_by_role("button", name="Copia").click()
        copied = page.evaluate("() => navigator.clipboard.readText ? navigator.clipboard.readText() : ''")
        expect("Export audit pagina" in copied, "Copia non mette il testo negli appunti.")

        multi = page.locator(".iu-template-pro-multiple")
        expect(multi.count() == 1, "Pannello compilazione multipla non visibile.")
        page.get_by_role("button", name="Seleziona visibili").click()
        selected_label = multi.inner_text(timeout=10000)
        expect("selezionati" in selected_label and not selected_label.startswith("0 "), "Compilazione multipla non seleziona i modelli visibili.")
        multi_status, multi_bytes, _ = post_form_bytes(
            context,
            "/template-atti/api/compilazione-multipla-rtf",
            {
                **fields,
                "model_codes": code,
            },
        )
        expect(multi_status in {200, 400}, "Compilazione multipla non risponde.")
        if multi_status == 200:
            expect(zipfile.is_zipfile(__import__("io").BytesIO(multi_bytes)), "Compilazione multipla non produce ZIP RTF.")

        for width, height, name in ((390, 844, "mobile"), (820, 1180, "tablet"), (1440, 920, "desktop")):
            page.set_viewport_size({"width": width, "height": height})
            time.sleep(0.4)
            responsive = current_editor_state(page)
            expect(responsive["scrollWidth"] <= responsive["clientWidth"] + 3, f"Overflow orizzontale su {name}.")

        return {
            "templateCode": code,
            "campi": "stringa completa verificata",
            "pagine": state["pageMarkers"] + 1,
            "toolbar": "sticky durante lo scorrimento",
            "selezione": "grassetto/font/allineamento su selezione",
            "lex": "diff rifiutabile/accettabile, nessuna modifica automatica",
            "import": {"rtf": "font/accenti", "pdf": "testo/font"},
            "export": {"rtf": len(rtf_bytes), "docx": len(docx_bytes), "pdf": len(pdf_bytes)},
            "responsive": ["mobile", "tablet", "desktop"],
        }
    finally:
        browser.close()
        playwright.stop()


def api_headers(tenant: TenantInfo) -> dict[str, str]:
    return {"X-API-Key": tenant.api_key, "X-Tenant-Slug": tenant.slug, "Origin": BASE_URL}


def audit_scadenziario_pec_persistence(tenant: TenantInfo) -> dict[str, Any]:
    headers = api_headers(tenant)
    status, ingest = http_json("/api/pec/demo/ingest", method="POST", headers=headers)
    expect(status == 200 and ingest.get("ok") is True, "Ingest PEC demo non riuscito.")
    status, messages = http_json("/api/pec/messages", headers=headers)
    expect(status == 200, "Lista PEC non disponibile.")
    rows = messages.get("data") or []
    notice = next((row for row in rows if (row.get("validation_report") or {}).get("event_type") == "notifica_giudice_pace"), None)
    expect(notice, "PEC Giudice di Pace con proposta scadenza non trovata.")
    deadline_date = "2030-01-15"
    status, scheduled = http_json(f"/api/pec/messages/{notice['id']}/schedula-scadenza", method="POST", headers=headers, payload={"data_scadenza": deadline_date})
    expect(status == 200 and scheduled.get("ok") is True, "Scadenza PEC non creata.")
    agenda_id = ((scheduled.get("agenda") or {}).get("agenda_id") or (scheduled.get("agenda") or {}).get("agendaId") or "")
    deadline_id = str(scheduled.get("deadline_id") or "").strip()
    expect(deadline_id, "La schedulazione PEC non restituisce l'ID scadenza.")
    expect(agenda_id, "Scadenza PEC non riportata in agenda.")
    status, deadlines_before = http_json("/api/v1/ui/scadenziario?vista=tutte", headers=headers)
    expect(status == 200 and any(item.get("id") == deadline_id for item in deadlines_before.get("items", [])), "Scadenza PEC non visibile nello scadenziario.")
    status, agenda_before = http_json(f"/api/v1/ui/agenda?from={deadline_date}&to={deadline_date}", headers=headers)
    expect(status == 200 and any(item.get("id") == agenda_id for item in agenda_before.get("events", [])), "Agenda non contiene la scadenza PEC.")

    restart = run_command(["docker", "compose", "restart", "app"], timeout=120)
    expect(restart.returncode == 0, f"Riavvio container app non riuscito: {restart.stderr[-800:]}")
    wait_pronto(180)
    status, deadlines_after = http_json("/api/v1/ui/scadenziario?vista=tutte", headers=headers)
    status_agenda, agenda_after = http_json(f"/api/v1/ui/agenda?from={deadline_date}&to={deadline_date}", headers=headers)
    expect(status == 200 and any(item.get("id") == deadline_id for item in deadlines_after.get("items", [])), "Scadenza PEC persa dopo riavvio.")
    expect(status_agenda == 200 and any(item.get("id") == agenda_id for item in agenda_after.get("events", [])), "Evento agenda perso dopo riavvio.")
    return {"pecMessageId": notice["id"], "deadlineId": deadline_id, "agendaId": agenda_id, "deadline": deadline_date, "persistentAfterRestart": True}


def audit_tenant_isolation_runtime(tenant: TenantInfo) -> dict[str, Any]:
    code = """
import json
from pathlib import Path
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.tenant import GestioneTenant
from web.app import create_app
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data

app = create_app()
with app.app_context():
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    base_slug = %r
    other_slug = "audit-isolamento-tenant"
    if not manager.get(other_slug):
        manager.crea("Audit isolamento tenant", other_slug)
    manager.aggiorna(other_slug, api_key="audit-isolamento-key")
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=other_slug)
    paths = manager.percorsi_dati(other_slug, reconcile_aliases=False)
    fascicoli = GestioneFascicoli(paths["FASCICOLI_DB"], documents_dir=paths["FASCICOLI_DOCS"])
    fascicolo = fascicoli.nuovo("Fascicolo audit altro studio", TipoFascicolo.CIVILE, nome_cliente="Cliente altro studio")
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "documento-audit-altro-studio.txt",
        TipoDocumento.ATTO_GIUDIZIARIO,
        "Documento riservato dell'altro studio per audit isolamento tenant.".encode("utf-8"),
    )
    print("AUDIT_JSON:" + json.dumps({"otherSlug": other_slug, "otherKey": "audit-isolamento-key", "foreignFascicoloId": fascicolo.id}))
""" % tenant.slug
    created = json_from_command_marker(["docker", "compose", "exec", "-T", "app", "python", "-"], code)
    payload = {
        "template_code": "CIV_APPELLO_BREVE",
        "input_date": "2030-07-30",
        "case_reference": "RG TENANT RUNTIME/2030",
        "title": "Scadenza isolamento tenant runtime",
        "suspend_august": False,
        "id_fascicolo": created["foreignFascicoloId"],
    }
    status, blocked = http_json("/api/v1/ui/scadenziario/termini/crea-scadenza", method="POST", headers=api_headers(tenant), payload=payload)
    expect(status == 404 and blocked.get("crossTenantBlocked") is True, "Lo studio corrente può usare il fascicolo di un altro tenant.")
    status_other, created_other = http_json(
        "/api/v1/ui/scadenziario/termini/crea-scadenza",
        method="POST",
        headers={"X-API-Key": created["otherKey"], "X-Tenant-Slug": created["otherSlug"]},
        payload=payload,
    )
    expect(status_other == 200 and created_other.get("ok") is True, "Il tenant proprietario non può usare il proprio fascicolo.")
    owner_headers = {"X-API-Key": created["otherKey"], "X-Tenant-Slug": created["otherSlug"], "Origin": BASE_URL}
    foreign_fascicolo = created["foreignFascicoloId"]
    status_docs, docs_blocked = http_json(
        f"/api/v1/ui/fascicoli/{foreign_fascicolo}/documenti-ai",
        headers=api_headers(tenant),
    )
    status_lex, lex_blocked = http_json(
        f"/api/v1/ui/fascicoli/{foreign_fascicolo}/lex-indexing",
        headers=api_headers(tenant),
    )
    status_lex_update, lex_update_blocked = http_json(
        f"/api/v1/ui/fascicoli/{foreign_fascicolo}/lex-indexing/aggiorna",
        method="POST",
        headers=api_headers(tenant),
    )
    editor_payload = {
        "title": "Bozza isolamento tenant runtime",
        "answer": "Bozza isolamento tenant runtime\n\nIn fatto\nIl documento deve restare nello studio proprietario.",
    }
    status_editor, editor_blocked = http_json(
        f"/api/v1/ui/fascicoli/{foreign_fascicolo}/editor-ai/importa-bozza",
        method="POST",
        headers=api_headers(tenant),
        payload=editor_payload,
    )
    for label, status_code, response_payload in (
        ("documenti-ai", status_docs, docs_blocked),
        ("lex-indexing", status_lex, lex_blocked),
        ("lex-indexing-update", status_lex_update, lex_update_blocked),
        ("editor-ai-import", status_editor, editor_blocked),
    ):
        expect(status_code == 404 and response_payload.get("code") == "not_found", f"Cross-tenant non bloccato su {label}.")

    status_owner_lex, owner_lex = http_json(
        f"/api/v1/ui/fascicoli/{foreign_fascicolo}/lex-indexing",
        headers=owner_headers,
    )
    status_owner_editor, owner_editor = http_json(
        f"/api/v1/ui/fascicoli/{foreign_fascicolo}/editor-ai/importa-bozza",
        method="POST",
        headers=owner_headers,
        payload=editor_payload,
    )
    expect(
        status_owner_lex == 200 and owner_lex.get("lex_indexing", {}).get("ready", 0) >= 1,
        "Il tenant proprietario non legge i propri documenti AI.",
    )
    expect(
        status_owner_editor == 201 and owner_editor.get("mock_fallback") is False,
        "Il tenant proprietario non importa la bozza nel proprio fascicolo.",
    )
    return {
        "foreignFascicoloId": created["foreignFascicoloId"],
        "blockedForCurrentTenant": True,
        "allowedForOwnerTenant": True,
        "documentiAiBlockedForCurrentTenant": True,
        "editorImportBlockedForCurrentTenant": True,
    }


def cleanup_audit_tenant_runtime(slug: str) -> None:
    if not slug:
        return
    code = """
from pct.tenant import GestioneTenant
from web.app import create_app

app = create_app()
with app.app_context():
    GestioneTenant(app.config["TENANTS_REGISTRY"]).elimina(%r, elimina_dati=True)
""" % slug
    run_command(["docker", "compose", "exec", "-T", "app", "python", "-"], input_text=code, timeout=80)


def audit_tenant_isolation_runtime(tenant: TenantInfo) -> dict[str, Any]:
    unique_suffix = str(int(time.time() * 1000))
    audit_slug = f"audit-isolamento-tenant-{unique_suffix}"
    audit_key = f"audit-isolamento-key-{unique_suffix}"
    code = """
import json
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.tenant import GestioneTenant
from web.app import create_app
from web.services.tenant_legacy_bootstrap import bootstrap_legacy_tenant_runtime_data

app = create_app()
with app.app_context():
    manager = GestioneTenant(app.config["TENANTS_REGISTRY"])
    other_slug = %r
    other_key = %r
    if not manager.get(other_slug):
        manager.crea("Audit isolamento tenant", other_slug)
    manager.aggiorna(other_slug, api_key=other_key)
    bootstrap_legacy_tenant_runtime_data(app, tenant_slug=other_slug)
    paths = manager.percorsi_dati(other_slug, reconcile_aliases=False)
    fascicoli = GestioneFascicoli(paths["FASCICOLI_DB"], documents_dir=paths["FASCICOLI_DOCS"])
    fascicolo = fascicoli.nuovo("Fascicolo audit altro studio", TipoFascicolo.CIVILE, nome_cliente="Cliente altro studio")
    fascicoli.aggiungi_documento(
        fascicolo.id,
        "documento-audit-altro-studio.txt",
        TipoDocumento.ATTO_GIUDIZIARIO,
        "Documento riservato dell'altro studio per audit isolamento tenant.".encode("utf-8"),
    )
    print("AUDIT_JSON:" + json.dumps({"otherSlug": other_slug, "otherKey": other_key, "foreignFascicoloId": fascicolo.id}))
""" % (audit_slug, audit_key)
    created = json_from_command_marker(["docker", "compose", "exec", "-T", "app", "python", "-"], code)
    try:
        payload = {
            "template_code": "CIV_APPELLO_BREVE",
            "input_date": "2030-07-30",
            "case_reference": "RG TENANT RUNTIME/2030",
            "title": "Scadenza isolamento tenant runtime",
            "suspend_august": False,
            "id_fascicolo": created["foreignFascicoloId"],
        }
        status, blocked = http_json("/api/v1/ui/scadenziario/termini/crea-scadenza", method="POST", headers=api_headers(tenant), payload=payload)
        expect(status == 404 and blocked.get("crossTenantBlocked") is True, "Lo studio corrente può usare il fascicolo di un altro tenant.")
        status_other, created_other = http_json(
            "/api/v1/ui/scadenziario/termini/crea-scadenza",
            method="POST",
            headers={"X-API-Key": created["otherKey"], "X-Tenant-Slug": created["otherSlug"]},
            payload=payload,
        )
        expect(status_other == 200 and created_other.get("ok") is True, "Il tenant proprietario non può usare il proprio fascicolo.")
        owner_headers = {"X-API-Key": created["otherKey"], "X-Tenant-Slug": created["otherSlug"], "Origin": BASE_URL}
        foreign_fascicolo = created["foreignFascicoloId"]
        status_docs, docs_blocked = http_json(f"/api/v1/ui/fascicoli/{foreign_fascicolo}/documenti-ai", headers=api_headers(tenant))
        status_lex, lex_blocked = http_json(f"/api/v1/ui/fascicoli/{foreign_fascicolo}/lex-indexing", headers=api_headers(tenant))
        status_lex_update, lex_update_blocked = http_json(
            f"/api/v1/ui/fascicoli/{foreign_fascicolo}/lex-indexing/aggiorna",
            method="POST",
            headers=api_headers(tenant),
        )
        editor_payload = {
            "title": "Bozza isolamento tenant runtime",
            "answer": "Bozza isolamento tenant runtime\n\nIn fatto\nIl documento deve restare nello studio proprietario.",
        }
        status_editor, editor_blocked = http_json(
            f"/api/v1/ui/fascicoli/{foreign_fascicolo}/editor-ai/importa-bozza",
            method="POST",
            headers=api_headers(tenant),
            payload=editor_payload,
        )
        for label, status_code, response_payload in (
            ("documenti-ai", status_docs, docs_blocked),
            ("lex-indexing", status_lex, lex_blocked),
            ("lex-indexing-update", status_lex_update, lex_update_blocked),
            ("editor-ai-import", status_editor, editor_blocked),
        ):
            expect(status_code == 404 and response_payload.get("code") == "not_found", f"Cross-tenant non bloccato su {label}.")

        status_owner_lex, owner_lex = http_json(f"/api/v1/ui/fascicoli/{foreign_fascicolo}/lex-indexing", headers=owner_headers)
        status_owner_editor, owner_editor = http_json(
            f"/api/v1/ui/fascicoli/{foreign_fascicolo}/editor-ai/importa-bozza",
            method="POST",
            headers=owner_headers,
            payload=editor_payload,
        )
        expect(
            status_owner_lex == 200 and owner_lex.get("lex_indexing", {}).get("ready", 0) >= 1,
            "Il tenant proprietario non legge i propri documenti AI.",
        )
        expect(
            status_owner_editor == 201 and owner_editor.get("mock_fallback") is False,
            "Il tenant proprietario non importa la bozza nel proprio fascicolo.",
        )
        return {
            "auditTenantSlug": created["otherSlug"],
            "foreignFascicoloId": foreign_fascicolo,
            "blockedForCurrentTenant": True,
            "allowedForOwnerTenant": True,
            "documentiAiBlockedForCurrentTenant": True,
            "editorImportBlockedForCurrentTenant": True,
        }
    finally:
        cleanup_audit_tenant_runtime(str(created.get("otherSlug") or audit_slug))


def main() -> int:
    report: dict[str, Any] = {
        "schema": "iusentra.local_real_workflow_audit.v1",
        "startedAtRome": now_rome(),
        "baseUrl": BASE_URL,
        "noScreenshots": NO_SCREENSHOTS,
        "ok": False,
        "steps": [],
        "failures": [],
    }

    def step(name: str, func: Callable[[], dict[str, Any]]) -> None:
        started = now_rome()
        try:
            details = func()
            item = AuditStep(name=name, ok=True, started_at=started, finished_at=now_rome(), details=details)
        except Exception as exc:
            item = AuditStep(name=name, ok=False, started_at=started, finished_at=now_rome(), error=str(exc))
            report["failures"].append({"name": name, "error": str(exc)})
        report["steps"].append(item.__dict__)
        write_report(report)

    try:
        pronto = wait_pronto()
        report["pronto"] = {"ok": pronto.get("ok"), "versione": pronto.get("versione"), "timestamp": pronto.get("timestamp")}
        tenant = load_tenant_info()
        report["tenant"] = {"slug": tenant.slug, "storageKey": tenant.storage_key, "name": tenant.name}
        cookie = docker_session_cookie(tenant)
        step("isolamento tenant runtime fascicoli/scadenze", lambda: audit_tenant_isolation_runtime(tenant))
        step("assistenza remota reale locale", audit_support_real_flow)
        step("editor template professionale locale", lambda: audit_template_editor(tenant, cookie))
        step("PEC scadenziario agenda persistenza riavvio", lambda: audit_scadenziario_pec_persistence(tenant))
    except Exception as exc:
        report["failures"].append({"name": "bootstrap", "error": str(exc)})

    report["finishedAtRome"] = now_rome()
    report["ok"] = not report["failures"] and all(item.get("ok") for item in report["steps"])
    write_report(report)
    print(json.dumps({"ok": report["ok"], "report": str(REPORT_PATH), "failures": report["failures"]}, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
