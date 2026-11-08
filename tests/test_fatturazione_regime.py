"""IVA, ritenuta e bollo secondo il regime fiscale dello studio.

Art. 25 D.P.R. 600/1973 (ritenuta 20% del sostituto d'imposta); Ris. AdE 35/E del 15/03/2019
(distrazione: ritenuta del soccombente); art. 1, commi 58 e 67, L. 190/2014 (forfetario senza IVA
né ritenuta); art. 13 Tariffa all. A D.P.R. 642/1972 (bollo € 2 oltre € 77,47 senza IVA).
"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pct.clienti import Cliente, Indirizzo, Recapiti, TipoCliente
from pct.fattura_pa import genera_xml_fattura_pa
from pct.fatturazione import GestioneFatturazione, VoceParcella
from pct.fatturazione_regime import bollo_dovuto, e_sostituto_imposta, parametri_fiscali
from pct.fascicolo_sentenza_economica import apply_sentenza_tribunale_automation
from tests.test_fascicolo_sentenza_economica import SENTENZA_TEXT, FakeFascicoliRepository


def test_parametri_per_regime():
    assert parametri_fiscali("RF01", pagatore_sostituto=True) == {
        "regime_fiscale": "RF01", "applica_iva": True, "applica_ritenuta": True}
    assert parametri_fiscali("RF01", pagatore_sostituto=False)["applica_ritenuta"] is False
    for regime in ("RF19", "RF02"):
        assert parametri_fiscali(regime, pagatore_sostituto=True) == {
            "regime_fiscale": regime, "applica_iva": False, "applica_ritenuta": False}
    assert parametri_fiscali("", pagatore_sostituto=False)["regime_fiscale"] == "RF01"


def test_sostituto_imposta_e_bollo():
    assert e_sostituto_imposta("Ministero dell'Istruzione e del Merito")
    assert e_sostituto_imposta("Alfa S.r.l.", "01234567890")
    assert not e_sostituto_imposta("Rossi Mario", "RSSMRA80A01H501U")
    assert bollo_dovuto(iva_applicabile=False, importo_non_soggetto=77.48)
    assert not bollo_dovuto(iva_applicabile=False, importo_non_soggetto=77.47)
    assert not bollo_dovuto(iva_applicabile=True, importo_non_soggetto=500)


def genera_xml_fattura(parcella):
    cliente = Cliente(
        id="CLI-1", tipo=TipoCliente.PERSONA_GIURIDICA, ragione_sociale="Beta Srl",
        indirizzo_sede_legale=Indirizzo(via="Via Roma", civico="5", cap="20100", comune="Milano", provincia="MI", nazione="Italia"),
        recapiti=Recapiti(email="amministrazione@beta.example"),
    )
    return genera_xml_fattura_pa(parcella=parcella, cliente=cliente, studio_nome="Studio Legale Rossi",
                                 studio_piva="09876543210", studio_cf="RSSMRA80A01H501U",
                                 regime_fiscale=parcella.regime_fiscale or "RF01")


def _proforma_da_sentenza(tmp_path: Path, regime: str):
    fascicoli = FakeFascicoliRepository()
    fascicoli.fascicolo.controparte = "Ministero dell'Istruzione e del Merito"
    fatturazione = GestioneFatturazione(str(tmp_path / f"parcelle_{regime}.json"))
    outcome = apply_sentenza_tribunale_automation(
        proforma_requested=True, fascicoli_repository=fascicoli, fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1", text=SENTENZA_TEXT, actor="Lex AI", regime_fiscale=regime,
        document_metadata={"document_id": "DOC-1", "filename": "sentenza.pdf", "tipo_documento": "Sentenza Tribunale"},
    )
    return fatturazione.get(outcome.proforma_id)


def test_proforma_da_sentenza_pa_regime_ordinario_con_iva_e_ritenuta(tmp_path: Path):
    proforma = _proforma_da_sentenza(tmp_path, "RF01")
    assert proforma.regime_fiscale == "RF01"
    assert proforma.iva_applicabile and proforma.applica_ritenuta
    base_ritenuta = proforma.totale_competenze + proforma.spese_generali
    assert proforma.ritenuta == pytest.approx(round(base_ritenuta * 0.20, 2))
    assert proforma.netto_a_pagare == pytest.approx(round(proforma.totale_documento - proforma.ritenuta, 2))
    assert not proforma.applica_bollo
    oggi = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    assert proforma.data_emissione == oggi
    assert proforma.dati_personalizzati["document"]["data_sentenza"] == "2024-05-07"
    xml = genera_xml_fattura(proforma)
    assert b"<CausalePagamento>A</CausalePagamento>" in xml


def test_proforma_da_sentenza_regime_forfetario_senza_iva_ritenuta_con_bollo(tmp_path: Path):
    proforma = _proforma_da_sentenza(tmp_path, "RF19")
    assert proforma.regime_fiscale == "RF19"
    assert not proforma.iva_applicabile and not proforma.applica_ritenuta
    assert proforma.iva == 0 and proforma.ritenuta == 0
    assert proforma.applica_bollo and proforma.bollo == 2.0
    xml = genera_xml_fattura(proforma)
    assert b"<Natura>N2.2</Natura>" in xml and b"<BolloVirtuale>SI</BolloVirtuale>" in xml


def test_bollo_esplicitamente_escluso_resta_escluso(tmp_path: Path):
    manager = GestioneFatturazione(str(tmp_path / "p.json"))
    voci = [VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=300)]
    proposto = manager.crea(id_cliente="c1", voci=voci, applica_iva=False)
    escluso = manager.crea(id_cliente="c1", voci=voci, applica_iva=False, applica_bollo=False)
    assert proposto.applica_bollo and not escluso.applica_bollo
