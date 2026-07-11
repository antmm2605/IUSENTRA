"""Test Fase 1 Lex Oggi: copertura tool Lex (scadute incluse, metadata, filtri).

Verifica che i tool agenda/scadenziario/fascicolo/preventivi non perdano
elementi importanti per limiti o filtri e che espongano i metadati di
copertura (returned_count/total_matching/truncated/coverage_complete).
"""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from pct.daily_plan.clock import Clock, ROME_TZ, system_clock
from zoneinfo import ZoneInfo


# ──────────────────────────────────────────────
# Clock
# ──────────────────────────────────────────────

def test_clock_data_fissa_per_test():
    clock = Clock(fixed_now=datetime(2026, 7, 10, 8, 30))
    assert clock.today() == date(2026, 7, 10)
    assert clock.now().tzinfo is not None
    assert clock.now().hour == 8


def test_clock_sistema_usa_europe_rome():
    clock = system_clock()
    assert str(clock.tz) == "Europe/Rome"
    assert clock.now().tzinfo is not None


def test_clock_mezzanotte_utc_resta_giorno_italiano():
    # 23:30 UTC del 9 luglio = 01:30 del 10 luglio a Roma (estate, UTC+2)
    utc_value = datetime(2026, 7, 9, 23, 30, tzinfo=ZoneInfo("UTC"))
    clock = Clock(fixed_now=utc_value)
    assert clock.today() == date(2026, 7, 10)
    assert clock.local_date_of(utc_value) == date(2026, 7, 10)


def test_clock_naive_interpretato_come_roma():
    clock = Clock(fixed_now=datetime(2026, 7, 10, 0, 15))
    assert clock.today() == date(2026, 7, 10)
    assert clock.now().tzinfo == ROME_TZ or clock.now().utcoffset() is not None


# ──────────────────────────────────────────────
# Scadenziario: arretrati inclusi + metadata
# ──────────────────────────────────────────────

def _scadenza(id_, giorni_da_oggi, stato="aperta", fascicolo=""):
    data = (date.today() + timedelta(days=giorni_da_oggi)).isoformat()
    return SimpleNamespace(
        id=id_,
        titolo=f"Scadenza {id_}",
        data_scadenza=data,
        stato=SimpleNamespace(value=stato),
        id_fascicolo=fascicolo,
        perentorio=False,
        id_utente_responsabile="",
    )


def test_scadenziario_tool_include_scadute_aperte(monkeypatch):
    from lex.tools import scadenziario_tool
    from lex.tools.scadenziario_tool import ScadenziarioTool

    class Store:
        def tutte(self):
            return [
                _scadenza("scaduta", -5),
                _scadenza("oggi", 0),
                _scadenza("futura", 7),
                _scadenza("oltre", 30),
            ]

    monkeypatch.setattr(scadenziario_tool, "_get_scadenziario_store", lambda: Store())

    result = ScadenziarioTool().run(giorni=14, solo_aperte=True)

    ids = [item["id"] for item in result["items"]]
    assert "scaduta" in ids, "le scadenze arretrate aperte non devono sparire"
    assert "oggi" in ids and "futura" in ids
    assert "oltre" not in ids
    # la scaduta viene prima (giorni_al_termine negativo)
    assert ids[0] == "scaduta"
    assert result["coverage_complete"] is True
    assert result["truncated"] is False
    assert result["total_matching"] == 3


def test_scadenziario_tool_esclusione_scadute_esplicita(monkeypatch):
    from lex.tools import scadenziario_tool
    from lex.tools.scadenziario_tool import ScadenziarioTool

    class Store:
        def tutte(self):
            return [_scadenza("scaduta", -3), _scadenza("futura", 3)]

    monkeypatch.setattr(scadenziario_tool, "_get_scadenziario_store", lambda: Store())

    result = ScadenziarioTool().run(giorni=14, include_scadute=False)
    ids = [item["id"] for item in result["items"]]
    assert ids == ["futura"]


def test_scadenziario_tool_limit_non_perde_le_piu_urgenti(monkeypatch):
    from lex.tools import scadenziario_tool
    from lex.tools.scadenziario_tool import ScadenziarioTool

    class Store:
        def tutte(self):
            # inserite in ordine inverso: l'urgente è l'ultima della lista
            return [_scadenza(f"s{i}", 14 - i) for i in range(10)]

    monkeypatch.setattr(scadenziario_tool, "_get_scadenziario_store", lambda: Store())

    result = ScadenziarioTool().run(giorni=14, limit=3)

    assert result["returned_count"] == 3
    assert result["total_matching"] == 10
    assert result["truncated"] is True
    assert result["coverage_complete"] is False
    # il limite non deve tagliare le scadenze più vicine
    giorni = [item["giorni_al_termine"] for item in result["items"]]
    assert giorni == sorted(giorni)
    assert giorni[0] == min(range(5, 15))


