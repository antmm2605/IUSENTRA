"""Memorie art. 171-ter c.p.c.: «almeno quaranta / venti / dieci giorni prima dell'udienza».

Fino alla 2.457.6 i preset dello scadenziario contavano in avanti dall'udienza: la memoria risultava dopo
l'udienza. Dall'audit del 29/10/2026 «almeno N giorni prima» si legge prudenzialmente a giorni liberi (escluso
anche il giorno finale), come i modelli CIV_MEMORIA_171_TER_* del motore `pct.termini_processuali`; anticipo al
giorno utile precedente se l'ultimo giorno cade di sabato o festivo (art. 155 c.p.c.) e sospensione feriale
dal 1° al 31 agosto (L. 742/1969).
"""
from __future__ import annotations

from datetime import date

import pytest

from pct.riconvalida_termini_ritroso import riconvalida_memorie_171ter
from pct.scadenziario import (
    PRESET_TERMINI,
    GestioneScadenziario,
    StatoTermine,
    TipoTermine,
    calcola_termine,
    profilo_da_preset,
)
from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator

_MODELLI = {template.code: template for template in DEFAULT_TEMPLATES}


def _legale(preset: str, udienza: str) -> str:
    esito = GestioneScadenziario.calcola_avanzata(start_at=date.fromisoformat(udienza), profile=profilo_da_preset(preset))
    return esito.legal_due_at[:10]


@pytest.mark.parametrize(
    ("preset", "udienza", "attesa"),
    [
        ("memoria_ex_171_ter_n1", "2026-11-23", "2026-10-13"),
        ("memoria_ex_171_ter_n2", "2026-11-23", "2026-11-02"),
        ("memoria_ex_171_ter_n3", "2026-11-23", "2026-11-12"),
        # Il conteggio a ritroso salta agosto (sospensione feriale).
        ("memoria_ex_171_ter_n1", "2026-09-20", "2026-07-10"),
        # Decimo giorno 07/12/2026; libero 06/12 domenica, 05/12 sabato -> venerdì 04/12/2026.
        ("memoria_ex_171_ter_n3", "2026-12-17", "2026-12-04"),
    ],
)
def test_memorie_171ter_prima_dell_udienza(preset: str, udienza: str, attesa: str) -> None:
    assert _legale(preset, udienza) == attesa
    assert attesa < udienza


def test_ultimo_giorno_festivo_si_anticipa() -> None:
    # Udienza 05/01/2027: dieci giorni liberi prima è il 25/12/2026 (Natale) → giovedì 24/12/2026.
    assert _legale("memoria_ex_171_ter_n3", "2027-01-05") == "2026-12-24"


@pytest.mark.parametrize("udienza", ["2026-11-23", "2026-09-20", "2027-01-05", "2027-03-01", "2026-10-05"])
@pytest.mark.parametrize(("preset", "giorni"), [("memoria_ex_171_ter_n1", 40), ("memoria_ex_171_ter_n2", 20), ("memoria_ex_171_ter_n3", 10)])
def test_stesso_risultato_del_motore_termini(preset: str, giorni: int, udienza: str) -> None:
    modello = _MODELLI[f"CIV_MEMORIA_171_TER_{preset[-1]}"]
    assert modello.base_value == giorni and modello.free_term is True
    motore = ItalianDeadlineCalculator().calculate_template(date.fromisoformat(udienza), modello)
    assert _legale(preset, udienza) == motore["deadline"]


def test_nuova_da_preset_salva_la_data_a_ritroso(tmp_path) -> None:
    gs = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = gs.nuova_da_preset("memoria_ex_171_ter_n1", "Memoria 171-ter n. 1", "2026-11-23")
    assert scadenza.data_scadenza == "2026-10-13"
    assert scadenza.deadline_profile_code == "TERM_40_DAYS_BEFORE"
    assert scadenza.source_event_at == "2026-11-23"


def test_profili_in_avanti_invariati() -> None:
    esito = GestioneScadenziario.calcola_avanzata(start_at=date(2026, 3, 2), profile=profilo_da_preset("appello_breve"))
    assert esito.legal_due_at[:10] > "2026-03-02"


def test_prescrizione_breve_cinque_anni() -> None:
    esito = GestioneScadenziario.calcola_avanzata(start_at=date(2026, 3, 2), profile=profilo_da_preset("prescrizione_breve_5anni"))
    assert esito.legal_due_at[:10] == "2031-03-03"  # 02/03/2031 è domenica: proroga al lunedì


def _vecchia_memoria(gs: GestioneScadenziario, udienza: str, *, data: str | None = None):
    preset = PRESET_TERMINI["memoria_ex_171_ter_n1"]
    vecchia = data or calcola_termine(date.fromisoformat(udienza), giorni=40, tipo="liberi", sospensione_feriale=True).isoformat()
    return gs.nuova(
        titolo="Memoria art. 171-ter n. 1", tipo=TipoTermine.TERMINE_PERENTORIO, data_scadenza=vecchia,
        descrizione=preset["descrizione"], data_decorrenza=udienza, deadline_profile_code="TERM_40_DAYS",
        source_event_type="udienza", source_event_at=udienza,
    )


