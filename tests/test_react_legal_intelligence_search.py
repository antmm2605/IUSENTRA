from types import SimpleNamespace

from web.services import react_legal_intelligence_bridge as bridge


class _Rows:
    def tutti(self, *args, **kwargs):
        return []

    def tutte(self):
        return []


class _NormativeTables:
    def __init__(self, rows_by_table=None, references=None):
        self.rows_by_table = {key: list(value or []) for key, value in dict(rows_by_table or {}).items()}
        self.references = list(references or [])

    def rows(self, table_id):
        return list(self.rows_by_table.get(table_id, []))

    def catalogo_riferimenti_normativi(self):
        return list(self.references)


class _Manager:
    def __init__(self, *, mediazione_rows=None, normative_tables=None, normative_rows=None, normative_references=None):
        self.mediazione_rows = list(mediazione_rows or [])
        self.normative_snapshot = dict(normative_tables or {})
        self.normative_tables = _NormativeTables(normative_rows, normative_references)

    def build_dashboard_snapshot(self, **kwargs):
        return {"headline": {}, "source_rows": [], "normative_tables": self.normative_snapshot}

    def mediazione_registry_snapshot(self, **kwargs):
        rows = list(self.mediazione_rows)
        return {"rows": rows, "total_rows": len(rows), "filtered_rows": len(rows), "mediazione_registry": {}}


class _Repository:
    def __init__(self, *, news=None, search_rows=None, sources=None, activity=None, agent_runs=None):
        self.news = list(news or [])
        self.search_rows = list(search_rows or [])
        self.sources = list(sources or [])
        self.activity = dict(activity or {})
        self.agent_runs = dict(agent_runs or {})
        self.search_queries = []

    def list_news(self, **kwargs):
        return self.news

    def list_matters(self):
        return []

    def search_lex_sources(self, query, *, limit=12):
        self.search_queries.append((query, limit))
        return self.search_rows

    def list_sources(self, enabled_only=False):
        if enabled_only:
            return [source for source in self.sources if source.get("enabled", True)]
        return self.sources

    def source_activity_summary(self):
        return self.activity

    def latest_source_agent_runs(self):
        return self.agent_runs


class _Pipeline:
    def __init__(self, repository):
        self.repository = repository

    def dashboard_snapshot(self):
        return {"headline": {}, "sources": []}


def _seed_agent_runs(path, agent_ids):
    from lex.operational_knowledge.nightly_agents import OperationalAgentRunRepository

    repository = OperationalAgentRunRepository(path)
    for agent_id in agent_ids:
        repository.record(
            {
                "agent_id": agent_id,
                "tenant_slug": "studio-test",
                "tenant_name": "Studio test",
                "status": "ok",
                "generated_at": "2026-05-17T21:00:00Z",
                "self_check": "Superato: inventario operativo aggiornato.",
            }
        )


def _payload(repository, *, page="ricerca-legale", query=None, manager=None, config=None):
    pipeline = _Pipeline(repository)
    return bridge.build_react_legal_intelligence_payload(
        get_legal_intelligence=lambda: manager or _Manager(),
        get_legal_update_pipeline=lambda: pipeline,
        get_fascicoli=lambda: _Rows(),
        get_clienti=lambda: _Rows(),
        get_agenda=lambda: _Rows(),
        get_scadenziario=lambda: _Rows(),
        page=page,
        query=query or {},
        config=config or {},
    )


def test_ricerca_legale_mostra_presidio_lex_ai_nella_pagina_studio(tmp_path):
    from web.services.lex_studio_knowledge_status import LEGAL_AGENT_FOCUS

    db_path = tmp_path / "lex_operational_agents.json"
    _seed_agent_runs(db_path, LEGAL_AGENT_FOCUS)

    payload = _payload(
        _Repository(),
        page="dashboard",
        config={"LEX_OPERATIONAL_AGENTS_DB": str(db_path)},
    )

    sections = {section["id"]: section for section in payload["sections"]}
    assert "lex_presidio" in sections
    assert "ai_avanzata" in sections
    lex_section = sections["lex_presidio"]
    assert any(item["label"] == "Ricerca completa" for item in lex_section["items"])
    assert any(
        item["label"] == "Citazioni verificate e ricerca giurisprudenziale" and item["value"] == "Pronto"
        for item in lex_section["items"]
    )
    agent_metric = next(metric for metric in payload["metrics"] if metric["id"] == "agenti_lex")
    assert agent_metric["value"] == len(LEGAL_AGENT_FOCUS)
    assert "pronti" in agent_metric["note"]


def test_ricerca_legale_espone_monitor_acquisizione_fonti_reali(tmp_path):
    repository = _Repository(
        sources=[
            {"id": 1, "code": "cassazione", "name": "Corte di Cassazione", "enabled": True, "is_official": True},
            {"id": 2, "code": "gazzetta_ufficiale", "name": "Gazzetta Ufficiale", "enabled": True, "is_official": True},
        ],
        activity={
            "cassazione": {
                "raw_documents": 3,
                "normalized_documents": 3,
                "review_pending": 0,
                "review_published": 2,
            },
            "gazzetta_ufficiale": {
                "raw_documents": 0,
                "normalized_documents": 0,
                "review_pending": 0,
                "review_published": 0,
            },
        },
    )

    payload = _payload(
        repository,
        page="ricerca-legale",
        config={"LEGAL_INTELLIGENCE_DB": str(tmp_path / "motori.json")},
    )

    monitor = payload["autofetchMonitor"]
    assert monitor["sources_total"] == 2
    assert monitor["sources_ready"] == 1
    assert monitor["sources_not_ready"] == 1
    assert any(question.startswith("La fonte risulta censita") for question in monitor["quality_questions"])
    readiness = monitor["lawyer_readiness"]
    assert readiness["operational_sources"] == 2
    assert readiness["lex_testable_sources"] == 2
    assert readiness["sources_with_decrees"] == 2
    cassazione = next(source for source in monitor["sources"] if source["source_code"] == "cassazione")
    assert cassazione["delivery_status_label"] == "operativa e controllabile"
    assert "strategia processuale" in cassazione["lawyer_use"]
    assert cassazione["practice_phase"] == "strategia, udienza, provvedimento e precedente"
    assert cassazione["lex_test_question"].startswith("Quali provvedimenti")
    assert cassazione["source_href"].startswith("https://www.cortedicassazione.it/")
    assert cassazione["legal_materials"]
    assert cassazione["articles_and_codes"]
    assert cassazione["decrees_and_rules"]
    assert cassazione["case_law_and_hearings"]
    assert cassazione["research_steps"]
    sections = {section["id"]: section for section in payload["sections"]}
    assert "acquisizione_fonti" in sections
    assert "domande_qualita_fonti" in sections
    fonti = sections["fonti"]
    assert any(item["label"] == "Corte di Cassazione" and item["tone"] == "success" for item in fonti["items"])
    assert any("Serve per: strategia processuale" in item["note"] for item in fonti["items"])
    assert any(metric["id"] == "fonti_pronte" and metric["value"] == 1 for metric in payload["metrics"])
    assert any(metric["id"] == "fonti_con_domanda_lex" and metric["value"] == 2 for metric in payload["metrics"])


