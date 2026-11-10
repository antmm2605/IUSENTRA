"""Vista «Gazzetta Ufficiale»: filtri della richiesta, pagina di atti, conteggi e stato delle serie.

L'archivio (`pct/gazzetta/`) è scritto dal lavoro pianificato o dal pulsante «Aggiorna ora»; l'apertura della
pagina e della Panoramica legge soltanto, con filtri e paginazione in SQL.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import threading
from typing import Any, Mapping

from pct.gazzetta import tipi
from pct.gazzetta.archivio import ORDINAMENTI, ArchivioGazzetta, Filtri
from pct.gazzetta.pianificazione import percorso_archivio
from pct.gazzetta.serie import PER_CODICE, SERIE, SERIE_PRINCIPALI

PER_PAGINA = 25
PER_PAGINA_MASSIMO = 100
ULTIME_IN_PANORAMICA = 5
INTERVALLO_MINIMO_AGGIORNAMENTO = timedelta(minutes=5)
TEMPO_MASSIMO_AGGIORNAMENTO = 45  # secondi: il pulsante non deve tenere occupato il processo web
_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AGGIORNAMENTO_IN_CORSO = threading.Lock()

MESSAGGIO_ARCHIVIO_ASSENTE = (
    "L'archivio della Gazzetta Ufficiale non è ancora stato creato: la prima lettura dei sommari ufficiali "
    "parte con il lavoro pianificato (ogni ora) oppure subito con «Aggiorna ora»."
)


def archivio_in_lettura(config: Mapping[str, Any]) -> ArchivioGazzetta | None:
    return ArchivioGazzetta.in_lettura(percorso_archivio(config))


def _testo(argomenti: Mapping[str, Any], nome: str, limite: int = 120) -> str:
    return " ".join(str(argomenti.get(nome) or "").split())[:limite]


def _elenco(argomenti: Mapping[str, Any], nome: str, ammessi: Mapping[str, Any]) -> tuple[str, ...]:
    valori = [v.strip() for v in _testo(argomenti, nome, 400).split(",")]
    return tuple(dict.fromkeys(v for v in valori if v in ammessi))


def _data(argomenti: Mapping[str, Any], nome: str) -> str:
    valore = _testo(argomenti, nome, 10)
    if not _DATA_ISO.match(valore):
        return ""
    try:
        datetime.strptime(valore, "%Y-%m-%d")
    except ValueError:
        return ""
    return valore


def _intero(valore: Any, predefinito: int) -> int:
    try:
        return int(valore)
    except (TypeError, ValueError):
        return predefinito


def filtri_richiesti(argomenti: Mapping[str, Any]) -> Filtri:
    numero = _testo(argomenti, "numero", 6)
    ordine = _testo(argomenti, "ordine", 20)
    dal, al = _data(argomenti, "dal"), _data(argomenti, "al")
    if dal and al and dal > al:
        dal, al = al, dal
    return Filtri(
        q=_testo(argomenti, "q"),
        serie=_elenco(argomenti, "serie", PER_CODICE),
        tipo=_elenco(argomenti, "tipo", tipi.ETICHETTE),
        rubrica=_testo(argomenti, "rubrica", 200),
        emittente=_testo(argomenti, "ente", 300),
        dal=dal,
        al=al,
        numero_gu=str(int(numero)) if numero.isdigit() else "",
        ordine=ordine if ordine in ORDINAMENTI else "recenti",
        pagina=max(1, _intero(argomenti.get("pagina"), 1)),
        per_pagina=min(PER_PAGINA_MASSIMO, max(5, _intero(argomenti.get("per_pagina"), PER_PAGINA))),
    )


def voce(atto: Mapping[str, Any]) -> dict[str, Any]:
    serie = PER_CODICE.get(str(atto.get("serie") or ""))
    intestazione = str(atto.get("intestazione") or "")
    descrizione = str(atto.get("descrizione") or "")
    return {
        "id": atto["id"],
        "series": atto["serie"],
        "seriesLabel": serie.etichetta if serie else atto["serie"],
        "seriesShort": serie.nome_breve if serie else atto["serie"],
        "issueNumber": atto["numero_gu"],
        "issueDate": atto["data_gu"],
        "issueUrl": atto["url_sommario"],
        "heading": intestazione,
        "title": intestazione or descrizione,
        "description": descrizione if intestazione else "",
        "authority": atto.get("emittente") or "",
        "section": atto.get("rubrica") or "",
        "kind": atto["tipo"],
        "kindLabel": tipi.ETICHETTE.get(atto["tipo"], tipi.ETICHETTE["altro"]),
        "actNumber": atto.get("numero_atto") or "",
        "actDate": atto.get("data_atto") or "",
        "editorialCode": atto.get("codice_redazionale") or "",
        "page": atto.get("pagina") or "",
        "officialUrl": atto["url"],
    }


def stato_delle_serie(archivio: ArchivioGazzetta | None) -> list[dict[str, Any]]:
    stati = archivio.stato_serie() if archivio is not None else {}
    righe: list[dict[str, Any]] = []
    for serie in SERIE:
        stato = stati.get(serie.codice) or {}
        ultimo = stato.get("ultimo_fascicolo") or {}
        righe.append({
            "id": serie.codice,
            "label": serie.etichetta,
            "url": serie.url_elenco,
            "checked": bool(stato.get("ultimo_tentativo")),
            "ok": bool(stato.get("ultimo_esito_ok")),
            "lastAttemptAt": str(stato.get("ultimo_tentativo") or ""),
            "lastSuccessAt": str(stato.get("ultimo_successo") or ""),
            "message": str(stato.get("messaggio") or ""),
            "count": int(stato.get("atti") or 0),
            "latestIssue": {
                "number": str(ultimo.get("numero") or ""),
                "date": str(ultimo.get("data") or ""),
                "url": str(ultimo.get("url_sommario") or ""),
            } if ultimo else None,
        })
    return righe


def _faccette(risultato: Mapping[str, Any], filtri: Filtri, enti: list[tuple[str, int]]) -> dict[str, Any]:
    conteggi = risultato["conteggi"]
    serie = [{"id": s.codice, "label": s.nome_breve, "count": conteggi["serie"].get(s.codice, 0)} for s in SERIE]
    tipi_presenti = [
        {"id": chiave, "label": etichetta, "count": conteggi["tipo"].get(chiave, 0)}
        for chiave, etichetta in tipi.ETICHETTE.items()
        if conteggi["tipo"].get(chiave) or chiave in filtri.tipo
    ]
    rubriche = [
        {"id": nome, "label": nome, "count": numero}
        for nome, numero in sorted(conteggi["rubrica"].items(), key=lambda voce: (-voce[1], voce[0]))
        if nome
    ]
    return {
        "series": serie,
        "kinds": tipi_presenti,
        "sections": rubriche,
        "authorities": [{"id": nome, "label": nome, "count": numero} for nome, numero in enti],
    }


def _vuota(filtri: Filtri, messaggio: str) -> dict[str, Any]:
    return {
        "ok": True,
        "archiveMissing": True,
        "message": messaggio,
        "items": [],
        "total": 0,
        "page": 1,
        "pageSize": filtri.per_pagina,
        "hasMore": False,
        "facets": {
            "series": [{"id": s.codice, "label": s.nome_breve, "count": 0} for s in SERIE],
            "kinds": [], "sections": [], "authorities": [],
        },
        "sourceStates": stato_delle_serie(None),
        "archive": {"from": "", "to": "", "total": 0},
        "kindsCatalog": [{"id": k, "label": v} for k, v in tipi.ETICHETTE.items()],
    }


def costruisci_vista(archivio: ArchivioGazzetta | None, filtri: Filtri) -> dict[str, Any]:
    if archivio is None:
        return _vuota(filtri, MESSAGGIO_ARCHIVIO_ASSENTE)
    risultato = archivio.cerca(filtri)
    inizio = (filtri.pagina - 1) * filtri.per_pagina
    return {
        "ok": True,
        "archiveMissing": False,
        "message": "",
        "items": [voce(atto) for atto in risultato["atti"]],
        "total": risultato["totale"],
        "page": filtri.pagina,
        "pageSize": filtri.per_pagina,
        "hasMore": inizio + filtri.per_pagina < risultato["totale"],
        "facets": _faccette(risultato, filtri, archivio.enti(filtri)),
        "sourceStates": stato_delle_serie(archivio),
        "archive": {"from": risultato["dal"], "to": risultato["al"], "total": risultato["in_archivio"]},
        "kindsCatalog": [{"id": k, "label": v} for k, v in tipi.ETICHETTE.items()],
    }


def ultime_pubblicazioni(archivio: ArchivioGazzetta | None, quante: int = ULTIME_IN_PANORAMICA) -> dict[str, Any]:
    """Le ultime pubblicazioni della Serie generale e della 1ª Serie speciale, nell'ordine del sommario."""
    stati = stato_delle_serie(archivio)
    if archivio is None:
        return {"ok": True, "archiveMissing": True, "message": MESSAGGIO_ARCHIVIO_ASSENTE, "items": [], "sourceStates": stati}
    risultato = archivio.cerca(Filtri(serie=SERIE_PRINCIPALI, per_pagina=quante))
    return {
        "ok": True,
        "archiveMissing": False,
        "message": "",
        "items": [voce(atto) for atto in risultato["atti"]],
        "sourceStates": stati,
    }


