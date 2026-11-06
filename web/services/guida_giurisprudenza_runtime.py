"""Giurisprudenza della Guida pratica nella richiesta: solo citazioni verificate nell'archivio e decisioni per norma.

Il servizio della Guida resta indipendente dallo studio; qui, con lo studio della richiesta, si aprono in sola lettura
l'archivio SentenzeWeb (``IUSENTRA_SENTENZEWEB_DIRECTORY``) e l'archivio dello studio (Corte costituzionale). Le
citazioni di giurisprudenza escono dai riferimenti normativi e vanno nella sezione «giurisprudenza»: quelle verificate
con il collegamento ufficiale, quelle non verificate solo contate.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from pct.guida_pratica.giurisprudenza_scheda import decisioni_per_norme, e_giurisprudenza, verifica_citazioni

logger = logging.getLogger(__name__)
_CODICI = {"c.c.", "c.p.c.", "c.p.", "c.p.p.", "disp. att. c.c.", "disp. att. c.p.c.", "c.p.a.", "Cost."}


def _archivi() -> tuple[Path | None, Path | None]:
    from flask import current_app, has_app_context
    cartella = (current_app.config.get("IUSENTRA_SENTENZEWEB_DIRECTORY") if has_app_context() else "") or os.getenv("IUSENTRA_SENTENZEWEB_DIRECTORY") or ""
    cassazione = Path(cartella) / "giurisprudenza_corpus.db" if cartella else None
    costituzionale = None
    try:
        from pct.giurisprudenza_corpus import derive_corpus_db_path
        from web.services.tenant_paths import tenant_data_path
        valore = tenant_data_path("GIURISPRUDENZA_DB", require_tenant=True)
        costituzionale = Path(derive_corpus_db_path(valore)) if valore else None
    except Exception as exc:  # fuori da una richiesta di studio: solo la Cassazione
        logger.debug("archivio dello studio non disponibile: %s", exc)
    return cassazione, costituzionale


def _norme_della_scheda(voci: list[Any]) -> list[tuple[str, str]]:
    norme = []
    for voce in voci:
        if not isinstance(voce, dict) or e_giurisprudenza(voce):
            continue
        fonte, articolo = str(voce.get("fonte") or ""), str(voce.get("articolo") or "").strip()
        if articolo and (fonte in _CODICI or fonte[:2] in {"L.", "D."}) and articolo.replace("-", "").isalnum():
            norme.append((fonte, articolo))
    return norme


def arricchisci_giurisprudenza(guida: dict[str, Any]) -> dict[str, Any]:
    normativa = guida.get("normativa") if isinstance(guida.get("normativa"), dict) else {}
    citazioni: list[dict[str, Any]] = []
    tutte_le_norme: list[Any] = []
    for chiave in ("riferimenti_primari", "riferimenti_secondari"):
        voci = normativa.get(chiave) if isinstance(normativa.get(chiave), list) else []
        citazioni.extend(v for v in voci if isinstance(v, dict) and e_giurisprudenza(v))
        normativa[chiave] = [v for v in voci if not (isinstance(v, dict) and e_giurisprudenza(v))]
        tutte_le_norme.extend(normativa[chiave])
    cassazione, costituzionale = _archivi()
    try:
        esiti = verifica_citazioni(citazioni, cassazione=cassazione, costituzionale=costituzionale)
        decisioni = decisioni_per_norme(_norme_della_scheda(tutte_le_norme), cassazione=cassazione)
    except Exception as exc:  # la guida non si blocca se l'archivio non risponde
        logger.warning("giurisprudenza della guida non disponibile: %s", exc)
        esiti, decisioni = [], []
    verificate = [e for e in esiti if e.get("verificata")]
    guida["normativa"] = normativa
    guida["giurisprudenza"] = {
        "verificate": verificate,
        "non_verificate": len(esiti) - len(verificate),
        "decisioni_per_norma": decisioni,
        "fonte": "Archivio di giurisprudenza del software: Cassazione SentenzeWeb e Corte costituzionale (open data ufficiali)",
        "archivio_disponibile": bool(cassazione and cassazione.is_file()),
    }
    return guida