def test_ricerca_legale_espone_fonti_web_template_atti():
    payload = _payload(_Repository(), page="ricerca-legale")

    sections = {section["id"]: section for section in payload["sections"]}
    assert "ricerche_web_modelli" in sections
    assert any(metric["id"] == "fonti_modelli" and metric["value"] > 0 for metric in payload["metrics"])
    assert any(record["id"].startswith("template-atti-source:") for record in payload["records"])
    dm_217 = next(record for record in payload["records"] if record["id"] == "template-atti-source:normattiva_dm_217_2023_giustizia_telematica")
    assert dm_217["sourceKind"] == "fonte secondaria collegata"
    assert "Modelli collegati per prefisso" in " ".join(dm_217["keyPoints"])
    assert dm_217["sourceHref"].startswith("https://www.normattiva.it/")


def test_ricerca_legale_espone_fonti_web_guida_pratica_e_rag():
    payload = _payload(_Repository(), page="ricerca-legale")

    sections = {section["id"]: section for section in payload["sections"]}
    assert "ricerche_web_guida_pratica" in sections
    assert any(metric["id"] == "fonti_guida_pratica" and metric["value"] > 0 for metric in payload["metrics"])
    source_ids = {record["id"] for record in payload["records"]}
    assert "guida-pratica-source:cassazione_sentenzeweb" in source_ids
    assert "guida-pratica-source:pst_udienze_da_remoto_2023" in source_ids
    assert "guida-pratica-source:normattiva_whistleblowing_24_2023" in source_ids
    guida_section = sections["ricerche_web_guida_pratica"]
    assert any(item["label"] == "Sentenze e giurisprudenza" and item["value"] > 0 for item in guida_section["items"])
    assert any(item["label"] == "Udienze e decreti" and item["value"] > 0 for item in guida_section["items"])


def test_ricerca_legale_espone_centro_fonti_ufficiali_lex():
    payload = _payload(_Repository(), page="ricerca-legale")

    sections = {section["id"]: section for section in payload["sections"]}
    assert "centro_fonti_ufficiali_lex" in sections
    assert any(metric["id"] == "centro_fonti_ufficiali" and metric["value"] >= 400 for metric in payload["metrics"])
    assert any(metric["id"] == "fonti_da_attivare" and metric["value"] >= 1 for metric in payload["metrics"])
    assert any(record["id"] == "source-delivery:lex_official_config:agenzia_entrate" for record in payload["records"])
    agenzia = next(record for record in payload["records"] if record["id"] == "source-delivery:lex_official_config:agenzia_entrate")
    assert agenzia["sourceKind"] == "fonte ufficiale governata"
    assert agenzia["sourceHref"].startswith("https://www.agenziaentrate.gov.it/")
    assert any("Uso per l'avvocato" in item for item in agenzia["keyPoints"])
    assert any("Articoli e codici" in item and "D.Lgs. 546/1992" in item for item in agenzia["keyPoints"])
    assert any("Decreti e regole tecniche" in item and "D.M. 163/2013" in item for item in agenzia["keyPoints"])
    assert any("Sentenze, udienze e provvedimenti" in item for item in agenzia["keyPoints"])
    assert any("testo vigente" in item.lower() for item in agenzia["operationalChecks"])


def test_ricerca_legale_cerca_centro_fonti_senza_fallback_live(monkeypatch):
    def _unexpected_public_search(*args, **kwargs):
        raise AssertionError("il Centro Fonti censito deve rispondere senza ricerca pubblica live")

    monkeypatch.setattr(bridge, "_run_public_legal_research", _unexpected_public_search)

    payload = _payload(_Repository(), page="ricerca-legale", query={"q": "Agenzia Entrate provvedimenti"})

    assert any(record["id"] == "source-delivery:lex_official_config:agenzia_entrate" for record in payload["records"])
    record = next(record for record in payload["records"] if record["id"] == "source-delivery:lex_official_config:agenzia_entrate")
    assert record["registryKind"] == "centro_fonti_ufficiali_lex"
    assert record["stateLabel"] == "operativa e controllabile"
    assert any("provvedimenti o prassi fiscali" in item.lower() for item in record["operationalChecks"])


def test_ricerca_legale_espone_db_normativa_operativo():
    normative_snapshot = {
        "totali": 2,
        "sincronizzate": 1,
        "verifica_richiesta": 1,
        "riferimenti_normativi_totali": 1,
        "tabelle": [
            {
                "id": "interesse_legale",
                "title": "Interessi legali",
                "category": "tassi",
                "description": "Saggi di interesse legale articolati per periodo di validità.",
                "sync_status": "sincronizzata",
                "last_synced_at": "2026-04-16T05:45:51",
                "sources": [
                    {
                        "code": "interesse_legale_2026",
                        "title": "Gazzetta Ufficiale - saggio interessi legali 2026",
                        "url": "https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.codiceRedazionale=25A06705",
                    }
                ],
                "watch_source_ids": ["gazzetta_ufficiale"],
            },
            {
                "id": "tariffario_forense_scaglioni",
                "title": "Tariffario forense - scaglioni e tabelle",
                "category": "tariffario_forense",
                "description": "Parametri forensi per preventivo, compenso e fasi.",
                "sync_status": "verifica_richiesta",
                "last_synced_at": "2026-04-16T05:45:51",
                "last_warning": "Verificare D.M. 55/2014 e D.M. 147/2022.",
                "sources": [
                    {
                        "code": "dm_55_2014_parametri",
                        "title": "D.M. 55/2014 - parametri forensi",
                        "url": "https://www.normattiva.it/",
                    }
                ],
                "watch_source_ids": ["normattiva"],
            },
        ],
        "riferimenti_normativi": [
            {
                "reference_code": "dm_55_parametri_compensi",
                "title": "Parametri forensi",
                "article": "D.M. 55/2014 aggiornato dal D.M. 147/2022",
                "description": "Fonte per preventivo, compensi e liquidazione giudiziale.",
                "url": "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?atto.codiceRedazionale=22G00157",
                "areas": ["Compensi"],
                "tipologie_labels": ["Preventivo e compenso"],
                "motori": ["Motore preventivo"],
                "redattori": ["Redattore preventivo"],
            }
        ],
    }
    manager = _Manager(
        normative_tables=normative_snapshot,
        normative_rows={
            "interesse_legale": [
                {"start": "2026-01-01", "end": "2026-12-31", "rate": 1.6, "label": "Interesse legale 2026"}
            ],
            "tariffario_forense_scaglioni": [
                {"table_label": "Tabella 1 - Giudice di Pace", "phase_label": "Studio", "base_amount": 68.0}
            ],
        },
        normative_references=normative_snapshot["riferimenti_normativi"],
    )

    payload = _payload(_Repository(), page="ricerca-legale", manager=manager)

    sections = {section["id"]: section for section in payload["sections"]}
    assert "db_normativa" in sections
    assert any(item["label"] == "Tabelle operative" and item["value"] == 2 for item in sections["db_normativa"]["items"])
    assert any(metric["id"] == "db_normativa" and metric["value"] == 2 for metric in payload["metrics"])
    source_ids = {record["id"] for record in payload["records"]}
    assert "normative-table:interesse_legale" in source_ids
    assert "normative-reference:dm_55_parametri_compensi" in source_ids
    interesse = next(record for record in payload["records"] if record["id"] == "normative-table:interesse_legale")
    assert interesse["sourceKind"] == "tabella normativa operativa"
    assert "Uso operativo" in " ".join(interesse["keyPoints"])
    assert any("capitale" in check or "decorrenza" in check for check in interesse["operationalChecks"])


