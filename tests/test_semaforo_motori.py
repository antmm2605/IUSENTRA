"""Semaforo dei motori: uno alla volta per tutto il server, coda per priorità, rilascio se il processo muore."""

from __future__ import annotations

import threading
import time

import pytest

from pct.semaforo_motori import PRIORITA_URGENTE, Semaforo, SemaforoOccupato, motore_pesante


class Orologio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_due_motori_non_partono_insieme(tmp_path):
    sem = Semaforo(tmp_path / "s.sqlite")
    attivi, massimo = [0], [0]
    blocco = threading.Lock()

    def lavora(nome):
        with motore_pesante(nome, semaforo=sem, intervallo=0.01):
            with blocco:
                attivi[0] += 1
                massimo[0] = max(massimo[0], attivi[0])
            time.sleep(0.05)
            with blocco:
                attivi[0] -= 1

    thread = [threading.Thread(target=lavora, args=(f"m{i}",)) for i in range(4)]
    for t in thread:
        t.start()
    for t in thread:
        t.join()
    assert massimo[0] == 1
    assert sem.stato()["in_corso"] == ""


def test_rilascio_alla_fine_e_su_errore(tmp_path):
    sem = Semaforo(tmp_path / "s.sqlite")
    with pytest.raises(RuntimeError):
        with motore_pesante("ocr", semaforo=sem):
            assert sem.stato()["in_corso"] == "ocr"
            raise RuntimeError("guasto")
    assert sem.prova("altro", "letture", 50)


def test_processo_morto_libera_il_semaforo(tmp_path):
    orologio = Orologio()
    sem = Semaforo(tmp_path / "s.sqlite", affitto_secondi=120, orologio=orologio)
    assert sem.prova("morto", "ocr", 10)  # il processo muore senza rilasciare
    assert not sem.prova("vivo", "letture", 50)
    orologio.t += 121
    assert sem.prova("vivo", "letture", 50)


def test_ordine_della_coda_per_priorita(tmp_path):
    orologio = Orologio()
    sem = Semaforo(tmp_path / "s.sqlite", orologio=orologio)
    assert sem.prova("a", "fonti ufficiali", 57)
    assert not sem.prova("b", "lex", 56)
    orologio.t += 1
    assert not sem.prova("c", "OCR", PRIORITA_URGENTE)
    stato = sem.stato()
    assert stato["in_corso"] == "fonti ufficiali" and stato["in_coda"] == ["OCR", "lex"]
    assert "In corso: fonti ufficiali; in coda: OCR, lex." == stato["testo"]
    sem.rilascia("a")
    assert not sem.prova("b", "lex", 56)  # tocca prima all'OCR
    assert sem.prova("c", "OCR", PRIORITA_URGENTE)


def test_attesa_massima(tmp_path):
    sem = Semaforo(tmp_path / "s.sqlite")
    assert sem.prova("x", "ocr", 10)
    with pytest.raises(SemaforoOccupato):
        with motore_pesante("lex", semaforo=sem, attesa_massima=0.05, intervallo=0.01):
            pass
    assert sem.stato()["in_coda"] == []


def test_senza_cartella_dati_non_blocca(monkeypatch):
    monkeypatch.delenv("PCT_SEMAFORO_DB", raising=False)
    monkeypatch.delenv("PCT_DATA_ROOT", raising=False)
    with motore_pesante("ocr") as preso:
        assert preso is False


def test_invecchiamento_chi_aspetta_supera_chi_rientra_subito(tmp_path):
    """Notte 03-04/11/2026: l'OCR (priorità 10) rientrava in coda dopo ogni documento e la catena non partiva mai."""
    orologio = Orologio()
    sem = Semaforo(tmp_path / "s.sqlite", orologio=orologio)
    assert sem.prova("ocr-1", "OCR", PRIORITA_URGENTE)
    assert not sem.prova("catena", "catena", 58)  # fase 8: priorità bassa
    turno_catena = False
    for giro in range(200):
        orologio.t += 5
        sem.rilascia(f"ocr-{giro + 1}")
        sem.prova("catena", "catena", 58)
        if sem.stato()["in_corso"] == "catena":
            turno_catena = True
            break
        assert sem.prova(f"ocr-{giro + 2}", "OCR", PRIORITA_URGENTE)
    assert turno_catena and orologio.t - 1000 <= 10 * 60
