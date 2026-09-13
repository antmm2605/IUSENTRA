"""Testi dei consensi del workflow di firma del Portale Cliente.

I testi sono versionati e vivono SOLO lato server: il client li mostra ma il
consenso registrato usa sempre la versione e il testo canonici di questo
modulo, mai stringhe inviate dal browser. Base normativa: CAD D.Lgs. 82/2005
artt. 20-21 (firma elettronica semplice con valore probatorio liberamente
valutabile, rafforzato dal pacchetto di evidenze) e GDPR 2016/679 artt. 6-7
(consenso esplicito e documentato).
"""

from __future__ import annotations

from typing import Any


CONSENT_VERSION = "2026-07"

IDENTITY_CONSENT_KEY = "acquisizione_documento_identita"
PREVENTIVO_CONSENT_KEY = "accettazione_preventivo"
CONFERIMENTO_CONSENT_KEY = "accettazione_conferimento"

IDENTITY_CONSENT_TEXT = (
    "Autorizzo lo studio ad acquisire e conservare copia del mio documento "
    "d'identità, caricato da me tramite file, fotocamera o webcam, al solo "
    "fine dell'identificazione richiesta dall'incarico professionale e degli "
    "adempimenti di legge (antiriciclaggio e deontologici)."
)

PREVENTIVO_CONSENT_TEXT = (
    "Dichiaro di aver letto integralmente il preventivo visualizzato e di "
    "accettarne espressamente contenuto, compensi, spese e condizioni."
)

CONFERIMENTO_CONSENT_TEXT = (
    "Dichiaro di aver letto integralmente la lettera di conferimento di "
    "incarico e di accettarne espressamente il contenuto, con consenso "
    "distinto e ulteriore rispetto all'accettazione del preventivo."
)

# Le quattro dichiarazioni obbligatorie prima dell'applicazione della firma.
SIGNING_CONSENTS: dict[str, str] = {
    "firma_lettura_documento": (
        "Dichiaro di aver letto integralmente il documento che sto per firmare."
    ),
    "firma_accettazione_contenuto": (
        "Accetto il contenuto del documento visualizzato."
    ),
    "firma_autorizzazione_applicazione": (
        "Autorizzo l'applicazione della mia firma elettronica/grafica al "
        "documento visualizzato. Sono consapevole che si tratta di una firma "
        "elettronica semplice con pacchetto di evidenze (artt. 20-21 CAD), "
        "non di una firma elettronica qualificata."
    ),
    "firma_conferma_dati": (
        "Confermo che i dati e i documenti da me inviati sono corretti e che "
        "il documento firmato sarà trasmesso allo studio."
    ),
}

SIGNING_CONSENT_KEYS: tuple[str, ...] = tuple(SIGNING_CONSENTS)

MANUAL_UPLOAD_DECLARATION = (
    "Dichiaro sotto la mia responsabilità che il file caricato è il documento "
    "ricevuto dallo studio, da me sottoscritto, e ne autorizzo la trasmissione "
    "allo studio."
)


def consent_texts_payload() -> dict[str, Any]:
    """Payload pubblico con i testi correnti dei consensi (per la UI)."""

    return {
        "version": CONSENT_VERSION,
        "identity": {"key": IDENTITY_CONSENT_KEY, "text": IDENTITY_CONSENT_TEXT},
        "preventivo": {"key": PREVENTIVO_CONSENT_KEY, "text": PREVENTIVO_CONSENT_TEXT},
        "conferimento": {"key": CONFERIMENTO_CONSENT_KEY, "text": CONFERIMENTO_CONSENT_TEXT},
        "signing": [
            {"key": key, "text": text} for key, text in SIGNING_CONSENTS.items()
        ],
        "manualUploadDeclaration": MANUAL_UPLOAD_DECLARATION,
    }


__all__ = [
    "CONSENT_VERSION",
    "IDENTITY_CONSENT_KEY",
    "PREVENTIVO_CONSENT_KEY",
    "CONFERIMENTO_CONSENT_KEY",
    "IDENTITY_CONSENT_TEXT",
    "PREVENTIVO_CONSENT_TEXT",
    "CONFERIMENTO_CONSENT_TEXT",
    "SIGNING_CONSENTS",
    "SIGNING_CONSENT_KEYS",
    "MANUAL_UPLOAD_DECLARATION",
    "consent_texts_payload",
]