def test_scadenziario_tool_espone_perentorio_e_responsabile(monkeypatch):
    from lex.tools import scadenziario_tool
    from lex.tools.scadenziario_tool import ScadenziarioTool

    sc = _scadenza("s1", 2)
    sc.perentorio = True
    sc.id_utente_responsabile = "utente-9"

    class Store:
        def tutte(self):
            return [sc]

    monkeypatch.setattr(scadenziario_tool, "_get_scadenziario_store", lambda: Store())

    result = ScadenziarioTool().run()
    assert result["items"][0]["perentorio"] is True
    assert result["items"][0]["id_utente_responsabile"] == "utente-9"


def test_scadenziario_tool_store_non_disponibile(monkeypatch):
    from lex.tools import scadenziario_tool
    from lex.tools.scadenziario_tool import ScadenziarioTool

    monkeypatch.setattr(scadenziario_tool, "_get_scadenziario_store", lambda: None)

    result = ScadenziarioTool().run()
    assert result["error"] == "store_unavailable"
    assert result["coverage_complete"] is False


# ──────────────────────────────────────────────
# Agenda: campi completi + metadata
# ──────────────────────────────────────────────

def test_agenda_tool_espone_avvocato_durata_orari(monkeypatch):
    from lex.tools import agenda_tool
    from lex.tools.agenda_tool import AgendaTool

    inizio = f"{date.today().isoformat()}T09:00:00"

    class Store:
        def tutti(self):
            return [
                SimpleNamespace(
                    id="udienza-1",
                    titolo="Udienza Rossi",
                    data_ora=inizio,
                    durata_minuti=90,
                    avvocato="Avv. Bianchi",
                    reminder_minuti=60,
                    stato=SimpleNamespace(value="CONFERMATO"),
                    luogo="Tribunale di Milano",
                    procedimento="123/2026",
                    tribunale="Tribunale di Milano",
                    id_cliente="cli-1",
                )
            ]

    monkeypatch.setattr(agenda_tool, "_get_agenda_store", lambda: Store())

    result = AgendaTool().run(giorni=1)
    item = result["items"][0]
    assert item["avvocato"] == "Avv. Bianchi"
    assert item["durata_minuti"] == 90
    assert item["data_inizio"] == inizio
    assert item["data_fine"].endswith("10:30:00")
    assert item["reminder_minuti"] == 60
    assert item["stato"] == "CONFERMATO"
    assert item["tribunale"] == "Tribunale di Milano"
    assert item["id_cliente"] == "cli-1"
    assert result["coverage_complete"] is True


def test_agenda_tool_metadata_troncamento(monkeypatch):
    from lex.tools import agenda_tool
    from lex.tools.agenda_tool import AgendaTool

    class Store:
        def tutti(self):
            return [
                SimpleNamespace(
                    id=f"app-{i}",
                    titolo=f"Appuntamento {i}",
                    data_ora=f"{(date.today() + timedelta(days=i)).isoformat()}T10:00:00",
                )
                for i in range(8)
            ]

    monkeypatch.setattr(agenda_tool, "_get_agenda_store", lambda: Store())

    result = AgendaTool().run(giorni=30, limit=3)
    assert result["returned_count"] == 3
    assert result["total_matching"] == 8
    assert result["truncated"] is True
    assert result["coverage_complete"] is False


# ──────────────────────────────────────────────
# Fascicolo: filtri applicati + metadata
# ──────────────────────────────────────────────

class _FascicoliStore:
    def __init__(self, fascicoli):
        self._fascicoli = fascicoli

    def tutti(self, archiviati=False):
        if archiviati:
            return list(self._fascicoli)
        return [f for f in self._fascicoli if f.stato.value != "ARCHIVIATO"]


def _fascicolo(id_, stato="APERTO", referente="", dominus=""):
    return SimpleNamespace(
        id=id_,
        numero=f"2026/{id_}",
        titolo=f"Fascicolo {id_}",
        nome_cliente="Cliente Test",
        controparte="Controparte",
        oggetto="Oggetto",
        stato=SimpleNamespace(value=stato),
        avvocato_referente=referente,
        avvocato_dominus=dominus,
        documenti=[],
        attivita=[],
        depositi_pct=[],
    )


def test_fascicolo_tool_include_archiviati_applicato(monkeypatch):
    from lex.tools import fascicolo_tool
    from lex.tools.fascicolo_tool import FascicoloTool

    store = _FascicoliStore([_fascicolo("a"), _fascicolo("b", stato="ARCHIVIATO")])
    monkeypatch.setattr(fascicolo_tool, "_get_store", lambda: store)

    result = FascicoloTool().run(query="")
    assert [i["id"] for i in result["items"]] == ["a"]

    result = FascicoloTool().run(query="", include_archiviati=True)
    assert sorted(i["id"] for i in result["items"]) == ["a", "b"]


