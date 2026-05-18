from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from lex.operational_knowledge.audit import OperationalAuditRecorder
from lex.operational_knowledge.permission_guard import resolve_query_context
from lex.operational_knowledge.service import OperationalKnowledgeService
from lex.operational_knowledge.settings import OperationalKnowledgeSettings
from lex.operational_knowledge.tools import OperationalKnowledgeTools
from lex.tools.registry import LexToolRegistry


class _User:
    def __init__(self, permissions: set[str], *, tenant_slug: str = "tenant-a"):
        self.id = "user-a"
        self.username = "avvocato"
        self.tenant_slug = tenant_slug
        self._permissions = set(permissions)

    @property
    def permessi_effettivi(self):
        return sorted(self._permissions)

    def ha_permesso(self, permission: str) -> bool:
        return permission in self._permissions


class _ListManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def tutti(self, *args, **kwargs):
        return list(self.rows)

    def cerca(self, query: str = "", *args, **kwargs):
        needle = str(query or "").lower().strip()
        if not needle:
            return list(self.rows)
        return [row for row in self.rows if needle in _haystack(row)]

    def get(self, identifier: str):
        for row in self.rows:
            if str(getattr(row, "id", "") or getattr(row, "numero", "")) == str(identifier):
                return row
        return None


class _FascicoliManager(_ListManager):
    pass


class _SoggettiManager(_ListManager):
    def __init__(self, rows, parti_by_fascicolo=None):
        super().__init__(rows)
        self._parti_by_fascicolo = dict(parti_by_fascicolo or {})

    def parti_fascicolo(self, fascicolo_id: str):
        return list(self._parti_by_fascicolo.get(str(fascicolo_id), []))

    def fascicoli_con_soggetto(self, soggetto_id: str):
        result = []
        for fascicolo_id, rows in self._parti_by_fascicolo.items():
            for parte, soggetto in rows:
                if str(getattr(soggetto, "id", "")) == str(soggetto_id) or str(getattr(parte, "id_soggetto", "")) == str(soggetto_id):
                    result.append(fascicolo_id)
                    break
        return result


class _PreventiviManager:
    def __init__(self, preventivi=None, conferimenti=None):
        self.preventivi = list(preventivi or [])
        self.conferimenti = list(conferimenti or [])

    def tutti_preventivi(self):
        return list(self.preventivi)

    def tutti_conferimenti(self):
        return list(self.conferimenti)

    def get_preventivo(self, identifier: str):
        return _get(self.preventivi, identifier)

    def get_conferimento(self, identifier: str):
        return _get(self.conferimenti, identifier)


class _FatturazioneManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def per_cliente(self, cliente_id: str):
        return [row for row in self.rows if getattr(row, "id_cliente", "") == cliente_id]

    def per_fascicolo(self, fascicolo_id: str):
        return [row for row in self.rows if getattr(row, "id_fascicolo", "") == fascicolo_id]


class _ScadenziarioManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def tutte(self, **kwargs):
        id_fascicolo = str(kwargs.get("id_fascicolo") or "")
        rows = [row for row in self.rows if not id_fascicolo or getattr(row, "id_fascicolo", "") == id_fascicolo]
        return rows


class _AgendaManager(_ListManager):
    def per_cliente(self, cliente_id: str):
        return [row for row in self.rows if getattr(row, "id_cliente", "") == cliente_id]


class _MessaggiManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def per_cliente(self, cliente_id: str):
        return [row for row in self.rows if getattr(row, "id_cliente", "") == cliente_id]

    def per_fascicolo(self, fascicolo_id: str):
        return [row for row in self.rows if getattr(row, "id_fascicolo", "") == fascicolo_id]


class _EmailManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def tutte(self, cartella=None, q: str = "", con_allegati: bool = False, **kwargs):
        needle = str(q or "").lower().strip()
        rows = list(self.rows)
        if cartella:
            rows = [row for row in rows if str(getattr(row, "cartella", "") or "") == str(cartella)]
        if needle:
            rows = [row for row in rows if needle in _haystack(row) or needle in str(getattr(row, "corpo_testo", "") or "").lower()]
        if con_allegati:
            rows = [row for row in rows if list(getattr(row, "allegati", []) or [])]
        return rows

    def allegato_disponibile(self, email, index: int = 0):
        allegati = list(getattr(email, "allegati", []) or [])
        if index < 0 or index >= len(allegati):
            return False
        attachment = allegati[index]
        return bool(attachment.get("archivio_membro") or attachment.get("path") or attachment.get("percorso"))


