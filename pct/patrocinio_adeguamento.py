"""Sorveglianza del decreto che adegua il limite di reddito per il patrocinio.

L'art. 77 D.P.R. 115/2002 prevede che l'importo dell'art. 76, comma 1, sia
adeguato ogni due anni con decreto del Ministero della giustizia di concerto
con il MEF, in relazione alla variazione ISTAT dei prezzi al consumo. Quel
decreto si pubblica in Gazzetta Ufficiale, e finche' non esce nessuno sa che
numero porta: per questo la soglia non si «calcola», si legge dal decreto.

La tabella ``patrocinio_limiti_reddito`` tiene una riga per decreto, versionata
nel codice. Questo modulo non la riscrive da solo — una soglia di legge non si
cambia senza che un avvocato l'abbia vista — ma sorveglia la Gazzetta, e quando
trova un decreto di adeguamento che la tabella non conosce prepara la riga da
aggiungere, con l'importo letto, il riferimento della pubblicazione e il
collegamento all'atto. All'avvocato resta di confermare.

Perche' la Gazzetta e non altro: la scheda del Ministero della giustizia sul
patrocinio resta indietro di mesi (a ottobre 2024 riportava ancora l'importo
del D.M. 2023), e Normattiva non espone l'importo vigente perche' i decreti di
adeguamento non modificano il testo dell'art. 76. La Gazzetta e' dove l'atto
nasce, ed e' gia' censita fra le fonti ufficiali del sistema (trust A).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable

from pct.soglie_nei_documenti import TABELLA_LIMITI, _euro

#: Ricerca della Gazzetta Ufficiale, Serie Generale, per testo.
RICERCA_GAZZETTA = (
    "https://www.gazzettaufficiale.it/ricerca/pdf/foglio_ordinario2/1/0/0"
)
#: Pagina di ricerca libera: e' l'ingresso pubblico e stabile della fonte.
RICERCA_TESTO = "https://www.gazzettaufficiale.it/ricerca/testo?testo={query}"

#: Le parole che un decreto di adeguamento porta sempre con se'. Devono
#: comparire tutte: un atto che parla d'altro non entra.
PAROLE_RICHIESTE: tuple[tuple[str, ...], ...] = (
    ("adeguamento", "aggiornamento", "adeguati", "modifica"),
    ("patrocinio",),
    ("reddito",),
)

_IMPORTO = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}")


def _testo(valore: Any) -> str:
    return " ".join(str(valore if valore is not None else "").split())


def _decimale(testo: str) -> Decimal | None:
    try:
        return Decimal(str(testo).replace(".", "").replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def riguarda_il_patrocinio(titolo: str, testo: str = "") -> bool:
    """Se l'atto e' un adeguamento dei limiti di reddito per il patrocinio."""
    materia = f"{_testo(titolo)} {_testo(testo)}".casefold()
    return all(any(parola in materia for parola in gruppo) for gruppo in PAROLE_RICHIESTE)


def importo_dichiarato(testo: str) -> Decimal | None:
    """L'importo del limite dichiarato dall'atto.

    Si prende il maggiore fra quelli scritti in forma di euro con i decimali:
    il decreto cita il nuovo limite e, nelle premesse, quello che sostituisce.
    Se l'atto non porta nessun importo leggibile non si inventa: si restituisce
    nulla e la proposta dira' che l'importo va letto a mano.
    """
    valori = [v for v in (_decimale(p) for p in _IMPORTO.findall(_testo(testo))) if v and v > 0]
    return max(valori) if valori else None


def soglia_in_tabella(norme: Any) -> dict[str, Any]:
    """L'ultima riga che la tabella versionata conosce."""
    righe = [dict(r) for r in norme.rows(TABELLA_LIMITI) if r.get("effective_from") and r.get("amount")]
    righe.sort(key=lambda r: str(r.get("effective_from")))
    return righe[-1] if righe else {}


