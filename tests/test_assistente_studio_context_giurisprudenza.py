from web.services.assistente_studio_context import _aggiornamenti_legali_lines, _archivio_sentenze_lines, _ricerca_legale_lines


class _DummyGiurisprudenza:
    def statistiche(self):
        return {
            "totale_sentenze": 14,
            "fonti_attive": 5,
            "corpus_sentenze": 7,
        }

    def cerca(self, q: str = ""):
        return [
            {
                "id": "json-1",
                "titolo": "Cassazione su responsabilita medica",
                "area": "Civile",
                "branca": "Responsabilita civile",
                "massima": "Massima archivio locale.",
                "stato_verifica_fonte": "parzialmente_verificata",
                "url_pagina_ufficiale": "https://www.cortedicassazione.it/archivio-locale",
                "url_pdf_ufficiale": "",
                "pdf_ufficiale_presente": False,
                "organo_giudicante": "Corte di Cassazione",
                "numero_provvedimento": "321/2026",
                "anno": "2026",
            }
        ]

    def statistiche_repository(self):
        return {
            "giurisprudenza_sources_repository": 11,
            "giurisprudenza_taxonomy_repository": 120,
            "giurisprudenza_sync_registry": 11,
        }

    def cerca_corpus_professionale(self, **kwargs):
        return [
            {
                "id": 101,
                "titolo": "Cassazione su consenso informato",
                "organo_giudicante": "Corte di Cassazione",
                "sezione": "Sez. III",
                "numero_sentenza": "1234",
                "anno_sentenza": 2026,
                "stato_verifica": "verificata",
                "url_pagina_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026",
                "url_pdf_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026.pdf",
                "principio_sintetico": "Il consenso informato va provato in modo specifico.",
                "massima_ufficiale": "Massima ufficiale.",
                "abstract": "Abstract strutturato.",
                "pdf_ufficiale_presente": 1,
                "ecli": "ECLI:IT:CASS:2026:1234",
            }
        ]

    def scheda_corpus_professionale(self, sentenza_id):
        return {
            "id": int(sentenza_id),
            "titolo": "Cassazione su consenso informato",
            "organo_giudicante": "Corte di Cassazione",
            "sezione": "Sez. III",
            "numero_sentenza": "1234",
            "anno_sentenza": 2026,
            "stato_verifica": "verificata",
            "url_pagina_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026",
            "url_pdf_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026.pdf",
            "principio_sintetico": "Il consenso informato va provato in modo specifico.",
            "massima_ufficiale": "Massima ufficiale.",
            "abstract": "Abstract strutturato.",
            "pdf_ufficiale_presente": 1,
            "ecli": "ECLI:IT:CASS:2026:1234",
        }

    def riferimento_professionale_verificato(self, sentenza_id):
        return True

    def pdf_professionale_disponibile(self, sentenza_id):
        return True

    def resolve_lex_giurisprudenza_route(self, question):
        return {
            "preferred_area_title": "Civile",
            "preferred_branch_title": "Responsabilita civile",
            "preferred_subbranch_title": "Responsabilita medica",
            "route_mode": "corpus_e_sync_pubblico",
            "reason": "corpus professionale come primo livello; area: Civile",
            "source_rows": [
                {
                    "source_id": "cassazione",
                    "nome": "Corte di Cassazione",
                    "giurisdizione": "Ordinaria",
                    "coverage": "Legittimita, massimario e principi di diritto.",
                    "official_url": "https://www.cortedicassazione.it/",
                    "search_url": "https://www.cortedicassazione.it/it/massimario.page",
                    "access_mode": "pubblico",
                    "sync_mode": "automatico_leggero",
                    "supports_auto_sync": True,
                    "judgment_count": 3,
                    "route_bias": "corpus_e_sync_pubblico",
                }
            ],
            "sync_rows": [
                {
                    "source_id": "cassazione",
                    "source_name": "Corte di Cassazione",
                    "last_status": "ok",
                }
            ],
            "corpus_rows": self.cerca_corpus_professionale(q=question),
            "archive_rows": self.cerca(q=question),
        }


class _DummyLegalUpdatesRepository:
    db_path = "/data/tenants/studio/intelligence/legal_updates.db"

    def search_lex_sources(self, question, limit=6):
        return [
            {
                "type": "giurisprudenza",
                "id": "legal-updates-jurisprudence:1",
                "title": "Cassazione su responsabilita medica",
                "excerpt": "Principio SQL pubblicato.",
                "content": "Principio SQL pubblicato.",
                "score": 0.91,
                "authority": "Corte di Cassazione",
                "official_url": "https://www.cortedicassazione.it/sentenza-1",
                "published_at": "2026-05-03",
                "trust_class": "A",
                "source_level": 1,
                "verified_reference": True,
                "repository": "legal_updates_sql",
                "entity_type": "jurisprudence",
            }
        ]


