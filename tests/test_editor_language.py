"""Le proposte linguistiche non possono cambiare tempi, negazioni o dati."""

import pytest

from pct.editor_language import verifica_proposta


def test_rifiuta_cambio_tempo_osservato_nella_prova_reale():
    with pytest.raises(ValueError, match="Proposta scartata"):
        verifica_proposta("L’avvocato esammina il documento.", "L'avvocato ha esaminato il documento.",
                         [{"parola": "esammina", "suggerimenti": ["esamina", "es ammina"]}])


def test_accetta_solo_refuso_univoco_del_vocabolario():
    verifica_proposta("L’avvocato esammina il documento.", "L'avvocato esamina il documento.",
                     [{"parola": "esammina", "suggerimenti": ["esamina", "es ammina"]}])


@pytest.mark.parametrize("proposta", ["Il cliente paga 500 euro.", "Il cliente paga 260 euro.",
                                     "Il cliente non ha pagato 260 euro."])
def test_conserva_negazione_importo_e_tempo(proposta):
    with pytest.raises(ValueError, match="Proposta scartata"):
        verifica_proposta("Il cliente non paga 260 euro.", proposta, [])


def test_refuso_ambiguo_non_diventa_correzione_certa():
    with pytest.raises(ValueError, match="Proposta scartata"):
        verifica_proposta("La csa.", "La casa.", [{"parola": "csa", "suggerimenti": ["casa", "cosa"]}])