class _TemplateManager(_ListManager):
    def select_best_templates(self, query: str, limit: int = 12):
        return self.cerca(query)[:limit]


def _haystack(row) -> str:
    values = []
    for key in ("id", "nome", "cognome", "nome_completo", "titolo", "oggetto", "numero", "id_cliente"):
        values.append(str(getattr(row, key, "") or ""))
    return " ".join(values).lower()


def _get(rows, identifier: str):
    for row in rows:
        if str(getattr(row, "id", "")) == str(identifier):
            return row
    return None


def _service(*, user=None, repositories=None, audit_sink=None):
    settings = OperationalKnowledgeSettings(enabled=True, audit_enabled=False, strict_mode_enabled=True)
    tools = OperationalKnowledgeTools(repositories=repositories or {})
    audit = OperationalAuditRecorder(settings=settings, sink=audit_sink)
    return OperationalKnowledgeService(settings=settings, tools=tools, audit=audit), user or _User(_all_permissions())


def _all_permissions() -> set[str]:
    return {
        "ai.usa",
        "clienti.leggi",
        "fascicoli.leggi",
        "agenda.leggi",
        "scadenziario.leggi",
        "fatturazione.leggi",
        "messaggi.leggi",
        "telematico.leggi",
        "ai.audit",
    }


