"""Riconvalida dei dati economici e delle scadenze di notifica già salvati, con le regole di oggi.

Gira nella riconvalida del ciclo delle letture (``archivio_letture_runtime._riconvalida``: a ogni giro e nelle
verifiche periodiche notturne dei presìdi), sul solo fascicolo in lavorazione e senza leggere documenti:

1. **«Pagato» senza prova** (``pct.incasso_provato``): la voce della liquidazione o della parcella segnata come
   pagata da un automatismo, senza incasso registrato né prova letta, torna «da incassare» (artt. 1188 e 2697 c.c.);
   la decisione dell'avvocato non si tocca mai.
2. **Proforma automatiche doppie** (``pct.proforma_unica``): la bozza superata dalla proforma dalla sentenza si
   dichiara superata (non si annulla: la proposta di annullamento è per l'avvocato); la voce «parcella» automatica
   riporta il totale della proforma valida, lo stesso del documento (accessori D.M. 55/2014 e regime dello studio).
3. **Scadenze degli obblighi di notifica** (``web.services.obblighi_notifica_runtime.allinea_scadenze``): un obbligo
   aperto con termine futuro entra nello scadenziario una volta sola.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

VOCI_DA_INCASSARE = ("liquidazione_giudice", "parcella")


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def _adesso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def incasso_registrato(fascicolo_id: str) -> bool:
    """Un incasso registrato nel fascicolo: parcella pagata o ricevuta nel registro degli incassi."""
    try:
        from web.services.fascicolo_conto_economico_runtime import parcelle_del_fascicolo

        return any(float(p.get("incassato") or 0) > 0 or _testo(p.get("stato")).upper() == "PAGATA"
                   for p in parcelle_del_fascicolo(fascicolo_id))
    except Exception:
        logger.debug("Incassi non leggibili per %s: nessuna riconvalida dei pagamenti", fascicolo_id, exc_info=True)
        return True  # nel dubbio non si tocca nulla


def riconvalida_incassi(fascicolo: Any, *, repository: Any) -> list[str]:
    from pct.incasso_provato import riconvalida_voce

    fid = _testo(getattr(fascicolo, "id", ""))
    pagamenti = dict(getattr(fascicolo, "pagamenti", {}) or {})
    if not any(isinstance(pagamenti.get(k), dict) and _testo(pagamenti[k].get("status")).lower() in {"pagato", "parziale"}
               for k in VOCI_DA_INCASSARE):
        return []
    registrato = incasso_registrato(fid)
    cambiate = []
    adesso = _adesso()
    for chiave in VOCI_DA_INCASSARE:
        voce = pagamenti.get(chiave)
        nuova = riconvalida_voce(voce, incasso_registrato=registrato, adesso=adesso) if isinstance(voce, dict) else None
        if nuova is not None:
            pagamenti[chiave] = nuova
            cambiate.append(chiave)
    if cambiate:
        repository.aggiorna_pagamenti(fid, pagamenti)
    return cambiate


def riconvalida_proforme(fascicolo: Any, *, repository: Any, fatturazione: Any) -> dict[str, Any]:
    from pct.incasso_provato import autore_automatico
    from pct.proforma_unica import CHIAVE_SUPERATA, dati, decidi, segno_superata

    fid = _testo(getattr(fascicolo, "id", ""))
    parcelle = list(fatturazione.per_fascicolo(fid) or [])
    valida, superate = decidi(parcelle)
    esito: dict[str, Any] = {"superate": [], "voce_parcella": False}
    for parcella in superate:
        nuovi = dati(parcella)
        nuovi[CHIAVE_SUPERATA] = segno_superata(valida, adesso=_adesso())
        fatturazione.aggiorna(_testo(parcella.id), dati_personalizzati=nuovi)
        esito["superate"].append(_testo(getattr(parcella, "numero", "")))
    if valida is None:
        return esito
    # La bozza automatica porta la data in cui è stata predisposta, non quella della sentenza (art. 21, comma 2,
    # lett. a, D.P.R. 633/1972: la data è quella del documento): regola in vigore dal 08/11/2026, qui per le bozze già salvate.
    creata = _testo(getattr(valida, "creato_il", ""))[:10]
    if creata and _testo(getattr(valida, "data_emissione", ""))[:10] < creata and len(creata) == 10:
        dati_valida = dati(valida)
        documento = dict(dati_valida.get("document") or {})
        documento.setdefault("data_sentenza", _testo(getattr(valida, "data_emissione", ""))[:10])
        documento["data_documento"] = creata
        dati_valida["document"] = documento
        fatturazione.aggiorna(_testo(valida.id), data_emissione=creata, dati_personalizzati=dati_valida)
        esito["data_corretta"] = creata
    pagamenti = dict(getattr(fascicolo, "pagamenti", {}) or {})
    voce = dict(pagamenti.get("parcella") or {})
    totale = round(float(getattr(valida, "totale", 0) or 0), 2)
    if (voce and autore_automatico(voce.get("updated_by")) and totale > 0
            and (abs(float(voce.get("importo") or 0) - totale) > 0.009 or _testo(voce.get("proforma_id")) != _testo(valida.id))):
        storico = list(voce.get("history") or [])
        storico.append({"at": _adesso(), "by": "IUSENTRA riconvalida proforma", "fromStatus": voce.get("status"),
                        "toStatus": voce.get("status"), "fromImporto": voce.get("importo"), "toImporto": totale,
                        "note": f"Importo della proforma valida {_testo(valida.numero)} (stesso calcolo del documento).",
                        "origine": "riconvalida_proforma"})
        voce.update(importo=totale, proforma_id=_testo(valida.id), proforma_number=_testo(valida.numero),
                    data_pagamento="" if _testo(voce.get("status")) != "pagato" else voce.get("data_pagamento"),
                    history=storico[-25:], updated_by="IUSENTRA riconvalida proforma", updated_at=_adesso())
        pagamenti["parcella"] = voce
        repository.aggiorna_pagamenti(fid, pagamenti)
        esito["voce_parcella"] = True
    return esito


def riconvalida_fascicolo(fascicolo: Any, *, con_notifiche: bool = True) -> dict[str, Any]:
    """Riconvalida l’economia e, se richiesto, le scadenze di notifica."""
    from web.helpers import get_fascicoli, get_fatturazione

    esito: dict[str, Any] = {}
    repository = get_fascicoli()
    passi = [
        ("incassi", lambda: riconvalida_incassi(fascicolo, repository=repository)),
        ("proforme", lambda: riconvalida_proforme(repository.get(_testo(fascicolo.id)) or fascicolo,
                                                  repository=repository, fatturazione=get_fatturazione())),
    ]
    if con_notifiche:
        passi.append(("scadenze_notifica", lambda: _allinea_scadenze(fascicolo)))
    for nome, passo in passi:
        try:
            esito[nome] = passo()
        except Exception as exc:
            logger.warning("Riconvalida %s non riuscita per %s: %s", nome, getattr(fascicolo, "id", ""), exc)
            esito[nome] = {"errore": type(exc).__name__}
    return esito


def _allinea_scadenze(fascicolo: Any) -> dict[str, int]:
    from web.services.obblighi_notifica_runtime import allinea_scadenze
    from web.services.obblighi_notifica_sintesi import salva, valuta

    obblighi = valuta(fascicolo)
    salva(_testo(fascicolo.id), obblighi)
    return allinea_scadenze(fascicolo, obblighi)


__all__ = ["incasso_registrato", "riconvalida_fascicolo", "riconvalida_incassi", "riconvalida_proforme"]
