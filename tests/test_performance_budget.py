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
    assert '"startup_ms": 4000' in text


def test_performance_smoke_misura_startup_su_mediana_di_avvii_a_freddo():
    """Il budget di avvio deve restare legato alla mediana, non a un campione singolo.

    La soglia `startup_ms` è passata da 3200 a 4000 perché il valore precedente
    non era raggiungibile in modo stabile sui runner condivisi. Il presidio
    sostitutivo richiesto da AGENTS.md è questo: la misura usa la mediana di più
    avvii a freddo eseguiti in processi separati, così un picco isolato non
    decide l'esito ma una regressione reale sposta la mediana e fa fallire il
    gate. Se qualcuno rimuove la mediana lasciando la soglia alta, il presidio
    si indebolisce senza che nessuno se ne accorga: questo test lo impedisce.
    """

    text = Path("tools/performance_smoke.py").read_text(encoding="utf-8")

    assert "--repeat" in text
    assert "--single-run" in text
    assert "statistics.median" in text
    assert "_aggregate_samples" in text
    assert "subprocess.run" in text


def test_performance_smoke_pulisce_i_dati_temporanei_di_ogni_campione():
    """Con più campioni per esecuzione, gli alberi dati temporanei vanno rimossi."""

    text = Path("tools/performance_smoke.py").read_text(encoding="utf-8")

    assert "shutil.rmtree" in text


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
