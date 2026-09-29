"""Percorso della posizione: passaggi ammessi e termini che ogni evento fa nascere.

- Art. 1219 c.c. (costituzione in mora con la diffida); art. 2943 c.c. (interruzione della prescrizione).
- Artt. 633-644 c.p.c.: ricorso, decreto, notifica entro 60 giorni dalla pronuncia a pena di inefficacia.
- Art. 641 c.p.c.: 40 giorni dalla notifica per l'opposizione; art. 647: esecutorietà in mancanza;
  art. 642: provvisoria esecuzione già nel decreto; art. 645: opposizione, si passa al giudizio ordinario.
- Artt. 479-481 c.p.c.: precetto, termine di almeno 10 giorni per adempiere, perdita di efficacia se
  l'esecuzione non inizia entro 90 giorni. Art. 543 c. 4: iscrizione a ruolo del pignoramento presso
  terzi entro 30 giorni dalla consegna dell'atto notificato.
I termini si calcolano con il motore ``pct.termini_processuali`` (modelli versionati).
"""

from __future__ import annotations

from datetime import date
from typing import Any

PASSAGGI: dict[str, tuple[str, ...]] = {
    "da_diffidare": ("diffidato", "ricorso_da_depositare", "chiusa_pagata", "chiusa_transatta", "chiusa_irrecuperabile"),
    "diffidato": ("ricorso_da_depositare", "chiusa_pagata", "chiusa_transatta", "chiusa_irrecuperabile"),
    "ricorso_da_depositare": ("ricorso_depositato", "chiusa_pagata", "chiusa_transatta", "chiusa_irrecuperabile"),
    "ricorso_depositato": ("decreto_emesso", "chiusa_pagata", "chiusa_transatta", "chiusa_irrecuperabile"),
    "decreto_emesso": ("decreto_notificato", "esecutivo", "chiusa_pagata", "chiusa_transatta"),
    "decreto_notificato": ("opposto", "esecutivo", "chiusa_pagata", "chiusa_transatta"),
    "opposto": ("esecutivo", "chiusa_pagata", "chiusa_transatta", "chiusa_irrecuperabile"),
    "esecutivo": ("precetto_notificato", "chiusa_pagata", "chiusa_transatta", "chiusa_irrecuperabile"),
    "precetto_notificato": ("pignoramento", "precetto_notificato", "chiusa_pagata", "chiusa_transatta", "chiusa_irrecuperabile"),
    "pignoramento": ("chiusa_pagata", "chiusa_transatta", "chiusa_irrecuperabile", "precetto_notificato"),
}

#: Termini che nascono dall'evento: modello del motore dei termini e titolo della scadenza.
TERMINI_EVENTO: dict[str, tuple[tuple[str, str], ...]] = {
    "decreto_emesso": (("CIV_DI_NOTIFICA_644", "Notifica del decreto ingiuntivo entro 60 giorni (art. 644 c.p.c.)"),),
    "decreto_notificato": (("CIV_OPPOSIZIONE_DI", "Termine per l'opposizione al decreto ingiuntivo (art. 641 c.p.c.)"),),
    "precetto_notificato": (("ESE_PRECETTO_ADEMPIMENTO_10GG", "Precetto: termine per adempiere (art. 480 c.p.c.)"),
                            ("ESE_PRECETTO_EFFICACIA_90GG", "Precetto: inizio dell'esecuzione entro 90 giorni (art. 481 c.p.c.)")),
    "pignoramento": (("ESE_ISCRIZIONE_RUOLO_PRESSO_TERZI", "Iscrizione a ruolo del pignoramento presso terzi (art. 543 c. 4 c.p.c.)"),),
}


def ammesso(da: str, a: str) -> bool:
    return a in PASSAGGI.get(da, ())


def termini_da_evento(stato: str, data_evento: date) -> list[dict[str, Any]]:
    """Scadenze calcolate dal motore dei termini per l'evento registrato."""
    from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

    modelli = {t.code: t for t in DEFAULT_TEMPLATES}
    calcolo = ItalianDeadlineCalculator()
    risultati = []
    for codice, titolo in TERMINI_EVENTO.get(stato, ()):
        modello = modelli.get(codice)
        if modello is None:
            continue
        esito = calcolo.calculate_template(data_evento, modello)
        risultati.append({"codice": codice, "titolo": titolo, "data": esito["deadline"], "norma": modello.reference_law})
    return risultati


__all__ = ["PASSAGGI", "TERMINI_EVENTO", "ammesso", "termini_da_evento"]