def test_ricerca_legale_cerca_db_normativa_senza_fallback_live(monkeypatch):
    def _unexpected_public_search(*args, **kwargs):
        raise AssertionError("il DB normativa operativo deve rispondere senza fallback live quando contiene la tabella")

    monkeypatch.setattr(bridge, "_run_public_legal_research", _unexpected_public_search)

    normative_snapshot = {
        "totali": 1,
        "sincronizzate": 1,
        "verifica_richiesta": 0,
        "riferimenti_normativi_totali": 0,
        "tabelle": [
            {
                "id": "interesse_legale",
                "title": "Interessi legali",
                "category": "tassi",
                "description": "Saggi di interesse legale articolati per periodo di validità.",
                "sync_status": "sincronizzata",
                "last_synced_at": "2026-04-16T05:45:51",
                "sources": [
                    {
                        "code": "interesse_legale_2026",
                        "title": "Gazzetta Ufficiale - saggio interessi legali 2026",
                        "url": "https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.codiceRedazionale=25A06705",
                    }
                ],
                "watch_source_ids": ["gazzetta_ufficiale"],
            }
        ],
        "riferimenti_normativi": [],
    }
    manager = _Manager(
        normative_tables=normative_snapshot,
        normative_rows={
            "interesse_legale": [
                {"start": "2026-01-01", "end": "2026-12-31", "rate": 1.6, "label": "Interesse legale 2026"}
            ]
        },
    )

    payload = _payload(_Repository(), page="ricerca-legale", query={"q": "interesse legale 2026"}, manager=manager)

    assert payload["contracts"]["external_fetch"] is False
    assert any(record["id"] == "normative-table:interesse_legale" for record in payload["records"])
    record = next(record for record in payload["records"] if record["id"] == "normative-table:interesse_legale")
    assert "Interesse legale 2026" in record["sourceExcerpt"]
    assert record["registryKind"] == "db_normativa"


def test_ricerca_legale_cerca_fonti_guida_pratica_per_giurisprudenza_udienze_e_decreti(monkeypatch):
    def _unexpected_public_search(*args, **kwargs):
        raise AssertionError("le fonti Guida/RAG indicizzate devono rispondere senza fallback live")

    monkeypatch.setattr(bridge, "_run_public_legal_research", _unexpected_public_search)

    whistleblowing = _payload(_Repository(), page="ricerca-legale", query={"q": "whistleblowing D.Lgs. 24 2023 ANAC"})
    udienza = _payload(_Repository(), page="ricerca-legale", query={"q": "udienza 127-ter note scritte"})
    cassazione = _payload(_Repository(), page="ricerca-legale", query={"q": "Cassazione SentenzeWeb giurisprudenza"})

    assert any(record["id"] == "guida-pratica-source:normattiva_whistleblowing_24_2023" for record in whistleblowing["records"])
    assert any(record["id"] == "guida-pratica-source:anac_whistleblowing" for record in whistleblowing["records"])
    assert any(record["id"] == "guida-pratica-source:ministero_giustizia_127ter_2023" for record in udienza["records"])
    assert any(record["id"] == "guida-pratica-source:pst_udienze_da_remoto_2023" for record in udienza["records"])
    assert any(record["id"] == "guida-pratica-source:cassazione_sentenzeweb" for record in cassazione["records"])
    assert any(record["sourceKind"] == "fonte giurisprudenziale" for record in cassazione["records"])


def test_ricerca_legale_cerca_fonti_template_atti_per_decreto_attuativo():
    payload = _payload(_Repository(), page="ricerca-legale", query={"q": "D.M. 217 2023 deposito telematico"})

    source_ids = {record["id"] for record in payload["records"]}
    assert "template-atti-source:normattiva_dm_217_2023_giustizia_telematica" in source_ids
    assert any(record["sourceKind"] == "fonte secondaria collegata" for record in payload["records"])


def test_ricerca_legale_cerca_fonti_template_atti_per_attestazione_sentenza(monkeypatch):
    def _unexpected_public_search(*args, **kwargs):
        raise AssertionError("le fonti specifiche su attestazione sentenza devono evitare la ricerca pubblica live")

    monkeypatch.setattr(bridge, "_run_public_legal_research", _unexpected_public_search)

    payload = _payload(
        _Repository(),
        page="ricerca-legale",
        query={"q": "attestazione conformità sentenza termine breve notifica"},
    )

    source_ids = {record["id"] for record in payload["records"]}
    assert "template-atti-source:normattiva_dl_179_2012_art_16_decies_attestazione" in source_ids
    assert "template-atti-source:disp_att_cpc_art_196_undecies_attestazione" in source_ids
    assert "template-atti-source:pst_dgsia_2024_art_27_attestazione_conformita" in source_ids
    assert "template-atti-source:normattiva_cpc_art_285_325_326_sentenza_termine_breve" in source_ids
    assert payload["contracts"]["external_fetch"] is False


def test_ricerca_legale_cerca_banche_dati_giurisprudenziali_ufficiali(monkeypatch):
    def _unexpected_public_search(*args, **kwargs):
        raise AssertionError("le banche dati giurisprudenziali ufficiali censite devono evitare fallback live")

    monkeypatch.setattr(bridge, "_run_public_legal_research", _unexpected_public_search)

    cassazione = _payload(_Repository(), page="ricerca-legale", query={"q": "Cassazione SentenzeWeb giurisprudenza"})
    cedu = _payload(_Repository(), page="ricerca-legale", query={"q": "HUDOC CEDU equo processo"})
    ue = _payload(_Repository(), page="ricerca-legale", query={"q": "CURIA CGUE EUR-Lex giurisprudenza UE"})

    assert any(record["id"] == "template-atti-source:corte_cassazione_sentenzeweb" for record in cassazione["records"])
    assert any(record["id"] == "template-atti-source:hudoc_cedu_giurisprudenza" for record in cedu["records"])
    assert any(record["id"] == "template-atti-source:curia_cgue_giurisprudenza_ue" for record in ue["records"])
    assert any(record["id"] == "template-atti-source:eurlex_legislazione_giurisprudenza_ue" for record in ue["records"])
    assert all(payload["contracts"]["external_fetch"] is False for payload in (cassazione, cedu, ue))


