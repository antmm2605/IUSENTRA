"""Una sola proforma automatica per lo stesso compenso: la bozza superata si dichiara superata, non si somma.

Il compenso della fase decisa si chiede una volta sola: l'avviso di parcella (proforma) precede la
fattura, che si emette al pagamento per l'importo ricevuto (art. 6, terzo comma, e art. 21, comma 4,
D.P.R. 633/1972). Due motori producevano bozze automatiche per lo stesso compenso (collaudo 10/11/2026,
G-13: 2026/036 «Bozza automatica da fascicolo definito» € 296,70 e 2026/062 dalla sentenza € 515,00,
sommate in «Parcella € 811,70»). Regole:

1. **La fonte più certa vince**: la bozza dal capo spese della sentenza (importo liquidato dal giudice,
   art. 91 c.p.c., D.M. 55/2014) prevale sulla bozza di riserva del fascicolo definito (importo della voce);
   a parità di fonte vale la più recente.
2. **La superata resta, dichiarata**: non si annulla né si cancella (la decisione è dell'avvocato); porta
   il segno «superata da …» e non entra nei totali.
3. Solo bozze automatiche: una proforma creata o toccata dall'avvocato, una fattura o un documento
   pagato non si toccano mai.

Modulo puro: riceve le parcelle già lette e restituisce le decisioni; la scrittura è del chiamante.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

ORIGINE_SENTENZA = "lex_ai_sentenza_tribunale"
ORIGINE_FASCICOLO_DEFINITO = "presidio_economico_fascicolo_definito"
PRIORITA = {ORIGINE_SENTENZA: 0, ORIGINE_FASCICOLO_DEFINITO: 1}
CHIAVE_SUPERATA = "superata"
NORMA = "art. 6, terzo comma, e art. 21, comma 4, D.P.R. 633/1972"


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def _campo(parcella: Any, nome: str, predefinito: Any = "") -> Any:
    return parcella.get(nome, predefinito) if isinstance(parcella, Mapping) else getattr(parcella, nome, predefinito)


def dati(parcella: Any) -> dict[str, Any]:
    valore = _campo(parcella, "dati_personalizzati", {}) or {}
    return dict(valore) if isinstance(valore, Mapping) else {}


def superata(parcella: Any) -> bool:
    return bool(dati(parcella).get(CHIAVE_SUPERATA))


def bozza_automatica(parcella: Any) -> bool:
    """Bozza creata da un motore automatico, non toccata a mano dall'avvocato."""
    stato = _testo(_campo(parcella, "stato")).upper().replace("STATOPARCELLA.", "")
    return stato == "BOZZA" and _testo(_campo(parcella, "origine")) in PRIORITA and not dati(parcella).get("modificata_da_avvocato")


def decidi(parcelle: Iterable[Any]) -> tuple[Any | None, list[Any]]:
    """(bozza valida, bozze da dichiarare superate) fra le bozze automatiche dello stesso fascicolo."""
    bozze = [p for p in parcelle if bozza_automatica(p)]
    if len(bozze) < 2:
        return (bozze[0] if bozze else None), []
    ordinate = sorted(bozze, key=lambda p: (PRIORITA[_testo(_campo(p, "origine"))],
                                            # la più recente prima: creata_il o, in mancanza, il numero progressivo
                                            _invertito(_testo(_campo(p, "creato_il") or _campo(p, "created_at") or _campo(p, "numero")))))
    valida = ordinate[0]
    return valida, [p for p in ordinate[1:] if not superata(p)]


def _invertito(testo: str) -> tuple[int, ...]:
    return tuple(-ord(c) for c in testo)


def segno_superata(valida: Any, *, adesso: str = "") -> dict[str, Any]:
    numero = _testo(_campo(valida, "numero"))
    return {"da_id": _testo(_campo(valida, "id")), "da_numero": numero, "il": adesso,
            "motivo": (f"Stesso compenso della proforma {numero}, che ha la fonte più certa: questa bozza non si somma. "
                       f"Proposta all'avvocato: annullarla ({NORMA})."),
            "proposta": "annullare"}


def attive_non_superate(parcelle: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Le parcelle che contano nei totali: non annullate e non dichiarate superate."""
    return [p for p in parcelle if _testo(p.get("stato")).upper() != "ANNULLATA" and not p.get("superata")]


__all__ = ["CHIAVE_SUPERATA", "NORMA", "ORIGINE_FASCICOLO_DEFINITO", "ORIGINE_SENTENZA", "attive_non_superate",
           "bozza_automatica", "dati", "decidi", "segno_superata", "superata"]
