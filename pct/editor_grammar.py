"""Revisione italiana sul solo loopback: nessun testo raggiunge servizi esterni."""
from __future__ import annotations

import json
import os
import re
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


_ABBREVIAZIONI = re.compile(
    r"\b(?:avv\.|dott\.ssa\b|dott\.|prof\.ssa\b|prof\.|cod\.\s*fisc\.|"
    r"artt?\.|d\.\s*lgs\.|c\.\s*p\.\s*c\.|c\.\s*f\.|r\.\s*g\.|n[°º])|"
    r"\b\d+\s*-\s*(?:bis|ter|quater)\b", re.I,
)
_RECAPITI = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://[^\s]+")
_ETICHETTE_TELEFONO = re.compile(r"\b(?:tel\.?|fax)\b(?=\.?\s*:?\s*\+?\d[\d ()-]{5,})", re.I)


def _intervalli_tecnici(testo: str) -> list[tuple[int, int]]:
    return [(len(testo[:m.start()].encode('utf-16-le')) // 2,
             len(testo[:m.end()].encode('utf-16-le')) // 2)
            for pattern in (_ABBREVIAZIONI, _RECAPITI, _ETICHETTE_TELEFONO) for m in pattern.finditer(testo)]


def controlla_documento(testo: str, *, termini_contesto=()) -> list[dict]:
    if not isinstance(testo, str) or not testo.strip():
        raise ValueError("Inserisci del testo prima di avviare il controllo.")
    if len(testo) > 200000:
        raise ValueError("Il controllo accetta documenti fino a 200.000 caratteri.")
    _avvia()
    # Solo termini presenti nei dati del procedimento, non tutti i campi del
    # modello: nazionalità e prosa restano controllate anche se auto-compilate.
    termini = {str(v).casefold() for v in termini_contesto} | {'cartabia'}
    tecnici = _intervalli_tecnici(testo)
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
            rule = errore['rule']
            offset = base + errore['offset']
            end = offset + errore['length']
            parola = parte.encode('utf-16-le')[errore['offset'] * 2:(errore['offset'] + errore['length']) * 2].decode('utf-16-le', errors='surrogatepass')
            # La d eufonica è una preferenza stilistica, non un errore del
            # modello. Non disabilitiamo le regole grammaticali del revisore.
            if rule['id'] in {'ST_03_001', 'WHITESPACE_RULE'}:
                continue
            if rule['id'] == 'MORFOLOGIK_RULE_IT_IT' and (
                parola.casefold() in termini or any(a <= offset and end <= b for a, b in tecnici)
            ):
                continue
            # La conversione conserva righe e rientri tipografici. Un nuovo
            # blocco senza fine frase non richiede una maiuscola né una nuova
            # frase: non cambiare l'impaginazione per soddisfare il revisore.
            prefix = testo.encode('utf-16-le')[:offset * 2].decode('utf-16-le', errors='surrogatepass')
            suffix = testo.encode('utf-16-le')[offset * 2:].decode('utf-16-le', errors='surrogatepass')
            if rule['id'] == 'UPPERCASE_SENTENCE_START' and re.match(r'promoss[oa]\s+da\s*:', suffix, re.I):
                continue
            if rule['id'] == 'UPPERCASE_SENTENCE_START' and prefix.rstrip() and not re.search(r'[.!?][»”\")]*$', prefix.rstrip()):
                continue
            esiti.append({
                "offset": offset, "length": errore["length"],
                "messaggio": errore["message"],
                "suggerimenti": [r["value"] for r in errore.get("replacements", [])][:8],
                "regola": errore["rule"]["id"],
                "categoria": errore["rule"].get("category", {}).get("name", "Lingua italiana"),
            })
        inizio = fine
    return esiti