def _base_repositories():
    cliente = SimpleNamespace(
        id="cli-1",
        nome="Mario",
        cognome="Rossi",
        nome_completo="Mario Rossi",
        tipo="PERSONA_FISICA",
        stato="ATTIVO",
        codice_fiscale="RSSMRA80A01H501U",
        data_nascita="1980-01-01",
        luogo_nascita="Roma",
        provincia_nascita="RM",
        nazionalita="Italiana",
        sesso="M",
        recapiti={"email": "mario@example.test", "pec": "mario@pec.test", "telefono": "061234"},
        indirizzo_residenza={"via": "Via Roma", "civico": "10", "cap": "00100", "comune": "Roma", "provincia": "RM", "nazione": "Italia"},
        documento={"tipo": "CARTA_IDENTITA", "numero": "AA123456", "rilasciato_da": "Comune di Roma", "data_rilascio": "2020-01-01", "data_scadenza": "2030-01-01"},
        data_prima_acquisizione="2026-01-10",
        provenienza="passaparola",
        procedimenti=[{"numero_rg": "10", "anno": 2026, "tribunale": "Roma", "attivo": True}],
        tag=["privato"],
        consenso_trattamento=True,
        data_consenso="2026-01-10",
        modalita_consenso="digitale",
        campi_mancanti_per_conferimento=[],
        tenant_id="tenant-a",
    )
    fascicolo = SimpleNamespace(
        id="fas-1",
        numero="RG 10/2026",
        titolo="Rossi / Bianchi",
        oggetto="Opposizione",
        id_cliente="cli-1",
        nome_cliente="Mario Rossi",
        stato="APERTO",
        documenti=[
            SimpleNamespace(id="doc-1", nome="ricorso.pdf", tipo="ATTO", percorso="D:/segreto/ricorso.pdf", sha256="abc123"),
        ],
        tenant_id="tenant-a",
    )
    soggetto = SimpleNamespace(
        id="sog-1",
        nome="Luigi",
        cognome="Bianchi",
        nome_completo="Luigi Bianchi",
        tipo="PERSONA_FISICA",
        codice_fiscale="BNCLGU80A01H501Z",
        data_nascita="1980-01-01",
        luogo_nascita="Roma",
        provincia_nascita="RM",
        sesso="M",
        recapiti={"email": "luigi@example.test", "pec": "luigi@pec.test", "telefono": "069999"},
        indirizzo={"via": "Via Milano", "civico": "20", "cap": "00100", "comune": "Roma", "provincia": "RM", "nazione": "Italia"},
        qualifica="Controparte",
        id_cliente="",
        note="Soggetto importato dal fascicolo telematico.",
        tag=["controparte"],
        tenant_id="tenant-a",
    )
    parte = SimpleNamespace(
        id="parte-1",
        id_soggetto="sog-1",
        ruolo="CONTROPARTE",
        note="Resistente nel procedimento.",
        data_aggiunta="2026-05-01",
    )
    return {
        "clienti": _ListManager([cliente]),
        "soggetti": _SoggettiManager([soggetto], {"fas-1": [(parte, soggetto)]}),
        "fascicoli": _FascicoliManager([fascicolo]),
        "scadenziario": _ScadenziarioManager([SimpleNamespace(id="sca-1", titolo="Costituzione", id_fascicolo="fas-1", data_scadenza="2026-05-20")]),
        "agenda": _AgendaManager([SimpleNamespace(id="app-1", titolo="Udienza", id_cliente="cli-1", data_ora="2026-05-21T10:00:00")]),
        "preventivi": _PreventiviManager(
            preventivi=[SimpleNamespace(id="prev-1", oggetto="Opposizione", id_cliente="cli-1", id_pratica="fas-1", totale=1200.0)],
            conferimenti=[SimpleNamespace(id="conf-1", oggetto="Incarico opposizione", id_cliente="cli-1", id_pratica="fas-1", stato="ATTIVO")],
        ),
        "fatturazione": _FatturazioneManager([SimpleNamespace(id="par-1", numero="P-1", id_cliente="cli-1", id_fascicolo="fas-1", totale=500.0)]),
        "messaggi": _MessaggiManager([SimpleNamespace(id="msg-1", oggetto="Aggiornamento pratica", id_cliente="cli-1", id_fascicolo="fas-1", canale="PEC")]),
        "email_pec": _EmailManager([
            SimpleNamespace(
                id="pec-1",
                cartella="inbox",
                stato="non_letta",
                mittente="cancelleria@pec.test",
                mittente_nome="Cancelleria",
                destinatari=["studio@pec.test"],
                oggetto="Esito deposito",
                data="2026-05-17",
                corpo_testo="Ricevuta di consegna del deposito telematico.",
                allegati=[{"nome": "ricevuta.eml", "size": 100, "archivio_membro": "aa/ricevuta.eml", "percorso": "D:/segreto/ricevuta.eml"}],
                origine="IMAP",
                stato_pct="ACCETTATO",
                auto_registrata=True,
                tenant_id="tenant-a",
            )
        ]),
        "email_ordinaria": _EmailManager([
            SimpleNamespace(
                id="mail-1",
                cartella="inbox",
                stato="letta",
                mittente="cliente@example.test",
                destinatari=["studio@example.test"],
                oggetto="Documenti contratto",
                data="2026-05-16",
                corpo_testo="Invio documenti per il contratto di locazione.",
                allegati=[{"nome": "contratto.pdf", "size": 200, "archivio_membro": "bb/contratto.pdf", "percorso": "D:/segreto/contratto.pdf"}],
                origine="IMAP",
                tenant_id="tenant-a",
            )
        ]),
        "template_atti": _TemplateManager([SimpleNamespace(id="tpl-1", titolo="Ricorso opposizione", categoria="atti")]),
    }


def test_operational_knowledge_feature_flag_off_returns_none():
    service = OperationalKnowledgeService(settings=OperationalKnowledgeSettings(enabled=False))

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=_User(_all_permissions()), studio=SimpleNamespace(slug="tenant-a"))

    assert answer is None


def test_operational_knowledge_settings_default_on(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)

    settings = OperationalKnowledgeSettings.from_env()

    assert settings.enabled is True


def test_operational_knowledge_settings_explicit_off(monkeypatch):
    monkeypatch.setenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", "0")

    settings = OperationalKnowledgeSettings.from_env()

    assert settings.enabled is False


def test_client_retrieval_uses_real_repositories_and_sources():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Scheda cliente: Mario Rossi" in answer.answer
    assert any(source.source_id == "clienti" for source in answer.sources)
    assert any(source.source_id == "fascicoli" for source in answer.sources)
    assert "clienti.leggi" in " ".join(answer.permissions_applied)


