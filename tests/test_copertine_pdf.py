"""Copertine del fascicolo e del faldone come PDF (prima pagine Jinja copertina.html / copertina_faldone.html)."""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader

from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app

RADICE = Path(__file__).resolve().parents[1]


def _testo(pdf: bytes) -> str:
    return "\n".join(pagina.extract_text() or "" for pagina in PdfReader(io.BytesIO(pdf)).pages)


def _dati(app):
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Giulia", cognome="Verdi <b>", codice_fiscale="VRDGLI80A41H501X")
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"], documents_dir=app.config["FASCICOLI_DOCS"], archive_dir=app.config["FASCICOLI_ARCH"],
    )
    attivo = fascicoli.nuovo("Opposizione a decreto ingiuntivo & spese", TipoFascicolo.CIVILE, id_cliente=cliente.id,
                             nome_cliente=cliente.nome_completo, tribunale="Tribunale di Roma")
    chiuso = fascicoli.nuovo("Sfratto per morosità", TipoFascicolo.CIVILE, id_cliente=cliente.id,
                             nome_cliente=cliente.nome_completo, tribunale="Tribunale di Latina")
    return cliente, attivo, chiuso


def test_copertina_fascicolo_e_faldone_sono_pdf_con_i_dati_della_pratica(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, attivo, _chiuso = _dati(app)
    with app.test_client() as client:
        _login(client)
        fascicolo = client.get(f"/fascicoli/{attivo.id}/copertina")
        faldone = client.get(f"/clienti/{cliente.id}/faldone/copertina")
        assente = client.get("/fascicoli/inesistente/copertina")

    for risposta in (fascicolo, faldone):
        assert risposta.status_code == 200
        assert risposta.mimetype == "application/pdf"
        assert risposta.headers["Content-Disposition"].startswith("inline;")
        assert risposta.headers["Cache-Control"] == "no-store"
        assert risposta.data.startswith(b"%PDF")
    testo = _testo(fascicolo.data)
    for atteso in ("Copertina del fascicolo", "Opposizione a decreto ingiuntivo & spese", "DATI DELLA PRATICA",
                   "DATI GIUDIZIARI", "Tribunale di Roma", "Civile", "Verdi <b>", "VRDGLI80A41H501X"):
        assert atteso in testo, atteso
    testo_faldone = _testo(faldone.data)
    for atteso in ("Copertina del faldone", "Giulia", "PRATICHE ATTIVE", "Opposizione a decreto", "Tribunale di Roma"):
        assert atteso in testo_faldone, atteso
    assert assente.status_code == 302


def test_template_delle_copertine_eliminati():
    for nome in ("fascicoli/copertina.html", "clienti/copertina_faldone.html"):
        assert not (RADICE / "web" / "templates" / nome).exists(), nome
