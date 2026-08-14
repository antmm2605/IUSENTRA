"""Bridge React della prima nota di studio (registro cronologico di cassa)."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from pct.prima_nota import CATEGORIE, METODI

_CATEGORIA_LABEL = {
    "onorari": "Onorari",
    "anticipazioni_rimborsate": "Anticipazioni rimborsate (art. 15)",
    "altri_incassi": "Altri incassi",
    "anticipazioni_clienti": "Anticipazioni per clienti (art. 15)",
    "spese_studio": "Spese di studio",
    "compensi_terzi": "Compensi a terzi",
    "imposte_contributi": "Imposte e contributi",
    "altri_pagamenti": "Altri pagamenti",
}


def _text(value: Any, fallback: str = "") -> str:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or fallback


def _money(value: float) -> str:
    intero, decimali = f"{float(value or 0.0):,.2f}".split(".")
    return f"€ {intero.replace(',', '.')},{decimali}"


def _movimento_payload(m: Any) -> dict[str, Any]:
    return {
        "id": m.id,
        "data": m.data,
        "tipo": m.tipo,
        "importo": float(m.importo),
        "importoLabel": _money(m.importo),
        "categoria": m.categoria,
        "categoriaLabel": _CATEGORIA_LABEL.get(m.categoria, m.categoria),
        "controparte": m.controparte,
        "causale": m.causale,
        "metodo": m.metodo,
        "documento": m.documento_riferimento,
        "fascicoloId": m.fascicolo_id,
        "parcellaId": m.parcella_id,
        "note": m.note,
        "stornabile": not str(m.note or "").casefold().startswith("storno di"),
        "actions": {"storna": f"/prima-nota/{m.id}/storna"},
    }


def build_react_prima_nota_payload(
    *,
    get_prima_nota: Callable[[], Any],
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = query or {}
    dal = _text(params.get("dal"))
    al = _text(params.get("al"))
    tipo = _text(params.get("tipo"))
    registro = get_prima_nota()
    movimenti = registro.registro(dal=dal, al=al, tipo=tipo)
    saldi = registro.saldi(dal=dal, al=al)
    return {
        "source": "repository_reali",
        "generatedAt": date.today().isoformat(),
        "contracts": {"mock_fallback": False, "writes": "operational_routes", "route_owner": "react_shell"},
        "filters": {"dal": dal, "al": al, "tipo": tipo},
        "summary": {
            "incassi": saldi["incassi"],
            "incassiLabel": _money(saldi["incassi"]),
            "pagamenti": saldi["pagamenti"],
            "pagamentiLabel": _money(saldi["pagamenti"]),
            "saldo": saldi["saldo"],
            "saldoLabel": _money(saldi["saldo"]),
            "movimenti": saldi["movimenti"],
            "perCategoria": [
                {
                    "categoria": categoria,
                    "label": _CATEGORIA_LABEL.get(categoria, categoria),
                    "importo": importo,
                    "importoLabel": _money(importo),
                }
                for categoria, importo in sorted(saldi["per_categoria"].items(), key=lambda kv: -kv[1])
            ],
        },
        "movimenti": [_movimento_payload(m) for m in reversed(movimenti)],
        "options": {
            "categorieIncasso": [
                {"value": c, "label": _CATEGORIA_LABEL.get(c, c)} for c in CATEGORIE["INCASSO"]
            ],
            "categoriePagamento": [
                {"value": c, "label": _CATEGORIA_LABEL.get(c, c)} for c in CATEGORIE["PAGAMENTO"]
            ],
            "metodi": [{"value": m, "label": m.capitalize()} for m in METODI],
        },
        "actions": {
            "registra": "/prima-nota/registra",
            "riconcilia": "/prima-nota/riconcilia-parcelle",
            "esporta": "/prima-nota/esporta.csv",
        },
        "avvertenza": (
            "La prima nota registra ed esporta i movimenti: non calcola imposte, "
            "ritenute o contributi. La qualificazione fiscale resta al professionista incaricato."
        ),
    }
