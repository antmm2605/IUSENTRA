"""Quote del contributo unificato nella ricevuta pagoPA e pagamento frazionato (31/10/2026).

Prima il caricamento registrava il totale della ricevuta (518 di contributo + 27 dell'art. 30 = 545 come
contributo pagato) e una seconda ricevuta sostituiva la prima invece di sommarsi.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from pct.contributo_quote import quote_della_ricevuta
from pct.pagamenti_giustizia import parse_rt
from web.services.ricevuta_pagopa_runtime import voce_contributo_da_ricevuta

_NS = "http://www.digitpa.gov.it/schemas/2011/Pagamenti/"


def _rt(quote: list[tuple[str, str]], *, totale: str | None = None, iuv: str = "IUV-1") -> bytes:
    totale = totale or str(sum(Decimal(importo) for importo, _ in quote))
    singoli = "".join(
        f"<pay_i:datiSingoloPagamento><pay_i:singoloImportoPagato>{importo}</pay_i:singoloImportoPagato>"
        f"<pay_i:causaleVersamento>{causale}</pay_i:causaleVersamento></pay_i:datiSingoloPagamento>"
        for importo, causale in quote
    )
    return (f'<pay_i:RT xmlns:pay_i="{_NS}"><pay_i:datiPagamento><pay_i:codiceEsitoPagamento>0</pay_i:codiceEsitoPagamento>'
            f"<pay_i:importoTotalePagato>{totale}</pay_i:importoTotalePagato>"
            f"<pay_i:identificativoUnivocoVersamento>{iuv}</pay_i:identificativoUnivocoVersamento>{singoli}"
            "</pay_i:datiPagamento></pay_i:RT>").encode()


def test_contributo_e_anticipazione_forfettaria_restano_separati():
    quote = quote_della_ricevuta(_rt([("518.00", "Contributo unificato RG 123/2026"),
                                      ("27.00", "Anticipazione forfettaria art. 30")]), 545.0)
    assert (quote.contributo, quote.art_30, quote.altre, quote.errore) == (Decimal("518.00"), Decimal("27.00"), 0, "")


def test_ricevute_incoerenti_o_senza_contributo_restano_da_verificare():
    assert quote_della_ricevuta(b"non xml", 1.0).errore
    assert quote_della_ricevuta(_rt([("abc", "Contributo unificato")], totale="1"), 1.0).errore
    assert quote_della_ricevuta(_rt([("-5.00", "Contributo unificato")], totale="1"), 1.0).errore
    assert quote_della_ricevuta(_rt([("10.00", "Contributo unificato")]), float("nan")).errore
    assert "coincidono" in quote_della_ricevuta(_rt([("10.00", "Contributo unificato")]), 99.0).errore
    senza = quote_della_ricevuta(_rt([("16.00", "Marca da bollo")]), 16.0)
    assert "contributo" in senza.errore and senza.altre == Decimal("16.00")


def _carica(precedente, contenuto: bytes, documento_id: str):
    rt = parse_rt(contenuto)
    return voce_contributo_da_ricevuta(precedente, rt, quote_della_ricevuta(contenuto, rt.importo_totale),
                                       nome=f"{documento_id}.xml", documento_id=documento_id)


def test_il_caricamento_registra_la_quota_del_contributo_e_somma_il_frazionato():
    voce = _carica(None, _rt([("518.00", "Contributo unificato"), ("27.00", "Anticipazione forfettaria")]), "D1")
    assert voce["importo"] == 518.0 and voce["art_30"] == 27.0 and voce["status"] == "pagato"
    prima = _carica(None, _rt([("259.00", "Contributo unificato")], iuv="IUV-A"), "D2")
    seconda = _carica(prima, _rt([("259.00", "Contributo unificato")], iuv="IUV-B"), "D3")
    assert seconda["importo"] == 518.0 and len(seconda["ricevute"]) == 2
    # Ricaricare la stessa ricevuta non la conta due volte.
    assert _carica(seconda, _rt([("259.00", "Contributo unificato")], iuv="IUV-B"), "D3")["importo"] == 518.0


def test_voce_precedente_senza_elenco_e_ricevuta_senza_contributo():
    vecchia = {"iuv": "IUV-OLD", "importo": 100.0, "documento_id": "D0", "data_pagamento": "2026-01-10"}
    assert _carica(vecchia, _rt([("137.00", "Contributo unificato")], iuv="IUV-NEW"), "D4")["importo"] == 237.0
    voce = _carica(None, _rt([("16.00", "Marca da bollo")]), "D5")
    assert voce["status"] == "da_verificare" and voce["pagato"] is False and "Da verificare" in voce["note"]
    assert voce_contributo_da_ricevuta("non un dizionario", SimpleNamespace(iuv="", data_esito_pagamento="", data_ricevuta=""),
                                       quote_della_ricevuta(_rt([("5.00", "Contributo unificato")]), 5.0),
                                       nome="x", documento_id="")["importo"] == 5.0
