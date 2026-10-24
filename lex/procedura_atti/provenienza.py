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
from datetime import datetime

CAMPI = ("tipo", "url", "versione", "acquisita_il", "sha256")
TIPI = ("norma", "decisione")
DATA = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def sha256_testo(testo: str) -> str:
    return hashlib.sha256((testo or "").encode("utf-8")).hexdigest()


def verifica_provenienza(caso: dict) -> list[str]:
    e: list[str] = []
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
        if f.get("evidence_scope") == "metadata_only" or p.get("evidence_scope") == "metadata_only":
            e.append(f"Fonte [{n}]: metadata_only resta uno spunto, non una Fonte")
        try:
            if not DATA.fullmatch(p["acquisita_il"]):
                raise ValueError()
            datetime.strptime(p["acquisita_il"], "%d/%m/%Y")
        except ValueError:
            e.append(f"Fonte [{n}]: data di acquisizione non valida in formato gg/mm/aaaa")
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
