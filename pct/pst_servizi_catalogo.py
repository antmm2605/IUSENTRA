"""Catalogo dei servizi PST rilevanti per il fascicolo telematico.

Questo modulo tiene allineata la classificazione interna di HACS con la
documentazione ufficiale del Portale dei Servizi Telematici, senza
hardcodare la logica direttamente nelle viste.
"""

from __future__ import annotations

SEZIONE_PROFILO = "profilo"
SEZIONE_ATTIVITA_PROCESSUALI = "attivita_processuali"
SEZIONE_DOCUMENTI_FASCICOLO = "documenti_fascicolo"
SEZIONE_UDIENZE_SCADENZE = "udienze_scadenze"
SEZIONE_COMUNICAZIONI_CANCELLERIA = "comunicazioni_cancelleria"
SEZIONE_ISTANZE = "istanze"

SERVIZIO_PST_PROFILO_FASCICOLO = "ProfiloFascicolo"
SERVIZIO_PST_DOCUMENTI_FASCICOLO = "DocumentiFascicolo"
SERVIZIO_PST_RICERCA_SCADENZE = "RicercaScadenze"
SERVIZIO_PST_COMUNICAZIONE_CANCELLERIA = "ComunicazioneCancelleria"
SERVIZIO_PST_DETTAGLIO_COMUNICAZIONE = "DettaglioComunicazione"
SERVIZIO_PST_NOTIFICHE_DA_RITIRARE = "NotificheDaRitirare"
SERVIZIO_PST_DETTAGLIO_ISTANZE = "DettaglioIstanze"

PST_DOCUMENTAZIONE_PAGINA_URL = "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4571"
PST_DOCUMENTAZIONE_SERVIZI_WEB_URL = (
    "https://pst.giustizia.it/PST/resources/cms/documents/Documentazione_servizi_web_v1.69.pdf"
)

PST_SERVIZI_FASCICOLO = {
    SERVIZIO_PST_PROFILO_FASCICOLO: {
        "sezione": SEZIONE_PROFILO,
        "label": "Profilo fascicolo",
        "note": "Anagrafica e contesto della pratica.",
    },
    SERVIZIO_PST_DOCUMENTI_FASCICOLO: {
        "sezione": SEZIONE_DOCUMENTI_FASCICOLO,
        "label": "Documenti fascicolo",
        "note": "Elenco e metadati dei documenti del fascicolo telematico.",
    },
    SERVIZIO_PST_RICERCA_SCADENZE: {
        "sezione": SEZIONE_UDIENZE_SCADENZE,
        "label": "Udienze e scadenze",
        "note": "Scadenze e adempimenti del fascicolo.",
    },
    SERVIZIO_PST_COMUNICAZIONE_CANCELLERIA: {
        "sezione": SEZIONE_COMUNICAZIONI_CANCELLERIA,
        "label": "Comunicazioni di cancelleria",
        "note": "Messaggi e comunicazioni provenienti dalla cancelleria.",
    },
    SERVIZIO_PST_DETTAGLIO_COMUNICAZIONE: {
        "sezione": SEZIONE_COMUNICAZIONI_CANCELLERIA,
        "label": "Dettaglio comunicazione",
        "note": "Dettagli delle comunicazioni di cancelleria.",
    },
    SERVIZIO_PST_NOTIFICHE_DA_RITIRARE: {
        "sezione": SEZIONE_COMUNICAZIONI_CANCELLERIA,
        "label": "Notifiche da ritirare",
        "note": "Notifiche e comunicazioni da prendere in carico.",
    },
    SERVIZIO_PST_DETTAGLIO_ISTANZE: {
        "sezione": SEZIONE_ISTANZE,
        "label": "Istanze",
        "note": "Istanze e relativi esiti presenti sul portale.",
    },
}


def info_servizio_pst(nome_servizio: str) -> dict:
    """Restituisce il catalogo di un servizio PST noto."""
    return dict(PST_SERVIZI_FASCICOLO.get((nome_servizio or "").strip(), {}))


def sezione_fascicolo_da_servizio_pst(nome_servizio: str) -> str:
    """Mappa il nome del servizio PST alla sezione fascicolo HACS."""
    info = info_servizio_pst(nome_servizio)
    return str(info.get("sezione") or "")


def fonti_catalogo_servizi_pst() -> list[dict]:
    """Riferimenti ufficiali da conservare per aggiornamenti futuri."""
    return [
        {
            "titolo": "PST - pagina documentazione ufficiale",
            "url": PST_DOCUMENTAZIONE_PAGINA_URL,
        },
        {
            "titolo": "PST - dettaglio documentazione servizi web v1.69",
            "url": PST_DOCUMENTAZIONE_SERVIZI_WEB_URL,
        },
        {
            "titolo": "PST - documentazione servizi web software house v1.69",
            "url": PST_DOCUMENTAZIONE_SERVIZI_WEB_URL,
        },
        {
            "titolo": "PST - catalogo WSDL ufficiale A1 v1.52b",
            "url": PST_DOCUMENTAZIONE_PAGINA_URL,
        },
    ]
