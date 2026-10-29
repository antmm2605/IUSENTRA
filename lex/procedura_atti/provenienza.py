"""Provenienza obbligatoria delle Fonti.

Ogni Fonte in ``caso["fonti_ref"]`` porta:
  "provenienza": {"tipo": "norma" | "decisione", "url": "indirizzo ufficiale o archivio",
                  "versione": "versione o data di pubblicazione", "acquisita_il": "gg/mm/aaaa",
                  "sha256": "impronta del testo passato al modello", "testo_integrale": bool}
Una decisione giurisprudenziale e' Fonte solo con testo integrale ufficiale acquisito: estremi, oggetto ed esito
(es. risultati della ricerca R6, metadata_only) restano spunti e non possono entrare fra le Fonti.
Base: art. 20 CAD (D.Lgs. 82/2005) su integrita' e immodificabilita' del documento informatico; l'impronta
SHA-256 rende verificabile che il testo citato sia quello acquisito.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from urllib.parse import urlparse

CAMPI = ("tipo", "url", "versione", "acquisita_il", "sha256")
TIPI = ("norma", "decisione")
DATA = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def sha256_testo(testo: str) -> str:
    return hashlib.sha256((testo or "").encode("utf-8")).hexdigest()


def url_ufficiale(url: str) -> bool:
    """Indirizzo http(s) su un dominio del catalogo delle fonti ufficiali (lex.research.official_sources)."""
    try:
        parsed = urlparse(str(url or "").strip())
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return False
    from lex.research.official_sources import OfficialSourcesCatalog

    descrittore = OfficialSourcesCatalog().describe(f"{parsed.scheme}://{parsed.hostname}{parsed.path}")
    return bool(descrittore is not None and descrittore.official and not descrittore.restricted)


def _data_di_oggi(caso: dict, oggi: date | None) -> date:
    if isinstance(oggi, date):
        return oggi
    try:
        return datetime.strptime(str(caso.get("oggi") or ""), "%d/%m/%Y").date()
    except ValueError:
        return date.today()


def verifica_provenienza(caso: dict, *, oggi: date | None = None) -> list[str]:
    """Errori di provenienza delle Fonti (lista vuota = verificabili).

    ``oggi``: data del confronto (default ``caso["oggi"]`` in gg/mm/aaaa, altrimenti la data di sistema):
    una Fonte acquisita dopo «oggi» non e' una Fonte verificabile a quella data.
    """
    e: list[str] = []
    riferimento = _data_di_oggi(caso, oggi)
    fonti, refs = caso.get("fonti"), caso.get("fonti_ref")
    if not isinstance(fonti, dict) or not fonti or not isinstance(refs, list):
        return ["Fonti: testi e riferimenti obbligatori"]
    numeri = set()
    for f in refs:
        if not isinstance(f, dict):
            e.append("Fonte: riferimento non strutturato")
            continue
        n = f.get("n")
        if type(n) is not int or n < 1 or n in numeri:
            e.append("Fonte: numero non valido o duplicato")
            continue
        numeri.add(n)
        p = f.get("provenienza")
        if not isinstance(p, dict):
            e.append(f"Fonte [{n}]: provenienza mancante")
            continue
        mancanti = [c for c in CAMPI if not isinstance(p.get(c), str) or not p[c].strip()]
        if mancanti:
            e.append(f"Fonte [{n}]: provenienza incompleta ({', '.join(mancanti)})")
            continue
        if p["tipo"] not in TIPI:
            e.append(f"Fonte [{n}]: tipo di provenienza non ammesso ({p['tipo']})")
        if not url_ufficiale(p["url"]):
            e.append(f"Fonte [{n}]: indirizzo non ufficiale o non http(s) ({p['url'][:80]})")
        if f.get("evidence_scope") == "metadata_only" or p.get("evidence_scope") == "metadata_only":
            e.append(f"Fonte [{n}]: metadata_only resta uno spunto, non una Fonte")
        try:
            if not DATA.fullmatch(p["acquisita_il"]):
                raise ValueError()
            acquisita = datetime.strptime(p["acquisita_il"], "%d/%m/%Y").date()
        except ValueError:
            e.append(f"Fonte [{n}]: data di acquisizione non valida in formato gg/mm/aaaa")
        else:
            if acquisita > riferimento:
                e.append(f"Fonte [{n}]: acquisita il {p['acquisita_il']}, dopo la data di riferimento "
                         f"{riferimento.strftime('%d/%m/%Y')}")
        testo = fonti.get(n)
        if not isinstance(testo, str) or not testo.strip():
            e.append(f"Fonte [{n}]: testo assente")
            continue
        if p["sha256"] != sha256_testo(testo):
            e.append(f"Fonte [{n}]: SHA-256 del testo non corrisponde all'impronta acquisita")
        if p["tipo"] == "decisione" and p.get("testo_integrale") is not True:
            e.append(f"Fonte [{n}]: decisione senza testo integrale ufficiale: resta uno spunto, non una Fonte")
    if any(type(n) is not int or n < 1 for n in fonti) or set(fonti) != numeri:
        e.append("Fonti: numeri dei testi e dei riferimenti non corrispondenti")
    return e
