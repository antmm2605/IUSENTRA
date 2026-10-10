"""Revisione italiana sul solo loopback: nessun testo raggiunge servizi esterni."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

_URL = "http://127.0.0.1:8091"


def _richiesta(percorso: str, dati: dict | None = None) -> dict:
    richiesta = Request(_URL + percorso, data=urlencode(dati).encode() if dati else None)
    with build_opener(ProxyHandler({})).open(richiesta, timeout=35) as risposta:
        return json.load(risposta)


def _avvia() -> None:
    import fcntl

    # Lock condiviso fra worker; il server ascolta soltanto il loopback del container.
    with open(f"/tmp/iusentra-editor-language-{os.getuid()}.lock", "a") as blocco:
        fcntl.flock(blocco, fcntl.LOCK_EX)
        try:
            _richiesta("/v2/languages")
            return
        except OSError:
            pass
        archivio = Path("/opt/iusentra/languagetool/languagetool-server.jar")
        if not archivio.is_file():
            raise RuntimeError("Revisore italiano locale non installato.")
        processo = subprocess.Popen(
            ["java", "-Xmx512m", "-cp", str(archivio),
             "org.languagetool.server.HTTPServer", "--port", "8091"],
            cwd=archivio.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, env={**os.environ, "JAVA_TOOL_OPTIONS": ""},
        )
        for _ in range(100):
            if processo.poll() is not None:
                raise RuntimeError("Avvio del revisore italiano non riuscito.")
            try:
                _richiesta("/v2/languages")
                return
            except OSError:
                time.sleep(0.2)
        processo.terminate()
        raise RuntimeError("Avvio del revisore italiano oltre il tempo consentito.")


def controlla_documento(testo: str) -> list[dict]:
    if not isinstance(testo, str) or not testo.strip() or len(testo) > 200000:
        raise ValueError("Il controllo accetta documenti fino a 200.000 caratteri.")
    _avvia()
    esiti = []
    inizio = 0
    # Nessun paragrafo viene omesso; offset UTF-16 uguali a quelli del browser.
    while inizio < len(testo):
        fine = min(inizio + 18000, len(testo))
        if fine < len(testo):
            confine = testo.rfind("\n\n", inizio + 9000, fine)
            if confine >= 0:
                fine = confine + 2
        parte = testo[inizio:fine]
        base = len(testo[:inizio].encode("utf-16-le")) // 2
        risposta = _richiesta("/v2/check", {"language": "it", "text": parte})
        for errore in risposta.get("matches", []):
            esiti.append({
                "offset": base + errore["offset"], "length": errore["length"],
                "messaggio": errore["message"],
                "suggerimenti": [r["value"] for r in errore.get("replacements", [])][:8],
                "regola": errore["rule"]["id"],
                "categoria": errore["rule"].get("category", {}).get("name", "Lingua italiana"),
            })
        inizio = fine
    return esiti
