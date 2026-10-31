"""Scadenza del documento d'identità del cliente: una sola data, preavviso a 60 e 30 giorni.

Base normativa: D.Lgs. 231/2007, artt. 18 e 19 (identificazione e verifica dell'identità su
documento d'identità non scaduto, controllo costante del rapporto); art. 35 D.P.R. 445/2000
(documenti equipollenti). La data è quella della scheda cliente; la scheda antiriciclaggio la
legge da lì quando non ne ha una propria, e segnala se le due date non coincidono.

Una data scritta male non solleva eccezioni: diventa «data non valida» da correggere.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

PREAVVISI = (60, 30)
MARCATORE = "DOC_IDENTITA:{cliente}:{scadenza}"


def data_scadenza(valore: Any) -> date | None:
    try:
        return date.fromisoformat(str(valore or "").strip()[:10])
    except ValueError:
        return None


def stato_documento(scadenza: Any, oggi: date) -> dict[str, Any]:
    """Stato del documento: valido, in scadenza (entro 60 o 30 giorni), scaduto, non indicata o non valida."""
    testo = str(scadenza or "").strip()
    if not testo:
        return {"stato": "non_indicata", "giorni": None, "messaggio": "Scadenza del documento d'identità non indicata."}
    giorno = data_scadenza(testo)
    if giorno is None:
        return {"stato": "data_non_valida", "giorni": None,
                "messaggio": f"La scadenza del documento d'identità «{testo}» non è una data valida: correggila."}
    giorni = (giorno - oggi).days
    quando = giorno.strftime("%d/%m/%Y")
    if giorni < 0:
        return {"stato": "scaduto", "giorni": giorni,
                "messaggio": f"Documento d'identità scaduto il {quando}: acquisiscine uno valido (artt. 18-19 D.Lgs. 231/2007)."}
    for soglia in sorted(PREAVVISI):
        if giorni <= soglia:
            return {"stato": f"in_scadenza_{soglia}", "giorni": giorni,
                    "messaggio": f"Documento d'identità in scadenza il {quando} (fra {giorni} giorni): chiedine il rinnovo."}
    return {"stato": "valido", "giorni": giorni, "messaggio": ""}


def scadenza_unica(scheda_cliente: Any, scheda_antiriciclaggio: Any) -> dict[str, Any]:
    """La data della scheda cliente prevale; quella antiriciclaggio vale solo se la prima manca."""
    cliente, aml = str(scheda_cliente or "").strip()[:10], str(scheda_antiriciclaggio or "").strip()[:10]
    esito = {"scadenza": cliente or aml, "fonte": "scheda cliente" if cliente else ("scheda antiriciclaggio" if aml else ""),
             "avviso": ""}
    if cliente and aml and cliente != aml:
        esito["avviso"] = ("La scadenza del documento nella scheda antiriciclaggio è diversa da quella della scheda "
                           "cliente: vale la scheda cliente, allinea l'altra.")
    return esito


def proponi_rinnovi(clienti: Iterable[Any], scadenziario: Any, *, oggi: date) -> dict[str, int]:
    """Una voce nello scadenziario per ogni documento attivo che scade entro 60 giorni, senza doppioni."""
    from pct.scadenziario import TipoTermine

    esito = {"proposte": 0, "date_non_valide": 0}
    esistenti = " ".join(str(getattr(s, "note", "") or "") for s in scadenziario.tutte(solo_aperte=False))
    for cliente in clienti:
        if str(getattr(getattr(cliente, "stato", ""), "value", getattr(cliente, "stato", "")) or "") not in {"", "ATTIVO"}:
            continue
        documento = getattr(cliente, "documento", None)
        stato = stato_documento(getattr(documento, "data_scadenza", ""), oggi)
        if stato["stato"] == "data_non_valida":
            esito["date_non_valide"] += 1
            continue
        if not stato["stato"].startswith("in_scadenza_"):
            continue
        scadenza = str(getattr(documento, "data_scadenza", ""))[:10]
        marcatore = MARCATORE.format(cliente=getattr(cliente, "id", ""), scadenza=scadenza)
        if marcatore in esistenti:
            continue
        nome = str(getattr(cliente, "nome_completo", "") or getattr(cliente, "id", ""))
        scadenziario.nuova(
            titolo=f"Rinnovo documento d'identità di {nome}", tipo=TipoTermine.ADEMPIMENTO, data_scadenza=scadenza,
            descrizione="Il documento d'identità del cliente scade: chiedi la copia del nuovo documento "
                        "(artt. 18-19 D.Lgs. 231/2007).",
            giorni_preavviso=[60, 30, 7], note=f"{marcatore}\nProposta automatica dalla scheda cliente.",
        )
        esistenti += f" {marcatore}"
        esito["proposte"] += 1
    return esito


__all__ = ["MARCATORE", "PREAVVISI", "data_scadenza", "proponi_rinnovi", "scadenza_unica", "stato_documento"]
