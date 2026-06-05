"""Dominio e helper condivisi per l'assistenza remota cliente."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import argparse
import ctypes
import io
import platform
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


SUPPORT_STATUS_LABELS: dict[str, str] = {
    "created": "Creata",
    "waiting_operator": "In attesa operatore",
    "waiting_client": "In attesa cliente",
    "waiting_peer": "In attesa dell'altra parte",
    "active": "Attiva",
    "closed": "Chiusa",
}
DEFAULT_SUPPORT_STUN_URLS: tuple[str, ...] = ("stun:stun.l.google.com:19302",)
SUPPORT_PC_AGENT_NAME = "IUSENTRA Support Remote Agent"
SUPPORT_PC_AGENT_VERSION = "1.0"
SUPPORT_PC_AGENT_DEFAULT_HOST = "127.0.0.1"
SUPPORT_PC_AGENT_DEFAULT_PORT = 27273
SUPPORT_PC_AGENT_DEFAULT_TTL_SECONDS = 30 * 60
SUPPORT_PC_AGENT_ALLOWED_ORIGINS: tuple[str, ...] = (
    "https://app.iusentra.it",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


def derive_support_repository_db_path(anchor_path: str) -> str:
    anchor = Path(str(anchor_path or "")).resolve()
    if anchor.suffix.lower() == ".json":
        root = anchor.parent.parent
    else:
        root = anchor.parent
    return str((root / "support" / "assistenza_remota.db").resolve())


def generate_support_public_id() -> str:
    return str(uuid4())


def generate_support_client_token() -> str:
    return secrets.token_urlsafe(32)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.secret_key,
        salt="support-room-operator-token",
    )


def issue_operator_token(public_id: str, actor_name: str, operator_id: str = "") -> str:
    return _serializer().dumps(
        {
            "public_id": str(public_id or ""),
            "role": "operator",
            "actor": str(actor_name or "Operatore"),
            "operator_id": str(operator_id or ""),
        }
    )


def verify_operator_token(public_id: str, token: str) -> dict[str, Any] | None:
    if not token:
        return None

    try:
        payload = _serializer().loads(
            token,
            max_age=int(current_app.config.get("SUPPORT_WS_TOKEN_MAX_AGE", 43200)),
        )
    except (BadSignature, SignatureExpired):
        return None

    if str(payload.get("public_id") or "") != str(public_id or ""):
        return None
    if str(payload.get("role") or "") != "operator":
        return None
    return dict(payload)


def normalize_ice_url_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(";", ",").replace("\n", ",").split(",")
    else:
        raw_items = list(value or [])
    return [str(item).strip() for item in raw_items if str(item).strip()]


def default_support_stun_urls() -> list[str]:
    return list(DEFAULT_SUPPORT_STUN_URLS)


def build_ice_servers(subject: str) -> list[dict[str, Any]]:
    servers: list[dict[str, Any]] = []
    stun_urls = normalize_ice_url_list(current_app.config.get("SUPPORT_STUN_URLS", [])) or default_support_stun_urls()
    for stun_url in stun_urls:
        servers.append({"urls": [str(stun_url)]})

    turn_urls = normalize_ice_url_list(current_app.config.get("SUPPORT_TURN_URLS", []))
    shared_secret = str(current_app.config.get("SUPPORT_TURN_SHARED_SECRET", "") or "").strip()
    ttl = int(current_app.config.get("SUPPORT_TURN_TTL_SECONDS", 3600) or 3600)
    if turn_urls and shared_secret:
        expiry = int(time.time()) + ttl
        username = f"{expiry}:{subject}"
        digest = hmac.new(
            shared_secret.encode("utf-8"),
            username.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        credential = base64.b64encode(digest).decode("utf-8")
        servers.append(
            {
                "urls": turn_urls,
                "username": username,
                "credential": credential,
            }
        )
    return servers


def build_advanced_url(public_id: str) -> str:
    template = str(current_app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE", "") or "").strip()
    if not template:
        return ""
    return template.format(public_id=public_id)


def support_status_label(status: str) -> str:
    normalized = str(status or "").strip().lower()
    return SUPPORT_STATUS_LABELS.get(normalized, normalized.replace("_", " ").title() or "Sconosciuta")


def safe_json_payload(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)


def parse_json_payload(payload_json: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(str(payload_json or "{}"))
    except Exception:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def build_support_event_story(
    event_type: str,
    *,
    actor_role: str = "",
    actor_name: str = "",
    payload: dict[str, Any] | None = None,
) -> str:
    data = payload or {}
    nome = str(actor_name or actor_role or "Sistema").strip() or "Sistema"
    event = str(event_type or "").strip().lower()

    if event == "session_created":
        studio_nome = str(data.get("studio_nome") or "").strip()
        practice_label = str(data.get("practice_label") or "").strip()
        customer_name = str(data.get("customer_name") or "").strip()
        parts = [f"{nome} ha aperto una nuova sessione di assistenza remota"]
        if customer_name:
            parts.append(f"per {customer_name}")
        if practice_label:
            parts.append(f"sulla pratica {practice_label}")
        elif studio_nome:
            parts.append(f"per lo studio {studio_nome}")
        return " ".join(parts).strip() + "."
    if event == "studio_support_requested":
        studio_nome = str(data.get("studio_nome") or "").strip()
        practice_label = str(data.get("practice_label") or "").strip()
        parts = [f"{nome} ha richiesto assistenza remota dallo studio"]
        if practice_label:
            parts.append(f"per {practice_label}")
        elif studio_nome:
            parts.append(f"{studio_nome}")
        return " ".join(parts).strip() + "."
    if event == "customer_room_opened":
        return f"{nome} ha aperto il link cliente e ha raggiunto la stanza di assistenza."
    if event == "operator_room_opened":
        return f"{nome} ha aperto la stanza operatore dalla cabina piattaforma."
    if event == "peer_connected":
        return f"{nome} si è collegato alla stanza WebRTC."
    if event == "peer_disconnected":
        return f"{nome} si è scollegato dalla stanza WebRTC."
    if event == "consent_updated":
        consensi: list[str] = []
        if data.get("consent_screen"):
            consensi.append("schermo")
        if data.get("consent_audio"):
            consensi.append("audio")
        if data.get("consent_chat"):
            consensi.append("chat")
        if not consensi:
            return f"{nome} ha revocato tutti i consensi iniziali della sessione."
        return f"{nome} ha autorizzato {', '.join(consensi)} per l'assistenza remota."
    if event == "session_started":
        return f"{nome} ha avviato la sessione operativa."
    if event == "advanced_control_requested":
        return f"{nome} ha richiesto il controllo remoto del PC cliente."
    if event == "advanced_control_approved":
        return f"{nome} ha approvato il controllo remoto del PC cliente."
    if event == "advanced_control_rejected":
        return f"{nome} ha rifiutato il controllo remoto del PC cliente."
    if event == "advanced_control_reset":
        return f"{nome} ha azzerato la richiesta di controllo remoto del PC cliente."
    if event == "note_updated":
        return f"{nome} ha aggiornato le note finali della sessione."
    if event == "session_closed":
        return f"{nome} ha chiuso la sessione di assistenza remota."
    if event == "webrtc_error":
        detail = str(data.get("detail") or "").strip()
        if detail:
            return f"{nome} ha segnalato un errore WebRTC: {detail}."
        return f"{nome} ha segnalato un errore WebRTC."
    return f"{nome} ha eseguito l'azione {event_type}."


class RemoteControlError(RuntimeError):
    pass


@dataclass
class ArmedSession:
    session_id: str
    token: str
    expires_at: float
    allow_control: bool = True


class AgentState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._armed: dict[str, ArmedSession] = {}

    def arm(
        self,
        session_id: str,
        token: str,
        ttl_seconds: int = SUPPORT_PC_AGENT_DEFAULT_TTL_SECONDS,
        allow_control: bool = True,
    ) -> ArmedSession:
        if not session_id or not token:
            raise RemoteControlError("session_id e token sono obbligatori.")
        ttl = max(60, min(int(ttl_seconds or SUPPORT_PC_AGENT_DEFAULT_TTL_SECONDS), 8 * 60 * 60))
        armed = ArmedSession(
            session_id=session_id,
            token=token,
            expires_at=time.time() + ttl,
            allow_control=bool(allow_control),
        )
        with self._lock:
            self._armed[session_id] = armed
        return armed

    def disarm(self, session_id: str, token: str) -> None:
        with self._lock:
            armed = self._armed.get(session_id)
            if armed and secrets.compare_digest(armed.token, token):
                self._armed.pop(session_id, None)

    def require(self, session_id: str, token: str, *, require_control: bool = False) -> ArmedSession:
        with self._lock:
            armed = self._armed.get(session_id)
            if not armed:
                raise RemoteControlError("Sessione PC non autorizzata.")
            if armed.expires_at < time.time():
                self._armed.pop(session_id, None)
                raise RemoteControlError("Autorizzazione PC scaduta.")
            if not secrets.compare_digest(armed.token, token):
                raise RemoteControlError("Token PC non valido.")
            if require_control and not armed.allow_control:
                raise RemoteControlError("Controllo PC non autorizzato dal cliente.")
            return armed

    def active_count(self) -> int:
        now = time.time()
        with self._lock:
            for key, armed in list(self._armed.items()):
                if armed.expires_at < now:
                    self._armed.pop(key, None)
            return len(self._armed)


SUPPORT_PC_AGENT_STATE = AgentState()


def _support_pc_is_windows() -> bool:
    return platform.system().lower() == "windows"


def _support_pc_screen_size() -> tuple[int, int]:
    if not _support_pc_is_windows():
        return 0, 0
    user32 = ctypes.windll.user32
    return int(user32.GetSystemMetrics(SM_CXSCREEN)), int(user32.GetSystemMetrics(SM_CYSCREEN))


def _support_pc_virtual_screen_geometry() -> dict[str, int]:
    if not _support_pc_is_windows():
        return {"x": 0, "y": 0, "width": 0, "height": 0}

    user32 = ctypes.windll.user32
    x = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    y = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    if width <= 0 or height <= 0:
        width, height = _support_pc_screen_size()
        x = 0
        y = 0
    return {"x": x, "y": y, "width": max(width, 0), "height": max(height, 0)}


def _support_pc_command_ratio(value: Any) -> float:
    try:
        ratio = float(value if value is not None else 0)
    except (TypeError, ValueError) as exc:
        raise RemoteControlError("Coordinate comando PC non valide.") from exc
    return max(0.0, min(1.0, ratio))


def _support_pc_mouse_event(flags: int) -> None:
    ctypes.windll.user32.mouse_event(flags, 0, 0, 0, 0)


def _support_pc_move_pointer(x: int, y: int) -> None:
    if not ctypes.windll.user32.SetCursorPos(int(x), int(y)):
        raise RemoteControlError("Impossibile muovere il puntatore.")


def _support_pc_click(button: str = "left", double: bool = False) -> None:
    down, up = (0x0008, 0x0010) if button == "right" else (0x0002, 0x0004)
    for _ in range(2 if double else 1):
        _support_pc_mouse_event(down)
        time.sleep(0.03)
        _support_pc_mouse_event(up)
        time.sleep(0.06)


ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", INPUTUNION)]


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_CODES = {
    "Enter": 0x0D,
    "Tab": 0x09,
    "Escape": 0x1B,
    "Backspace": 0x08,
    "Delete": 0x2E,
    "ArrowLeft": 0x25,
    "ArrowUp": 0x26,
    "ArrowRight": 0x27,
    "ArrowDown": 0x28,
    "Home": 0x24,
    "End": 0x23,
}


def _support_pc_key_input(vk: int, flags: int = 0, scan: int = 0) -> INPUT:
    return INPUT(type=INPUT_KEYBOARD, union=INPUTUNION(ki=KEYBDINPUT(vk, scan, flags, 0, 0)))


def _support_pc_send_inputs(inputs: list[INPUT]) -> None:
    arr = (INPUT * len(inputs))(*inputs)
    send_input = ctypes.windll.user32.SendInput
    send_input.argtypes = (ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int)
    send_input.restype = ctypes.c_uint
    sent = send_input(len(inputs), arr, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        error_code = ctypes.windll.kernel32.GetLastError()
        raise RemoteControlError(f"Invio input Windows non riuscito (codice {error_code}).")


def _support_pc_send_key(key: str) -> None:
    if key not in VK_CODES:
        raise RemoteControlError(f"Tasto non supportato: {key}")
    vk = VK_CODES[key]
    _support_pc_send_inputs([_support_pc_key_input(vk), _support_pc_key_input(vk, KEYEVENTF_KEYUP)])


def _support_pc_send_text(text: str) -> int:
    inputs: list[INPUT] = []
    for char in text:
        scan = ord(char)
        inputs.append(_support_pc_key_input(0, KEYEVENTF_UNICODE, scan))
        inputs.append(_support_pc_key_input(0, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, scan))
    if inputs:
        _support_pc_send_inputs(inputs)
    return len(text)


def _support_pc_capture_screen(max_width: int = 1600, quality: int = 55) -> dict[str, Any]:
    if not _support_pc_is_windows():
        raise RemoteControlError("Visualizzazione schermo reale disponibile su Windows.")
    try:
        from PIL import ImageGrab
    except Exception as exc:  # pragma: no cover - dipendenza runtime locale
        raise RemoteControlError("Cattura schermo non disponibile: installa Pillow nell'ambiente locale.") from exc

    geometry = _support_pc_virtual_screen_geometry()
    image = ImageGrab.grab(all_screens=True)
    original_width, original_height = image.size
    max_width = max(480, min(int(max_width or 1600), 2400))
    if original_width > max_width:
        target_height = max(1, int(original_height * (max_width / original_width)))
        image = image.resize((max_width, target_height))
    if image.mode != "RGB":
        image = image.convert("RGB")

    quality = max(35, min(int(quality or 55), 85))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return {
        "ok": True,
        "width": original_width,
        "height": original_height,
        "screen": geometry,
        "x": geometry["x"],
        "y": geometry["y"],
        "virtual_width": geometry["width"],
        "virtual_height": geometry["height"],
        "preview_width": image.size[0],
        "preview_height": image.size[1],
        "captured_at": time.time(),
        "image": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
    }


def execute_command(command: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    action = str(command.get("action") or "").strip().lower()
    if not action:
        raise RemoteControlError("Azione mancante.")
    if dry_run:
        return {"ok": True, "dry_run": True, "action": action}
    if not _support_pc_is_windows():
        raise RemoteControlError("Controllo PC reale disponibile su Windows.")
    if action in {"click", "double_click"}:
        geometry = _support_pc_virtual_screen_geometry()
        width = geometry["width"]
        height = geometry["height"]
        if width <= 0 or height <= 0:
            raise RemoteControlError("Dimensione schermo PC non disponibile.")
        min_x = geometry["x"]
        min_y = geometry["y"]
        max_x = min_x + width - 1
        max_y = min_y + height - 1
        x = min_x + int(_support_pc_command_ratio(command.get("x_ratio")) * max(width - 1, 1))
        y = min_y + int(_support_pc_command_ratio(command.get("y_ratio")) * max(height - 1, 1))
        _support_pc_move_pointer(max(min_x, min(x, max_x)), max(min_y, min(y, max_y)))
        _support_pc_click(str(command.get("button") or "left").lower(), double=action == "double_click")
        return {"ok": True, "action": action}
    if action == "text":
        return {"ok": True, "action": action, "chars": _support_pc_send_text(str(command.get("text") or ""))}
    if action == "key":
        key = str(command.get("key") or "")
        _support_pc_send_key(key)
        return {"ok": True, "action": action, "key": key}
    raise RemoteControlError(f"Azione non supportata: {action}")


def _support_pc_allowed_origin(origin: str) -> str:
    raw = str(origin or "").strip()
    for allowed in SUPPORT_PC_AGENT_ALLOWED_ORIGINS:
        if secrets.compare_digest(raw, allowed):
            return allowed
    return ""


class SupportPcAgentRequestHandler(BaseHTTPRequestHandler):
    server_version = f"{SUPPORT_PC_AGENT_NAME}/{SUPPORT_PC_AGENT_VERSION}"

    def _headers(self, status: HTTPStatus = HTTPStatus.OK) -> None:
        origin = _support_pc_allowed_origin(self.headers.get("Origin", ""))
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        self._headers(status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            raise RemoteControlError("Payload JSON non valido.") from exc
        return payload if isinstance(payload, dict) else {}

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] == "/status":
            geometry = _support_pc_virtual_screen_geometry()
            self._send_json(
                {
                    "ok": True,
                    "agent": SUPPORT_PC_AGENT_NAME,
                    "version": SUPPORT_PC_AGENT_VERSION,
                    "platform": platform.system(),
                    "screen": geometry,
                    "screen_width": geometry["width"],
                    "screen_height": geometry["height"],
                    "armed_sessions": SUPPORT_PC_AGENT_STATE.active_count(),
                }
            )
            return
        self._send_json({"ok": False, "error": "Endpoint non trovato."}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            payload = self._read_json()
            session_id = str(payload.get("session_id") or "").strip()
            token = str(payload.get("token") or "").strip()
            if path == "/arm":
                armed = SUPPORT_PC_AGENT_STATE.arm(
                    session_id,
                    token,
                    int(payload.get("ttl_seconds") or SUPPORT_PC_AGENT_DEFAULT_TTL_SECONDS),
                    allow_control=bool(payload.get("control", True)),
                )
                self._send_json({"ok": True, "expires_at": armed.expires_at, "control": armed.allow_control})
                return
            if path == "/disarm":
                SUPPORT_PC_AGENT_STATE.disarm(session_id, token)
                self._send_json({"ok": True})
                return
            if path == "/screenshot":
                SUPPORT_PC_AGENT_STATE.require(session_id, token)
                self._send_json(
                    _support_pc_capture_screen(
                        max_width=int(payload.get("max_width") or 1600),
                        quality=int(payload.get("quality") or 55),
                    )
                )
                return
            if path == "/execute":
                SUPPORT_PC_AGENT_STATE.require(session_id, token, require_control=True)
                result = execute_command(dict(payload.get("command") or {}), dry_run=bool(payload.get("dry_run")))
                self._send_json(result)
                return
            self._send_json({"ok": False, "error": "Endpoint non trovato."}, HTTPStatus.NOT_FOUND)
        except RemoteControlError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            self._send_json({"ok": False, "error": exc.__class__.__name__}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"[{SUPPORT_PC_AGENT_NAME}] {self.address_string()} - {fmt % args}\n")


def run_support_pc_agent(host: str = SUPPORT_PC_AGENT_DEFAULT_HOST, port: int = SUPPORT_PC_AGENT_DEFAULT_PORT) -> None:
    httpd = ThreadingHTTPServer((host, port), SupportPcAgentRequestHandler)
    print(f"{SUPPORT_PC_AGENT_NAME} in ascolto su http://{host}:{port}", flush=True)
    httpd.serve_forever()


def support_pc_agent_self_test() -> int:
    if not _support_pc_is_windows():
        print("SELF_TEST_SKIPPED piattaforma non Windows")
        return 0
    import tkinter as tk

    marker = f"IUSENTRA-E2E-{int(time.time())}"
    root = tk.Tk()
    root.title("IUSENTRA Support Remote Agent Self Test")
    root.geometry("520x160+120+120")
    entry = tk.Entry(root, font=("Segoe UI", 16))
    entry.pack(padx=24, pady=48, fill="x")
    root.update()
    entry.focus_force()
    root.update()
    _support_pc_move_pointer(root.winfo_rootx() + 90, root.winfo_rooty() + 78)
    _support_pc_click("left")
    _support_pc_send_text(marker)
    deadline = time.time() + 3
    ok = False
    while time.time() < deadline:
        root.update()
        if entry.get() == marker:
            ok = True
            break
        time.sleep(0.05)
    print(f"SELF_TEST_{'OK' if ok else 'FAILED'} marker={marker} value={entry.get()!r}")
    root.destroy()
    return 0 if ok else 1


def support_pc_agent_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=SUPPORT_PC_AGENT_NAME)
    parser.add_argument("--host", default=SUPPORT_PC_AGENT_DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=SUPPORT_PC_AGENT_DEFAULT_PORT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return support_pc_agent_self_test()
    run_support_pc_agent(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(support_pc_agent_main())