def test_ricerca_legale_fonte_modello_ufficiale_non_chiama_fallback_pubblico(monkeypatch):
    def _unexpected_public_search(*args, **kwargs):
        raise AssertionError("la fonte ufficiale modello deve evitare la ricerca pubblica live")

    monkeypatch.setattr(bridge, "_run_public_legal_research", _unexpected_public_search)

    payload = _payload(_Repository(), page="ricerca-legale", query={"q": "D.M. 217 2023 deposito telematico"})

    assert any(
        record["id"] == "template-atti-source:normattiva_dm_217_2023_giustizia_telematica"
        for record in payload["records"]
    )
    assert payload["contracts"]["external_fetch"] is False


def test_ricerca_legale_fonte_modello_ufficiale_non_scansiona_archivi_pesanti(monkeypatch):
    def _unexpected_archive_search(*args, **kwargs):
        raise AssertionError("la fonte ufficiale modello deve evitare la scansione foreground degli archivi estesi")

    monkeypatch.setattr(bridge, "_official_archive_records", _unexpected_archive_search)

    payload = _payload(_Repository(), page="ricerca-legale", query={"q": "D.M. 217 2023 deposito telematico"})

    assert any(
        record["id"] == "template-atti-source:normattiva_dm_217_2023_giustizia_telematica"
        for record in payload["records"]
    )


def test_ricerca_legale_fonte_modello_esatta_non_scansiona_repository_tenant():
    repository = _Repository(
        search_rows=[
            {
                "id": "row-lenta",
                "title": "Archivio interno non necessario",
                "excerpt": "La fonte modello specifica deve bastare per il D.M. 217.",
                "source_code": "archivio",
            }
        ]
    )

    payload = _payload(repository, page="ricerca-legale", query={"q": "D.M. 217 2023 deposito telematico"})

    assert repository.search_queries == []
    assert any(
        record["id"] == "template-atti-source:normattiva_dm_217_2023_giustizia_telematica"
        for record in payload["records"]
    )


def test_ricerca_legale_interroga_repository_e_mantiene_estratti(monkeypatch):
    def _unexpected_public_search(*args, **kwargs):
        raise AssertionError("la ricerca web non serve quando l'archivio interno ha fonti ufficiali sufficienti")

    monkeypatch.setattr(bridge, "_run_public_legal_research", _unexpected_public_search)
    long_excerpt = (
        "Estratto ufficiale completo sul credito di imposta per investimenti produttivi, "
        "con pubblicazione, fonte primaria e contenuto sufficiente per mostrare il contesto."
    )
    repository = _Repository(
        search_rows=[
            {
                "type": "normativa",
                "id": "normativa:1",
                "title": "Decreto credito imposta investimenti",
                "excerpt": long_excerpt,
                "authority": "Gazzetta Ufficiale",
                "official_url": "https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00038/sg",
                "published_at": "2026-03-27",
                "verified_reference": True,
            },
            {
                "type": "prassi",
                "id": "prassi:1",
                "title": "Circolare credito imposta investimenti",
                "excerpt": long_excerpt,
                "authority": "Agenzia delle Entrate",
                "official_url": "https://www.agenziaentrate.gov.it/portale/",
                "published_at": "2026-03-28",
                "verified_reference": True,
            },
        ]
    )

    payload = _payload(repository, query={"q": "credito imposta investimenti"})

    assert repository.search_queries == [("credito imposta investimenti", 12)]
    assert payload["contracts"]["external_fetch"] is False
    assert [record["title"] for record in payload["records"][:2]] == [
        "Decreto credito imposta investimenti",
        "Circolare credito imposta investimenti",
    ]
    assert all(record["subtitle"] for record in payload["records"][:2])
    assert all(record["sourceExcerpt"] for record in payload["records"][:2])
    assert all(record["sourceContext"] for record in payload["records"][:2])
    assert all(record["practicalUse"] for record in payload["records"][:2])
    assert all(record["reliabilityNote"] for record in payload["records"][:2])


def test_ricerca_legale_non_duplica_contesto_operativo_e_contenuto_identici():
    excerpt = (
        "Protocollo n. 0048405 del 06/02/2026 ASSOCIAZIONE EMITTENTI RADIO "
        "Contributo alla consultazione pubblica AGCOM alla cortese attenzione "
        "dell'Autorita per le Garanzie nelle Comunicazioni."
    )

    record = bridge._enrich_record_context(
        {
            "id": "legal-updates-web_evidence:42",
            "kind": "legal web evidence",
            "title": "02 Assoradio",
            "sourceExcerpt": excerpt,
            "contextSummary": excerpt,
            "sourceLabel": "AGCOM - atti e provvedimenti",
            "sourceKind": "fonte ufficiale",
            "sourceHref": "https://www.agcom.it/provvedimenti",
            "area": "pdf",
            "branch": "legal web evidence",
        }
    )

    assert any(item.startswith("Contesto operativo:") for item in record["sourceContext"])
    assert not any(item.startswith("Contenuto:") for item in record["sourceContext"])


def test_ricerca_legale_filtra_contributi_agcom_non_utili_allo_studio():
    repository = _Repository(
        search_rows=[
            {
                "type": "legal_web_evidence",
                "id": "legal-updates-web_evidence:42",
                "title": "02 Assoradio",
                "excerpt": (
                    "Protocollo n. 0048405 del 06/02/2026 ASSOCIAZIONE EMITTENTI RADIO "
                    "Contributo alla consultazione pubblica AGCOM. Richiesta di "
                    "pianificazione di una frequenza DAB+ locale per l'area di Bari."
                ),
                "content": "Documento di posizione tecnica di un'associazione di emittenti radio.",
                "authority": "AGCOM - atti e provvedimenti",
                "official_url": "https://www.agcom.it/provvedimenti/02_Assoradio.pdf",
                "source_code": "agcom_provvedimenti",
                "verified_reference": True,
            },
            {
                "type": "prassi",
                "id": "legal-updates-prassi:7",
                "title": "Delibera AGCOM n. 123/26/CONS",
                "excerpt": "Provvedimento sanzionatorio AGCOM con obblighi regolamentari e tutela utenti.",
                "content": "Delibera su procedimento sanzionatorio e violazione di obblighi regolamentari.",
                "authority": "AGCOM",
                "official_url": "https://www.agcom.it/provvedimenti/delibera-123-26-cons",
                "source_code": "agcom_provvedimenti",
                "verified_reference": True,
            },
        ]
    )

    payload = _payload(repository, query={"q": "AGCOM"})

    titles = [record["title"] for record in payload["records"]]
    assert "02 Assoradio" not in titles
    assert "Delibera AGCOM n. 123/26/CONS" in titles


