"""Il controllo periodico del decreto che adegua la soglia del patrocinio.

Tiene insieme due cose che esistono gia': la raccolta degli atti dalla Gazzetta
Ufficiale, che e' compito della pipeline delle fonti legali, e la tabella
normativa versionata ``patrocinio_limiti_reddito``. La decisione sta in
``pct.patrocinio_adeguamento``, che non conosce ne' Flask ne' la rete.

Il controllo non riscrive la soglia. Prepara la riga da aggiungere e la
consegna all'avvocato — in chat sul presidio degli aggiornamenti legali e in
audit — perche' una soglia di legge la conferma una persona, sull'atto.
Base normativa: art. 77 D.P.R. 115/2002.
"""

from __future__ import annotations

from typing import Any

from flask import current_app

FONTE = "gazzetta_ufficiale"


def _atti_dalla_gazzetta(config: Any) -> list[dict[str, Any]]:
    """Gli atti raccolti dalla fonte ufficiale gia' censita nel sistema."""
    import requests

    from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS
    from pct.legal_update_source_parsers import fetch_source_documents

    sorgente = next((dict(r) for r in DEFAULT_SOURCE_ROWS if r.get("code") == FONTE), None)
    if not sorgente:
        return []
    documenti = fetch_source_documents(
        sorgente,
        request_get=lambda url, **kw: requests.get(url, timeout=kw.pop("timeout", 30), **kw),
    )
    return [
        {
            "titolo": documento.get("title") or documento.get("titolo") or "",
            "testo": documento.get("body_short") or documento.get("raw_text") or "",
            "data": (documento.get("published_at") or documento.get("data") or "")[:10],
            "url": documento.get("url") or documento.get("link") or "",
        }
        for documento in documenti
    ]


def controlla_adeguamento_patrocinio(config: Any = None) -> dict[str, Any]:
    """Esegue il controllo e restituisce l'esito, senza toccare la tabella."""
    from pct.patrocinio_adeguamento import controlla_adeguamento
    from web.helpers import get_normative_tables

    esito = controlla_adeguamento(
        get_normative_tables(),
        lambda: _atti_dalla_gazzetta(config or current_app.config),
    )
    if esito.get("aggiornamento"):
        current_app.logger.warning(
            "[patrocinio] Adeguamento da confermare: %s", esito.get("messaggio")
        )
    else:
        current_app.logger.info("[patrocinio] %s", esito.get("messaggio"))
    _registra_esito(esito)
    return esito


def _registra_esito(esito: dict[str, Any]) -> None:
    """Lascia traccia dell'esito dove lo studio lo vede e dove resta in audit."""
    if not esito.get("aggiornamento"):
        return
    try:
        from pct.legal_update_repository import LegalUpdateDbConfig, LegalUpdateRepository

        repository = LegalUpdateRepository(
            LegalUpdateDbConfig(path=str(current_app.config.get("LEGAL_UPDATE_DB") or ""))
        )
        registra = getattr(repository, "registra_segnalazione", None)
        if callable(registra):
            registra({
                "fonte": FONTE,
                "materia": "patrocinio_limiti_reddito",
                "messaggio": esito.get("messaggio", ""),
                "atto": esito.get("atto", {}),
                "riga_proposta": esito.get("riga_proposta", {}),
            })
    except Exception:
        # La segnalazione e' un di piu': l'esito resta nel log e nel ritorno.
        current_app.logger.exception("[patrocinio] Segnalazione dell'adeguamento non registrata")


__all__ = ["FONTE", "controlla_adeguamento_patrocinio"]
