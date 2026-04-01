from pct.normative_tables import GestioneTabelleNormative


def test_catalogo_normativo_seeded(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    snapshot = gestore.snapshot()

    assert snapshot["totali"] >= 9
    assert snapshot["sincronizzate"] >= 9
    assert any(row["id"] == "interesse_legale" for row in snapshot["tabelle"])
    assert any(row["id"] == "riferimenti_normativi_catalogo" for row in snapshot["tabelle"])
    assert snapshot["riferimenti_normativi_totali"] >= 8


def test_catalogo_riferimenti_normativi_include_fonti_preventivo(tmp_path):
    gestore = GestioneTabelleNormative(str(tmp_path / "tabelle_normative.json"))

    riferimenti = gestore.catalogo_riferimenti_normativi()

    assert any(row["title"] == "D.M. 10 marzo 2014, n. 55" for row in riferimenti)
    mediazione = next(row for row in riferimenti if row["title"] == "D.M. 24 ottobre 2023, n. 150")
    assert "Stragiudiziale" in mediazione["areas"]
    assert "mediazione" in mediazione["tipologie_ids"]


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
