from __future__ import annotations

from lex.knowledge.knowledge_base import KnowledgeBase
from lex.retrieval.learning_memory import search_learning_memory

_URL_2043 = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262~art2043!vig="
_ESTRATTO_2043 = (
    "Art. 2043. Risarcimento per fatto illecito. Qualunque fatto doloso o colposo, "
    "che cagiona ad altri un danno ingiusto, obbliga colui che ha commesso il fatto a risarcire il danno."
)


def _semina(kb: KnowledgeBase, *, url: str = _URL_2043, tier: str = "tier_1", allowed: bool = True,
            status: str = "ok", excerpt: str = _ESTRATTO_2043) -> None:
    kb.append(
        "source_readings",
        f"read-{url}",
        {
            "url": url,
            "title": "Art. 2043 c.c. (vigente) — Normattiva",
            "area": "civile",
            "status": status,
            "source_id": "archivio_locale:normattiva",
            "text_characters": len(excerpt),
            "citations_normalized": ["art. 2043 c.c."],
            "terms_normalized": ["danno ingiusto"],
            "excerpt": excerpt,
            "fetched_at": "2026-07-04T02:40:00+00:00",
        },
    )
    kb.append(
        "trust_assessments",
        f"trust-{url}",
        {"url": url, "tier": tier, "allowed_for_learning": allowed, "domain": "www.normattiva.it"},
    )


def test_lettura_fidata_diventa_evidenza_con_ancora_ufficiale(tmp_path):
    kb = KnowledgeBase(tmp_path / "memoria")
    _semina(kb)
    rows = search_learning_memory("Cosa stabilisce l'art. 2043 c.c.?", memory_dir=kb.memory_dir)
    assert len(rows) == 1
    row = rows[0]
    assert "danno ingiusto" in row["content"]
    assert row["official_url"] == _URL_2043
    assert row["trust_class"] == "A" and row["source_level"] == 1
    assert row["authority"] == "www.normattiva.it"


def test_senza_valutazione_di_fiducia_niente_evidenza(tmp_path):
    kb = KnowledgeBase(tmp_path / "memoria")
    kb.append(
        "source_readings",
        "read-orfano",
        {"url": _URL_2043, "title": "Art. 2043", "status": "ok", "excerpt": _ESTRATTO_2043,
         "citations_normalized": ["art. 2043 c.c."]},
    )
    assert search_learning_memory("art. 2043", memory_dir=kb.memory_dir) == []


def test_tier_non_ammesso_o_lettura_non_ok_esclusi(tmp_path):
    kb = KnowledgeBase(tmp_path / "memoria")
    _semina(kb, url="https://blog.example.com/2043", tier="tier_3")
    _semina(kb, url="https://www.normattiva.it/bloccata", status="robots_blocked")
    _semina(kb, url="https://www.normattiva.it/senza-estratto", excerpt="")
    assert search_learning_memory("art. 2043 danno ingiusto", memory_dir=kb.memory_dir) == []


def test_query_senza_overlap_o_vuota_fail_closed(tmp_path):
    kb = KnowledgeBase(tmp_path / "memoria")
    _semina(kb)
    assert search_learning_memory("licenziamento giusta causa", memory_dir=kb.memory_dir) == []
    assert search_learning_memory("", memory_dir=kb.memory_dir) == []


def test_memoria_assente_lista_vuota_senza_side_effect(tmp_path):
    base = tmp_path / "non-esiste"
    assert search_learning_memory("art. 2043", memory_dir=base) == []
    assert not base.exists()
