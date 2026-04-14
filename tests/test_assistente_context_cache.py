from pathlib import Path

from web.services.assistente_context_cache import (
    build_file_fingerprint,
    cached_compute,
    clear_cached_values,
    question_signature,
)


def test_cached_compute_riusa_il_valore_finche_il_ttl_e_valido():
    clear_cached_values("lex-test")
    calls = {"count": 0}

    def builder():
        calls["count"] += 1
        return {"build": calls["count"]}

    first = cached_compute("lex-test", ("sessione", "contesto"), 60, builder)
    second = cached_compute("lex-test", ("sessione", "contesto"), 60, builder)

    assert first == {"build": 1}
    assert second == {"build": 1}
    assert calls["count"] == 1


def test_build_file_fingerprint_cambia_quando_cambia_il_file(tmp_path: Path):
    target = tmp_path / "studio.json"
    target.write_text('{"studio":"a"}', encoding="utf-8")
    first = build_file_fingerprint([str(target)])

    target.write_text('{"studio":"b","versione":2}', encoding="utf-8")
    second = build_file_fingerprint([str(target)])

    assert first != second


def test_question_signature_compatta_e_deduplica_i_termini():
    signature = question_signature("Agenda agenda cliente udienza RG 123/2026", limit=6)

    assert signature.startswith("agenda|cliente|udienza")
    assert signature.count("agenda") == 1
