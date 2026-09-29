"""Avvisi PST nel repository del fascicolo; nessun esito dedotto dal redirect."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

ENTE_GIUSTIZIA = "80184430587"
KEY = "pagopa_portale"


def checkout_url(numero: str) -> str:
    if not re.fullmatch(r"\d{18}", numero):
        raise ValueError("Il numero avviso deve contenere 18 cifre.")
    # Route :rptid del checkout ufficiale pagoPA: CF ente + numero avviso.
    return f"https://checkout.pagopa.it/{ENTE_GIUSTIZIA}{numero}"


def leggi_avvisi(gestore: Any, fascicolo_id: str) -> list[dict]:
    fascicolo = gestore.get(fascicolo_id)
    if fascicolo is None:
        raise LookupError("Fascicolo non trovato.")
    return list((dict(fascicolo.pagamenti or {}).get(KEY) or {}).get("avvisi") or [])


def registra_avviso(gestore: Any, fascicolo_id: str, dati: dict, actor: str) -> dict:
    numero = str(dati.get("numero_avviso") or "").strip()
    href = checkout_url(numero)
    try:
        importo = Decimal(str(dati.get("importo") or "").replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Importo dell’avviso non valido.") from exc
    if (not importo.is_finite() or importo <= 0 or importo > Decimal("999999999")
            or importo != importo.quantize(Decimal("0.01"))):
        raise ValueError("Importo dell’avviso non valido.")
    fascicolo = gestore.get(fascicolo_id)
    if fascicolo is None:
        raise LookupError("Fascicolo non trovato.")
    pagamenti = dict(fascicolo.pagamenti or {})
    sezione = dict(pagamenti.get(KEY) or {})
    avvisi = list(sezione.get("avvisi") or [])
    existing = next((a for a in avvisi if a.get("numero_avviso") == numero), None)
    if existing:
        if Decimal(str(existing["importo"])) != importo:
            raise ValueError("L’importo non coincide con l’avviso già conservato.")
        return existing
    avviso = {
        "numero_avviso": numero, "importo": str(importo),
        "ente_creditore": "Ministero della Giustizia", "codice_fiscale_ente": ENTE_GIUSTIZIA,
        "tipologia": str(dati.get("tipologia") or "Pagamento di giustizia")[:250],
        "codice_fiscale_debitore": str(dati.get("codice_fiscale_debitore") or "").strip().upper()[:16],
        "checkout_url": href, "stato": "ricevuta_da_acquisire",
        "creato_il": datetime.now(timezone.utc).isoformat(), "registrato_da": actor,
    }
    avvisi.append(avviso)
    sezione["avvisi"] = avvisi
    pagamenti[KEY] = sezione
    gestore.aggiorna(fascicolo_id, pagamenti=pagamenti)
    return avviso


def acquisisci_rt(gestore: Any, fascicolo_id: str, contenuto: bytes, actor: str) -> dict:
    from pct.fascicoli import TipoDocumento
    from pct.pagamenti_giustizia import parse_rt, nota_ricevuta

    rt = parse_rt(contenuto)
    if rt is None or not rt.pagamento_eseguito or rt.avvisi:
        raise ValueError("La ricevuta non attesta un pagamento eseguito con dati completi.")
    fascicolo = gestore.get(fascicolo_id)
    if fascicolo is None:
        raise LookupError("Fascicolo non trovato.")
    pagamenti = dict(fascicolo.pagamenti or {})
    sezione = dict(pagamenti.get(KEY) or {})
    avvisi = [dict(a) for a in sezione.get("avvisi") or []]
    avviso = next((a for a in avvisi if rt.iuv in {a["numero_avviso"], a["numero_avviso"][1:]}), None)
    if not avviso:
        raise ValueError("Lo IUV della ricevuta non corrisponde agli avvisi conservati in questo fascicolo.")
    if Decimal(str(rt.importo_totale)) != Decimal(avviso["importo"]):
        raise ValueError("L’importo della ricevuta non coincide con quello dell’avviso.")
    if avviso.get("documento_id"):
        return avviso
    nome = f"RT-{avviso['numero_avviso']}.xml"
    if not contenuto.lstrip().startswith(b"<"):
        nome += ".p7m"
    documento = gestore.aggiungi_documento(
        fascicolo_id, nome, TipoDocumento.ALLEGATO, contenuto,
        note=nota_ricevuta(rt), caricato_da=actor, fonte_documento="pagopa_rt",
        tags=["PagoPA", "ricevuta telematica"],
    )
    avviso.update(stato="ricevuta_acquisita", documento_id=documento.id, iuv=rt.iuv,
                  data_pagamento=rt.data_esito_pagamento or rt.data_ricevuta)
    sezione["avvisi"] = avvisi
    pagamenti[KEY] = sezione
    gestore.aggiorna(fascicolo_id, pagamenti=pagamenti)
    return avviso


def avviso_riuso(gestore: Any, fascicolo_id: str, iuv: str) -> str:
    """Avviso se la ricevuta risulta già usata in un altro fascicolo (non blocca nulla)."""
    from pct.pagamenti_giustizia_registro import avviso_riuso as testo, usi_altrove

    try:
        return testo(usi_altrove(gestore.tutti(archiviati=True), iuv, escludi=fascicolo_id))
    except Exception:
        return ""


def recupera_dal_pst(gestore: Any, fascicolo_id: str, numero: str, codice_fiscale: str, actor: str, *, verify: str) -> dict:
    """Chiede al PST pubblico la ricevuta dell'avviso e, se c'è, la verifica e la archivia.

    Stessa verifica dell'acquisizione manuale (IUV e importo dell'avviso conservato). Se il PST non la
    pubblica ancora torna ``{"trovata": False}``: non significa che il pagamento manchi.
    """
    from web.services.pagopa_pst_receipts import recupera_rt

    avvisi = leggi_avvisi(gestore, fascicolo_id)
    avviso = next((a for a in avvisi if a.get("numero_avviso") == numero), None)
    if avviso is None:
        raise ValueError("Avviso non conservato in questo fascicolo.")
    if avviso.get("documento_id"):
        return {"trovata": True, "avviso": avviso, "gia_acquisita": True}
    cf = str(codice_fiscale or avviso.get("codice_fiscale_debitore") or "").strip().upper()
    contenuto = recupera_rt(numero, cf, verify=verify)
    if contenuto is None:
        return {"trovata": False, "avviso": avviso}
    if cf and not avviso.get("codice_fiscale_debitore"):
        avviso["codice_fiscale_debitore"] = cf
    acquisito = acquisisci_rt(gestore, fascicolo_id, contenuto, actor)
    return {"trovata": True, "avviso": acquisito}
