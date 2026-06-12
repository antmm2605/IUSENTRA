from pathlib import Path

from lex.context.builder import LexContextBuilder
from lex.contracts import LexRequest


def test_performance_smoke_exists():
    assert Path("tools/performance_smoke.py").exists()


def test_performance_smoke_usa_contesto_deterministico_senza_web_esterno():
    text = Path("tools/performance_smoke.py").read_text(encoding="utf-8")

    assert "allow_external_research=False" in text
    assert '"benchmark_mode": "performance_smoke"' in text
    assert '"lightweight_context": True' in text
    assert '"disable_official_web": True' in text
    assert '"startup_ms": 3200' in text


def test_performance_smoke_costruisce_contesto_minimo():
    request = LexRequest(
        tenant_id="benchmark",
        user_id="superadmin",
        session_id="smoke-session",
        query="Misura prestazioni",
        fascicolo_id="FASC-001",
        document_id="DOC-001",
        metadata={
            "benchmark_mode": "performance_smoke",
            "disable_official_web": True,
            "lightweight_context": True,
        },
    )

    context = LexContextBuilder().build_request_context(request, "chat")

    assert context["runtime"]["performance_smoke"] is True
    assert context["studio"]["effective_question"] == "Misura prestazioni"
    assert "agenda" not in context
    assert "documenti" not in context
    assert "fascicolo" not in context
