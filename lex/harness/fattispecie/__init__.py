"""Catalogo delle regole giuridiche dell'harness: ogni voce riconosce la fattispecie e produce l'analisi con le norme.

L'ordine conta a parità di punteggio: le fattispecie specifiche vengono prima delle domande puntuali generiche.
"""
from __future__ import annotations

from collections.abc import Callable

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..modello import Analisi
from . import civile, domande, famiglia, lavoro, locazione, monitorio

Regola = tuple[str, Callable[[Comprensione, Fatti], int], Callable[[Comprensione, Fatti], Analisi]]

REGOLE: tuple[Regola, ...] = (
    ("caparra_confirmatoria", civile.riconosci_caparra, civile.analizza_caparra),
    ("impugnazione_licenziamento", lavoro.riconosci_licenziamento, lavoro.analizza_licenziamento),
    ("appello_lavoro", domande.riconosci_appello_lavoro, domande.analizza_appello_lavoro),
    ("crediti_lavoro", lavoro.riconosci_crediti, lavoro.analizza_crediti),
    ("competenza_lavoro", lavoro.riconosci_competenza_lavoro, lavoro.analizza_competenza_lavoro),
    ("divorzio_tempi", famiglia.riconosci_divorzio_tempi, famiglia.analizza_divorzio_tempi),
    ("figlio_maggiorenne", famiglia.riconosci_maggiorenne, famiglia.analizza_maggiorenne),
    ("separazione_giudiziale", famiglia.riconosci_separazione, famiglia.analizza_separazione),
    ("sanatoria_morosita", locazione.riconosci_sanatoria, locazione.analizza_sanatoria),
    ("sfratto_morosita", locazione.riconosci_sfratto, locazione.analizza_sfratto),
    ("causa_locazione", locazione.riconosci_cause_locazione, locazione.analizza_cause_locazione),
    ("notifica_decreto_ingiuntivo", monitorio.riconosci_notifica_di, monitorio.analizza_notifica_di),
    ("decreto_ingiuntivo", monitorio.riconosci_ricorso_di, monitorio.analizza_ricorso_di),
    ("opposizione_atti_esecutivi", domande.riconosci_opposizione_atti, domande.analizza_opposizione_atti),
    ("precetto", domande.riconosci_precetto, domande.analizza_precetto),
    ("impugnazione_delibera", domande.riconosci_delibera, domande.analizza_delibera),
    ("lite_condominio", domande.riconosci_lite_condominio, domande.analizza_lite_condominio),
    ("consumatore", domande.riconosci_consumatore, domande.analizza_consumatore),
    ("ricorso_tar", domande.riconosci_tar, domande.analizza_tar),
    ("ricorso_tributario", domande.riconosci_tributario, domande.analizza_tributario),
    ("ricorso_straordinario", domande.riconosci_straordinario, domande.analizza_straordinario),
    ("termine_querela", domande.riconosci_querela, domande.analizza_querela),
    ("impugnazione_penale", domande.riconosci_appello_penale, domande.analizza_appello_penale),
    ("comparsa_risposta", civile.riconosci_comparsa, civile.analizza_comparsa),
    ("negoziazione_obbligatoria", domande.riconosci_negoziazione, domande.analizza_negoziazione),
    ("mediazione_obbligatoria", domande.riconosci_mediazione, domande.analizza_mediazione),
    ("rito_semplificato", domande.riconosci_semplificato, domande.analizza_semplificato),
    ("competenza_pagamento", civile.riconosci_pagamento, civile.analizza_pagamento),
)


def scegli(c: Comprensione, f: Fatti) -> Regola | None:
    migliore, punteggio = None, 0
    for regola in REGOLE:
        p = regola[1](c, f)
        if p > punteggio:
            migliore, punteggio = regola, p
    return migliore
