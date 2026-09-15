"""Il collaudo del lettore: il software prova se stesso, sul testo e sull'OCR reale."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from legal_ocr.collaudo import CASI, esegui_collaudo, leggi_caso, salva_esito, corpo_del_caso, ultimo_esito


def test_ogni_caso_del_corpus_passa_sul_testo():
    for caso in CASI:
        esito = leggi_caso(caso, testo=corpo_del_caso(caso))
        assert esito["superato"], (caso.id, esito["mancanti"], esito["indebiti"], esito["fatti"])


def test_esito_salvato_e_riletto(tmp_path: Path):
    percorso = tmp_path / "intelligence" / "collaudo_lettore.json"
    assert ultimo_esito(percorso) == {"eseguito": False}
    salva_esito(percorso, {"superato": False, "corretti": 2, "totali": 3, "eseguito_il": "2026-09-16T04:10:00+02:00", "casi": [{"id": "a", "titolo": "Relata", "superato": False}, {"id": "b", "superato": True}]})
    esito = ultimo_esito(percorso)
    assert esito["eseguito"] and not esito["superato"] and esito["corretti"] == 2 and esito["casi_falliti"] == ["Relata"] and esito["eseguito_il_it"]


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract non installato: il collaudo con OCR reale gira dove c'è il motore")
def test_il_collaudo_con_ocr_reale_passa():
    pytest.importorskip("pytesseract")
    esito = esegui_collaudo()
    assert esito["superato"], [(c["id"], c["mancanti"], c["indebiti"], c["testo"][:200]) for c in esito["casi"] if not c["superato"]]
    assert esito["corretti"] == esito["totali"] == len(CASI)