def test_client_card_question_returns_real_customer_sheet():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Dammi la scheda cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Scheda cliente: Mario Rossi" in answer.answer
    assert "Codice fiscale: RSSMRA80A01H501U." in answer.answer
    assert "Nascita: 1980-01-01 a Roma (RM)." in answer.answer
    assert "Residenza: Via Roma 10, 00100 Roma (RM)." in answer.answer
    assert "Recapiti autorizzati: email mario@example.test; PEC mario@pec.test; telefono 061234." in answer.answer
    assert "Documento: CARTA_IDENTITA, n. AA123456" in answer.answer
    assert "Privacy: consenso trattamento registrato, data 2026-01-10, modalità digitale." in answer.answer
    assert "Procedimenti in scheda: 1." in answer.answer
    assert "Fascicoli collegati: 1" in answer.answer
    assert "Non ho trovato dati reali sufficienti" not in answer.answer


def test_subject_card_question_returns_real_party_sheet():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Dammi la scheda soggetto Bianchi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Scheda soggetto: Luigi Bianchi." in answer.answer
    assert "Codice fiscale: BNCLGU80A01H501Z." in answer.answer
    assert "Nascita: 1980-01-01 a Roma (RM)." in answer.answer
    assert "Indirizzo: Via Milano 20, 00100 Roma (RM)." in answer.answer
    assert "Recapiti autorizzati: email luigi@example.test; PEC luigi@pec.test; telefono 069999." in answer.answer
    assert "Note operative: Soggetto importato dal fascicolo telematico." in answer.answer
    assert "CONTROPARTE: Luigi Bianchi" in answer.answer
    assert any(source.source_id == "soggetti" for source in answer.sources)
    assert "Non ho trovato dati reali sufficienti" not in answer.answer


def test_parties_for_current_fascicolo_return_roles():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(
        question="Quali sono le parti del fascicolo?",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        metadata={"fascicolo_id": "fas-1"},
    )

    assert answer is not None
    assert "Parti del fascicolo: 1." in answer.answer
    assert "CONTROPARTE: Luigi Bianchi" in answer.answer
    assert "CF BNCLGU80A01H501Z" in answer.answer
    assert "Resistente nel procedimento." in answer.answer
    assert any(obj.object_type == "parte" for obj in answer.objects)


def test_client_context_id_resolves_this_client_without_guessing():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(
        question="Quali fascicoli ha questo cliente?",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        metadata={"cliente_id": "cli-1"},
    )

    assert answer is not None
    assert "Fascicoli collegati: 1" in answer.answer
    assert any(obj.object_id == "fas-1" for obj in answer.objects)


def test_tenant_isolation_excludes_other_tenant_records():
    repos = _base_repositories()
    repos["clienti"] = _ListManager([
        SimpleNamespace(id="cli-b", nome="Mario", cognome="Rossi", nome_completo="Mario Rossi", tenant_id="tenant-b"),
    ])
    service, user = _service(repositories=repos)

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"), tenant_id="tenant-a")

    assert answer is not None
    assert "Non ho trovato dati reali sufficienti" in answer.answer
    assert any("tenant diverso" in gap for gap in answer.coverage_gaps)


def test_rbac_blocks_client_without_permission():
    user = _User({"ai.usa", "fascicoli.leggi"})
    service, _ = _service(user=user, repositories=_base_repositories())

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Non ho trovato dati reali sufficienti" in answer.answer
    assert any("clienti" in gap for gap in answer.coverage_gaps)


def test_deadline_and_agenda_retrieval_are_structured():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Quali scadenze ho questa settimana?", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Scadenze consultabili" in answer.answer
    assert any(source.source_id in {"agenda", "scadenziario"} for source in answer.sources)


def test_preventivo_conferimento_and_billing_do_not_invent_amounts():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Preparami il riepilogo del preventivo opposizione", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Preventivi: 1" in answer.answer
    assert "1200" not in answer.answer or "EUR" not in answer.answer
    assert any(source.source_id == "preventivi" for source in answer.sources)


def test_tariffario_missing_parameters_returns_coverage_gap():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Quale tariffario si applica al preventivo?", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert any("materia" in gap and "grado" in gap for gap in answer.coverage_gaps)


def test_document_retrieval_does_not_expose_filesystem_paths():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Quali documenti mancano nel fascicolo Rossi?", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    payload = answer.to_dict()
    assert "D:/segreto" not in str(payload)
    assert any(source.source_id == "documenti_fascicolo" for source in answer.sources)


def test_message_retrieval_uses_tenant_internal_sources_only():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Mostrami i messaggi PEC del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert any(source.source_id == "messaggi" for source in answer.sources)
    assert "Aggiornamento pratica" in str(answer.to_dict())
    assert answer.metadata["operational_layer"] is True