def proposta_di_aggiornamento(
    atti: Iterable[dict[str, Any]],
    norme: Any,
    *,
    oggi: date | None = None,
) -> dict[str, Any]:
    """Confronta gli atti trovati in Gazzetta con la tabella e prepara la riga.

    Gli ``atti`` sono quelli che la pipeline delle fonti ha gia' raccolto:
    ognuno con titolo, data di pubblicazione, url e, se disponibile, il testo.
    Non si scrive nulla: si restituisce che cosa e' stato trovato e la riga da
    aggiungere a ``patrocinio_limiti_reddito``, perche' sia un avvocato ad
    accettarla.
    """
    ultima = soglia_in_tabella(norme)
    nota = Decimal(str(ultima.get("amount") or 0))
    dal_noto = _testo(ultima.get("effective_from"))
    candidati = []
    for atto in atti:
        titolo = _testo(atto.get("titolo") or atto.get("title"))
        testo = _testo(atto.get("testo") or atto.get("text") or "")
        if not riguarda_il_patrocinio(titolo, testo):
            continue
        pubblicato = _testo(atto.get("data") or atto.get("published_at") or atto.get("data_pubblicazione"))
        if pubblicato and dal_noto and pubblicato <= dal_noto:
            continue
        importo = importo_dichiarato(f"{titolo} {testo}")
        if importo is not None and nota and importo == nota:
            continue
        candidati.append({
            "titolo": titolo,
            "pubblicato": pubblicato,
            "url": _testo(atto.get("url") or atto.get("link")),
            "importo": importo,
        })
    if not candidati:
        return {
            "aggiornamento": False,
            "soglia_nota": float(nota) if nota else None,
            "decreto_noto": _testo(ultima.get("decreto")),
            "messaggio": (
                f"Nessun nuovo decreto di adeguamento in Gazzetta: resta vigente "
                f"{_euro(nota)} euro del {_testo(ultima.get('decreto'))}."
                if nota else "Nessun decreto di adeguamento trovato e nessuna soglia in tabella."
            ),
        }
    candidati.sort(key=lambda c: c["pubblicato"], reverse=True)
    trovato = candidati[0]
    importo = trovato["importo"]
    riga = {
        "effective_from": trovato["pubblicato"],
        "amount": float(importo) if importo is not None else None,
        "decreto": trovato["titolo"],
        "gazzetta": trovato["url"],
        "note": "Riga proposta dalla sorveglianza della Gazzetta Ufficiale: da confermare sull'atto.",
    }
    if importo is None:
        messaggio = (
            f"Trovato in Gazzetta un decreto di adeguamento ({trovato['titolo']}) del "
            f"{trovato['pubblicato']}, ma l'importo non e' leggibile dal testo raccolto: "
            "apri l'atto e riporta il limite a mano."
        )
    else:
        messaggio = (
            f"Trovato in Gazzetta un decreto di adeguamento: {trovato['titolo']} "
            f"({trovato['pubblicato']}) porta il limite dell'art. 76 a {_euro(importo)} euro "
            f"— in tabella c'e' ancora {_euro(nota)} euro del {_testo(ultima.get('decreto'))}. "
            f"Il parametro dell'art. 9 comma 1-bis diventa {_euro(importo * 3)} euro."
        )
    return {
        "aggiornamento": True,
        "soglia_nota": float(nota) if nota else None,
        "decreto_noto": _testo(ultima.get("decreto")),
        "atto": trovato,
        "riga_proposta": riga,
        "messaggio": messaggio,
    }


def controlla_adeguamento(
    norme: Any,
    leggi_atti: Callable[[], Iterable[dict[str, Any]]],
    *,
    oggi: date | None = None,
) -> dict[str, Any]:
    """Il controllo periodico: legge gli atti dalla fonte e prepara l'esito.

    ``leggi_atti`` e' iniettato perche' la raccolta dalla Gazzetta e' gia'
    compito della pipeline delle fonti legali: qui si decide soltanto, e il
    modulo resta verificabile senza rete.
    """
    try:
        atti = list(leggi_atti() or [])
    except Exception as errore:  # la fonte non risponde: si dice, non si indovina
        return {
            "aggiornamento": False,
            "errore": str(errore),
            "messaggio": "Gazzetta Ufficiale non raggiungibile: controllo rinviato, soglia invariata.",
        }
    return proposta_di_aggiornamento(atti, norme, oggi=oggi)


__all__ = [
    "PAROLE_RICHIESTE",
    "RICERCA_GAZZETTA",
    "RICERCA_TESTO",
    "controlla_adeguamento",
    "importo_dichiarato",
    "proposta_di_aggiornamento",
    "riguarda_il_patrocinio",
    "soglia_in_tabella",
]
