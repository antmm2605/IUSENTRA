"""La sintesi degli obblighi di notifica già calcolati, conservata per il quadro del fascicolo.

Calcolare gli obblighi di notifica costa secondi (fatti dell'archivio, catalogo, verifiche per atto): il quadro
del fascicolo deve rispondere in meno di un secondo e non può ricalcolarli nella richiesta. La sintesi si salva
quando il calcolo avviene comunque (giro in sfondo della lettura del fascicolo, apertura degli obblighi di notifica)
nella cache dei payload del registro delle letture, la stessa della Lettura: ``invalida_lettura`` la cancella
quando cambiano documenti o PEC, e il giro successivo la ricrea. Senza sintesi il quadro lo dice, senza inventare.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

logger = logging.getLogger(__name__)

CHIAVE = "obblighi-notifica-sintesi:v1"
DURATA = timedelta(days=30)


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def compatta(obblighi: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per ogni atto: etichetta, stato dell'obbligo e scadenza (ISO); nient'altro esce dal calcolo."""
    return [{"atto": _testo(o.get("etichetta") or o.get("atti") or o.get("documento")), "stato": _testo(o.get("stato")),
             "scadenza": _testo(o.get("scadenza"))[:10],
             **({"regola": "sentenza_notifica_breve",
                 "documenti": sorted({oid for f in [o, *(o.get("fonti_documentali") or [])]
                                      if (oid := _testo(f.get("documentoId")))})}
                if o.get("regola") == "sentenza_notifica_breve" else {}),
             # I termini che nascono dalla sentenza notificata (pct.sentenza_notificata): breve, giudicato, art. 14 D.L. 669/1996.
             **({"termini": termini} if (termini := [{"codice": _testo(c.get("codice")), "deadline": _testo(c.get("deadline"))[:10],
                                                     "precetto_dal": _testo(c.get("precetto_dal"))[:10], "norma": _testo(c.get("norma"))}
                                                    for c in o.get("calcoli") or [] if c.get("codice")]) else {})}
            for o in obblighi if _testo(o.get("etichetta") or o.get("atti"))]


def salva(fascicolo_id: str, obblighi: Iterable[Mapping[str, Any]]) -> None:
    try:
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        scade = (datetime.now(timezone.utc) + DURATA).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        payload = json.dumps({"obblighi": compatta(obblighi),
                              "calcolata_il": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}, ensure_ascii=False)
        registro_corrente().payload_cache_set(tenant_corrente(), _testo(fascicolo_id), CHIAVE, payload, expires_at=scade)
    except Exception as exc:  # la sintesi è un'accelerazione: il calcolo resta valido anche senza
        logger.debug("Sintesi degli obblighi di notifica non salvata per %s: %s", fascicolo_id, exc)


def _integra_identita(sintesi: dict[str, Any], fascicolo_id: str) -> dict[str, Any]:
    obblighi = sintesi.get("obblighi") or []
    if not any(voce.get("atto") == "Sentenza" and not voce.get("regola") for voce in obblighi):
        return sintesi

    from web.services.pannelli_pronti_runtime import voce_del_profilo

    voce = voce_del_profilo(fascicolo_id, "obblighi-notifica", precedente=True)
    if voce is None or not sintesi.get("calcolata_il"):
        return sintesi
    # La sintesi è scritta prima del payload integrale dalla stessa vista.
    # Lo scarto ammette l'arrotondamento ai secondi del registro.
    sintetizzata = datetime.fromisoformat(sintesi["calcolata_il"])
    archiviata = datetime.fromisoformat(voce.calcolato_il)
    if not timedelta(0) <= archiviata - sintetizzata <= timedelta(seconds=2):
        return sintesi
    completo = json.loads(voce.corpo) if voce.corpo else {}
    if not completo.get("ok") or not isinstance(completo.get("obblighi"), list):
        return sintesi
    proposta = compatta(completo["obblighi"])
    # Recupera soltanto l'identità da una proiezione dello stesso profilo che
    # concorda con tutti gli stati, le date e i calcoli già salvati.
    campi_identita = {"regola", "documenti"}
    ridotta = [{k: v for k, v in voce.items() if k not in campi_identita} for voce in proposta]
    if ridotta == obblighi:
        return {**sintesi, "obblighi": proposta}
    return sintesi


def leggi(fascicolo_id: str) -> dict[str, Any] | None:
    try:
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        grezzo = registro_corrente().payload_cache_get(tenant_corrente(), _testo(fascicolo_id), CHIAVE)
        sintesi = json.loads(grezzo) if grezzo else None
        if isinstance(sintesi, dict):
            try:
                return _integra_identita(sintesi, fascicolo_id)
            except (TypeError, ValueError, AttributeError):
                return sintesi
        return None
    except Exception as exc:
        logger.debug("Sintesi degli obblighi di notifica non leggibile per %s: %s", fascicolo_id, exc)
        return None


__all__ = ["CHIAVE", "compatta", "leggi", "salva"]
