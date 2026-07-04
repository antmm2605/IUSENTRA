"""Estrazione governata dei link di dettaglio dalle liste ufficiali di giurisprudenza.

Drill-down «dalla lista al provvedimento»: data una pagina-lista ufficiale già
scaricata (fase 2 del workflow "Lex ciclo web" o altri harness), individua gli
URL dei singoli provvedimenti da approfondire. Nessun pattern è inventato: ogni
regola rispecchia conoscenza di produzione già versionata.

- **Cassazione**: marker identici a ``CASSAZIONE_DETAIL_URL_MARKERS`` di
  ``pct/legal_update_source_parsers.py``, nella variante severa del parser
  (``_cassazione_detail_url``: marker + ``contentId=``).
- **Corte costituzionale**: schede pronuncia ``/scheda-pronuncia/<anno>/<numero>``
  — lo stesso pattern con cui il filtro ``corte_costituzionale`` del parser di
  produzione distingue una scheda pronuncia da un link di navigazione.
- **Giustizia amministrativa**: provvedimenti PDF sotto ``/documents/`` (forma
  censita in ``pct/legal_practice_research_matrix``, es. Cons. St., A.P.,
  sent. 10/2020). Il canale HTML di G.A. è instabile per i crawler (la fonte
  diretta è disabilitata in produzione a favore di OpenGA): l'estrazione qui è
  best-effort e un esito vuoto è un esito valido, non un errore.

Fail-closed: pagina-lista non riconosciuta → nessun link; href risolto fuori
dal dominio della lista → scartato; schemi non http(s) → scartati; dedup
case-insensitive a ordine stabile. L'allineamento coi marker di produzione è
verificato da ``tests/test_lex_autonomy_detail_links.py``.
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

# Copia versionata dei marker di produzione (pct/legal_update_source_parsers.py):
# il test di allineamento fallisce se le due tuple divergono.
CASSAZIONE_DETAIL_URL_MARKERS: tuple[str, ...] = (
    "/it/civile_dettaglio.page",
    "/it/penale_dettaglio.page",
    "/it/qsp_dettaglio.page",
    "/it/qsc_dettaglio.page",
    "/it/quc_dettaglio.page",
    "/it/rlc_dettaglio.page",
    "/it/rlp_dettaglio.page",
    "/it/su_dettaglio.page",
)

_HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


@dataclass(frozen=True)
class DetailLinkRule:
    """Regola di drill-down per una famiglia di liste ufficiali."""

    source: str
    host_suffix: str
    list_url_markers: tuple[str, ...]
    detail_pattern: re.Pattern[str]
    detail_label: str
    required_tokens: tuple[str, ...] = field(default=())

    def matches_list(self, list_url: str) -> bool:
        lowered = str(list_url or "").casefold()
        return any(marker in lowered for marker in self.list_url_markers)

    def is_detail_url(self, absolute_url: str) -> bool:
        lowered = absolute_url.casefold()
        if not all(token in lowered for token in self.required_tokens):
            return False
        return bool(self.detail_pattern.search(absolute_url))

    def allows_host(self, host: str) -> bool:
        lowered = str(host or "").casefold()
        return lowered == self.host_suffix or lowered.endswith("." + self.host_suffix)


RULES: tuple[DetailLinkRule, ...] = (
    DetailLinkRule(
        source="cassazione",
        host_suffix="cortedicassazione.it",
        list_url_markers=(
            "cortedicassazione.it/it/giurisprudenza_civile.page",
            "cortedicassazione.it/it/giurisprudenza_penale.page",
            "cortedicassazione.it/it/ultime_sent_ord_e_questioni.page",
        ),
        detail_pattern=re.compile("|".join(re.escape(marker) for marker in CASSAZIONE_DETAIL_URL_MARKERS), re.IGNORECASE),
        required_tokens=("contentid=",),
        detail_label="Dettaglio sentenza Cassazione",
    ),
    DetailLinkRule(
        source="corte_costituzionale",
        host_suffix="cortecostituzionale.it",
        list_url_markers=("cortecostituzionale.it",),
        detail_pattern=re.compile(r"/scheda-pronuncia/\d{4}/\d+", re.IGNORECASE),
        detail_label="Scheda pronuncia Corte costituzionale",
    ),
    DetailLinkRule(
        source="giustizia_amministrativa",
        host_suffix="giustizia-amministrativa.it",
        list_url_markers=("giustizia-amministrativa.it",),
        detail_pattern=re.compile(r"/documents/[^\s\"']+\.pdf(?:/[0-9a-f\-]+)?(?:[?#]|$)", re.IGNORECASE),
        detail_label="Provvedimento Giustizia amministrativa (PDF)",
    ),
)


def rule_for(list_url: str) -> DetailLinkRule | None:
    """La regola di drill-down applicabile alla pagina-lista, se esiste."""

    for rule in RULES:
        if rule.matches_list(list_url):
            return rule
    return None


def extract_detail_links(list_url: str, page_html: str, *, limit: int = 2) -> list[str]:
    """URL assoluti dei dettagli da approfondire (max ``limit``), fail-closed.

    Pagina-lista senza regola, HTML vuoto o ``limit`` non positivo → lista
    vuota. Gli href relativi sono risolti contro ``list_url``; restano solo
    quelli sul dominio della regola che corrispondono al pattern di dettaglio.
    """

    rule = rule_for(list_url)
    if rule is None or limit <= 0 or not page_html:
        return []
    results: list[str] = []
    seen: set[str] = set()
    for raw_href in _HREF_RE.findall(page_html):
        href = html_lib.unescape(raw_href).strip()
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        absolute = urljoin(list_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not rule.allows_host(parsed.netloc):
            continue
        if not rule.is_detail_url(absolute):
            continue
        key = absolute.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(absolute)
        if len(results) >= limit:
            break
    return results


__all__ = [
    "CASSAZIONE_DETAIL_URL_MARKERS",
    "DetailLinkRule",
    "RULES",
    "extract_detail_links",
    "rule_for",
]
