"""Il controllo del contributo riguarda l'atto scelto e la natura della prova."""

import pytest

from pct.deposito_studio_telematico_validation import validate_studio_telematico_deposit


@pytest.mark.parametrize(
    'key,contribution,blocked',
    [
        ('Parte_SICID::Memoria183', {}, False),
        ('Introduttivi_SICID::Citazione', {}, True),
        ('Introduttivi_SICID::Citazione', {'mode': 'esente', 'resolved': True}, False),
        ('Introduttivi_SICID::Citazione', {'mode': 'prenotato_a_debito', 'resolved': True}, False),
        ('Introduttivi_SICID::Citazione', {'mode': 'pagato', 'importo': 259, 'payment_evidence': False}, True),
        ('Introduttivi_SICID::Citazione', {'mode': 'pagato', 'importo': 259, 'payment_evidence': True}, False),
    ],
)
def test_contributo_solo_quando_previsto_e_ricevuta_solo_per_pagamento(key, contribution, blocked):
    findings = validate_studio_telematico_deposit(
        key=key,
        context={'contributo_unificato': contribution},
        selected_documents=[],
    )
    assert bool([item for item in findings if item['field'] == 'contributo_unificato']) is blocked
