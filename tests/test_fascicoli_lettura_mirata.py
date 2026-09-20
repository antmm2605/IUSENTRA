"""Aprire un fascicolo non deve costare la lettura dell'intero archivio.

Il repository nasceva su un file JSON unico: caricare tutto era l'unico modo
possibile. Con SQLite `id` e' PRIMARY KEY, quindi il fascicolo richiesto si
prende con una ricerca su indice. Questi test fissano le due cose che contano:
il fascicolo letto cosi' e' identico a prima, e l'archivio non viene letto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pct.fascicoli import Fascicolo, GestioneFascicoli, StatoFascicolo, TipoFascicolo


def _studio(tmp_path: Path) -> GestioneFascicoli:
    from pct.storage import StudioDB

    db = StudioDB.get(str(tmp_path / "studio.db"))
    db.ensure_schema()
    return db


def _repo(tmp_path: Path, *, carica_tutto: bool = True) -> GestioneFascicoli:
    return GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        studio_db=_studio(tmp_path),
        carica_tutto=carica_tutto,
    )


def _semina(tmp_path: Path, quanti: int = 5) -> list[str]:
    repo = _repo(tmp_path)
    ids: list[str] = []
    for indice in range(quanti):
        creato = repo.nuovo(
            titolo=f"Pratica {indice}",
            tipo=TipoFascicolo.CIVILE,
            nome_cliente=f"Cliente {indice}",
            numero_rg=str(1000 + indice),
            anno_rg="2026",
        )
        ids.append(creato.id)
    return sorted(ids)


def test_il_fascicolo_letto_in_modo_mirato_e_identico(tmp_path: Path):
    ids = _semina(tmp_path)

    completo = _repo(tmp_path)
    mirato = _repo(tmp_path, carica_tutto=False)

    atteso = completo.get(ids[2])
    ottenuto = mirato.get(ids[2])

    assert ottenuto is not None
    assert ottenuto.to_dict() == atteso.to_dict()


def test_in_modo_mirato_gli_altri_fascicoli_non_vengono_letti(tmp_path: Path):
    ids = _semina(tmp_path)
    mirato = _repo(tmp_path, carica_tutto=False)

    assert mirato._fascicoli == {}  # niente in memoria prima della richiesta
    mirato.get(ids[2])

    # In memoria c'e' solo quello richiesto: gli altri quattro non sono stati letti.
    assert list(mirato._fascicoli) == [ids[2]]


def test_un_id_inesistente_non_carica_l_archivio(tmp_path: Path):
    _semina(tmp_path)
    mirato = _repo(tmp_path, carica_tutto=False)

    assert mirato.get("NON-ESISTE") is None
    assert mirato._fascicoli == {}


def test_indice_leggero_elenca_tutti_senza_idratarli(tmp_path: Path):
    ids = _semina(tmp_path)
    mirato = _repo(tmp_path, carica_tutto=False)

    indice = mirato.indice_leggero()

    assert len(indice) == 5
    assert {riga.id for riga in indice} == set(ids)
    # Le righe servono ad appaiare cliente e ruolo, non a leggere i documenti.
    assert indice[0].nome_cliente
    assert indice[0].numero_rg
    assert not hasattr(indice[0], "documenti")
    # E nessun fascicolo e' stato idratato per ottenerle.
    assert mirato._fascicoli == {}


def test_chi_chiede_tutti_ottiene_l_archivio_intero(tmp_path: Path):
    """Nessun chiamante deve ritrovarsi con dati parziali senza accorgersene."""

    ids = _semina(tmp_path)
    mirato = _repo(tmp_path, carica_tutto=False)
    mirato.get(ids[1])

    tutti = mirato.tutti()

    assert len(tutti) == 5
    assert {f.id for f in tutti} == set(ids)


def test_dopo_tutti_la_lettura_mirata_resta_coerente(tmp_path: Path):
    ids = _semina(tmp_path)
    mirato = _repo(tmp_path, carica_tutto=False)
    mirato.tutti()

    letto = mirato.get(ids[3])

    assert letto is not None
    assert letto.nome_cliente.startswith("Cliente ")


def test_il_comportamento_predefinito_non_cambia(tmp_path: Path):
    """Chi non chiede la modalita' mirata trova l'archivio gia' caricato."""

    _semina(tmp_path)
    repo = _repo(tmp_path)

    assert len(repo._fascicoli) == 5
    assert len(repo.tutti()) == 5
