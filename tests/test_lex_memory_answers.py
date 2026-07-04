"""La memoria di apprendimento autonomo alimenta le risposte di Lex.

Regressione della catena completa: memoria durevole seminata (lettura con
estratto + valutazione di fiducia tier_1) → domanda reale via
`/api/assistente/context` → la risposta contiene il TESTO della norma e
l'ancora ufficiale. Senza valutazione di fiducia la stessa lettura non deve
entrare (fail-closed).
"""

from __future__ import annotations

from pathlib import Path

from tests.test_lex_assistente_context_real_requests import _login, _seed_studio_con_moscato

URL_2043 = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262~art2043!vig="
ESTRATTO_2043 = (
    "Art. 2043. Risarcimento per fatto illecito. Qualunque fatto doloso o colposo, "
    "che cagiona ad altri un danno ingiusto, obbliga colui che ha commesso il fatto a risarcire il danno."
)


def _semina_memoria(root: Path, *, con_fiducia: bool) -> None:
    from lex.knowledge.knowledge_base import KnowledgeBase

    kb = KnowledgeBase(root / "intelligence" / "lex_memory")
    kb.append(
        "source_readings",
        "read-2043",
        {
            "url": URL_2043,
            "title": "Art. 2043 c.c. (vigente) — Normattiva",
            "area": "civile",
            "status": "ok",
            "source_id": "archivio_locale:normattiva",
            "text_characters": len(ESTRATTO_2043),
            "citations_normalized": ["art. 2043 c.c."],
            "terms_normalized": ["danno ingiusto"],
            "excerpt": ESTRATTO_2043,
            "fetched_at": "2026-07-04T02:40:00+00:00",
        },
    )
    if con_fiducia:
        kb.append(
            "trust_assessments",
            "trust-2043",
            {"url": URL_2043, "tier": "tier_1", "allowed_for_learning": True, "domain": "www.normattiva.it"},
        )


def _chiedi_2043(tmp_path: Path, monkeypatch, *, con_fiducia: bool) -> str:
    monkeypatch.setenv("PCT_DATA_ROOT", str(tmp_path / "data-root"))
    monkeypatch.delenv("IUSENTRA_DATA_DIR", raising=False)
    _semina_memoria(tmp_path / "data-root", con_fiducia=con_fiducia)
    app, studio, admin = _seed_studio_con_moscato(tmp_path / "app")
    with app.test_client() as client:
        _login(client, studio, admin)
        response = client.post(
            "/api/assistente/context",
            json={"question": "Cosa stabilisce l'art. 2043 c.c.?"},
        )
    payload = response.get_json() or {}
    assert response.status_code == 200 and payload.get("ok") is True
    return str(payload.get("answer", ""))


def test_memoria_appresa_alimenta_la_risposta_con_ancora_ufficiale(tmp_path, monkeypatch):
    answer = _chiedi_2043(tmp_path, monkeypatch, con_fiducia=True)
    assert "danno ingiusto" in answer  # testo della norma dall'estratto appreso
    assert "normattiva.it" in answer  # ancora ufficiale visibile nella risposta


def test_senza_valutazione_di_fiducia_la_memoria_non_entra(tmp_path, monkeypatch):
    answer = _chiedi_2043(tmp_path, monkeypatch, con_fiducia=False)
    assert "danno ingiusto" not in answer  # fail-closed: lettura senza trust esclusa