def test_ricerca_legale_usa_testo_pdf_esteso_senza_metterlo_tutto_nel_contesto():
    full_text = (
        "Delibera AGCOM n. 123/26/CONS. Procedimento sanzionatorio e tutela utenti. "
        + "Obblighi regolamentari, ordine di adeguamento e motivazione del provvedimento. " * 35
        + "Conclusione specifica del testo completo indicizzato."
    )
    repository = _Repository(
        search_rows=[
            {
                "type": "legal_web_evidence",
                "id": "legal-updates-web_evidence:77",
                "title": "Delibera AGCOM n. 123/26/CONS",
                "excerpt": "Delibera AGCOM n. 123/26/CONS. Procedimento sanzionatorio e tutela utenti.",
                "content": full_text,
                "authority": "AGCOM - atti e provvedimenti",
                "official_url": "https://www.agcom.it/provvedimenti/delibera-123-26-cons.pdf",
                "source_code": "agcom_provvedimenti",
                "verified_reference": True,
            }
        ]
    )

    payload = _payload(repository, query={"q": "Delibera AGCOM 123/26"})
    record = payload["records"][0]

    assert "Conclusione specifica del testo completo indicizzato" in record["officialContext"]
    assert "Conclusione specifica" not in record["sourceExcerpt"]
    assert record["contextCompleted"] is True
    assert any("Testo letto" in item for item in record["sourceContext"])


def test_ricerca_legale_mostra_pdf_ocr_riferimenti_e_domande():
    repository = _Repository(
        search_rows=[
            {
                "type": "legal_web_evidence",
                "entity_type": "web_evidence",
                "id": "legal-updates-web_evidence:50194",
                "title": "Questione Penale Pendente del ricorso R.G. 9926/2026",
                "excerpt": "PDF ufficiale Cassazione con testo OCR leggibile.",
                "content": "Testo OCR ufficiale: art. 606 c.p.p. e art. 599-bis c.p.p.",
                "authority": "Corte Suprema di Cassazione",
                "official_url": "https://www.cortedicassazione.it/resources/cms/documents/qsp50194.pdf",
                "source_code": "cassazione_ultime_sent_ord_questioni",
                "verified_reference": True,
                "attachment_url": "https://www.cortedicassazione.it/resources/cms/documents/qsp50194.pdf",
                "attachment_type": "pdf",
                "context_chars": 420,
                "norm_references": ["art. 606 c.p.p.", "art. 599-bis c.p.p."],
                "rg_references": ["9926/2026", "9966/2026"],
                "contextual_questions": [
                    {
                        "check": "pdf_allegato",
                        "question": "Quale PDF o allegato ufficiale è collegato e il link è cliccabile?",
                    }
                ],
            }
        ]
    )

    payload = _payload(repository, query={"q": "PDF allegato art. 606 c.p.p."})
    record = payload["records"][0]

    assert record["evidenceType"] == "PDF ufficiale letto"
    assert any("Riferimenti normativi" in item for item in record["keyPoints"])
    assert any("Riferimenti R.G." in item for item in record["keyPoints"])
    assert any("Domanda per Lex" in item for item in record["operationalChecks"])
    assert record["sourceHref"].endswith("qsp50194.pdf")


def test_ricerca_legale_attiva_fonti_ufficiali_quando_archivio_non_basta(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "_rewrite_query_for_legal_research",
        lambda query: SimpleNamespace(
            original_query=query,
            public_research_query=query,
            can_use_ldr=True,
            local_deep_research_query=query,
        ),
    )

    def _public_search(rewritten, **kwargs):
        assert rewritten.can_use_ldr is False
        return SimpleNamespace(
            warnings=[],
            sources=[
                SimpleNamespace(
                    id="pst-mediazione",
                    title="Registro organismi di mediazione",
                    source_name="Portale Servizi Telematici",
                    source_type="web_ufficiale",
                    official=True,
                    url="https://pst.giustizia.it/PST/it/servizi.page",
                    date="2026-05-11",
                    excerpt=(
                        "Fonte ufficiale PST sul registro degli organismi di mediazione, "
                        "con contenuto utile alla verifica del ripristino dei servizi."
                    ),
                )
            ],
        )

    monkeypatch.setattr(bridge, "_run_public_legal_research", _public_search)
    repository = _Repository()

    payload = _payload(repository, query={"q": "usura bancaria tasso soglia"})

    assert repository.search_queries == [("usura bancaria tasso soglia", 12)]
    assert payload["contracts"]["external_fetch"] is True
    assert any(record["title"] == "Registro organismi di mediazione" for record in payload["records"])
    assert any(record["sourceKind"] == "fonte ufficiale" for record in payload["records"])


def test_ricerca_legale_sentenza_corte_costituzionale_scarta_risultati_cassazione(monkeypatch):
    monkeypatch.setattr(bridge, "_search_normattiva", None)
    monkeypatch.setattr(bridge, "_search_gazzetta", lambda *args, **kwargs: [])
    monkeypatch.setattr(bridge, "_build_official_context", None)
    monkeypatch.setattr(
        bridge,
        "_rewrite_query_for_legal_research",
        lambda query: SimpleNamespace(
            original_query=query,
            public_research_query=query,
            can_use_ldr=True,
            local_deep_research_query=query,
        ),
    )

    def _public_search(rewritten, **kwargs):
        return SimpleNamespace(
            warnings=[],
            sources=[
                SimpleNamespace(
                    id="corte-cost-50-2026",
                    title="Sentenza della Corte Costituzionale n. 50 del 27/1/2026",
                    source_name="Corte Costituzionale",
                    source_type="web_ufficiale",
                    official=True,
                    url="https://www.cortecostituzionale.it/actionSchedaPronuncia.do?anno=2026&numero=50",
                    date="2026-01-27",
                    excerpt="Scheda ufficiale della sentenza n. 50 del 27 gennaio 2026.",
                )
            ],
        )

    monkeypatch.setattr(bridge, "_run_public_legal_research", _public_search)
    repository = _Repository(
        search_rows=[
            {
                "id": "cassazione-noise",
                "title": "Sentenza n. 11513 del 28/04/2026",
                "authority": "Corte Suprema di Cassazione",
                "official_url": "https://www.cortedicassazione.it/it/civile_dettaglio.page?contentId=SZC50131",
                "excerpt": "Richiama Corte Costituzionale e il 2026, ma non e' la sentenza n. 50 richiesta.",
                "content": "Risultato Cassazione non pertinente alla Corte Costituzionale n. 50.",
                "source_code": "cassazione",
                "verified_reference": True,
            }
        ]
    )

    payload = _payload(
        repository,
        query={"q": "Sentenza della Corte Costituzionale n. 50 del 27/1/2026"},
    )

    titles = [record["title"] for record in payload["records"]]
    assert "Sentenza della Corte Costituzionale n. 50 del 27/1/2026" in titles
    assert "Sentenza n. 11513 del 28/04/2026" not in titles
    assert payload["contracts"]["external_fetch"] is True


