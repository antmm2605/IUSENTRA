"""Un documento che cita una soglia di legge ormai superata.

Un modulo preparato due anni fa continua a girare con l'importo di allora.
E' successo con l'autocertificazione per l'esenzione dal contributo unificato:
il modello riportava 38.514,03 euro — il triplo del limite fissato dal D.M. 10
maggio 2023 — quando il D.M. 22 aprile 2025 aveva gia' portato quel triplo a
40.978,92. Chi lo compila dichiara su una soglia che non esiste piu'.

Qui non si indovina: si confronta ogni importo scritto nel documento con i
valori che la tabella normativa versionata conosce. Si segnala solo l'importo
che coincide, al centesimo, con una soglia che quella tabella registra come
non piu' vigente — con il decreto che l'ha sostituita. Un numero qualunque,
per quanto somigliante, non produce avvisi.

Base normativa: art. 76 e art. 77 D.P.R. 115/2002 (limite di reddito e suo
adeguamento biennale con decreto interministeriale), art. 9 comma 1-bis dello
stesso testo unico per l'esenzione dal contributo unificato, il cui parametro
e' il triplo di quel limite.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

TABELLA_LIMITI = "patrocinio_limiti_reddito"

#: Il parametro dell'art. 9 comma 1-bis e' il triplo del limite dell'art. 76:
#: un modulo di esenzione cita quello, non il limite base.
MULTIPLI_DICHIARATI: tuple[tuple[int, str], ...] = (
    (1, "limite di reddito per il patrocinio a spese dello Stato (art. 76 D.P.R. 115/2002)"),
    (3, "triplo del limite, parametro per l'esenzione dal contributo unificato (art. 9 comma 1-bis D.P.R. 115/2002)"),
)

_IMPORTO = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2}")


def _euro(valore: Decimal) -> str:
    """L'importo come lo scrive un atto italiano: 40.978,92."""
    intero, _punto, centesimi = f"{valore:.2f}".partition(".")
    gruppi = f"{int(intero):,}".replace(",", ".")
    return f"{gruppi},{centesimi}"


def _decimale(testo: str) -> Decimal | None:
    try:
        return Decimal(testo.replace(".", "").replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def importi_nel_testo(testo: str) -> set[Decimal]:
    """Gli importi in euro scritti nel documento, nella forma italiana."""
    trovati = set()
    for pezzo in _IMPORTO.findall(str(testo or "")):
        valore = _decimale(pezzo)
        if valore is not None and valore > 0:
            trovati.add(valore)
    return trovati


def _righe_ordinate(norme: Any) -> list[dict[str, Any]]:
    righe = [dict(r) for r in norme.rows(TABELLA_LIMITI) if r.get("effective_from") and r.get("amount")]
    return sorted(righe, key=lambda r: str(r.get("effective_from")))


def soglie_conosciute(norme: Any, riferimento: date | None = None) -> dict[Decimal, dict[str, Any]]:
    """Ogni importo che la tabella conosce, con il suo decreto e se e' vigente."""
    oggi = riferimento or date.today()
    righe = _righe_ordinate(norme)
    vigente = None
    for riga in righe:
        if str(riga.get("effective_from")) <= oggi.isoformat():
            vigente = riga
    conosciute: dict[Decimal, dict[str, Any]] = {}
    for riga in righe:
        base = Decimal(str(riga.get("amount")))
        for fattore, descrizione in MULTIPLI_DICHIARATI:
            conosciute[(base * fattore).quantize(Decimal("0.01"))] = {
                "decreto": str(riga.get("decreto") or ""),
                "gazzetta": str(riga.get("gazzetta") or ""),
                "dal": str(riga.get("effective_from") or ""),
                "fattore": fattore,
                "descrizione": descrizione,
                "vigente": riga is vigente,
                "sostituito_da": None,
            }
    if vigente is not None:
        for valore, dati in conosciute.items():
            if not dati["vigente"]:
                atteso = (Decimal(str(vigente.get("amount"))) * dati["fattore"]).quantize(Decimal("0.01"))
                dati["sostituito_da"] = {
                    "importo": atteso,
                    "decreto": str(vigente.get("decreto") or ""),
                    "gazzetta": str(vigente.get("gazzetta") or ""),
                    "dal": str(vigente.get("effective_from") or ""),
                }
    return conosciute


def soglie_superate_nel_testo(
    testo: str,
    norme: Any,
    riferimento: date | None = None,
) -> list[dict[str, Any]]:
    """Le soglie non piu' vigenti citate dal documento, con quella che le sostituisce."""
    conosciute = soglie_conosciute(norme, riferimento)
    segnalazioni = []
    for importo in sorted(importi_nel_testo(testo)):
        dati = conosciute.get(importo)
        if not dati or dati["vigente"] or not dati["sostituito_da"]:
            continue
        nuovo = dati["sostituito_da"]
        segnalazioni.append({
            "importo_citato": f"{importo:.2f}",
            "importo_vigente": f"{nuovo['importo']:.2f}",
            "descrizione": dati["descrizione"],
            "decreto_citato": dati["decreto"],
            "decreto_vigente": nuovo["decreto"],
            "gazzetta_vigente": nuovo["gazzetta"],
            "vigente_dal": nuovo["dal"],
            "messaggio": (
                f"Il documento riporta {_euro(importo)} euro come {dati['descrizione']}: "
                f"è l'importo del {dati['decreto']}, superato dal {nuovo['decreto']} "
                f"({nuovo['gazzetta']}), che dal {nuovo['dal']} lo porta a {_euro(nuovo['importo'])} euro."
            ),
        })
    return segnalazioni


def soglie_superate_nel_pdf(raw: bytes, norme: Any, riferimento: date | None = None) -> list[dict[str, Any]]:
    """Come sopra, leggendo il testo di un PDF."""
    from pct.lettura_pdf import leggi_testo

    return soglie_superate_nel_testo(leggi_testo(raw), norme, riferimento)


__all__ = [
    "MULTIPLI_DICHIARATI",
    "TABELLA_LIMITI",
    "_euro",
    "importi_nel_testo",
    "soglie_conosciute",
    "soglie_superate_nel_pdf",
    "soglie_superate_nel_testo",
]
