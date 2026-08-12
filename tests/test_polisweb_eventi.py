"""Lettura eventi/scadenze dai registri e proposte in BOZZA (Fase 1 sync Polisweb).

Verifica il parsing delle classi QBuilder InfoScadenze/EventoFascicoloAgenda,
la normalizzazione/dedup, la selezione dei candidati futuri (con esclusione
delle date gia' presenti — incluse quelle create dalla PEC) e la creazione di
proposte in stato BOZZA idempotenti nel ciclo di sincronizzazione.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from pct.polisweb_eventi import (
    EventoRegistro,
    evento_da_agenda,
    evento_da_info_scadenza,
    normalizza_eventi,
)
from pct.scadenze_proposte_polisweb import (
    bozza_marker,
    bozza_scadenza_fields,
    select_event_candidates,
)
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from web.services import polisweb_fascicolo_sync as sync_module

FUTURO = (date.today() + timedelta(days=20)).isoformat()
FUTURO_2 = (date.today() + timedelta(days=35)).isoformat()
PASSATO = (date.today() - timedelta(days=10)).isoformat()


# --- Parsing e normalizzazione ---------------------------------------------------


def test_info_scadenza_distingue_udienza_da_scadenza():
    udienza = evento_da_info_scadenza({"tipoScadenza": "Udienza di comparizione", "dataScadenza": FUTURO, "descScadenza": "Prima udienza"})
    scadenza = evento_da_info_scadenza({"tipoScadenza": "Termine", "dataScadenza": FUTURO, "descScadenza": "Memoria 183"})

    assert udienza.tipo == "udienza"
    assert scadenza.tipo == "scadenza"
    assert udienza.data == FUTURO
    assert scadenza.descrizione == "Memoria 183"


def test_info_scadenza_senza_data_scartata():
    assert evento_da_info_scadenza({"tipoScadenza": "Udienza", "descScadenza": "senza data"}) is None


def test_evento_agenda_mappa_storico():
    evento = evento_da_agenda({"tipo": "DEPOSITO", "desc": "Deposito comparsa", "data": PASSATO, "idDocumento": "77"})
    assert evento.tipo == "evento"
    assert evento.fonte_classe == "EventoFascicoloAgenda"
    assert evento.id_documento == "77"


def test_normalizza_deduplica_e_ordina():
    righe = [
        {"tipoScadenza": "Termine", "dataScadenza": FUTURO_2, "descScadenza": "Note conclusionali"},
        {"tipoScadenza": "Udienza", "dataScadenza": FUTURO, "descScadenza": "Udienza"},
        {"tipoScadenza": "Udienza", "dataScadenza": FUTURO, "descScadenza": "Udienza"},  # duplicato
    ]
    eventi = normalizza_eventi(righe)
    assert len(eventi) == 2
    assert eventi[0].tipo == "udienza"  # udienza prima
    assert eventi[1].tipo == "scadenza"


# --- Selezione candidati ---------------------------------------------------------


def _ev(tipo: str, data: str, desc: str = "x") -> EventoRegistro:
    return EventoRegistro(tipo=tipo, descrizione=desc, data=data, fonte_classe="InfoScadenze")


def test_select_event_candidates_esclude_passato_eventi_storici_e_date_note():
    candidati = select_event_candidates(
        [_ev("udienza", FUTURO), _ev("scadenza", FUTURO_2), _ev("udienza", PASSATO), _ev("evento", FUTURO), _ev("scadenza", FUTURO)],
        today=date.today(),
        date_gia_presenti={FUTURO},  # gia' coperta (es. da PEC)
    )
    date_candidati = sorted(e.data for e in candidati)
    assert date_candidati == [FUTURO_2]


def test_bozza_marker_stabile():
    ev = _ev("udienza", FUTURO, "Prima udienza")
    m1 = bozza_marker("F1", "0580010", "100/2026", ev.chiave())
    m2 = bozza_marker("F1", "0580010", "100/2026", ev.chiave())
    assert m1 == m2
    assert m1.startswith("POLISWEB:F1")


def test_bozza_fields_porta_snippet_e_fonte_registro():
    ev = _ev("udienza", FUTURO, "Udienza di trattazione")
    fields = bozza_scadenza_fields(ev, fascicolo_id="F1", ufficio="0580010", rg="100/2026")
    assert fields["deadline_profile_code"] == "PST_PROPOSTA_EVENTO"
    assert fields["source_event_type"] == "polisweb_registro"
    assert fields["source_snippet"] == "Udienza di trattazione"
    assert "Registro di cancelleria" in fields["source_document_name"]
    assert fields["data_scadenza"] == FUTURO


# --- Ciclo di sincronizzazione ---------------------------------------------------


class _FakeFascicoliManager:
    def __init__(self, fascicolo):
        self._fascicolo = fascicolo

    def get(self, _id):
        return self._fascicolo

    def aggiorna(self, _id, **campi):
        for key, value in campi.items():
            setattr(self._fascicolo, key, value)
        return self._fascicolo


class _FakeClient:
    def __init__(self, eventi):
        self._eventi = eventi

    def ricerca_fascicoli(self, ufficio, **kwargs):
        return [SimpleNamespace(numero_rg="100", anno_rg=2026)]

    def sincronizza_fascicolo_esistente(self, pw, locale, gestione_fascicoli, clienti, **kwargs):
        return SimpleNamespace(successo=True, messaggio="Sincronizzato.", avvisi=[], depositi_importati=0, documenti_importati=0)

    def consulta_scadenze(self, ufficio, numero_rg, anno_rg, **kwargs):
        return self._eventi


def _fascicolo():
    return SimpleNamespace(
        id="F1", numero_rg="100", anno_rg=2026, codice_ufficio_portale="0580010",
        tribunale="MILANO", tipo_registro="", registro_portale="", servizio_pst="",
        ruolo_polisweb="AVV", sub_procedimento="", id_dfa="", last_sync_at="", sync_status="",
    )


def test_sync_crea_proposte_bozza_idempotenti(tmp_path, monkeypatch):
    eventi = [_ev("udienza", FUTURO, "Prima udienza"), _ev("scadenza", FUTURO_2, "Note conclusionali")]
    manager_fasc = _FakeFascicoliManager(_fascicolo())
    scadenziario = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    monkeypatch.setattr(sync_module, "crea_client", lambda demo=False: _FakeClient(eventi))

    esito1 = sync_module.sincronizza_fascicolo_da_registro(
        "F1",
        get_fascicoli=lambda: manager_fasc,
        get_clienti=lambda: None,
        get_scadenziario=lambda: scadenziario,
        auth_mode="reale",
        avvocato_referente="avv.rossi",
    )
    esito2 = sync_module.sincronizza_fascicolo_da_registro(
        "F1",
        get_fascicoli=lambda: manager_fasc,
        get_clienti=lambda: None,
        get_scadenziario=lambda: scadenziario,
        auth_mode="reale",
        avvocato_referente="avv.rossi",
    )

    assert esito1["ok"] is True
    assert esito1["proposte_scadenze"] == 2
    assert esito2["proposte_scadenze"] == 0  # idempotente
    bozze = scadenziario.bozze()
    assert len(bozze) == 2
    assert {b.tipo for b in bozze} == {TipoTermine.UDIENZA, TipoTermine.ADEMPIMENTO}
    assert all(b.stato == StatoTermine.BOZZA for b in bozze)
    # nessuna proposta finisce tra le operative
    assert not scadenziario.tutte(solo_aperte=True)


def test_sync_non_duplica_date_gia_presenti_da_pec(tmp_path, monkeypatch):
    scadenziario = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    # scadenza gia' creata dalla PEC sulla stessa data dell'udienza del registro
    scadenziario.nuova(
        titolo="Udienza da PEC",
        tipo=TipoTermine.UDIENZA,
        data_scadenza=FUTURO,
        id_fascicolo="F1",
    )
    manager_fasc = _FakeFascicoliManager(_fascicolo())
    monkeypatch.setattr(sync_module, "crea_client", lambda demo=False: _FakeClient([_ev("udienza", FUTURO, "Udienza")]))

    esito = sync_module.sincronizza_fascicolo_da_registro(
        "F1",
        get_fascicoli=lambda: manager_fasc,
        get_clienti=lambda: None,
        get_scadenziario=lambda: scadenziario,
        auth_mode="reale",
    )

    assert esito["proposte_scadenze"] == 0
    assert not scadenziario.bozze()
