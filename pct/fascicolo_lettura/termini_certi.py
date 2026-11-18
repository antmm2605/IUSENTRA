"""Le proposte di scadenza (bozze) che il modello della causa rende certe: si registrano da sole, con la prova.

Il presidio PEC propone in bozza i termini letti in un provvedimento del giudice (``PEC_TERMINE_PROPOSTO``). Una bozza è
certa quando il modello della causa (pct/ragionamento) ha letto lo stesso termine nello stesso provvedimento: stesso
adempimento, stessa scadenza calcolata secondo la norma, nessun dubbio sul computo (destinazione della notifica, data
di pronuncia, udienza, comunicazione, parte onerata). Fonte certa + lettura certa = dato definitivo (regola
dell'avvocato): la bozza si conferma con la prova e non si chiede nulla. Resta da verificare solo la bozza che il
modello non conferma, con il motivo.

Modulo puro.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from ._testo import data_it, pulisci
from .passi_note_127_ter import _e_termine_note

# Codice della proposta del presidio PEC → codice della conclusione del modello.
_CODICI_PROPOSTA = {
    "LAV_415_NOTIFICA_TRENTA_GIORNI": "notifica_ricorso_decreto_415",
    "LAV_415_NOTIFICA_DIECI_GIORNI": "notifica_ricorso_decreto_415",
    "LAV_416_COSTITUZIONE": "costituzione_convenuto",
    "NOTE_127_TER": "note_127ter",
}
# Dubbi che rendono incerto il computo del termine: con questi la bozza resta da verificare.
_DUBBI_DEL_COMPUTO = {"destinazione_notifica_ignota", "pronuncia_ignota", "udienza_ignota", "comunicazione_non_trovata",
                      "parte_onerata_ignota", "adempimento_generico", "decorrenza_ignota"}
_RE_PROPOSTA = re.compile(r"PEC_TERMINE_PROPOSTO:[\w-]+:([A-Z0-9_]+)")


def codice_della_bozza(scadenza: dict[str, Any]) -> str:
    if scadenza.get("codice_proposta"):
        return str(scadenza["codice_proposta"])
    m = _RE_PROPOSTA.search(str(scadenza.get("note") or ""))
    if m and m.group(1) in _CODICI_PROPOSTA:
        return _CODICI_PROPOSTA[m.group(1)]
    titolo = pulisci(scadenza.get("titolo")).lower()
    if _e_termine_note(scadenza):
        return "note_127ter"
    if titolo.startswith(("notifica di ricorso e decreto", "notificare ricorso e decreto")):
        return "notifica_ricorso_decreto_415"
    if titolo.startswith("costituzione del convenuto") or titolo.startswith("costituzione del resistente"):
        return "costituzione_convenuto"
    return ""


def _scadenza_conclusione(voce: dict[str, Any]) -> str:
    termine = voce.get("termine") or {}
    return pulisci(termine.get("scadenza_iso") or termine.get("scadenza"))[:10]


def _onerato(voce: dict[str, Any]) -> str:
    return str(voce.get("onerato_codice") or voce.get("onerato") or "")


def bozze_della_controparte(scadenze: Iterable[dict[str, Any]], conclusioni: Iterable[dict[str, Any]] | None) -> set[str]:
    """Le bozze che sono termini della controparte letti nel provvedimento (es. costituzione del convenuto, art. 416
    c.p.c.): non sono adempimenti dello studio né dubbi; restano proposte informative, non si confermano da sole."""
    controparte = [c for c in conclusioni or [] if isinstance(c, dict) and _onerato(c) == "controparte"]
    return set(bozze_certe(scadenze, controparte, includi_controparte=True))


def bozze_certe(scadenze: Iterable[dict[str, Any]], conclusioni: Iterable[dict[str, Any]] | None, *,
                includi_controparte: bool = False) -> dict[str, str]:
    """Le bozze certe dello studio: id (o titolo, se manca l'id) → la prova (provvedimento del giudice letto dal modello)."""
    certe: dict[str, str] = {}
    lette = [c for c in conclusioni or [] if isinstance(c, dict)
             and (includi_controparte or _onerato(c) in {"noi", "tutte_le_parti", ""})]
    for scadenza in scadenze or []:
        if pulisci(scadenza.get("stato")).upper() != "BOZZA":
            continue
        codice = codice_della_bozza(scadenza)
        giorno = pulisci(scadenza.get("data") or scadenza.get("data_scadenza"))[:10]
        if not codice or not giorno:
            continue
        for voce in lette:
            letto = voce.get("letto") or {}
            documento = letto.get("documento") or letto.get("nome") or ""
            sorgente = letto.get("documento_id") or letto.get("oggetto_id") or ""
            dubbi = {d.get("codice") for d in voce.get("dubbi") or []}
            if (voce.get("codice") == codice and _scadenza_conclusione(voce) == giorno and sorgente
                    and not dubbi & _DUBBI_DEL_COMPUTO):
                quando = pulisci(letto.get("data")) if "/" in pulisci(letto.get("data")) else data_it(letto.get("data"))
                certe[pulisci(scadenza.get("id")) or pulisci(scadenza.get("titolo"))] = (
                    f"termine letto nel provvedimento del giudice «{documento}»" + (f" del {quando}" if quando else "")
                    + f" e calcolato dal modello della causa: scadenza {data_it(giorno)}")
                break
    return certe


__all__ = ["bozze_certe", "bozze_della_controparte", "codice_della_bozza"]
