"""Verifica del modulo PAT firmato in Adobe Reader (Istruzioni per la compilazione dei moduli v9.6.2)."""

from __future__ import annotations

import io

from pct.pat_pdf_templates import build_pat_official_pdf
from pct.pat_verifica_modulo import verifica
from tests.test_pat_formweb import pdf_pades

BASE = {"sede": "Tribunale Amministrativo regionale del Veneto - Venezia", "tipo_ricorso": "ORDINARIO",
        "ricorrente": "Rossi Mario", "resistente": "Comune di Venezia", "oggetto": "Annullamento del diniego"}


def _codici(esito, livello):
    return {e["codice"] for e in esito["esiti"] if e["livello"] == livello}


def _con_allegato(pdf: bytes, nome: str, dimensione: int) -> bytes:
    from pypdf import PdfReader, PdfWriter

    scrittore = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    scrittore.add_attachment(nome, b"x" * dimensione)
    uscita = io.BytesIO()
    scrittore.write(uscita)
    return uscita.getvalue()


def test_modulo_non_firmato_si_segnala():
    esito = verifica(build_pat_official_pdf("deposito_ricorso", BASE)[0].getvalue())
    assert esito["ok"] is False and "FIRMA" in _codici(esito, "errore") and "VERSIONE" in _codici(esito, "ok")


def test_modulo_firmato_integro_e_modificato_dopo_la_firma():
    firmato = pdf_pades(build_pat_official_pdf("deposito_ricorso", BASE)[0].getvalue())
    esito = verifica(firmato)
    assert esito["ok"] is True and esito["firme"][0]["firmatario"] == "Avvocato di prova"
    assert esito["anteprima"]["versione"] == "4.03"
    alterato = verifica(firmato + b"\n% aggiunta dopo la firma\n")
    assert alterato["ok"] is False and "FIRMA" in _codici(alterato, "errore")


def test_nomi_e_dimensioni_degli_allegati():
    pdf = build_pat_official_pdf("deposito_ricorso", BASE)[0].getvalue()
    esito = verifica(pdf_pades(_con_allegato(pdf, "Ricorso-TAR (firmato).pdf", 100)))
    assert "NOME_ALLEGATO" in _codici(esito, "errore")
    grande = verifica(pdf_pades(_con_allegato(pdf, "Perizia tecnica.pdf", 11 * 1024 * 1024)))
    assert "DIMENSIONE_ALLEGATO" in _codici(grande, "errore")
    assert "DIMENSIONE_ALLEGATO" not in _codici(verifica(pdf_pades(_con_allegato(pdf, "Perizia tecnica.pdf", 11 * 1024 * 1024)),
                                                         canale="upload"), "errore")


def test_file_che_non_e_un_modulo():
    assert verifica(b"testo")["ok"] is False
    from tests.test_penale_pdp import pdf_testo

    assert verifica(pdf_testo("Un PDF qualunque"))["esiti"][0]["codice"] == "NON_MODULO"


def test_api_verifica_del_modulo_firmato(tmp_path):
    from tests.test_react_shell import _app

    app = _app(tmp_path)
    firmato = pdf_pades(build_pat_official_pdf("deposito_ricorso", BASE)[0].getvalue())
    with app.test_client() as client:
        risposta = client.post("/api/v1/ui/pat/moduli/verifica", headers={"X-API-Key": "react-test-key"},
                               data={"file": (io.BytesIO(firmato), "modulo firmato.pdf"), "canale": "pec"},
                               content_type="multipart/form-data")
        assert risposta.status_code == 200 and risposta.get_json()["ok"] is True
        vuota = client.post("/api/v1/ui/pat/moduli/verifica", headers={"X-API-Key": "react-test-key"},
                            data={}, content_type="multipart/form-data")
        assert vuota.status_code == 400
