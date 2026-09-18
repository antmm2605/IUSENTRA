"""Il cliente compila nel portale i moduli che lo studio gli manda.

Prima doveva scaricarli, aprirli con un programma proprio, compilarli e
ricaricarli: sul telefono, senza un lettore PDF che scrive nei campi, restava
fermo. Le regole sui campi predisposti non si riscrivono: sono quelle di
`pct.mediazione_documenti`, usate anche per i moduli degli organismi.
"""

from __future__ import annotations

import io
from pathlib import Path

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_client_portal_api import _app, _create_invite, _seed_cliente_fascicolo


def _pdf_con_campi() -> bytes:
    """Un PDF con due campi predisposti, come un modulo dell'organismo."""
    import pymupdf as fitz

    documento = fitz.open()
    pagina = documento.new_page()
    for nome, alto in (("nome_istante", 100), ("recapito", 160)):
        widget = fitz.Widget()
        widget.field_name = nome
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(72, alto, 400, alto + 24)
        widget.field_value = ""
        pagina.add_widget(widget)
    dati = documento.tobytes()
    documento.close()
    return dati


def _pdf_senza_campi() -> bytes:
    import pymupdf as fitz

    documento = fitz.open()
    pagina = documento.new_page()
    pagina.insert_text((72, 100), "Nessun campo predisposto")
    dati = documento.tobytes()
    documento.close()
    return dati


def _carica_nel_portale(client, token: str, contenuto: bytes, nome: str) -> str:
    risposta = client.post(
        "/api/v1/ui/client-portal/public/documents",
        data={"file": (io.BytesIO(contenuto), nome), "requestId": ""},
        content_type="multipart/form-data",
        headers={"X-Client-Portal-Token": token},
    ).get_json()
    assert risposta["ok"] is True, risposta
    return risposta["item"]["id"]


def _portale_pronto(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    return app, cliente, fascicolo


def test_il_modulo_con_campi_predisposti_si_legge_e_si_compila(tmp_path: Path):
    app, cliente, fascicolo = _portale_pronto(tmp_path)
    with app.test_client() as client:
        _login(client)
        token, _ = _create_invite(client, cliente.id, fascicolo.id)
        client.post(f"/api/v1/ui/client-portal/public/invites/{token}/accept", json={})
        documento_id = _carica_nel_portale(client, token, _pdf_con_campi(), "Modulo organismo.pdf")

        campi = client.get(
            f"/api/v1/ui/client-portal/public/documents/{documento_id}/modulo",
            headers={"X-Client-Portal-Token": token},
        ).get_json()
        assert campi["ok"] is True
        assert campi["compilabile"] is True
        assert {voce["nome"] for voce in campi["campi"]} == {"nome_istante", "recapito"}
        assert campi["pagine"][0]["numero"] == 1

        compilato = client.post(
            f"/api/v1/ui/client-portal/public/documents/{documento_id}/modulo",
            json={"valori": {"nome_istante": "Antonio Affinito", "recapito": "3331234567"}},
            headers={"X-Client-Portal-Token": token},
        ).get_json()

    assert compilato["ok"] is True
    # La copia compilata è un documento nuovo: l'originale non si tocca.
    assert compilato["item"]["id"] != documento_id
    # Il portale normalizza gli spazi nei nomi dei file caricati.
    assert compilato["item"]["filename"] == "Modulo_organismo-compilato.pdf"
    nomi = {voce["filename"] for voce in compilato["dashboard"]["documents"]}
    assert "Modulo_organismo.pdf" in nomi
    assert "Modulo_organismo-compilato.pdf" in nomi


def test_un_pdf_senza_campi_resta_consultabile_e_lo_dice(tmp_path: Path):
    """Non si finge di compilare un PDF che non ha campi predisposti."""
    app, cliente, fascicolo = _portale_pronto(tmp_path)
    with app.test_client() as client:
        _login(client)
        token, _ = _create_invite(client, cliente.id, fascicolo.id)
        client.post(f"/api/v1/ui/client-portal/public/invites/{token}/accept", json={})
        documento_id = _carica_nel_portale(client, token, _pdf_senza_campi(), "Lettera.pdf")

        campi = client.get(
            f"/api/v1/ui/client-portal/public/documents/{documento_id}/modulo",
            headers={"X-Client-Portal-Token": token},
        ).get_json()

    assert campi["ok"] is True
    assert campi["compilabile"] is False
    assert campi["campi"] == []
    assert "non contiene campi predisposti" in campi["message"]


def test_il_modulo_di_un_altra_pratica_non_si_apre(tmp_path: Path):
    """Il cliente vede solo i documenti della propria pratica."""
    app, cliente, fascicolo = _portale_pronto(tmp_path)
    with app.test_client() as client:
        _login(client)
        token, _ = _create_invite(client, cliente.id, fascicolo.id)
        client.post(f"/api/v1/ui/client-portal/public/invites/{token}/accept", json={})

        campi = client.get(
            "/api/v1/ui/client-portal/public/documents/cpd_inesistente/modulo",
            headers={"X-Client-Portal-Token": token},
        ).get_json()

    assert campi["ok"] is False
    assert campi["code"] == "not_found"
