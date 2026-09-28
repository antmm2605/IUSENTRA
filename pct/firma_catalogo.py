"""Catalogo della firma digitale: prestatori qualificati e produttori dei dispositivi.

Fonte unica: ``pct/data/cataloghi/firma_digitale.json`` (letto anche dal frontend), con
l'elenco AgID dei prestatori di servizi fiduciari attivi in Italia, i protocolli di firma
remota documentati pubblicamente (ARSS, SWS, CSC) e le librerie PKCS#11 dei dispositivi.
Base normativa: Reg. eIDAS 910/2014 artt. 22 e 29 (elenchi di fiducia, dispositivi
qualificati); CAD D.Lgs. 82/2005 art. 29 (prestatori qualificati).
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

PERCORSO = Path(__file__).resolve().parent / "data" / "cataloghi" / "firma_digitale.json"
PROTOCOLLI_REMOTI = ("arss", "sws", "csc")


@lru_cache(maxsize=1)
def catalogo() -> dict[str, Any]:
    return json.loads(PERCORSO.read_text(encoding="utf-8"))


def prestatori() -> list[dict[str, Any]]:
    return list(catalogo()["prestatori"])


def prestatore(identificativo: str) -> dict[str, Any] | None:
    chiave = str(identificativo or "").strip().lower()
    return next((p for p in prestatori() if p["id"] == chiave), None)


def protocolli_remoti(identificativo: str) -> list[str]:
    voce = prestatore(identificativo) or {}
    return [p for p in (voce.get("remota") or {}).get("protocolli") or [] if p in PROTOCOLLI_REMOTI]


def endpoint_predefinito(identificativo: str, protocollo: str) -> str:
    voce = prestatore(identificativo) or {}
    return str(((voce.get("remota") or {}).get("endpoint") or {}).get(protocollo) or "")


def produttori() -> list[dict[str, Any]]:
    return list(catalogo()["produttori_dispositivo"])


def produttore(identificativo: str) -> dict[str, Any] | None:
    chiave = str(identificativo or "").strip().lower()
    return next((p for p in produttori() if p["id"] == chiave), None)


def sistema_corrente() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def librerie_candidate(identificativo: str = "", sistema: str | None = None) -> list[str]:
    """Percorsi possibili delle librerie PKCS#11: del produttore scelto, o di tutti se non indicato."""
    sistema = sistema or sistema_corrente()
    cartelle = catalogo()["cartelle_librerie"].get(sistema, [])
    scelti = [produttore(identificativo)] if identificativo else produttori()
    separatore = "\\" if sistema == "windows" else "/"
    percorsi: list[str] = []
    for voce in scelti:
        if not voce:
            continue
        for nome in voce["librerie"].get(sistema, []):
            for cartella in cartelle:
                percorso = f"{cartella.rstrip(separatore)}{separatore}{nome}"
                if percorso not in percorsi:
                    percorsi.append(percorso)
    return percorsi


def opzioni_impostazioni() -> dict[str, list[dict[str, str]]]:
    """Le scelte per Impostazioni → Firma digitale: prestatori, produttori e protocolli."""
    dati = catalogo()
    return {
        "prestatori": [{"value": p["id"], "label": p["nome"]} for p in dati["prestatori"]],
        "produttori": [{"value": p["id"], "label": p["nome"]} for p in dati["produttori_dispositivo"]],
        "protocolli": [{"value": k, "label": v["etichetta"]} for k, v in dati["protocolli_remoti"].items()],
    }


__all__ = [
    "PROTOCOLLI_REMOTI", "catalogo", "endpoint_predefinito", "librerie_candidate", "opzioni_impostazioni",
    "prestatore", "prestatori", "produttore", "produttori", "protocolli_remoti", "sistema_corrente",
]
