from pathlib import Path

from pct.fatturazione import GestioneFatturazione, VoceParcella
from pct.preventivi import GestionePreventivi, VocePreventivo


def test_preventivo_salva_log_calcolo(tmp_path: Path):
    db_path = tmp_path / "preventivi.json"
    gp = GestionePreventivi(db_path=str(db_path))

    preventivo = gp.crea_preventivo(
        id_cliente="cliente-1",
        oggetto="Preventivo prova",
        voci=[VocePreventivo(descrizione="Compenso", importo=1000.0)],
        log_calcolo='{"source":"preventivo_guidato","pratica_label":"Mediazione civile"}',
    )

    gp_reload = GestionePreventivi(db_path=str(db_path))
    loaded = gp_reload.get_preventivo(preventivo.id)

    assert loaded is not None
    assert loaded.log_calcolo
    assert "Mediazione civile" in loaded.log_calcolo


def test_parcella_salva_provenienza_e_log_calcolo(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        id_preventivo="prev-123",
        origine="preventivo",
        id_pratica="negoziazione_assistita",
        area_pratica="Stragiudiziale",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
        tipo_procedimento="Negoziazione assistita — Procedura ADR",
        valore_controversia=10000.0,
        complessita="media",
        log_calcolo='{"source":"parcella_da_preventivo","adr":{"enabled":true,"accordo":true}}',
        voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=1000.0)],
        note="Compenso professionale",
    )

    gf_reload = GestioneFatturazione(db_path=str(db_path))
    loaded = gf_reload.get(parcella.id)

    assert loaded is not None
    assert loaded.id_preventivo == "prev-123"
    assert loaded.origine == "preventivo"
    assert loaded.id_pratica == "negoziazione_assistita"
    assert loaded.log_calcolo
    assert '"accordo":true' in loaded.log_calcolo


def test_parcella_associa_la_procedura_operativa(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        id_preventivo="prev-ric-001",
        origine="preventivo",
        id_pratica="ricorso_tributario",
        area_pratica="Tributario",
        tipo_compenso="Per fasi processuali (D.M. 55/2014)",
        tipo_procedimento="Ricorso tributario di primo grado",
        voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=1200.0)],
    )

    gf_reload = GestioneFatturazione(db_path=str(db_path))
    loaded = gf_reload.get(parcella.id)

    assert loaded is not None
    assert loaded.procedura_operativa_codice == "PROC_TRIB_RIC_002"
    assert loaded.canale_operativo == "PTT_TRIBUTARIO"
    assert loaded.registro_operativo == "PTT_TRIBUTARIO"


def test_parcella_personalizzata_calcola_spese_generali_spese_e_anticipazioni(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        data_emissione="2026-05-10",
        data_scadenza="2026-06-09",
        applica_iva=True,
        applica_cassa=True,
        applica_ritenuta=True,
        percentuale_spese_generali=15,
        voci=[
            VoceParcella(descrizione="Compenso professionale", quantita=1, prezzo_unitario=200.0, tipo="ONORARIO"),
            VoceParcella(descrizione="Spese imponibili", quantita=1, prezzo_unitario=20.0, tipo="SPESE"),
            VoceParcella(descrizione="Contributo unificato", quantita=1, prezzo_unitario=43.5, tipo="ANTICIPO"),
        ],
    )

    assert parcella.totale_competenze == 200.0
    assert parcella.totale_spese_imponibili == 20.0
    assert parcella.totale_anticipazioni == 43.5
    assert parcella.spese_generali == 30.0
    assert parcella.imponibile == 250.0
    assert parcella.cassa_forense == 10.0
    assert parcella.base_iva == 260.0
    assert parcella.iva == 57.2
    assert parcella.ritenuta == 46.0
    assert parcella.totale_documento == 360.7
    assert parcella.totale == 314.7


def test_parcella_personalizzata_salva_tipo_voci_e_snapshot_documento(tmp_path: Path):
    db_path = tmp_path / "parcelle.json"
    gf = GestioneFatturazione(db_path=str(db_path))

    parcella = gf.crea(
        id_cliente="cliente-1",
        percentuale_spese_generali=15,
        metodo_pagamento="Bonifico",
        voci=[VoceParcella(descrizione="Visura", quantita=1, prezzo_unitario=18.0, tipo="SPESE")],
        dati_personalizzati={
            "document": {
                "tipo_documento": "TD01",
                "numero_documento": "2026/005",
                "causale_oggetto": "Parcella fascicolo RG 120/2026",
            },
            "payment": {
                "modalita_pagamento_label": "Bonifico",
                "iban": "IT60X0542811101000000123456",
            },
        },
    )

    gf_reload = GestioneFatturazione(db_path=str(db_path))
    loaded = gf_reload.get(parcella.id)

    assert loaded is not None
    assert loaded.percentuale_spese_generali == 15
    assert loaded.metodo_pagamento == "Bonifico"
    assert loaded.voci[0].tipo == "SPESE"
    assert loaded.dati_personalizzati["document"]["numero_documento"] == "2026/005"
    assert loaded.dati_personalizzati["payment"]["iban"] == "IT60X0542811101000000123456"