def test_fascicolo_tool_filtri_stato_e_avvocato(monkeypatch):
    from lex.tools import fascicolo_tool
    from lex.tools.fascicolo_tool import FascicoloTool

    store = _FascicoliStore(
        [
            _fascicolo("a", stato="APERTO", referente="Avv. Bianchi"),
            _fascicolo("b", stato="SOSPESO", referente="Avv. Verdi"),
            _fascicolo("c", stato="APERTO", dominus="Avv. Verdi"),
        ]
    )
    monkeypatch.setattr(fascicolo_tool, "_get_store", lambda: store)

    result = FascicoloTool().run(stato="APERTO")
    assert sorted(i["id"] for i in result["items"]) == ["a", "c"]

    result = FascicoloTool().run(avvocato="verdi")
    assert sorted(i["id"] for i in result["items"]) == ["b", "c"]
    assert result["items"][0]["avvocato_dominus"] in ("", "Avv. Verdi")


def test_fascicolo_tool_metadata_troncamento(monkeypatch):
    from lex.tools import fascicolo_tool
    from lex.tools.fascicolo_tool import FascicoloTool

    store = _FascicoliStore([_fascicolo(f"f{i}") for i in range(6)])
    monkeypatch.setattr(fascicolo_tool, "_get_store", lambda: store)

    result = FascicoloTool().run(limit=2)
    assert result["returned_count"] == 2
    assert result["total_matching"] == 6
    assert result["truncated"] is True
    assert result["coverage_complete"] is False


def test_fascicolo_tool_store_senza_kwargs_compatibile(monkeypatch):
    from lex.tools import fascicolo_tool
    from lex.tools.fascicolo_tool import FascicoloTool

    class LegacyStore:
        def tutti(self):
            return [_fascicolo("x")]

    monkeypatch.setattr(fascicolo_tool, "_get_store", lambda: LegacyStore())

    result = FascicoloTool().run(query="")
    assert [i["id"] for i in result["items"]] == ["x"]


# ──────────────────────────────────────────────
# Preventivi: tool reale, non stub
# ──────────────────────────────────────────────

class _PreventiviStore:
    def __init__(self, preventivi, conferimenti=()):
        self._preventivi = list(preventivi)
        self._conferimenti = list(conferimenti)

    def tutti_preventivi(self):
        return list(self._preventivi)

    def tutti_conferimenti(self):
        return list(self._conferimenti)


def _preventivo(id_, stato="BOZZA", cliente="cli-1", fascicolo=""):
    return SimpleNamespace(
        id=id_,
        numero=f"2026/{id_}",
        id_cliente=cliente,
        id_fascicolo=fascicolo,
        data_emissione="2026-07-01",
        data_scadenza="2026-07-31",
        oggetto=f"Preventivo {id_}",
        stato=SimpleNamespace(value=stato),
        totale=1234.56,
        versione=1,
        inviato_cliente_il=None,
        accettato_il=None,
    )


def test_preventivi_tool_non_e_uno_stub(monkeypatch):
    from lex.tools import preventivi_tool
    from lex.tools.preventivi_tool import PreventiviTool

    store = _PreventiviStore(
        [_preventivo("p1"), _preventivo("p2", stato="ACCETTATO", fascicolo="fasc-1")],
        [
            SimpleNamespace(
                id="c1",
                numero="2026/C1",
                id_preventivo="p2",
                id_cliente="cli-1",
                id_fascicolo="fasc-1",
                data_incarico="2026-07-02",
                oggetto="Incarico",
                stato=SimpleNamespace(value="ATTIVO"),
                firma_cliente_richiesta=True,
                firma_cliente_eseguita=False,
            )
        ],
    )
    monkeypatch.setattr(preventivi_tool, "_get_preventivi_store", lambda: store)

    result = PreventiviTool().run()
    assert result["total_matching"] == 2
    assert result["items"][0]["totale"] == 1234.56
    assert result["conferimenti"][0]["id"] == "c1"
    assert result["coverage_complete"] is True

    result = PreventiviTool().run(stato="ACCETTATO")
    assert [i["id"] for i in result["items"]] == ["p2"]

    result = PreventiviTool().run(fascicolo_id="fasc-1")
    assert [i["id"] for i in result["items"]] == ["p2"]
    assert [c["id"] for c in result["conferimenti"]] == ["c1"]


def test_preventivi_tool_store_non_disponibile(monkeypatch):
    from lex.tools import preventivi_tool
    from lex.tools.preventivi_tool import PreventiviTool

    monkeypatch.setattr(preventivi_tool, "_get_preventivi_store", lambda: None)

    result = PreventiviTool().run()
    assert result["error"] == "store_unavailable"
    assert result["coverage_complete"] is False


# ──────────────────────────────────────────────
# Ricetta triage: clock iniettabile
# ──────────────────────────────────────────────

def test_triage_giornaliero_usa_clock_iniettabile():
    from lex.agents.recipes.triage_giornaliero import build

    clock = Clock(fixed_now=datetime(2026, 7, 10, 7, 30))
    piano = build({}, clock=clock)
    step = next(s for s in piano.steps if s.step_key == "promemoria_urgenze")
    assert step.input_json["data_scadenza"] == "2026-07-11"
