"""Retrieval giurisprudenziale per Lex."""

from __future__ import annotations

from lex.schemas import LexSource

try:  # sola lettura: la ricerca non riallinea il repository ne' riesporta i JSON
    from web.helpers import get_giurisprudenza_readonly as _gestore_giurisprudenza
except ImportError:  # pragma: no cover - versioni senza accessore in sola lettura
    from web.helpers import get_giurisprudenza as _gestore_giurisprudenza

# Spazio della massima nel testo della fonte: il resto del blocco (1600 caratteri) resta al dispositivo.
_MASSIMA_MAX_CHARS = 1100


def _first_non_empty(*values) -> str:
    for value in values:
        if isinstance(value, (list, tuple, set)):
            clean = ", ".join(str(item).strip() for item in value if str(item).strip())
        else:
            clean = str(value or "").strip()
        if clean:
            return clean
    return ""


def _compatto(value) -> str:
    return " ".join(str(value or "").split())


def _accorcia(text: str, limite: int) -> str:
    if len(text) <= limite:
        return text
    taglio = text[:limite]
    spazio = taglio.rfind(" ")
    if spazio > limite * 0.6:
        taglio = taglio[:spazio]
    return taglio.rstrip(" ,;:") + "…"


def _testo_fonte(row: dict, *, massima: str, dispositivo: str, principio: str) -> str:
    """Massima ufficiale prima, poi dispositivo: entro il limite del blocco il modello vede il principio."""

    parti: list[str] = []
    if massima:
        parti.append(f"Massima: {_accorcia(massima, _MASSIMA_MAX_CHARS) if dispositivo else massima}")
    if dispositivo:
        parti.append(f"Dispositivo: {dispositivo}")
    if principio and principio != dispositivo and principio.lower() not in " ".join(parti).lower():
        parti.append(f"Principio: {principio}")
    if parti:
        return " ".join(parti)
    return _compatto(_first_non_empty(row.get("text"), row.get("sintesi"), row.get("oggetto")))


def _riferimento_verificato(row: dict, official_url: str) -> bool:
    if row.get("verified_reference") is not None:
        return bool(row.get("verified_reference"))
    stato = str(row.get("stato_verifica") or "").strip()
    return stato == "verificata" and official_url.startswith(("http://", "https://"))


def search_giurisprudenza_sources(message: str) -> list[LexSource]:
    gestore = _gestore_giurisprudenza()
    rows = []
    if hasattr(gestore, "resolve_lex_giurisprudenza_route"):
        try:
            rows = list((gestore.resolve_lex_giurisprudenza_route(message) or {}).get("corpus_rows") or [])
        except Exception:
            rows = []
    if not rows:
        rows = list(gestore.cerca_corpus_professionale(q=message, limit=4) or [])
    results: list[LexSource] = []
    for row in rows[:4]:
        official_url = _first_non_empty(row.get("official_url"), row.get("url_pagina_ufficiale"), row.get("url_html_ufficiale"))
        organo = _first_non_empty(row.get("organo"), row.get("organo_giudicante"), row.get("court"), row.get("grado"))
        numero = _first_non_empty(row.get("numero_sentenza"), row.get("numero"))
        anno = _first_non_empty(row.get("anno_sentenza"), row.get("anno"))
        data_deposito = _first_non_empty(row.get("data_deposito"), row.get("published_at"))
        massima = _compatto(_first_non_empty(row.get("massima_ufficiale")))
        dispositivo = _compatto(_first_non_empty(row.get("dispositivo"), row.get("esito")))
        principio = _compatto(_first_non_empty(row.get("principio_sintetico"), row.get("principio")))
        metadata = {
            "verified_reference": _riferimento_verificato(row, official_url),
            "official_url": official_url,
            "url": official_url,
            "url_pagina_ufficiale": _first_non_empty(row.get("url_pagina_ufficiale"), official_url),
            "url_pdf_ufficiale": _first_non_empty(row.get("url_pdf_ufficiale"), row.get("pdf_url")),
            "organo": organo,
            "court": organo,
            "authority": organo,
            "sezione": _first_non_empty(row.get("sezione")),
            "numero_sentenza": numero,
            "anno_sentenza": anno,
            "tipo_provvedimento": _first_non_empty(row.get("tipo_provvedimento")),
            "ecli": _first_non_empty(row.get("ecli")),
            "stato_verifica": _first_non_empty(row.get("stato_verifica")),
            "relatore": _first_non_empty(row.get("relatore")),
            "data_deposito": data_deposito,
            "data_decisione": _first_non_empty(row.get("data_decisione")),
            "norme_citate": row.get("norme_citate") or row.get("riferimenti_normativi") or [],
            "questione": _first_non_empty(row.get("questione"), row.get("questione_giuridica"), row.get("oggetto")),
            "dispositivo": dispositivo,
            "principio": principio,
            "principio_sintetico": principio,
            "massima_ufficiale": massima,
            "published_at": data_deposito,
        }
        results.append(
            LexSource(
                source_type="giurisprudenza",
                source_id=str(row.get("id") or row.get("sentenza_id") or ""),
                title=str(row.get("titolo") or row.get("citation") or "Sentenza"),
                excerpt=_testo_fonte(row, massima=massima, dispositivo=dispositivo, principio=principio),
                score=float(row.get("score") or 0.85),
                metadata=metadata,
            )
        )
    return results
