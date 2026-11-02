"""Le voci della normativa del fascicolo, costruite solo da fonti già registrate.

Ogni voce nasce da una riga di un registro ufficiale del software: il registro
delle fonti procedurali (`pct.procedura_fasi.fonti.FONTI`, con estratto
letterale e data di consultazione su Normattiva), le fonti del catalogo dei
documenti (`pct.document_intelligence.catalog_sources.CATALOG_SOURCES`) e le
fonti dei modelli (`pct.template_atti_legal_sources`). Una citazione scritta in
una scadenza e assente dai registri diventa soltanto un collegamento ufficiale
a Normattiva, costruito dall'URN del codice: nessun testo è scritto qui.

Base normativa del collegamento: URN NIR delle fonti normative
(Normattiva, servizio `uri-res/N2Ls`), D.L. 225/2010 art. 1 e D.L. 200/2008.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlsplit

_DATA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?!\d)")
_URN = re.compile(r"^urn:nir:[a-z0-9.:;\-]+$")
_ALLEGATO = re.compile(r"(;\d+):\d+$")


def fonte_ufficiale(url: str) -> str:
    """Il nome della fonte da cui si apre il testo ufficiale."""
    host = (urlsplit(str(url or "")).hostname or "").lower()
    if host.endswith("normattiva.it"):
        return "Normattiva"
    if host.endswith("giustizia.it"):
        return "Ministero della Giustizia"
    if host.endswith("gazzettaufficiale.it"):
        return "Gazzetta Ufficiale"
    if host.endswith("finanze.it"):
        return "Ministero dell'Economia e delle Finanze"
    if host.endswith("europa.eu"):
        return "EUR-Lex"
    return "Fonte ufficiale"


def url_sicuro(url: str) -> str:
    """Solo collegamenti https senza credenziali: nessun altro schema arriva al browser."""
    parti = urlsplit(str(url or "").strip())
    if parti.scheme != "https" or not parti.hostname or parti.username or parti.password:
        return ""
    return parti.geturl()


def consultata_il(verifica: str) -> str:
    """La data di consultazione dichiarata dal registro, in formato italiano."""
    testo = str(verifica or "")
    trovata = _DATA.findall(testo)
    if trovata:
        return trovata[-1]
    iso = _ISO.search(testo)
    return f"{iso.group(3)}/{iso.group(2)}/{iso.group(1)}" if iso else ""


def riferimento_archivio(url: str) -> dict[str, str]:
    """URN e articolo dal collegamento Normattiva, per cercare il testo nell'archivio locale."""
    parti = urlsplit(str(url or ""))
    if parti.scheme != "https" or not (parti.hostname or "").endswith("normattiva.it"):
        return {}
    richiesta = unquote(parti.query)
    if not richiesta.startswith("urn:nir:") or "~art" not in richiesta:
        return {}
    urn, articolo = richiesta.split("~art", 1)
    urn = _ALLEGATO.sub(r"\1", urn.split("!", 1)[0])
    articolo = re.split(r"[!&]", articolo, maxsplit=1)[0]
    if not _URN.match(urn) or not re.fullmatch(r"[0-9]+[a-z0-9.]*", articolo):
        return {}
    return {"urn": urn, "articolo": articolo}


def _voce(
    chiave: str, *, norma: str, rubrica: str, url: str, verifica: str, estratto: str = "",
    lettura_interna: str = "", riferimento: dict[str, str] | None = None,
) -> dict[str, Any]:
    collegamento = url_sicuro(url)
    return {
        "id": chiave,
        "norma": " ".join(str(norma or "").split()),
        "rubrica": " ".join(str(rubrica or "").split()),
        "estratto": " ".join(str(estratto or "").split()),
        "url": collegamento,
        "fonte": fonte_ufficiale(collegamento),
        "verifica": " ".join(str(verifica or "").split()),
        "consultataIl": consultata_il(verifica),
        "letturaInterna": lettura_interna if lettura_interna.startswith("/api/v1/ui/") else "",
        "archivio": riferimento if riferimento is not None else riferimento_archivio(collegamento),
        "perche": [],
    }


