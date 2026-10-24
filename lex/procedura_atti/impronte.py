"""Impronte SHA-256 canoniche: una validazione vale solo per la scheda e le Fonti esattamente approvate."""
from __future__ import annotations

import hashlib
import json


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def impronta_scheda(scheda: dict) -> str:
    return _sha(scheda)


def impronta_fonti(caso: dict) -> str:
    """Testi delle Fonti come arrivano al modello piu' l'elenco completo, provenienza inclusa (tipo, URL, versione,
    data di acquisizione, impronta): stesso testo con provenienza diversa = impronta diversa."""
    return _sha({"testi": {str(k): v for k, v in sorted(caso["fonti"].items())},
                 "elenco": caso["fonti_ref"]})


def impronta_fascicolo(caso: dict) -> str:
    return _sha({k: caso[k] for k in ("fatti", "richiesta", "oggi", "parte_assistita", "controparte")})


def impronta_config(cfg: dict) -> str:
    return _sha(cfg)[:12]
