"""Registro del contributo unificato del fascicolo: dovuto, pagato, art. 30, esenzione, differenza.

Una sola lettura dello stato del contributo, da cui le viste del fascicolo, del presidio e
dell'economia proiettano lo stesso esito:

- dovuto: art. 13 D.P.R. 115/2002, calcolato per la tipologia del fascicolo e il valore dichiarato
  (art. 14) con `pct.contributo_preventivo`; senza valore, dove il contributo ne dipende, resta da
  verificare invece di presumere lo scaglione dell'indeterminabile;
- pagato: le sole quote «contributo unificato» delle ricevute (la voce di `fascicolo.pagamenti`
  scritta da `web.services.ricevuta_pagopa_runtime`), mai il totale con l'anticipazione forfettaria;
- anticipazione forfettaria dell'art. 30 (27 euro) a parte;
- esenzione (artt. 9 e 10) e prenotazione a debito (art. 131) senza importo dovuto ora;
- differenza: contributo insufficiente da integrare (art. 16, comma 1, recupero con invito al pagamento).

Il registro informa il presidio: non cambia i controlli della busta di deposito.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pct.contributo_preventivo import contributo_per_preventivo, dipende_dal_valore

_TOLLERANZA = 0.01


@dataclass(frozen=True)
class RegistroContributo:
    stato: str
    etichetta: str
    dovuto: float | None = None
    base_dovuto: str = ""
    pagato: float = 0.0
    art_30: float = 0.0
    differenza: float | None = None
    avvisi: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _euro(importo: float) -> str:
    from pct.pagamenti_giustizia import format_importo_euro_it

    return format_importo_euro_it(importo)


def _numero(valore: Any) -> float:
    try:
        return round(float(valore or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def dovuto_del_fascicolo(fascicolo: Any, calcolatore: Any) -> tuple[float | None, str]:
    """Contributo dovuto per tipologia, valore e grado del fascicolo; None con il motivo se non determinabile."""
    tipologia = str(getattr(fascicolo, "id_pratica", "") or "")
    valore = _numero(getattr(fascicolo, "valore_causa", 0))
    if dipende_dal_valore(tipologia) and valore <= 0:
        return None, "Valore della causa non indicato: il contributo dovuto dipende dal valore dichiarato (art. 14)."
    try:
        dovuto = contributo_per_preventivo(calcolatore, tipologia, valore=valore,
                                           grado_scelto=str(getattr(fascicolo, "tribunale", "") or ""))
    except (ValueError, KeyError):
        dovuto = None
    if dovuto is None:
        return None, "Tipologia senza calcolo automatico del contributo: verificare il dovuto."
    base = (f"art. 13 D.P.R. 115/2002, valore {_euro(valore)}" if dipende_dal_valore(tipologia)
            else "art. 13 D.P.R. 115/2002, importo fisso della tipologia")
    return dovuto, base


def registro_contributo(voce: Any, *, dovuto: float | None, base_dovuto: str = "") -> RegistroContributo:
    """Stato del contributo dalla voce del fascicolo e dal dovuto."""
    voce = voce if isinstance(voce, dict) else {}
    stato_voce = str(voce.get("status") or voce.get("stato") or "")
    art_30 = _numero(voce.get("art_30"))
    if stato_voce == "esente" or voce.get("esente") is True:
        return RegistroContributo("esente", "Contributo unificato esente", None, base_dovuto, 0.0, art_30)
    if stato_voce == "prenotato_a_debito" or voce.get("prenotato_a_debito") is True:
        return RegistroContributo("prenotato_a_debito", "Contributo unificato prenotato a debito (art. 131)",
                                  None, base_dovuto, 0.0, art_30)
    pagato = _numero(voce.get("importo")) if stato_voce == "pagato" or voce.get("pagato") is True else 0.0
    avvisi = [] if dovuto is not None else ([base_dovuto] if base_dovuto else [])
    if pagato <= 0:
        return RegistroContributo("da_pagare", "Contributo unificato da versare", dovuto, base_dovuto if dovuto is not None else "",
                                  0.0, art_30, dovuto, avvisi)
    if dovuto is None:
        return RegistroContributo("pagato_da_verificare", "Contributo versato: dovuto da verificare", None, "", pagato,
                                  art_30, None, avvisi)
    differenza = round(dovuto - pagato, 2)
    if differenza > _TOLLERANZA:
        avvisi.append(f"Contributo insufficiente: mancano {_euro(differenza)} rispetto al dovuto (art. 16 D.P.R. 115/2002).")
        return RegistroContributo("insufficiente", "Contributo unificato insufficiente", dovuto, base_dovuto, pagato, art_30,
                                  differenza, avvisi)
    if differenza < -_TOLLERANZA:
        avvisi.append(f"Versati {_euro(-differenza)} oltre il dovuto: verificare valore dichiarato e ricevute.")
    return RegistroContributo("pagato", "Contributo unificato versato", dovuto, base_dovuto, pagato, art_30, 0.0, avvisi)


__all__ = ["RegistroContributo", "dovuto_del_fascicolo", "registro_contributo"]
