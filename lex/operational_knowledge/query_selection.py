"""Selezione consultiva deterministica; non esegue comandi o interrogazioni SQL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .query_dates import QueryDates, resolve_query_dates


@dataclass(frozen=True)
class QuerySelection:
    domain: str
    dates: QueryDates
    states: tuple[str, ...] = ()
    direction: str = ""
    folder: str = ""
    date_axis: str = ""
    error: str = ""
    kinds: tuple[str, ...] = ()


def is_plain_pec_query(question: str) -> bool:
    """Non scarta filtri di cliente, contenuto o allegati non ancora risolti.

    Questo percorso gestisce soltanto la selezione strutturata della casella;
    domande più articolate mantengono il proprio percorso governato.
    """
    text = question.casefold().replace("’", "'")
    words = re.findall(r"[^\W\d_]+", text, flags=re.UNICODE)
    allowed = set((
        "pec posta certificata casella studio ricevute ricevuti ricevuta ricevuto "
        "inviate inviati inviata inviato spedite spediti spedita spedito "
        "cestino in arrivo oggi ieri domani dopodomani avantieri altro l "
        "questa settimana gennaio febbraio marzo aprile maggio giugno luglio "
        "agosto settembre ottobre novembre dicembre "
        "mostra mostrami elenca cerca trova trovami dammi quali quale tutte tutti altre altri "
        "ho abbiamo hai avete sono state stati era erano è e ed nel nella nelle "
        "del dello della delle di da dal dalla al alla il lo la le i gli per "
        "mi puoi vorrei vedere visualizza controlla ricevuto inviato"
    ).split())
    return 'pec' in words and all(word in allowed for word in words)


def is_plain_notification_query(question: str) -> bool:
    """Accetta soltanto filtri supportati, senza perdere cliente o contenuto."""
    text = question.casefold().replace('’', "'")
    words = re.findall(r'[^\W\d_]+', text, flags=re.UNICODE)
    domain = {'notifiche', 'notificazioni'}
    if not domain.intersection(words):
        return False
    translated = re.sub(r'\b(?:notifiche|notificazioni)\b', 'pec', text)
    translated = re.sub(r'\b(?:accettate|accettata|notificare|preparare)\b', '', translated)
    translated = re.sub(r'\bfare\b', '', translated)
    return is_plain_pec_query(translated)


def is_plain_deposit_query(question: str) -> bool:
    """La pagina strutturata non elimina filtri di cliente o contenuto."""
    text = question.casefold().replace('’', "'")
    if not re.search(r'\bdeposit[oi]\b', text):
        return False
    if not re.search(r'\baccettat[io]\b', text) and ' '.join(text.split()) != 'mostra altri depositi':
        return False
    translated = re.sub(r'\bdeposit[oi]\b', 'pec', text)
    translated = re.sub(r'\b(?:accettat[io]|cancelleria|tribunale|gestore|rac|smtp)\b', '', translated)
    return is_plain_pec_query(translated)


def is_plain_receipt_query(question: str) -> bool:
    """Il richiamo generico ai fascicoli include il catalogo già consultato.

    Non elimina nomi, ruoli o richieste esclusive: il catalogo comprende
    documenti e PEC e non supporta ancora quei filtri nella pagina globale.
    """
    text = question.casefold().replace('’', "'")
    if not re.search(r'\bricevut[ae]\b', text) or not re.search(r'\b(?:accettazione|consegna|rac|rdac)\b', text):
        return False
    translated = re.sub(r'\b(?:accettazione|consegna|rac|rdac)\b', '', text)
    translated = re.sub(r'\b(?:anche\s+)?nei\s+fascicoli\b', '', translated)
    return is_plain_pec_query(translated + ' pec')


def is_plain_calendar_query(question: str) -> bool:
    text = question.casefold().replace('’', "'")
    words = set(re.findall(r'[^\W\d_]+', text, flags=re.UNICODE))
    calendar = {'agenda', 'appuntamenti', 'udienze', 'calendario', 'scadenziario', 'scadenze'}
    if not words.intersection(calendar):
        return False
    translated = re.sub(r'\b(?:agenda|appuntamenti|udienze|calendario|scadenziario|scadenze)\b', 'pec', text)
    translated = re.sub(r'\b(?:completat[aeio]|annullat[aeio]|rinviat[aeio]|programmat[aeio]|apert[aeio]|fare)\b', '', translated)
    return is_plain_pec_query(translated)


def has_scoped_query_context(metadata: dict) -> bool:
    active = metadata.get('active_context')
    active = active if isinstance(active, dict) else {}
    if any(metadata.get(key) or active.get(key) for key in (
        'fascicolo_id', 'cliente_id', 'case_id', 'client_id', 'linked_case_id', 'linked_client_id')):
        return True
    return any(re.search(r'/(?:fascicoli|clienti)/[^/?#]+', str(owner.get(key) or ''))
               for owner in (metadata, active) for key in ('page_path', 'pagePath'))


def resolve_query_selection(question: str, *, today: date) -> QuerySelection | None:
    """Distingue evento e dominio prima di interpretare data e stato.

    ACCETTATO_PEC non dimostra accettazione di cancelleria; la RAC di una
    notifica non è una notifica della campanella. Gli stati qui prodotti sono
    criteri di selezione, mai nuovi fatti da memorizzare.
    """
    text = " ".join(question.casefold().replace("’", "'").split())
    domains = []
    if is_plain_receipt_query(question):
        acceptance = bool(re.search(r'\b(?:accettazione|rac)\b', text))
        delivery = bool(re.search(r'\b(?:consegna|rdac)\b', text))
        selected = 'rac' if acceptance else 'rdac'
        return QuerySelection('archived_receipts', resolve_query_dates(question, today=today),
                              states=(selected,), date_axis='receipt_at',
                              error='Indica ricevute di accettazione oppure di consegna.' if acceptance and delivery else '')
    if re.search(r"\bdeposit[oi]\b", text):
        domains.append("deposits")
    if re.search(r"\bnotific(?:a|he|azioni)\b", text) and not re.search(
        r"\b(?:campanella|notifiche operative|notifiche dell'app)\b", text
    ):
        domains.append("legal_notifications")
    if re.search(r"\b(?:agenda|appuntamenti|udienze|calendario)\b", text):
        domains.append("agenda")
    if re.search(r"\b(?:scadenziario|scadenze|termini)\b", text):
        domains.append("deadlines")
    if not domains and re.search(r"\bpec\b", text):
        domains.append("pec")
    if not domains:
        return None
    dates = resolve_query_dates(question, today=today)
    if len(domains) != 1:
        return QuerySelection("multiple", dates, error="Seleziona un dominio alla volta per applicare data e stato senza ambiguità.")
    domain = domains[0]
    direction = ""
    folder = "trash" if re.search(r"\bcestino\b", text) else ""
    states: tuple[str, ...] = ()
    axis = {"pec": "message_at", "agenda": "appointment_at", "deadlines": "due_on"}.get(domain, "")
    error = dates.error
    if domain == "pec":
        sent = bool(re.search(r"\b(?:inviat[aeio]|spedit[aeio])\b", text))
        received = bool(re.search(r"\b(?:ricevut[aeio]|in arrivo)\b", text))
        if sent and received:
            error = error or "Indica PEC ricevute oppure inviate per distinguere la direzione."
        direction = "sent" if sent else "received" if received else ""
    elif domain == "deposits":
        if re.search(r"\baccettat[io]\b", text):
            if re.search(r"\b(?:smtp|gestore|rac|pec)\b", text):
                states, axis = ("ACCETTATO_PEC",), "pec_acceptance_at"
            else:
                states, axis = ("ACCETTATO_CANCELLERIA",), "registry_acceptance_at"
        elif re.search(r"\b(?:da fare|da depositare|da preparare)\b", text):
            states, axis = ("pending",), "due_on"
        else:
            axis = "deposit_at"
    elif domain == "legal_notifications":
        if re.search(r"\baccettat[ae]\b", text):
            states, axis = ("rac_received",), "rac_at"
        elif re.search(r"\b(?:da fare|da notificare|da preparare)\b", text):
            states, axis = ("pending",), "due_on"
        else:
            axis = "notification_at"
    else:
        tokens = ((r"completat[aeio]", "COMPLETATO"), (r"annullat[aeio]", "ANNULLATO"))
        for pattern, state in tokens:
            if re.search(rf"\b{pattern}\b", text):
                states += (state,)
        if domain == "agenda":
            if re.search(r"\brinviat[aeio]\b", text):
                states += ("RINVIATO",)
            if re.search(r"\bprogrammat[aeio]\b", text):
                states += ("PROGRAMMATO",)
        elif re.search(r"\b(?:apert[aeio]|da fare)\b", text):
            states += ("APERTO",)
    kinds = ('UDIENZA',) if domain == 'agenda' and re.search(r'\budienze\b', text) else ()
    return QuerySelection(domain, dates, states, direction, folder, axis, error, kinds)
