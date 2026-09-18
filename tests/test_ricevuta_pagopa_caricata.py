"""La ricevuta pagoPA riconosciuta quando l'avvocato la carica nel fascicolo.

Il pagamento avviene sul portale ufficiale con l'autenticazione dell'avvocato:
il gestionale non paga e non scarica nulla (regole PST). Quello che può fare è
riconoscere la ricevuta che l'avvocato riporta nel fascicolo — trascinandola
fra i documenti come farebbe con qualsiasi altro file — verificarla secondo lo
schema ministeriale e annotare il versamento.

Base normativa: art. 4 c.9 D.L. 193/2009; D.P.R. 115/2002 art. 13.
"""

from __future__ import annotations

import io

from pct.fascicoli import TipoFascicolo
from pct.pagamenti_giustizia import nota_ricevuta, riconosci_ricevuta_caricata
from tests.test_applicazioni import _cfg_web, _crea_operatore, _login
from tests.test_pagamenti_giustizia import _rt_xml
from web.app import create_app
from web.helpers import get_fascicoli


def _fascicolo(app):
    with app.app_context():
        return get_fascicoli().nuovo(
            "Rossi c. MIM", TipoFascicolo.CIVILE, nome_cliente="Rossi Mario",
            tribunale="Tribunale di Palmi", numero_rg="1234", anno_rg=2024,
        )


def _carica(client, id_fasc: str, nome: str, dati: bytes):
    return client.post(
        f"/fascicoli/{id_fasc}/documenti/carica",
        data={"files": (io.BytesIO(dati), nome)},
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )


def test_una_rt_valida_viene_riconosciuta_dal_nome_e_dallo_schema():
    assert riconosci_ricevuta_caricata("RT.xml", _rt_xml()) is not None
    assert riconosci_ricevuta_caricata("rt_ABC123.xml.p7m", _rt_xml()) is not None


def test_non_si_indovina_un_pagamento_da_un_file_qualsiasi():
    """Un falso positivo farebbe risultare pagato un contributo che non lo è."""
    assert riconosci_ricevuta_caricata("ricevuta.pdf", b"%PDF-1.4 pagamento 237,00") is None
    assert riconosci_ricevuta_caricata("rt.xml", b"<qualcosa/>") is None
    assert riconosci_ricevuta_caricata("rt.xml", b"") is None
    assert riconosci_ricevuta_caricata("pagamento.txt", _rt_xml()) is None


def test_la_nota_dice_che_cosa_prova_quel_file():
    """L'avvocato deve leggerlo dal fascicolo, senza riaprire l'XML."""
    nota = nota_ricevuta(riconosci_ricevuta_caricata("RT.xml", _rt_xml()))
    for atteso in ("Pagamento eseguito", "237", "RF123456789012345678", "2026-08-10"):
        assert atteso in nota, f"«{atteso}» non compare nella nota"


def test_caricando_la_ricevuta_il_contributo_risulta_versato(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)
    fascicolo = _fascicolo(app)
    with app.test_client() as client:
        _login(client)
        risposta = _carica(client, fascicolo.id, "RT.xml", _rt_xml())
    assert risposta.status_code == 200, risposta.get_data(as_text=True)[:300]
    corpo = risposta.get_json() or {}
    assert corpo.get("ok") is True
    assert "ricevuta telematica" in (corpo.get("messaggio") or "").casefold()

    with app.app_context():
        aggiornato = get_fascicoli().get(fascicolo.id)
    contributo = (getattr(aggiornato, "pagamenti", {}) or {}).get("contributo_unificato") or {}
    assert contributo.get("status") == "pagato"
    assert contributo.get("importo") == 237.0
    assert contributo.get("documento_fonte") == "RT.xml"
    assert "RF123456789012345678" in str(contributo.get("note") or "")


def test_una_ricevuta_non_eseguita_resta_agli_atti_ma_non_fa_risultare_pagato(tmp_path):
    """Fail-closed: solo l'esito «eseguito» prova un versamento."""
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)
    fascicolo = _fascicolo(app)
    with app.test_client() as client:
        _login(client)
        risposta = _carica(client, fascicolo.id, "RT.xml", _rt_xml(esito="1"))
    assert risposta.status_code == 200

    with app.app_context():
        aggiornato = get_fascicoli().get(fascicolo.id)
    contributo = (getattr(aggiornato, "pagamenti", {}) or {}).get("contributo_unificato") or {}
    assert contributo.get("status") != "pagato", "una ricevuta non eseguita non prova un versamento"
    documenti = list(getattr(aggiornato, "documenti", []) or [])
    assert documenti, "la ricevuta deve restare agli atti"
    assert "non eseguito" in str(getattr(documenti[0], "note", "")).casefold()


def test_un_documento_qualsiasi_resta_un_documento_qualsiasi(tmp_path):
    app = create_app(_cfg_web(tmp_path))
    _crea_operatore(app)
    fascicolo = _fascicolo(app)
    with app.test_client() as client:
        _login(client)
        risposta = _carica(client, fascicolo.id, "memoria.pdf", b"%PDF-1.4\nmemoria\n%%EOF")
    assert risposta.status_code == 200
    corpo = risposta.get_json() or {}
    assert "ricevuta telematica" not in (corpo.get("messaggio") or "").casefold()

    with app.app_context():
        aggiornato = get_fascicoli().get(fascicolo.id)
    assert not (getattr(aggiornato, "pagamenti", {}) or {}).get("contributo_unificato")