class _DummyLegalUpdatesPipeline:
    repository = _DummyLegalUpdatesRepository()

    def dashboard_snapshot(self):
        return {
            "headline": {
                "sources": 11,
                "raw_documents": 794,
                "analyses": 794,
                "review_pending": 207,
                "published_news": 323,
                "published_normative": 12,
                "published_jurisprudence": 40,
                "published_prassi": 2,
            },
            "sources": [
                {
                    "name": "Cassazione Massimario",
                    "code": "cassazione_massimario",
                    "category": "giurisprudenza",
                    "trust_class": "A",
                }
            ],
        }


class _DummyLegalIntelligence:
    def resolve_lex_legal_route(self, question):
        return {
            "reason": "routing mediazione",
            "engine_ids": ["fonti_ufficiali"],
            "source_ids": ["registro_mediazione"],
            "engine_rows": [],
            "source_rows": [
                {
                    "source_id": "registro_mediazione",
                    "nome": "Registro organismi di mediazione",
                    "area": "ADR / mediazione civile",
                    "motore": "fonti_ufficiali",
                    "capability": "Registro ufficiale organismi.",
                    "official_url": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
                    "monitor_url": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
                }
            ],
            "monitoring_rows": [],
            "alert_rows": [],
        }

    def statistiche_repository(self):
        return {
            "legal_sources_repository": 1,
            "legal_engines_repository": 1,
            "legal_keyword_to_engine": 1,
            "legal_keyword_to_source": 1,
            "legal_operational_repository": 1,
        }

    def build_dashboard_snapshot(self, **kwargs):
        return {"headline": {}}

    def lex_mediazione_registry_sources(self, question, limit=4):
        return [
            {
                "type": "registro_mediazione",
                "id": "registro-mediazione:1",
                "title": "ADR Center srl",
                "excerpt": "Organismo ADR Center srl numero registro 1 stato attivo.",
                "content": "Organismo ADR Center srl numero registro 1 stato attivo.",
                "score": 0.9,
                "authority": "Ministero della Giustizia",
                "official_url": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
                "trust_class": "A",
                "source_level": 1,
                "verified_reference": True,
                "registration_number": "1",
                "registry_status": "attivo",
            }
        ]


def test_aggiornamenti_legali_lines_usa_repository_sql_per_lex(monkeypatch):
    monkeypatch.setattr(
        "web.services.assistente_studio_context.build_legal_update_pipeline_runtime",
        lambda: _DummyLegalUpdatesPipeline(),
    )

    lines, sources = _aggiornamenti_legali_lines("ultimi aggiornamenti Cassazione")

    assert any("Aggiornamenti legali condivisi" in line for line in lines)
    assert any("Lex AI legge gli aggiornamenti da legal_updates.db" in line for line in lines)
    assert any("Cassazione su responsabilita medica" in line for line in lines)
    assert any(source["id"] == "legal-updates:dashboard" for source in sources)
    assert any(source.get("repository") == "legal_updates_sql" for source in sources)
    assert not any(str(source.get("db_path", "")).endswith(".json") for source in sources)


def test_ricerca_legale_lines_espone_registro_mediazione_a_lex(monkeypatch):
    monkeypatch.setattr(
        "web.services.assistente_studio_context.get_legal_intelligence",
        lambda: _DummyLegalIntelligence(),
    )

    lines, sources = _ricerca_legale_lines("ADR Center registro mediazione")

    assert any("Registro mediazione interno" in line for line in lines)
    assert any("ADR Center srl" in line for line in lines)
    assert any(source["id"] == "registro-mediazione:1" for source in sources)
    registry_source = next(source for source in sources if source["id"] == "registro-mediazione:1")
    assert registry_source["trust_class"] == "A"
    assert registry_source["verified_reference"] is True


def test_archivio_sentenze_lines_integra_corpus_professionale(monkeypatch):
    monkeypatch.setattr(
        "web.services.assistente_studio_context.get_giurisprudenza",
        lambda: _DummyGiurisprudenza(),
    )

    lines, sources = _archivio_sentenze_lines("consenso informato")

    assert any("Corpus professionale: 7 schede strutturate." in line for line in lines)
    assert any("Repository giurisprudenza:" in line for line in lines)
    assert any("Routing giurisprudenza:" in line for line in lines)
    assert any("Corpus giurisprudenziale verificabile:" in line for line in lines)
    assert any(source["id"] == "giurisprudenza:repository" for source in sources)
    assert any(source["id"] == "giurisprudenza-fonte:cassazione" for source in sources)
    assert any(source["id"] == "corpus-sentenza:101" for source in sources)
    assert any(source.get("verified_reference") is True for source in sources if source["id"] == "corpus-sentenza:101")
    assert any(source.get("downloadable_pdf") is True for source in sources if source["id"] == "corpus-sentenza:101")
