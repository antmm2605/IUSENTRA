"""Test per il generatore di report PDF (ReportLab)."""

import os
import pytest
from datetime import date, datetime

from pct.reports import GeneratoreReport, fascicolo_pdf, scadenze_pdf


@pytest.fixture
def gen():
    return GeneratoreReport()


@pytest.fixture
def fascicolo_dict():
    return {
        "id": "FASC001",
        "numero": "2024/001",
        "titolo": "Rossi c/ Bianchi",
        "tipo": "CIVILE",
        "stato": "APERTO",
        "tribunale": "Tribunale di Roma",
        "sezione": "Prima",
        "giudice": "Dott. Neri",
        "numero_rg": "1234",
        "anno_rg": "2024",
        "data_apertura": "2024-01-15",
        "data_chiusura": "",
        "nome_cliente": "Mario Rossi",
        "controparte": "Luigi Bianchi",
        "avvocato_referente": "Avv. Verdi",
        "avvocato_dominus": "Avv. Gialli",
        "oggetto": "Controversia contrattuale relativa a compravendita immobiliare.",
        "note": "Udienza fissata per il 20 marzo 2026.",
        "attivita": [
            {
                "data": "2024-02-10",
                "tipo": "UDIENZA",
                "titolo": "Prima udienza di comparizione",
                "esito": "Rinviata",
                "note": "Rinvio al 20/03/2024",
            },
            {
                "data": "2024-03-20",
                "tipo": "DEPOSITO",
                "titolo": "Deposito memoria ex art. 183",
                "esito": "OK",
                "note": "",
            },
        ],
        "documenti": [
            {
                "nome": "atto_citazione.pdf",
                "tipo": "ATTO",
                "data_caricamento": "2024-01-15",
                "dimensione_bytes": 204800,
            },
            {
                "nome": "memoria_183.docx",
                "tipo": "MEMORIA",
                "data_caricamento": "2024-03-19",
                "dimensione_bytes": 51200,
            },
        ],
    }


@pytest.fixture
def scadenze_lista():
    return [
        {
            "scadenza": "2026-04-01",
            "titolo": "Deposito memoria integrativa",
            "tipo": "DEPOSITO_MEMORIA",
            "fascicolo": "2024/001",
            "priorita": "ALTA",
            "perentorio": True,
        },
        {
            "scadenza": "2026-05-15",
            "titolo": "Udienza di precisazione",
            "tipo": "UDIENZA",
            "fascicolo": "2024/002",
            "priorita": "MEDIA",
            "perentorio": False,
        },
        {
            "scadenza": date(2026, 3, 10).isoformat(),
            "titolo": "Scadenza già trascorsa",
            "tipo": "SCADENZA",
            "fascicolo": "",
            "priorita": "CRITICA",
            "perentorio": True,
        },
    ]


# ------------------------------------------------------------------ fascicolo_pdf

def test_fascicolo_pdf_crea_file(gen, fascicolo_dict, tmp_path):
    out = str(tmp_path / "fascicolo.pdf")
    result = gen.fascicolo_pdf(fascicolo_dict, out)
    assert result == os.path.abspath(out)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1024  # almeno 1 KB


def test_fascicolo_pdf_convenienza(fascicolo_dict, tmp_path):
    out = str(tmp_path / "fasc_conv.pdf")
    result = fascicolo_pdf(fascicolo_dict, out, studio_nome="Studio Test")
    assert os.path.exists(result)


def test_fascicolo_pdf_senza_attivita(gen, fascicolo_dict, tmp_path):
    fascicolo_dict["attivita"] = []
    out = str(tmp_path / "no_attivita.pdf")
    gen.fascicolo_pdf(fascicolo_dict, out)
    assert os.path.exists(out)


def test_fascicolo_pdf_senza_documenti(gen, fascicolo_dict, tmp_path):
    fascicolo_dict["documenti"] = []
    out = str(tmp_path / "no_docs.pdf")
    gen.fascicolo_pdf(fascicolo_dict, out)
    assert os.path.exists(out)


