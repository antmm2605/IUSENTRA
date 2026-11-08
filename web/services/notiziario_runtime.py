"""Vista «Notizie utili» dall'archivio condiviso: filtri, pagine leggere e fascicoli pertinenti.

L'archivio è scritto solo dal lavoro pianificato (o dal pulsante «Aggiorna»):
l'apertura della pagina legge, filtra e impagina, senza traffico verso le fonti.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any, Iterable, Mapping

from pct.notiziario.archivio import ArchivioNotiziario
from pct.notiziario.fonti import ETICHETTE_TIPO, FONTI, PER_ID
from pct.notiziario.pertinenza import IndicePertinenza, costruisci_indice, fascicoli_pertinenti
from pct.notiziario.pianificazione import percorso_archivio

PER_PAGINA = 25
PER_PAGINA_MASSIMO = 60
MATERIA_NON_INDICATA = "Materia non indicata dalla fonte"
_STATI = {"all", "unread", "favorite"}


def archivio_in_lettura(config: Mapping[str, Any]) -> ArchivioNotiziario | None:
    return ArchivioNotiziario.in_lettura(percorso_archivio(config))


def _valore(item: Any, nome: str) -> str:
    valore = getattr(item, nome, "")
    valore = getattr(valore, "value", valore)
    return " ".join(str(valore or "").split())


def fascicoli_aperti(righe: Iterable[Any]) -> list[dict[str, str]]:
    """Fascicoli non archiviati dell'indice leggero, con l'etichetta del menu «Collega a fascicolo»."""
    elenco: list[tuple[str, dict[str, str]]] = []
    for item in righe:
        item_id = _valore(item, "id")
        if not item_id or _valore(item, "stato").rsplit(".", 1)[-1].upper() == "ARCHIVIATO":
            continue
        numero_rg, anno_rg = _valore(item, "numero_rg"), _valore(item, "anno_rg")
        rg = f"RG {numero_rg}/{anno_rg}" if numero_rg and anno_rg else (numero_rg or _valore(item, "numero"))
        titolo = _valore(item, "titolo") or _valore(item, "oggetto") or "Fascicolo"
        elenco.append((_valore(item, "numero"), {
            "id": item_id,
            "etichetta": f"{rg} - {titolo}" if rg else titolo,
            "titolo": titolo,
            "oggetto": _valore(item, "oggetto"),
            "tipo": _valore(item, "tipo").rsplit(".", 1)[-1],
            "area_pratica": _valore(item, "area_pratica"),
            "codice_oggetto_pst": _valore(item, "codice_oggetto_pst"),
        }))
    elenco.sort(key=lambda voce: voce[0], reverse=True)
    return [voce for _, voce in elenco]


def filtri_richiesti(argomenti: Mapping[str, Any]) -> dict[str, Any]:
    def _testo(nome: str) -> str:
        return " ".join(str(argomenti.get(nome) or "").split())[:120]

    try:
        pagina = max(1, int(argomenti.get("pagina") or 1))
    except (TypeError, ValueError):
        pagina = 1
    try:
        per_pagina = min(PER_PAGINA_MASSIMO, max(5, int(argomenti.get("per_pagina") or PER_PAGINA)))
    except (TypeError, ValueError):
        per_pagina = PER_PAGINA
    stato = _testo("stato") or "all"
    return {
        "fonte": _testo("fonte") if _testo("fonte") in PER_ID else "",
        "tipo": _testo("tipo") if _testo("tipo") in ETICHETTE_TIPO else "",
        "materia": _testo("materia"),
        "q": _testo("q").casefold(),
        "stato": stato if stato in _STATI else "all",
        "pertinenti": str(argomenti.get("pertinenti") or "").lower() in {"1", "true", "si", "sì"},
        "nuove": str(argomenti.get("nuove") or "").lower() in {"1", "true", "si", "sì"},
        "pagina": pagina,
        "per_pagina": per_pagina,
    }


def _voce(
    notizia: Mapping[str, Any],
    interazione: Mapping[str, Any],
    etichette_fascicoli: Mapping[str, str],
    pertinenti: list[dict[str, str]],
    ieri: str,
) -> dict[str, Any]:
    collegato = str(interazione.get("linkedCaseId") or "")
    materia = str(notizia.get("materia") or "")
    return {
        "id": notizia["id"],
        "slug": "",
        "title": notizia["titolo"],
        "summary": notizia.get("sintesi") or "",
        "content": "",
        "newsType": notizia["tipo"],
        "kind": notizia["tipo"],
        "kindLabel": ETICHETTE_TIPO.get(notizia["tipo"], ""),
        "publishedAt": notizia["data"],
        "sourceName": notizia["etichetta_fonte"],
        "authority": notizia["ente"],
        "sourceCode": notizia["fonte"],
        "sourceGroup": notizia["fonte"],
        "sourceUrl": notizia["url"],
        "officialReference": notizia.get("riferimento_ufficiale") or "",
        "matterName": materia or MATERIA_NON_INDICATA,
        "submatterName": "",
        "isNew": notizia["data"] >= ieri,
        "relatedCases": pertinenti,
        "read": bool(interazione.get("read")),
        "readAt": str(interazione.get("readAt") or ""),
        "favorite": bool(interazione.get("favorite")),
        "linkedCaseId": collegato,
        "linkedCaseLabel": str(etichette_fascicoli.get(collegato) or ""),
    }


def _corrisponde(voce: Mapping[str, Any], filtri: Mapping[str, Any], *, salta: str = "") -> bool:
    if salta != "fonte" and filtri["fonte"] and voce["sourceCode"] != filtri["fonte"]:
        return False
    if salta != "tipo" and filtri["tipo"] and voce["kind"] != filtri["tipo"]:
        return False
    if salta != "materia" and filtri["materia"] and voce["matterName"] != filtri["materia"]:
        return False
    if filtri["pertinenti"] and not voce["relatedCases"] and not voce["linkedCaseId"]:
        return False
    if filtri["nuove"] and not voce["isNew"]:
        return False
    if filtri["stato"] == "unread" and voce["read"]:
        return False
    if filtri["stato"] == "favorite" and not voce["favorite"]:
        return False
    if filtri["q"]:
        testo = " ".join(
            str(voce.get(campo) or "") for campo in ("title", "summary", "sourceName", "authority", "matterName", "officialReference")
        ).casefold()
        if filtri["q"] not in testo:
            return False
    return True


def _conteggi(voci: list[dict[str, Any]], filtri: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Per ogni filtro, quante notizie si vedrebbero scegliendo quella voce (gli altri filtri restano)."""
    fonti = Counter(v["sourceCode"] for v in voci if _corrisponde(v, filtri, salta="fonte"))
    tipi = Counter(v["kind"] for v in voci if _corrisponde(v, filtri, salta="tipo"))
    materie = Counter(v["matterName"] for v in voci if _corrisponde(v, filtri, salta="materia"))
    return {
        "sources": [
            {"id": fonte.id, "label": fonte.etichetta, "count": fonti.get(fonte.id, 0)} for fonte in FONTI
        ],
        "kinds": [{"id": chiave, "label": etichetta, "count": tipi.get(chiave, 0)} for chiave, etichetta in ETICHETTE_TIPO.items()],
        "matters": [
            {"id": materia, "label": materia, "count": numero}
            for materia, numero in sorted(materie.items(), key=lambda voce: (-voce[1], voce[0]))
        ],
    }


