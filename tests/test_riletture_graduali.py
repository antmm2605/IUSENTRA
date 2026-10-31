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
    assert set(elenco) == {"F-VECCHIO", "F-MEDIO"} and "F-NUOVO" not in elenco
    assert runtime.fascicoli_da_aggiornare(registro, TENANT, limite=1) == elenco[:1]
    assert runtime.accoda_riletture_notturne(registro, TENANT, ora=14) == 0
    assert runtime.accoda_riletture_notturne(registro, TENANT, ora=2, limite=2) == 2
    assert {e["fascicolo_id"] for e in registro.eventi_da_riprendere(TENANT, limite=10)} == set(elenco)


def test_accodamento_che_fallisce_non_ferma_il_giro():
    class Guasto:
        def righe_fascicoli(self, *a, **k):
            raise RuntimeError("registro")

    assert runtime.accoda_riletture_notturne(Guasto(), TENANT, ora=1) == 0
