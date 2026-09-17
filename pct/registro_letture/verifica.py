"""La verifica delle letture: dai dati letti alle anomalie da confermare.

Funzioni pure. Ricevono l'esito di una lettura — le date processuali con il
loro contesto, le date nel testo, i riferimenti — e il contesto del fascicolo,
e restituiscono le anomalie nel formato che il registro persiste: campo,
valore letto, valore proposto, motivo, codice, gravità.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from .verifica_date import interpreta_data, valuta_data

CAMPI_PROCESSUALI = ("udienza", "termine", "scadenza", "deposito", "notifica", "comunicazione", "sentenza", "provvedimento")


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _campo_processuale(etichetta: str) -> bool:
    chiave = _testo(etichetta).casefold()
    return any(token in chiave for token in CAMPI_PROCESSUALI)


def verifica_date_lette(date_lette: Iterable[Any], contesto: dict[str, Any]) -> list[dict[str, Any]]:
    """Ogni data letta diventa un'anomalia se il giudizio non è «valida».

    Una voce può essere una stringa (data trovata nel testo, campo «data») o un
    dizionario con `valore`, `campo` (udienza, termine, …), `contesto` (il
    brano), `confronto` (data nota da altra fonte) ed `etichetta_confronto`.
    """
    oggi = contesto.get("oggi") or date.today()
    anno = contesto.get("anno_riferimento")
    data_minima = contesto.get("data_minima")
    anomalie: list[dict[str, Any]] = []
    viste: set[tuple[str, str]] = set()
    for voce in date_lette:
        if isinstance(voce, dict):
            valore = _testo(voce.get("valore") or voce.get("raw_date") or voce.get("date"))
            campo = _testo(voce.get("campo") or voce.get("label")) or "data"
            brano = _testo(voce.get("contesto") or voce.get("context"))
            confronto = interpreta_data(voce.get("confronto"))
            etichetta_confronto = _testo(voce.get("etichetta_confronto"))
        else:
            valore, campo, brano, confronto, etichetta_confronto = _testo(voce), "data", "", None, ""
        if not valore or (campo, valore) in viste:
            continue
        viste.add((campo, valore))
        giudizio = valuta_data(
            valore, oggi=oggi, anno_riferimento=anno,
            data_minima=data_minima if _campo_processuale(campo) else None,
            data_confronto=confronto, etichetta_confronto=etichetta_confronto,
        )
        # Nascita, scadenza del documento e citazioni storiche non seguono
        # l'orizzonte della causa. Restano controlli di calendario e concordanza.
        if not _campo_processuale(campo) and set(giudizio.codici) <= {"anno_remoto", "anno_futuro"}:
            continue
        if giudizio.stato == "valida":
            continue
        anomalie.append({
            "campo": campo,
            "valore_letto": valore,
            "valore_proposto": giudizio.valore_proposto,
            "contesto": brano[:300],
            "motivo": " ".join(giudizio.motivi),
            "codice": giudizio.codici[0] if giudizio.codici else "data_sospetta",
            "gravita": giudizio.gravita,
        })
    return anomalie


def verifica_lettura(esito: dict[str, Any], contesto: dict[str, Any]) -> list[dict[str, Any]]:
    """Le anomalie di una lettura: date processuali con contesto, poi le altre date del testo."""
    date_lette: list[Any] = []
    for voce in list(esito.get("date_processuali") or []):
        if isinstance(voce, dict):
            date_lette.append(voce)
    for voce in list(esito.get("date") or []):
        date_lette.append(voce if isinstance(voce, dict) else {"valore": voce, "campo": "data"})
    return verifica_date_lette(date_lette, contesto)


def applica_correzioni(valori: Iterable[dict[str, Any]], correzioni: dict[tuple[str, str, str], str], *, oggetto_id: str, campo: str = "") -> list[dict[str, Any]]:
    """Sostituisce nei valori letti quelli che l'avvocato ha corretto o confermato."""
    esito: list[dict[str, Any]] = []
    for voce in valori:
        copia = dict(voce)
        nome_campo = campo or _testo(voce.get("campo") or voce.get("label")) or "data"
        letto = _testo(voce.get("valore") or voce.get("raw_date") or voce.get("date"))
        giusto = correzioni.get((oggetto_id, nome_campo, letto))
        if giusto:
            copia["valore_corretto"] = giusto
            data = interpreta_data(giusto)
            if data is not None:
                copia["date"] = data.isoformat()
                copia["valore"] = giusto
        esito.append(copia)
    return esito


__all__ = ["CAMPI_PROCESSUALI", "applica_correzioni", "verifica_date_lette", "verifica_lettura"]
