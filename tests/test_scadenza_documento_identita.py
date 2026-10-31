"""Scadenza del documento d'identità: preavviso a 60/30 giorni, una sola data, nessuna eccezione."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from pct.clienti import DocumentoIdentita
from pct.scadenza_documento_identita import proponi_rinnovi, scadenza_unica, stato_documento
from pct.scadenziario import GestioneScadenziario
from web.services import notifications_runtime

OGGI = date(2026, 10, 31)


@pytest.mark.parametrize("scadenza, stato", [
    ("", "non_indicata"),
    ("31/12/2026", "data_non_valida"),
    ("2026-02-30", "data_non_valida"),
    ("2026-10-30", "scaduto"),
    ("2026-11-20", "in_scadenza_30"),
    ("2026-12-20", "in_scadenza_60"),
    ("2027-06-01", "valido"),
])
def test_stato_documento(scadenza, stato):
    esito = stato_documento(scadenza, OGGI)
    assert esito["stato"] == stato
    assert bool(esito["messaggio"]) is (stato != "valido")


def test_documento_scaduto_non_solleva_su_data_malformata():
    assert DocumentoIdentita(data_scadenza="31/12/2026").scaduto is False
    assert DocumentoIdentita(data_scadenza="2000-01-01").scaduto is True
    assert DocumentoIdentita().scaduto is False


def test_scadenza_unica():
    assert scadenza_unica("2027-01-01", "")["fonte"] == "scheda cliente"
    assert scadenza_unica("", "2027-01-01") == {"scadenza": "2027-01-01", "fonte": "scheda antiriciclaggio", "avviso": ""}
    assert "allinea" in scadenza_unica("2027-01-01", "2027-02-01")["avviso"]
    assert scadenza_unica("", "")["fonte"] == ""


def _cliente(cid, scadenza, stato="ATTIVO"):
    return SimpleNamespace(id=cid, nome_completo=f"Cliente {cid}", stato=SimpleNamespace(value=stato),
                           documento=SimpleNamespace(data_scadenza=scadenza))


def test_proponi_rinnovi_senza_doppioni(tmp_path):
    scadenziario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    clienti = [_cliente("A", "2026-12-20"), _cliente("B", "2027-06-01"), _cliente("C", "31/12/2026"),
               _cliente("D", "2026-11-10", stato="ARCHIVIATO"), _cliente("E", "2026-10-01")]
    assert proponi_rinnovi(clienti, scadenziario, oggi=OGGI) == {"proposte": 1, "date_non_valide": 1}
    (voce,) = scadenziario.tutte(solo_aperte=False)
    assert voce.data_scadenza == "2026-12-20" and "DOC_IDENTITA:A:2026-12-20" in voce.note
    assert proponi_rinnovi(clienti, scadenziario, oggi=OGGI)["proposte"] == 0


def test_giro_notifiche_rinnovi(tmp_path, monkeypatch):
    scadenziario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    assert notifications_runtime._proponi_rinnovi_documenti({}, None, scadenziario, OGGI) == {"proposte": 0, "date_non_valide": 0}
    import pct.clienti as clienti_mod

    monkeypatch.setattr(clienti_mod.GestioneClienti, "tutti", lambda self, *a, **k: [_cliente("A", "2026-12-20")])
    paths = {"CLIENTI_DB": str(tmp_path / "clienti" / "anagrafica.json")}
    assert notifications_runtime._proponi_rinnovi_documenti(paths, None, scadenziario, OGGI)["proposte"] == 1

    def guasto(self, *a, **k):
        raise RuntimeError("archivio")

    monkeypatch.setattr(clienti_mod.GestioneClienti, "tutti", guasto)
    assert "errore" in notifications_runtime._proponi_rinnovi_documenti(paths, None, scadenziario, OGGI)
