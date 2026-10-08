"""Contesto unico della Ricerca Studio.

Le sorgenti che alimentano l'indice erano elencate due volte: nella pagina
Ricerca e nella top bar. La top bar ne dichiarava nove invece di dodici,
senza messaggi, PEC ed email ordinaria, e ricostruiva l'indice con quella
lista ridotta quando lo trovava vuoto: da quel momento cercare una PEC non
dava piu' risultati, ne' dalla top bar ne' dalla pagina Ricerca.

Da qui in avanti l'elenco delle sorgenti sta in un punto solo. Chi indicizza
e chi interroga partono dallo stesso contesto, quindi una sorgente aggiunta
qui vale per tutte le superfici senza doverla ricordare altrove.
"""

from __future__ import annotations

from typing import Any, Callable
from pathlib import Path


def percorso_indice_ricerca_studio() -> Path:
    """Pagina e top bar interrogano lo stesso indice dello studio corrente."""
    from flask import current_app, g
    from pct.global_search.service import default_global_search_db_path

    paths = dict(getattr(g, "data_paths", {}) or {})
    multi = current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False)
    if multi or getattr(g, "tenant_context_missing", False):
        if not paths.get("SEARCH_INDEX"):
            raise RuntimeError("Contesto studio non disponibile per la ricerca")
        from web.services.tenant_isolation_runtime import assert_tenant_data_path
        path = paths.get("GLOBAL_SEARCH_INDEX") or default_global_search_db_path(paths["SEARCH_INDEX"])
        return Path(assert_tenant_data_path(str(path), key="SEARCH_INDEX"))
    configured = paths.get("GLOBAL_SEARCH_INDEX") or current_app.config.get("GLOBAL_SEARCH_INDEX")
    return Path(configured) if configured else default_global_search_db_path(
        paths.get("SEARCH_INDEX") or current_app.config.get("SEARCH_INDEX", "./data/search/index.db")
    )

#  Nomi delle sorgenti nell'ordine in cui gli adapter se le aspettano. La
#  chiave e' il nome usato dal contesto, il valore il nome della funzione in
#  web.helpers che costruisce il gestore corrispondente.
SORGENTI_RICERCA: tuple[str, ...] = (
    "fascicoli",
    "clienti",
    "soggetti",
    "scadenziario",
    "agenda",
    "preventivi",
    "fatturazione",
    "pagamenti",
    "legal_intelligence",
    "messaggi",
    "email_pec",
    "email_ordinaria",
)


def costruisci_contesto_ricerca(
    *,
    tenant_id: str,
    search_index_path: str,
    factories: dict[str, Callable[[], Any]],
    on_error: Callable[[str, Exception], None] | None = None,
) -> dict[str, Any]:
    """Prepara il contesto con tutte le sorgenti dichiarate.

    Una sorgente non disponibile resta a ``None`` e viene segnalata, invece di
    far fallire l'intera ricerca: meglio un indice parziale e un messaggio nel
    log che nessun risultato.
    """

    contesto: dict[str, Any] = {
        "tenant_id": tenant_id,
        "search_index_path": search_index_path,
    }
    for nome in SORGENTI_RICERCA:
        contesto[nome] = None

    for nome in SORGENTI_RICERCA:
        factory = factories.get(nome)
        if factory is None:
            continue
        try:
            contesto[nome] = factory()
        except Exception as exc:  # pragma: no cover - dipende dai moduli attivi
            if on_error is not None:
                on_error(nome, exc)

    #  Gli adapter leggono le comunicazioni sotto questo nome: e' lo stesso
    #  gestore dei messaggi, non una sorgente in piu'.
    contesto["comunicazioni"] = contesto.get("messaggi")
    return contesto
