"""Termini a mesi, sospensione feriale e materia lavoro: i tre motori danno la stessa data.

Norme (testo vigente su Normattiva, verificato l'08/11/2026):
- art. 155 c.p.c.: mesi a calendario comune, proroga del termine che scade di sabato o festivo;
- art. 327 c.p.c.: sei mesi dalla pubblicazione della sentenza;
- art. 1 L. 742/1969: «Ove il decorso abbia inizio durante il periodo di sospensione, l'inizio stesso è differito
  alla fine di detto periodo» (Cass. SS.UU. n. 21197/2009);
- art. 3 L. 742/1969: nessuna sospensione nelle controversie di lavoro e previdenza;
- art. 189 c.p.c. (D.Lgs. 149/2022): comparse conclusionali e repliche non oltre 30 e 15 giorni prima dell'udienza;
  art. 190 c.p.c. abrogato.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from pct.redazione_normativa import riferimenti_per_modello
from pct.scadenziario import (
    PRESET_TERMINI,
    GestioneScadenziario,
    calcola_termine,
    profilo_da_preset,
    riepilogo_operativo_scadenza,
)
from pct.termine_lungo_sentenza import scadenza_termine_lungo
from pct.termini_materia import NOTA_LAVORO, fascicolo_di_lavoro, lavoro_da_richiesta, profilo_per_materia
from pct.termini_mesi import decorrenza_differita, scadenza_a_mesi


def _tre_motori(deposito: date, *, lavoro: bool) -> set[str]:
    profilo = profilo_per_materia(profilo_da_preset("appello_lungo"), lavoro=lavoro)
    return {
        scadenza_termine_lungo(deposito, lavoro=lavoro)["deadline"],
        calcola_termine(deposito, mesi=6, sospensione_feriale=not lavoro).isoformat(),
        GestioneScadenziario.calcola_avanzata(start_at=deposito, profile=profilo).legal_due_at[:10],
    }


@pytest.mark.parametrize(
    ("deposito", "attesa"),
    [
        # Prima di agosto: 31/01/2027 + 31 giorni di agosto -> 03/03/2027.
        (date(2026, 7, 31), "2027-03-03"),
        # Durante agosto: decorrenza al 31/08, sei mesi 28/02/2027 domenica -> 01/03/2027 (caso della scheda).
        (date(2026, 8, 1), "2027-03-01"),
        (date(2026, 8, 10), "2027-03-01"),
        (date(2026, 8, 15), "2027-03-01"),
        (date(2026, 8, 31), "2027-03-01"),
        # Dopo agosto: 01/03/2027 lunedì, nessuna sospensione attraversata.
        (date(2026, 9, 1), "2027-03-01"),
        # Scadenza grezza in agosto: 15/08 + 31 giorni sospesi -> 15/09/2026.
        (date(2026, 2, 15), "2026-09-15"),
        # Fine anno: 15/12/2026 -> 15/06/2027, nessun agosto.
        (date(2026, 12, 15), "2027-06-15"),
        # Non lavoro, sentenza del 15/06/2026: 15/12/2026 + 31 -> 15/01/2027 (prova reale della scheda).
        (date(2026, 6, 15), "2027-01-15"),
    ],
)
def test_termine_lungo_con_sospensione_feriale(deposito, attesa):
    assert _tre_motori(deposito, lavoro=False) == {attesa}


@pytest.mark.parametrize(
    ("deposito", "attesa"),
    [
        # RG 3001/2025 (lavoro): 01/01/2027 festivo -> 02/01 sabato -> 04/01/2027.
        (date(2026, 7, 1), "2027-01-04"),
        # Deposito in agosto senza differimento (art. 3 L. 742/1969): 10/02/2027.
        (date(2026, 8, 10), "2027-02-10"),
        # 31/08 + 6 mesi = 28/02/2027 domenica -> 01/03/2027.
        (date(2026, 8, 31), "2027-03-01"),
        # Scadenza nel mese di agosto: 15/08/2026 Ferragosto -> 16 domenica -> 17/08/2026.
        (date(2026, 2, 15), "2026-08-17"),
    ],
)
def test_termine_lungo_lavoro_senza_sospensione(deposito, attesa):
    assert _tre_motori(deposito, lavoro=True) == {attesa}


def test_decorrenza_differita_alla_fine_di_agosto():
    assert decorrenza_differita(date(2026, 8, 10)) == date(2026, 8, 31)
    assert decorrenza_differita(date(2026, 7, 31)) == date(2026, 7, 31)
    esito = scadenza_a_mesi(date(2026, 8, 10), 6, sospensione=True)
    assert (esito.decorrenza, esito.base, esito.giorni_sospesi, esito.differita) == (
        date(2026, 8, 31), date(2027, 2, 28), 0, True)


def test_termine_annuale_attraversa_il_secondo_agosto():
    # Decorrenza 31/08/2026, un anno 31/08/2027, più i 31 giorni dell'agosto 2027 -> 01/10/2027.
    assert calcola_termine(date(2026, 8, 10), anni=1) == date(2027, 10, 1)


def test_motore_spiegabile_registra_il_differimento():
    esito = scadenza_termine_lungo(date(2026, 8, 10), lavoro=False)
    codici = [passo["code"] for passo in esito["steps"]]
    assert "ferial_start_deferred" in codici
    assert esito["rawDeadline"] == "2027-02-28"


def test_traccia_del_preset_indica_il_differimento():
    esito = GestioneScadenziario.calcola_avanzata(start_at=date(2026, 8, 10), profile=profilo_da_preset("appello_lungo"))
    assert any("differita" in riga for riga in esito.trace)


def test_termini_a_giorni_attraverso_il_capodanno():
    assert calcola_termine(date(2026, 12, 20), giorni=30) == date(2027, 1, 19)


# ---- Materia lavoro nei preset (art. 3 L. 742/1969) ----

def test_preset_appello_breve_lavoro_senza_agosto():
    profilo = profilo_per_materia(profilo_da_preset("appello_breve"), lavoro=True)
    assert GestioneScadenziario.calcola_avanzata(start_at=date(2026, 7, 15), profile=profilo).legal_due_at[:10] == "2026-08-14"
    generale = GestioneScadenziario.calcola_avanzata(start_at=date(2026, 7, 15), profile=profilo_da_preset("appello_breve"))
    assert generale.legal_due_at[:10] == "2026-09-14"


def test_preset_cassazione_lavoro_senza_agosto():
    profilo = profilo_per_materia(profilo_da_preset("cassazione_lungo"), lavoro=True)
    assert GestioneScadenziario.calcola_avanzata(start_at=date(2026, 7, 1), profile=profilo).legal_due_at[:10] == "2027-01-04"


def test_fascicolo_di_lavoro():
    assert fascicolo_di_lavoro(SimpleNamespace(tipo=SimpleNamespace(value="LAVORO"), sezione=""))
    assert fascicolo_di_lavoro(SimpleNamespace(tipo="CIVILE", sezione="Sezione Lavoro"))
    assert fascicolo_di_lavoro(SimpleNamespace(tipo="CIVILE", sezione="lavoro, previdenza ed assistenza obbligatoria"))
    assert not fascicolo_di_lavoro(SimpleNamespace(tipo="CIVILE", sezione="SEZIONE PRIMA", oggetto="infortunio sul lavoro"))
    assert not fascicolo_di_lavoro(None)


def test_lavoro_da_richiesta():
    fascicoli = {"F1": SimpleNamespace(tipo="LAVORO", sezione=""), "F2": SimpleNamespace(tipo="CIVILE", sezione="")}
    assert lavoro_da_richiesta({"id_fascicolo": "F1"}, fascicoli.get)
    assert not lavoro_da_richiesta({"id_fascicolo": "F2"}, fascicoli.get)
    assert not lavoro_da_richiesta({}, fascicoli.get)
    assert lavoro_da_richiesta({"materia_lavoro": "1", "id_fascicolo": "F2"}, fascicoli.get)

    def guasto(_id):
        raise RuntimeError("archivio non leggibile")

    assert not lavoro_da_richiesta({"id_fascicolo": "F1"}, guasto)


def test_riepilogo_non_dice_sospensione_applicata_nel_lavoro():
    voci = riepilogo_operativo_scadenza(trace=[NOTA_LAVORO, "Scadenza base a calendario comune -> 2027-01-01T00:00:00"])
    assert NOTA_LAVORO in voci
    assert "Il calcolo ha intercettato la sospensione feriale dei termini." not in voci


def test_nuova_da_preset_lavoro(tmp_path):
    gestione = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    scadenza = gestione.nuova_da_preset("appello_lungo", "Appello RG 3001/2025", "2026-07-01", materia_lavoro=True)
    assert scadenza.data_scadenza == "2027-01-04"


# ---- Art. 189 c.p.c.: conclusionali e repliche a ritroso ----

def test_preset_conclusionale_e_replica_prima_dell_udienza():
    conclusionale = GestioneScadenziario.calcola_avanzata(start_at=date(2026, 11, 10), profile=profilo_da_preset("comparsa_conclusionale"))
    replica = GestioneScadenziario.calcola_avanzata(start_at=date(2026, 11, 10), profile=profilo_da_preset("memoria_replica"))
    # 30 giorni prima del 10/11/2026: 11/10 domenica e 10/10 sabato -> 09/10/2026.
    assert conclusionale.legal_due_at[:10] == "2026-10-09"
    # 15 giorni prima: a giorni pieni 26/10 lunedì; prudenziale a giorni liberi 25/10 domenica -> 23/10/2026.
    assert replica.legal_due_at[:10] == "2026-10-23"
    assert replica.scadenza_di_legge[:10] == "2026-10-26"
    assert "189" in PRESET_TERMINI["comparsa_conclusionale"]["descrizione"]
    assert "190" not in PRESET_TERMINI["comparsa_conclusionale"]["descrizione"]


def test_conclusionale_salta_agosto_a_ritroso():
    esito = GestioneScadenziario.calcola_avanzata(start_at=date(2026, 9, 20), profile=profilo_da_preset("comparsa_conclusionale"))
    assert esito.legal_due_at[:10] == "2026-07-20"
    assert esito.scadenza_di_legge[:10] == "2026-07-21"


def test_preset_art_190_solo_rito_previgente():
    for chiave in ("comparsa_conclusionale_190", "memoria_replica_190"):
        assert "rito previgente" in PRESET_TERMINI[chiave]["label"]
        assert "abrogato" in PRESET_TERMINI[chiave]["descrizione"]


def test_riferimento_cpc_190_segnalato_abrogato(tmp_path):
    registro = str(tmp_path / "riferimenti.json")
    vigenti = riferimenti_per_modello("CIV_CONCL_001", db_path=registro)
    articoli = {riga["articolo"] for riga in vigenti["processuali"]}
    assert "189" in articoli and "190" not in articoli
    previgente = riferimenti_per_modello("CIV_CONCL_001", condizioni={"rito_previgente": True}, db_path=registro)
    riga_190 = next(riga for riga in previgente["processuali"] if riga["articolo"] == "190")
    assert "abrogat" in riga_190["rubrica"].lower()
    assert riga_190["valid_to"] == "2023-02-28"


def test_tipo_liberi_esclude_il_giorno_finale():
    assert calcola_termine(date(2026, 1, 12), giorni=120, tipo="continui") == date(2026, 5, 12)
    assert calcola_termine(date(2026, 1, 12), giorni=120, tipo="liberi") == date(2026, 5, 13)
    # Giorno finale libero che cade in agosto: si salta il periodo sospeso.
    assert calcola_termine(date(2026, 7, 1), giorni=30, tipo="liberi") == date(2026, 9, 1)


def test_route_calcola_termine_preset_lavoro(tmp_path):
    """RG 3001/2025 (lavoro): il preset «Appello (termine lungo)» dà 04/01/2027, non 01/02/2027."""
    from pct.auth import GestioneUtenti
    from tests.test_scadenziario import _cfg_web
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    GestioneUtenti(db_path=cfg["AUTH_DB"], audit_path=cfg["AUDIT_DB"], secret_key="test", bootstrap_admin_password="admin")
    client = create_app(cfg).test_client()
    assert client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True).status_code == 200

    lavoro = client.post("/scadenziario/calcola-termine", json={
        "preset": "appello_lungo", "source_event_at": "2026-07-01", "materia_lavoro": "1"}).get_json()
    assert lavoro["data_scadenza"] == "2027-01-04"
    assert lavoro["materia_lavoro"] is True
    assert NOTA_LAVORO in lavoro["operational_notes"]

    civile = client.post("/scadenziario/calcola-termine", json={
        "preset": "appello_lungo", "source_event_at": "2026-07-01"}).get_json()
    assert civile["data_scadenza"] == "2027-02-01"
    assert civile["materia_lavoro"] is False
