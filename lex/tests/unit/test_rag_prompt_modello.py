"""Modulo 1 del risanamento RAG di Lex: prompt e chiamata al modello.

Un finto client Ollama registra il payload inviato a /api/chat: si verifica che
le domande giuridiche non contengano i dati dello studio, il formato delle
fonti, il budget di contesto, i parametri unici da variabili d'ambiente,
"think": false, la rimozione di <think> e l'avviso quando il modello non risponde.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from lex.contracts import EvidenceItem
from lex.prompts.legal_rag_prompt import LEX_LEGAL_RAG_SYSTEM_PROMPT
from lex.providers import ollama_provider
from lex.providers.local_llm import LocalLLMProvider
from lex.providers.ollama_provider import OllamaProvider
from lex.providers.prompt_budget import (
    ThinkStreamFilter,
    build_rag_prompt,
    estimate_tokens,
    format_evidence_item,
    strip_think,
)
from lex.settings import LexGenerationSettings, lex_generation_settings

_ENV_GENERAZIONE = (
    "LEX_NUM_CTX",
    "LEX_NUM_PREDICT",
    "LEX_TEMPERATURE",
    "LEX_LLM_TIMEOUT_S",
    "LEX_THINK",
    "LEX_MAX_EVIDENCE_ITEMS",
    "LEX_EVIDENCE_MAX_CHARS",
    "LEX_STUDIO_CONTEXT_MAX_CHARS",
)

CODICE_FISCALE = "RSSMRA80A01H501U"


@pytest.fixture(autouse=True)
def _env_pulito(monkeypatch):
    for name in _ENV_GENERAZIONE:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "lex.providers.ollama_provider._resolve_runtime",
        lambda: {"api_base_url": "http://127.0.0.1:11434/api", "chat_model": "qwen3.5:9b", "keep_alive": "10m"},
    )


class FintoOllama:
    """Sostituisce `requests.request` di pct.local_ai e registra i payload /api/chat."""

    def __init__(self, contenuto: str = "Risposta fondata sulla fonte [1].", *, stats: dict | None = None,
                 rifiuta_think: bool = False, errore: Exception | None = None) -> None:
        self.contenuto = contenuto
        self.stats = stats or {"prompt_eval_count": 900, "eval_count": 40}
        self.rifiuta_think = rifiuta_think
        self.errore = errore
        self.payloads: list[dict] = []

    def __call__(self, method, url, json=None, timeout=None):  # noqa: A002 - firma di requests.request
        self.payloads.append({"url": url, "payload": json, "timeout": timeout})
        if self.errore is not None:
            raise self.errore
        finto = self
        rifiutata = bool(finto.rifiuta_think and "think" in (json or {}))

        class Risposta:
            status_code = 400 if rifiutata else 200
            text = '{"error":"\\"gemma3:1b\\" does not support thinking"}' if rifiutata else ""

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.HTTPError("400 Client Error", response=self)

            def json(self):
                return {"message": {"role": "assistant", "content": finto.contenuto}, "done": True, **finto.stats}

        return Risposta()


@pytest.fixture
def finto_ollama(monkeypatch):
    from pct.runtime_resilience import clear_runtime_circuit_breakers

    clear_runtime_circuit_breakers()
    finto = FintoOllama()
    monkeypatch.setattr("pct.local_ai.requests.request", finto)
    yield finto
    clear_runtime_circuit_breakers()


def _norma(numero: int = 1, testo: str = "Qualunque fatto doloso o colposo che cagiona ad altri un danno ingiusto obbliga al risarcimento.") -> EvidenceItem:
    return EvidenceItem(
        source_type="normativa",
        source_id=f"cc-{numero}",
        title="Codice civile",
        content=f"Art. {2043 + numero}. {testo}",
        score=0.9,
        metadata={
            "fonte": "Normattiva",
            "vigenza": "VIGENTE",
            "data": "1942-03-16",
            "metadata": {"article_number": str(2043 + numero), "urn": "urn:nir:stato:regio.decreto:1942-03-16;262"},
        },
        trust_class="A",
        source_level=1,
        verified_reference=True,
    )


def _sentenza() -> EvidenceItem:
    return EvidenceItem(
        source_type="giurisprudenza",
        source_id="cass-1",
        title="Cassazione civile",
        content="La perdita di chance e' risarcibile se seria e apprezzabile.",
        score=0.88,
        metadata={
            "organo": "Corte di cassazione",
            "numero_sentenza": "12345",
            "anno_sentenza": "2024",
            "sezione": "III",
            "ecli": "ECLI:IT:CASS:2024:12345CIV",
            "data_deposito": "2024-05-10",
        },
    )


def _contesto_studio() -> dict:
    """Contesto come lo costruisce LexContextBuilder: dati dello studio e clienti."""
    return {
        "workflow": "normativa",
        "studio": {
            "prompt_block": (
                "Profilo richiesta: preparazione udienza.\n\n"
                "=== PEC E CANALI EMAIL ===\nPEC studio configurata: studio@pec.example.it.\n\n"
                "=== AGENDA ===\nUdienza Esposito c. Verdi il 08/07/2026 11:00 con Esposito Anna.\n\n"
                f"=== CLIENTI ===\nEsposito Anna, codice fiscale {CODICE_FISCALE}.\n"
            ),
            "sources": [{"title": "x", "text": "y" * 5000}],
            "request_metadata": {"blob": "z" * 20000},
        },
        "agenda": [{"titolo": "Udienza Esposito", "cliente": "Esposito Anna", "codice_fiscale": CODICE_FISCALE}],
        "economico": {"best_practice": "w" * 60000},
        "runtime": {"chat_model": "qwen3.5:9b"},
    }


def _genera(workflow: str, *, query: str = "Cosa prevede l'art. 2044 c.c.?", evidence=None, context=None):
    return OllamaProvider().generate(
        request=SimpleNamespace(query=query),
        context=_contesto_studio() if context is None else context,
        evidence={"items": [_norma()]} if evidence is None else evidence,
        workflow=workflow,
    )


def _messaggi(finto: FintoOllama) -> tuple[str, str]:
    payload = finto.payloads[-1]["payload"]
    return payload["messages"][0]["content"], payload["messages"][-1]["content"]


# ---------------------------------------------------------------------------
# 1. Workflow giuridici senza i dati dello studio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("workflow", ["normativa", "giurisprudenza", "prassi", "fonti", "giurisprudenza_specifica"])
def test_workflow_giuridico_non_invia_i_dati_dello_studio(finto_ollama, workflow):
    evidence = {"items": [_sentenza(), _norma()]}
    _genera(workflow, evidence=evidence)

    system, user = _messaggi(finto_ollama)
    assert system == LEX_LEGAL_RAG_SYSTEM_PROMPT
    assert user.startswith("Domanda:\nCosa prevede l'art. 2044 c.c.?\n\nFonti:\n[1] ")
    assert "Dati dello studio" not in user
    assert "Contesto sessione" not in user
    assert CODICE_FISCALE not in user
    assert "Esposito" not in user
    assert "studio@pec.example.it" not in user
    assert len(user) < 3000


def test_system_prompt_giuridico_fisso_e_con_regole(finto_ollama):
    _genera("normativa")
    _genera("giurisprudenza", evidence={"items": [_sentenza()]})
    primo = finto_ollama.payloads[0]["payload"]["messages"][0]["content"]
    secondo = finto_ollama.payloads[1]["payload"]["messages"][0]["content"]
    assert primo == secondo == LEX_LEGAL_RAG_SYSTEM_PROMPT
    for regola in ("SOLO le Fonti", "[1]", "non determinabile con le fonti disponibili", "vigenza",
                   "AFFIDABILITA' DEI RIFERIMENTI LEGALI", "Contratto qualita' Lex AI"):
        assert regola in primo


def test_workflow_normativa_registrato():
    from lex.workflows import WORKFLOW_REGISTRY, NormativaWorkflow, system_prompt_for

    assert WORKFLOW_REGISTRY["normativa"] is NormativaWorkflow
    assert system_prompt_for("normativa") == LEX_LEGAL_RAG_SYSTEM_PROMPT


def test_workflow_sui_dati_dello_studio_riceve_estratto_ridotto(finto_ollama):
    _genera("udienza", query="Prepara l'udienza Esposito")

    _system, user = _messaggi(finto_ollama)
    assert "\n\nDati dello studio:\n" in user
    assert "Udienza Esposito c. Verdi" in user
    # Mai codici fiscali, canali PEC o blocchi tecnici del contesto.
    assert CODICE_FISCALE not in user
    assert "studio@pec.example.it" not in user
    assert "zzzz" not in user and "wwww" not in user
    assert len(user) < 3000


def test_domanda_generica_di_diritto_in_chat_senza_dati_studio(finto_ollama):
    _genera("question_answering", query="Che differenza c'e' tra prescrizione e decadenza?")
    _system, user = _messaggi(finto_ollama)
    assert "Dati dello studio" not in user
    assert CODICE_FISCALE not in user


# ---------------------------------------------------------------------------
# 2. Formato delle fonti
# ---------------------------------------------------------------------------


def test_formato_fonte_normativa_con_articolo_urn_vigenza_data():
    blocco, troncato = format_evidence_item(1, _norma())
    intestazione, testo = blocco.split("\n", 1)
    assert intestazione == (
        "[1] Codice civile (Normattiva) · art. 2044 · urn:nir:stato:regio.decreto:1942-03-16;262"
        " · vigente · 16/03/1942"
    )
    assert testo.startswith("Art. 2044.")
    assert troncato is False


def test_formato_fonte_sentenza_con_ecli():
    blocco, _ = format_evidence_item(2, _sentenza())
    assert blocco.splitlines()[0] == (
        "[2] Cassazione civile (Corte di cassazione) · n. 12345/2024, sez. III · ECLI:IT:CASS:2024:12345CIV · 10/05/2024"
    )


def test_formato_fonte_tronca_ogni_passaggio():
    blocco, troncato = format_evidence_item(1, _norma(testo="parola " * 1000))
    testo = blocco.split("\n", 1)[1]
    assert troncato is True
    assert len(testo) <= 1600
    assert testo.endswith("…")


def test_numero_massimo_fonti_coerente_con_la_guardia(finto_ollama):
    items = [_norma(i, testo="breve") for i in range(15)]
    _genera("normativa", evidence={"items": items})
    _system, user = _messaggi(finto_ollama)
    assert "[12] " in user
    assert "[13] " not in user


# ---------------------------------------------------------------------------
# 3. Budget di contesto
# ---------------------------------------------------------------------------


def test_budget_toglie_le_fonti_meno_rilevanti_non_system_ne_domanda(monkeypatch, finto_ollama):
    monkeypatch.setenv("LEX_NUM_CTX", "2048")
    monkeypatch.setenv("LEX_NUM_PREDICT", "700")
    items = [_norma(i, testo=f"passaggio {i} " + "testo normativo " * 120) for i in range(10)]
    domanda = "Quali sono i presupposti del risarcimento? " * 5

    draft = _genera("normativa", query=domanda, evidence={"items": items})

    system, user = _messaggi(finto_ollama)
    assert system == LEX_LEGAL_RAG_SYSTEM_PROMPT
    assert user.startswith("Domanda:\n" + " ".join(domanda.split()) + "\n\nFonti:\n")
    budget = draft.metadata["prompt_budget"]
    assert budget["evidenze_incluse"][0] == 1
    assert budget["evidenze_escluse_budget"]
    # Si escludono le meno rilevanti: quelle in coda alla lista ordinata.
    assert budget["evidenze_escluse_budget"] == list(range(len(budget["evidenze_incluse"]) + 1, 11))
    assert estimate_tokens(system) + estimate_tokens(user) <= 2048 - 700 - 64
    assert budget["prompt_tokens_stimati"] <= budget["budget_input_tokens"]
    assert "passaggio 0" in user and "passaggio 9" not in user


def test_budget_non_taglia_mai_la_domanda_anche_se_sfora():
    settings = LexGenerationSettings(num_ctx=1024, num_predict=700)
    domanda = "Domanda molto lunga sul danno ingiusto. " * 200
    plan = build_rag_prompt(
        system_prompt=LEX_LEGAL_RAG_SYSTEM_PROMPT,
        question=domanda,
        evidence={"items": [_norma()]},
        workflow="normativa",
        context={},
        settings=settings,
    )
    assert plan.system_prompt == LEX_LEGAL_RAG_SYSTEM_PROMPT
    assert " ".join(domanda.split()) in plan.user_message
    assert plan.metadata["budget_superato"] is True
    assert plan.metadata["evidenze_escluse_budget"] == [1]


# ---------------------------------------------------------------------------
# 4. Parametri di generazione unificati
# ---------------------------------------------------------------------------


def test_parametri_default():
    settings = lex_generation_settings()
    assert (settings.num_ctx, settings.num_predict, settings.temperature, settings.timeout_s, settings.think) == (
        8192, 700, 0.2, 300, False,
    )


def test_parametri_letti_da_env_e_usati_da_entrambi_i_percorsi(monkeypatch, finto_ollama):
    monkeypatch.setenv("LEX_NUM_CTX", "16384")
    monkeypatch.setenv("LEX_NUM_PREDICT", "900")
    monkeypatch.setenv("LEX_TEMPERATURE", "0,3")
    monkeypatch.setenv("LEX_LLM_TIMEOUT_S", "450")

    _genera("normativa")
    governato = finto_ollama.payloads[-1]
    streaming = LocalLLMProvider().build_chat_payload(
        runtime={"chat_model": "qwen3.5:9b"}, llm_messages=[{"role": "user", "content": "x"}], system_content="s"
    )

    attese = {"temperature": 0.3, "num_ctx": 16384, "num_predict": 900}
    assert governato["payload"]["options"] == attese
    assert streaming["options"] == attese
    assert governato["timeout"] == 450
    assert governato["payload"]["think"] is False and streaming["think"] is False


def test_parametri_env_non_validi_tornano_ai_default(monkeypatch):
    monkeypatch.setenv("LEX_NUM_CTX", "tanti")
    monkeypatch.setenv("LEX_TEMPERATURE", "9")
    monkeypatch.setenv("LEX_THINK", "forse")
    settings = lex_generation_settings()
    assert settings.num_ctx == 8192 and settings.temperature == 0.2 and settings.think is False


# ---------------------------------------------------------------------------
# 5. think=false e rimozione di <think>
# ---------------------------------------------------------------------------


def test_think_false_nel_payload_top_level(finto_ollama):
    _genera("normativa")
    payload = finto_ollama.payloads[-1]["payload"]
    assert payload["think"] is False
    assert "think" not in payload["options"]


def test_think_true_da_env(monkeypatch, finto_ollama):
    monkeypatch.setenv("LEX_THINK", "1")
    _genera("normativa")
    assert finto_ollama.payloads[-1]["payload"]["think"] is True


def test_modello_senza_ragionamento_riprova_senza_campo_think(finto_ollama):
    finto_ollama.rifiuta_think = True
    draft = _genera("normativa")
    assert "think" in finto_ollama.payloads[0]["payload"]
    assert "think" not in finto_ollama.payloads[1]["payload"]
    assert draft.metadata["status"] == "ok"


def test_rimozione_think_dalla_risposta(finto_ollama):
    finto_ollama.contenuto = "<think>ragionamento interno</think>\nL'art. 2044 disciplina la legittima difesa [1]."
    draft = _genera("normativa")
    assert draft.text == "L'art. 2044 disciplina la legittima difesa [1]."


@pytest.mark.parametrize(
    ("grezzo", "atteso"),
    [
        ("<think>a</think>Risposta", "Risposta"),
        ("<THINK>\na\n</THINK>\n\nRisposta", "Risposta"),
        ("Risposta<think>ragionamento non chiuso", "Risposta"),
        ("ragionamento senza apertura</think>Risposta", "Risposta"),
        ("<think>a</think>Uno<think>b</think> due", "Uno due"),
        ("Nessun ragionamento", "Nessun ragionamento"),
    ],
)
def test_strip_think(grezzo, atteso):
    assert strip_think(grezzo) == atteso


def test_filtro_think_in_streaming_con_tag_spezzati():
    filtro = ThinkStreamFilter()
    pezzi = ["Ciao ", "<th", "ink>segr", "eto</thi", "nk>", "mondo <b>", "</b>"]
    assert "".join(filtro.feed(p) for p in pezzi) + filtro.flush() == "Ciao mondo <b></b>"


def test_streaming_rimuove_think_e_usa_timeout_unico(monkeypatch):
    monkeypatch.setenv("LEX_LLM_TIMEOUT_S", "321")
    chiamate = {}

    class FintoRequests:
        class exceptions:
            ConnectionError = requests.ConnectionError
            Timeout = requests.Timeout

        @staticmethod
        def post(url, json=None, stream=False, timeout=None):
            chiamate["timeout"] = timeout
            righe = [
                {"message": {"content": "<think>pen"}},
                {"message": {"content": "so</think>Ri"}},
                {"message": {"content": "sposta"}, "done": True},
            ]
            return SimpleNamespace(status_code=200, iter_lines=lambda: [__import__("json").dumps(r) for r in righe])

    gen = LocalLLMProvider().stream_chat(
        requests_module=FintoRequests, api_base_url="http://x/api", payload={"think": False}, base_url="http://x"
    )
    corpo = "".join(gen())
    token = "".join(json.loads(r[5:])["token"] for r in corpo.split("\n\n") if r.startswith("data: {"))
    assert token == "Risposta"
    assert chiamate["timeout"] == 321


# ---------------------------------------------------------------------------
# 6. Errore o timeout del modello: avviso esplicito, mai silenzioso
# ---------------------------------------------------------------------------


def test_timeout_del_modello_avvisa_l_utente(monkeypatch, finto_ollama):
    finto_ollama.errore = requests.Timeout("read timed out")
    monkeypatch.setattr("lex.providers.ollama_runtime.refresh_live_ollama_runtime", lambda: {})

    draft = _genera("atto", query="scrivi una diffida", context={"focus": "redazione"})

    assert draft.text.startswith("Il modello locale non ha risposto entro 300 secondi.")
    assert draft.metadata["status"] == "fallback_runtime_unavailable"
    assert draft.metadata["model_error_kind"] == "timeout"
    assert draft.metadata["model_error_notice"] in draft.text
    assert "ollama" not in draft.text.lower()


def test_modello_non_raggiungibile_avvisa_l_utente(monkeypatch):
    monkeypatch.setattr(
        "lex.providers.ollama_provider._call_ollama",
        lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("Failed to resolve 'ollama'")),
    )
    monkeypatch.setattr("lex.providers.ollama_runtime.refresh_live_ollama_runtime", lambda: {})
    draft = _genera("normativa")
    assert draft.text.startswith("Il modello locale non è raggiungibile in questo momento.")
    assert "Failed to resolve" not in draft.text


def test_risposta_solo_ragionamento_conta_come_risposta_vuota(monkeypatch, finto_ollama):
    finto_ollama.contenuto = "<think>solo ragionamento, nessuna risposta"
    monkeypatch.setattr("lex.providers.ollama_runtime.refresh_live_ollama_runtime", lambda: {})
    draft = _genera("normativa")
    assert draft.text.startswith("Il modello locale non ha prodotto una risposta.")
    assert draft.metadata["model_error_kind"] == "vuoto"


# ---------------------------------------------------------------------------
# 7. Telemetria: token stimati e possibile troncamento
# ---------------------------------------------------------------------------


def test_telemetria_budget_e_prompt_eval_count(finto_ollama):
    draft = _genera("normativa", evidence={"items": [_norma(i) for i in range(3)]})
    budget = draft.metadata["prompt_budget"]
    assert budget["evidenze_incluse"] == [1, 2, 3]
    assert budget["prompt_tokens_stimati"] == budget["system_tokens_stimati"] + budget["user_tokens_stimati"]
    assert draft.metadata["prompt_eval"]["prompt_eval_count"] == 900
    assert draft.metadata["generation"]["num_ctx"] == 8192


def test_avviso_possibile_troncamento(finto_ollama, caplog):
    finto_ollama.stats = {"prompt_eval_count": 50}
    items = [_norma(i, testo="testo normativo " * 90) for i in range(6)]
    with caplog.at_level(logging.WARNING, logger="lex.prompt_budget"):
        draft = _genera("normativa", evidence={"items": items})
    assert draft.metadata["prompt_eval"]["possibile_troncamento"] is True
    assert "possibile troncamento" in caplog.text


# ---------------------------------------------------------------------------
# 8. Modello configurabile senza toccare il codice
# ---------------------------------------------------------------------------


def test_modello_da_env_prevale_sulla_configurazione(tmp_path: Path, monkeypatch):
    from pct.local_ai import LocalAIService

    config = tmp_path / "config" / "studio.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"studio": {"nome": "Studio"}, "ai": {"enabled": True, "chat_model": "gemma3:1b"}}))
    service = LocalAIService(
        db_path=str(tmp_path / "local_ai.db"),
        policy_path=str(Path(__file__).resolve().parents[3] / "config" / "ai-policy.json"),
        config_path=str(config),
        app_root=str(Path(__file__).resolve().parents[3]),
        models_path=str(tmp_path / "models"),
    )
    monkeypatch.delenv("PCT_LOCAL_AI_CHAT_MODEL", raising=False)
    assert service._load_settings().chat_model == "gemma3:1b"
    monkeypatch.setenv("PCT_LOCAL_AI_CHAT_MODEL", "qwen3.5:9b")
    assert service._load_settings().chat_model == "qwen3.5:9b"


def test_modello_risolto_usato_nel_payload(finto_ollama):
    _genera("normativa")
    assert finto_ollama.payloads[-1]["payload"]["model"] == "qwen3.5:9b"
    assert ollama_provider._resolve_runtime()["chat_model"] == "qwen3.5:9b"
