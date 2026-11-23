"""Catalogo delle regole giuridiche dell'harness: ogni voce riconosce la fattispecie e produce l'analisi con le norme.

L'ordine conta a parità di punteggio: le fattispecie specifiche vengono prima delle domande puntuali generiche.
"""
from __future__ import annotations

from collections.abc import Callable

from ..comprensione import Comprensione
from ..fatti import Fatti
from ..modello import Analisi
from . import amministrativo, appalto, civile, consumo, domande, pubblico, esecuzione, famiglia, lavoro, locazione, monitorio, stragiudiziale, varie

Regola = tuple[str, Callable[[Comprensione, Fatti], int], Callable[[Comprensione, Fatti], Analisi]]

REGOLE: tuple[Regola, ...] = (
    ("opposizione_precetto", esecuzione.riconosci_opposizione_precetto, esecuzione.analizza_opposizione_precetto),
    ("opposizione_decreto_ingiuntivo", monitorio.riconosci_opposizione_di, monitorio.analizza_opposizione_di),
    ("opposizione_sfratto_commerciale", locazione.riconosci_sfratto_commerciale, locazione.analizza_sfratto_commerciale),
    ("negoziazione_locazione_inadatta", locazione.riconosci_negoziazione_locazione, locazione.analizza_negoziazione_locazione),
    ("procedibilita_locazione", locazione.riconosci_procedibilita_locazione, locazione.analizza_procedibilita_locazione),
    ("restituzione_canone_non_registrato", locazione.riconosci_indebito_locazione, locazione.analizza_indebito_locazione),
    ("sequestro_conservativo", varie.riconosci_sequestro, varie.analizza_sequestro),
    ("sequestro_ante_causam", varie.riconosci_sequestro_ante_causam, varie.analizza_sequestro_ante_causam),
    ("garanzia_conformita", consumo.riconosci_garanzia_consumo, consumo.analizza_garanzia_consumo),
    ("opposizione_verbale_cds", varie.riconosci_verbale_cds, varie.analizza_verbale_cds),
    ("disconoscimento_paternita", varie.riconosci_disconoscimento, varie.analizza_disconoscimento),
    ("chiamato_nel_possesso", varie.riconosci_eredita_possesso, varie.analizza_eredita_possesso),
    ("diffida_commerciale", stragiudiziale.riconosci_diffida_commerciale, stragiudiziale.analizza_diffida_commerciale),
    ("diffida_messa_mora", stragiudiziale.riconosci_diffida_messa_mora, stragiudiziale.analizza_diffida_messa_mora),
    ("diffida_1454", stragiudiziale.riconosci_diffida_1454, stragiudiziale.analizza_diffida_1454),
    ("sinistro_stradale", stragiudiziale.riconosci_sinistro, stragiudiziale.analizza_sinistro),
    ("vizi_appalto", appalto.riconosci_vizi_appalto, appalto.analizza_vizi_appalto),
    ("termini_precetto", esecuzione.riconosci_termini_precetto, esecuzione.analizza_termini_precetto),
    ("pignoramento_terzi", esecuzione.riconosci_pignoramento_terzi, esecuzione.analizza_pignoramento_terzi),
    ("ricerca_beni", esecuzione.riconosci_ricerca_beni, esecuzione.analizza_ricerca_beni),
    ("caparra_confirmatoria", civile.riconosci_caparra, civile.analizza_caparra),
    ("recesso_contratto", civile.riconosci_recesso_contratto, civile.analizza_recesso_contratto),
    ("impugnazione_licenziamento", lavoro.riconosci_licenziamento, lavoro.analizza_licenziamento),
    ("appello_lavoro", domande.riconosci_appello_lavoro, domande.analizza_appello_lavoro),
    ("ricorso_dipendente_pubblico", pubblico.riconosci_dipendente_pubblico, pubblico.analizza_dipendente_pubblico),
    ("esecuzione_contro_pa", pubblico.riconosci_esecuzione_pa, pubblico.analizza_esecuzione_pa),
    ("ordinanza_ingiunzione", pubblico.riconosci_ordinanza_ingiunzione, pubblico.analizza_ordinanza_ingiunzione),
    ("crediti_lavoro", lavoro.riconosci_crediti, lavoro.analizza_crediti),
    ("competenza_lavoro", lavoro.riconosci_competenza_lavoro, lavoro.analizza_competenza_lavoro),
    ("divorzio_tempi", famiglia.riconosci_divorzio_tempi, famiglia.analizza_divorzio_tempi),
    ("figlio_maggiorenne", famiglia.riconosci_maggiorenne, famiglia.analizza_maggiorenne),
    ("separazione_giudiziale", famiglia.riconosci_separazione, famiglia.analizza_separazione),
    ("modifica_condizioni", famiglia.riconosci_modifica_condizioni, famiglia.analizza_modifica_condizioni),
    ("negoziazione_familiare", famiglia.riconosci_negoziazione_familiare, famiglia.analizza_negoziazione_familiare),
    ("ordini_protezione", famiglia.riconosci_ordini_protezione, famiglia.analizza_ordini_protezione),
    ("sanatoria_morosita", locazione.riconosci_sanatoria, locazione.analizza_sanatoria),
    ("sfratto_morosita", locazione.riconosci_sfratto, locazione.analizza_sfratto),
    ("sfratto_finita_locazione", locazione.riconosci_finita, locazione.analizza_finita_locazione),
    ("rilascio", locazione.riconosci_rilascio, locazione.analizza_rilascio),
    ("opposizione_convalida", locazione.riconosci_opposizione_convalida, locazione.analizza_opposizione_convalida),
    ("causa_locazione", locazione.riconosci_cause_locazione, locazione.analizza_cause_locazione),
    ("notifica_decreto_ingiuntivo", monitorio.riconosci_notifica_di, monitorio.analizza_notifica_di),
    ("decreto_ingiuntivo", monitorio.riconosci_ricorso_di, monitorio.analizza_ricorso_di),
    ("opposizione_atti_esecutivi", domande.riconosci_opposizione_atti, domande.analizza_opposizione_atti),
    ("impugnazione_delibera", domande.riconosci_delibera, domande.analizza_delibera),
    ("lite_condominio", domande.riconosci_lite_condominio, domande.analizza_lite_condominio),
    ("consumatore", domande.riconosci_consumatore, domande.analizza_consumatore),
    ("ricorso_tar", domande.riconosci_tar, domande.analizza_tar),
    ("appalti_120", amministrativo.riconosci_appalti, amministrativo.analizza_appalti),
    ("accesso_atti", amministrativo.riconosci_accesso, amministrativo.analizza_accesso),
    ("silenzio", amministrativo.riconosci_silenzio, amministrativo.analizza_silenzio),
    ("motivi_aggiunti", amministrativo.riconosci_motivi_aggiunti, amministrativo.analizza_motivi_aggiunti),
    ("ottemperanza", amministrativo.riconosci_ottemperanza, amministrativo.analizza_ottemperanza),
    ("permesso_soggiorno", amministrativo.riconosci_unita_familiare, amministrativo.analizza_unita_familiare),
    ("appello_tributario", amministrativo.riconosci_appello_tributario, amministrativo.analizza_appello_tributario),
    ("sospensione_tributaria", amministrativo.riconosci_sospensione_tributaria, amministrativo.analizza_sospensione_tributaria),
    ("reclamo_mediazione_tributaria", amministrativo.riconosci_reclamo_tributario, amministrativo.analizza_reclamo_tributario),
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

# Regole per materia (schede in materia_*.py): in coda, vincono solo con un punteggio più alto.
from .materie import REGOLE_MATERIE  # noqa: E402

REGOLE = REGOLE + REGOLE_MATERIE


def scegli(c: Comprensione, f: Fatti) -> Regola | None:
    migliore, punteggio = None, 0
    for regola in REGOLE:
        p = regola[1](c, f)
        if p > punteggio:
            migliore, punteggio = regola, p
    return migliore
