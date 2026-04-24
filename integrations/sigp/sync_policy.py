"""Policy applicativa per la sincronizzazione autorizzata SIGP/PST."""

from __future__ import annotations

AUTHORIZED_CHANNELS = (
    {
        "id": "pst_pubblico",
        "label": "PST pubblico",
        "descrizione": "Consultazione tramite sessione ufficiale e autenticazione forte.",
    },
    {
        "id": "punto_accesso_autorizzato",
        "label": "Punto di Accesso autorizzato",
        "descrizione": "Servizi esposti da un PdA abilitato per lo studio o la software house.",
    },
    {
        "id": "model_office_sigp",
        "label": "Model Office SIGP",
        "descrizione": "Ambiente di test riservato alle software house abilitate.",
    },
)

SYNC_FUNCTIONS = (
    "ricerca_fascicolo",
    "elenco_fascicoli_visibili",
    "dettaglio_fascicolo",
    "parti",
    "eventi",
    "udienze",
    "documenti",
    "download_documenti_selezionati",
    "download_nuovi_documenti",
    "log_sincronizzazione",
)

SECURITY_RULES = {
    "scraping_html": False,
    "pin_salvato": False,
    "credenziali_cloud": False,
    "download_massivo_non_presidiato": False,
    "sessione_temporanea": True,
    "certificato_sul_pc_studio": True,
    "log_privacy": True,
}


def get_sigp_sync_policy() -> dict:
    """Restituisce la policy visibile in UI/API senza avviare alcun accesso esterno."""

    return {
        "nome": "Sincronizzazione fascicolo telematico",
        "canali": list(AUTHORIZED_CHANNELS),
        "funzioni": list(SYNC_FUNCTIONS),
        "sicurezza": dict(SECURITY_RULES),
        "note": (
            "IUSENTRA importa solo payload ottenuti tramite canali autorizzati "
            "PST/PdA/Model Office o tramite Local Connector sul PC dello studio. "
            "Non esegue scraping HTML e non conserva PIN o credenziali del portale."
        ),
    }
