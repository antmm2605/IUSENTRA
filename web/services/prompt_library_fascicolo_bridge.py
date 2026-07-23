"""Costruzione del contesto fascicolo per la libreria prompt LegalSkills Italia.

Legge il fascicolo dal runtime tenant-aware del gestionale e lo riduce
alla fotografia minima (`ContestoFascicolo`) usata dal compositore per
precompilare i prompt. Dati sporchi o runtime assenti non propagano
eccezioni: il chiamante riceve ``None`` e il prompt resta generico.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from flask import current_app

from lex.legal_skills.prompt_library import ContestoFascicolo

_MAX_DOCUMENTI = 10
_MAX_SCADENZE = 5


def _core_runtime_func(name: str) -> Callable[..., Any] | None:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    func = core_runtime.get(name)
    return func if callable(func) else None


def _data_italiana(iso: str) -> str:
    try:
        return date.fromisoformat(str(iso or "")[:10]).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return ""


def _scadenze_fascicolo(fascicolo_id: str) -> list[str]:
    loader = _core_runtime_func("get_scadenziario")
    if loader is None:
        return []
    try:
        scadenze = loader().tutte(id_fascicolo=fascicolo_id, solo_aperte=True)
    except Exception:
        current_app.logger.exception("Scadenze non leggibili per il contesto prompt del fascicolo %s", fascicolo_id)
        return []
    voci: list[tuple[str, str]] = []
    for scadenza in scadenze:
        titolo = str(getattr(scadenza, "titolo", "") or "").strip()
        data_iso = str(getattr(scadenza, "data_scadenza", "") or "")
        data_it = _data_italiana(data_iso)
        if titolo and data_it:
            voci.append((data_iso[:10], f"{data_it} — {titolo}"))
    return [testo for _, testo in sorted(voci)[:_MAX_SCADENZE]]


def costruisci_contesto_fascicolo(fascicolo_id: str) -> ContestoFascicolo | None:
    """Restituisce il contesto del fascicolo, o ``None`` se non disponibile."""
    identificativo = str(fascicolo_id or "").strip()
    if not identificativo:
        return None
    loader = _core_runtime_func("get_fascicoli")
    if loader is None:
        return None
    try:
        fascicolo = loader().get(identificativo)
    except Exception:
        current_app.logger.exception("Fascicolo non leggibile per il contesto prompt: %s", identificativo)
        return None
    if fascicolo is None:
        return None

    valore = float(getattr(fascicolo, "valore_causa", 0) or 0)
    anno_rg = int(getattr(fascicolo, "anno_rg", 0) or 0)
    documenti = [
        str(getattr(documento, "nome", "") or "").strip()
        for documento in list(getattr(fascicolo, "documenti", []) or [])[:_MAX_DOCUMENTI]
    ]
    return ContestoFascicolo(
        fascicolo_id=str(getattr(fascicolo, "id", identificativo) or identificativo),
        numero=str(getattr(fascicolo, "numero", "") or ""),
        titolo=str(getattr(fascicolo, "titolo", "") or ""),
        cliente=str(getattr(fascicolo, "nome_cliente", "") or ""),
        controparte=str(getattr(fascicolo, "controparte", "") or ""),
        ufficio=str(getattr(fascicolo, "tribunale", "") or ""),
        numero_rg=str(getattr(fascicolo, "numero_rg", "") or ""),
        anno_rg=str(anno_rg) if anno_rg else "",
        giudice=str(getattr(fascicolo, "giudice", "") or ""),
        sezione=str(getattr(fascicolo, "sezione", "") or ""),
        oggetto=str(getattr(fascicolo, "oggetto", "") or ""),
        valore_causa=f"{valore:,.2f} euro".replace(",", "X").replace(".", ",").replace("X", ".") if valore else "",
        tipo_procedimento=str(getattr(fascicolo, "tipo_procedimento", "") or ""),
        documenti=[nome for nome in documenti if nome],
        scadenze=_scadenze_fascicolo(identificativo),
    )


__all__ = ["costruisci_contesto_fascicolo"]
