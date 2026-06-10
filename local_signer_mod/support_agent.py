"""Agente assistenza remota integrato nel Local Signer.

Espone su 127.0.0.1:27272 (porta Local Signer) gli stessi endpoint
dell'agente dedicato `pct/support_remote.py` (porta 27273), con prefisso
`/support/*`:

  GET  /support/status      -> stato agente + geometria schermo
  POST /support/arm         -> autorizza una sessione (token + TTL)
  POST /support/disarm      -> revoca l'autorizzazione
  POST /support/screenshot  -> cattura schermo JPEG base64 (Pillow)
  POST /support/execute     -> esegue comando mouse/tastiera (solo Windows)

Cosi' lo studio che ha gia' il Local Signer installato non deve installare
un secondo agente per l'assistenza remota: la stanza cliente prova prima
la porta 27273 e poi questa.

La sicurezza segue lo stesso modello dell'agente dedicato: ogni operazione
richiede `session_id` + `token` armati esplicitamente dal cliente nella
stanza assistenza (consenso nel browser), con scadenza TTL.
"""

from __future__ import annotations

import base64
import ctypes
import io
import platform
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

SUPPORT_AGENT_NAME = "IUSENTRA Assistenza (Local Signer)"
SUPPORT_AGENT_DEFAULT_TTL_SECONDS = 30 * 60

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class RemoteControlError(Exception):
    """Errore operativo del controllo remoto (mostrato al cliente)."""


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
        ttl_seconds: int = SUPPORT_AGENT_DEFAULT_TTL_SECONDS,
        allow_control: bool = True,
    ) -> ArmedSession:
        if not session_id or not token:
            raise RemoteControlError("session_id e token sono obbligatori.")
        ttl = max(60, min(int(ttl_seconds or SUPPORT_AGENT_DEFAULT_TTL_SECONDS), 8 * 60 * 60))
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


_STATE = AgentState()


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _screen_size() -> tuple[int, int]:
    if not _is_windows():
        return 0, 0
    user32 = ctypes.windll.user32
    return int(user32.GetSystemMetrics(SM_CXSCREEN)), int(user32.GetSystemMetrics(SM_CYSCREEN))


def _virtual_screen_geometry() -> dict[str, int]:
    if not _is_windows():
        return {"x": 0, "y": 0, "width": 0, "height": 0}
    user32 = ctypes.windll.user32
    x = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    y = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    if width <= 0 or height <= 0:
        width, height = _screen_size()
        x = 0
        y = 0
    return {"x": x, "y": y, "width": max(width, 0), "height": max(height, 0)}


def _command_ratio(value: Any) -> float:
    try:
        ratio = float(value if value is not None else 0)
    except (TypeError, ValueError) as exc:
        raise RemoteControlError("Coordinate comando PC non valide.") from exc
    return max(0.0, min(1.0, ratio))


def _mouse_event(flags: int) -> None:
    ctypes.windll.user32.mouse_event(flags, 0, 0, 0, 0)


def _move_pointer(x: int, y: int) -> None:
    if not ctypes.windll.user32.SetCursorPos(int(x), int(y)):
        raise RemoteControlError("Impossibile muovere il puntatore.")


def _click(button: str = "left", double: bool = False) -> None:
    down, up = (0x0008, 0x0010) if button == "right" else (0x0002, 0x0004)
    for _ in range(2 if double else 1):
        _mouse_event(down)
        time.sleep(0.03)
        _mouse_event(up)
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


def _key_input(vk: int, flags: int = 0, scan: int = 0) -> INPUT:
    return INPUT(type=INPUT_KEYBOARD, union=INPUTUNION(ki=KEYBDINPUT(vk, scan, flags, 0, 0)))


