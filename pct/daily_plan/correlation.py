"""Correlazione tra fonti prima della deduplicazione.

Riscrive l'evento canonico dei segnali quando esiste un collegamento forte
già governato dal dominio (es. una scadenza estratta da PEC che il presidio
ha già registrato nello scadenziario), così fonti diverse dello stesso
evento collassano sulla stessa chiave di deduplicazione.

Le associazioni deboli (match testuale RG, solo cliente) NON producono mai
collegamenti definitivi: abbassano la confidence e marcano ``needs_review``.
"""

from __future__ import annotations

import re
from typing import Iterable

from .clock import Clock, system_clock
from .deduplication import build_dedupe_key, normalize_due_date
from .models import OperationalSignal

WEAK_LINK_MAX_CONFIDENCE = 0.6

_RG_PATTERN = re.compile(r"(\d{1,6})\s*/\s*(\d{2,4})")


def normalize_rg(value: str) -> str:
    """Normalizza un riferimento RG in forma ``numero/anno`` (anno a 4 cifre)."""
    match = _RG_PATTERN.search(str(value or ""))
    if not match:
        return ""
    numero = match.group(1).lstrip("0") or "0"
    anno = match.group(2)
    if len(anno) == 2:
        anno = ("20" if int(anno) < 70 else "19") + anno
    return f"{numero}/{anno}"


def canonical_event_for(signal: OperationalSignal) -> str:
    """Evento canonico stabile per un segnale, usando i link forti."""
    meta = signal.metadata or {}
    scadenza_id = str(meta.get("scadenziario_id") or "").strip()
    if scadenza_id:
        return f"scadenziario:{scadenza_id}"
    agenda_id = str(meta.get("agenda_id") or "").strip()
    if agenda_id:
        return f"agenda:{agenda_id}"
    explicit = str(meta.get("canonical_event") or "").strip()
    if explicit:
        return explicit
    if signal.kind == "hearing_attend" and signal.fascicolo_id and signal.due_at:
        return f"hearing:{signal.fascicolo_id}:{signal.due_at[:10]}"
    return f"{signal.source_type}:{signal.source_id or signal.id}"


def correlate(
    signals: Iterable[OperationalSignal], *, clock: Clock | None = None
) -> list[OperationalSignal]:
    """Ricalcola evento canonico e dedupe_key; degrada i link deboli.

    Un segnale con associazione fascicolo debole (``fascicolo_match: weak``)
    non deve mai fondersi con i segnali certi del fascicolo: perde il
    fascicolo dalla chiave, viene marcato ``needs_review`` e la confidence
    viene limitata a ``WEAK_LINK_MAX_CONFIDENCE``.
    """
    clock = clock or system_clock()
    out: list[OperationalSignal] = []
    for sig in signals:
        meta = dict(sig.metadata or {})
        weak = str(meta.get("fascicolo_match") or "").lower() == "weak"
        if weak:
            meta["needs_review"] = True
            sig.confidence = min(float(sig.confidence or 0.0), WEAK_LINK_MAX_CONFIDENCE)

        key_fascicolo = "" if weak else sig.fascicolo_id
        due_date = normalize_due_date(sig.due_at, clock)
        canonical = canonical_event_for(sig)
        meta["canonical_event"] = canonical
        sig.metadata = meta
        sig.dedupe_key = build_dedupe_key(
            sig.tenant_id, key_fascicolo, sig.kind, canonical, due_date
        )
        out.append(sig)
    return out


__all__ = [
    "WEAK_LINK_MAX_CONFIDENCE",
    "canonical_event_for",
    "correlate",
    "normalize_rg",
]
