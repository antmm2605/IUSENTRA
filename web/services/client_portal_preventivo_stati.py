"""Stati del preventivo ammessi dal Portale Cliente — unica fonte di verità.

Il preventivo è un atto dello studio che diventa opponibile al cliente solo
quando gli viene effettivamente trasmesso: fino a quel momento resta materiale
interno. Questo modulo tiene insieme, in un punto solo, quali stati di
``pct.preventivi.StatoPreventivo`` valgono per ciascun passaggio del percorso
«preventivo → conferimento incarico → firma», così che la pagina dello studio
(``react_client_portal_bridge``) e la mini app del cliente
(``client_portal_signing_bridge``) non possano divergere.

Base normativa del percorso: D.M. 55/2014 e D.M. 147/2022 (compensi forensi),
art. 13 L. 247/2012 e art. 9 D.L. 1/2012 conv. L. 27/2012 (obbligo di rendere
noto al cliente il compenso prevedibile in forma scritta), art. 25-bis CDF
(equo compenso). Il conferimento dell'incarico presuppone un preventivo già
comunicato e accettato: per questo il cliente vede solo i preventivi trasmessi.
"""

from __future__ import annotations

from pct.preventivi import StatoPreventivo


#: Preventivi che il cliente può vedere nel proprio portale: quelli che lo
#: studio gli ha già trasmesso, più quelli che ha accettato o convertito.
STATI_PORTALE = {
    StatoPreventivo.INVIATO,
    StatoPreventivo.APERTO,
    StatoPreventivo.ACCETTATO,
    StatoPreventivo.CONVERTITO,
}

#: Preventivi su cui il cliente può ancora esprimersi (accetta / rifiuta).
STATI_ACCETTABILI = {StatoPreventivo.INVIATO, StatoPreventivo.APERTO}

#: Preventivi già accettati: da qui nasce il conferimento dell'incarico.
STATI_ACCETTATI = {StatoPreventivo.ACCETTATO, StatoPreventivo.CONVERTITO}

#: Preventivi con il documento già prodotto ma non ancora comunicati al
#: cliente. Sono proponibili dalla pagina dello studio: mandarli alla firma
#: significa trasmetterli, quindi il passaggio a ``INVIATO`` è parte dell'invio.
STATI_DA_TRASMETTERE = {StatoPreventivo.GENERATO, StatoPreventivo.VERIFICATO}

#: Tutto ciò che lo studio può scegliere di mandare alla firma del cliente.
#: ``BOZZA`` e ``IN_CALCOLO`` restano fuori: il documento non esiste ancora.
STATI_PROPONIBILI = STATI_DA_TRASMETTERE | STATI_ACCETTABILI


def stato_di(preventivo) -> str:
    """Stato del preventivo come testo, qualunque sia la forma sul record."""

    stato = getattr(preventivo, "stato", "")
    return str(getattr(stato, "value", stato) or "").strip()


def e_proponibile(preventivo) -> bool:
    """Vero se lo studio può mandare questo preventivo alla firma del cliente."""

    return stato_di(preventivo) in {stato.value for stato in STATI_PROPONIBILI}


def richiede_trasmissione(preventivo) -> bool:
    """Vero se il preventivo va portato a ``INVIATO`` prima di mostrarlo."""

    return stato_di(preventivo) in {stato.value for stato in STATI_DA_TRASMETTERE}
