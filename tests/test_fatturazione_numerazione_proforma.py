"""Numerazione separata delle proforma e conversione in fattura.

Art. 21, comma 2, lett. a-b, D.P.R. 633/1972: la fattura reca la data di emissione
e un numero progressivo univoco; la proforma non è una fattura e non consuma la serie.
"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pct.fatturazione import GestioneFatturazione, Parcella, StatoParcella, VoceParcella
from pct.storage import StudioDB

_PROFORMA = {"document": {"documento_operativo": "PROFORMA", "tipo_documento_label": "Proforma"}}


def _voci():
    return [VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=500)]


def _proforma(manager, data="2026-03-10", scadenza="2026-04-09"):
    return manager.crea(id_cliente="c1", voci=_voci(), data_emissione=data, data_scadenza=scadenza,
                        dati_personalizzati={"document": dict(_PROFORMA["document"])})


def test_proforma_ha_numerazione_propria_e_non_consuma_la_serie_fiscale(tmp_path: Path):
    manager = GestioneFatturazione(db_path=str(tmp_path / "p.json"))
    prima = manager.crea(id_cliente="c1", voci=_voci(), data_emissione="2026-03-01")
    pf1 = _proforma(manager)
    pf2 = _proforma(manager)
    seconda = manager.crea(id_cliente="c1", voci=_voci(), data_emissione="2026-03-12")
    assert prima.numero == "2026/001"
    assert (pf1.numero, pf2.numero) == ("PF-2026/001", "PF-2026/002")
    assert pf1.dati_personalizzati["document"]["numero_documento"] == "PF-2026/001"
    assert seconda.numero == "2026/002"
    numerazione = manager.carica_numerazione(2026)
    assert numerazione["prossimoNumero"] == "2026/003"
    assert numerazione["prossimoNumeroProforma"] == "PF-2026/003"


def test_conversione_assegna_numero_fiscale_successivo_e_data_odierna(tmp_path: Path):
    manager = GestioneFatturazione(db_path=str(tmp_path / "p.json"))
    manager.crea(id_cliente="c1", voci=_voci(), data_emissione="2026-01-05")
    pf = _proforma(manager, data="2025-12-01", scadenza="2025-12-31")
    manager.cambia_stato(pf.id, StatoParcella.EMESSA)
    fattura = manager.get(pf.id)
    oggi = datetime.now(ZoneInfo("Europe/Rome")).date()
    assert fattura.numero == f"{oggi.year}/" + ("002" if oggi.year == 2026 else "001")
    assert fattura.data_emissione == oggi.isoformat()
    document = fattura.dati_personalizzati["document"]
    assert document["documento_operativo"] == "FATTURA"
    assert document["numero_documento"] == fattura.numero
    assert document["data_documento"] == oggi.isoformat()
    riferimento = fattura.dati_personalizzati["proforma"]
    assert riferimento["numero_proforma"] == "PF-2025/001"
    assert riferimento["data_proforma"] == "2025-12-01"
    # la scadenza scaduta riparte dalla data della fattura conservando i 30 giorni
    assert fattura.data_scadenza > fattura.data_emissione


def test_proforma_storiche_in_formato_fiscale_non_bloccano_la_serie(tmp_path: Path):
    """Le proforma storiche con numero 2026/009-085 restano fuori dalla serie fiscale."""
    manager = GestioneFatturazione(db_path=str(tmp_path / "p.json"))
    annullata = manager.crea(id_cliente="c1", voci=_voci(), data_emissione="2026-04-10")
    manager.cambia_stato(annullata.id, StatoParcella.ANNULLATA)
    for numero in ("2026/009", "2026/085"):
        storica = Parcella.from_dict({**_proforma(manager).to_dict(), "numero": numero})
        manager._parcelle[storica.id] = storica
    assert manager._prossimo_numero(2026) == "2026/002"
    assert manager._prossimo_numero_proforma(2026).startswith("PF-2026/")
    assert int(manager._prossimo_numero_proforma(2026).rsplit("/", 1)[1]) > 85
    storica = next(p for p in manager.tutte() if p.numero == "2026/085")
    assert storica.numero_visibile == "PF-2026/085"
    assert annullata.numero_visibile == "2026/001"


def test_conversione_sql_conserva_il_riferimento(tmp_path: Path):
    db = StudioDB.get(str(tmp_path / "studio.db"))
    try:
        manager = GestioneFatturazione(db_path=str(tmp_path / "p.json"), studio_db=db)
        pf = _proforma(manager)
        manager.cambia_stato(pf.id, StatoParcella.EMESSA)
        fresh = GestioneFatturazione(db_path=str(tmp_path / "p.json"), studio_db=db)
        fattura = fresh.get(pf.id)
        assert not fattura.numero.startswith("PF-")
        assert fattura.dati_personalizzati["proforma"]["numero_proforma"] == pf.numero
        nuova_pf = _proforma(fresh)
        assert nuova_pf.numero.startswith("PF-")
    finally:
        db.chiudi()
