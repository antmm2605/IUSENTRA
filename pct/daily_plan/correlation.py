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
import unicodedata
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


_NON_WORD = re.compile(r"[^a-z0-9]+")


def event_text_key(value: str, *, limit: int = 120) -> str:
    """Testo normalizzato per riconoscere lo stesso adempimento.

    Minuscole, senza accenti e punteggiatura: «Deposito note scritte ex art.
    127-ter c.p.c.» letto da tre copie del decreto produce la stessa chiave.
    """
    raw = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()
    return _NON_WORD.sub("-", ascii_text).strip("-")[:limit]


def presidio_event_canonical(signal: OperationalSignal) -> str:
    """Evento del presidio fascicolo: fascicolo + settore + adempimento.

    L'identificativo tecnico dell'azione del presidio contiene la posizione
    nell'elenco (``documenti-note_127_ter-4``) e cambia quando cambiano i
    documenti letti: non può identificare l'evento. Lo stesso adempimento con
    la stessa data (la data entra comunque nella chiave di deduplica) letto da
    più documenti dello stesso fascicolo è UN solo evento con più evidenze.
    """
    meta = signal.metadata or {}
    sector = str(meta.get("sector") or signal.kind or "").strip()
    return f"presidio:{signal.fascicolo_id or '-'}:{sector}:{event_text_key(signal.title)}"


def scadenza_event_canonical(signal: OperationalSignal) -> str:
    """Evento della scadenza: stessa comunicazione registrata più volte = uno.

    Una comunicazione di cancelleria ricevuta due volte (stessa data evento,
    stesso adempimento, stesso fascicolo) apre un solo termine: il termine
    decorre dall'evento, non dal numero di copie ricevute (art. 127-ter c.p.c.,
    art. 16 D.L. 179/2012). Scadenze inserite a mano o senza evento d'origine
    restano distinte; senza fascicolo si fondono solo le scadenze nate dalla
    stessa PEC.
    """
    meta = signal.metadata or {}
    own_id = str(meta.get("scadenziario_id") or signal.source_id or "").strip()
    event_day = str(meta.get("evento_origine_giorno") or "").strip()
    if not event_day:
        return f"scadenziario:{own_id}"
    event_type = event_text_key(str(meta.get("evento_origine_tipo") or ""), limit=60)
    scope = signal.fascicolo_id
    if not scope:
        pec_id = str(meta.get("pec_audit_id") or "").strip()
        if not pec_id:
            return f"scadenziario:{own_id}"
        scope = f"-:{pec_id}"
    return f"scadenza:{scope}:{event_text_key(signal.title)}:{event_type}:{event_day}"


def canonical_event_for(
    signal: OperationalSignal, scadenza_aliases: dict[str, str] | None = None
) -> str:
    """Evento canonico stabile per un segnale, usando i link forti."""
    meta = signal.metadata or {}
    if signal.source_type == "scadenziario":
        return scadenza_event_canonical(signal)
    scadenza_id = str(meta.get("scadenziario_id") or "").strip()
    if scadenza_id:
        return (scadenza_aliases or {}).get(scadenza_id) or f"scadenziario:{scadenza_id}"
    agenda_id = str(meta.get("agenda_id") or "").strip()
    if agenda_id:
        return f"agenda:{agenda_id}"
    if signal.source_type == "case_presidio":
        return presidio_event_canonical(signal)
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
    batch = list(signals)
    # prima passata: ogni scadenza punta all'evento del suo gruppo, così PEC e
    # documenti collegati a una copia si fondono con l'unica attività
    scadenza_aliases: dict[str, str] = {}
    for sig in batch:
        if sig.source_type != "scadenziario":
            continue
        canonical = scadenza_event_canonical(sig)
        for ref in (sig.source_id, (sig.metadata or {}).get("scadenziario_id")):
            if str(ref or "").strip():
                scadenza_aliases[str(ref).strip()] = canonical
    out: list[OperationalSignal] = []
    for sig in batch:
        meta = dict(sig.metadata or {})
        weak = str(meta.get("fascicolo_match") or "").lower() == "weak"
        if weak:
            meta["needs_review"] = True
            sig.confidence = min(float(sig.confidence or 0.0), WEAK_LINK_MAX_CONFIDENCE)

        key_fascicolo = "" if weak else sig.fascicolo_id
        due_date = normalize_due_date(sig.due_at, clock)
        canonical = canonical_event_for(sig, scadenza_aliases)
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
    "event_text_key",
    "normalize_rg",
    "presidio_event_canonical",
    "scadenza_event_canonical",
]
