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
# `su_richiesta`: il lettore non deve leggere ogni oggetto, ma solo quelli che gli servono quando serve
# (scadenze dai PDF: all'anteprima dello Scadenziario; proforma: fascicoli definiti senza parcella). Un oggetto
# che non ha mai toccato non è «da leggere»; lo è solo ciò che ha letto con un'impronta ora cambiata.
# Collaudo del 03/11/2026: non sono più censiti «Presidio PEC» (gli stessi allegati li legge il motore PEC
# dell'archivio; nessuno scriveva più il lettore dal 16/09) e «Sentenza e preparazione archivio» (lo stesso
# lavoro lo fa «Sentenza e definizione», sentenza_proposte_runtime; nessuno lo scriveva dall'08/10).
LETTORI: dict[str, dict[str, Any]] = {
    "proposta_definizione": {
        "etichetta": "Sentenza e definizione",
        "descrizione": "Definizione del fascicolo e credito delle spese dalla sentenza che decide la causa, nei documenti e negli allegati PEC: automatici solo se certi, altrimenti da confermare dall'avvocato",
        "livello": "oggetto",
        "tipi": ("documento", "allegato_pec"),
    },
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
        "su_richiesta": True,
    },
    "motore_documenti": {
        "etichetta": "Motore documenti (archivio)",
        "descrizione": "Date, ruoli e prove di notifica letti dai documenti e collaudati per l'archivio",
        "livello": "oggetto",
        "tipi": ("documento",),
    },
    "scadenze_pdf": {
        "etichetta": "Scadenze dai PDF",
        "descrizione": "Udienze e termini letti nei PDF per la proposta allo scadenziario",
        "livello": "oggetto",
        "tipi": ("documento",),
        "su_richiesta": True,
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


def _versione_motore_documenti() -> str:
    from pct.archivio_letture import VERSIONE_MOTORE_DOCUMENTI

    return str(VERSIONE_MOTORE_DOCUMENTI)


def _versioni_compatibili_motore_documenti() -> tuple[str, ...]:
    from pct.archivio_letture.motore_documenti import VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI

    return tuple(str(v or "") for v in VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI if str(v or ""))


def _versione_motore_pec() -> str:
    from pct.archivio_letture import VERSIONE_MOTORE_PEC

    return str(VERSIONE_MOTORE_PEC)


def _versioni_compatibili_motore_pec() -> tuple[str, ...]:
    from pct.archivio_letture.estrazione_importi import VERSIONE_ESTRAZIONE_IMPORTI, VERSIONE_ESTRAZIONE_IMPORTI_PRE_DISTINZIONE

    current = _versione_motore_pec()
    return (current, current.replace(VERSIONE_ESTRAZIONE_IMPORTI, VERSIONE_ESTRAZIONE_IMPORTI_PRE_DISTINZIONE))


def _versione_presidio_economico() -> str:
    from web.services.react_fascicoli_bridge import ECONOMIC_DOCUMENT_ANALYSIS_VERSION

    return str(ECONOMIC_DOCUMENT_ANALYSIS_VERSION)


_VERSIONI: dict[str, Callable[[], str]] = {
    "proposta_definizione": lambda: __import__("pct.fascicolo_sentenza_archiviazione", fromlist=["VERSIONE_PROPOSTA"]).VERSIONE_PROPOSTA,
    "ocr": _versione_ocr,
    "indice_documentale": _versione_indice_documentale,
    "catalogo": _versione_catalogo,
    "rag_locale": lambda: "rag-locale.v3.sql-riscontri",
    "presidio_economico": _versione_presidio_economico,
    "proforma_automatica": _versione_presidio_economico,
    "motore_documenti": _versione_motore_documenti,
    "motore_pec": _versione_motore_pec,
    "scadenze_pdf": lambda: "scadenze-pdf.v1",
}


_VERSIONI_COMPATIBILI: dict[str, Callable[[], tuple[str, ...]]] = {
    "motore_pec": _versioni_compatibili_motore_pec,
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


def su_richiesta_lettore(lettore: str) -> bool:
    """Vero se il lettore lavora solo quando serve (non ogni oggetto è suo da leggere)."""
    voce = LETTORI.get(str(lettore or ""))
    return bool(voce and voce.get("su_richiesta"))


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
    "LETTORI", "etichetta_lettore", "livello_lettore", "su_richiesta_lettore", "tipi_lettore",
    "versione_compatibile_lettore", "versione_lettore", "versioni_compatibili_lettore",
]