def test_ricerca_legale_legge_archivi_normattiva_e_gazzetta_locali(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "_official_archive_snapshot",
        lambda: {
            "normattiva": {"available": True, "documents": 189851, "articles": 800757, "chunks": 639273},
            "gazzetta": {"available": True, "documents": 28, "chunks": 3911, "sources": 1},
        },
    )
    monkeypatch.setattr(
        bridge,
        "_search_normattiva",
        lambda query, limit=8: [
            {
                "chunk_id": "normattiva:1",
                "document_id": 10,
                "fonte": "Normattiva",
                "titolo": "Delega al Governo per l'efficienza del processo civile",
                "testo": "Estratto ufficiale Normattiva sulla mediazione obbligatoria e sul processo civile.",
                "data": "2021-11-26",
                "url_origine": "https://www.normattiva.it/",
                "materia": "Diritto civile",
            }
        ],
    )
    monkeypatch.setattr(
        bridge,
        "_search_gazzetta",
        lambda query, limit=6: [
            {
                "chunk_id": "gazzetta:1",
                "document_id": 20,
                "fonte": "Gazzetta Ufficiale",
                "titolo": "Gazzetta Ufficiale - Serie Generale",
                "testo": "Estratto della Gazzetta Ufficiale collegato alla ricerca.",
                "data": "2026-05-14",
                "url_origine": "https://www.gazzettaufficiale.it/",
            }
        ],
    )
    monkeypatch.setattr(
        bridge,
        "_run_public_legal_research",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("non serve ricerca web se gli archivi locali bastano")),
    )

    payload = _payload(_Repository(), page="ricerca-legale", query={"q": "mediazione obbligatoria"})

    titles = [record["title"] for record in payload["records"]]
    assert "Delega al Governo per l'efficienza del processo civile" in titles
    assert "Gazzetta Ufficiale - Serie Generale" in titles
    assert payload["contracts"]["external_fetch"] is False
    assert any(metric["id"] == "normattiva" and metric["value"] == 189851 for metric in payload["metrics"])
    archive_section = next(section for section in payload["sections"] if section["id"] == "archivi_ufficiali")
    assert any(item["label"] == "Normattiva" and item["value"] == 189851 for item in archive_section["items"])


def test_news_pst_mediazione_ripristinata_presente_in_news_e_ricerca():
    repository = _Repository()

    news_payload = _payload(repository, page="news")
    search_payload = _payload(repository, page="ricerca-legale")

    for payload in (news_payload, search_payload):
        pst_record = next(
            record for record in payload["records"]
            if record["id"] == "pst-nws4865-ripristino-mediazione"
        )
        assert pst_record["date"] == "2026-05-11"
        assert pst_record["registryNumber"] == "NWS4865"
        assert "22/04/2026" in pst_record["subtitle"]
        assert pst_record["sourceHref"] == bridge._PST_MEDIAZIONE_RECOVERY_URL


def test_news_gazzetta_ripulisce_blocchi_cumulativi_e_corregge_fonte():
    repository = _Repository(
        news=[
            {
                "id": 7,
                "title": "D.Lgs. 13 marzo 2026, n. 39",
                "slug": "d-lgs-13-marzo-2026-n-39",
                "short_summary": (
                    "27/03/2026 TUTELA DEI MINORI IN AFFIDAMENTO "
                    "( L. 17 marzo 2026, n. 37 ) Leggi la notizia "
                    "27/03/2026 ACCORDI DI DELEGA, GESTIONE RISCHIO DI LIQUIDITA' "
                    "E VIGILANZA - RECEPIMENTO DIRETTIVA (UE) "
                    "( D.Lgs. 13 marzo 2026, n. 39 ) Leggi la notizia"
                ),
                "content": "Introduce un nuovo atto o un nuovo riferimento normativo da censire in archivio.",
                "news_type": "normativa",
                "source_url": "http://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00056/sg",
                "source_name": "Gazzetta Ufficiale",
                "source_code": "gazzetta_ufficiale",
                "matter_name": "Diritto tributario",
                "submatter_name": "IVA",
                "publication_status": "published",
                "published_at": "2026-04-19T10:43:19",
            }
        ]
    )

    payload = _payload(repository, page="news")
    record = next(record for record in payload["records"] if record["id"] == "7")

    assert "accordi di delega" in record["sourceExcerpt"].lower()
    assert "gestione rischio di liquidità" in record["sourceExcerpt"]
    assert "Tutela dei minori" not in record["sourceExcerpt"]
    assert "Leggi la notizia" not in record["sourceExcerpt"]
    assert record["sourceKind"] == "fonte ufficiale"
    assert record["sourceLabel"] == "Gazzetta Ufficiale"
    assert record["sourceHref"].startswith("http://www.gazzettaufficiale.it/")
    assert record["area"] == "Unione europea"
    assert record["branch"] == "Mercati finanziari e vigilanza"
    assert "Fonte ufficiale: Gazzetta Ufficiale" in record["sourceContext"]
    assert any("Anteprima" in item or "Testo letto" in item for item in record["sourceContext"])


