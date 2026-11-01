"""Riga di sintesi per fascicolo del registro delle letture (01/11/2026)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from pct.registro_letture import Oggetto, RegistroLetture
from pct.registro_letture.identita import date_di_chiusura, identita_fascicolo, prossima_udienza
from pct.registro_letture.sintesi import identita_cambiata

OGGI = date(2026, 11, 1)


def _fascicolo(**campi):
    base = dict(id="F1", id_cliente="C1", nome_cliente="Anna Bianchi", tipo="LAVORO", tribunale="Tribunale di Palmi",
                numero_rg="1306", anno_rg=2024, stato="DEFINITO", data_apertura="2024-05-10", data_chiusura="2025-03-21",
                data_prossima_udienza="2025-03-21", attivita=[], archivio=None)
    base.update(campi)
    return SimpleNamespace(**base)


def test_prossima_udienza_solo_futura_anche_dalle_attivita():
    assert prossima_udienza(_fascicolo(), oggi=OGGI) == ""
    attivita = [SimpleNamespace(tipo="UDIENZA", titolo="Udienza di discussione", data="2026-12-03"),
                SimpleNamespace(tipo="ALTRO", titolo="Deposito memoria", data="2026-11-20")]
    assert prossima_udienza(_fascicolo(attivita=attivita), oggi=OGGI) == "2026-12-03"


def test_definizione_e_archiviazione_non_si_confondono():
    assert date_di_chiusura(_fascicolo()) == ("2025-03-21", "")
    archiviato = _fascicolo(stato="ARCHIVIATO", data_chiusura="2025-06-30", archivio=SimpleNamespace(data_archiviazione="2025-06-30"))
    assert date_di_chiusura(archiviato) == ("", "2025-06-30")
    definito_poi_archiviato = _fascicolo(stato="ARCHIVIATO", data_chiusura="2025-03-21", archivio=SimpleNamespace(data_archiviazione="2025-06-30"))
    assert date_di_chiusura(definito_poi_archiviato) == ("2025-03-21", "2025-06-30")


def test_la_riga_di_sintesi_riassume_identita_inventario_e_lettori(tmp_path: Path):
    registro = RegistroLetture(tmp_path / "registro.db")
    oggetti = [
        Oggetto(tipo="documento", oggetto_id="D1", nome="sentenza.pdf", sha256="a" * 64),
        Oggetto(tipo="documento", oggetto_id="D2", nome="ricorso.pdf", sha256="b" * 64),
        Oggetto(tipo="pec", oggetto_id="M1", nome="pec.eml", sha256="c" * 64),
    ]
    registro.registra_inventario("studio", "F1", oggetti)
    registro.segna_letto("studio", "F1", oggetti[0], "motore_documenti")
    identita = identita_fascicolo(_fascicolo(), oggi=OGGI)
    riga = registro.aggiorna_sintesi("studio", "F1", identita)
    assert (riga["documenti_presenti"], riga["pec_collegate"], riga["allegati_pec"]) == (2, 1, 0)
    assert riga["stato"] == "DEFINITO" and riga["data_definizione"] == "2025-03-21" and riga["prossima_udienza"] == ""
    motore = riga["lettori"]["motore_documenti"]
    assert motore["letti"] == 1 and motore["da_leggere"] == 1 and motore["versione"]
    assert riga["da_leggere"] >= 1
    # Riletta dal database: stessa riga, una sola per fascicolo
    registro.aggiorna_sintesi("studio", "F1", identita)
    salvata = registro.sintesi("studio", "F1")
    assert salvata["cliente"] == "Anna Bianchi" and salvata["lettori"]["motore_documenti"]["letti"] == 1
    assert [r["fascicolo_id"] for r in registro.sintesi_studio("studio")] == ["F1"]
    assert not identita_cambiata(salvata, identita)
    assert identita_cambiata(salvata, {**identita, "stato": "ARCHIVIATO"})


def test_il_giro_di_lettura_scrive_la_riga_di_sintesi(tmp_path: Path):
    from tests.test_archivio_letture_runtime import _app, _fascicolo as carica, _seed

    app = _app(tmp_path)
    fid, _, _ = _seed(app)
    with app.app_context():
        from web.services import archivio_letture_runtime as runtime
        from web.services.sintesi_fascicolo_runtime import sintesi_fascicolo

        runtime.leggi_fascicolo(carica(app, fid))
        riga = sintesi_fascicolo(fid)
        assert riga is not None and riga["documenti_presenti"] == 2
        assert riga["cliente"] == "Anna Bianchi" and riga["ufficio"] == "Tribunale di Torino"
        assert riga["lettori"]["motore_documenti"]["da_leggere"] == 0
