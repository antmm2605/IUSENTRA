"""Clienti visibili all'utente nelle API dell'interfaccia React.

Chi ha il permesso ``clienti.leggi`` vede l'intera anagrafica dello studio; gli
altri vedono solo le cartelle cliente condivise con loro (``GestioneCondivisioni``),
come già avveniva nelle pagine storiche (``cliente_accessibile``).
Base: art. 32 GDPR e art. 2-quaterdecies D.Lgs. 196/2003 (accesso limitato
alle persone autorizzate) e segreto professionale (art. 13 L. 247/2012).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import current_app, flash, g, redirect, url_for


class ClientiFiltrati:
    """Repository dei clienti limitato agli identificativi ammessi."""

    def __init__(self, repo: Any, ammessi: set[str]):
        self._repo = repo
        self._ammessi = set(ammessi)

    def tutti(self, *args: Any, **kwargs: Any) -> list[Any]:
        return [c for c in self._repo.tutti(*args, **kwargs) if str(getattr(c, "id", "") or "") in self._ammessi]

    def get(self, id_cliente: str) -> Any:
        return self._repo.get(id_cliente) if str(id_cliente or "") in self._ammessi else None

    def __getattr__(self, nome: str) -> Any:
        return getattr(self._repo, nome)


def _condivisioni() -> Any | None:
    runtime = current_app.extensions.get("core_runtime", {}) or {}
    getter = runtime.get("get_condivisioni")
    return getter() if callable(getter) else None


def clienti_condivisi_con_utente() -> set[str]:
    utente = g.get("utente_corrente")
    if utente is None:
        return set()
    try:
        gestore = _condivisioni()
        return set(gestore.ids_clienti_accessibili(utente.id)) if gestore is not None else set()
    except Exception:
        current_app.logger.warning("Condivisioni clienti non leggibili: nessuna cartella condivisa mostrata.")
        return set()


def accesso_globale_clienti() -> bool:
    utente = g.get("utente_corrente")
    return bool(utente is not None and utente.ha_permesso("clienti.leggi"))


def loader_clienti_visibili(get_clienti: Callable[[], Any], *, api_key: bool = False) -> Callable[[], Any]:
    if api_key or accesso_globale_clienti():
        return get_clienti
    ammessi = clienti_condivisi_con_utente()
    return lambda: ClientiFiltrati(get_clienti(), ammessi)


def cliente_visibile(id_cliente: str, *, api_key: bool = False) -> bool:
    if api_key or accesso_globale_clienti():
        return True
    return str(id_cliente or "") in clienti_condivisi_con_utente()


def pagina_cartella_negata(path: str) -> Any | None:
    """Rifiuto per la pagina React della cartella cliente non visibile all'utente.

    La shell React rispondeva 200 prima del controllo della vista storica
    (``cliente_accessibile``): il rifiuto non scattava più sulla pagina.
    """
    parti = [parte for parte in path.split("/") if parte]
    if len(parti) < 2 or parti[0].lower() != "clienti" or parti[1].lower() in {"nuovo", "esporta", "importa"}:
        return None
    if cliente_visibile(parti[1]):
        return None
    flash("Non hai accesso a questa cartella cliente.", "danger")
    return redirect(url_for("lista_clienti"))