def voce_registro(identificativo: str) -> dict[str, Any] | None:
    """Una voce del registro delle fonti procedurali: norma, rubrica ed estratto letterale."""
    from pct.procedura_fasi.fonti import FONTI

    riga = FONTI.get(str(identificativo or ""))
    if not riga:
        return None
    return _voce(
        f"registro:{identificativo}", norma=riga.get("norma", ""), rubrica=riga.get("titolo", ""),
        url=riga.get("url", ""), verifica=riga.get("verifica", ""), estratto=riga.get("estratto", ""),
        lettura_interna=str(riga.get("reader_url") or ""),
    )


def voce_catalogo(identificativo: str) -> dict[str, Any] | None:
    """Una fonte del catalogo dei documenti o dei modelli: norma e collegamento, senza estratto."""
    from pct.document_intelligence.catalog_sources import CATALOG_SOURCES

    riga = CATALOG_SOURCES.get(str(identificativo or ""))
    if riga:
        if str(riga.get("source_type") or "") != "normativa":
            return None
        etichetta = str(riga.get("label") or "")
        norma, _, rubrica = etichetta.partition(": ")
        return _voce(f"catalogo:{identificativo}", norma=norma, rubrica=rubrica, url=str(riga.get("official_url") or ""),
                     verifica=str(riga.get("verification_status") or ""))
    from pct.template_atti_legal_sources import TEMPLATE_ATTI_LEGAL_SOURCES

    modello = next((r for r in TEMPLATE_ATTI_LEGAL_SOURCES if r.get("id") == identificativo), None)
    if not modello or str(modello.get("source_type") or "") != "normativa":
        return None
    verifica = str(modello.get("verification_status") or "")
    if modello.get("last_verified_at"):
        verifica = f"{verifica} il {consultata_il(str(modello['last_verified_at']))}".strip()
    articolo = str(modello.get("article") or "")
    return _voce(f"catalogo:{identificativo}", norma=articolo or str(modello.get("source_title") or ""),
                 rubrica=str(modello.get("title") or ""), url=str(modello.get("official_url") or ""),
                 verifica=verifica, riferimento=riferimento_citazione(articolo))


def riferimento_citazione(citazione: str) -> dict[str, str]:
    """URN e articolo da una citazione puntuale di un codice («art. 167 c.p.c.»)."""
    from lex.testi_ufficiali import riconosci_articolo

    richiesta = riconosci_articolo(str(citazione or "")[:120])
    if richiesta is None or not richiesta.urn:
        return {}
    return {"urn": richiesta.urn, "articolo": richiesta.chiave}


def voce_citazione(citazione: str) -> dict[str, Any] | None:
    """Una norma citata e assente dai registri: solo il collegamento ufficiale, nessun testo."""
    from lex.testi_ufficiali import riconosci_articolo

    richiesta = riconosci_articolo(str(citazione or "")[:120])
    if richiesta is None or not richiesta.urn:
        return None
    norma = richiesta.citazione
    return _voce(f"citazione:{richiesta.urn}~{richiesta.chiave}", norma=norma, rubrica="",
                 url=richiesta.collegamento(), verifica="",
                 riferimento={"urn": richiesta.urn, "articolo": richiesta.chiave})


def aggiungi(voci: dict[str, dict[str, Any]], voce: dict[str, Any] | None, perche: str) -> None:
    """Una voce per norma: i motivi si sommano, la norma non si ripete."""
    if voce is None or not voce.get("url"):
        return
    esistente = voci.setdefault(voce["id"], voce)
    if perche and perche not in esistente["perche"]:
        esistente["perche"].append(perche)


def data_italiana(valore: Any) -> str:
    """Data in gg/mm/aaaa nel fuso Europe/Rome; valori con o senza fuso, mai un'eccezione."""
    from pct.formatting import format_date_it

    try:
        return format_date_it(valore)
    except (TypeError, ValueError, OverflowError):
        return ""


__all__ = [
    "aggiungi", "consultata_il", "data_italiana", "fonte_ufficiale", "riferimento_archivio", "riferimento_citazione",
    "url_sicuro", "voce_catalogo", "voce_citazione", "voce_registro",
]