def _send_inputs(inputs: list[INPUT]) -> None:
    arr = (INPUT * len(inputs))(*inputs)
    send_input = ctypes.windll.user32.SendInput
    send_input.argtypes = (ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int)
    send_input.restype = ctypes.c_uint
    sent = send_input(len(inputs), arr, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        error_code = ctypes.windll.kernel32.GetLastError()
        raise RemoteControlError(f"Invio input Windows non riuscito (codice {error_code}).")


def _send_key(key: str) -> None:
    if key not in VK_CODES:
        raise RemoteControlError(f"Tasto non supportato: {key}")
    vk = VK_CODES[key]
    _send_inputs([_key_input(vk), _key_input(vk, KEYEVENTF_KEYUP)])


def _send_text(text: str) -> int:
    inputs: list[INPUT] = []
    for char in text:
        scan = ord(char)
        inputs.append(_key_input(0, KEYEVENTF_UNICODE, scan))
        inputs.append(_key_input(0, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, scan))
    if inputs:
        _send_inputs(inputs)
    return len(text)


def capture_screen(max_width: int = 1600, quality: int = 55) -> dict[str, Any]:
    if not _is_windows():
        raise RemoteControlError("Visualizzazione schermo reale disponibile su Windows.")
    try:
        from PIL import ImageGrab
    except Exception as exc:  # pragma: no cover - dipendenza runtime locale
        raise RemoteControlError("Cattura schermo non disponibile: installa Pillow nell'ambiente locale.") from exc

    geometry = _virtual_screen_geometry()
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


def execute_command(command: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    action = str(command.get("action") or "").strip().lower()
    if dry_run:
        return {"ok": True, "action": action, "dry_run": True}
    if not _is_windows():
        raise RemoteControlError("Controllo PC reale disponibile su Windows.")
    if action in {"click", "double_click"}:
        geometry = _virtual_screen_geometry()
        width = geometry["width"]
        height = geometry["height"]
        if width <= 0 or height <= 0:
            raise RemoteControlError("Risoluzione schermo non disponibile.")
        min_x = geometry["x"]
        min_y = geometry["y"]
        max_x = min_x + width - 1
        max_y = min_y + height - 1
        x = min_x + int(_command_ratio(command.get("x_ratio")) * max(width - 1, 1))
        y = min_y + int(_command_ratio(command.get("y_ratio")) * max(height - 1, 1))
        _move_pointer(max(min_x, min(x, max_x)), max(min_y, min(y, max_y)))
        _click(str(command.get("button") or "left").lower(), double=action == "double_click")
        return {"ok": True, "action": action}
    if action == "text":
        return {"ok": True, "action": action, "chars": _send_text(str(command.get("text") or ""))}
    if action == "key":
        key = str(command.get("key") or "")
        _send_key(key)
        return {"ok": True, "action": action, "key": key}
    raise RemoteControlError(f"Azione non supportata: {action}")


class SupportAgentFacade:
    """Adatta gli endpoint /support/* al request handler del Local Signer."""

    def __init__(self, *, read_json: Any, send_json: Any, logger: Any, version: str) -> None:
        self.read_json = read_json
        self.send_json = send_json
        self.logger = logger
        self.version = version

    def status(self) -> None:
        geometry = _virtual_screen_geometry()
        self.send_json(
            {
                "ok": True,
                "agent": SUPPORT_AGENT_NAME,
                "version": self.version,
                "platform": platform.system(),
                "screen": geometry,
                "screen_width": geometry["width"],
                "screen_height": geometry["height"],
                "armed_sessions": _STATE.active_count(),
            }
        )

    def _payload(self) -> tuple[dict[str, Any], str, str]:
        payload = self.read_json() or {}
        session_id = str(payload.get("session_id") or "").strip()
        token = str(payload.get("token") or "").strip()
        return payload, session_id, token

    def arm(self) -> None:
        try:
            payload, session_id, token = self._payload()
            armed = _STATE.arm(
                session_id,
                token,
                int(payload.get("ttl_seconds") or SUPPORT_AGENT_DEFAULT_TTL_SECONDS),
                allow_control=bool(payload.get("control", True)),
            )
            self.logger.info("Assistenza remota: sessione %s armata (controllo=%s)", session_id, armed.allow_control)
            self.send_json({"ok": True, "expires_at": armed.expires_at, "control": armed.allow_control})
        except RemoteControlError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 400)

    def disarm(self) -> None:
        _, session_id, token = self._payload()
        _STATE.disarm(session_id, token)
        self.logger.info("Assistenza remota: sessione %s disarmata", session_id)
        self.send_json({"ok": True})

    def screenshot(self) -> None:
        try:
            payload, session_id, token = self._payload()
            _STATE.require(session_id, token)
            self.send_json(
                capture_screen(
                    max_width=int(payload.get("max_width") or 1600),
                    quality=int(payload.get("quality") or 55),
                )
            )
        except RemoteControlError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:  # pragma: no cover - dipendenze runtime locali
            self.logger.error("Assistenza remota: screenshot fallito: %s", exc)
            self.send_json({"ok": False, "error": exc.__class__.__name__}, 500)

    def execute(self) -> None:
        try:
            payload, session_id, token = self._payload()
            _STATE.require(session_id, token, require_control=True)
            result = execute_command(dict(payload.get("command") or {}), dry_run=bool(payload.get("dry_run")))
            self.send_json(result)
        except RemoteControlError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:  # pragma: no cover - dipendenze runtime locali
            self.logger.error("Assistenza remota: comando fallito: %s", exc)
            self.send_json({"ok": False, "error": exc.__class__.__name__}, 500)
