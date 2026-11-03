"""Panoramica e Statistiche contano le scadenze «aperte» come lo Scadenziario (regola V28).

Riverifica a vista del 03/11/2026 (STU-04): Panoramica e Statistiche mostravano 87 scadenze
aperte, lo Scadenziario 79, perché le prime contavano anche gli adempimenti scaduti e le
udienze passate (esito da registrare), che lo Scadenziario tiene fuori dalle «Aperte»
(`pct/scadenze_stato.py`).
"""
from datetime import date, timedelta
from types import SimpleNamespace

from pct.ora_italiana import oggi_roma
import web.blueprints.api_v1_react as api


def _voce(giorni: int, tipo: str = "DEPOSITO_MEMORIA", priorita: str = "CRITICA"):
    giorno: date = oggi_roma() + timedelta(days=giorni)
    return SimpleNamespace(stato="APERTO", tipo=tipo, priorita=priorita, data_scadenza=giorno.isoformat(), provenienza={})


class _Gestore:
    def __init__(self, voci):
        self._voci = voci

    def tutte(self, solo_aperte=True):
        return list(self._voci)


def test_distribuzione_panoramica_esclude_scadute_e_udienze_passate(monkeypatch):
    voci = [_voce(-3), _voce(-2, tipo="UDIENZA"), _voce(0), _voce(5, priorita="BASSA")]
    monkeypatch.setattr(api, "gestore_panoramica", lambda factory: _Gestore(voci))
    righe = api._deadline_distribution()
    assert sum(r["count"] for r in righe) == 2
    assert righe[0]["count"] == 1  # critiche: solo quella di oggi


def test_trattazione_scritta_con_vecchio_indicatore_remoto_non_e_audiovisiva():
    """Riverifica 03/11/2026 (STU-08): indicatore remoto acceso ma modalità «trattazione scritta»."""
    from web.services.topbar_operational import _remote_hearing_notification_payload

    scadenza = SimpleNamespace(
        remote_hearing_detected=True, remote_hearing_mode="trattazione scritta", hearing_mode="Trattazione scritta",
        remote_hearing_url="", remote_hearing_source="", remote_hearing_verified=False, remote_hearing_pdf_required=False,
    )
    assert _remote_hearing_notification_payload(scadenza) == {}
    remota = SimpleNamespace(remote_hearing_detected=True, remote_hearing_mode="", hearing_mode="")
    assert _remote_hearing_notification_payload(remota)["remoteHearingDetected"] is True


def test_deposito_note_con_profilo_opposizione_non_riceve_avviso_cinque_giorni():
    """Riverifica 03/11/2026 (STU-26): il titolo «Deposito note scritte» non è un'opposizione."""
    from pct.proposte_decorse import opposizione_127_ter_incoerente

    base = dict(deadline_profile_code="CIV_OPPOSIZIONE_127_TER", data_scadenza="2026-12-10", creata_il="2026-09-01T10:00:00")
    deposito = SimpleNamespace(titolo="Deposito note scritte ex art. 127-ter c.p.c. - 10/12/2026", **base)
    opposizione = SimpleNamespace(titolo="Opposizione alla trattazione scritta ex art. 127-ter c.p.c.", **base)
    assert opposizione_127_ter_incoerente(deposito) is False
    assert opposizione_127_ter_incoerente(opposizione) is True


def test_fascicoli_priorita_alta_ignorano_udienze_passate(monkeypatch):
    """Riverifica 03/11/2026 (STU-01): un'udienza passata critica non rende «URGENTE» il fascicolo."""
    udienza = _voce(-5, tipo="UDIENZA")
    udienza.id_fascicolo = "F1"
    scaduta = _voce(-2)
    scaduta.id_fascicolo = "F2"
    fascicoli = [SimpleNamespace(id="F1", rg_completo="RG 1/2026", titolo="A", tribunale="T"),
                 SimpleNamespace(id="F2", rg_completo="RG 2/2026", titolo="B", tribunale="T")]

    class _G:
        def __init__(self, voci):
            self.voci = voci

        def tutte(self, solo_aperte=True):
            return [udienza, scaduta]

        def tutti(self, archiviati=False):
            return fascicoli

    monkeypatch.setattr(api, "gestore_panoramica", lambda factory: _G(None))
    righe = api._high_priority_matters()
    assert [r["id"] for r in righe] == ["F2"]