def test_riconvalida_corregge_le_memorie_del_vecchio_calcolo(tmp_path) -> None:
    gs = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = _vecchia_memoria(gs, "2026-11-23")
    assert scadenza.data_scadenza > "2026-11-23"

    esito = riconvalida_memorie_171ter(gs)

    corretta = gs.get(scadenza.id)
    assert esito == {"corrette": 1, "da_verificare": 0}
    assert corretta.data_scadenza == "2026-10-13"
    assert corretta.deadline_profile_code == "TERM_40_DAYS_BEFORE"
    assert "ricalcolata a ritroso" in corretta.note
    # Idempotente: un secondo giro non cambia nulla.
    assert riconvalida_memorie_171ter(gs) == {"corrette": 0, "da_verificare": 0}


def test_riconvalida_non_tocca_la_data_scelta_dall_avvocato(tmp_path) -> None:
    gs = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = _vecchia_memoria(gs, "2026-11-23", data="2026-12-20")

    esito = riconvalida_memorie_171ter(gs)

    rimasta = gs.get(scadenza.id)
    assert esito == {"corrette": 0, "da_verificare": 1}
    assert rimasta.data_scadenza == "2026-12-20"
    assert "13/10/2026" in rimasta.note
    assert riconvalida_memorie_171ter(gs) == {"corrette": 0, "da_verificare": 0}


def test_riconvalida_ignora_completate_e_altri_termini(tmp_path) -> None:
    gs = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    completata = _vecchia_memoria(gs, "2026-11-23")
    gs.completa(completata.id)
    altro = gs.nuova(titolo="Appello", tipo=TipoTermine.TERMINE_PERENTORIO, data_scadenza="2026-12-30",
                     deadline_profile_code="TERM_30_DAYS", source_event_type="notifica", source_event_at="2026-11-23")

    assert riconvalida_memorie_171ter(gs) == {"corrette": 0, "da_verificare": 0}
    assert gs.get(completata.id).stato == StatoTermine.COMPLETATO
    assert gs.get(altro.id).data_scadenza == "2026-12-30"


def test_appello_lungo_include_la_sospensione_feriale() -> None:
    # Art. 327 c.p.c. e L. 742/1969: sei mesi più i 31 giorni di agosto (11/10/2026 è domenica → 12/10/2026).
    esito = GestioneScadenziario.calcola_avanzata(start_at=date(2026, 3, 10), profile=profilo_da_preset("appello_lungo"))
    assert esito.legal_due_at[:10] == "2026-10-12"
    assert calcola_termine(date(2026, 3, 10), mesi=6, tipo="continui", sospensione_feriale=True).isoformat() == "2026-10-12"
    # Senza agosto nel periodo il termine resta di sei mesi.
    assert calcola_termine(date(2026, 1, 31), mesi=6, tipo="continui", sospensione_feriale=True).isoformat() == "2026-07-31"


def test_doppia_data_prudenziale_e_di_legge() -> None:
    esito = GestioneScadenziario.calcola_avanzata(start_at=date(2026, 11, 23), profile=profilo_da_preset("memoria_ex_171_ter_n1"))
    assert esito.legal_due_at[:10] == "2026-10-13"
    assert esito.scadenza_di_legge[:10] == "2026-10-14"
    assert "Depositare entro il 13/10/2026" in esito.nota_scadenza_di_legge()
    assert "14/10/2026" in esito.nota_scadenza_di_legge()


def test_nuova_da_preset_riporta_la_scadenza_di_legge(tmp_path) -> None:
    gs = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = gs.nuova_da_preset("memoria_ex_171_ter_n2", "Memoria 171-ter n. 2", "2026-11-23")
    assert scadenza.data_scadenza == "2026-11-02"
    assert "03/11/2026" in scadenza.descrizione


def test_motore_termini_espone_la_scadenza_di_legge() -> None:
    risultato = ItalianDeadlineCalculator().calculate_template(date(2026, 11, 23), _MODELLI["CIV_MEMORIA_171_TER_1"])
    assert risultato["deadline"] == "2026-10-13"
    assert risultato["legalDeadline"] == "2026-10-14"
    assert "prudential_free_days_reading" in risultato["rulesApplied"]


def test_riconvalida_porta_alla_data_prudenziale_le_memorie_a_giorni_pieni(tmp_path) -> None:
    gs = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = _vecchia_memoria(gs, "2026-11-23", data="2026-10-14")
    gs.aggiorna(scadenza.id, deadline_profile_code="TERM_40_DAYS_BEFORE")

    assert riconvalida_memorie_171ter(gs) == {"corrette": 1, "da_verificare": 0}
    corretta = gs.get(scadenza.id)
    assert corretta.data_scadenza == "2026-10-13"
    assert "14/10/2026" in corretta.note
    assert riconvalida_memorie_171ter(gs) == {"corrette": 0, "da_verificare": 0}


def test_riconvalida_non_tocca_una_data_anticipata_dall_avvocato(tmp_path) -> None:
    gs = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = _vecchia_memoria(gs, "2026-11-23", data="2026-10-05")
    gs.aggiorna(scadenza.id, deadline_profile_code="TERM_40_DAYS_BEFORE")

    assert riconvalida_memorie_171ter(gs) == {"corrette": 0, "da_verificare": 0}
    assert gs.get(scadenza.id).data_scadenza == "2026-10-05"
