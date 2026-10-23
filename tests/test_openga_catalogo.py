import csv
import hashlib
from pathlib import Path

import pytest

from pct.openga_catalogo import CatalogoOpenGA
from scripts.precedenti.openga import categoria


def risorsa(tmp_path, rows, rid="risorsa", name="file.csv"):
    path = tmp_path / name
    fields = [
        "CODICE_SEDE",
        "NOME_SEDE",
        "TIPO_PROVVEDIMENTO",
        "NUMERO_PROVVEDIMENTO",
        "ANNO_PUBBLICAZIONE",
        "NUMERO_RICORSO",
        "OGGETTO_RICORSO",
        "ESITO_PROVVEDIMENTO",
        "FLG_DEFINISCE",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                dict(
                    CODICE_SEDE="CDS",
                    NOME_SEDE="Consiglio di Stato",
                    TIPO_PROVVEDIMENTO="SENTENZA",
                    ANNO_PUBBLICAZIONE="2026",
                    OGGETTO_RICORSO="Permesso di soggiorno",
                    FLG_DEFINISCE="D",
                    **row,
                )
            )
    return path, {
        "package_id": "dataset",
        "download_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "resource": {
            "id": rid,
            "url": "https://openga.giustizia-amministrativa.it/risorsa",
            "license_id": "cc-by-04",
            "last_modified": "2026-09-30",
        },
    }


def test_provvedimenti_e_rapporti_non_sono_stesso_denominatore(tmp_path):
    path, meta = risorsa(
        tmp_path,
        [
            {"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "ACCOGLIE"},
            {"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "B", "ESITO_PROVVEDIMENTO": "RESPINGE"},
            {"NUMERO_PROVVEDIMENTO": "2", "NUMERO_RICORSO": "C", "ESITO_PROVVEDIMENTO": "DICHIARA IMPROCEDIBILE"},
        ],
    )
    catalog = CatalogoOpenGA(tmp_path / "catalogo.db")
    assert catalog.importa(path, meta)["righe_valide"] == 3
    assert catalog.importa(path, meta)["nuove_righe"] == 0
    before = (tmp_path / "catalogo.db").read_bytes()
    report = catalog.riepilogo(dal=2026, al=2026)
    assert report["provvedimenti_distinti"] == 2
    assert report["denominatore_relazioni_definite"] == 3
    assert report["esiti_per_relazione_definita"] == {"accolto": 1, "respinto": 1, "improcedibile": 1}
    assert (tmp_path / "catalogo.db").read_bytes() == before
    assert report["risorse"][0]["sha256"] == meta["download_sha256"]


def test_revisioni_backup_e_risorse_sovrapposte_senza_doppi_conteggi(tmp_path):
    rows = [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "RESPINGE"}]
    path, meta = risorsa(tmp_path, rows)
    catalog = CatalogoOpenGA(tmp_path / "catalogo.db")
    catalog.importa(path, meta)
    p2, m2 = risorsa(tmp_path, rows, rid="altra", name="seconda.csv")
    assert catalog.importa(p2, m2)["backup"] is None
    assert catalog.riepilogo()["denominatore_relazioni_definite"] == 1
    rows[0]["ESITO_PROVVEDIMENTO"] = "ACCOGLIE"
    p3, m3 = risorsa(tmp_path, rows)
    result = catalog.importa(p3, m3)
    assert Path(result["backup"]).is_file()
    assert catalog.riepilogo()["esiti_per_relazione_definita"] == {"esiti multipli da verificare": 1}


def test_nessun_catalogo_fittizio_o_import_con_impronta_licenza_errata(tmp_path):
    catalog = CatalogoOpenGA(tmp_path / "catalogo.db")
    with pytest.raises(ValueError, match="assente"):
        catalog.riepilogo()
    assert not catalog.path.exists()
    path, meta = risorsa(tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": ""}])
    meta["resource"]["license_id"] = ""
    with pytest.raises(ValueError, match="Licenza"):
        catalog.importa(path, meta)
    meta["resource"]["license_id"] = "cc-by-04"
    meta["download_sha256"] = "errato"
    with pytest.raises(ValueError, match="Impronta"):
        catalog.importa(path, meta)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("PARTE RIGETTA E PARTE ACCOGLIE", "esito misto"),
        ("RESPINGE APPELLO INCIDENTALE", "esito incidentale"),
        ("NON ACCOGLIE", "non classificato"),
        ("COMMISSARIO AD ACTA", "commissario ad acta"),
        ("DICHIARA INAMMISSIBILE", "inammissibile"),
        ("DICHIARA IMPROCEDIBILE", "improcedibile"),
        ("FORMULA NUOVA", "non classificato"),
    ],
)
def test_esiti_non_forzati_in_vittoria_o_rigetto(raw, expected):
    assert categoria(raw) == expected


