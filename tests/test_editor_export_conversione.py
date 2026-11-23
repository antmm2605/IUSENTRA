"""Export dell'editor: tempo massimo della conversione locale e preriscaldamento del convertitore.

Collaudo del 21/11/2026: con il PC carico la conversione LibreOffice durava 45,1 s e l'export PDF
rispondeva 503. Il limite passa a 120 s (regolabile con IUSENTRA_EDITOR_CONVERSIONE_SECONDI) e
all'avvio del worker una conversione di prova evita la prima esportazione a freddo.
"""

import sys
import time

import pytest

import pct.editor_export as ee


@pytest.fixture(autouse=True)
def _stato_pulito(monkeypatch):
    monkeypatch.delenv(ee.VARIABILE_TEMPO_CONVERSIONE, raising=False)
    monkeypatch.delenv("IUSENTRA_EDITOR_PRERISCALDAMENTO", raising=False)
    monkeypatch.setitem(ee._PRERISCALDAMENTO, "avviato", False)
    monkeypatch.setitem(ee._PRERISCALDAMENTO, "esito", None)


def test_tempo_predefinito_120_secondi():
    assert ee.tempo_conversione() == 120.0


@pytest.mark.parametrize("valore, atteso", [("200", 200.0), ("90.5", 90.5), ("abc", 120.0), ("0", 120.0), ("-3", 120.0), ("", 120.0)])
def test_tempo_regolabile_con_variabile(monkeypatch, valore, atteso):
    monkeypatch.setenv(ee.VARIABILE_TEMPO_CONVERSIONE, valore)
    assert ee.tempo_conversione() == atteso


def test_conversione_oltre_il_limite_ferma_il_processo_con_messaggio_chiaro(monkeypatch):
    monkeypatch.setenv(ee.VARIABILE_TEMPO_CONVERSIONE, "0.5")
    inizio = time.monotonic()
    with pytest.raises(ee.ConversioneEditorScaduta, match="non è terminata in tempo"):
        ee._converti_editor([sys.executable, "-c", "import time; time.sleep(30)"], {})
    assert time.monotonic() - inizio < 10


def test_conversione_entro_il_limite_non_scade(monkeypatch):
    monkeypatch.setenv(ee.VARIABILE_TEMPO_CONVERSIONE, "20")
    ee._converti_editor([sys.executable, "-c", "import time; time.sleep(1)"], {})


def test_preriscaldamento_riuscito(monkeypatch):
    chiamate = []

    def finta(html, *, formato, titolo="Documento", **_):
        chiamate.append(formato)
        return b"%PDF-1.7 prova"

    monkeypatch.setattr(ee, "esporta_documento_editor", finta)
    esito = ee.preriscalda_convertitore()
    assert esito["ok"] is True and chiamate == ["pdf"]
    assert ee._PRERISCALDAMENTO["esito"] == esito


def test_preriscaldamento_non_solleva_se_il_convertitore_fallisce(monkeypatch):
    def guasta(*_, **__):
        raise RuntimeError("Convertitore locale dei documenti non disponibile.")

    monkeypatch.setattr(ee, "esporta_documento_editor", guasta)
    esito = ee.preriscalda_convertitore()
    assert esito["ok"] is False and "non disponibile" in esito["errore"]


def test_preriscaldamento_in_sfondo_una_sola_volta_e_disattivabile(monkeypatch):
    monkeypatch.setattr(ee.shutil, "which", lambda nome: "/usr/bin/" + nome)
    monkeypatch.setattr(ee, "esporta_documento_editor", lambda *_, **__: b"%PDF")
    filo = ee.avvia_preriscaldamento_in_sfondo()
    assert filo is not None and filo.daemon
    filo.join(timeout=10)
    assert ee._PRERISCALDAMENTO["esito"]["ok"] is True
    assert ee.avvia_preriscaldamento_in_sfondo() is None  # già avviato in questo processo

    monkeypatch.setitem(ee._PRERISCALDAMENTO, "avviato", False)
    monkeypatch.setenv("IUSENTRA_EDITOR_PRERISCALDAMENTO", "0")
    assert ee.avvia_preriscaldamento_in_sfondo() is None


def test_senza_convertitore_installato_nessun_preriscaldamento(monkeypatch):
    monkeypatch.setattr(ee.shutil, "which", lambda nome: None)
    assert ee.avvia_preriscaldamento_in_sfondo() is None
