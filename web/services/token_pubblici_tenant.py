"""Studio di un link pubblico (portale del cliente, link di pagamento).

Il cliente apre il link senza sessione: in un'installazione con più studi lo
studio si ricava dal token, cercandolo negli archivi di ciascuno studio attivo.
Senza questo passo le pagine leggerebbero l'archivio comune invece di quello
dello studio che ha creato il link (per i pagamenti: link sempre «scaduto»).

La ricerca è una sola, usata dal portale e dai pagamenti: cambia solo la
verifica del token nell'archivio dello studio candidato. I webhook dei gestori
di pagamento la usano con il riferimento del link al posto del token.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from typing import Any

from flask import current_app, g

# Impronta del token -> slug dello studio: evita di rileggere tutti gli studi a
# ogni richiesta dello stesso link. Il token in chiaro non viene conservato.
VerificaToken = Callable[[Any, dict[str, str]], bool]

_ATTRIBUTI_CONTESTO = ("tenant", "tenant_context_slug", "data_paths", "storage_runtime")
_CACHE_ARCHIVIO = ("_storage_runtime_profile", "_runtime_studio_db", "_tenant_isolation_root_cache")

# Link sconosciuti di recente: per un token che non esiste la ricerca legge gli
# archivi di tutti gli studi; ripetuta a raffica (link inventati) moltiplicava il
# lavoro per il numero di studi. Per un minuto la risposta resta «non trovato».
DURATA_NEGATIVI_SECONDI = 60
MASSIMO_NEGATIVI = 4096
_NEGATIVI: dict[str, float] = {}
_LOCK_NEGATIVI = threading.Lock()


def _negativo_recente(chiave: str) -> bool:
    adesso = time.monotonic()
    with _LOCK_NEGATIVI:
        scadenza = _NEGATIVI.get(chiave)
        if scadenza is None:
            return False
        if scadenza < adesso:
            _NEGATIVI.pop(chiave, None)
            return False
        return True


def _registra_negativo(chiave: str) -> None:
    adesso = time.monotonic()
    with _LOCK_NEGATIVI:
        if len(_NEGATIVI) >= MASSIMO_NEGATIVI:
            for vecchia in [k for k, v in _NEGATIVI.items() if v < adesso]:
                _NEGATIVI.pop(vecchia, None)
            if len(_NEGATIVI) >= MASSIMO_NEGATIVI:
                _NEGATIVI.clear()
        _NEGATIVI[chiave] = adesso + DURATA_NEGATIVI_SECONDI


def dimentica_negativi() -> None:
    """Svuota i link sconosciuti ricordati (test e creazione di un nuovo link)."""
    with _LOCK_NEGATIVI:
        _NEGATIVI.clear()


def impronta_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def multi_studio_attivo() -> bool:
    return bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False))


def _pulisci_cache_archivio() -> None:
    for nome in _CACHE_ARCHIVIO:
        g.pop(nome, None)


def _imposta_studio(studio: Any, percorsi: dict[str, str]) -> None:
    _pulisci_cache_archivio()
    g.tenant = studio
    g.tenant_context_slug = studio.slug
    g.data_paths = percorsi


def risolvi_studio_da_token(token: str, *, verifica: VerificaToken, cache: dict[str, str], etichetta: str) -> bool:
    """Imposta lo studio del link in `g` e restituisce True se trovato.

    Non fa nulla in modalità a studio singolo o se la richiesta ha già uno
    studio (sessione dello studio aperta nello stesso browser): comportamento
    identico a quello storico del portale.
    """
    if getattr(g, "data_paths", None) or not current_app.config.get("MULTI_TENANT"):
        return False
    token = str(token or "").strip()
    if not token:
        return False
    precedente = {nome: getattr(g, nome, None) for nome in _ATTRIBUTI_CONTESTO}
    try:
        from pct.tenant import GestioneTenant, StatoTenant

        tenants = GestioneTenant(registry_path=current_app.config["TENANTS_REGISTRY"])
        impronta = impronta_token(token)
        slug = cache.get(impronta, "")
        chiave_negativa = f"{etichetta}:{current_app.config.get('TENANTS_REGISTRY', '')}:{impronta}"
        if not slug and _negativo_recente(chiave_negativa):
            return False
        studi = [tenants.get(slug)] if slug else [s for s in tenants.lista() if s.stato != StatoTenant.SOSPESO]
        for studio in studi:
            if studio is None:
                continue
            percorsi = tenants.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
            # La verifica può usare l'archivio SQL dello studio candidato: il
            # contesto deve già essere il suo, e le cache di richiesta azzerate.
            _imposta_studio(studio, percorsi)
            if verifica(studio, percorsi):
                cache[impronta] = studio.slug
                _pulisci_cache_archivio()
                return True
        if not slug:
            _registra_negativo(chiave_negativa)
    except Exception:
        current_app.logger.exception("%s: studio del link non determinato", etichetta)
    for nome, valore in precedente.items():
        setattr(g, nome, valore)
    _pulisci_cache_archivio()
    return False


def risolvi_studio_da_slug(slug: str, *, etichetta: str) -> bool:
    """Imposta in `g` lo studio indicato dall'indirizzo (es. webhook per studio).

    Solo con più studi e solo per uno studio registrato e non sospeso. Se la
    richiesta ha già uno studio vale solo quando è lo stesso: l'indirizzo non
    sposta mai una richiesta in un altro studio.
    """
    if not current_app.config.get("MULTI_TENANT"):
        return False
    slug = str(slug or "").strip().lower()
    if not slug:
        return False
    if getattr(g, "data_paths", None):
        attuale = getattr(getattr(g, "tenant", None), "slug", "") or getattr(g, "tenant_context_slug", "")
        return str(attuale or "").strip().lower() == slug
    try:
        from pct.tenant import GestioneTenant, StatoTenant

        tenants = GestioneTenant(registry_path=current_app.config["TENANTS_REGISTRY"])
        studio = tenants.get(slug)
        if studio is None or studio.stato == StatoTenant.SOSPESO:
            return False
        percorsi = tenants.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
    except Exception:
        current_app.logger.exception("%s: studio dell'indirizzo non determinato", etichetta)
        return False
    _imposta_studio(studio, percorsi)
    return True


def contesto_studio_mancante() -> bool:
    """Vero se con più studi la richiesta non ha uno studio: il link non si serve.

    Senza studio le letture ricadrebbero sull'archivio comune dell'installazione.
    """
    return multi_studio_attivo() and not getattr(g, "data_paths", None)


__all__ = [
    "contesto_studio_mancante",
    "impronta_token",
    "multi_studio_attivo",
    "risolvi_studio_da_slug",
    "risolvi_studio_da_token",
]
