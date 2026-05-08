"""Guard per ricerche di sentenze con riferimento esatto.

Impedisce che un frammento locale (senza URL ufficiale, senza dispositivo)
venga presentato come risposta definitiva a una ricerca esatta.

Confidence caps:
- Nessun exact_match trovato: ≤ 0.45
- Exact_match trovato ma senza testo completo: ≤ 0.55
- Exact_match con testo completo: nessun cap aggiuntivo
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExactCaseLawCheckResult:
    match_status: str = "not_found"  # "exact_match" | "possible_match" | "not_found"
    confidence_cap: float = 0.45
    confidence_cap_reason: str = ""
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    official_url: str = ""
    has_full_text: bool = False
    has_pdf: bool = False
    has_dispositivo: bool = False
    has_motivazione: bool = False
    discarded_unrelated_count: int = 0


_OFFICIAL_DOMAINS = frozenset({
    "giustizia.it",
    "cortedicassazione.it",
    "cortecostituzionale.it",
    "normattiva.it",
    "giustizia-amministrativa.it",
    "italgiure.giustizia.it",
})


def _is_official_url(url: str) -> bool:
    if not url:
        return False
    return any(domain in url.lower() for domain in _OFFICIAL_DOMAINS)


def _item_str(item: Any, *keys: str) -> str:
    for key in keys:
        val = getattr(item, key, None) if not isinstance(item, dict) else item.get(key)
        if val:
            return str(val).strip()
    return ""


def check_exact_case_law(
    evidence_items: list[Any],
    *,
    exact_number: str = "",
    exact_year: str = "",
    exact_date: str = "",
    exact_court: str = "",
) -> ExactCaseLawCheckResult:
    """Classifica i risultati di ricerca rispetto a un riferimento esatto.

    Scarta le sentenze non pertinenti al numero/anno richiesto.
    Calcola il confidence_cap in base alla completezza dell'exact_match.
    """
    result = ExactCaseLawCheckResult()

    if not evidence_items:
        result.confidence_cap_reason = "Nessuna evidenza trovata"
        result.next_actions.append("Cerca la sentenza direttamente su italgiure.giustizia.it o cortedicassazione.it")
        return result

    exact_match_item = None
    possible_match_item = None
    discarded = 0

    for item in evidence_items:
        title = _item_str(item, "title", "citation").lower()
        content = _item_str(item, "content", "excerpt", "text").lower()
        combined = f"{title} {content}"
        official_url = _item_str(item, "official_url", "url")

        # Controlla corrispondenza numero
        number_match = bool(exact_number and exact_number in combined)
        year_match = bool(exact_year and exact_year in combined)
        date_match = bool(exact_date and exact_date.replace("/", "") in combined.replace("/", "").replace("-", ""))
        court_lower = exact_court.lower()
        official = _is_official_url(official_url)
        court_match = bool(
            not exact_court
            or court_lower in combined
            or (court_lower == "corte di cassazione" and "cortedicassazione.it" in official_url.lower())
        )

        # Exact match: numero + (anno o data) + URL ufficiale
        if number_match and (year_match or date_match) and court_match and official:
            exact_match_item = item
            result.official_url = official_url
            break
        # Possible match: numero + (anno o data) senza URL ufficiale
        elif number_match and (year_match or date_match):
            if possible_match_item is None:
                possible_match_item = item
        else:
            discarded += 1

    result.discarded_unrelated_count = discarded

    if exact_match_item is not None:
        result.match_status = "exact_match"
        # Verifica completezza testo
        content = _item_str(exact_match_item, "content", "excerpt", "text").lower()
        dispositivo_markers = ["p.q.m.", "per questi motivi", "si rigetta", "si accoglie", "condanna", "dispositivo"]
        motivazione_markers = ["motivazione", "ritenuto", "considerato", "in fatto", "in diritto", "svolgimento"]
        result.has_dispositivo = any(
            m in content and f"senza {m}" not in content and f"manca {m}" not in content
            for m in dispositivo_markers
        )
        result.has_motivazione = any(
            m in content and f"senza {m}" not in content and f"manca {m}" not in content
            for m in motivazione_markers
        )
        result.has_pdf = result.official_url.lower().endswith(".pdf")
        result.has_full_text = result.has_dispositivo or result.has_motivazione or len(content) > 1200

        if result.has_full_text:
            result.confidence_cap = 0.92
            result.confidence_cap_reason = "Sentenza verificata con URL ufficiale e testo completo"
        else:
            result.confidence_cap = 0.55
            result.confidence_cap_reason = "Sentenza trovata su fonte ufficiale ma senza testo integrale"
            result.warnings.append("Testo completo non disponibile: verifica il dispositivo sulla fonte ufficiale")
            result.next_actions.append(f"Consulta il testo integrale su {result.official_url}")

    elif possible_match_item is not None:
        result.match_status = "possible_match"
        result.confidence_cap = 0.45
        result.confidence_cap_reason = "Riferimento numerico trovato ma senza URL ufficiale verificato"
        result.warnings.append(
            "Il riferimento trovato non proviene da una fonte ufficiale verificata. "
            "Potrebbe essere un frammento o una massima di terzi."
        )
        result.next_actions.append("Verifica la sentenza direttamente su italgiure.giustizia.it")

    else:
        result.match_status = "not_found"
        result.confidence_cap = 0.45
        result.confidence_cap_reason = "Sentenza non trovata nei risultati di ricerca"
        result.warnings.append(
            "La sentenza richiesta non è stata trovata con i dati disponibili. "
            "È possibile che non sia ancora pubblicata o che il riferimento sia parziale."
        )
        result.next_actions.extend([
            "Cerca su italgiure.giustizia.it con il numero esatto",
            "Verifica che numero e anno siano corretti",
        ])

    return result
