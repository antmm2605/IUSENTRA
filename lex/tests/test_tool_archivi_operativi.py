"""I tool deterministici del registro delle sorgenti esistono davvero; i quattro collegati leggono le funzioni reali."""
from __future__ import annotations

import inspect
from urllib.parse import urlsplit

from lex.operational_knowledge.agents import DEFAULT_OPERATIONAL_AGENTS
from lex.operational_knowledge.models import OperationalQueryContext
from lex.operational_knowledge.source_registry import DEFAULT_SOURCE_DEFINITIONS, TOOL_TOLTI
from lex.operational_knowledge.tools import OperationalKnowledgeTools


def _eseguibili() -> set[str]:
    import lex.tools.economic_context_tools as economici
    from lex.tools.registry import LexToolRegistry

    nomi = {n for n, _ in inspect.getmembers(OperationalKnowledgeTools, inspect.isfunction)}
    nomi |= {n for n, _ in inspect.getmembers(economici, inspect.isfunction)}
    return nomi | {d["tool_name"] for d in LexToolRegistry().list_tools()}


def test_nessun_tool_dichiarato_senza_funzione():
    eseguibili = _eseguibili()
    assert [t for s in DEFAULT_SOURCE_DEFINITIONS for t in s.deterministic_tools if t not in eseguibili] == []
    assert [t for a in DEFAULT_OPERATIONAL_AGENTS for t in a.tools if t not in eseguibili] == []
    dichiarati = {t for s in DEFAULT_SOURCE_DEFINITIONS for t in s.deterministic_tools}
    assert not set(TOOL_TOLTI) & dichiarati and all(m.strip() for _, m in TOOL_TOLTI.values())


def _contesto(*permessi):
    from types import SimpleNamespace

    utente = SimpleNamespace(id="u", ha_permesso=lambda p: p in permessi)
    return OperationalQueryContext(tenant_id="t", user_id="u", user=utente, permissions=set(permessi))


class _Indice:
    def cerca(self, query, limit=20):
        from pct.search_index import RisultatoRicerca

        return [RisultatoRicerca("fascicolo", "F1", "Revocatoria Alfa", "Tribunale", "/fascicoli/F1", "bi", 1.0, "revocatoria")]


class _Uffici:
    def cerca(self, q, tipo="", limit=20):
        return [{"codice": "0580010", "nome": "Tribunale di Milano", "pec": "x@giustiziacert.it", "tipo": "TRIBUNALE"}]


def test_indice_e_uffici():
    tools = OperationalKnowledgeTools(repositories={"ricerca_studio": _Indice(), "uffici_giudiziari": _Uffici()})
    r = tools.search_studio_index("revocatoria", _contesto("ai.usa", "fascicoli.leggi"))
    assert r.ok and r.data[0]["titolo"] == "Revocatoria Alfa"
    assert not tools.search_studio_index("revocatoria", _contesto("ai.usa")).ok  # senza fascicoli.leggi
    u = tools.lookup_uffici_giudiziari("Milano", _contesto("ai.usa", "telematico.leggi"))
    assert u.ok and u.data[0]["nome"] == "Tribunale di Milano"


def test_cassazione_e_archivio(monkeypatch):
    import lex.harness.giurisprudenza as g

    class _Corpus:
        def cerca_sentenze(self, q, limit=3, semantica=False, **_):
            return [{"organo_giudicante": "Corte di cassazione", "sezione": "3", "numero_sentenza": "9449",
                     "anno_sentenza": "2016", "url_pagina_ufficiale": "https://www.italgiure.giustizia.it/x"}]

    monkeypatch.setattr(g, "archivi", lambda: [("Cassazione (SentenzeWeb)", _Corpus()),
                                               ("archivio dello studio (Consulta e fonti pubbliche)", _Corpus())])
    tools = OperationalKnowledgeTools()
    r = tools.search_verified_cassazione("9449/2016", _contesto("ai.usa"))
    assert r.ok and r.data[0]["numero"] == "9449" and urlsplit(r.data[0]["url"]).hostname == "www.italgiure.giustizia.it"
    assert tools.get_giurisprudenza_items("9449/2016", _contesto("ai.usa")).ok


def test_archivi_dichiarano_indisponibilita_al_posto_di_risultati(monkeypatch):
    from lex.harness import giurisprudenza

    class ArchivioNonDisponibile:
        def cerca(self, *args, **kwargs):
            raise OSError("Archivio non disponibile")

    tools = OperationalKnowledgeTools(repositories={"ricerca_studio": ArchivioNonDisponibile()})
    assert not tools.search_studio_index("revocatoria", _contesto("ai.usa", "fascicoli.leggi")).ok
    assert not tools.lookup_uffici_giudiziari("Milano", _contesto("ai.usa")).ok
    monkeypatch.setattr("pct.uffici_giudiziari.get_gestore", ArchivioNonDisponibile)
    assert not tools.lookup_uffici_giudiziari("Milano", _contesto("ai.usa", "telematico.leggi")).ok

    monkeypatch.setattr(giurisprudenza, "archivi", lambda: [])
    esito = tools.search_verified_cassazione("9449/2016", _contesto("ai.usa"))
    assert not esito.data and any("non disponibile" in testo for testo in esito.coverage_gaps)