def _istante(valore: str) -> datetime | None:
    try:
        istante = datetime.fromisoformat(str(valore or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return istante if istante.tzinfo else istante.replace(tzinfo=timezone.utc)


def aggiorna_ora(config: Mapping[str, Any], *, adesso: datetime | None = None, esegui=None) -> dict[str, Any]:
    """Pulsante «Aggiorna ora»: un giro alla volta e non più spesso di ogni 5 minuti, con tempo limitato."""
    from pct.gazzetta.pianificazione import esegui_da_pianificazione

    adesso = adesso or datetime.now(timezone.utc)
    if not _AGGIORNAMENTO_IN_CORSO.acquire(blocking=False):
        return {"eseguito": False, "motivo": "Un aggiornamento della Gazzetta Ufficiale è già in corso."}
    try:
        archivio = archivio_in_lettura(config)
        ultimi = [s["lastAttemptAt"] for s in stato_delle_serie(archivio) if s["lastAttemptAt"]]
        ultimo = max((_istante(v) for v in ultimi if _istante(v)), default=None)
        if ultimo is not None and adesso - ultimo < INTERVALLO_MINIMO_AGGIORNAMENTO:
            return {"eseguito": False, "motivo": "Le serie sono state controllate da meno di 5 minuti."}
        esito = (esegui or esegui_da_pianificazione)(config, tempo_massimo=TEMPO_MASSIMO_AGGIORNAMENTO)
        return {"eseguito": True, "esito": esito}
    finally:
        _AGGIORNAMENTO_IN_CORSO.release()


__all__ = [
    "MESSAGGIO_ARCHIVIO_ASSENTE", "aggiorna_ora", "archivio_in_lettura", "costruisci_vista", "filtri_richiesti",
    "stato_delle_serie", "ultime_pubblicazioni", "voce",
]