def test_indice_oggetti_separato_e_schede_solo_metadati(tmp_path):
    from lex.ricerca_giuridica.embedding import EmbedderFinto

    path, meta = risorsa(
        tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "RESPINGE"}]
    )
    catalog = CatalogoOpenGA(tmp_path / "catalogo.db")
    catalog.importa(path, meta)
    engine = EmbedderFinto()
    assert catalog.costruisci_indice(embedder=engine)["completo"] is True
    rows = catalog.cerca("permesso di soggiorno", semantica=True, embedder=engine)
    assert rows and rows[0]["evidence_scope"] == "metadata_only"
    assert rows[0]["massima_ufficiale"] == rows[0]["principio_sintetico"] == ""
    assert rows[0]["testo_integrale_presente"] is False
    assert catalog.cerca("permesso", sede="TAR diverso", semantica=True, embedder=engine) == []
    path, meta = risorsa(
        tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "ACCOGLIE"}]
    )
    catalog.importa(path, meta)
    rows = catalog.cerca("permesso", semantica=True, embedder=engine)
    assert rows and all(row["esito"] == "ACCOGLIE" for row in rows)


def test_primo_semantico_non_scompare_fra_doppi_punteggi_deboli(tmp_path, monkeypatch):
    from lex.ricerca_giuridica.embedding import EmbedderFinto
    from lex.ricerca_giuridica.indice_vettoriale import IndiceVettoriale

    rows = [
        {"NUMERO_PROVVEDIMENTO": str(i), "NUMERO_RICORSO": str(i), "ESITO_PROVVEDIMENTO": "RESPINGE"}
        for i in range(1, 31)
    ]
    path, manifest = risorsa(tmp_path, rows)
    catalog = CatalogoOpenGA(tmp_path / "catalogo.db")
    catalog.importa(path, manifest)
    engine = EmbedderFinto()
    catalog.costruisci_indice(embedder=engine)
    monkeypatch.setattr(
        IndiceVettoriale, "cerca", lambda self, *a, **kw: [(30, 1.0)] + [(i, 0.5) for i in range(1, 21)]
    )
    hits = catalog.cerca("permesso soggiorno", limit=10, semantica=True, embedder=engine)
    numbers = {x["numero_sentenza"] for x in hits}
    assert "30" in numbers
    assert set(map(str, range(1, 6))).issubset(numbers)


