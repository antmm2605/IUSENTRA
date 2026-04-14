from pathlib import Path

from pct.giurisprudenza import GestioneGiurisprudenza


def _build_gestore(tmp_path: Path) -> GestioneGiurisprudenza:
    return GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))


def test_giurisprudenza_repository_sync_and_export(tmp_path: Path):
    gestore = _build_gestore(tmp_path)

    stats = gestore.statistiche_repository()
    assert stats["giurisprudenza_sources_repository"] > 0
    assert stats["giurisprudenza_taxonomy_repository"] > 0
    assert stats["giurisprudenza_usage_policy_repository"] > 0
    assert stats["giurisprudenza_sync_registry"] > 0

    payload = gestore.repository_payload()
    assert payload["counts"]["sources"] == stats["giurisprudenza_sources_repository"]
    assert any(row["source_id"] == "cassazione" for row in payload["sources"])
    assert any(row["title"] == "Civile" and row["level_name"] == "area" for row in payload["taxonomy"])
    assert any(row["policy_id"] == "regola:corpus_first_search" for row in payload["usage_policy"])

    paths = gestore.export_giurisprudenza_repositories(str(tmp_path / "export"))
    assert "sources" in paths
    assert "taxonomy" in paths
    assert "usage_policy" in paths
    assert "sync_registry" in paths


def test_giurisprudenza_route_usa_repository_e_corpus_professionale(tmp_path: Path):
    gestore = _build_gestore(tmp_path)
    gestore.salva(
        {
            "source_system": "cassazione",
            "titolo": "Cassazione su anatocismo bancario",
            "organo_giudicante": "Corte di Cassazione",
            "sezione": "Sez. I",
            "numero_provvedimento": "777/2026",
            "data_deposito": "2026-04-12",
            "area": "Civile",
            "branca": "Bancario e finanziario",
            "sottobranca": "Anatocismo",
            "massima": "L'anatocismo richiede verifica puntuale della clausola contrattuale.",
            "principio_diritto": "Il controllo va svolto sulla clausola e sulla sua trasparenza.",
            "stato_verifica_fonte": "verificata",
            "fonte_ufficiale_confermata": True,
            "url_pagina_ufficiale": "https://www.cortedicassazione.it/sentenza-777-2026",
            "url_pdf_ufficiale": "https://www.cortedicassazione.it/sentenza-777-2026.pdf",
            "pdf_ufficiale_presente": True,
            "uso_nel_software": "precedente forte",
        }
    )

    route = gestore.resolve_lex_giurisprudenza_route("ultime sentenze Cassazione su anatocismo pdf")

    assert "cassazione" in route["source_ids"]
    assert route["route_mode"] == "corpus_e_sync_pubblico"
    assert route["prefer_pdf"] is True
    assert route["prefer_verified_only"] is True
    assert route["preferred_area_title"] == "Civile"
    assert any("anatocismo" in (row.get("titolo") or "").lower() for row in route["corpus_rows"])
