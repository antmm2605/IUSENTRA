"""V31: la scheda del fascicolo non mostra appuntamenti di altri procedimenti (RG 538/2026, 31/10/2026)."""

from __future__ import annotations

from types import SimpleNamespace

from web.services.react_fascicoli_bridge import _agenda_for_fascicolo


def _app(id_, **campi):
    base = dict(id=id_, titolo="", note="", procedimento="", cliente="", tribunale="", external_source_url="",
                external_profile_id="", external_uid="", id_fascicolo="", data_ora="2026-10-01T09:00:00", stato="PROGRAMMATO")
    base.update(campi)
    return SimpleNamespace(**base)


def test_solo_il_ruolo_completo_del_fascicolo_e_le_voci_collegate():
    fascicolo = SimpleNamespace(id="1F244953", numero_rg="538", anno_rg="2026", rg="538/2026",
                                source_external_id="", source_snapshot=None)
    voci = [
        _app("altro-anno", titolo="Udienza del 20/04/2023", procedimento="RG 538/2024"),
        _app("hash-pec", titolo="PEC ricevuta: annotazione - RG 1814/2024", procedimento="RG 1814/2024",
             external_uid="PEC_RICEZIONE:pec_7597a50ec12804242eb3d2c41ae66649575d25fc6f2892ded642ab0ae0538bf5"),
        _app("numero-nel-testo", titolo="Termine note - RG 901/2026", note="protocollo 538 del registro"),
        _app("giusta", titolo="Deposito note scritte - 15/09/2026 - RG 538/2026", procedimento="RG 538/2026"),
        _app("collegata", titolo="Udienza", id_fascicolo="1F244953", procedimento="RG 538/2024"),
        _app("altro-fascicolo", titolo="Udienza RG 538/2026", id_fascicolo="ZZZ"),
    ]
    agenda = SimpleNamespace(tutti=lambda: voci)
    assert {a.id for a in _agenda_for_fascicolo(lambda: agenda, fascicolo)} == {"giusta", "collegata"}


def test_agenda_del_fascicolo_prima_i_prossimi_poi_i_passati_in_tono_neutro(monkeypatch):
    """V34: promemoria PEC del 2024 e udienze del 2023 non restano in testa né «da attenzionare»."""
    from datetime import date
    from types import SimpleNamespace

    from web.services import react_fascicoli_bridge as bridge

    monkeypatch.setattr(bridge, "oggi_rome", lambda: date(2026, 10, 31))
    voci = bridge._appointments([
        SimpleNamespace(id="A", titolo="Udienza del 20/04/2023", data_ora="2023-04-20T09:00:00", tipo="UDIENZA"),
        SimpleNamespace(id="B", titolo="Classifica PEC e conferma adempimenti", data_ora="2024-06-04T09:00:00+02:00", tipo="SCADENZA"),
        SimpleNamespace(id="C", titolo="Udienza di discussione", data_ora="2026-11-24T09:30:00", tipo="UDIENZA"),
        SimpleNamespace(id="D", titolo="Termine note", data_ora="2026-11-01T09:00:00", tipo="SCADENZA"),
    ])
    assert [voce["id"] for voce in voci] == ["D", "C", "B", "A"]
    assert [voce["tone"] for voce in voci] == ["warning", "primary", "neutral", "neutral"]
    assert [voce["past"] for voce in voci] == [False, False, True, True]
