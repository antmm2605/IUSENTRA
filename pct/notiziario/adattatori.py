"""Dalle voci grezze di ciascun canale alla notizia normalizzata dell'archivio.

Regole comuni: il collegamento deve portare a un host dell'ente (gli indirizzi
`http://` della Gazzetta Ufficiale si portano su `https://`, stesso documento);
una voce senza data di pubblicazione dichiarata non entra (nessuna data di
ripiego); la sintesi è la descrizione ufficiale, accorciata a fine parola.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from pct.notiziario import classifica
from pct.notiziario.feed import VoceGrezza
from pct.notiziario.fonti import ETICHETTE_TIPO, Fonte

LUNGHEZZA_SINTESI = 480
_CELEX = re.compile(r"^CELEX:(?P<celex>[0-9A-Z()]+):\s*", re.IGNORECASE)
_CODICE_GU = re.compile(r"\((?P<codice>\d{2}[A-Z]\d{5})\)\s*$")
_NON_ITALIANA = "non riguarda la versione italiana"


def identificativo_notizia(fonte_id: str, url: str) -> str:
    """Stesso schema di `pct.notizie_utili._item`: le letture e i preferiti già salvati restano validi."""
    digest = hashlib.sha256(f"{fonte_id}|{url}".encode("utf-8")).hexdigest()[:24]
    return f"official_{digest}"


def sintesi_ufficiale(testo: str, limite: int = LUNGHEZZA_SINTESI) -> str:
    testo = " ".join(str(testo or "").split())
    if len(testo) <= limite:
        return testo
    return testo[:limite].rsplit(" ", 1)[0].rstrip(" ,;:.") + "…"


def collegamento_ufficiale(url: str, host_ammessi: tuple[str, ...]) -> str:
    """URL `https://` ricostruito dall'host validato, o "" se il collegamento non è dell'ente.

    Si rifiutano spazi e caratteri di controllo (es. «doc.jsp?ID=Concorso notai: …» nel feed del
    Garante), la barra rovesciata, le credenziali nella netloc («@»), le porte esplicite e gli
    schemi diversi da http/https (javascript:, data:, …).
    """
    testo = str(url or "").strip()
    if not testo or "\\" in testo or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in testo):
        return ""
    try:
        parti = urlsplit(testo)
        porta = parti.port
    except ValueError:
        return ""
    if parti.scheme.lower() not in {"http", "https"} or "@" in parti.netloc or porta is not None:
        return ""
    host = (parti.hostname or "").lower()
    if not host or host not in host_ammessi or parti.netloc.lower() != host:
        return ""
    percorso = parti.path.replace("/./", "/")
    return urlunsplit(("https", host, percorso, parti.query, ""))


def _adesso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def notizia(
    fonte: Fonte,
    *,
    titolo: str,
    url: str,
    data: str,
    descrizione: str,
    riferimento_ufficiale: str = "",
) -> dict[str, Any]:
    testo = f"{titolo} {descrizione}"
    tipo = classifica.tipo_della_notizia(fonte, titolo)
    return {
        "id": identificativo_notizia(fonte.id, url),
        "fonte": fonte.id,
        "etichetta_fonte": fonte.etichetta,
        "ente": fonte.ente,
        "titolo": titolo,
        "url": url,
        "data": data,
        "sintesi": sintesi_ufficiale(descrizione) if descrizione.casefold() != titolo.casefold() else "",
        "tipo": tipo,
        "etichetta_tipo": ETICHETTE_TIPO.get(tipo, ""),
        "materia": classifica.materia_della_notizia(fonte, testo),
        "atti": classifica.atti_citati(testo),
        "riferimento_ufficiale": riferimento_ufficiale,
        "acquisita_il": _adesso(),
    }


def _riferimento(fonte: Fonte, voce: VoceGrezza) -> tuple[str, str]:
    """Titolo da mostrare e identificativo ufficiale (CELEX, codice redazionale GU, ricorsi CEDU)."""
    titolo = voce.titolo
    if fonte.id == "eurlex_gu_l":
        trovato = _CELEX.match(titolo)
        if trovato:
            return titolo[trovato.end():].strip() or titolo, f"CELEX {trovato.group('celex')}"
    if fonte.id.startswith("gu_"):
        trovato = _CODICE_GU.search(voce.descrizione)
        if trovato:
            return titolo, f"Codice redazionale {trovato.group('codice')}"
    if fonte.id == "cedu_italia":
        return titolo, voce.descrizione
    return titolo, ""


def da_feed(fonte: Fonte, voci: Iterable[VoceGrezza]) -> list[dict[str, Any]]:
    risultato: list[dict[str, Any]] = []
    visti: set[str] = set()
    for voce in voci:
        if not voce.data:
            continue
        if fonte.id == "eurlex_gu_l" and _NON_ITALIANA in voce.descrizione.casefold():
            continue
        url = collegamento_ufficiale(voce.collegamento, fonte.host_ammessi)
        if not url:
            continue
        titolo, riferimento = _riferimento(fonte, voce)
        # La CEDU pubblica la stessa sentenza in inglese e in francese: una sola notizia per ricorso e data.
        chiave = f"{voce.descrizione}|{voce.data}" if fonte.id == "cedu_italia" else url
        if chiave in visti:
            continue
        visti.add(chiave)
        risultato.append(notizia(
            fonte, titolo=titolo, url=url, data=voce.data, descrizione=voce.descrizione,
            riferimento_ufficiale=riferimento,
        ))
        if len(risultato) >= fonte.max_voci:
            break
    return risultato


def da_pagina_istituzionale(fonte: Fonte, righe: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Righe prodotte da `pct.notizie_utili` (stesso identificativo, stessa sintesi ufficiale)."""
    risultato: list[dict[str, Any]] = []
    for riga in righe:
        url = collegamento_ufficiale(str(riga.get("source_url") or ""), fonte.host_ammessi)
        data = str(riga.get("published_at") or "")[:10]
        titolo = " ".join(str(riga.get("title") or "").split())
        if not url or not data or not titolo:
            continue
        voce = notizia(fonte, titolo=titolo, url=url, data=data, descrizione=str(riga.get("short_summary") or ""))
        voce["id"] = str(riga.get("id") or voce["id"])
        risultato.append(voce)
    return risultato


__all__ = ["collegamento_ufficiale", "da_feed", "da_pagina_istituzionale", "identificativo_notizia", "notizia", "sintesi_ufficiale"]