def test_fascicolo_pdf_senza_oggetto(gen, fascicolo_dict, tmp_path):
    fascicolo_dict["oggetto"] = ""
    fascicolo_dict["note"] = ""
    out = str(tmp_path / "no_obj.pdf")
    gen.fascicolo_pdf(fascicolo_dict, out)
    assert os.path.exists(out)


def test_fascicolo_pdf_dati_mancanti(gen, tmp_path):
    """Deve funzionare anche con un dict minimale."""
    minimal = {"id": "X", "titolo": "Test"}
    out = str(tmp_path / "minimal.pdf")
    gen.fascicolo_pdf(minimal, out)
    assert os.path.exists(out)


def test_fascicolo_pdf_crea_directory(gen, fascicolo_dict, tmp_path):
    """Deve creare le directory intermedie se non esistono."""
    out = str(tmp_path / "subdir" / "nested" / "out.pdf")
    gen.fascicolo_pdf(fascicolo_dict, out)
    assert os.path.exists(out)


# ------------------------------------------------------------------ scadenze_pdf

def test_scadenze_pdf_crea_file(gen, scadenze_lista, tmp_path):
    out = str(tmp_path / "scadenze.pdf")
    result = gen.scadenze_pdf(scadenze_lista, out)
    assert result == os.path.abspath(out)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1024


def test_scadenze_pdf_convenienza(scadenze_lista, tmp_path):
    out = str(tmp_path / "sc_conv.pdf")
    result = scadenze_pdf(scadenze_lista, out, titolo="Scadenziario Marzo 2026")
    assert os.path.exists(result)


def test_scadenze_pdf_lista_vuota(gen, tmp_path):
    out = str(tmp_path / "sc_vuoto.pdf")
    gen.scadenze_pdf([], out, titolo="Nessuna scadenza")
    assert os.path.exists(out)


def test_scadenze_pdf_con_date_oggetto(gen, tmp_path):
    """Accetta anche oggetti date/datetime (non solo stringhe ISO)."""
    scadenze = [
        {
            "scadenza": date(2026, 6, 1),
            "titolo": "Udienza",
            "tipo": "UDIENZA",
            "priorita": "ALTA",
            "perentorio": False,
        }
    ]
    out = str(tmp_path / "sc_date.pdf")
    gen.scadenze_pdf(scadenze, out)
    assert os.path.exists(out)


def test_scadenze_pdf_perentorio_flag(gen, tmp_path):
    """Vari formati del flag perentorio non devono causare errori."""
    scadenze = [
        {"titolo": "A", "scadenza": "2026-04-01", "perentorio": True},
        {"titolo": "B", "scadenza": "2026-04-02", "perentorio": False},
        {"titolo": "C", "scadenza": "2026-04-03", "perentorio": "SI"},
        {"titolo": "D", "scadenza": "2026-04-04", "perentorio": "0"},
    ]
    out = str(tmp_path / "sc_per.pdf")
    gen.scadenze_pdf(scadenze, out)
    assert os.path.exists(out)


# ------------------------------------------------------------------ Utility interne

def test_fmt_bytes():
    from pct.reports import _fmt_bytes
    assert _fmt_bytes(500) == "500 B"
    assert "KB" in _fmt_bytes(2048)
    assert "MB" in _fmt_bytes(2 * 1024 * 1024)
    assert _fmt_bytes(None) == "—"
    assert _fmt_bytes("abc") == "—"


def test_fmt_date():
    from pct.reports import _fmt_date
    assert _fmt_date("2024-03-15") == "15/03/2024"
    assert _fmt_date(date(2024, 3, 15)) == "15/03/2024"
    assert _fmt_date(datetime(2024, 3, 15, 10, 30)) == "15/03/2024"
    assert _fmt_date("") == "—"
    assert _fmt_date(None) == "—"


def test_val():
    from pct.reports import _val
    d = {"chiave": "valore", "vuota": "  "}
    assert _val(d, "chiave") == "valore"
    assert _val(d, "vuota") == "—"
    assert _val(d, "inesistente") == "—"
    assert _val(d, "inesistente", "default") == "default"
