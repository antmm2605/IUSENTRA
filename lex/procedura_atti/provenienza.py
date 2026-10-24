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

CAMPI = ("tipo", "url", "versione", "acquisita_il", "sha256")
TIPI = ("norma", "decisione")
DATA = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def sha256_testo(testo: str) -> str:
    return hashlib.sha256((testo or "").encode("utf-8")).hexdigest()


def verifica_provenienza(caso: dict) -> list[str]:
    e: list[str] = []
    for f in caso.get("fonti_ref", []):
        n = f.get("n")
        p = f.get("provenienza")
        if not isinstance(p, dict):
            e.append(f"Fonte [{n}]: provenienza mancante")
            continue
        mancanti = [c for c in CAMPI if not str(p.get(c, "")).strip()]
        if mancanti:
            e.append(f"Fonte [{n}]: provenienza incompleta ({', '.join(mancanti)})")
            continue
        if p["tipo"] not in TIPI:
            e.append(f"Fonte [{n}]: tipo di provenienza non ammesso ({p['tipo']})")
        if not DATA.match(str(p["acquisita_il"])):
            e.append(f"Fonte [{n}]: data di acquisizione non in formato gg/mm/aaaa")
        testo = caso.get("fonti", {}).get(n, "")
        if p["sha256"] != sha256_testo(testo):
            e.append(f"Fonte [{n}]: il testo non corrisponde all'impronta acquisita")
        if p["tipo"] == "decisione" and p.get("testo_integrale") is not True:
            e.append(f"Fonte [{n}]: decisione senza testo integrale ufficiale: resta uno spunto, non una Fonte")
    return e
