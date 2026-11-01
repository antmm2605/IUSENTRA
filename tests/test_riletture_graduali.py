"""Rilettura graduale con il motore corrente dei documenti letti da motori superati (31/10/2026).

In produzione 277 fascicoli su 336 erano fermi alla lettura del 17/09/2026: le regole nuove non
arrivavano ai documenti già letti. La rilettura usa i testi salvati, di notte, pochi fascicoli per giro.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pct.archivio_letture import VERSIONE_MOTORE_DOCUMENTI
from pct.registro_letture import Oggetto, RegistroLetture
from web.services import archivio_letture_runtime as runtime

TENANT = "default"


def _oggetto(indice: int) -> Oggetto:
    return Oggetto(tipo="documento", oggetto_id=f"DOC{indice}", nome=f"atto{indice}.pdf",
                   sha256=hashlib.sha256(f"atto{indice}".encode()).hexdigest())


def _registro(tmp_path: Path) -> RegistroLetture:
    return RegistroLetture(db_path=str(tmp_path / "registro.db"))


def test_superati_solo_letture_riuscite_di_versione_diversa(tmp_path):
    registro = _registro(tmp_path)
    oggetti = [_oggetto(i) for i in range(4)]
    registro.registra_inventario(TENANT, "F1", oggetti, tipi=("documento",))
    registro.segna_letto(TENANT, "F1", oggetti[0], "motore_documenti", versione="vecchia")
    registro.segna_letto(TENANT, "F1", oggetti[1], "motore_documenti", versione=VERSIONE_MOTORE_DOCUMENTI)
    registro.segna_letto(TENANT, "F1", oggetti[2], "motore_documenti", versione="vecchia", stato="non_leggibile")
    superati = registro.superati(TENANT, "F1", "motore_documenti", versione=VERSIONE_MOTORE_DOCUMENTI, tipi=("documento",))
    assert [o.oggetto_id for o in superati] == ["DOC0"]
    assert registro.superati(TENANT, "F1", "motore_documenti", versione=VERSIONE_MOTORE_DOCUMENTI, tipi=("pec",)) == []


def test_fascicoli_da_aggiornare_i_piu_vecchi_per_primi_e_solo_di_notte(tmp_path):
    registro = _registro(tmp_path)
    for fid, versione in (("F-NUOVO", VERSIONE_MOTORE_DOCUMENTI), ("F-VECCHIO", "v7"), ("F-MEDIO", "v12")):
        registro.registra_inventario(TENANT, fid, [_oggetto(1)], tipi=("documento",))
        registro.segna_fascicolo(TENANT, fid, "motore_documenti", impronta="i", oggetti_totali=1, oggetti_letti=1,
                                 versione=versione)
    registro.segna_fascicolo(TENANT, "F-ROTTO", "motore_documenti", impronta="i", oggetti_totali=1, oggetti_letti=0,
                             stato="errore", versione="v7")
    elenco = runtime.fascicoli_da_aggiornare(registro, TENANT, limite=10)
    # Anche il fascicolo rimasto in errore torna in coda (01/11/2026: 99 fascicoli esclusi per sempre).
    assert set(elenco) == {"F-VECCHIO", "F-MEDIO", "F-ROTTO"} and "F-NUOVO" not in elenco
    assert runtime.fascicoli_da_aggiornare(registro, TENANT, limite=1) == elenco[:1]
    assert runtime.accoda_riletture_notturne(registro, TENANT, ora=14) == 0
    assert runtime.accoda_riletture_notturne(registro, TENANT, ora=2, limite=2) == 2
    assert {e["fascicolo_id"] for e in registro.eventi_da_riprendere(TENANT, limite=10)} == set(elenco[:2])


def test_un_fascicolo_in_errore_con_versione_corrente_torna_in_coda(tmp_path):
    registro = _registro(tmp_path)
    registro.segna_fascicolo(TENANT, "F-LOCK", "motore_documenti", impronta="", oggetti_totali=0, oggetti_letti=0,
                             stato="errore", versione=VERSIONE_MOTORE_DOCUMENTI, esito={"motivo": "OperationalError: database is locked"})
    registro.segna_fascicolo(TENANT, "F-OK", "motore_documenti", impronta="i", oggetti_totali=1, oggetti_letti=1,
                             versione=VERSIONE_MOTORE_DOCUMENTI)
    assert runtime.fascicoli_da_aggiornare(registro, TENANT, limite=10) == ["F-LOCK"]


def test_accodamento_che_fallisce_non_ferma_il_giro():
    class Guasto:
        def righe_fascicoli(self, *a, **k):
            raise RuntimeError("registro")

    assert runtime.accoda_riletture_notturne(Guasto(), TENANT, ora=1) == 0


def test_recupero_completo_mette_in_coda_tutti_i_fascicoli_da_riprendere(tmp_path, monkeypatch):
    """01/11/2026: avvio manuale del recupero dalla console «Pianificazioni», a qualsiasi ora."""
    from types import SimpleNamespace

    registro = _registro(tmp_path)
    for fid, versione, stato in (("F-V7", "v7", "completa"), ("F-ERR", VERSIONE_MOTORE_DOCUMENTI, "errore"),
                                 ("F-OK", VERSIONE_MOTORE_DOCUMENTI, "completa")):
        registro.segna_fascicolo(TENANT, fid, "motore_documenti", impronta="i", oggetti_totali=1, oggetti_letti=1,
                                 stato=stato, versione=versione)
    monkeypatch.setattr(runtime, "_studi_della_coda", lambda app: [(TENANT, {})])
    monkeypatch.setattr(runtime, "registro_per_percorsi", lambda paths: registro)
    esito = runtime.accoda_recupero_completo(SimpleNamespace(config={}))
    assert esito == {"studi": 1, "accodati": 2}
    assert {e["fascicolo_id"] for e in registro.eventi_da_riprendere(TENANT, limite=10)} == {"F-V7", "F-ERR"}


def test_il_recupero_completo_e_una_pianificazione_della_console():
    from pct.scheduler_registry import default_scheduler_templates

    voce = next(t for t in default_scheduler_templates({}) if t.key == "letture_recupero_completo")
    assert voce.built_in and voce.day_of_week == "sun" and voce.name == "Recupero completo delle letture"
