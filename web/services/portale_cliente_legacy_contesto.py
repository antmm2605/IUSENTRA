"""Accesso al portale del cliente con link personale (`/portale/<token>`).

Unica verifica del token per le pagine storiche, la shell React e le API JSON:
studio del link, token valido e attivo (altrimenti 410), cliente esistente
(altrimenti 404), permessi della scheda portale (altrimenti 403), registrazione
dell'accesso.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import current_app, request

from web.services.tenant_paths import tenant_data_path
from web.services.token_pubblici_tenant import contesto_studio_mancante, risolvi_studio_da_token

# Impronta del token -> studio (vedi token_pubblici_tenant).
_STUDIO_DEL_TOKEN: dict[str, str] = {}

MESSAGGIO_LINK_SCADUTO = (
    "Questo link di accesso al portale è scaduto o è stato revocato. "
    "Contatta il tuo avvocato per ricevere un nuovo link di accesso."
)
MESSAGGIO_NEGATO = "Sezione non disponibile per questo accesso."


class AccessoPortaleNegato(Exception):
    """Accesso rifiutato con lo stato HTTP da restituire (403, 404, 410)."""

    def __init__(self, status: int, codice: str, messaggio: str):
        super().__init__(messaggio)
        self.status = status
        self.codice = codice
        self.messaggio = messaggio


@dataclass
class ContestoPortale:
    gestore: Any
    portale: Any
    cliente: Any


def gestore_portale():
    from pct.portale import GestionePortale

    return GestionePortale(
        db_path=tenant_data_path("PORTALE_DB", "./portale/portali.json"),
        uploads_dir=tenant_data_path("PORTALE_UPLOADS", "./portale/uploads"),
    )


def _token_nello_studio(token: str):
    def verifica(_studio, percorsi: dict[str, str]) -> bool:
        from pct.portale import GestionePortale

        gestore = GestionePortale(db_path=percorsi["PORTALE_DB"], uploads_dir=percorsi.get("PORTALE_UPLOADS", ""))
        return gestore.verifica_token(token) is not None

    return verifica


def risolvi_studio_portale(token: str) -> None:
    """Imposta lo studio che ha creato il link (installazioni con più studi)."""
    risolvi_studio_da_token(token, verifica=_token_nello_studio(token), cache=_STUDIO_DEL_TOKEN, etichetta="Portale")


def verifica_contesto(token: str, *, registra_accesso: bool = True) -> ContestoPortale:
    """Token valido e cliente esistente; registra l'accesso come le pagine storiche."""
    if contesto_studio_mancante():
        # Con più studi, un link di cui non si trova lo studio non legge l'archivio comune.
        raise AccessoPortaleNegato(410, "link_non_valido", MESSAGGIO_LINK_SCADUTO)
    gestore = gestore_portale()
    portale = gestore.verifica_token(token)
    if not portale:
        raise AccessoPortaleNegato(410, "link_non_valido", MESSAGGIO_LINK_SCADUTO)
    from web.helpers import get_clienti

    cliente = get_clienti().get(portale.id_cliente)
    if not cliente:
        raise AccessoPortaleNegato(404, "cliente_non_trovato", "Scheda cliente non disponibile.")
    if registra_accesso:
        gestore.registra_accesso(portale.id, request.remote_addr or "")
    return ContestoPortale(gestore=gestore, portale=portale, cliente=cliente)


def permesso(contesto: ContestoPortale, nome: str, predefinito: bool = False) -> bool:
    return bool(getattr(contesto.portale.permessi, nome, predefinito))


def richiedi_permessi(contesto: ContestoPortale, *requisiti: tuple[str, bool]) -> None:
    """Ogni requisito è (nome permesso, valore predefinito se assente)."""
    for nome, predefinito in requisiti:
        if not permesso(contesto, nome, predefinito):
            raise AccessoPortaleNegato(403, "permesso_negato", MESSAGGIO_NEGATO)


def fascicoli_cliente(id_cliente: str) -> list[Any]:
    from web.helpers import get_fascicoli

    try:
        return [f for f in get_fascicoli().tutti() if f.id_cliente == id_cliente]
    except Exception:
        return []


def fascicoli_visibili(contesto: ContestoPortale) -> list[Any]:
    """Pratiche del cliente del link, solo se il portale le mostra."""
    if not permesso(contesto, "vedi_fascicoli"):
        return []
    return fascicoli_cliente(contesto.cliente.id)


def studio_nome() -> str:
    return str(current_app.config.get("STUDIO_NOME", "IUSENTRA"))


# Requisiti delle sezioni: una sola tabella per pagine storiche, shell e API.
REQUISITI_SEZIONE: dict[str, tuple[tuple[str, bool], ...]] = {
    "home": (),
    "privacy": (("firma_privacy", False),),
    "documenti": (("carica_documenti", False),),
    "economici": (("vedi_economici", False),),
    "anagrafica": (("vedi_anagrafica", False),),
}


__all__ = [
    "AccessoPortaleNegato",
    "ContestoPortale",
    "MESSAGGIO_LINK_SCADUTO",
    "MESSAGGIO_NEGATO",
    "REQUISITI_SEZIONE",
    "fascicoli_cliente",
    "fascicoli_visibili",
    "gestore_portale",
    "permesso",
    "richiedi_permessi",
    "risolvi_studio_portale",
    "studio_nome",
    "verifica_contesto",
]