def test_ricerca_legale_completa_record_povero_con_contesto_interno(monkeypatch):
    official_url = "http://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00056/sg"
    repository = _Repository(
        news=[
            {
                "id": 7,
                "title": "D.Lgs. 13 marzo 2026, n. 39",
                "short_summary": "D.Lgs. 13 marzo 2026, n. 39",
                "content": "Introduce un nuovo atto o un nuovo riferimento normativo da censire in archivio.",
                "news_type": "normativa",
                "source_url": official_url,
                "source_name": "Gazzetta Ufficiale",
                "source_code": "gazzetta_ufficiale",
                "matter_name": "Diritto tributario",
                "submatter_name": "IVA",
                "publication_status": "published",
                "published_at": "2026-04-19T10:43:19",
            }
        ]
    )

    monkeypatch.setattr(bridge, "_search_normattiva", None)
    monkeypatch.setattr(bridge, "_search_gazzetta", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        bridge,
        "_rewrite_query_for_legal_research",
        lambda query: SimpleNamespace(
            original_query=query,
            public_research_query=query,
            local_deep_research_query=query,
            can_use_ldr=True,
            can_use_official_web=True,
        ),
    )

    def _official_result(*args, **kwargs):
        return SimpleNamespace(
            warnings=[],
            sources=[
                SimpleNamespace(
                    id="gazzetta-26g00056",
                    title="D.Lgs. 13 marzo 2026, n. 39 - Gazzetta Ufficiale",
                    source_name="Gazzetta Ufficiale",
                    source_type="web_ufficiale",
                    official=True,
                    url=official_url,
                    date="2026-03-27",
                    excerpt=(
                        "Testo ufficiale più ampio: accordi di delega, gestione rischio di liquidità, "
                        "vigilanza e recepimento della direttiva dell'Unione europea in materia di "
                        "deleghe, controlli e presidi finanziari."
                    ),
                )
            ],
        )

    monkeypatch.setattr(bridge, "_run_public_legal_research", _official_result)
    def _official_context(url, query, **kwargs):
        assert url == official_url
        assert kwargs["timeout"] == bridge._OFFICIAL_CONTEXT_TIMEOUT
        assert kwargs["max_bytes"] == bridge._OFFICIAL_CONTEXT_MAX_BYTES
        return {
            "officialContext": (
                "DECRETO LEGISLATIVO 13 marzo 2026, n. 39. Recepimento della direttiva "
                "dell'Unione europea sugli accordi di delega, sulla gestione del rischio di "
                "liquidità e sui poteri di vigilanza. Il testo disciplina controlli, presidi "
                "organizzativi, decorrenze e obblighi di adeguamento per gli operatori interessati."
            ),
            "contextSummary": (
                "Recepimento della direttiva dell'Unione europea sugli accordi di delega, "
                "gestione del rischio di liquidità e poteri di vigilanza."
            ),
            "keyPoints": ["Oggetto: accordi di delega, rischio di liquidità e vigilanza."],
            "operationalChecks": ["Controlla decorrenza e obblighi di adeguamento."],
            "contextCompleted": True,
            "warnings": [],
        }

    monkeypatch.setattr(bridge, "_build_official_context", _official_context)

    payload = _payload(repository, page="ricerca-legale", query={"q": "D.Lgs. 13 marzo 2026 n. 39"})
    record = next(record for record in payload["records"] if record["id"] == "7")

    assert payload["contracts"]["external_fetch"] is True
    assert "gestione del rischio di liquidità" in record["sourceExcerpt"]
    assert "Introduce un nuovo atto" not in record["sourceExcerpt"]
    assert record["contextCompleted"] is True
    assert "Recepimento della direttiva" in record["officialContext"]
    assert record["contextSummary"]
    assert any("Oggetto:" in item for item in record["keyPoints"])
    assert any("decorrenza" in item.lower() for item in record["operationalChecks"])
    assert record["sourceKind"] == "fonte ufficiale"
    assert record["sourceLabel"] == "Gazzetta Ufficiale"
    assert any("Lettura in pagina" in item for item in record["sourceContext"])


def test_ricerca_legale_non_marca_completo_elenco_gazzetta_cumulativo(monkeypatch):
    official_url = "http://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00056/sg"
    cumulative_excerpt = (
        "27/03/2026 TUTELA DEI MINORI IN AFFIDAMENTO "
        "( L. 17 marzo 2026, n. 37 ) Leggi la notizia "
        "27/03/2026 ACCORDI DI DELEGA, GESTIONE RISCHIO DI LIQUIDITA' "
        "E VIGILANZA - RECEPIMENTO DIRETTIVA (UE) "
        "( D.Lgs. 13 marzo 2026, n. 39 ) Leggi la notizia "
        "25/03/2026 LEGGE DI DELEGAZIONE EUROPEA 2025 "
        "( L. 17 marzo 2026, n. 36 ) Leggi la notizia"
    )
    repository = _Repository(
        search_rows=[
            {
                "type": "normativa",
                "id": "legal-updates-normative:6",
                "title": "D.Lgs. 13 marzo 2026, n. 39",
                "excerpt": cumulative_excerpt,
                "content": cumulative_excerpt,
                "authority": "Gazzetta Ufficiale",
                "official_url": official_url,
                "published_at": "2026-03-27",
                "verified_reference": True,
                "source_code": "gazzetta_ufficiale",
                "matter_name": "Diritto tributario",
                "submatter_name": "IVA",
            }
        ]
    )
    monkeypatch.setattr(bridge, "_search_normattiva", None)
    monkeypatch.setattr(bridge, "_search_gazzetta", lambda *args, **kwargs: [])
    monkeypatch.setattr(bridge, "_run_public_legal_research", None)

    def _official_context(url, query, **kwargs):
        assert url == official_url
        return {
            "officialContext": (
                "Home Atto Completo Chiudi DECRETO LEGISLATIVO 13 marzo 2026, n. 39 "
                "Recepimento della direttiva (UE) 2024/927 per quanto riguarda gli accordi "
                "di delega, la gestione del rischio di liquidità, le segnalazioni a fini "
                "di vigilanza e i servizi di custodia e depositario."
            ),
            "contextSummary": "Home Atto Completo Chiudi DECRETO LEGISLATIVO 13 marzo 2026, n. 39",
            "keyPoints": ["Home Atto Completo Chiudi DECRETO LEGISLATIVO 13 marzo 2026, n. 39"],
            "operationalChecks": ["Controlla decorrenza e obblighi di adeguamento."],
            "contextCompleted": True,
            "warnings": [],
        }

    monkeypatch.setattr(bridge, "_build_official_context", _official_context)

    payload = _payload(repository, query={"q": "D.Lgs. 13 marzo 2026 n. 39"})
    record = payload["records"][0]

    assert record["title"] == "D.Lgs. 13 marzo 2026, n. 39"
    assert "accordi di delega" in record["sourceExcerpt"].lower()
    assert "Tutela dei minori" not in record["sourceExcerpt"]
    assert "Leggi la notizia" not in record["sourceExcerpt"]
    assert record["contextCompleted"] is True
    assert record["officialContext"].startswith("DECRETO LEGISLATIVO 13 marzo 2026, n. 39")
    assert "Home Atto Completo" not in record["officialContext"]
    assert record["area"] == "Unione europea"
    assert record["branch"] == "Mercati finanziari e vigilanza"
    assert any("Oggetto:" in item for item in record["keyPoints"])
    assert not any(
        warning.get("code") == "ricerca_ufficiale_avviso"
        and "nessuna evidenza pubblica" in warning.get("message", "").lower()
        for warning in payload["warnings"]
    )


