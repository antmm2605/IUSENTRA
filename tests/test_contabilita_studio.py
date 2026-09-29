"""Contabilità di studio: riepilogo annuale per cassa (art. 54 TUIR, L. 190/2014) e registro fatture emesse (art. 23 D.P.R. 633/1972)."""

from __future__ import annotations

from types import SimpleNamespace

from pct.contabilita.registro_iva import csv_registro, registro_fatture_emesse
from pct.contabilita.riepilogo import riepilogo_annuale
from pct.prima_nota import GestionePrimaNota


def _registro(tmp_path):
    registro = GestionePrimaNota(str(tmp_path / "prima_nota.json"))
    registro.registra(data="2026-02-10", tipo="INCASSO", importo=10000, categoria="onorari")
    registro.registra(data="2026-03-10", tipo="INCASSO", importo=2000, categoria="onorari")
    registro.registra(data="2026-03-11", tipo="INCASSO", importo=300, categoria="anticipazioni_rimborsate")
    registro.registra(data="2026-04-01", tipo="PAGAMENTO", importo=1500, categoria="spese_studio")
    registro.registra(data="2026-04-02", tipo="PAGAMENTO", importo=300, categoria="anticipazioni_clienti")
    registro.registra(data="2026-06-30", tipo="PAGAMENTO", importo=1200, categoria="contributi_previdenziali")
    registro.registra(data="2025-12-30", tipo="INCASSO", importo=999, categoria="onorari")
    return registro


def test_riepilogo_ordinario_per_cassa_con_storno(tmp_path):
    registro = _registro(tmp_path)
    secondo = [m for m in registro.registro() if m.importo == 2000][0]
    registro.storna(secondo.id, motivo="Incasso registrato due volte")
    esito = riepilogo_annuale(registro, 2026, regime="RF01")
    assert esito["compensi_incassati"] == 10000.0  # lo storno si toglie dagli onorari
    assert esito["spese_deducibili"] == 1500.0 and esito["anticipazioni_per_clienti"] == 300.0
    assert esito["stima"]["reddito_lavoro_autonomo"] == 8500.0
    assert esito["mesi"][1] == {"mese": "feb", "incassi": 10000.0, "pagamenti": 0.0}


def test_riepilogo_forfettario_usa_il_coefficiente_del_78(tmp_path):
    esito = riepilogo_annuale(_registro(tmp_path), 2026, regime="RF19")
    stima = esito["stima"]
    assert stima["reddito_forfettario"] == 9360.0  # 12.000 × 78%
    assert stima["imponibile"] == 8160.0 and stima["aliquota"] == 15.0
    assert stima["imposta_sostitutiva"] == 1224.0
    assert riepilogo_annuale(_registro(tmp_path / "b"), 2026, regime="RF19", startup=True)["stima"]["aliquota"] == 5.0


def _parcella(numero, data, *, trasmessa=True, iva=220.0, imponibile=1000.0, stato="EMESSA", split=False):
    return SimpleNamespace(
        numero=numero, data_emissione=data, id_cliente="C1", stato=SimpleNamespace(value=stato),
        sdi_identificativo="123" if trasmessa else "", sdi_data_invio="", iva=iva, imponibile=imponibile,
        cassa_forense=imponibile * 0.04, aliquota_iva=22.0, iva_applicabile=True, totale_documento=imponibile + iva,
        dati_personalizzati={"document": {"esigibilita_iva": "S" if split else "I"}},
    )


def test_registro_fatture_emesse_e_iva_a_debito():
    fatturazione = SimpleNamespace(tutte=lambda: [
        _parcella("2026/1", "2026-01-15"), _parcella("2026/2", "2026-05-20", iva=110.0, imponibile=500.0),
        _parcella("2026/3", "2026-05-21", trasmessa=False), _parcella("2026/4", "2026-06-01", stato="BOZZA"),
        _parcella("2026/5", "2026-11-03", split=True), _parcella("2025/9", "2025-12-30"),
    ])
    registro = registro_fatture_emesse(fatturazione, 2026)
    assert [f["numero"] for f in registro["fatture"]] == ["2026/1", "2026/2", "2026/5"]
    assert registro["proforma_escluse"] == 1
    liquidazioni = {r["periodo"]: r for r in registro["liquidazioni"]}
    assert liquidazioni["1° trimestre"]["iva_a_debito"] == 220.0 and liquidazioni["1° trimestre"]["interessi_1_per_cento"] == 2.2
    assert liquidazioni["2° trimestre"]["iva_a_debito"] == 110.0
    assert "4° trimestre" not in liquidazioni  # scissione dei pagamenti: IVA versata dall'ente
    assert "2026/5;2026-11-03" in csv_registro(registro)
