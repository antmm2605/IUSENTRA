"""Pre-generazione delle pagine del sito pubblico dello studio (React ``renderToString`` eseguito da Node).

- Quando i contenuti del sito vengono salvati o pubblicati, si generano tutte le pagine pubbliche in un
  solo processo Node breve (limite di memoria V8, di CPU e di tempo) in un thread separato: la
  risposta all'avvocato non aspetta.
- L'HTML si salva su disco per sito, pagina e versione: la versione è l'impronta dei dati pubblici e del
  bundle di pre-generazione, quindi una pagina non è mai servita con contenuti superati.
- Alla richiesta del visitatore si legge solo la cache. Se manca (prima pubblicazione, salvataggio fatto
  per altra via) si genera la sola pagina richiesta, con un processo alla volta e tempi stretti; se
  nemmeno questo riesce, la pagina parte senza HTML pre-generato e React la disegna nel browser.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any

from web.services.sito_pubblico_dati import chiave_pagina

LOG = logging.getLogger(__name__)

MEMORIA_V8_MB = 128
CPU_SECONDI = 20
TIMEOUT_LOTTO = 30.0
TIMEOUT_RICHIESTA = 6.0
_UN_PROCESSO = threading.BoundedSemaphore(1)


def bundle_ssr() -> Path:
    return Path(__file__).resolve().parents[1] / "sito_pubblico_ssr" / "sito-pubblico-ssr.mjs"


def binario_node() -> str:
    return os.environ.get("IUSENTRA_NODE_BIN") or shutil.which("node") or ""


def _impronta_bundle() -> str:
    try:
        return hashlib.sha256(bundle_ssr().read_bytes()).hexdigest()[:16]
    except OSError:
        return "senza-bundle"


def versione(dati: dict[str, Any]) -> str:
    corpo = json.dumps(dati, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{_impronta_bundle()}:{corpo}".encode()).hexdigest()[:24]


def _comando(node: str, bundle: Path) -> list[str]:
    """Node con heap V8 limitato; CPU e file aperti limitati da prlimit (niente preexec_fn nei worker a thread)."""
    base = [node, f"--max-old-space-size={MEMORIA_V8_MB}", "--disallow-code-generation-from-strings", str(bundle)]
    prlimit = shutil.which("prlimit")
    return [prlimit, f"--cpu={CPU_SECONDI}", "--nofile=64", *base] if prlimit else base


def genera(richieste: list[dict[str, Any]], *, timeout: float) -> list[str] | None:
    """HTML delle pagine, nello stesso ordine; None se Node o il bundle mancano o il processo fallisce."""
    node, bundle = binario_node(), bundle_ssr()
    if not node or not bundle.is_file() or not richieste:
        if not node or not bundle.is_file():
            LOG.warning("Sito pubblico: pre-generazione non disponibile (node=%s, bundle=%s)", bool(node), bundle.is_file())
        return None
    try:
        esito = subprocess.run(  # noqa: S603 - binario e argomenti fissi, dati solo su stdin
            _comando(node, bundle),
            input=json.dumps({"richieste": richieste}, ensure_ascii=False).encode("utf-8"),
            capture_output=True, timeout=timeout, check=False,
            env={"PATH": os.environ.get("PATH", ""), "NODE_ENV": "production"},
        )
        risposta = json.loads(esito.stdout.decode("utf-8") or "{}")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        LOG.warning("Sito pubblico: pre-generazione non riuscita: %s", exc)
        return None
    html = risposta.get("html")
    if esito.returncode != 0 or not isinstance(html, list) or len(html) != len(richieste):
        LOG.warning("Sito pubblico: pre-generazione con esito %s: %s", esito.returncode,
                    str(risposta.get("errore") or esito.stderr.decode("utf-8", "replace"))[:300])
        return None
    return [str(pagina) for pagina in html]


def _file(cartella: Path, chiave: str, ver: str) -> Path:
    sicura = "".join(c if c.isalnum() or c in "-_" else "_" for c in chiave)[:120]
    return cartella / f"{sicura}--{ver}.html"


def _salva(cartella: Path, chiave: str, ver: str, html: str) -> None:
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = _file(cartella, chiave, ver)
    temporaneo = destinazione.with_suffix(".tmp")
    temporaneo.write_text(html, encoding="utf-8")
    os.replace(temporaneo, destinazione)
    prefisso = destinazione.name.split("--")[0] + "--"
    for vecchio in cartella.glob(prefisso + "*.html"):
        if vecchio != destinazione:
            vecchio.unlink(missing_ok=True)


def leggi_cache(cartella: Path, dati: dict[str, Any]) -> str | None:
    try:
        return _file(cartella, chiave_pagina(dati), versione(dati)).read_text(encoding="utf-8")
    except OSError:
        return None


def pagina_pre_generata(cartella: Path, dati: dict[str, Any]) -> str | None:
    """HTML della pagina per il visitatore: cache, oppure una sola generazione limitata se manca."""
    html = leggi_cache(cartella, dati)
    if html is not None:
        return html
    if not _UN_PROCESSO.acquire(timeout=0.5):
        return None
    try:
        generate = genera([dati], timeout=TIMEOUT_RICHIESTA)
    finally:
        _UN_PROCESSO.release()
    if not generate:
        return None
    try:
        _salva(cartella, chiave_pagina(dati), versione(dati), generate[0])
    except OSError as exc:
        LOG.warning("Sito pubblico: cache non salvata: %s", exc)
    return generate[0]


def pre_genera_sito(cartella: Path, pagine: list[dict[str, Any]]) -> int:
    """Genera e salva tutte le pagine indicate in un solo processo; restituisce quante ne ha salvate."""
    mancanti = [dati for dati in pagine if leggi_cache(cartella, dati) is None]
    if not mancanti:
        return 0
    with _UN_PROCESSO:
        generate = genera(mancanti, timeout=TIMEOUT_LOTTO)
    if not generate:
        return 0
    for dati, html in zip(mancanti, generate):
        _salva(cartella, chiave_pagina(dati), versione(dati), html)
    return len(generate)


def pre_genera_in_sfondo(cartella: Path, pagine: list[dict[str, Any]]) -> threading.Thread:
    filo = threading.Thread(target=pre_genera_sito, args=(cartella, pagine), name="sito-pubblico-pregenera", daemon=True)
    filo.start()
    return filo


__all__ = [
    "binario_node",
    "bundle_ssr",
    "genera",
    "leggi_cache",
    "pagina_pre_generata",
    "pre_genera_in_sfondo",
    "pre_genera_sito",
    "versione",
]
