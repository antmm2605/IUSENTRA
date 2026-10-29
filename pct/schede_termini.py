"""Termini delle schede di compilazione calcolati dal software, non da Lex.

Un campo ``calcolo`` di una scheda può dichiarare ``termine``: evento da cui decorre (``base``), durata in
giorni o mesi, direzione (``avanti`` o ``ritroso``) e applicazione della sospensione feriale. Il calcolo usa
lo stesso motore dello scadenziario (``pct.termini_processuali.ItalianDeadlineCalculator``): art. 155 c.p.c.
(dies a quo escluso, proroga o anticipo se l'ultimo giorno è sabato o festivo; per i termini sostanziali, art. 2963
c.c., e penali, art. 172 c.p.p., il sabato non proroga: ``sabato: false``) e L. 742/1969 (sospensione
dal 1° al 31 agosto). Lex riceve la data già calcolata e si limita a spiegarla.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from pct.termini_processuali import LETTURA_PRUDENZIALE, ItalianDeadlineCalculator

# Evento di partenza → fatti dell'archivio delle letture da cui leggerne la data
BASI = {
    "udienza": [{"categoria": "data", "campo": "udienza"}],
    "notifica": [{"categoria": "data", "campo": "notifica"}, {"categoria": "prova_notifica"}],
    "comunicazione": [{"categoria": "data", "campo": "comunicazione"}],
    "provvedimento": [{"categoria": "data", "campo": "provvedimento"}],
    "evento": [{"categoria": "data", "campo": "evento"}],
}
CHIAVI = {"base", "giorni", "mesi", "direzione", "feriale", "sabato", "liberi"}


def valida_termine(termine: dict[str, Any]) -> list[str]:
    """Errori di forma della dichiarazione ``termine`` di un campo."""
    errori = [f"chiave sconosciuta: {k}" for k in termine if k not in CHIAVI]
    if termine.get("base") not in BASI:
        errori.append(f"base non ammessa: {termine.get('base')}")
    if bool(termine.get("giorni")) == bool(termine.get("mesi")):
        errori.append("indicare giorni oppure mesi")
    for unita in ("giorni", "mesi"):
        if unita in termine and (type(termine[unita]) is not int or termine[unita] <= 0):
            errori.append(f"{unita} deve essere un intero positivo")
    if termine.get("direzione") not in ("avanti", "ritroso"):
        errori.append("direzione deve essere avanti o ritroso")
    if not isinstance(termine.get("feriale"), bool):
        errori.append("feriale deve essere vero o falso")
    if "sabato" in termine and not isinstance(termine["sabato"], bool):
        errori.append("sabato deve essere vero o falso")
    if "liberi" in termine and not isinstance(termine["liberi"], bool):
        errori.append("liberi deve essere vero o falso")
    return errori


def _data(valore: Any) -> date | None:
    try:
        return date.fromisoformat(str(valore)[:10])
    except ValueError:
        return None


def fatti_base(termine: dict[str, Any], fatti: Iterable[Any]) -> list[Any]:
    """Fonti pertinenti e utilizzabili; nessuna scelta per ordine di lettura."""
    from pct.registro_letture.fatti_repository import VERIFICHE_UTILI
    return [fatto for fatto in fatti
            if getattr(fatto, "verifica", "") in VERIFICHE_UTILI
            and _data(getattr(fatto, "valore", "")) is not None
            and any(getattr(fatto, "categoria", "") == sel["categoria"]
                    and (not sel.get("campo") or getattr(fatto, "campo", "") == sel["campo"])
                    for sel in BASI[termine["base"]])]


def data_base(termine: dict[str, Any], fatti: Iterable[Any]) -> date | None:
    """Date discordanti richiedono riscontro: non si prende la prima disponibile."""
    date_lette = {_data(fatto.valore) for fatto in fatti_base(termine, fatti)}
    if len(date_lette) > 1:
        raise ValueError("Più date di partenza discordanti: verificare la fonte pertinente prima del calcolo.")
    return next(iter(date_lette), None)


def calcola(termine: dict[str, Any], base: date) -> dict[str, Any]:
    """Scadenza e spiegazione del termine a partire dalla data base."""
    errori = valida_termine(termine)
    if errori:
        raise ValueError("; ".join(errori))
    unita = "months" if termine.get("mesi") else "days"
    valore = int(termine.get("mesi") or termine.get("giorni"))
    ritroso = termine["direzione"] == "ritroso"
    # «Almeno N giorni prima»: data prudenziale a giorni liberi e, accanto, la scadenza di legge a giorni pieni.
    # I termini che la norma dichiara già «liberi» (``liberi: true``) restano come scritti nella scheda.
    prudenziale = ritroso and not termine.get("liberi")
    r = ItalianDeadlineCalculator().calculate(
        base, valore, "backward" if ritroso else "forward",
        suspend_august=termine["feriale"], period_type=unita, extend_saturday=termine.get("sabato", True),
        metadata={LETTURA_PRUDENZIALE: True} if prudenziale else {})
    return {"scadenza": r["deadline"], "base": base.isoformat(), "spiegazione": r["explanation"],
            "scadenza_di_legge": r.get("legalDeadline") or "",
            "verifica_avvocato": bool(r.get("requiresLegalReview"))}
