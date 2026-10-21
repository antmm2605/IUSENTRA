"""Schede di compilazione degli atti: da dove viene ogni dato e chi lo scrive.

Ogni scheda (``pct/template_atti_schede/<ID>.json``) dichiara, per un modello di atto, i campi con la
loro base normativa e la fonte: ``database`` (gestionale), ``archivio_letture`` (fatti letti dai documenti
e dalle PEC), ``documento``, ``calcolo`` (regola deterministica del software), ``avvocato`` (dato da
chiedere) o ``lex`` (proposta da confermare). Le parti narrative che Lex può redigere e i casi in cui
deve astenersi sono elencati nella scheda. Base normativa: c.p.c. e leggi citate in ciascuna scheda.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

CARTELLA = Path(__file__).with_name("template_atti_schede")
FONTI = ("database", "archivio_letture", "documento", "calcolo", "avvocato", "lex")


@lru_cache(maxsize=1)
def carica_schede() -> dict[str, dict[str, Any]]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(CARTELLA.glob("*.json"))}


def scheda_per_template(template_id: str) -> dict[str, Any] | None:
    """La scheda che copre il modello indicato (anche come variante), se esiste."""
    return next((s for s in carica_schede().values() if template_id in s["template"]), None)


def campi_da_chiedere(scheda: dict[str, Any], valori: dict[str, Any]) -> list[dict[str, Any]]:
    """Campi obbligatori ancora vuoti dopo la precompilazione, nell'ordine della scheda.

    I campi a calcolo li produce il software e non si chiedono; gli altri si propongono all'avvocato
    con la domanda della scheda o, se manca, con l'etichetta del campo.
    """
    mancanti = []
    for campo in scheda["campi"]:
        if not campo["obbligatorio"] or campo["fonte"]["tipo"] == "calcolo":
            continue
        if str(valori.get(campo["campo"]) or "").strip():
            continue
        mancanti.append({"campo": campo["campo"], "domanda": campo["fonte"].get("domanda") or campo["etichetta"],
                         "se_manca": campo.get("se_manca", "")})
    return mancanti


def scheda_per_modello(model_code: str) -> dict[str, Any] | None:
    """La scheda di un modello del compilatore o del catalogo, se esiste."""
    return next((s for s in carica_schede().values()
                 if model_code in s.get("modelli_compilatore", []) or model_code in s["template"]), None)


def _vuoto(valore: Any) -> bool:
    return valore is None or (isinstance(valore, str) and not valore.strip())


def _fatti_del_campo(campo: dict[str, Any], fatti: list[Any]) -> list[Any]:
    selettori = campo.get("fatti") or []
    trovati = []
    for fatto in fatti:
        if getattr(fatto, "verifica", "") in {"respinto", "respinta", "ignorata"}:
            continue
        for sel in selettori:
            if getattr(fatto, "categoria", "") == sel["categoria"] and (not sel.get("campo") or getattr(fatto, "campo", "") == sel["campo"]):
                trovati.append(fatto)
                break
    return trovati


def _termine_calcolato(termine: dict[str, Any] | None, fatti: Any, oggi: date | None) -> dict[str, Any]:
    """Scadenza calcolata dal software quando la data di partenza è nell'archivio delle letture."""
    if not termine:
        return {}
    from pct.schede_termini import calcola, data_base, fatti_base

    fonti = fatti_base(termine, list(fatti))
    try:
        base = data_base(termine, fonti)
    except ValueError as exc:
        return {"spiegazione": str(exc), "verifica_avvocato": True}
    if base is None:
        return {}
    r = calcola(termine, base)
    scadenza = date.fromisoformat(r["scadenza"])
    oggi = oggi or datetime.now(ZoneInfo("Europe/Rome")).date()
    return {"stato": "calcolato", "valore": scadenza.strftime("%d/%m/%Y"), "spiegazione": r["spiegazione"],
            "scaduto": scadenza < oggi,
            "verifica_avvocato": r["verifica_avvocato"] or not any(
                getattr(fatto, "verifica", "") in {"verificata", "corretta"} for fatto in fonti)}


def risolvi_scheda(scheda: dict[str, Any], valori: dict[str, Any], *, fatti: list[Any] = (),
                   documenti: list[str] = (), oggi: date | None = None) -> dict[str, Any]:
    """Stato di ogni campo della scheda e sole domande da fare all'avvocato.

    Ordine delle fonti: dato del gestionale (``compilatore``), fatto letto dall'archivio (da confermare),
    documento presente nel fascicolo (da verificare), regola di calcolo, proposta di Lex, domanda.
    Nessun valore viene inventato: un campo senza fonte resta una domanda.
    """
    nomi_documenti = [str(n) for n in documenti]
    campi, domande = [], []
    for campo in scheda["campi"]:
        voce = {"campo": campo["campo"], "etichetta": campo["etichetta"], "obbligatorio": campo["obbligatorio"],
                "norma": campo.get("norma", [])}
        valore = next((valori.get(k) for k in campo.get("compilatore", []) if not _vuoto(valori.get(k))), None)
        letti = _fatti_del_campo(campo, list(fatti))
        parole = [p.lower() for p in campo.get("parole_documento", [])]
        trovati = [n for n in nomi_documenti if any(p in n.lower() for p in parole)] if parole else []
        if not trovati and "documenti.nomi" in campo["fonte"].get("percorsi", []):
            trovati = list(nomi_documenti)
        if valore is not None:
            voce.update(stato="compilato", valore=valore, fonte="gestionale")
        elif letti:
            voce.update(stato="da_confermare", fonte="documenti letti",
                        valore="; ".join(getattr(f, "etichetta", "") or getattr(f, "valore", "") for f in letti))
        elif trovati:
            voce.update(stato="documento_presente", fonte="documenti del fascicolo", valore="; ".join(trovati))
        elif campo["fonte"]["tipo"] == "calcolo":
            voce.update(stato="calcolo", fonte="calcolo del software", regola=campo["fonte"]["regola"],
                        spiegazione=campo["fonte"]["regola"])
            voce.update(_termine_calcolato(campo["fonte"].get("termine"), fatti, oggi))
        elif campo["fonte"]["tipo"] == "lex":
            voce.update(stato="proposta_lex", fonte="proposta di Lex da confermare", compito=campo["fonte"]["compito"])
        else:
            voce.update(stato="da_chiedere" if campo["obbligatorio"] or campo["fonte"]["tipo"] == "avvocato" else "facoltativo")
            if voce["stato"] == "da_chiedere":
                domande.append({"campo": campo["campo"], "obbligatorio": campo["obbligatorio"],
                                "domanda": campo["fonte"].get("domanda") or f"Indica: {campo['etichetta'][0].lower()}{campo['etichetta'][1:]}.",
                                "se_manca": campo.get("se_manca", "")})
        campi.append(voce)
    domande.sort(key=lambda d: not d["obbligatorio"])
    return {"scheda": scheda["id"], "titolo": scheda["titolo"], "campi": campi, "domande": domande,
            "scrive_lex": scheda["scrive_lex"], "astensione": scheda["astensione"],
            "base_normativa": scheda["base_normativa"]}
