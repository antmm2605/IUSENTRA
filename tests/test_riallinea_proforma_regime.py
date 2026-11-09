"""Script di riallineamento delle proforma al regime forfetario (art. 1, commi 54-89, L. 190/2014)."""
import importlib.util
from pathlib import Path

from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "riallinea_proforma_regime_20261108.py"
_spec = importlib.util.spec_from_file_location("riallinea_proforma_regime", _PATH)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _proforma(manager, **extra):
    dati = {"document": {"documento_operativo": "PROFORMA"}}
    return manager.crea(id_cliente="c1", voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=500)],
                        applica_iva=True, applica_bollo=False, percentuale_spese_generali=15, dati_personalizzati=dati, **extra)


def test_elenco_e_correzione_solo_delle_proforma_in_bozza(tmp_path: Path):
    manager = GestioneFatturazione(str(tmp_path / "p.json"))
    da_correggere = _proforma(manager)
    da_preventivo = _proforma(manager, id_preventivo="PREV-1")
    pagata = _proforma(manager)
    manager._parcelle[pagata.id].data_pagamento = "2026-10-01"
    fattura = manager.crea(id_cliente="c1", voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=500)])
    manager.cambia_stato(fattura.id, StatoParcella.EMESSA)

    esito = script.classifica(manager, "RF19")
    assert [r["id"] for r in esito["da_correggere"]] == [da_correggere.id]
    assert {r["id"] for r in esito["da_decidere"]} == {da_preventivo.id, pagata.id}
    riga = esito["da_correggere"][0]
    # 500 + 15% spese generali = 575; CPA 4% = 23; senza IVA; bollo dovuto oltre € 77,47
    assert (riga["imponibile"], riga["cpa"], riga["totale_corretto"], riga["bollo_corretto"]) == (575.0, 23.0, 600.0, 2.0)
    assert riga["totale_attuale"] == round(598 * 1.22, 2)

    eventi = []
    fatti = script.correggi(manager, esito["da_correggere"], "RF19", audit=lambda *a: eventi.append(a))
    corretta = manager.get(da_correggere.id)
    assert fatti == [da_correggere.id] and len(eventi) == 1
    assert corretta.iva == 0 and corretta.totale == 600.0 and corretta.applica_bollo is None
    assert corretta.dati_personalizzati["document"]["regime_fiscale"] == "RF19"
    storico = corretta.dati_personalizzati["storico_regime"][0]
    assert storico["motivo"] == "regime forfettario RF19 – art. 1 c. 54-89 L. 190/2014"
    assert storico["prima"]["totale"] == riga["totale_attuale"]
    assert manager.get(fattura.id).dati_personalizzati.get("storico_regime") is None
    assert script.classifica(manager, "RF19")["da_correggere"] == []


def test_backup_prima_di_scrivere(tmp_path: Path):
    manager = GestioneFatturazione(str(tmp_path / "p.json"))
    _proforma(manager)
    copia = Path(script._backup(manager))
    assert copia.exists() and copia.read_bytes() == (tmp_path / "p.json").read_bytes()


def test_backup_su_database_copia_solo_le_parcelle(tmp_path: Path):
    """Il database dello studio pesa decine di GB: la copia di sicurezza prende solo la tabella che si riscrive."""
    import sqlite3
    from types import SimpleNamespace

    sorgente = tmp_path / "studio.db"
    with sqlite3.connect(sorgente) as conn:
        conn.execute("CREATE TABLE parcelle (id TEXT PRIMARY KEY, dati TEXT)")
        conn.executemany("INSERT INTO parcelle VALUES (?, ?)", [("p1", "a"), ("p2", "b")])
        conn.execute("CREATE TABLE documenti (id TEXT, contenuto BLOB)")
        conn.execute("INSERT INTO documenti VALUES ('d1', zeroblob(100000))")
    manager = SimpleNamespace(_studio_db=SimpleNamespace(db_path=str(sorgente)))

    copia = Path(script._backup(manager))
    with sqlite3.connect(copia) as conn:
        tabelle = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        righe = conn.execute("SELECT id, dati FROM parcelle ORDER BY id").fetchall()
    assert tabelle == ["parcelle"] and righe == [("p1", "a"), ("p2", "b")]
    assert copia.stat().st_size < sorgente.stat().st_size