def test_pec_inventory_uses_dedicated_email_source_without_paths():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Mostrami le PEC ricevute", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    payload = answer.to_dict()
    assert any(source.source_id == "email_pec" for source in answer.sources)
    assert "Esito deposito" in str(payload)
    assert "D:/segreto" not in str(payload)


def test_latest_pec_question_returns_real_latest_message_details():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Qual è l'ultima PEC?", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Ultima PEC trovata: Esito deposito." in answer.answer
    assert "Mittente: Cancelleria." in answer.answer
    assert "Data: 2026-05-17." in answer.answer
    assert "Allegati: 1." in answer.answer
    assert "Non ho trovato dati reali sufficienti" not in answer.answer


def test_ordinary_email_inventory_has_dedicated_source():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Mostrami la posta ordinaria", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert any(source.source_id == "email_ordinaria" for source in answer.sources)
    assert "Documenti contratto" in str(answer.to_dict())


def test_template_lookup_is_reported_as_template_source():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Cerca template ricorso opposizione", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert any(source.source_id == "template_atti" for source in answer.sources)


def test_rg_questione_penale_usa_archivio_legale_e_allegato_ufficiale():
    class _Repo:
        def search_lex_sources(self, query: str, limit: int = 6):
            assert "9926/2026" in query or "9926" in query
            return [
                {
                    "id": "web-evidence-754",
                    "title": "Ordinanza di rimessione",
                    "source_name": "Corte Suprema di Cassazione",
                    "official_url": "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                    "attachment_url": "https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf",
                    "excerpt": "Nota Ufficio Spoglio V Sezione penale. R.G. 9966/2026. Ordinanza di rimessione.",
                    "verified_reference": True,
                }
            ]

    class _Pipeline:
        repository = _Repo()

    repos = _base_repositories()
    repos["update_intelligence"] = _Pipeline()
    service, user = _service(repositories=repos)

    answer = service.answer(
        question="Quale allegato ufficiale ha la questione penale R.G. 9926/2026?",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
    )

    assert answer is not None
    assert answer.route.intent == "official_sources_lookup"
    assert "Allegato ufficiale trovato: Ordinanza di rimessione." in answer.answer
    assert "Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf" in answer.answer
    assert "R.G. 9926/2026" in answer.answer
    assert "R.G. 9966/2026" in answer.answer
    assert "Non ho trovato dati reali sufficienti" not in answer.answer
    assert any(source.source_id == "update_intelligence" for source in answer.sources)


def test_rg_questione_penale_non_trascina_fonti_non_pertinenti():
    class _Repo:
        def search_lex_sources(self, query: str, limit: int = 6):
            return [
                {
                    "id": "web-evidence-page",
                    "title": "Questione Penale Pendente del ricorso R.G. 9926/2026 ud. 09/07/2026",
                    "source_name": "Corte Suprema di Cassazione",
                    "official_url": "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                    "excerpt": "Questione penale pendente R.G. 9926/2026.",
                    "verified_reference": True,
                    "score": 2.0,
                },
                {
                    "id": "web-evidence-attachment",
                    "title": "Ordinanza di rimessione",
                    "source_name": "Corte Suprema di Cassazione",
                    "official_url": "https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf",
                    "attachment_url": "https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf",
                    "excerpt": "Nota Ufficio Spoglio V Sezione penale. R.G. 9966/2026. Ordinanza di rimessione.",
                    "verified_reference": True,
                    "score": 1.48,
                },
                {
                    "id": "web-evidence-noise",
                    "title": "Camera Arbitrale e di Conciliazione",
                    "source_name": "Ministero della giustizia",
                    "official_url": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
                    "excerpt": "Organismo di mediazione attivo.",
                    "verified_reference": True,
                    "score": 1.06,
                },
            ]

    class _Pipeline:
        repository = _Repo()

    repos = _base_repositories()
    repos["update_intelligence"] = _Pipeline()
    service, user = _service(repositories=repos)

    answer = service.answer(
        question="Questione Penale Pendente del ricorso R.G. 9926/2026",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
    )

    assert answer is not None
    assert "Allegato ufficiale trovato: Ordinanza di rimessione." in answer.answer
    assert "Camera Arbitrale" not in answer.answer
    assert "Nessuna fonte ufficiale citabile" not in answer.answer
    assert all("Camera Arbitrale" not in source.title for source in answer.sources)


