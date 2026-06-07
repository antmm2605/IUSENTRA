from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from lex.operational_knowledge.audit import OperationalAuditRecorder
from lex.operational_knowledge.models import OperationalQueryContext
from lex.operational_knowledge.permission_guard import resolve_query_context
from lex.operational_knowledge.query_router import OperationalQueryRouter
from lex.operational_knowledge.service import OperationalKnowledgeService
from lex.operational_knowledge.settings import OperationalKnowledgeSettings
from lex.operational_knowledge.tools import OperationalKnowledgeTools
from lex.tools.registry import LexToolRegistry

RAW_VISIBLE_DATE_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}(?:(?:T|\s)\d{2}:\d{2}(?::\d{2})?)?\b")
ITALIAN_MONTH_RE = re.compile(
    r"\b\d{1,2}\s+"
    r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
    r"\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)

QSP_ATTACHMENT_OCR_TEXT = (
    "CORTE SUPREMA DI CASSAZIONE QUINTA SEZIONE PENALE. Oggetto: ricorso n. 9966/2026 R.G. "
    "E' pervenuto all'esame preliminare di questo Ufficio il ricorso RG 9966/26, proposto nell'interesse "
    "di Gianfranco Greco avverso la sentenza della Corte d'appello di Caltanissetta del 10 ottobre 2025, "
    "con la quale, in parziale riforma della decisione del Tribunale di Gela del 19 novembre 2024, è stata "
    "rideterminata la pena per furto aggravato consumato e tentato e inosservanza delle prescrizioni della "
    "sorveglianza speciale, nella misura di anni due e mesi otto di reclusione ed euro 1.236,00 di multa, "
    "concordata tra le parti ex art. 599-bis cod. proc. pen. "
    "1.1. Dalla proposta di concordato la pena risulta così determinata: pena base, anni due di reclusione "
    "ed euro 927,00 di multa; pena elevata per effetto della continuazione sino alla misura conclusivamente "
    "indicata di anni due e mesi otto di reclusione ed euro 1.236,00 di multa. "
    "1.2. Il ricorrente deduce, con quattro motivi, le seguenti censure: - l'illegalità della pena, per non "
    "essere stato motivato il giudizio di comparazione tra la recidiva e le ulteriori circostanze; - il difetto "
    "di controllo giudiziale sull'accordo; - la motivazione apparente in ordine all'esclusione di cause di "
    "proscioglimento ex art. 129 cod. proc. pen.; - la violazione dei limiti del concordato per omessa indicazione "
    "in ordine al bilanciamento tra circostanze eterogenee, l'incidenza della recidiva e la determinazione della "
    "pena finale. Al netto del riferimento nominalistico alla illegalità della pena, il ricorso pone il tema della "
    "deducibilità dell'erronea determinazione della sanzione, concordata tra le parti ex art. 599-bis cod. proc. pen., "
    "sul quale si registra un contrasto nella giurisprudenza di questa Corte, con richiamo all'art. 81, comma secondo, "
    "cod. pen. per la continuazione."
)


@pytest.fixture(autouse=True)
def _stable_lex_reference_date(monkeypatch):
    monkeypatch.setenv("IUSENTRA_LEX_REFERENCE_DATE", "2026-05-20")


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


class _PagamentiManager:
    def __init__(self, rows):
        self.rows = list(rows)

    def tutti_link(self):
        return list(self.rows)

    def link_per_cliente(self, cliente_id: str):
        return [row for row in self.rows if getattr(row, "id_cliente", "") == cliente_id]

    def link_per_parcella(self, parcella_id: str):
        return [row for row in self.rows if getattr(row, "id_parcella", "") == parcella_id]


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
        data_apertura="2026-05-01",
        documenti=[
            SimpleNamespace(
                id="doc-1",
                nome="ricorso.pdf",
                tipo="ATTO",
                percorso="D:/segreto/ricorso.pdf",
                sha256="abc123",
                data_caricamento="2026-05-10",
            ),
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
        "pagamenti": _PagamentiManager([
            SimpleNamespace(
                id="pay-1",
                id_parcella="par-1",
                id_cliente="cli-1",
                importo=500.0,
                descrizione="Saldo parcella P-1",
                stato="ATTESO",
                creato_il="2026-05-18T10:00:00",
                valuta="EUR",
                tenant_id="tenant-a",
            )
        ]),
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
                id_cliente="cli-1",
                id_fascicolo="fas-1",
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
                id_cliente="cli-1",
                id_fascicolo="fas-1",
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


def test_operational_knowledge_document_analysis_usa_testo_indicizzato():
    repositories = _base_repositories()
    fascicolo = repositories["fascicoli"].rows[0]
    fascicolo.documenti[0].anteprima = (
        "Il ricorso espone opposizione a decreto ingiuntivo, eccezione sulla prova del credito "
        "e richiesta di sospensione della provvisoria esecutorietà."
    )
    service, user = _service(repositories=repositories)

    answer = service.answer(
        question="Fammi una sintesi del fascicolo attivo: documenti chiave, rischi aperti, cosa manca e prossimi passi.",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        metadata={"active_context": {"context_type": "case", "case_id": "fas-1", "client_id": "cli-1"}},
    )

    assert answer is not None
    assert "Sintesi operativa per l'avvocato" in answer.answer
    assert "Documenti chiave letti o indicizzati" in answer.answer
    assert "Rischi aperti da presidiare" in answer.answer
    assert "Cosa manca o va confermato" in answer.answer
    assert "Prossimi passi operativi" in answer.answer
    assert "opposizione a decreto ingiuntivo" in answer.answer
    assert "non invento contenuti" not in answer.answer


def test_operational_knowledge_fascicolo_attivo_da_page_path_js_usa_fonti_reali():
    repositories = _base_repositories()
    fascicolo = repositories["fascicoli"].rows[0]
    fascicolo.documenti[0].anteprima = (
        "Il fascicolo contiene opposizione a decreto ingiuntivo, rischio di decadenza "
        "e necessita di verificare la procura alle liti prima del prossimo deposito."
    )
    service, user = _service(repositories=repositories)

    answer = service.answer(
        question="Fammi una sintesi del fascicolo attivo: documenti chiave, rischi aperti, cosa manca e prossimi passi.",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        metadata={"pagePath": "/fascicoli/fas-1", "context": "fascicolo-dettaglio"},
    )

    assert answer is not None
    assert answer.route is not None
    assert answer.route.intent == "fascicolo_summary"
    assert "Fascicolo: Rossi / Bianchi" in answer.answer
    assert "Sintesi operativa per l'avvocato" in answer.answer
    assert "Documenti chiave letti o indicizzati" in answer.answer
    assert "Rischi aperti da presidiare" in answer.answer
    assert "Cosa manca o va confermato" in answer.answer
    assert "Prossimi passi operativi" in answer.answer
    assert "rischio di decadenza" in answer.answer
    assert "Non ho trovato dati reali sufficienti" not in answer.answer


def test_operational_knowledge_document_analysis_legge_file_fascicolo_se_indice_ai_manca(tmp_path: Path):
    repositories = _base_repositories()
    fascicolo = repositories["fascicoli"].rows[0]
    fascicolo.documenti[0].anteprima = ""
    fascicolo.documenti[0].summary = ""
    fascicolo.documenti[0].percorso = "fas-1/ricorso.txt"
    documents_dir = tmp_path / "documenti"
    document_path = documents_dir / "fas-1" / "ricorso.txt"
    document_path.parent.mkdir(parents=True)
    document_path.write_text(
        "Il fascicolo Betti C. MIM contiene contratti scolastici, rischio di decadenza "
        "e termine lungo di impugnazione da presidiare.",
        encoding="utf-8",
    )
    repositories["fascicoli"].documents_dir = documents_dir
    service, user = _service(repositories=repositories)

    answer = service.answer(
        question="Fammi una sintesi del fascicolo attivo: documenti chiave, rischi aperti, cosa manca e prossimi passi.",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        metadata={"active_context": {"context_type": "case", "case_id": "fas-1", "client_id": "cli-1"}},
    )

    assert answer is not None
    assert "Sintesi operativa per l'avvocato" in answer.answer
    assert "Documenti chiave letti o indicizzati" in answer.answer
    assert "Rischi aperti da presidiare" in answer.answer
    assert "Cosa manca o va confermato" in answer.answer
    assert "Prossimi passi operativi" in answer.answer
    assert "contratti scolastici" in answer.answer
    assert "termine lungo di impugnazione" in answer.answer
    assert "Il testo integrale non risulta disponibile" not in answer.answer


def test_operational_knowledge_sintesi_fascicolo_scolastico_mim_ragiona_da_avvocato():
    repositories = _base_repositories()
    fascicolo = repositories["fascicoli"].rows[0]
    fascicolo.titolo = "Betti C. MIM"
    fascicolo.oggetto = "Contratti scolastici a tempo determinato e servizio presso istituti statali"
    fascicolo.nome_cliente = "Betti"
    fascicolo.controparte = "Ministero dell'Istruzione e del Merito"
    fascicolo.documenti = [
        SimpleNamespace(
            id="doc-contratto-2022",
            nome="contratto_scuola_2022.pdf",
            tipo="CONTRATTO",
            sha256="a" * 64,
            data_caricamento="2026-06-01",
            anteprima="Contratto individuale di lavoro a tempo determinato presso istituto scolastico statale, docente, Ministero dell'Istruzione e del Merito.",
        ),
        SimpleNamespace(
            id="doc-contratto-2023",
            nome="contratto_scuola_2023.pdf",
            tipo="CONTRATTO",
            sha256="b" * 64,
            data_caricamento="2026-06-01",
            anteprima="Contratti scolastici annuali e servizio prestato presso istituto statale; verificare prescrizione e differenze retributive.",
        ),
    ]
    service, user = _service(repositories=repositories)

    answer = service.answer(
        question="Fammi una sintesi del fascicolo attivo: documenti chiave, rischi aperti, cosa manca e prossimi passi.",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
        metadata={"active_context": {"context_type": "case", "case_id": "fas-1", "client_id": "cli-1"}},
    )

    assert answer is not None
    assert answer.route.intent == "fascicolo_summary"
    assert "Betti C. MIM" in answer.answer
    assert "Sintesi operativa per l'avvocato" in answer.answer
    assert "pratica scolastica/lavoro pubblico" in answer.answer
    assert "Documenti chiave letti o indicizzati" in answer.answer
    assert "contratto_scuola_2022.pdf" in answer.answer
    assert "Rischi aperti da presidiare" in answer.answer
    assert "annualità di servizio" in answer.answer
    assert "stato di servizio completo" in answer.answer
    assert "Prossimi passi operativi" in answer.answer
    assert "scegliere domanda praticabile" in answer.answer
    assert "Non ho trovato dati reali sufficienti" not in answer.answer


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
    assert "Nascita: 1 gennaio 1980 a Roma (RM)." in answer.answer
    assert "Residenza: Via Roma 10, 00100 Roma (RM)." in answer.answer
    assert "Recapiti autorizzati: email mario@example.test; PEC mario@pec.test; telefono 061234." in answer.answer
    assert "Documento: CARTA_IDENTITA, n. AA123456" in answer.answer
    assert "Privacy: consenso trattamento registrato, data 10 gennaio 2026, modalità digitale." in answer.answer
    assert "Procedimenti in scheda: 1." in answer.answer
    assert "Fascicoli collegati: 1" in answer.answer
    assert "Non ho trovato dati reali sufficienti" not in answer.answer


def test_subject_card_question_returns_real_party_sheet():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Dammi la scheda soggetto Bianchi", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Scheda soggetto: Luigi Bianchi." in answer.answer
    assert "Codice fiscale: BNCLGU80A01H501Z." in answer.answer
    assert "Nascita: 1 gennaio 1980 a Roma (RM)." in answer.answer
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


def test_scadenziario_non_filtra_studio_id_tecnico_come_tenant():
    repositories = _base_repositories()
    repositories["scadenziario"] = _ScadenziarioManager(
        [
            SimpleNamespace(
                id="sca-pec-1",
                titolo="Udienza da PEC",
                data_scadenza="2026-07-09",
                note="PEC_AUDIT:pec-test",
                studio_id="default-studio",
            )
        ]
    )
    service, user = _service(repositories=repositories)

    answer = service.answer(question="Quali scadenze ho questa settimana?", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Scadenze consultabili: 1" in answer.answer
    assert "Udienza da PEC" in answer.answer
    assert not any("tenant diverso" in gap for gap in answer.coverage_gaps)


def test_all_scadenze_passa_contesto_tenant_al_manager():
    service, user = _service(repositories={})
    calls: list[str] = []

    def fake_manager(source_id: str, helper_name: str, context=None):
        calls.append(str(getattr(context, "tenant_id", "") or ""))
        assert source_id == "scadenziario"
        assert helper_name == "get_scadenziario"
        return _ScadenziarioManager(
            [
                SimpleNamespace(
                    id="sca-tenant-1",
                    titolo="Presidio PEC tenant",
                    data_scadenza="2026-07-09",
                    note="PEC_AUDIT:pec-tenant",
                )
            ]
        )

    service.tools._manager = fake_manager
    context = OperationalQueryContext(
        tenant_id="tenant-a",
        user_id=user.id,
        user=user,
        permissions=_all_permissions(),
    )

    result = service._all_scadenze(context)

    assert result.ok
    assert calls == ["tenant-a"]
    assert result.data[0]["titolo"] == "Presidio PEC tenant"


def test_lex_operational_knowledge_include_db_normativa_operativo():
    class _NormativeTables:
        def snapshot(self):
            return {
                "tabelle": [
                    {
                        "id": "interesse_legale",
                        "title": "Interessi legali",
                        "category": "tassi",
                        "description": "Saggi di interesse legale per periodo di validità.",
                        "sync_status": "sincronizzata",
                        "last_synced_at": "2026-06-06T09:00:00",
                        "sources": [
                            {
                                "code": "interesse_legale_2026",
                                "title": "Gazzetta Ufficiale - saggio interessi legali 2026",
                                "url": "https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.codiceRedazionale=25A06705",
                            }
                        ],
                    }
                ]
            }

        def rows(self, table_id: str):
            assert table_id == "interesse_legale"
            return [
                {
                    "label": "Interesse legale 2026",
                    "start": "2026-01-01",
                    "end": "2026-12-31",
                    "rate": 1.6,
                }
            ]

        def catalogo_riferimenti_normativi(self):
            return [
                {
                    "reference_code": "dm_55_parametri_compensi",
                    "title": "D.M. 55/2014 - parametri compensi forensi",
                    "article": "artt. 1-29",
                    "description": "Parametri per fasi, valore, preventivo, liquidazione e presidio deontologico.",
                    "url": "https://www.normattiva.it/",
                }
            ]

    class _LegalIntelligence:
        normative_tables = _NormativeTables()

        def recent_alerts(self, limit=12):
            return []

        def catalogo_fonti(self):
            return []

    tools = OperationalKnowledgeTools(repositories={"legal_intelligence": _LegalIntelligence()})
    user = _User(_all_permissions())
    context = OperationalQueryContext(
        tenant_id="tenant-a",
        user_id=user.id,
        user=user,
        permissions=_all_permissions(),
    )

    interessi = tools.get_legal_intelligence_items("interesse legale 2026", context, limit=5)
    assert interessi.ok
    table = next(item for item in interessi.data if item["kind"] == "tabella_normativa")
    assert table["id"] == "interesse_legale"
    assert table["fonti"][0]["codice"] == "interesse_legale_2026"
    assert table["righe_campione"][0]["label"] == "Interesse legale 2026"
    assert "calcolare interessi" in table["uso_operativo"]
    assert any("decorrenza" in check for check in table["controlli_lex"])

    compensi = tools.get_legal_intelligence_items("parametri compensi", context, limit=5)
    assert compensi.ok
    reference = next(item for item in compensi.data if item["kind"] == "riferimento_normativo")
    assert reference["id"] == "dm_55_parametri_compensi"
    assert "modello" in reference["uso_operativo"]
    assert any("testo vigente" in check for check in reference["controlli_lex"])


def test_lex_operational_knowledge_cerca_matrice_pratica_legale():
    tools = OperationalKnowledgeTools()
    user = _User(_all_permissions())
    context = OperationalQueryContext(
        tenant_id="tenant-a",
        user_id=user.id,
        user=user,
        permissions=_all_permissions(),
    )

    amministrativo = tools.search_legal_practice_matrix(
        "ricorso TAR calendario udienze decreti sentenze",
        context,
        limit=10,
    )
    penale = tools.search_legal_practice_matrix("PDP penale Cartabia", context, limit=10)
    lavoro = tools.search_legal_practice_matrix("licenziamento rito lavoro", context, limit=10)
    scolastico = tools.search_legal_practice_matrix(
        "sostegno scolastico PEI graduatoria docente ricorso TAR MIM",
        context,
        limit=10,
    )
    pubblico = tools.search_legal_practice_matrix(
        "concorso pubblico inPA graduatoria D.Lgs. 165 DPR 487",
        context,
        limit=10,
    )
    immigrazione = tools.search_legal_practice_matrix(
        "protezione internazionale cittadinanza permesso soggiorno Ministero Interno",
        context,
        limit=10,
    )

    assert amministrativo.ok
    assert penale.ok
    assert lavoro.ok
    assert scolastico.ok
    assert pubblico.ok
    assert immigrazione.ok
    amministrativo_ids = {item["id"] for item in amministrativo.data}
    penale_ids = {item["id"] for item in penale.data}
    lavoro_ids = {item["id"] for item in lavoro.data}
    scolastico_ids = {item["id"] for item in scolastico.data}
    pubblico_ids = {item["id"] for item in pubblico.data}
    immigrazione_ids = {item["id"] for item in immigrazione.data}
    assert "amministrativo_tar_cds_appalti" in amministrativo_ids
    assert "openga_calendario_udienze" in amministrativo_ids
    assert "openga_decreti_ordinanze_sentenze" in amministrativo_ids
    assert "penale_difesa_rito_pdp" in penale_ids
    assert "dlgs_150_2022_cartabia_penale" in penale_ids
    assert "pdp_penale_pst" in penale_ids
    assert "lavoro_previdenza_inps_inail" in lavoro_ids
    assert "legge_300_1970_statuto_lavoratori" in lavoro_ids
    assert "legge_604_1966_licenziamenti" in lavoro_ids
    assert "scolastico_docenti_alunni_concorsi" in scolastico_ids
    assert "dlgs_297_1994_testo_unico_scuola" in scolastico_ids
    assert "dlgs_66_2017_inclusione_scolastica" in scolastico_ids
    assert "pubblico_impiego_concorsi_mobilita" in pubblico_ids
    assert "inpa_portale_reclutamento" in pubblico_ids
    assert "dpr_487_1994_concorsi_pubblici" in pubblico_ids
    assert "immigrazione_cittadinanza_protezione" in immigrazione_ids
    assert "dlgs_286_1998_testo_unico_immigrazione" in immigrazione_ids
    assert "dlgs_25_2008_protezione_internazionale" in immigrazione_ids
    assert all(item.get("action_url") == "/ricerca-legale" for item in amministrativo.data)


def test_lex_tools_dispatcher_cerca_matrice_pratica_legale():
    from lex.tools.legal_studio_tools import dispatch_tool, list_tools

    tools = {item["name"] for item in list_tools()}
    assert "search_pratica_legale" in tools

    result = dispatch_tool(name="search_pratica_legale", query="notifica PEC L. 53", limit=8)

    assert result["ok"] is True
    ids = {item["id"] for item in result["risultati"]}
    assert "civile_notifiche_monitorio_esecuzioni" in ids
    assert "legge_53_1994_notifiche_avvocati" in ids
    assert any("relata" in " ".join(item.get("atti_da_produrre", [])).lower() for item in result["risultati"])

    scolastico = dispatch_tool(
        name="search_pratica_legale",
        query="PEI sostegno scolastico graduatoria MIM",
        limit=8,
    )
    scolastico_ids = {item["id"] for item in scolastico["risultati"]}
    assert "scolastico_docenti_alunni_concorsi" in scolastico_ids
    assert "dlgs_66_2017_inclusione_scolastica" in scolastico_ids

    immigrazione = dispatch_tool(
        name="search_pratica_legale",
        query="protezione internazionale cittadinanza Ministero Interno",
        limit=8,
    )
    immigrazione_ids = {item["id"] for item in immigrazione["risultati"]}
    assert "immigrazione_cittadinanza_protezione" in immigrazione_ids
    assert "legge_91_1992_cittadinanza" in immigrazione_ids


def test_lex_fonti_ufficiali_risponde_con_codici_decreti_sentenz_udienze():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(
        question="Quali fonti ufficiali mi servono per codice civile, codice penale, decreti legislativi, sentenze e udienze?",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
    )

    assert answer is not None
    assert answer.route is not None
    assert answer.route.intent == "official_sources_lookup"
    assert "Fonti operative pertinenti trovate" in answer.answer
    assert "Codice civile" in answer.answer
    assert "Codice penale" in answer.answer
    assert "D.Lgs." in answer.answer
    assert "Articoli/codici" in answer.answer
    assert "Sentenze, udienze e provvedimenti" in answer.answer
    assert "OpenGA" in answer.answer
    assert any(source.source_id == "fonti_ufficiali" for source in answer.sources)


def test_lex_risponde_a_domanda_reale_su_correttivo_cartabia_civile_senza_perdersi_sulle_notifiche():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(
        question=(
            "Fonte correttiva collegata alla riforma civile Cartabia per controllare "
            "rito, decorrenze, famiglia, esecuzione, notifiche e ADR."
        ),
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
    )

    assert answer is not None
    assert answer.route is not None
    assert answer.route.intent == "official_sources_lookup"
    assert "Non ho trovato dati reali sufficienti" not in answer.answer
    assert "D.Lgs. 31 ottobre 2024, n. 164" in answer.answer
    assert "Correttivo Cartabia civile" in answer.answer or "Correttivo processo civile" in answer.answer
    assert "rito" in answer.answer.lower()
    assert "famiglia" in answer.answer.lower()
    assert "notific" in answer.answer.lower()
    assert "ADR" in answer.answer or "adr" in answer.answer.lower()
    assert any(source.source_id in {"fonti_ufficiali", "matrice_pratica_legale"} for source in answer.sources)


def test_fascicolo_route_risolve_domanda_lunga_senza_perdere_il_nucleo_pratica():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(
        question=(
            "Fammi una sintesi del fascicolo Rossi Bianchi: "
            "documenti chiave, rischi aperti, cosa manca e prossimi passi."
        ),
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
    )

    assert answer is not None
    assert "Fascicolo: Rossi / Bianchi" in answer.answer
    assert "Documenti del fascicolo collegati o indicizzati" in answer.answer
    assert not any("Nessun dato reale disponibile dalla sorgente fascicoli" in gap for gap in answer.coverage_gaps)


def test_preventivo_conferimento_and_billing_do_not_invent_amounts():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Preparami il riepilogo del preventivo opposizione", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Preventivi: 1" in answer.answer
    assert "1200" not in answer.answer or "EUR" not in answer.answer
    assert any(source.source_id == "preventivi" for source in answer.sources)


def test_payment_lookup_uses_real_accounting_source_only_when_available():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="Verifica pagamenti", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Pagamenti: 1" in answer.answer
    assert any(source.source_id == "pagamenti" for source in answer.sources)


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
    assert "Data: 17 maggio 2026." in answer.answer
    assert "Allegati: 1." in answer.answer
    assert "Non ho trovato dati reali sufficienti" not in answer.answer


def test_latest_pec_response_exposes_openable_message_and_attachment_links():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="ultima PEC ricevuta", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    assert "Collegamento: [Apri comunicazione](/email/messaggio/pec-1)." in answer.answer
    assert "Allegati apribili: [ricevuta.eml](/email/messaggio/pec-1/allegato/0)." in answer.answer
    assert any(obj.object_type == "email" and obj.action_url == "/email/messaggio/pec-1" for obj in answer.objects)
    assert any(obj.object_type == "allegato_email" and obj.action_url == "/email/messaggio/pec-1/allegato/0" for obj in answer.objects)


def test_lex_attachment_act_question_uses_pec_context_not_templates():
    service, user = _service(repositories=_base_repositories())
    question = "Quale atto risulta notificato, depositato o comunicato negli allegati?"

    route = OperationalQueryRouter().route(question)
    answer = service.answer(question=question, user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert route is not None
    assert route.intent == "communications_lookup"
    assert {"email_pec", "pec_audit", "email_ordinaria", "messaggi"}.issubset(set(route.source_ids))
    assert answer is not None
    assert "Atto risultante dagli allegati." in answer.answer
    assert "Comunicazione di riferimento: Esito deposito." in answer.answer
    assert "Non emerge con certezza un atto principale" in answer.answer
    assert "ricevuta.eml" in answer.answer
    assert "Template atti" not in answer.answer
    assert not any(source.source_id == "template_atti" for source in answer.sources)


def test_lex_studio_reasoner_real_question_audit_matrix():
    service, user = _service(repositories=_base_repositories())
    studio = SimpleNamespace(slug="tenant-a")
    cases = [
        {
            "question": "ultima PEC ricevuta",
            "metadata": {},
            "intent": "communications_lookup",
            "must": ["Ultima PEC trovata", "Cancelleria", "Esito deposito", "/email/messaggio/pec-1", "ricevuta.eml"],
            "must_not": ["BOZZA", "Non ho trovato"],
            "sources": {"email_pec"},
        },
        {
            "question": "ultima PEC ricevuta",
            "metadata": {"active_context": {"context_type": "case", "case_id": "fas-1", "client_id": "cli-1"}},
            "intent": "communications_lookup",
            "must": ["Rossi / Bianchi", "Aggiornamento pratica", "Esito deposito", "Fonti interne"],
            "must_not": ["BOZZA", "Non ho trovato"],
            "sources": {"fascicoli", "messaggi", "email_pec"},
        },
        {
            "question": "spiegami questa PEC e dimmi quali allegati contiene",
            "metadata": {"active_context": {"context_type": "pec", "pec_id": "pec-1", "linked_case_id": "fas-1", "linked_client_id": "cli-1"}},
            "intent": "communications_lookup",
            "must": ["Ricevuta di consegna", "Allegati: 1", "ricevuta.eml", "/email/messaggio/pec-1"],
            "must_not": ["BOZZA", "Non ho trovato"],
            "sources": {"email_pec"},
        },
        {
            "question": "ultima email ordinaria ricevuta e allegati",
            "metadata": {},
            "intent": "communications_lookup",
            "must": ["Ultima email ordinaria trovata", "Documenti contratto", "contratto.pdf", "/email-ordinaria/messaggio/mail-1"],
            "must_not": ["BOZZA", "Non ho trovato"],
            "sources": {"email_ordinaria"},
        },
        {
            "question": "quali soggetti sono collegati a questa pratica?",
            "metadata": {"active_context": {"context_type": "case", "case_id": "fas-1", "client_id": "cli-1"}},
            "intent": "soggetti_lookup",
            "must": ["Parti del fascicolo: 1", "CONTROPARTE", "Luigi Bianchi", "Resistente nel procedimento"],
            "must_not": ["Nessun dato reale disponibile", "Parti del fascicolo: 2"],
            "sources": {"soggetti"},
        },
        {
            "question": "chi è la controparte del fascicolo?",
            "metadata": {"active_context": {"context_type": "case", "case_id": "fas-1", "client_id": "cli-1"}},
            "intent": "soggetti_lookup",
            "must": ["CONTROPARTE", "Luigi Bianchi", "BNCLGU80A01H501Z"],
            "must_not": ["Nessun dato reale disponibile", "Parti del fascicolo: 2"],
            "sources": {"soggetti"},
        },
        {
            "question": "Dammi la scheda cliente Rossi",
            "metadata": {},
            "intent": "client_situation",
            "must": ["Scheda cliente: Mario Rossi", "Codice fiscale", "Fascicoli collegati", "Pagamenti collegati"],
            "must_not": ["Non ho trovato"],
            "sources": {"clienti", "fascicoli", "pagamenti"},
        },
        {
            "question": "quali fascicoli ha il cliente Rossi?",
            "metadata": {},
            "intent": "client_fascicoli",
            "must": ["Scheda cliente: Mario Rossi", "Fascicoli collegati: 1", "Rossi / Bianchi"],
            "must_not": ["Non ho trovato"],
            "sources": {"clienti", "fascicoli"},
        },
        {
            "question": "Costruisci la timeline del fascicolo Rossi",
            "metadata": {"active_context": {"context_type": "case", "case_id": "fas-1", "client_id": "cli-1"}},
            "intent": "build_case_timeline",
            "must": ["Fascicolo: Rossi / Bianchi", "ricorso.pdf", "Costituzione", "Udienza"],
            "must_not": ["Non ho trovato"],
            "sources": {"fascicoli", "documenti_fascicolo", "scadenziario", "agenda"},
        },
        {
            "question": "Analizza i documenti presenti nel fascicolo Rossi e dimmi i punti importanti",
            "metadata": {"active_context": {"context_type": "case", "case_id": "fas-1", "client_id": "cli-1"}},
            "intent": "documenti_fascicolo",
            "must": ["Sintesi operativa per l'avvocato", "ricorso.pdf", "hash abc123", "non invento contenuti"],
            "must_not": ["Non ho trovato"],
            "sources": {"fascicoli", "documenti_fascicolo"},
        },
        {
            "question": "Quali scadenze urgenti ho questa settimana?",
            "metadata": {},
            "intent": "deadlines_overview",
            "must": ["Costituzione (20 maggio 2026)", "Udienza (21 maggio 2026 alle 10:00)", "Fonti interne"],
            "must_not": ["Non ho trovato"],
            "sources": {"agenda", "scadenziario"},
        },
        {
            "question": "cosa ho in agenda questa settimana?",
            "metadata": {},
            "intent": "deadlines_overview",
            "must": ["Scadenze consultabili", "Impegni agenda consultabili", "Udienza (21 maggio 2026 alle 10:00)"],
            "must_not": ["Non ho trovato"],
            "sources": {"agenda", "scadenziario"},
        },
        {
            "question": "fammi il riepilogo del fascicolo Rossi",
            "metadata": {"active_context": {"context_type": "case", "case_id": "fas-1", "client_id": "cli-1"}},
            "intent": "fascicolo_summary",
            "must": ["Fascicolo: Rossi / Bianchi", "ricorso.pdf", "Parcelle: 1 elementi"],
            "must_not": ["Non ho trovato"],
            "sources": {"fascicoli", "documenti_fascicolo", "fatturazione"},
        },
        {
            "question": "Verifica pagamenti e fatture del cliente Rossi",
            "metadata": {"cliente_id": "cli-1"},
            "intent": "client_economic_summary",
            "must": ["Quadro economico", "Pagamenti collegati", "Saldo parcella P-1", "500.0 EUR"],
            "must_not": ["stima", "invent"],
            "sources": {"clienti", "fatturazione", "pagamenti"},
        },
        {
            "question": "usa tutto il contesto studio e dimmi cosa devo guardare oggi",
            "metadata": {},
            "intent": "studio_context_overview",
            "must": ["Priorità operative", "Clienti: 1", "Fascicoli: 1", "PEC: 1", "Email ordinaria: 1", "Pagamenti: 1"],
            "must_not": ["Nessun dato reale disponibile"],
            "sources": {"clienti", "fascicoli", "email_pec", "email_ordinaria", "pagamenti"},
        },
        {
            "question": "scrivi risposta alla PEC di Rossi",
            "metadata": {},
            "intent": "draft_communication",
            "must": ["BOZZA — RISPOSTA PEC", "Esito deposito", "Ricevuta di consegna", "Dati da verificare"],
            "must_not": ["Non ho trovato"],
            "sources": {"email_pec"},
        },
    ]

    for case in cases:
        answer = service.answer(
            question=case["question"],
            user=user,
            studio=studio,
            tenant_id="tenant-a",
            metadata=case["metadata"],
        )
        assert answer is not None, case["question"]
        assert answer.route.intent == case["intent"], case["question"]
        for fragment in case["must"]:
            assert fragment in answer.answer, case["question"]
        for fragment in case["must_not"]:
            assert fragment not in answer.answer, case["question"]
        assert {source.source_id for source in answer.sources}.issuperset(case["sources"]), case["question"]
        assert answer.confidence >= 0.4, case["question"]


def test_lex_studio_reasoner_negative_question_audit_matrix():
    service, user = _service(repositories=_base_repositories())

    missing_case = service.answer(
        question="ultima PEC del fascicolo inesistente",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
        metadata={"active_context": {"context_type": "case", "case_id": "fas-x"}},
    )
    assert missing_case is not None
    assert "Non ho trovato dati reali sufficienti" in missing_case.answer
    assert "Esito deposito" not in missing_case.answer
    assert not any(source.source_id == "email_pec" for source in missing_case.sources)
    assert any("fascicolo" in gap.lower() for gap in missing_case.coverage_gaps)

    no_mail_permission = _User(_all_permissions() - {"messaggi.leggi"})
    denied = service.answer(
        question="ultima PEC ricevuta",
        user=no_mail_permission,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
    )
    assert denied is not None
    assert denied.blocked_reason == "missing_permission"
    assert "Non ho trovato dati reali sufficienti" in denied.answer
    assert not denied.sources

    ambiguous_repositories = _base_repositories()
    rows = list(ambiguous_repositories["clienti"].rows)
    rows.append(
        SimpleNamespace(
            id="cli-2",
            nome="Maria",
            cognome="Rossi",
            nome_completo="Maria Rossi",
            tipo="PERSONA_FISICA",
            stato="ATTIVO",
            tenant_id="tenant-a",
        )
    )
    ambiguous_repositories["clienti"] = _ListManager(rows)
    ambiguous_service, ambiguous_user = _service(repositories=ambiguous_repositories)
    ambiguous = ambiguous_service.answer(
        question="Dammi la scheda cliente Rossi",
        user=ambiguous_user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
    )
    assert ambiguous is not None
    assert "Ho trovato piu" in ambiguous.answer or "Ho trovato più" in ambiguous.answer
    assert "Mario Rossi" in ambiguous.answer
    assert "Maria Rossi" in ambiguous.answer


def test_lex_studio_reasoner_colleague_conversation_audit():
    service, user = _service(repositories=_base_repositories())
    studio = SimpleNamespace(slug="tenant-a")
    history: list[dict[str, str]] = []

    turns = [
        {
            "question": "ultima PEC ricevuta",
            "must": ["Ultima PEC trovata", "Esito deposito", "/email/messaggio/pec-1"],
            "intent": "communications_lookup",
        },
        {
            "question": "e gli allegati?",
            "must": ["Allegati: 1", "ricevuta.eml", "/email/messaggio/pec-1/allegato/0"],
            "intent": "communications_lookup",
            "effective": "allegati della PEC precedente",
        },
        {
            "question": "preparami una risposta",
            "must": ["BOZZA", "RISPOSTA PEC", "Esito deposito", "Dati da verificare"],
            "intent": "draft_communication",
            "effective": "scrivi risposta alla PEC precedente",
        },
        {
            "question": "fammi il riepilogo del fascicolo Rossi",
            "must": ["Fascicolo: Rossi / Bianchi", "ricorso.pdf", "/fascicoli/fas-1"],
            "intent": "fascicolo_summary",
        },
        {
            "question": "chi è la controparte?",
            "must": ["CONTROPARTE", "Luigi Bianchi", "Resistente nel procedimento"],
            "intent": "soggetti_lookup",
            "effective": "quali soggetti sono collegati al fascicolo precedente",
        },
        {
            "question": "e le scadenze?",
            "must": ["Costituzione (20 maggio 2026)", "Udienza (21 maggio 2026 alle 10:00)"],
            "intent": "deadlines_overview",
            "effective": "scadenze e agenda del fascicolo precedente",
        },
        {
            "question": "Dammi la scheda cliente Rossi",
            "must": ["Scheda cliente: Mario Rossi", "/clienti/cli-1/cartella"],
            "intent": "client_situation",
        },
        {
            "question": "quali fascicoli ha?",
            "must": ["Fascicoli collegati: 1", "Rossi / Bianchi"],
            "intent": "client_fascicoli",
            "effective": "quali fascicoli ha il cliente precedente",
        },
    ]

    for turn in turns:
        messages = [*history, {"role": "user", "content": turn["question"]}]
        answer = service.answer(
            question=turn["question"],
            user=user,
            studio=studio,
            tenant_id="tenant-a",
            metadata={"messages": messages},
        )
        assert answer is not None, turn["question"]
        assert answer.route.intent == turn["intent"], turn["question"]
        for fragment in turn["must"]:
            assert fragment in answer.answer, turn["question"]
        if turn.get("effective"):
            assert answer.metadata.get("conversation_effective_question") == turn["effective"]
        assert "Non ho trovato dati reali sufficienti" not in answer.answer, turn["question"]
        assert answer.sources, turn["question"]
        history.extend(
            [
                {"role": "user", "content": turn["question"]},
                {"role": "assistant", "content": answer.answer},
            ]
        )


def test_lex_studio_reasoner_colleague_conversation_score_reaches_90_percent():
    service, user = _service(repositories=_base_repositories())
    studio = SimpleNamespace(slug="tenant-a")
    history: list[dict[str, str]] = []
    turns = [
        ("ultima PEC ricevuta", "communications_lookup", ["Ultima PEC trovata", "Esito deposito", "/email/messaggio/pec-1"]),
        ("chi me l'ha mandata e quando?", "communications_lookup", ["Mittente: Cancelleria", "Data: 17 maggio 2026"]),
        ("e gli allegati?", "communications_lookup", ["Allegati: 1", "ricevuta.eml"]),
        ("preparami una risposta", "draft_communication", ["BOZZA", "RISPOSTA PEC", "Dati da verificare"]),
        ("mostrami anche l'email ordinaria ricevuta", "communications_lookup", ["Ultima email ordinaria trovata", "Documenti contratto"]),
        ("e gli allegati di quella?", "communications_lookup", ["contratto.pdf", "/email-ordinaria/messaggio/mail-1"]),
        ("scrivi una risposta anche a questa email", "draft_communication", ["BOZZA", "RISPOSTA EMAIL", "Documenti contratto"]),
        ("fammi il riepilogo del fascicolo Rossi", "fascicolo_summary", ["Fascicolo: Rossi / Bianchi", "ricorso.pdf"]),
        ("che documenti ci sono?", "documenti_fascicolo", ["Documenti del fascicolo", "ricorso.pdf"]),
        ("dimmi i punti importanti", "documenti_fascicolo", ["Sintesi operativa per l'avvocato", "non invento contenuti"]),
        ("chi e' la controparte?", "soggetti_lookup", ["CONTROPARTE", "Luigi Bianchi"]),
        ("e le scadenze?", "deadlines_overview", ["Costituzione (20 maggio 2026)", "Udienza"]),
        ("costruisci la timeline", "build_case_timeline", ["Fascicolo: Rossi / Bianchi", "ricorso.pdf", "Udienza"]),
        ("e i pagamenti e fatture?", "billing_summary", ["Parcelle/fatture", "Pagamenti"]),
        ("quali sono le prossime azioni operative?", "fascicolo_summary", ["Fascicolo: Rossi / Bianchi", "Fonti interne"]),
        ("Dammi la scheda cliente Rossi", "client_situation", ["Scheda cliente: Mario Rossi", "Recapiti autorizzati"]),
        ("quali recapiti ha?", "client_situation", ["mario@example.test", "mario@pec.test", "061234"]),
        ("quali fascicoli ha?", "client_fascicoli", ["Fascicoli collegati: 1", "Rossi / Bianchi"]),
        ("e i pagamenti?", "client_economic_summary", ["Pagamenti collegati", "Saldo parcella P-1"]),
        ("comunicazioni PEC/email del cliente", "communications_lookup", ["Cliente di contesto", "Esito deposito"]),
        ("usa tutto il contesto studio e dimmi le priorita'", "studio_context_overview", ["Priorit", "Clienti: 1", "Fascicoli: 1"]),
        ("cosa devo guardare oggi?", "deadlines_overview", ["Scadenze consultabili", "Fonti interne"]),
        ("cosa ho in agenda questa settimana?", "deadlines_overview", ["Impegni agenda consultabili", "Udienza"]),
        ("dammi la scheda soggetto Bianchi", "soggetti_lookup", ["Scheda soggetto: Luigi Bianchi", "BNCLGU80A01H501Z"]),
        ("riassumi il preventivo opposizione", "preventivo_summary", ["Preventivi: 1", "Conferimenti: 1"]),
        ("e il conferimento incarico?", "conferimento_summary", ["Conferimenti: 1", "Incarico opposizione"]),
        ("trova template ricorso opposizione", "template_lookup", ["Template atti", "Ricorso opposizione"]),
        ("mostrami la situazione del cliente Rossi", "client_situation", ["Scheda cliente: Mario Rossi", "Privacy"]),
        ("ultima PEC del fascicolo Rossi", "communications_lookup", ["Fascicolo di contesto", "Esito deposito"]),
        ("quali fonti interne hai usato per questa risposta?", "sources_overview", ["Fonti operative consultabili"]),
    ]
    failures: list[str] = []

    for index, (question, expected_intent, fragments) in enumerate(turns, start=1):
        messages = [*history, {"role": "user", "content": question}]
        answer = service.answer(
            question=question,
            user=user,
            studio=studio,
            tenant_id="tenant-a",
            metadata={"messages": messages},
        )
        ok = True
        detail = ""
        if answer is None:
            ok = False
            detail = "nessuna risposta"
        elif answer.route.intent != expected_intent:
            ok = False
            detail = f"intent {answer.route.intent!r}, atteso {expected_intent!r}"
        elif "Non ho trovato dati reali sufficienti" in answer.answer:
            ok = False
            detail = "risposta negativa generica"
        else:
            missing = [fragment for fragment in fragments if fragment not in answer.answer]
            if missing:
                ok = False
                detail = f"frammenti mancanti: {missing}"
        if not ok:
            failures.append(f"{index}. {question}: {detail}")
        if answer is not None:
            history.extend(
                [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer.answer},
                ]
            )

    score = (len(turns) - len(failures)) / len(turns)
    assert score >= 0.90, f"Score conversazione Lex {score:.0%}, fallimenti: {failures}"


def test_fascicolo_summary_espone_udienze_sentenze_esito_e_prossimi_passi():
    repositories = _base_repositories()
    fascicolo = repositories["fascicoli"].rows[0]
    fascicolo.documenti.append(
        SimpleNamespace(
            id="doc-sentenza-1",
            nome="sentenza_accoglimento.pdf",
            tipo="SENTENZA",
            sha256="def456",
            data_caricamento="2026-05-22",
            anteprima="Sentenza di accoglimento con condanna alle spese; decisiva la prova documentale prodotta prima dell'udienza.",
        )
    )
    repositories["agenda"].rows.append(
        SimpleNamespace(
            id="app-esito-1",
            titolo="Udienza di discussione",
            tipo="UDIENZA",
            id_cliente="cli-1",
            data_ora="2026-05-21T09:00:00",
            esito="Discussione trattenuta in decisione",
            provvedimento="Sentenza depositata",
            prossima_attivita="Verificare termine per impugnazione e notifica della sentenza",
        )
    )
    repositories["scadenziario"].rows.append(
        SimpleNamespace(
            id="sca-imp-1",
            titolo="Valutare impugnazione o notifica sentenza",
            id_fascicolo="fas-1",
            data_scadenza="2026-06-21",
        )
    )
    service, user = _service(repositories=repositories)
    answer = service.answer(
        question="Fammi una sintesi del fascicolo attivo: esito, udienze, cosa manca e prossimi passi.",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
        metadata={"fascicolo_id": "fas-1", "pagePath": "/fascicoli/fas-1"},
    )

    assert answer is not None
    assert answer.route.intent == "fascicolo_summary"
    assert "Provvedimenti, verbali o sentenze rilevati nel fascicolo" in answer.answer
    assert "Sentenza di accoglimento" in answer.answer
    assert "Udienze ed eventi processuali collegati" in answer.answer
    assert "Discussione trattenuta in decisione" in answer.answer
    assert "Termini e attività successive da presidiare" in answer.answer
    assert "21 giugno 2026" in answer.answer
    assert "Fonti interne: fascicolo e moduli collegati autorizzati" in answer.answer


def test_lex_studio_reasoner_legal_language_and_dates_audit_reaches_99_percent():
    service, user = _service(repositories=_base_repositories())
    studio = SimpleNamespace(slug="tenant-a")
    history: list[dict[str, str]] = []
    base_turns = [
        ("ultima PEC ricevuta", True),
        ("chi me l'ha mandata e quando?", True),
        ("e gli allegati?", True),
        ("preparami una risposta", True),
        ("mostrami anche l'email ordinaria ricevuta", True),
        ("scrivi una risposta anche a questa email", True),
        ("fammi il riepilogo del fascicolo Rossi", True),
        ("che documenti ci sono?", True),
        ("dimmi i punti importanti del documento", True),
        ("chi e' la controparte?", True),
        ("e le scadenze?", True),
        ("costruisci la timeline del fascicolo", True),
        ("e i pagamenti e fatture?", True),
        ("Dammi la scheda cliente Rossi", True),
        ("quali recapiti ha?", True),
        ("quali fascicoli ha?", True),
        ("e i pagamenti?", True),
        ("comunicazioni PEC/email del cliente", True),
        ("usa tutto il contesto studio e dimmi le priorita'", True),
        ("cosa devo guardare oggi?", True),
        ("cosa ho in agenda questa settimana?", True),
        ("dammi la scheda soggetto Bianchi", True),
        ("riassumi il preventivo opposizione", False),
        ("e il conferimento incarico?", False),
        ("trova template ricorso opposizione", False),
    ]
    professional_markers = (
        "fonti interne",
        "fonte:",
        "scheda",
        "fascicolo",
        "pec",
        "document",
        "privacy",
        "collegamento",
        "scaden",
        "agenda",
        "pagament",
        "bozza",
        "limiti",
        "dati da verificare",
    )
    banned_markers = ("sono qui per aiutarti", "come posso aiutarti", "non sono un avvocato")
    failures: list[str] = []
    dated_checks = 0

    for index, (question, requires_italian_date) in enumerate(base_turns * 4, start=1):
        messages = [*history, {"role": "user", "content": question}]
        answer = service.answer(
            question=question,
            user=user,
            studio=studio,
            tenant_id="tenant-a",
            metadata={"messages": messages},
        )
        text = answer.answer if answer is not None else ""
        normalized = text.lower()
        reasons = []
        if answer is None:
            reasons.append("nessuna risposta")
        if RAW_VISIBLE_DATE_RE.search(text):
            reasons.append("data tecnica visibile")
        if requires_italian_date:
            dated_checks += 1
            if not ITALIAN_MONTH_RE.search(text):
                reasons.append("manca data italiana in risposta con dato temporale")
        if not any(marker in normalized for marker in professional_markers):
            reasons.append("linguaggio non professionale o senza contesto studio")
        if any(marker in normalized for marker in banned_markers):
            reasons.append("formula da chatbot generico")
        if reasons:
            failures.append(f"{index}. {question}: {', '.join(reasons)}")
        if answer is not None:
            history.extend(
                [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer.answer},
                ]
            )

    score = (len(base_turns) * 4 - len(failures)) / (len(base_turns) * 4)
    assert dated_checks >= 80
    assert score >= 0.99, f"Audit linguaggio giuridico/date Lex {score:.0%}, fallimenti: {failures}"


def test_fascicolo_reasoner_builds_entity_map_timeline_and_editor_links():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(
        question="Analizza i documenti presenti nel fascicolo",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        metadata={"fascicolo_id": "fas-1"},
    )

    assert answer is not None
    assert "[ricorso.pdf](/fascicoli/fas-1/documenti/doc-1/editor)" in answer.answer
    assert any(obj.object_type == "fascicolo" and obj.action_url == "/fascicoli/fas-1" for obj in answer.objects)
    assert any(obj.object_type == "documento" and obj.action_url == "/fascicoli/fas-1/documenti/doc-1/editor" for obj in answer.objects)
    report = answer.metadata["studio_reasoner"]
    nodes = report["entity_map"]["nodes"]
    timeline = report["fascicolo_timeline"]
    assert any(node["type"] == "fascicolo" and node["id"] == "fas-1" for node in nodes)
    assert any(node["type"] == "documento" and node["action_url"].endswith("/documenti/doc-1/editor") for node in nodes)
    assert any(event["type"] == "documento" and event["object_id"] == "doc-1" for event in timeline)


def test_lex_studio_reasoner_attaches_governed_rag_report_to_latest_pec():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(question="ultima PEC ricevuta", user=user, studio=SimpleNamespace(slug="tenant-a"))

    assert answer is not None
    report = answer.metadata["studio_reasoner"]
    assert report["name"] == "Lex Studio Reasoner"
    assert report["mode"] == "llm_rag_governato"
    assert report["rag_policy"]["tenant_aware"] is True
    assert report["rag_policy"]["no_legacy_aggregator"] is True
    assert report["rag_policy"]["excludes_public_legal_sources"] is True
    assert report["colleague_policy"]["conversation_style"] == "confronto professionale tra colleghi"
    assert report["colleague_policy"]["contradict_lawyer_min_confidence"] == 0.99
    assert report["colleague_policy"]["jurisprudence_practice_mode"] == "canary_web_governato_no_publish"
    assert "email_pec" in report["verification"]["verified_internal_sources"]
    assert "fonti_ufficiali" not in report["verification"]["verified_internal_sources"]
    assert report["verification"]["evidence_sufficient"] is True
    assert any(step["phase"] == "verifica" and step["verified"] for step in report["steps"])


def test_lex_studio_reasoner_excludes_public_legal_sources_from_internal_verifier():
    from lex.operational_knowledge.models import OperationalRoute, OperationalSourceReference, OperationalToolResult
    from lex.operational_knowledge.reasoner import LexStudioReasoner

    reasoner = LexStudioReasoner()
    route = OperationalRoute(
        "official_sources_lookup",
        "official_sources_lookup",
        ("fonti_ufficiali", "legal_intelligence", "clienti"),
        "articolo 599-bis cpp",
    )
    plan = reasoner.build_plan(question="cerca articolo 599-bis cpp", route=route)
    report = reasoner.verify(
        plan=plan,
        results=[
            OperationalToolResult(
                True,
                "fonti_ufficiali",
                data=[{"id": "src-1", "titolo": "Fonte pubblica"}],
                sources=[
                    OperationalSourceReference(
                        source_id="fonti_ufficiali",
                        source_name="Fonti ufficiali",
                        source_type="fonte_ufficiale",
                        object_type="fonte",
                        object_id="src-1",
                        title="Fonte pubblica",
                        confidence=0.9,
                        internal=False,
                    )
                ],
            )
        ],
    )

    assert plan.required_sources == ("clienti",)
    assert report.verified_internal_sources == ()
    assert report.excluded_sources == ("fonti_ufficiali",)
    assert report.evidence_sufficient is False


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


def test_template_lookup_include_fonti_ufficiali_modello():
    service, user = _service(repositories=_base_repositories())

    answer = service.answer(
        question="Quali fonti del modello preventivo professionale includono codice deontologico ed equo compenso?",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
    )

    assert answer is not None
    payload = str(answer.to_dict())
    assert any(source.source_id == "template_atti_fonti_ufficiali" for source in answer.sources)
    assert "Codice deontologico" in payload
    assert "equo compenso" in payload


def test_router_fonti_modello_deontologico_usa_sorgente_template_fonti():
    route = OperationalQueryRouter().route("fonti del modello incarico con codice deontologico")

    assert route is not None
    assert "template_atti_fonti_ufficiali" in route.source_ids


def _qsp_9926_rows():
    return [
        {
            "id": "web-evidence-page",
            "title": "Questione Penale Pendente del ricorso R.G. 9926/2026 ud. 09/07/2026",
            "source_name": "Corte Suprema di Cassazione",
            "official_url": "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
            "excerpt": "Questione penale pendente R.G. 9926/2026.",
            "content": (
                "Data inserimento: 05 maggio 2026 Questione penale Pendente del ricorso R.G. n. 9926/2026 "
                "ud. 09/07/2026 Se, avverso la sentenza emessa a seguito di concordato in appello, siano "
                "deducibili con il ricorso per cassazione i vizi attinenti alla determinazione della pena non "
                "comportanti l'illegalità della stessa. Ricorrente: Turco G. Relatore: E. Morosini Data udienza: "
                "09 luglio 2026 Riferimenti normativi: Cod. proc. pen. artt. 599-bis e 606 Allegati Ordinanza "
                "di rimessione."
            ),
            "verified_reference": True,
            "score": 2.0,
        },
        {
            "id": "web-evidence-attachment",
            "title": "Ordinanza di rimessione",
            "source_name": "Corte Suprema di Cassazione",
            "official_url": "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
            "attachment_url": "https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf",
            "excerpt": "Nota Ufficio Spoglio V Sezione penale. R.G. 9966/2026. Ordinanza di rimessione.",
            "content": QSP_ATTACHMENT_OCR_TEXT,
            "verified_reference": True,
            "score": 1.8,
        },
    ]


def _qsp_9926_service():
    class _Repo:
        def search_lex_sources(self, query: str, limit: int = 6):
            assert "9926" in query or "9966" in query or "QSP50194" in query
            return _qsp_9926_rows()

    class _Pipeline:
        repository = _Repo()

    class _WebLibero:
        queries: list[str] = []

        def search_free_public_web(self, query: str, limit: int = 4):
            self.queries.append(query)
            return [
                {
                    "id": "web-libero-cpp-599-bis",
                    "title": "Brocardi - art. 599-bis c.p.p.",
                    "url": "https://www.brocardi.it/codice-di-procedura-penale/libro-nono/titolo-ii/art599bis.html",
                    "source_id": "web_libero",
                    "source_name": "Web libero",
                    "source_access_label": "Web libero",
                    "source_priority": "web_libero",
                    "excerpt": "Concordato anche con rinuncia ai motivi di appello.",
                },
                {
                    "id": "web-libero-cpp-129",
                    "title": "Altalex - art. 129 c.p.p.",
                    "url": "https://www.altalex.com/documents/news/2014/09/15/codice-di-procedura-penale-articolo-129",
                    "source_id": "web_libero",
                    "source_name": "Web libero",
                    "source_access_label": "Web libero",
                    "source_priority": "web_libero",
                    "excerpt": "Obbligo della immediata declaratoria di determinate cause di non punibilità.",
                },
            ]

    repos = _base_repositories()
    repos["update_intelligence"] = _Pipeline()
    repos["web_libero"] = _WebLibero()
    return _service(repositories=repos)


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
                    "content": QSP_ATTACHMENT_OCR_TEXT,
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
    assert "### Fonte e PDF" in answer.answer
    assert "Allegato: **Ordinanza di rimessione**." in answer.answer
    assert "Apri PDF ufficiale" in answer.answer
    assert "### Sintesi" in answer.answer
    assert "### Norme rilevanti" in answer.answer
    assert "### Fonte e PDF" in answer.answer
    assert answer.answer.count("### Sintesi") == 1
    assert "### Cosa dice la scheda ufficiale" not in answer.answer
    assert "### Sintesi dell'ordinanza" not in answer.answer
    assert "Non risulta una sentenza" in answer.answer
    assert "Motivi/censure dal PDF collegato" in answer.answer
    assert "PDF ufficialmente collegato" in answer.answer
    assert "Contesto processuale" not in answer.answer
    assert "Gianfranco Greco" not in answer.answer
    assert "Estratto leggibile" not in answer.answer
    assert "R.G. 9926/2026" in answer.answer
    assert "R.G. 9966/2026" in answer.answer
    assert "Non ho trovato dati reali sufficienti" not in answer.answer
    assert any(source.source_id == "update_intelligence" for source in answer.sources)


@pytest.mark.parametrize(
    ("question", "expected_fragments"),
    [
        (
            "mi puoi sintetizzare questa sentenza Penale Pendente del ricorso R.G. 9926/2026",
            [
                "### Sintesi",
                "Oggetto",
                "Non risulta una sentenza",
                "PDF collegato riporta R.G. 9966/2026",
                "Effetto pratico",
            ],
        ),
        (
            "qual è il punto di diritto della questione penale R.G. 9926/2026?",
            [
                "Punto di diritto",
                "deducibilità dell'erronea determinazione della sanzione",
                "concordata tra le parti ex art. 599-bis",
            ],
        ),
        (
            "quali sono i motivi del ricorso R.G. 9926/2026?",
            [
                "Motivi/censure dal PDF collegato",
                "non come dati certi autonomi della scheda",
                "difetto di controllo giudiziale",
                "art. 129 cod. proc. pen.",
            ],
        ),
        (
            "è una sentenza o una questione pendente R.G. 9926/2026?",
            [
                "Natura dell'atto",
                "Non risulta una sentenza",
                "questione è pendente",
            ],
        ),
        (
            "quando è fissata l'udienza e quali norme sono indicate per R.G. 9926/2026?",
            [
                "udienza 09 luglio 2026",
                "Cod. proc. pen. artt. 599-bis e 606",
                "Riferimenti trovati",
            ],
        ),
        (
            "trova gli articoli di riferimento della questione R.G. 9926/2026",
            [
                "Riferimenti trovati",
                "Cod. proc. pen. artt. 599-bis e 606",
                "art. 599-bis c.p.p.",
                "art. 129 c.p.p.",
                "art. 81, comma secondo c.p.",
                "Integrazione web libera sugli articoli",
                "Brocardi - art. 599-bis c.p.p.",
                "Altalex - art. 129 c.p.p.",
            ],
        ),
        (
            "chi sono ricorrente e relatore della questione penale R.G. 9926/2026?",
            [
                "Dati della scheda: ricorrente Turco G; relatore E. Morosini.",
            ],
        ),
        (
            "mi dai il PDF e l'allegato ufficiale della questione R.G. 9926/2026?",
            [
                "Allegato/PDF",
                "Allegato: **Ordinanza di rimessione**.",
                "Apri PDF ufficiale",
            ],
        ),
        (
            "posso citare la questione R.G. 9926/2026 in un atto come decisione definitiva?",
            [
                "Uso prudente",
                "non come arresto definitivo",
                "questione pendente",
            ],
        ),
        (
            "qual è l'esito della questione R.G. 9926/2026?",
            [
                "Stato:",
                "questione è pendente",
                "non risulta una decisione finale",
            ],
        ),
        (
            "spiegami la discrepanza tra R.G. 9926/2026 e R.G. 9966/2026",
            [
                "Punto da verificare",
                "R.G. 9926/2026",
                "R.G. 9966/2026",
                "PDF ufficialmente collegato",
                "non come dati certi autonomi della scheda",
            ],
        ),
    ],
)
def test_rg_questione_penale_risponde_a_domande_da_avvocato(question, expected_fragments):
    service, user = _qsp_9926_service()

    answer = service.answer(
        question=question,
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
    )

    assert answer is not None
    assert answer.route.intent == "official_sources_lookup"
    for fragment in expected_fragments:
        assert fragment in answer.answer
    assert "Editor Lex" not in answer.answer
    assert "template_atti" not in answer.answer
    assert "Camera Arbitrale" not in answer.answer
    assert "Non ho trovato dati reali sufficienti" not in answer.answer


def test_rg_questione_penale_articoli_attiva_web_libero_distinto_dalla_fonte_ufficiale():
    class _Repo:
        def search_lex_sources(self, query: str, limit: int = 6):
            return _qsp_9926_rows()

    class _Pipeline:
        repository = _Repo()

    class _WebLibero:
        def __init__(self):
            self.queries: list[str] = []

        def search_free_public_web(self, query: str, limit: int = 4):
            self.queries.append(query)
            return [
                {
                    "id": "web-libero-art-606",
                    "title": "Studio Cataldi - art. 606 c.p.p.",
                    "url": "https://www.studiocataldi.it/codiceprocedurapenale/articolo-606.asp",
                    "source_id": "web_libero",
                    "source_name": "Web libero",
                    "source_access_label": "Web libero",
                    "source_priority": "web_libero",
                    "excerpt": "Casi di ricorso per cassazione.",
                }
            ]

    web_libero = _WebLibero()
    repos = _base_repositories()
    repos["update_intelligence"] = _Pipeline()
    repos["web_libero"] = web_libero
    service, user = _service(repositories=repos)

    answer = service.answer(
        question="trova gli articoli di riferimento della questione R.G. 9926/2026",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
    )

    assert answer is not None
    assert web_libero.queries
    assert "art. 599-bis c.p.p." in web_libero.queries[0]
    assert "art. 129 c.p.p." in web_libero.queries[0]
    assert "### Integrazione web libera sugli articoli" in answer.answer
    assert "Studio Cataldi - art. 606 c.p.p." in answer.answer
    assert "non sostituisce la fonte ufficiale Cassazione" not in answer.answer
    assert "Allegato: **Ordinanza di rimessione**." in answer.answer
    assert any(source.source_id == "web_libero" for source in answer.sources)


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
                    "content": QSP_ATTACHMENT_OCR_TEXT,
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
                {
                    "id": "web-evidence-other-rg",
                    "title": "Questione Penale Pendente del ricorso R.G. 37184/2025 ud. 25/06/2026",
                    "source_name": "Corte Suprema di Cassazione",
                    "official_url": "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP99999",
                    "excerpt": "Questione penale pendente R.G. 37184/2025.",
                    "verified_reference": True,
                    "score": 1.46,
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
    assert "Allegato: **Ordinanza di rimessione**." in answer.answer
    assert "Camera Arbitrale" not in answer.answer
    assert "Nessuna fonte ufficiale citabile" not in answer.answer
    assert all("Camera Arbitrale" not in source.title for source in answer.sources)
    assert all("37184/2025" not in source.title for source in answer.sources)


def test_rg_questione_penale_prefisso_template_resta_fonte_ufficiale():
    class _Repo:
        def search_lex_sources(self, query: str, limit: int = 6):
            return [
                {
                    "id": "web-evidence-attachment",
                    "title": "Ordinanza di rimessione",
                    "source_name": "Corte Suprema di Cassazione",
                    "official_url": "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                    "attachment_url": "https://www.cortedicassazione.it/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf",
                    "excerpt": "Nota Ufficio Spoglio V Sezione penale. R.G. 9966/2026. Ordinanza di rimessione.",
                    "content": QSP_ATTACHMENT_OCR_TEXT,
                    "verified_reference": True,
                    "score": 1.48,
                }
            ]

    class _Pipeline:
        repository = _Repo()

    repos = _base_repositories()
    repos["update_intelligence"] = _Pipeline()
    service, user = _service(repositories=repos)

    answer = service.answer(
        question="atti template Questione Penale Pendente del ricorso R.G. 9926/2026",
        user=user,
        studio=SimpleNamespace(slug="tenant-a"),
        tenant_id="tenant-a",
        metadata={"focus_topic": "atti_template", "request_profile": {"intent": "giurisprudenza", "source_mode": "strict"}},
    )

    assert answer is not None
    assert answer.route.intent == "official_sources_lookup"
    assert "Allegato: **Ordinanza di rimessione**." in answer.answer
    assert "Editor Lex" not in answer.answer
    assert "template_atti" not in answer.answer


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
                    "Questione penale pendente R.G. 9926/2026. Se, avverso la sentenza emessa a seguito di concordato in appello, siano deducibili con il ricorso per cassazione i vizi attinenti alla determinazione della pena non comportanti l'illegalità della stessa.",
                    "Data inserimento: 05 maggio 2026 Questione penale Pendente del ricorso R.G. n. 9926/2026 ud. 09/07/2026 Se, avverso la sentenza emessa a seguito di concordato in appello, siano deducibili con il ricorso per cassazione i vizi attinenti alla determinazione della pena non comportanti l'illegalità della stessa. Ricorrente: Turco G. Relatore: E. Morosini Data udienza: 09 luglio 2026 Riferimenti normativi: Cod. proc. pen. artt. 599-bis e 606 Allegati Ordinanza di rimessione.",
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
                    QSP_ATTACHMENT_OCR_TEXT,
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
    assert "Allegato: **Ordinanza di rimessione**." in answer.answer
    assert "### Sintesi" in answer.answer
    assert "concordato in appello" in answer.answer
    assert "Cod. proc. pen. artt. 599-bis e 606" in answer.answer
    assert "Apri PDF ufficiale" in answer.answer
    assert "### Norme rilevanti" in answer.answer
    assert "### Fonte e PDF" in answer.answer
    assert answer.answer.count("### Sintesi") == 1
    assert "### Cosa dice la scheda ufficiale" not in answer.answer
    assert "### Sintesi dell'ordinanza" not in answer.answer
    assert "Motivi/censure dal PDF collegato" in answer.answer
    assert "Contesto processuale" not in answer.answer
    assert "Gianfranco Greco" not in answer.answer
    assert "Estratto leggibile" not in answer.answer
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


def test_operational_router_contesto_studio_resta_su_sorgenti_interne():
    route = OperationalQueryRouter().route("usa tutto il contesto studio")

    assert route is not None
    assert route.intent == "studio_context_overview"
    assert "clienti" in route.source_ids
    assert "fascicoli" in route.source_ids
    assert "email_pec" in route.source_ids
    assert "fonti_ufficiali" not in route.source_ids


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


def test_lex_unified_chat_global_context_renders_latest_pec_cards(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            assert kwargs["metadata"]["active_context"]["context_type"] == "global"
            return OperationalAnswer(
                handled=True,
                answer="Ho trovato l'ultima PEC ricevuta.",
                route=OperationalRoute("communications_lookup", "communications_lookup", ("email_pec",), ""),
                sources=[
                    OperationalSourceReference(
                        source_id="email_pec",
                        source_name="Email PEC",
                        source_type="email_pec",
                        object_type="email",
                        object_id="pec-1",
                        title="Esito deposito",
                        confidence=0.91,
                        metadata={
                            "action_url": "/email/messaggio/pec-1",
                            "record": {
                                "id": "pec-1",
                                "oggetto": "Esito deposito",
                                "mittente": "cancelleria@pec.test",
                                "destinatari": ["studio@pec.test"],
                                "data": "2026-05-19",
                                "allegati_count": 1,
                                "allegati": [{"nome": "ricevuta.eml", "view_url": "/email/messaggio/pec-1/allegato/0"}],
                                "action_url": "/email/messaggio/pec-1",
                            },
                        },
                    )
                ],
                confidence=0.91,
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"active_context": {"context_type": "global"}},
        current_user_message="ultima PEC ricevuta",
        resolved_effective_question="ultima PEC ricevuta",
        studio_context={"focus_topic": "pec_firma", "request_profile": {"intent": "comunicazioni_lookup"}},
    )

    assert payload is not None
    assert payload["chat_component"] == "LexUnifiedChat"
    assert payload["detected_intent"] == "consult_pec"
    assert payload["lex_unified_chat"]["engine"] == "Lex Studio Reasoner"
    assert payload["structured_context"]["active_context"]["context_type"] == "global"
    assert any(block["type"] == "pec_card" for block in payload["message_blocks"])
    assert any(block["type"] == "attachment_card" for block in payload["message_blocks"])
    action_labels = {action["label"] for action in payload["lex_actions"]}
    assert {"Apri PEC", "Apri allegato", "Prepara bozza risposta"} <= action_labels
    assert "BOZZA" not in payload["answer"]


def test_lex_unified_chat_case_context_scopes_operational_retrieval(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            assert kwargs["metadata"]["fascicolo_id"] == "fas-1"
            assert kwargs["metadata"]["active_context"]["case_id"] == "fas-1"
            return OperationalAnswer(
                handled=True,
                answer="Ultima PEC collegata al fascicolo trovata.",
                route=OperationalRoute("communications_lookup", "communications_lookup", ("fascicoli", "email_pec"), ""),
                sources=[
                    OperationalSourceReference(
                        source_id="fascicoli",
                        source_name="Fascicoli",
                        source_type="fascicolo",
                        object_type="fascicolo",
                        object_id="fas-1",
                        title="RG 10/2026",
                        confidence=0.9,
                        metadata={"action_url": "/fascicoli/fas-1", "record": {"id": "fas-1", "numero": "RG 10/2026", "action_url": "/fascicoli/fas-1"}},
                    ),
                    OperationalSourceReference(
                        source_id="email_pec",
                        source_name="Email PEC",
                        source_type="email_pec",
                        object_type="email",
                        object_id="pec-1",
                        title="Esito deposito",
                        confidence=0.9,
                        metadata={"action_url": "/email/messaggio/pec-1", "record": {"id": "pec-1", "oggetto": "Esito deposito", "data": "2026-05-19", "action_url": "/email/messaggio/pec-1"}},
                    ),
                ],
                confidence=0.9,
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"active_context": {"context_type": "case", "case_id": "fas-1"}},
        current_user_message="ultima PEC ricevuta",
        resolved_effective_question="ultima PEC ricevuta",
        studio_context={"focus_topic": "fascicoli", "request_profile": {"intent": "comunicazioni_lookup"}},
    )

    assert payload is not None
    assert payload["active_context"]["context_type"] == "case"
    assert payload["active_context"]["case_id"] == "fas-1"
    assert any(block["type"] == "case_card" for block in payload["message_blocks"])
    assert any(action["label"] == "Apri fascicolo" for action in payload["lex_actions"])


def test_lex_unified_chat_pec_context_passes_selected_pec_id(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            assert kwargs["metadata"]["pec_id"] == "pec-1"
            return OperationalAnswer(
                handled=True,
                answer="PEC selezionata trovata.",
                route=OperationalRoute("communications_lookup", "communications_lookup", ("email_pec",), ""),
                sources=[
                    OperationalSourceReference(
                        source_id="email_pec",
                        source_name="Email PEC",
                        source_type="email_pec",
                        object_type="email",
                        object_id="pec-1",
                        title="Esito deposito",
                        confidence=0.88,
                        metadata={"action_url": "/email/messaggio/pec-1", "record": {"id": "pec-1", "oggetto": "Esito deposito", "data": "2026-05-19", "action_url": "/email/messaggio/pec-1"}},
                    )
                ],
                confidence=0.88,
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"active_context": {"context_type": "pec", "pec_id": "pec-1", "linked_case_id": "fas-1"}},
        current_user_message="leggi questa PEC",
        resolved_effective_question="leggi questa PEC",
        studio_context={"focus_topic": "pec_firma", "request_profile": {"intent": "comunicazioni_lookup"}},
    )

    assert payload is not None
    assert payload["active_context"]["context_type"] == "pec"
    assert payload["active_context"]["pec_id"] == "pec-1"
    assert payload["active_context"]["linked_case_id"] == "fas-1"
    assert any(block["type"] == "pec_card" for block in payload["message_blocks"])


def test_lex_unified_chat_source_verifier_hides_sources_without_permission(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            return OperationalAnswer(
                handled=True,
                answer="Non ho trovato dati reali sufficienti nelle sorgenti operative autorizzate per rispondere.",
                route=OperationalRoute("communications_lookup", "communications_lookup", ("email_pec",), ""),
                sources=[],
                confidence=0.2,
                coverage_gaps=["Accesso a email_pec non consentito."],
                blocked_reason="missing_permission",
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User({"ai.usa"}),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"active_context": {"context_type": "global"}},
        current_user_message="ultima PEC ricevuta",
        resolved_effective_question="ultima PEC ricevuta",
        studio_context={"focus_topic": "pec_firma", "request_profile": {"intent": "comunicazioni_lookup"}},
    )

    assert payload is not None
    assert payload["lex_unified_chat"]["source_verification"]["allowed"] is False
    assert payload["lex_actions"] == []
    assert not any(block["type"] == "source_card" for block in payload["message_blocks"])
    assert any(block["type"] == "warning" for block in payload["message_blocks"])


def test_lex_unified_chat_ambiguous_client_returns_clarification_options(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            return OperationalAnswer(
                handled=True,
                answer="Ho trovato più clienti compatibili.",
                route=OperationalRoute("client_situation", "client_situation", ("clienti",), "rossi"),
                sources=[
                    OperationalSourceReference("clienti", "Clienti", "cliente", "cliente", "cli-1", "Mario Rossi", 0.8),
                    OperationalSourceReference("clienti", "Clienti", "cliente", "cliente", "cli-2", "Maria Rossi", 0.8),
                ],
                confidence=0.62,
                coverage_gaps=["Più clienti compatibili."],
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"active_context": {"context_type": "global"}},
        current_user_message="Dammi i dati del cliente Rossi",
        resolved_effective_question="Dammi i dati del cliente Rossi",
        studio_context={"focus_topic": "clienti", "request_profile": {"intent": "cliente_anagrafica"}},
    )

    assert payload is not None
    verifier = payload["lex_unified_chat"]["source_verification"]
    assert verifier["requires_clarification"] is True
    assert verifier["ambiguous_entities"][0]["type"] == "client"
    assert any(block["type"] == "warning" for block in payload["message_blocks"])


def test_lex_unified_chat_missing_source_returns_clear_negative_result(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            return OperationalAnswer(
                handled=True,
                answer="Non ho trovato dati reali sufficienti nelle sorgenti operative autorizzate per rispondere.",
                route=OperationalRoute("communications_lookup", "communications_lookup", ("email_pec",), ""),
                sources=[],
                confidence=0.25,
                coverage_gaps=["Nessuna PEC reale disponibile nella casella autorizzata."],
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"active_context": {"context_type": "global"}},
        current_user_message="ultima PEC ricevuta",
        resolved_effective_question="ultima PEC ricevuta",
        studio_context={"focus_topic": "pec_firma", "request_profile": {"intent": "comunicazioni_lookup"}},
    )

    assert payload is not None
    missing = payload["lex_unified_chat"]["source_verification"]["missing_information"]
    assert any("Nessuna PEC reale" in item for item in missing)
    assert any("Nessuna fonte interna verificata" in item for item in missing)
    assert any(block["type"] == "warning" for block in payload["message_blocks"])


def test_lex_unified_chat_timeline_returns_dates_and_sources(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            return OperationalAnswer(
                handled=True,
                answer="Timeline fascicolo costruita.",
                route=OperationalRoute("build_case_timeline", "build_case_timeline", ("fascicoli", "documenti_fascicolo"), ""),
                sources=[
                    OperationalSourceReference(
                        "documenti_fascicolo",
                        "Documenti fascicolo",
                        "documento",
                        "documento",
                        "doc-1",
                        "ricorso.pdf",
                        0.9,
                        metadata={"action_url": "/fascicoli/fas-1/documenti/doc-1/editor", "record": {"id": "doc-1", "titolo": "ricorso.pdf", "data": "2026-05-10", "action_url": "/fascicoli/fas-1/documenti/doc-1/editor"}},
                    )
                ],
                confidence=0.9,
                metadata={
                    "operational_layer": True,
                    "studio_reasoner": {
                        "fascicolo_timeline": [
                            {
                                "date": "2026-05-10",
                                "type": "documento",
                                "source_id": "documenti_fascicolo",
                                "object_id": "doc-1",
                                "label": "ricorso.pdf",
                                "action_url": "/fascicoli/fas-1/documenti/doc-1/editor",
                            }
                        ]
                    },
                },
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"active_context": {"context_type": "case", "case_id": "fas-1"}},
        current_user_message="costruisci timeline del fascicolo",
        resolved_effective_question="costruisci timeline del fascicolo",
        studio_context={"focus_topic": "fascicoli", "request_profile": {"intent": "domanda_generica"}},
    )

    assert payload is not None
    assert payload["detected_intent"] == "build_case_timeline"
    timeline_block = next(block for block in payload["message_blocks"] if block["type"] == "timeline")
    assert timeline_block["items"][0]["date"] == "2026-05-10"
    assert timeline_block["items"][0]["source_id"] == "documenti_fascicolo"


def test_lex_unified_chat_payments_require_accounting_sources(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.operational_knowledge.integration import build_operational_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            with_payment = kwargs["metadata"].get("with_payment")
            sources = []
            if with_payment:
                sources.append(
                    OperationalSourceReference(
                        "pagamenti",
                        "Pagamenti",
                        "pagamento",
                        "pagamento",
                        "pay-1",
                        "Saldo parcella P-1",
                        0.87,
                        metadata={"action_url": "/incassi-pagamenti", "record": {"id": "pay-1", "descrizione": "Saldo parcella P-1", "importo": 500.0, "stato": "ATTESO", "action_url": "/incassi-pagamenti"}},
                    )
                )
            return OperationalAnswer(
                handled=True,
                answer="Quadro pagamenti consultato." if with_payment else "Nessun dato contabile consultabile.",
                route=OperationalRoute("billing_summary", "billing_summary", ("pagamenti",), ""),
                sources=sources,
                confidence=0.87 if with_payment else 0.3,
                coverage_gaps=[] if with_payment else ["Nessuna fonte contabile autorizzata ha restituito dati."],
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"with_payment": True, "active_context": {"context_type": "global"}},
        current_user_message="verifica pagamenti",
        resolved_effective_question="verifica pagamenti",
        studio_context={"focus_topic": "fatture", "request_profile": {"intent": "domanda_generica"}},
    )
    assert payload is not None
    assert payload["detected_intent"] == "check_payments"
    assert any(block["type"] == "payment_card" for block in payload["message_blocks"])

    no_source_payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"active_context": {"context_type": "global"}},
        current_user_message="verifica pagamenti",
        resolved_effective_question="verifica pagamenti",
        studio_context={"focus_topic": "fatture", "request_profile": {"intent": "domanda_generica"}},
    )
    assert no_source_payload is not None
    missing = no_source_payload["lex_unified_chat"]["source_verification"]["missing_information"]
    assert any("fonte contabile" in item for item in missing)


def test_lex_draft_request_to_pec_uses_governed_context_before_drafting():
    from lex.operational_knowledge.integration import _should_defer_to_public_legal_research
    from lex.operational_knowledge.query_router import OperationalQueryRouter
    from lex.research.request_profile import classify_request

    question = "scrivi risposta alla PEC di Rossi"
    profile = classify_request(question)

    assert profile.drafting_mode is True
    assert OperationalQueryRouter().route(question).intent == "draft_communication"
    assert _should_defer_to_public_legal_research(
        question,
        metadata={"request_profile": profile.to_dict()},
        studio_context={"focus_topic": "pec_firma", "request_profile": profile.to_dict()},
    ) is False


def test_bounded_chat_payload_exposes_studio_reasoner_links_map_and_timeline(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.http_bounded_bridge import build_bounded_http_payload
    from lex.operational_knowledge.models import (
        OperationalAnswer,
        OperationalObjectReference,
        OperationalRoute,
        OperationalSourceReference,
    )
    from lex.research.request_profile import classify_request

    reasoner_report = {
        "name": "Lex Studio Reasoner",
        "mode": "llm_rag_governato",
        "entity_map": {
            "nodes": [
                {
                    "type": "fascicolo",
                    "id": "fas-1",
                    "label": "RG 10/2026",
                    "source_id": "fascicoli",
                    "action_url": "/fascicoli/fas-1",
                },
                {
                    "type": "documento",
                    "id": "doc-1",
                    "label": "ricorso.pdf",
                    "source_id": "documenti_fascicolo",
                    "action_url": "/fascicoli/fas-1/documenti/doc-1/editor",
                },
            ],
            "relations": [{"from": "fascicolo:fas-1", "to": "documento:doc-1", "label": "contiene"}],
        },
        "fascicolo_timeline": [
            {
                "date": "2026-05-10",
                "type": "documento",
                "source_id": "documenti_fascicolo",
                "object_id": "doc-1",
                "label": "ricorso.pdf",
                "action_url": "/fascicoli/fas-1/documenti/doc-1/editor",
                "fascicolo_id": "fas-1",
            }
        ],
        "rag_policy": {
            "tenant_aware": True,
            "internal_sources_only": True,
            "excludes_public_legal_sources": True,
            "no_legacy_aggregator": True,
            "no_raw_prompt_context": True,
        },
    }

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            assert kwargs["metadata"]["fascicolo_id"] == "fas-1"
            return OperationalAnswer(
                handled=True,
                answer="Documenti del fascicolo: [ricorso.pdf](/fascicoli/fas-1/documenti/doc-1/editor).",
                route=OperationalRoute("documenti_fascicolo", "documenti_fascicolo", ("fascicoli", "documenti_fascicolo"), ""),
                sources=[
                    OperationalSourceReference(
                        source_id="documenti_fascicolo",
                        source_name="Documenti fascicolo",
                        source_type="studio",
                        object_type="documento",
                        object_id="doc-1",
                        title="ricorso.pdf",
                        confidence=0.91,
                        metadata={"action_url": "/fascicoli/fas-1/documenti/doc-1/editor"},
                    )
                ],
                objects=[
                    OperationalObjectReference(
                        object_type="fascicolo",
                        object_id="fas-1",
                        label="Apri fascicolo",
                        source_id="fascicoli",
                        action_url="/fascicoli/fas-1",
                    ),
                    OperationalObjectReference(
                        object_type="documento",
                        object_id="doc-1",
                        label="Apri ricorso.pdf",
                        source_id="documenti_fascicolo",
                        action_url="/fascicoli/fas-1/documenti/doc-1/editor",
                    ),
                ],
                confidence=0.91,
                metadata={
                    "operational_layer": True,
                    "studio_reasoner": reasoner_report,
                    "reasoner_mode": "llm_rag_governato",
                    "rag_governato": True,
                },
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    question = "Analizza i documenti presenti nel fascicolo"
    profile = classify_request(question)
    payload = build_bounded_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"messages": [], "fascicolo_id": "fas-1"},
        current_user_message=question,
        resolved_effective_question=question,
        studio_context={"focus_topic": "fascicoli", "request_profile": profile.to_dict()},
        attachments=[],
    )

    assert payload is not None
    assert payload["workflow"] == "operational_knowledge"
    assert payload["studio_reasoner"]["mode"] == "llm_rag_governato"
    assert payload["rag_governato"] is True
    assert payload["reasoner_mode"] == "llm_rag_governato"
    assert payload["entity_map"]["nodes"][1]["action_url"].endswith("/documenti/doc-1/editor")
    assert payload["fascicolo_timeline"][0]["object_id"] == "doc-1"
    assert any(link["url"] == "/fascicoli/fas-1/documenti/doc-1/editor" for link in payload["operational_links"])
    assert payload["evidence_summary"]["studio_reasoner"] is True
    assert payload["evidence_summary"]["operational_link_count"] == 2
    assert payload["evidence_summary"]["entity_count"] == 2
    assert payload["evidence_summary"]["timeline_event_count"] == 1


def test_http_bridge_routes_ultima_pec_ricevuta_to_operational_layer_without_draft(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.http_bounded_bridge import build_bounded_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference
    from lex.research.request_profile import classify_request

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            assert kwargs["metadata"]["request_profile"]["intent"] == "comunicazioni_lookup"
            return OperationalAnswer(
                handled=True,
                answer="Ultima PEC ricevuta: Esito deposito del 19/05/2026, con 2 allegati.",
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

    question = "ultima pec ricevuta"
    profile = classify_request(question)
    payload = build_bounded_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"messages": []},
        current_user_message=question,
        resolved_effective_question=question,
        studio_context={"focus_topic": "pec_firma", "request_profile": profile.to_dict()},
        attachments=[],
    )

    assert profile.intent == "comunicazioni_lookup"
    assert payload is not None
    assert payload["workflow"] == "operational_knowledge"
    assert "Ultima PEC ricevuta" in payload["answer"]
    assert "BOZZA" not in payload["answer"]


def test_pec_deposito_control_question_is_lookup_not_draft():
    from lex.operational_knowledge.integration import _should_defer_to_public_legal_research
    from lex.operational_knowledge.query_router import OperationalQueryRouter
    from lex.research.request_profile import classify_request

    question = "Che PEC di deposito devo controllare?"
    profile = classify_request(question)
    route = OperationalQueryRouter().route(question, metadata={"focus_topic": "pec_firma"})

    assert profile.intent == "comunicazioni_lookup"
    assert profile.drafting_mode is False
    assert route is not None
    assert route.intent == "communications_lookup"
    assert "email_pec" in route.source_ids
    assert "pec_audit" in route.source_ids
    assert _should_defer_to_public_legal_research(
        question,
        metadata={"focus_topic": "pec_firma", "request_profile": profile.to_dict()},
        studio_context={"focus_topic": "pec_firma", "request_profile": profile.to_dict()},
    ) is False


def test_http_bridge_routes_pec_deposito_control_to_operational_layer_without_draft(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.http_bounded_bridge import build_bounded_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference
    from lex.research.request_profile import classify_request

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            assert kwargs["metadata"]["request_profile"]["intent"] == "comunicazioni_lookup"
            return OperationalAnswer(
                handled=True,
                answer=(
                    "PEC da controllare: Esito deposito del 19 maggio 2026. "
                    "Verifica accettazione, consegna, esito controlli e accettazione finale; nessuna bozza da preparare."
                ),
                route=OperationalRoute("communications_lookup", "communications_lookup", ("email_pec", "pec_audit"), ""),
                sources=[
                    OperationalSourceReference(
                        source_id="pec_audit",
                        source_name="Controlli automatici PEC",
                        source_type="pec_audit",
                        object_type="pec",
                        object_id="pec-1",
                        title="Esito deposito",
                        confidence=0.9,
                    )
                ],
                confidence=0.9,
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    question = "Che PEC di deposito devo controllare?"
    profile = classify_request(question)
    payload = build_bounded_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"messages": []},
        current_user_message=question,
        resolved_effective_question=question,
        studio_context={"focus_topic": "pec_firma", "request_profile": profile.to_dict()},
        attachments=[],
    )

    assert payload is not None
    assert payload["workflow"] == "operational_knowledge"
    assert "PEC da controllare" in payload["answer"]
    assert "BOZZA" not in payload["answer"]


def test_http_bridge_routes_contesto_studio_to_governed_operational_layer(monkeypatch):
    monkeypatch.delenv("LEX_OPERATIONAL_KNOWLEDGE_ENABLED", raising=False)
    from lex.http_bounded_bridge import build_bounded_http_payload
    from lex.operational_knowledge.models import OperationalAnswer, OperationalRoute, OperationalSourceReference
    from lex.research.request_profile import classify_request

    class _FakeOperationalKnowledgeService:
        def __init__(self, *args, **kwargs):
            pass

        def answer(self, **kwargs):
            assert kwargs["metadata"]["request_profile"]["intent"] == "studio_context_lookup"
            return OperationalAnswer(
                handled=True,
                answer="Ho consultato il contesto operativo autorizzato dello studio: clienti, fascicoli, scadenze e agenda.",
                route=OperationalRoute("studio_context_overview", "studio_context_overview", ("clienti", "fascicoli", "agenda"), ""),
                sources=[
                    OperationalSourceReference(
                        source_id="fascicoli",
                        source_name="Fascicoli",
                        source_type="studio",
                        object_type="fascicolo",
                        object_id="fas-1",
                        title="Fascicolo Rossi",
                        confidence=0.86,
                    )
                ],
                confidence=0.86,
                metadata={"operational_layer": True},
            )

    monkeypatch.setattr("lex.operational_knowledge.integration.OperationalKnowledgeService", _FakeOperationalKnowledgeService)

    question = "usa tutto il contesto studio"
    profile = classify_request(question)
    payload = build_bounded_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"messages": []},
        current_user_message=question,
        resolved_effective_question=question,
        studio_context={"focus_topic": "studio", "request_profile": profile.to_dict()},
        attachments=[],
    )

    assert profile.intent == "studio_context_lookup"
    assert payload is not None
    assert payload["workflow"] == "operational_knowledge"
    assert payload["external_sources_used"] is False
    assert "contesto operativo autorizzato" in payload["answer"]


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

    corte_cost_payload = build_operational_http_payload(
        user=_User(_all_permissions()),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"external_sources_reason": "riferimento giurisprudenziale esatto"},
        current_user_message="Sentenza della Corte Costituzionale n. 50 del 27/1/2026",
        resolved_effective_question="Sentenza della Corte Costituzionale n. 50 del 27/1/2026",
        studio_context={"focus_topic": "sentenze_web", "request_profile": {"intent": "giurisprudenza_specifica"}},
    )

    assert corte_cost_payload is None


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
                    "Ho trovato una fonte ufficiale collegata alla richiesta.\n"
                    "### Allegato ufficiale\n"
                    "- Allegato: **Ordinanza di rimessione**.\n"
                    "- PDF ufficiale: [Apri PDF ufficiale](https://www.cortedicassazione.it/resources/cms/documents/Nota%5FUfficio%5FSpoglio%5FV%5FSez.%5Fpenale%5FRG%5F9966%5F2026%5F1.pdf)."
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
    assert "Allegato: **Ordinanza di rimessione**." in payload["answer"]
    assert "Apri PDF ufficiale" in payload["answer"]


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
