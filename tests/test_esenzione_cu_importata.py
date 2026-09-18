"""L'autocertificazione di esenzione archiviata sotto la voce sbagliata.

Le pratiche importate da un gestionale precedente portano spesso
l'autocertificazione sotto «spese ed esborsi»: l'import ha conservato il file,
non il suo significato. Per l'avvocato è doppio danno — il contributo
unificato resta «da registrare» per una somma che non è dovuta, e fra le spese
compare una voce che spesa non è.
"""

from __future__ import annotations

import pytest

from pct.fascicolo_esenzione_cu import (
    NOTA_VOCE_SPURIA,
    VOCI_SPURIE,
    e_autocertificazione_di_esenzione,
    sposta_esenzione_sul_contributo,
    voce_spuria_con_esenzione,
)


@pytest.mark.parametrize("nome", [
    "Autocertificazione esenzione cu diritto lavoro.PDF",
    "Dichiarazione sostitutiva esenzione contributo unificato.pdf",
    "AUTOCERTIFICAZIONE ESENZIONE CONTRIBUTO UNIFICATO.pdf",
    "autocertificazione - esenzione c.u..pdf",
])
def test_riconosce_l_autocertificazione_dal_nome(nome):
    """Si riconosce dal nome: non serve aprirla per sapere a che cosa si riferisce."""
    assert e_autocertificazione_di_esenzione(nome)


@pytest.mark.parametrize("nome", [
    "Ricevuta pagamento cu.pdf",
    "Autocertificazione redditi.pdf",
    "Dichiarazione sostitutiva di residenza.pdf",
    "Esenzione bollo.pdf",
    "",
])
def test_non_scambia_altri_documenti_per_autocertificazioni(nome):
    """Un falso positivo azzererebbe un contributo unificato realmente dovuto."""
    assert not e_autocertificazione_di_esenzione(nome)


@pytest.mark.parametrize("voce", VOCI_SPURIE)
def test_la_trova_sotto_qualunque_voce_l_import_l_abbia_messa(voce):
    pagamenti = {voce: {"status": "da_registrare", "documento_fonte": "Autocertificazione esenzione cu.pdf"}}
    assert voce_spuria_con_esenzione(pagamenti) == (voce, "Autocertificazione esenzione cu.pdf")


def test_sposta_l_esenzione_sul_contributo_e_svuota_la_voce_sbagliata():
    corrette = sposta_esenzione_sul_contributo({
        "spese_esborsi": {"status": "da_registrare", "importo": 0,
                          "documento_fonte": "Autocertificazione esenzione cu diritto lavoro.PDF"},
    })
    contributo = corrette["contributo_unificato"]
    assert contributo["status"] == "non_previsto"
    assert contributo["previsto"] is False
    assert contributo["natura"] == "esenzione_contributo_unificato"
    assert contributo["documento_fonte"] == "Autocertificazione esenzione cu diritto lavoro.PDF"
    assert "115/2002" in contributo["note"]

    spese = corrette["spese_esborsi"]
    assert spese["status"] == "non_previsto"
    assert spese["documento_fonte"] == NOTA_VOCE_SPURIA


def test_senza_autocertificazione_non_tocca_niente():
    assert sposta_esenzione_sul_contributo({}) == {}
    assert sposta_esenzione_sul_contributo({"spese_esborsi": {"documento_fonte": "Fattura CTU.pdf"}}) == {}
    assert sposta_esenzione_sul_contributo(None) == {}
