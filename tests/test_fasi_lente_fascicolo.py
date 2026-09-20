"""Quale fase pesa sull'apertura di un fascicolo, misurata invece che dedotta.

Un fascicolo aperto per la prima volta puo' costare decine di secondi mentre
lo stesso fascicolo riaperto e' immediato. Dal totale non si capisce quale
delle trenta fasi del dettaglio se li prenda, e su questo abbiamo gia'
tirato a indovinare troppe volte. Ogni fase passa da `_safe`, che ora la
cronometra; le fasi sopra soglia finiscono nel payload.
"""

from __future__ import annotations

import time

from flask import Flask

from web.services.react_fascicoli_bridge import SOGLIA_FASE_LENTA_MS, _safe, fasi_lente


def _app():
    return Flask(__name__)


def test_una_fase_lenta_viene_riportata():
    app = _app()
    with app.test_request_context("/prova"):
        _safe("lettura_documenti", lambda: time.sleep(0.08) or "ok", None)

        lente = fasi_lente()

    assert "lettura_documenti" in lente
    assert lente["lettura_documenti"] >= 70


def test_le_fasi_veloci_restano_fuori():
    """L'elenco deve far vedere i colpevoli, non seppellirli."""

    app = _app()
    with app.test_request_context("/prova"):
        _safe("fase_rapida", lambda: "ok", None)

        assert fasi_lente() == {}


def test_le_fasi_sono_ordinate_dalla_piu_lenta():
    app = _app()
    with app.test_request_context("/prova"):
        _safe("media", lambda: time.sleep(0.07) or "ok", None)
        _safe("lenta", lambda: time.sleep(0.15) or "ok", None)

        nomi = list(fasi_lente().keys())

    assert nomi[0] == "lenta"
    assert nomi[1] == "media"


def test_la_stessa_fase_chiamata_piu_volte_si_somma():
    """Le idratazioni dentro un ciclo sono il sospetto numero uno: vanno sommate."""

    app = _app()
    with app.test_request_context("/prova"):
        for _ in range(3):
            _safe("idrata_documenti", lambda: time.sleep(0.03) or "ok", None)

        lente = fasi_lente()

    assert lente["idrata_documenti"] >= 80


def test_una_fase_che_fallisce_viene_comunque_cronometrata():
    """Il ripiego silenzioso non deve nascondere anche il tempo speso."""

    def esplode():
        time.sleep(0.07)
        raise RuntimeError("archivio irraggiungibile")

    app = _app()
    with app.test_request_context("/prova"):
        assert _safe("fase_rotta", esplode, "ripiego") == "ripiego"

        assert fasi_lente()["fase_rotta"] >= 60


def test_fuori_da_una_richiesta_non_si_rompe_niente():
    """`_safe` gira anche dai job dello scheduler, dove non c'e' richiesta."""

    assert _safe("fuori_richiesta", lambda: "ok", None) == "ok"
    assert fasi_lente() == {}


def test_due_richieste_non_si_mescolano():
    app = _app()
    with app.test_request_context("/prima"):
        _safe("prima", lambda: time.sleep(0.07) or "ok", None)
        assert "prima" in fasi_lente()

    with app.test_request_context("/seconda"):
        assert fasi_lente() == {}


def test_la_soglia_e_dichiarata_e_si_puo_abbassare():
    app = _app()
    with app.test_request_context("/prova"):
        _safe("fase_rapida", lambda: "ok", None)

        assert fasi_lente(soglia_ms=0) != {}

    assert SOGLIA_FASE_LENTA_MS > 0
