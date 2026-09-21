"""I lettori censiti dal registro, con etichetta italiana e versione.

La versione di un lettore cambia quando cambia il modo in cui legge davvero
il contenuto. Se una versione nuova è compatibile con letture già eseguite,
il registro non deve riaprire tutti i fascicoli: il ciclo resta fermo e si
riattiva solo su documento o PEC nuovi/cambiati. Le versioni si risolvono
pigramente per non importare i motori dal registro.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# `livello`: «oggetto» se il lettore legge documento per documento e registra ogni
# lettura; «fascicolo» se legge il fascicolo nel suo insieme e registra solo
# l'impronta dell'inventario che ha esaminato. `tipi`: gli oggetti che legge.
LETTORI: dict[str, dict[str, Any]] = {
    "ocr": {
        "etichetta": "Testo e ricerca",
        "descrizione": "Riconoscimento del testo e indice di ricerca a testo pieno",
        "livello": "oggetto",
        "tipi": ("documento",),
    },
    "indice_documentale": {
        "etichetta": "Indice documentale",
        "descrizione": "Testo estratto per Lex, catalogo e presidi",
        "livello": "oggetto",
        "tipi": ("documento",),
    },
    "catalogo": {
        "etichetta": "Catalogo dal contenuto",
        "descrizione": "Natura, sezione e ruolo di deposito di ogni documento",
        "livello": "oggetto",
        "tipi": ("documento",),
    },
    "rag_locale": {
        "etichetta": "Assistente locale",
        "descrizione": "Indicizzazione per l'AI locale del fascicolo",
        "livello": "oggetto",
        "tipi": ("documento",),
    },
    "presidio_pec": {
        "etichetta": "Presidio PEC",
        "descrizione": "Allegati PEC letti dal presidio audit-grade",
        "livello": "oggetto",
        "tipi": ("allegato_pec",),
    },
    "presidio_economico": {
        "etichetta": "Presidio economico",
        "descrizione": "Contributo unificato, liquidazioni e prove economiche nei documenti",
        "livello": "fascicolo",
        "tipi": ("documento",),
    },
    "proforma_automatica": {
        "etichetta": "Proforma automatica",
        "descrizione": "Sentenze e importi letti per proporre la parcella proforma",
        "livello": "fascicolo",
        "tipi": ("documento",),
    },
    "motore_documenti": {
        "etichetta": "Motore documenti (archivio)",
        "descrizione": "Date, ruoli e prove di notifica letti dai documenti e collaudati per l'archivio",
        "livello": "oggetto",
        "tipi": ("documento",),
    },
    "motore_pec": {
        "etichetta": "Motore PEC (archivio)",
        "descrizione": "Udienze, termini, ricevute ed eventi dei messaggi PEC e dei loro allegati per l'archivio",
        "livello": "oggetto",
        "tipi": ("pec", "allegato_pec"),
    },
}


def _versione_ocr() -> str:
    from legal_ocr.formulario import VERSIONE_FORMULARIO
    from legal_ocr.motore import VERSIONE_MOTORE

    return f"{VERSIONE_MOTORE}+{VERSIONE_FORMULARIO}"


def _versione_indice_documentale() -> str:
    from pct.document_intelligence.pdf_inspector_engine import ENGINE_VERSION

    return str(ENGINE_VERSION)


def _versione_catalogo() -> str:
    from pct.document_intelligence.catalog_resolver import RESOLVER_VERSION

    return str(RESOLVER_VERSION)


def _versione_presidio_pec() -> str:
    from pct.pec_pipeline import PEC_ATTACHMENT_EXTRACTION_VERSION

    return str(PEC_ATTACHMENT_EXTRACTION_VERSION)


def _versione_motore_documenti() -> str:
    from pct.archivio_letture import VERSIONE_MOTORE_DOCUMENTI

    return str(VERSIONE_MOTORE_DOCUMENTI)


def _versioni_compatibili_motore_documenti() -> tuple[str, ...]:
    from pct.archivio_letture.motore_documenti import VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI

    return tuple(str(v or "") for v in VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI if str(v or ""))


def _versione_motore_pec() -> str:
    from pct.archivio_letture import VERSIONE_MOTORE_PEC

    return str(VERSIONE_MOTORE_PEC)


def _versione_presidio_economico() -> str:
    from web.services.react_fascicoli_bridge import ECONOMIC_DOCUMENT_ANALYSIS_VERSION

    return str(ECONOMIC_DOCUMENT_ANALYSIS_VERSION)


_VERSIONI: dict[str, Callable[[], str]] = {
    "ocr": _versione_ocr,
    "indice_documentale": _versione_indice_documentale,
    "catalogo": _versione_catalogo,
    "rag_locale": lambda: "rag-locale.v2.sql-pagine",
    "presidio_pec": _versione_presidio_pec,
    "presidio_economico": _versione_presidio_economico,
    "proforma_automatica": _versione_presidio_economico,
    "motore_documenti": _versione_motore_documenti,
    "motore_pec": _versione_motore_pec,
}


_VERSIONI_COMPATIBILI: dict[str, Callable[[], tuple[str, ...]]] = {
    "motore_documenti": _versioni_compatibili_motore_documenti,
}


def versione_lettore(lettore: str) -> str:
    """La versione corrente del lettore; stringa vuota se il lettore non è censito."""
    risolutore = _VERSIONI.get(str(lettore or ""))
    if risolutore is None:
        return ""
    try:
        return str(risolutore() or "")
    except Exception:
        return "sconosciuta"


def versioni_compatibili_lettore(lettore: str, versione_corrente: str | None = None) -> tuple[str, ...]:
    """Versioni che non impongono una rilettura massiva del contenuto."""
    corrente = str(versione_corrente if versione_corrente is not None else versione_lettore(lettore) or "")
    compatibili = {corrente} if corrente else set()
    risolutore = _VERSIONI_COMPATIBILI.get(str(lettore or ""))
    if risolutore is not None:
        try:
            compatibili.update(str(v or "") for v in risolutore() if str(v or ""))
        except Exception:
            pass
    return tuple(sorted(compatibili))


def versione_compatibile_lettore(lettore: str, versione_registrata: str, versione_corrente: str | None = None) -> bool:
    versione = str(versione_registrata or "")
    return bool(versione and versione in set(versioni_compatibili_lettore(lettore, versione_corrente)))


def livello_lettore(lettore: str) -> str:
    voce = LETTORI.get(str(lettore or ""))
    return str(voce.get("livello") or "oggetto") if voce else "oggetto"


def tipi_lettore(lettore: str) -> tuple[str, ...]:
    voce = LETTORI.get(str(lettore or ""))
    return tuple(voce.get("tipi") or ()) if voce else ()


def etichetta_lettore(lettore: str) -> str:
    voce = LETTORI.get(str(lettore or ""))
    return voce["etichetta"] if voce else str(lettore or "")


__all__ = [
    "LETTORI", "etichetta_lettore", "livello_lettore", "tipi_lettore",
    "versione_compatibile_lettore", "versione_lettore", "versioni_compatibili_lettore",
]
