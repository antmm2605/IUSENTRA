"""Riconvalida: ciò che è già registrato torna alle regole di oggi.

L'OCR aveva letto «l. 69/2023» come una data e il registro ne aveva fatto
un'anomalia aperta e un fatto plausibile. La regola sui riferimenti normativi
ha cambiato quel giudizio: senza riconvalida l'avvocato continuerebbe a vedere
conferme che il software oggi non chiederebbe.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pct.archivio_letture.presidi import da_confermare_ora
from pct.registro_letture import Fatto, Oggetto, RegistroLetture
from pct.registro_letture.modello import Anomalia
from pct.registro_letture.riconvalida import anomalie_superate, regola_superata

T = "studio-prova"
OGGI = date(2026, 9, 15)
CONTESTO = {"oggi": OGGI, "anno_riferimento": 2026, "data_minima": None}


def _registro(tmp_path: Path) -> RegistroLetture:
    return RegistroLetture(tmp_path / "intelligence" / "registro_letture.db")


def _oggetto() -> Oggetto:
    return Oggetto(tipo="documento", oggetto_id="d1", nome="ricorso.pdf", sha256="a" * 64, sha256_archivio="e" * 64, dimensione=10)


def _anomalia(valore: str, *, campo: str = "data", codice: str = "corretta_da_ocr") -> Anomalia:
    return Anomalia(
        id="ano-1", tipo="documento", oggetto_id="d1", sha256="a" * 64, lettore="indice_documentale",
        campo=campo, valore_letto=valore, valore_proposto="", contesto=f"ai sensi della {valore}",
        motivo="Dato da verificare.", codice=codice, gravita="bassa",
    )


def test_un_riferimento_normativo_registrato_come_data_e_una_regola_superata():
    motivo = regola_superata(_anomalia("l. 69/2023"), contesto=CONTESTO)
    assert "riferimento normativo" in motivo
    assert "l. 69/2023" in motivo


def test_una_data_impossibile_resta_aperta():
    assert regola_superata(_anomalia("31/02/2026", campo="udienza", codice="giorno_inesistente"), contesto=CONTESTO) == ""


def test_una_decisione_dell_avvocato_non_si_riapre_ne_si_richiude():
    decisa = _anomalia("l. 22/2020")
    decisa.stato = "corretta"
    assert regola_superata(decisa, contesto=CONTESTO) == ""


def test_le_anomalie_superate_si_chiudono_da_sole_lasciando_traccia(tmp_path: Path):
    registro = _registro(tmp_path)
    oggetto = _oggetto()
    registro.registra_inventario(T, "F1", [oggetto])
    registro.registra_anomalie(T, "F1", oggetto, "indice_documentale", [
        {"campo": "data", "valore_letto": "l. 69/2023", "contesto": "ai sensi della l. 69/2023", "motivo": "L'OCR ha letto «l. 69/2023».", "codice": "corretta_da_ocr", "gravita": "bassa"},
        {"campo": "udienza", "valore_letto": "31/02/2026", "contesto": "udienza del 31/02/2026", "motivo": "Non esiste nel calendario.", "codice": "giorno_inesistente", "gravita": "alta"},
    ])
    assert len(registro.anomalie(T, "F1", stato="aperta")) == 2

    chiuse = registro.chiudi_anomalie_superate(T, "F1", contesto=CONTESTO)

    assert [anomalia.valore_letto for anomalia in chiuse] == ["l. 69/2023"]
    assert chiuse[0].risolta_da == "riconvalida automatica"
    assert "riferimento normativo" in chiuse[0].motivo
    aperte = registro.anomalie(T, "F1", stato="aperta")
    assert [anomalia.valore_letto for anomalia in aperte] == ["31/02/2026"]
    # La riga resta nel registro: la chiusura è tracciata, non cancellata.
    assert len(registro.anomalie(T, "F1")) == 2
    assert registro.chiudi_anomalie_superate(T, "F1", contesto=CONTESTO) == []


def test_i_fatti_gia_registrati_tornano_alle_regole_di_oggi(tmp_path: Path):
    registro = _registro(tmp_path)
    oggetto = _oggetto()
    registro.registra_inventario(T, "F1", [oggetto])
    registro.registra_fatti(T, "F1", oggetto, "documenti", [
        Fatto(categoria="data", campo="udienza", valore="2023-06-01", valore_letto="l. 69/2023", etichetta="Udienza", contesto="ai sensi della l. 69/2023", verifica="plausibile"),
        Fatto(categoria="data", campo="udienza", valore="2026-11-10", valore_letto="10/11/2026", etichetta="Udienza", contesto="udienza del 10/11/2026", verifica="plausibile"),
    ])

    respinti = registro.riconvalida_fatti(T, "F1")

    assert [fatto.valore_letto for fatto in respinti] == ["l. 69/2023"]
    assert respinti[0].verifica == "respinta"
    assert any(prova.get("codice") == "riconvalida" for prova in respinti[0].prove)
    restanti = registro.fatti(T, "F1")
    assert [fatto.valore_letto for fatto in restanti] == ["10/11/2026"]
    assert registro.riconvalida_fatti(T, "F1") == []


def test_una_decisione_sul_fatto_non_viene_riscritta_dalla_riconvalida(tmp_path: Path):
    registro = _registro(tmp_path)
    oggetto = _oggetto()
    registro.registra_inventario(T, "F1", [oggetto])
    registro.registra_fatti(T, "F1", oggetto, "documenti", [
        Fatto(categoria="data", campo="udienza", valore="2023-06-01", valore_letto="l. 69/2023", etichetta="Udienza", contesto="ai sensi della l. 69/2023", verifica="plausibile"),
    ])
    fatto = registro.fatti(T, "F1")[0]
    registro.decidi_fatto(T, fatto.id, verifica="corretta", valore="2026-06-01", utente_id="avv")

    assert registro.riconvalida_fatti(T, "F1") == []
    assert registro.fatti(T, "F1")[0].verifica == "corretta"


def test_anomalie_superate_elenca_solo_le_aperte():
    aperta = _anomalia("l. 5/2026")
    decisa = _anomalia("l. 12/2026")
    decisa.stato = "ignorata"
    superate = anomalie_superate([aperta, decisa], contesto=CONTESTO)
    assert [anomalia.valore_letto for anomalia, _motivo in superate] == ["l. 5/2026"]


# ── Conferme mirate ─────────────────────────────────────────────────────────

def _data(campo: str, valore: str, *, verifica: str = "plausibile") -> Fatto:
    return Fatto(categoria="data", campo=campo, valore=valore, valore_letto=valore, etichetta=campo.capitalize(), contesto=f"{campo} del {valore}", verifica=verifica, id=f"{campo}-{valore}")


def test_si_chiedono_solo_le_date_che_cambiano_agenda_o_scadenziario():
    fatti = [
        _data("udienza", "2026-11-10"),
        _data("termine", "2026-10-05"),
        _data("udienza", "2026-03-02"),
        _data("data_atto", "2026-11-20"),
        _data("notifica", "2026-12-01"),
        _data("udienza", "2026-12-15", verifica="verificata"),
    ]
    richieste = da_confermare_ora(fatti, oggi=OGGI)
    assert [voce["valore"] for voce in richieste] == ["2026-10-05", "2026-11-10"]


def test_una_data_gia_passata_non_si_chiede():
    assert da_confermare_ora([_data("udienza", "2026-09-14")], oggi=OGGI) == []
    assert [voce["valore"] for voce in da_confermare_ora([_data("udienza", "2026-09-15")], oggi=OGGI)] == ["2026-09-15"]


def test_la_stessa_data_non_si_chiede_due_volte():
    doppia = [_data("udienza", "2026-11-10"), _data("udienza", "2026-11-10")]
    assert len(da_confermare_ora(doppia, oggi=OGGI)) == 1
