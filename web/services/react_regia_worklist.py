"""Coda di lavoro unificata della Regia Operativa.

La Regia deve dare all'avvocato una sola risposta: «cosa lavoro adesso?».
Questo modulo fonde i processi aperti gia' letti dagli archivi reali dello
studio (scadenze, udienze di oggi, PEC non lette, conferimenti mancanti,
azioni della regia) in un'unica lista ordinata per urgenza, dove ogni voce
porta direttamente all'evento da risolvere.

Regole:
- nessun dato inventato: si compongono solo righe gia' costruite dai
  repository reali oppure scadenze aperte del Termometro (fonti certe);
- l'urgenza e' deterministica: scaduto > scade oggi > critico > udienza di
  oggi > alta priorita' > PEC non letta > conferimento mancante > azione
  ordinaria. Il conto alla rovescia usa il fuso Europe/Rome;
- ogni voce conserva l'href profondo verso l'evento (mai la lista generica).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote

__all__ = ["build_regia_worklist", "countdown_scadenza"]

# Punteggi di urgenza: piu' basso = piu' in alto nella coda.
_RANK_SCADUTA = 0
_RANK_SCADE_OGGI = 1
_RANK_CRITICA = 2
_RANK_UDIENZA_OGGI = 3
_RANK_ALTA = 4
_RANK_PEC_NON_LETTA = 5
_RANK_CONFERIMENTO = 6
_RANK_AZIONE = 7


def countdown_scadenza(due: date | None, oggi: date) -> tuple[str, str, int]:
    """(etichetta, tono, rank) del conto alla rovescia di una scadenza.

    Etichette italiane deterministiche: nessuna stima, solo aritmetica di
    calendario sul fuso dell'utente.
    """

    if due is None:
        return "", "warning", _RANK_ALTA
    delta = (due - oggi).days
    if delta < 0:
        giorni = -delta
        label = "SCADUTA IERI" if giorni == 1 else f"SCADUTA DA {giorni} GG"
        return label, "danger", _RANK_SCADUTA
    if delta == 0:
        return "SCADE OGGI", "danger", _RANK_SCADE_OGGI
    if delta == 1:
        return "SCADE DOMANI", "danger", _RANK_CRITICA
    if delta <= 7:
        return f"SCADE TRA {delta} GG", "warning", _RANK_CRITICA
    return f"TRA {delta} GG", "warning", _RANK_ALTA


def _copy_row(row: Mapping[str, Any], **overrides: Any) -> dict[str, Any]:
    out = dict(row)
    out.update(overrides)
    return out


def build_regia_worklist(
    *,
    oggi: date,
    scadenze: Iterable[Any],
    parse_date: Callable[[Any], date | None],
    enum_value: Callable[[Any], str],
    short_text: Callable[[Any, int], str],
    priorita_urgenti: set[str],
    agenda_rows: Iterable[Mapping[str, Any]],
    pec_rows: Iterable[Mapping[str, Any]],
    engagement_rows: Iterable[Mapping[str, Any]],
    operations: Iterable[Mapping[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Costruisce la coda «Da lavorare adesso» della Regia Operativa."""

    candidates: list[tuple[int, int, dict[str, Any]]] = []
    order = 0

    # 1. Scadenze aperte urgenti (fonte: Termometro/scadenziario reale).
    for scadenza in scadenze:
        priority = enum_value(getattr(scadenza, "priorita", ""))
        due = parse_date(getattr(scadenza, "data_scadenza", ""))
        label, tone, rank = countdown_scadenza(due, oggi)
        overdue_or_today = rank in {_RANK_SCADUTA, _RANK_SCADE_OGGI}
        if priority not in priorita_urgenti and not overdue_or_today:
            continue
        deadline_id = str(getattr(scadenza, "id", "") or "")
        candidates.append(
            (
                rank,
                order,
                {
                    "id": f"scadenza-{deadline_id or order}",
                    "title": short_text(getattr(scadenza, "titolo", "") or "Scadenza da lavorare", 90),
                    "subtitle": short_text(
                        " - ".join(
                            part
                            for part in [
                                "Scadenziario",
                                str(getattr(scadenza, "descrizione", "") or "").strip(),
                            ]
                            if part
                        ),
                        120,
                    ),
                    "time": due.strftime("%d/%m") if due else "",
                    "avatar": "",
                    "unread": False,
                    "badge": label or "URGENTE",
                    "tone": tone,
                    "href": f"/scadenziario/{quote(deadline_id)}" if deadline_id else "/scadenziario",
                },
            )
        )
        order += 1

    # 2. Udienze e appuntamenti di oggi (righe gia' pronte, con deep link).
    for row in agenda_rows:
        if str(row.get("badge") or "").upper() != "OGGI":
            continue
        candidates.append((_RANK_UDIENZA_OGGI, order, _copy_row(row, badge="OGGI", tone="warning")))
        order += 1

    # 3. PEC non lette: vanno presidiate in giornata.
    for row in pec_rows:
        if not row.get("unread"):
            continue
        candidates.append((_RANK_PEC_NON_LETTA, order, _copy_row(row, badge="PEC DA LEGGERE", tone="primary")))
        order += 1

    # 4. Conferimenti incarico mancanti: bloccano l'avvio della pratica.
    for row in engagement_rows:
        candidates.append((_RANK_CONFERIMENTO, order, _copy_row(row)))
        order += 1

    # 5. Azioni della regia (workspace intelligente), in coda alle urgenze.
    for row in operations:
        candidates.append((_RANK_AZIONE, order, _copy_row(row)))
        order += 1

    candidates.sort(key=lambda item: (item[0], item[1]))

    # Dedup per href: lo stesso evento puo' arrivare da piu' sorgenti
    # (es. scadenza urgente presente anche fra le azioni della regia).
    out: list[dict[str, Any]] = []
    seen_hrefs: set[str] = set()
    for _, _, row in candidates:
        href = str(row.get("href") or "")
        key = href or f"__row__{row.get('id')}"
        if key in seen_hrefs:
            continue
        seen_hrefs.add(key)
        out.append(row)
        if len(out) >= limit:
            break
    return out
