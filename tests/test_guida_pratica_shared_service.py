"""Il servizio Guida Pratica deve essere un singleton di processo.

Il KB completo (full JSON + 100+ moduli) supera i 100 MB una volta caricato:
i percorsi runtime (bridge React, blueprint API, creazione fascicoli, sorgente
Lex, validazione) devono condividere l'istanza invece di ricostruirla per
richiesta, altrimenti ogni vista costa ~100 MB di picco e oltre un secondo di CPU.
"""

from pct.guida_pratica import GuidaPraticaService, get_guida_pratica_service


def test_factory_restituisce_sempre_la_stessa_istanza():
    first = get_guida_pratica_service()
    second = get_guida_pratica_service()
    assert first is second
    assert isinstance(first, GuidaPraticaService)


def test_sorgente_lex_riusa_il_singleton_di_processo():
    from lex.retrieval.sources.guida_pratica import _default_service

    assert _default_service() is get_guida_pratica_service()


def test_validation_engine_riusa_il_singleton_di_processo():
    from pct.guida_pratica.validation import GuidaPraticaValidationEngine

    assert GuidaPraticaValidationEngine().service is get_guida_pratica_service()


def test_istanza_esplicita_resta_prioritaria():
    from pct.guida_pratica.validation import GuidaPraticaValidationEngine

    dedicato = GuidaPraticaService(catalog_records=[])
    assert GuidaPraticaValidationEngine(service=dedicato).service is dedicato
