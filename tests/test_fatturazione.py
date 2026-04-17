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
