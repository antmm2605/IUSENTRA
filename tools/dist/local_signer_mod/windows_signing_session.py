"""Una sola chiave Windows aperta per il lotto; nessun PIN o documento su disco."""
from __future__ import annotations

import atexit
import base64
import json
import os
import queue
import re
import subprocess
import threading
from pathlib import Path

_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$rsa = $null
try {
  while ($null -ne ($line = [Console]::In.ReadLine())) {
    try {
      $request = $line | ConvertFrom-Json
      if (-not $rsa) {
        $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('My', 'CurrentUser')
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
        try { $cert = $store.Certificates.Find([System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint, $request.thumbprint, $false)[0] }
        finally { $store.Close() }
        if (-not $cert -or -not $cert.HasPrivateKey) { throw 'Certificato Windows con chiave privata non disponibile.' }
        $rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert)
        if (-not $rsa) { throw 'Chiave privata RSA non disponibile.' }
      }
      $signature = $rsa.SignData([Convert]::FromBase64String($request.payload), [System.Security.Cryptography.HashAlgorithmName]::SHA256, [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
      [Console]::Out.WriteLine((@{signature=[Convert]::ToBase64String($signature)} | ConvertTo-Json -Compress))
      [Console]::Out.Flush()
    } catch {
      [Console]::Out.WriteLine((@{error=$_.Exception.Message} | ConvertTo-Json -Compress))
      [Console]::Out.Flush()
      break
    }
  }
} finally { if ($rsa) { $rsa.Dispose() } }
"""


class WindowsSigningSession:
    def __init__(self, thumbprint: str, ttl: int = 1800):
        if not re.fullmatch(r"[0-9A-F]{40,128}", thumbprint):
            raise ValueError("Thumbprint del certificato Windows non valido.")
        self.thumbprint = thumbprint
        self.ttl = ttl
        self.lock = threading.RLock()
        self.timer = None
        self.responses = queue.Queue()
        executable = Path(os.getenv("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.process = subprocess.Popen(
            [str(executable), "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(_SCRIPT.encode("utf-16-le")).decode("ascii")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.process.stdout:
                self.responses.put(line)
        finally:
            self.responses.put(None)

    def sign(self, payload: bytes) -> bytes:
        with self.lock:
            if self.timer:
                self.timer.cancel()
            try:
                if self.process.poll() is not None:
                    raise RuntimeError("Sessione Windows terminata. Ripeti il comando di firma.")
                self.process.stdin.write(json.dumps({"thumbprint": self.thumbprint, "payload": base64.b64encode(payload).decode("ascii")}) + "\n")
                self.process.stdin.flush()
                response = self.responses.get(timeout=240)
                if response is None:
                    raise RuntimeError("Firma Windows interrotta dal dispositivo.")
                result = json.loads(response)
                if result.get("error"):
                    raise RuntimeError(result["error"])
                signature = base64.b64decode(result["signature"], validate=True)
                if not signature:
                    raise RuntimeError("Il dispositivo non ha restituito la firma.")
                self.timer = threading.Timer(self.ttl, self.close)
                self.timer.daemon = True
                self.timer.start()
                return signature
            except queue.Empty as exc:
                self.close()
                raise RuntimeError("Tempo esaurito per il PIN del dispositivo.") from exc
            except Exception:
                self.close()
                raise

    def close(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()


_sessions: dict[str, WindowsSigningSession] = {}
_lock = threading.RLock()


def sign_raw(thumbprint: str, payload: bytes) -> bytes:
    with _lock:
        session = _sessions.get(thumbprint)
        if session is None or session.process.poll() is not None:
            if session:
                session.close()
            if len(_sessions) >= 4:
                _sessions.pop(next(iter(_sessions))).close()
            session = _sessions[thumbprint] = WindowsSigningSession(thumbprint)
    return session.sign(payload)


@atexit.register
def close_sessions():
    with _lock:
        for session in _sessions.values():
            session.close()
        _sessions.clear()
