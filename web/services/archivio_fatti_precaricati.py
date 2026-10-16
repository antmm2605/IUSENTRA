"""Fatti dell'archivio precaricati per una richiesta che scorre molti fascicoli.

L'elenco dei fascicoli costruisce una riga per fascicolo e ogni riga chiede
all'archivio delle letture gli importi e le esenzioni del proprio fascicolo:
con 300 fascicoli erano 600 interrogazioni, ognuna con l'apertura del
registro. Qui si legge una volta sola, per tutti i fascicoli e le categorie
dichiarate, e `fatti_fascicolo` risponde dalla memoria della richiesta.

La memoria vive solo dentro il blocco `precaricati(...)`: fuori da lì ogni
chiamata torna a leggere l'archivio, così una scrittura successiva non può
essere nascosta da un dato vecchio. Una lettura cumulativa fallita resta
un errore esplicito della proiezione.
"""

from __future__ import annotations

import logging
from functools import wraps
from copy import deepcopy
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

from flask import g, has_request_context

logger = logging.getLogger(__name__)
_CHIAVE = "_archivio_fatti_precaricati"


def _testo(valore: Any) -> str:
    return str(valore or "").strip()


@contextmanager
def precaricati(fascicoli: Iterable[Any], categorie: Iterable[str]) -> Iterator[None]:
    """Dentro il blocco, i fatti delle categorie indicate arrivano dalla lettura cumulativa."""
    if not has_request_context():
        yield
        return
    precedente = getattr(g, _CHIAVE, None)
    try:
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente, percorso_registro

        ids = [_testo(getattr(f, "id", "")) for f in fascicoli]
        tenant, path = tenant_corrente(), percorso_registro()
        grezzi = registro_corrente().fatti_per_fascicoli(tenant, ids, categorie, verifiche=None)
        nomi = registro_corrente().nomi_documenti_per_fascicoli(tenant, ids)
        setattr(g, _CHIAVE, {'tenant': tenant, 'path': path, 'fatti': grezzi, 'nomi': nomi, 'ids': frozenset(ids)})
    except Exception as exc:
        raise RuntimeError("Archivio delle letture non disponibile per l’elenco dei fascicoli.") from exc
    try:
        yield
    finally:
        setattr(g, _CHIAVE, precedente)


def nome_documento_precaricato(fascicolo_id: str, documento_id: str) -> str | None:
    """None fuori dall'istantanea; stringa vuota se il nome non è registrato."""
    memoria = getattr(g, _CHIAVE, None) if has_request_context() else None
    if not memoria or _testo(fascicolo_id) not in memoria['ids']:
        return None
    from web.services.registro_letture_runtime import tenant_corrente, percorso_registro
    if memoria['tenant'] != tenant_corrente() or memoria['path'] != percorso_registro():
        return None
    return memoria['nomi'].get((_testo(fascicolo_id), _testo(documento_id)), '')


def fatti_precaricati(fascicolo_id: str, filtri: dict[str, Any], canonico: bool) -> list[Any] | None:
    """I fatti già in memoria per questa domanda, oppure None se va letto l'archivio."""
    snapshot = getattr(g, '_archivio_fatti_dettaglio', None) if has_request_context() else None
    if snapshot is not None and snapshot['fascicolo'] == _testo(fascicolo_id):
        from web.services.registro_letture_runtime import tenant_corrente, percorso_registro
        if snapshot['tenant'] == tenant_corrente() and snapshot['path'] == percorso_registro() and set(filtri) <= {'categoria', 'campo', 'verifiche', 'motore', 'tipo'}:
            from pct.registro_letture.fatti_repository import VERIFICHE_UTILI
            from pct.archivio_letture import fatti_canonici
            allowed = filtri.get('verifiche', VERIFICHE_UTILI)
            allowed = set(allowed) if allowed is not None else None
            facts = [f for f in snapshot['fatti'] if (allowed is None or f.verifica in allowed)
                     and all(not filtri.get(k) or getattr(f, k) == filtri[k] for k in ('categoria', 'campo', 'motore', 'tipo'))]
            facts = deepcopy(facts)
            return fatti_canonici(facts) if canonico and not filtri.get('motore') and not filtri.get('tipo') else facts
    if not has_request_context() or set(filtri) - {'categoria', 'campo', 'verifiche', 'motore', 'tipo'}:
        return None
    memoria = getattr(g, _CHIAVE, None)
    if not memoria:
        return None
    from web.services.registro_letture_runtime import tenant_corrente, percorso_registro
    if memoria['tenant'] != tenant_corrente() or memoria['path'] != percorso_registro():
        return None
    fatti = memoria['fatti'].get((_testo(fascicolo_id), _testo(filtri.get("categoria"))))
    if fatti is None:
        return None
    from pct.registro_letture.fatti_repository import VERIFICHE_UTILI
    from pct.archivio_letture import fatti_canonici
    allowed = filtri.get('verifiche', VERIFICHE_UTILI)
    allowed = set(allowed) if allowed is not None else None
    selected = deepcopy([f for f in fatti if (allowed is None or f.verifica in allowed)
                         and all(not filtri.get(k) or getattr(f, k) == filtri[k]
                                 for k in ('campo', 'motore', 'tipo'))])
    return fatti_canonici(selected) if canonico and not filtri.get('motore') and not filtri.get('tipo') else selected


def istantanea_dettaglio(function):
    """Una sola lettura SQL per la proiezione GET di un singolo fascicolo."""
    @wraps(function)
    def wrapped(**kwargs):
        from flask import request
        if not has_request_context() or request.method != 'GET':
            return function(**kwargs)
        repo = kwargs['get_fascicoli']()
        fascicolo = repo.get(kwargs['id_fasc'])
        if fascicolo is None:
            return function(**kwargs)
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente, percorso_registro
        previous = getattr(g, '_archivio_fatti_dettaglio', None)
        tenant, path = tenant_corrente(), percorso_registro()
        facts = registro_corrente().fatti(tenant, str(fascicolo.id), verifiche=None)
        g._archivio_fatti_dettaglio = {'tenant': tenant, 'path': path, 'fascicolo': str(fascicolo.id), 'fatti': facts}
        try:
            return function(**{**kwargs, 'get_fascicoli': lambda: repo})
        finally:
            g._archivio_fatti_dettaglio = previous
    return wrapped


__all__ = ["fatti_precaricati", "precaricati"]
