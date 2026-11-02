"""Riconvalida dei profili procedurali: i fascicoli rimasti «da confermare» con le regole di oggi.

Prima di questa revisione il resolver lasciava senza profilo i fascicoli che
non avevano un codice procedura o un codice oggetto lavoro, e proponeva sempre
le stesse cinque pratiche del catalogo (ambientale, accesso agli atti, gara
d'appalto, sinistro, bancario) anche per un ricorso di lavoro. Qui ogni
fascicolo senza profilo salvato si ripassa con il resolver corrente: quando i
dati certi bastano il profilo si imposta da solo, con la fonte nell'audit; gli
altri restano proposte da confermare, con le sole alternative pertinenti.

Non si tocca mai un profilo già salvato (confermato dall'avvocato o impostato
in precedenza): la riconvalida è idempotente.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from .evaluator import ensure_profile_for_fascicolo


def riconvalida_profili(
    repository: Any,
    fascicoli: Iterable[Any],
    *,
    etichette_di: Callable[[str], list[str]] | None = None,
    limite: int = 0,
) -> dict[str, Any]:
    """Imposta il profilo dei fascicoli senza profilo quando i dati certi bastano; conta gli esiti.

    ``limite`` (0 = nessuno) è il lotto: quanti fascicoli senza profilo si ripassano in un giro;
    quelli oltre il lotto restano per il giro successivo (``restano``).
    """
    esito: dict[str, Any] = {
        "esaminati": 0, "gia_salvati": 0, "impostati": 0, "da_confermare": 0, "errori": 0, "restano": 0,
        "fascicoli_impostati": [],
    }
    ripassati = 0
    for fascicolo in fascicoli:
        fascicolo_id = str(getattr(fascicolo, "id", "") or "").strip()
        if not fascicolo_id:
            continue
        if repository.get_profile_snapshot(fascicolo_id):
            esito["esaminati"] += 1
            esito["gia_salvati"] += 1
            continue
        if limite and ripassati >= limite:
            esito["restano"] += 1
            continue
        ripassati += 1
        esito["esaminati"] += 1
        try:
            etichette = etichette_di(fascicolo_id) if etichette_di else []
            ensure_profile_for_fascicolo(repository, fascicolo=fascicolo, etichette_documenti=etichette)
        except Exception:
            esito["errori"] += 1
            continue
        if repository.get_profile_snapshot(fascicolo_id):
            esito["impostati"] += 1
            esito["fascicoli_impostati"].append(fascicolo_id)
        else:
            esito["da_confermare"] += 1
    return esito


__all__ = ["riconvalida_profili"]
