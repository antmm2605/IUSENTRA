from pct.normative_tables import GestioneTabelleNormative


def test_catalogo_normativo_seeded(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    snapshot = gestore.snapshot()

    assert snapshot["totali"] >= 8
    assert snapshot["sincronizzate"] >= 8
    assert any(row["id"] == "interesse_legale" for row in snapshot["tabelle"])


def test_sync_normativo_segnala_verifica_su_fonte_variata(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    report = gestore.sync_from_canonical(
        source_runs={
            "gazzetta_ufficiale": {
                "status": "ok",
                "changed": True,
                "checked_at": "2026-04-01T09:30:00",
            }
        },
        source_ids=["gazzetta_ufficiale"],
    )

    assert report["processed_tables"] >= 1
    assert report["review_required"] >= 1
    assert any(row["sync_status"] == "verifica_richiesta" for row in report["tables"])
