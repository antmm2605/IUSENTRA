"""Chi, dove, che cosa: l'intestazione della pratica."""

from __future__ import annotations

from typing import Any

from ._testo import data_it, euro, pulisci

STATI_FASCICOLO = {
    "APERTO": "aperto",
    "IN_CORSO": "in corso",
    "SOSPESO": "sospeso",
    "DEFINITO": "definito",
    "CHIUSO": "chiuso",
    "ARCHIVIATO": "archiviato",
}


def intestazione(fascicolo: dict[str, Any], parti: list[dict[str, Any]], catalogo: list[dict[str, Any]]) -> dict[str, Any]:
    numero_rg = pulisci(fascicolo.get("numero_rg"))
    anno_rg = pulisci(fascicolo.get("anno_rg"))
    rg = f"{numero_rg}/{anno_rg}" if numero_rg and anno_rg not in {"", "0"} else numero_rg
    ruoli: dict[str, list[str]] = {}
    for parte in parti:
        ruolo = pulisci(parte.get("ruolo") or parte.get("parte")).lower() or "parte"
        nome = pulisci(parte.get("nome") or parte.get("denominazione"))
        if nome:
            ruoli.setdefault(ruolo, []).append(nome)
    area = pulisci(fascicolo.get("area_pratica")) or pulisci(next((voce.get("legal_area") for voce in catalogo if voce.get("legal_area")), ""))
    stato_codice = pulisci(fascicolo.get("stato")).upper()
    return {
        "numero": pulisci(fascicolo.get("numero")),
        "titolo": pulisci(fascicolo.get("titolo")),
        "rg": rg,
        "ufficio": pulisci(fascicolo.get("tribunale")),
        "giudice": pulisci(fascicolo.get("giudice")),
        "sezione": pulisci(fascicolo.get("sezione")),
        "cliente": pulisci(fascicolo.get("cliente") or fascicolo.get("nome_cliente")),
        "controparte": pulisci(fascicolo.get("controparte")),
        "parti": ruoli,
        "oggetto": pulisci(fascicolo.get("oggetto")),
        "tipo": pulisci(fascicolo.get("tipo")).replace("_", " ").lower(),
        "rito": pulisci(fascicolo.get("tipo_procedimento")),
        "area": area,
        "codice_oggetto_pst": pulisci(fascicolo.get("codice_oggetto_pst")),
        "stato": STATI_FASCICOLO.get(stato_codice, stato_codice.lower()),
        "stato_codice": stato_codice,
        "da_archiviare": bool(fascicolo.get("archivio_pronto")) and stato_codice == "DEFINITO",
        "valore_causa": euro(fascicolo.get("valore_causa")),
        "data_apertura": data_it(fascicolo.get("data_apertura")),
        "avvocato": pulisci(fascicolo.get("avvocato_referente")),
        "canale": pulisci(fascicolo.get("canale_operativo") or fascicolo.get("source")).upper(),
        "prossima_udienza": data_it(fascicolo.get("data_prossima_udienza")),
        "prima_udienza": data_it(fascicolo.get("data_prima_udienza")),
        "data_notifica_citazione": data_it(fascicolo.get("data_notifica_citazione")),
    }


__all__ = ["STATI_FASCICOLO", "intestazione"]
