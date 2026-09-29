"""Deposito e notifica di un solo documento, caricamento rapido dei documenti del fascicolo."""

from __future__ import annotations

import io
from pathlib import Path

from pct.fascicoli import TipoFascicolo

from tests.test_revisione_2410_sicurezza import _app
from tests.test_topbar_operational_api import _login
from web.helpers import get_fascicoli

ROOT = Path(__file__).resolve().parents[1]


def _sorgente(percorso: str) -> str:
    return (ROOT / percorso).read_text(encoding="utf-8")


def test_riga_documento_apre_direttamente_deposito_e_notifica():
    pagina = _sorgente("frontend/src/components/FascicoliPage.tsx")
    riga = pagina[pagina.index("function DocumentRow("):pagina.index("type DocumentFlowMode")]
    # Deposito e Notifica stanno prima di Elimina e portano il solo documento, senza la finestra di scelta.
    assert riga.index("<span>Deposito</span>") < riga.index("<span>Notifica</span>") < riga.index("<span>Elimina</span>")
    assert "documentoSingoloHref(depositoHref, doc.id, true)" in riga
    assert "documentoSingoloHref(notificaHref, doc.id, false)" in riga
    helper = pagina[pagina.index("function documentoSingoloHref"):pagina.index("function isNotificationSelectableDocument")]
    assert "appendSelectedDocumentsToHref(href, [documentId])" in helper
    assert "atto_principale=" in helper
    assert "depositoHref={depositTelematicHref}" in pagina and "notificaHref={notificationHref}" in pagina


def test_deposito_con_un_solo_documento_lo_rende_atto_principale():
    deposito = _sorgente("frontend/src/components/FascicoloDepositoPage.tsx")
    assert "get('atto_principale')" in deposito
    assert "explicitDocumentSelection && requestedDepositSelectionIds.length === 1" in deposito
    assert "const forcedRole: DepositDocumentRole = doc.id === requestedMainActId ? 'atto_principale'" in deposito
    assert "ricevuto dal fascicolo come atto principale del deposito." in deposito
    # La notifica riceve il documento con lo stesso parametro già gestito dalla pagina.
    notifiche = _sorgente("frontend/src/components/NotificheLegaliPage.tsx")
    assert "'documenti'" in notifiche and "setSelectedDocumentId(matchedIds[0] || '')" in notifiche


def test_caricamento_non_attende_la_lettura_del_contenuto(tmp_path, monkeypatch):
    chiamate: list[bool] = []

    def finto_indicizza(*_args, blocking=True, **_kwargs):
        chiamate.append(blocking)

    monkeypatch.setattr("web.bootstrap.fascicoli_document_routes.indicizza_documento_lex", finto_indicizza)
    app = _app(tmp_path)
    app.config["LEX_INDEXING_SYNC"] = False
    with app.test_request_context("/"):
        fascicolo = get_fascicoli().nuovo("Rossi c. Bianchi", TipoFascicolo.CIVILE)
    with app.test_client() as client:
        _login(client)
        risposta = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/carica",
            data={"files": (io.BytesIO(b"%PDF-1.4\n%prova\n"), "memoria.pdf"), "classificazione_modalita": "auto"},
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
            content_type="multipart/form-data",
        )
    dati = risposta.get_json()
    assert risposta.status_code == 200 and dati["ok"] is True and dati["documenti_id"]
    assert chiamate == [False]


def test_caricamento_mostra_avanzamento_e_aggiorna_solo_i_documenti():
    carica = _sorgente("frontend/src/components/fascicoli/caricaDocumenti.tsx")
    assert "xhr.upload.onprogress" in carica
    assert "Invio a IUSENTRA in corso…" in carica
    assert "File ricevuti: registrazione nel fascicolo…" in carica
    pagina = _sorgente("frontend/src/components/FascicoliPage.tsx")
    assert "<DocumentUploadWorkspace data={data} onDone={refreshDocuments} onError={failDetail}/>" in pagina
    assert "<AvanzamentoCaricamento stato={stato}/>" in pagina