def stato_fonti(archivio: ArchivioNotiziario) -> list[dict[str, Any]]:
    stato = archivio.stato_fonti()
    righe: list[dict[str, Any]] = []
    for fonte in FONTI:
        voce = stato.get(fonte.id) or {}
        righe.append({
            "id": fonte.id,
            "label": fonte.etichetta,
            "authority": fonte.ente,
            "url": fonte.url,
            "ok": bool(voce.get("ultimo_esito_ok")),
            "checked": bool(voce),
            "count": int(voce.get("in_archivio") or 0),
            "latestPublishedAt": str(voce.get("ultima_pubblicazione") or ""),
            "lastAttemptAt": str(voce.get("ultimo_tentativo") or ""),
            "lastSuccessAt": str(voce.get("ultimo_successo") or ""),
            "message": str(voce.get("messaggio") or ""),
            "frequencyMinutes": fonte.frequenza_minuti,
            "verifiedOn": fonte.verificato_il,
            "preservedFromCache": bool(voce) and not voce.get("ultimo_esito_ok") and int(voce.get("in_archivio") or 0) > 0,
        })
    return righe


def costruisci_vista(
    archivio: ArchivioNotiziario,
    *,
    interazioni: Mapping[str, Mapping[str, Any]],
    fascicoli: list[dict[str, str]],
    filtri: Mapping[str, Any],
    oggi: date,
    indice: IndicePertinenza | None = None,
) -> dict[str, Any]:
    notizie = archivio.elenco()
    indice = indice or costruisci_indice(fascicoli)
    etichette = {voce["id"]: voce["etichetta"] for voce in fascicoli}
    ieri = (oggi - timedelta(days=1)).isoformat()
    voci = [
        _voce(notizia, interazioni.get(notizia["id"], {}), etichette, fascicoli_pertinenti(notizia, indice), ieri)
        for notizia in notizie
    ]
    filtrate = [voce for voce in voci if _corrisponde(voce, filtri)]
    pagina, per_pagina = int(filtri["pagina"]), int(filtri["per_pagina"])
    inizio = (pagina - 1) * per_pagina
    stati = stato_fonti(archivio)
    ultimo_giro = max((riga["lastAttemptAt"] for riga in stati), default="")
    return {
        "ok": True,
        "source": "archivio_notizie_utili",
        "refreshedAt": ultimo_giro,
        "refreshRequired": False,
        "items": filtrate[inizio:inizio + per_pagina],
        "total": len(filtrate),
        "page": pagina,
        "pageSize": per_pagina,
        "hasMore": inizio + per_pagina < len(filtrate),
        "facets": _conteggi(voci, filtri),
        "relevantCount": sum(1 for voce in voci if voce["relatedCases"]),
        "newCount": sum(1 for voce in voci if voce["isNew"]),
        "unreadCount": sum(1 for voce in voci if not voce["read"]),
        "sourceStates": stati,
        # l'elenco per «Collega a fascicolo» viaggia solo con la prima pagina
        "cases": [{"id": voce["id"], "label": voce["etichetta"]} for voce in fascicoli] if pagina == 1 else [],
        "appliedFilters": {chiave: filtri[chiave] for chiave in ("fonte", "tipo", "materia", "stato", "pertinenti", "nuove")},
    }


def voce_singola(
    archivio: ArchivioNotiziario | None,
    notizia_id: str,
) -> dict[str, Any] | None:
    """Riga dell'archivio nel formato della cache precedente (per le interazioni)."""
    if archivio is None:
        return None
    notizia = archivio.notizia(notizia_id)
    if not notizia:
        return None
    return {
        "id": notizia["id"],
        "slug": "",
        "title": notizia["titolo"],
        "short_summary": notizia.get("sintesi") or "",
        "content": "",
        "news_type": notizia["tipo"],
        "published_at": notizia["data"],
        "source_name": notizia["etichetta_fonte"],
        "source_code": notizia["fonte"],
        "source_url": notizia["url"],
        "matter_name": notizia.get("materia") or "",
        "submatter_name": "",
        "publication_status": "published",
    }


__all__ = [
    "archivio_in_lettura", "costruisci_vista", "fascicoli_aperti", "filtri_richiesti", "stato_fonti", "voce_singola",
]
