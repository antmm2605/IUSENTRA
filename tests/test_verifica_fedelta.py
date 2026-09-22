"""La misura della fedelta' deve dire di no quando il documento e' cambiato.

Un controllo che passa sempre non protegge nessuno: questi test verificano
prima di tutto che il confronto sappia bocciare.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from pct.verifica_fedelta import (
    SCARTO_TOLLERATO_MM,
    VerificaFedeltaError,
    confronta,
)

RIGHE = [
    "TRIBUNALE ORDINARIO DI NAPOLI",
    "Per il sig. ROSSI MARIO, nato a Napoli il 12 marzo 1974",
    "il corrispettivo pattuito era di euro 48.500,00 oltre IVA",
    "la diffida del 9 settembre 2025 restava senza riscontro",
]


def _scrivi(percorso: Path, righe=RIGHE, *, scarto_mm: float = 0.0, pagine: int = 1) -> Path:
    foglio = canvas.Canvas(str(percorso), pagesize=A4)
    for _ in range(pagine):
        y = 250 * mm - scarto_mm * mm
        for riga in righe:
            foglio.setFont("Helvetica", 11)
            foglio.drawString(25 * mm + scarto_mm * mm, y, riga)
            y -= 8 * mm
        foglio.showPage()
    foglio.save()
    return percorso


def test_un_documento_confrontato_con_se_stesso_e_fedele(tmp_path):
    uno = _scrivi(tmp_path / "uno.pdf")
    esito = confronta(uno, uno)
    assert esito.verdetto == "fedele"
    assert esito.entro_tolleranza == 100.0
    assert esito.parole_perse_totali == 0


def test_uno_spostamento_impercettibile_resta_fedele(tmp_path):
    partenza = _scrivi(tmp_path / "a.pdf")
    arrivo = _scrivi(tmp_path / "b.pdf", scarto_mm=SCARTO_TOLLERATO_MM / 2)
    esito = confronta(partenza, arrivo)
    assert esito.verdetto == "fedele"


def test_uno_spostamento_di_un_centimetro_viene_bocciato(tmp_path):
    partenza = _scrivi(tmp_path / "a.pdf")
    arrivo = _scrivi(tmp_path / "b.pdf", scarto_mm=10.0)
    esito = confronta(partenza, arrivo)
    assert esito.verdetto == "da rivedere"
    assert esito.entro_tolleranza == 0.0
    pagina = esito.pagine[0]
    assert pagina.scarto_x_mediano == pytest.approx(10.0, abs=0.3)
    assert pagina.scarto_y_mediano == pytest.approx(10.0, abs=0.3)


def test_una_parola_sparita_manda_la_pagina_da_rivedere(tmp_path):
    partenza = _scrivi(tmp_path / "a.pdf")
    arrivo = _scrivi(tmp_path / "b.pdf", righe=RIGHE[:-1] + ["la diffida del 9 settembre 2025 restava senza"])
    esito = confronta(partenza, arrivo)
    assert esito.parole_perse_totali >= 1
    assert esito.verdetto == "da rivedere"
    assert esito.da_rivedere == [1]


def test_il_numero_di_pagine_cambiato_viene_segnalato(tmp_path):
    partenza = _scrivi(tmp_path / "a.pdf", pagine=2)
    arrivo = _scrivi(tmp_path / "b.pdf", pagine=1)
    esito = confronta(partenza, arrivo)
    assert any("2 pagine" in a and "1" in a for a in esito.avvisi)
    assert esito.verdetto == "da rivedere"


def test_una_pagina_in_piu_non_tocca_le_pagine_gia_fedeli(tmp_path):
    partenza = _scrivi(tmp_path / "a.pdf", pagine=1)
    arrivo = _scrivi(tmp_path / "b.pdf", pagine=2)
    esito = confronta(partenza, arrivo)
    assert esito.pagine[0].verdetto == "fedele"
    assert esito.avvisi


def test_un_documento_senza_testo_non_si_puo_confrontare(tmp_path):
    vuoto = tmp_path / "vuoto.pdf"
    foglio = canvas.Canvas(str(vuoto), pagesize=A4)
    foglio.showPage()
    foglio.save()
    with pytest.raises(VerificaFedeltaError, match="non ha testo"):
        confronta(vuoto, vuoto)


def test_un_file_che_non_e_un_pdf_viene_rifiutato(tmp_path):
    finto = tmp_path / "finto.pdf"
    finto.write_bytes(b"non sono un PDF")
    buono = _scrivi(tmp_path / "buono.pdf")
    with pytest.raises(VerificaFedeltaError, match="illeggibile"):
        confronta(buono, finto)


def test_il_sommario_e_una_riga_leggibile(tmp_path):
    partenza = _scrivi(tmp_path / "a.pdf")
    arrivo = _scrivi(tmp_path / "b.pdf", scarto_mm=10.0)
    riga = confronta(partenza, arrivo).sommario()
    assert "entro" in riga
    assert "pagina 1" in riga
