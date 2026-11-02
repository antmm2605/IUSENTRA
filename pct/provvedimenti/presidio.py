"""Le voci del provvedimento nel presidio documentale del fascicolo.

Il presidio (``pct/fascicolo_document_presidio.py``) legge i testi già associati al
fascicolo; qui le voci del provvedimento diventano azioni nello stesso formato, senza
doppioni con ciò che il presidio già legge da sé:

* il decreto ex art. 127-ter c.p.c. resta all'analisi dedicata (voci ``127ter.*``);
* le date scritte in chiaro nel dispositivo le legge già l'analisi generica delle date;
* restano i termini calcolati (di legge o relativi all'udienza), le attese e le domande.

Il documento non ha la data della comunicazione: i termini che ne decorrono diventano
domande, come vuole la regola «nessuna data indovinata».
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .modello import EsitoProvvedimento, Voce

TIPO_TERMINE = "provvedimento_termine"
TIPO_ATTESA = "provvedimento_attesa"
TIPO_DA_VERIFICARE = "provvedimento_da_verificare"
_TONO = {"termine": "danger", "verifica": "warning", "attesa": "neutral", "adempimento": "neutral", "da_verificare": "warning"}


def _da_mostrare(voce: Voce) -> bool:
    if voce.regola_id.startswith("127ter.") or voce.genere == "udienza":
        return False
    if voce.dati and voce.dati[0][0] == "Data scritta nel provvedimento":
        return False
    return voce.genere in {"termine", "verifica", "attesa", "da_verificare"}


def azioni_presidio(esito: EsitoProvvedimento | None, *, source: str, document_id: str,
                    crea_azione: Callable[..., dict[str, Any]]) -> list[dict[str, Any]]:
    if esito is None or "note_127_ter" in esito.tipi:
        # Il decreto di trattazione scritta ha la sua analisi nel presidio (opposizione compresa).
        return []
    azioni = []
    for voce in esito.voci:
        if not _da_mostrare(voce):
            continue
        tipo = TIPO_DA_VERIFICARE if voce.genere == "da_verificare" else TIPO_ATTESA if voce.genere == "attesa" else TIPO_TERMINE
        descrizione = voce.domanda or voce.nota or voce.calcolo or voce.prova
        azione = crea_azione(
            action_type=tipo, title=voce.titolo, due=voce.giorno, source=source, document_id=document_id,
            description=descrizione, tone=_TONO.get(voce.genere, "warning"),
            priority="urgent" if voce.perentorio and voce.genere == "termine" else "important",
            peremptory=bool(voce.perentorio) and voce.genere == "termine", time_value=voce.ora,
        )
        azione["id"] = f"{azione['id']}-{voce.regola_id}"
        azione["ruleId"] = voce.regola_id
        azione["norme"] = list(voce.norme)
        azioni.append(azione)
    return azioni


__all__ = ["TIPO_ATTESA", "TIPO_DA_VERIFICARE", "TIPO_TERMINE", "azioni_presidio"]