def test_ricerca_legale_limita_letture_ufficiali_live(monkeypatch):
    official_records = [
        {
            "type": "normativa",
            "id": f"normativa:{index}",
            "title": "D.Lgs. 13 marzo 2026, n. 39",
            "excerpt": "D.Lgs. 13 marzo 2026, n. 39",
            "authority": "Gazzetta Ufficiale",
            "official_url": f"https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G0005{index}/sg",
            "verified_reference": True,
        }
        for index in range(5)
    ]
    calls: list[str] = []
    monkeypatch.setattr(bridge, "_search_gazzetta", lambda *args, **kwargs: [])
    monkeypatch.setattr(bridge, "_search_normattiva", None)
    monkeypatch.setattr(bridge, "_run_public_legal_research", None)

    def _official_context(url, query, **kwargs):
        calls.append(url)
        return {
            "officialContext": (
                "Testo ufficiale letto in IUSENTRA con contenuto utile, decorrenza e oggetto dell'atto. "
                "La scheda contiene il riferimento normativo, i presidi applicativi e i controlli "
                "necessari prima dell'uso professionale nel fascicolo."
            ),
            "contextSummary": "Contesto ufficiale letto in IUSENTRA.",
            "keyPoints": ["Oggetto: contenuto ufficiale."],
            "operationalChecks": ["Controlla decorrenza."],
            "contextCompleted": True,
            "warnings": [],
        }

    monkeypatch.setattr(bridge, "_build_official_context", _official_context)

    payload = _payload(
        _Repository(search_rows=official_records),
        query={"q": "D.Lgs. 13 marzo 2026 n. 39"},
    )

    assert payload["contracts"]["external_fetch"] is True
    assert len(calls) == bridge._OFFICIAL_CONTEXT_FETCH_LIMIT
    assert sum(1 for record in payload["records"] if record["contextCompleted"]) == bridge._OFFICIAL_CONTEXT_FETCH_LIMIT


def test_ricerca_legale_non_rilegge_estratto_ufficiale_gia_completo(monkeypatch):
    def _unexpected_official_context(*args, **kwargs):
        raise AssertionError("non deve leggere il web quando il contesto ufficiale locale e' gia completo")

    monkeypatch.setattr(bridge, "_build_official_context", _unexpected_official_context)
    monkeypatch.setattr(bridge, "_search_gazzetta", lambda *args, **kwargs: [])
    monkeypatch.setattr(bridge, "_search_normattiva", None)
    monkeypatch.setattr(bridge, "_run_public_legal_research", None)
    long_excerpt = " ".join(["Estratto ufficiale locale completo su atto normativo, decorrenza, oggetto e controlli."] * 12)

    payload = _payload(
        _Repository(
            search_rows=[
                {
                    "type": "normativa",
                    "id": "normativa:99",
                    "title": "D.Lgs. 13 marzo 2026, n. 39",
                    "excerpt": long_excerpt,
                    "authority": "Gazzetta Ufficiale",
                    "official_url": "https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00056/sg",
                    "verified_reference": True,
                }
            ]
        ),
        query={"q": "D.Lgs. 13 marzo 2026 n. 39"},
    )

    assert payload["contracts"]["external_fetch"] is False
    assert payload["records"][0]["contextCompleted"] is True
    assert payload["records"][0]["officialContext"].startswith("Estratto ufficiale locale completo")
    assert payload["records"][0]["sourceExcerpt"].startswith("Estratto ufficiale locale completo")
    assert len(payload["records"][0]["officialContext"]) > len(payload["records"][0]["sourceExcerpt"])


def test_ricerca_legale_non_legge_dominio_simile_a_fonte_ufficiale(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(bridge, "_search_gazzetta", lambda *args, **kwargs: [])
    monkeypatch.setattr(bridge, "_search_normattiva", None)
    monkeypatch.setattr(bridge, "_run_public_legal_research", None)
    monkeypatch.setattr(bridge, "_build_official_context", lambda url, *args, **kwargs: calls.append(url) or {})

    payload = _payload(
        _Repository(
            search_rows=[
                {
                    "type": "normativa",
                    "id": "normativa:evil",
                    "title": "D.Lgs. 13 marzo 2026, n. 39",
                    "excerpt": "D.Lgs. 13 marzo 2026, n. 39",
                    "authority": "Fonte non ufficiale",
                    "official_url": "https://evilgiustizia.it/eli/id/2026/03/27/26G00056/sg",
                    "verified_reference": False,
                }
            ]
        ),
        query={"q": "D.Lgs. 13 marzo 2026 n. 39"},
    )

    assert payload["contracts"]["external_fetch"] is False
    assert calls == []
    assert payload["records"][0]["contextCompleted"] is False


def test_mediazione_espone_accessi_ufficiali_ripristinati():
    repository = _Repository()

    mediazione_payload = _payload(repository, page="mediazione")
    search_payload = _payload(repository, page="ricerca-legale", query={"q": "elenco formatori mediazione"})

    records_by_id = {record["id"]: record for record in mediazione_payload["records"]}
    expected_links = {
        "mediazione-registro-organismi": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
        "mediazione-elenco-enti": "https://mediazione.giustizia.it/ROM/AlboEntiFormazione.aspx",
        "mediazione-elenco-formatori": "https://mediazione.giustizia.it/ROM/AlboFormatori.aspx",
    }
    for record_id, official_url in expected_links.items():
        record = records_by_id[record_id]
        assert record["sourceKind"] == "fonte ufficiale"
        assert record["sourceHref"] == official_url
        assert record["date"] == "22/04/2026"
        assert record["approvalLabel"] == "ripristinato"
        assert record["evidenceType"] == "accesso ufficiale"
        assert record["sourceContext"]
        assert "mediazione" in record["practicalUse"].lower()

    assert any(
        record["id"] == "mediazione-elenco-formatori"
        for record in search_payload["records"]
    )


def test_mediazione_importata_non_viene_deduplicata_come_solo_link():
    official_url = "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX"
    manager = _Manager(
        mediazione_rows=[
            {
                "registration_number": "42",
                "registry_kind": "organismo",
                "registry_section": "Organismi di mediazione",
                "name": "ADR Roma",
                "type": "Organismo privato",
                "city": "Roma",
                "province": "RM",
                "tax_code": "ABCDEF12G34H501Z",
                "email": "segreteria@example.it",
                "status": "attivo",
                "official": True,
                "source": "ministero",
                "official_registry_url": official_url,
            }
        ]
    )

    mediazione_payload = _payload(_Repository(), page="mediazione", manager=manager)
    ricerca_payload = _payload(_Repository(), page="ricerca-legale", query={"q": "ABCDEF12G34H501Z"}, manager=manager)

    mediazione_ids = {record["id"] for record in mediazione_payload["records"]}
    assert "mediazione-registro-organismi" in mediazione_ids
    assert "registro-mediazione-organismo-42" in mediazione_ids

    imported = next(record for record in mediazione_payload["records"] if record["id"] == "registro-mediazione-organismo-42")
    assert imported["sourceHref"] == official_url
    assert imported["sourceKind"] == "fonte ufficiale"
    assert imported["taxCode"] == "ABCDEF12G34H501Z"
    assert imported["email"] == "segreteria@example.it"
    assert any(record["id"] == "registro-mediazione-organismo-42" for record in ricerca_payload["records"])
