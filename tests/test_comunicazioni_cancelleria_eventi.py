"""Eventi specifici dall'oggetto di Comunicazione.xml e termini di riassunzione (31/10/2026)."""

from __future__ import annotations

import pytest

from pct.pec_legal_deadline_proposer import propose_legal_deadline
from pct.pec_legal_workflow import _evento_da_comunicazione


@pytest.mark.parametrize(
    ("oggetto", "evento", "con_termine"),
    [
        ("DEPOSITO DECRETO INGIUNTIVO", "decreto_ingiuntivo_emesso", True),
        ("RIGETTO RICORSO PER DECRETO INGIUNTIVO", "decreto_ingiuntivo_rigettato", False),
        ("DICHIARAZIONE ESECUTORIETA' DECRETO INGIUNTIVO", "decreto_ingiuntivo_esecutivo", False),
        ("CANCELLAZIONE DELLA CAUSA DAL RUOLO", "cancellazione_dal_ruolo", True),
        ("INTERRUZIONE DEL PROCESSO", "interruzione_processo", True),
        ("SCIOGLIMENTO RISERVA", "scioglimento_riserva", True),
        ("DEPOSITO ATTO DI PARTE", "comunicazione_cancelleria", False),
    ],
)
def test_ogni_oggetto_della_cancelleria_ha_il_suo_evento(oggetto, evento, con_termine):
    esito = _evento_da_comunicazione(oggetto, "")
    assert esito["event_type"] == evento
    assert esito["creates_deadline"] is con_termine


@pytest.mark.parametrize(
    ("testo", "norma"),
    [
        ("Il giudice dispone la cancellazione della causa dal ruolo ai sensi dell'art. 309 c.p.c.", "Art. 307 c.p.c."),
        ("Il giudice dichiara interrotto il processo per il decesso della parte.", "Art. 305 c.p.c."),
    ],
)
def test_riassunzione_entro_tre_mesi_con_agosto_sospeso(testo, norma):
    proposta = propose_legal_deadline(testo, dies_a_quo_date="2026-06-15")
    # 15/06 + 3 mesi = 15/09, + 31 giorni di agosto = venerdì 16/10.
    assert proposta["ok"] is True and proposta["norma"] == norma and proposta["deadline"] == "2026-10-16"