def test_canali_separati_preservano_tutti_i_lessicali_e_aggiungono_vettori(tmp_path, monkeypatch):
    from lex.ricerca_giuridica.embedding import EmbedderFinto
    from lex.ricerca_giuridica.indice_vettoriale import IndiceVettoriale

    rows = [
        {"NUMERO_PROVVEDIMENTO": str(i), "NUMERO_RICORSO": str(i), "ESITO_PROVVEDIMENTO": "RESPINGE"}
        for i in range(1, 31)
    ]
    path, manifest = risorsa(tmp_path, rows)
    catalog = CatalogoOpenGA(tmp_path / "catalogo.db")
    catalog.importa(path, manifest)
    engine = EmbedderFinto()
    catalog.costruisci_indice(embedder=engine)
    monkeypatch.setattr(
        IndiceVettoriale, "cerca", lambda self, *a, **kw: [(30, 1.0)] + [(i, 0.5) for i in range(1, 21)]
    )
    baseline = catalog.cerca("permesso soggiorno", limit=10)
    result = catalog.cerca_canali("permesso soggiorno", limit=10, embedder=engine)
    assert result["lessicali"] == baseline and len(baseline) == 10
    assert result["errore_semantico"] is None
    assert result["semantici_aggiuntivi"][0]["numero_sentenza"] == "30"
    primary = {r["relazione_id"] for r in baseline}
    assert not primary & {r["relazione_id"] for r in result["semantici_aggiuntivi"]}
    assert len(result["semantici_aggiuntivi"]) <= 10
    for r in result["semantici_aggiuntivi"]:
        assert r["evidence_scope"] == "metadata_only" and not r["testo_integrale_presente"]
    filtered = catalog.cerca_canali("permesso", sede="TAR diverso", limit=10, embedder=engine)
    assert filtered["lessicali"] == filtered["semantici_aggiuntivi"] == []


def test_canali_separati_indice_assente_non_finge_ricerca_semantica(tmp_path):
    path, manifest = risorsa(
        tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "RESPINGE"}]
    )
    catalog = CatalogoOpenGA(tmp_path / "catalogo.db")
    catalog.importa(path, manifest)
    result = catalog.cerca_canali("permesso", limit=10)
    assert result["lessicali"] == catalog.cerca("permesso", limit=10)
    assert result["semantici_aggiuntivi"] == []
    assert result["errore_semantico"]


def test_canali_separati_errore_vettoriale_non_elimina_lessicali(tmp_path, monkeypatch):
    from lex.ricerca_giuridica.embedding import EmbedderFinto
    from lex.ricerca_giuridica.indice_vettoriale import IndiceVettoriale

    path, manifest = risorsa(
        tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "RESPINGE"}]
    )
    catalog = CatalogoOpenGA(tmp_path / "catalogo.db")
    catalog.importa(path, manifest)
    engine = EmbedderFinto()
    catalog.costruisci_indice(embedder=engine)

    def broken(*a, **kw):
        raise RuntimeError("servizio embedding non disponibile")

    monkeypatch.setattr(IndiceVettoriale, "cerca", broken)
    result = catalog.cerca_canali("permesso", embedder=engine)
    assert result["lessicali"] == catalog.cerca("permesso", limit=10)
    assert not result["semantici_aggiuntivi"]
    assert "non disponibile" in result["errore_semantico"]


@pytest.mark.parametrize("guasto", ["archivio_diverso", "modello_diverso"])
def test_canali_rifiutano_indice_o_modello_diverso_preservando_lessicali(tmp_path, guasto):
    import json
    from lex.ricerca_giuridica.embedding import EmbedderFinto

    path, manifest = risorsa(
        tmp_path, [{"NUMERO_PROVVEDIMENTO": "1", "NUMERO_RICORSO": "A", "ESITO_PROVVEDIMENTO": "RESPINGE"}]
    )
    catalog = CatalogoOpenGA(tmp_path / "catalogo.db")
    catalog.importa(path, manifest)
    engine = EmbedderFinto()
    catalog.costruisci_indice(embedder=engine)
    before = catalog.path.read_bytes()
    if guasto == "archivio_diverso":
        scope_path = catalog.path.with_name(catalog.path.name + ".vettori-oggetti") / "scope.json"
        scope = json.loads(scope_path.read_text())
        scope["catalogo"] = str(tmp_path / "altro.db")
        scope_path.write_text(json.dumps(scope))
    else:
        engine.modello = "modello-diverso"
    result = catalog.cerca_canali("permesso", embedder=engine)
    assert result["lessicali"] == catalog.cerca("permesso", limit=10)
    assert result["errore_semantico"] and not result["semantici_aggiuntivi"]
    assert catalog.path.read_bytes() == before