def test_rg_questione_penale_end_to_end_da_legal_updates_db(tmp_path: Path, monkeypatch):
    from pct.legal_update_repository import LegalUpdateRepository

    monkeypatch.setattr(
        "lex.legal_sources.tools.search_legal_sources",
        lambda query, limit=6: {"data": {"passages": []}},
    )
    repo = LegalUpdateRepository(db_path=str(tmp_path / "legal_updates.db"), json_path="")
    with sqlite3.connect(repo.db_path) as conn:
        conn.executemany(
            """
            INSERT INTO web_verification_evidence (
                evidence_key, source_code, source_name, query, origin, title,
                source_url, attachment_url, attachment_type, sha256, is_official,
                context_chars, excerpt, content_text, matched_terms_json,
                verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "qsp-page",
                    "cassazione_massimario",
                    "Corte Suprema di Cassazione",
                    "Questione Penale Pendente del ricorso R.G. 9926/2026",
                    "pagina_fonte_ufficiale",
                    "Questione Penale Pendente del ricorso R.G. 9926/2026 ud. 09/07/2026",
                    "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                    "",
                    "",
                    "a" * 64,
                    1,
                    320,
                    "Questione penale pendente R.G. 9926/2026.",
                    "Questione penale pendente R.G. 9926/2026. Concordato in appello.",
                    '["questione penale", "9926/2026"]',
                    "verified",
                ),
                (
                    "qsp-attachment",
                    "cassazione_massimario",
                    "Corte Suprema di Cassazione",
                    "Questione Penale Pendente del ricorso R.G. 9926/2026",
                    "allegato_fonte_ufficiale",
                    "Ordinanza di rimessione",
                    "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                    "https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf",
                    "pdf",
                    "b" * 64,
                    1,
                    620,
                    "R.G. 9966/2026. Ordinanza di rimessione.",
                    "CORTE SUPREMA DI CASSAZIONE. Oggetto: ricorso n. 9966/2026 R.G. Ordinanza di rimessione.",
                    '["ordinanza", "rimessione", "9966/2026"]',
                    "verified",
                ),
                (
                    "fonte-non-pertinente",
                    "mediazione",
                    "Ministero della giustizia",
                    "Camera Arbitrale",
                    "pagina_fonte_ufficiale",
                    "Camera Arbitrale e di Conciliazione",
                    "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
                    "",
                    "",
                    "c" * 64,
                    1,
                    180,
                    "Organismo di mediazione attivo nel 2026.",
                    "Camera Arbitrale e di Conciliazione, organismo di mediazione attivo nel 2026.",
                    '["2026"]',
                    "verified",
                ),
            ],
        )
        conn.commit()

    class _Pipeline:
        repository = repo

    repos = _base_repositories()
    repos["update_intelligence"] = _Pipeline()
    service, user = _service(repositories=repos)

    answer = service.answer(
        question="Questione Penale Pendente del ricorso R.G. 9926/2026",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
    )

    assert answer is not None
    assert answer.route.intent == "official_sources_lookup"
    assert "Allegato ufficiale trovato: Ordinanza di rimessione." in answer.answer
    assert "Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf" in answer.answer
    assert "R.G. 9926/2026" in answer.answer
    assert "R.G. 9966/2026" in answer.answer
    assert "Camera Arbitrale" not in answer.answer
    assert "Nessuna fonte ufficiale citabile" not in answer.answer
    assert all("Camera Arbitrale" not in source.title for source in answer.sources)


def test_request_profile_non_scambia_questione_penale_rg_per_bozza_atto():
    from lex.research.request_profile import classify_request

    profile = classify_request("Questione Penale Pendente del ricorso R.G. 9926/2026")

    assert profile.intent == "giurisprudenza"
    assert profile.source_mode == "strict"
    assert profile.drafting_mode is False


def test_editor_professionale_exposes_lex_support():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(
        question="Come mi supporta Lex nell'editor professionale per una bozza?",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        metadata={"fascicolo_id": "fas-1"},
    )

    assert answer is not None
    assert any(source.source_id == "editor_ai" for source in answer.sources)
    assert "Editor Lex" in answer.answer or "Supporto disponibile" in answer.answer


def test_operational_agent_registry_copre_tutto_il_perimetro_lex():
    from lex.operational_knowledge.agents import build_default_agent_registry
    from lex.operational_knowledge.source_registry import build_default_registry

    agents = {agent.agent_id for agent in build_default_agent_registry().all()}
    sources = {source.source_id for source in build_default_registry().all()}

    assert {
        "fascicoli_documenti_timeline",
        "redazione_atti_editor",
        "giurisprudenza_cassazione",
        "pct_depositi_telematici",
        "ai_locale_rag_runtime",
    }.issubset(agents)
    assert {
        "citazioni_cassazione",
        "chat_lex_editor",
        "pdf_manager",
        "firma_digitale",
        "fatturazione_elettronica_sdi",
        "client_portal",
        "antiriciclaggio",
        "rest_api_webhooks",
    }.issubset(sources)


def test_legal_action_request_is_blocked():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Invia PEC al cliente Rossi e deposita l'atto", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert answer.blocked_reason == "legal_action_blocked"
    assert "Non posso eseguire direttamente" in answer.answer


def test_audit_event_is_recorded_to_in_memory_sink():
    sink = []
    service, user = _service(repositories=_base_repositories(), audit_sink=sink)

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert answer.audit_event_id == "memory:1"
    assert sink[0]["route"] == "client_situation"
    assert sink[0]["tenant"] == "tenant-a"


def test_internal_customer_query_does_not_call_legal_source_web(monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("fonti ufficiali non devono essere chiamate per dati cliente")

    monkeypatch.setattr("lex.legal_sources.tools.search_legal_sources", _forbidden)
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert answer.metadata["operational_layer"] is True


def test_permission_guard_requires_ai_usa():
    user = _User({"clienti.leggi"})
    context = resolve_query_context(user=user, studio=SimpleNamespace(slug="tenant-a"))
    tools = OperationalKnowledgeTools(repositories=_base_repositories())

    result = tools.search_clienti("Rossi", context)

    assert not result.ok
    assert result.permission is not None
    assert "ai.usa" in result.permission.missing_permissions


def test_tool_registry_exposes_operational_knowledge_tool_default_on(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    registry = LexToolRegistry()

    result = registry.tools["operational_knowledge"].run(
        question="Mostrami il cliente Rossi",
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
    )

    assert result["ok"] is True
    assert result["workflow"] == "operational_knowledge"


def test_tool_registry_can_disable_operational_knowledge(monkeypatch):
    monkeypatch.setenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", "0")
    registry = LexToolRegistry()

    result = registry.tools["operational_knowledge"].run(question="Mostrami il cliente Rossi")

    assert result == {"ok": False, "reason": "feature_flag_disabled"}


def test_http_bridge_operational_layer_handles_studio_data_by_default(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            return OperationalAnswer(
                handled=True,
                answer="Cliente: Mario Rossi.",
                route=OperationalRoute("client_situation", "client_situation", ("clienti",), "rossi"),
                sources=[
                    OperationalSourceReference(
                        source_id="clienti",
                        source_name="Clienti",
                        source_type="studio",
                        object_type="cliente",
                        object_id="cli-1",
                        title="Mario Rossi",
                        confidence=0.86,
                    )
                ],
                confidence=0.86,
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={},
        current_user_message="Mostrami la situazione del cliente Rossi",
        resolved_effective_question="Mostrami la situazione del cliente Rossi",
        studio_context={"focus_topic": "clienti", "request_profile": {"intent": "cliente_anagrafica"}},
    )

    assert payload is not None
    assert payload["workflow"] == "operational_knowledge"
    assert payload["provider"] == "deterministic"


def test_http_bridge_routes_pec_lookup_to_operational_layer(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            return OperationalAnswer(
                handled=True,
                answer="Ultima PEC trovata: Esito deposito.",
                route=OperationalRoute("communications_lookup", "communications_lookup", ("email_pec",), ""),
                sources=[
                    OperationalSourceReference(
                        source_id="email_pec",
                        source_name="Email PEC",
                        source_type="email_pec",
                        object_type="email",
                        object_id="pec-1",
                        title="Esito deposito",
                        confidence=0.86,
                    )
                ],
                confidence=0.86,
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={},
        current_user_message="Qual è l'ultima PEC?",
        resolved_effective_question="Qual è l'ultima PEC?",
        studio_context={"focus_topic": "pec_firma", "request_profile": {"intent": "pec_comunicazioni"}},
    )

    assert payload is not None
    assert payload["workflow"] == "operational_knowledge"
    assert payload["answer"] == "Ultima PEC trovata: Esito deposito."


def test_http_bridge_defers_specific_case_law_to_public_research(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"external_sources_reason": "riferimento giurisprudenziale esatto"},
        current_user_message="Mi puoi trovare questa Sentenza n. 7919 del 31/03/2026?",
        resolved_effective_question="Mi puoi trovare questa Sentenza n. 7919 del 31/03/2026?",
        studio_context={"focus_topic": "sentenze_web", "request_profile": {"intent": "giurisprudenza_specifica"}},
    )

    assert payload is None


def test_http_bridge_non_devia_questione_penale_rg_in_bozza_atto(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            assert kwargs["metadata"]["request_profile"]["intent"] == "bozza_atto"
            return OperationalAnswer(
                handled=True,
                answer=(
                    "Allegato ufficiale trovato: Ordinanza di rimessione.\n"
                    "PDF: Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf."
                ),
                route=OperationalRoute(
                    "official_sources_lookup",
                    "official_sources_lookup",
                    ("fonti_ufficiali", "legal_intelligence", "update_intelligence"),
                    "questione penale r.g. 9926/2026",
                ),
                sources=[
                    OperationalSourceReference(
                        source_id="update_intelligence",
                        source_name="Fonti ufficiali",
                        source_type="public_source",
                        object_type="legal_update",
                        object_id="web-evidence-754",
                        title="Ordinanza di rimessione",
                        confidence=0.91,
                    )
                ],
                confidence=0.91,
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={},
        current_user_message="Questione Penale Pendente del ricorso R.G. 9926/2026",
        resolved_effective_question="Questione Penale Pendente del ricorso R.G. 9926/2026",
        studio_context={"focus_topic": "sentenze_web", "request_profile": {"intent": "bozza_atto", "drafting_mode": True}},
    )

    assert payload is not None
    assert payload["workflow"] == "operational_knowledge"
    assert "Allegato ufficiale trovato: Ordinanza di rimessione." in payload["answer"]
    assert "Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf" in payload["answer"]


def test_http_bridge_defers_without_permission_context(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload

    payload = build_operational_http_payload(
        user=SimpleNamespace(username="utente-senza-contesto-permessi"),
        studio=SimpleNamespace(slug="tenant-a"),
        data={},
        current_user_message="Che cosa devo fare oggi?",
        resolved_effective_question="Che cosa devo fare oggi?",
        studio_context={"request_profile": {"intent": ""}},
    )

    assert payload is None


def test_response_composer_reports_coverage_gap_for_absent_data():
    service, user = _service(repositories={"clienti": _ListManager([])})

    answer = service.answer(question="Mostrami la situazione del cliente Rossi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert answer.confidence < 0.55
    assert answer.coverage_gaps


def test_operational_agent_prepara_archivio_pdp_penale_tenant_aware(tmp_path: Path):
    from lex.operational_knowledge.nightly_agents import run_operational_micro_agent

    telematico_db = tmp_path / "tenant" / "telematico" / "workflow.db"
    email_db = tmp_path / "tenant" / "email" / "casella.json"
    pdp_db = tmp_path / "tenant" / "penale" / "pdp_penale.db"
    telematico_db.parent.mkdir(parents=True)
    telematico_db.write_bytes(b"")
    email_db.parent.mkdir(parents=True)
    email_db.write_text("{}", encoding="utf-8")

    result = run_operational_micro_agent(
        agent_id="pct_depositi_telematici",
        config={
            "TELEMATICO_DB": str(telematico_db),
            "EMAIL_CASELLA_DB": str(email_db),
            "PDP_PENALE_DB": str(pdp_db),
            "LEX_OPERATIONAL_AGENTS_DB": str(tmp_path / "runs" / "lex_operational_agents.json"),
        },
        required_path_keys=["TELEMATICO_DB", "PDP_PENALE_DB", "EMAIL_CASELLA_DB"],
    )

    assert result["ok"] is True
    assert pdp_db.exists()
    with sqlite3.connect(str(pdp_db)) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "criminal_cases" in tables
