"""Tool deterministici dichiarati nel registro delle sorgenti e collegati alle funzioni reali del software.

- ``search_studio_index``: indice di ricerca dello studio (``pct.search_index.IndiceRicerca``, FTS5, tenant corrente);
- ``search_verified_cassazione``: archivio SentenzeWeb della Cassazione (``pct.sentenzeweb_corpus``), entro il tempo
  massimo e con i posti contati di ``lex.harness.giurisprudenza.cerca``;
- ``get_giurisprudenza_items``: archivio nativo della giurisprudenza (Corte costituzionale e fonti pubbliche);
- ``lookup_uffici_giudiziari``: bundle degli uffici giudiziari (``pct.uffici_giudiziari``: 648 uffici con PEC).
Nessuno scrive dati; i risultati riportano estremi e collegamenti ufficiali come li ha l'archivio.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from .models import OperationalQueryContext, OperationalToolResult


def _riga(oggetto: Any) -> dict[str, Any]:
    return asdict(oggetto) if is_dataclass(oggetto) else dict(oggetto)


class ArchiviToolsMixin:
    """Metodi aggiunti a ``OperationalKnowledgeTools`` (usa ``_decision``, ``_blocked``, ``_unavailable``, ``_rows_result``)."""

    def _indice_studio(self) -> Any:
        if "ricerca_studio" in self.repositories:  # type: ignore[attr-defined]
            return self.repositories["ricerca_studio"]  # type: ignore[attr-defined]
        from flask import current_app

        from pct.search_index import IndiceRicerca
        from web.services.tenant_paths import tenant_data_path

        percorso = tenant_data_path("SEARCH_INDEX", current_app.config.get("SEARCH_INDEX", ""), require_tenant=True)
        return IndiceRicerca(index_path=percorso)

    def search_studio_index(self, query: str, context: OperationalQueryContext, *, limit: int = 12) -> OperationalToolResult:
        decision = self._decision("ricerca_studio", context)  # type: ignore[attr-defined]
        if not decision.allowed:
            return self._blocked("ricerca_studio", decision)  # type: ignore[attr-defined]
        try:
            righe = [_riga(r) for r in self._indice_studio().cerca(query, limit=limit)]
        except Exception as exc:
            return self._unavailable("ricerca_studio", f"Indice di ricerca dello studio non interrogabile: {exc}")  # type: ignore[attr-defined]
        return self._rows_result("ricerca_studio", context, righe, dict, "risultato_ricerca", decision)  # type: ignore[attr-defined]

    def _pronunce(self, query: str, context: OperationalQueryContext, *, archivio: str, limit: int) -> OperationalToolResult:
        decision = self._decision("citazioni_cassazione", context)  # type: ignore[attr-defined]
        if not decision.allowed:
            return self._blocked("citazioni_cassazione", decision)  # type: ignore[attr-defined]
        from lex.harness.giurisprudenza import archivi, cerca

        esito = cerca(query, limite=limit, sorgenti=lambda: [(n, c) for n, c in archivi() if n.startswith(archivio)])
        righe = [{"id": f"{p.archivio}|{p.numero}/{p.anno}", "titolo": p.estremi, "organo": p.organo, "sezione": p.sezione,
                  "numero": p.numero, "anno": p.anno, "data": p.data, "url": p.url, "massima": p.massima}
                 for p in esito.pronunce]
        risultato = self._rows_result("citazioni_cassazione", context, righe, dict, "pronuncia", decision)  # type: ignore[attr-defined]
        risultato.coverage_gaps.extend(esito.errori)
        if not esito.archivi:
            risultato.coverage_gaps.append(f"Archivio «{archivio}» non disponibile in questo processo.")
        return risultato

    def search_verified_cassazione(self, query: str, context: OperationalQueryContext, *, limit: int = 5) -> OperationalToolResult:
        return self._pronunce(query, context, archivio="Cassazione", limit=limit)

    def get_giurisprudenza_items(self, query: str, context: OperationalQueryContext, *, limit: int = 5) -> OperationalToolResult:
        return self._pronunce(query, context, archivio="archivio dello studio", limit=limit)

    def lookup_uffici_giudiziari(self, query: str, context: OperationalQueryContext, *, tipo: str = "",
                                 limit: int = 12) -> OperationalToolResult:
        decision = self._decision("uffici_giudiziari", context)  # type: ignore[attr-defined]
        if not decision.allowed:
            return self._blocked("uffici_giudiziari", decision)  # type: ignore[attr-defined]
        try:
            gestore = self.repositories.get("uffici_giudiziari")  # type: ignore[attr-defined]
            if gestore is None:
                from pct.uffici_giudiziari import get_gestore

                gestore = get_gestore()
            righe = [dict(r, id=r.get("codice", "")) for r in gestore.cerca(query, tipo=tipo, limit=limit)]
        except Exception as exc:
            return self._unavailable("uffici_giudiziari", f"Elenco degli uffici giudiziari non disponibile: {exc}")  # type: ignore[attr-defined]
        return self._rows_result("uffici_giudiziari", context, righe, dict, "ufficio_giudiziario", decision)  # type: ignore[attr-defined]


__all__ = ["ArchiviToolsMixin"]
