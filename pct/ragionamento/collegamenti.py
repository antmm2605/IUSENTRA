"""I fascicoli della stessa vicenda: il titolo esecutivo in un fascicolo, il precetto e l'esecuzione in un altro.

Lo studio apre spesso un fascicolo per il monitorio (ricorso e decreto ingiuntivo) e un altro per l'esecuzione
(precetto, pignoramento). Ciascuno, letto da solo, sbaglia: l'esecuzione chiede il titolo esecutivo che sta nel primo
(art. 474 c.p.c.), il monitorio propone di notificare un precetto già notificato (art. 480 c.p.c.). Il collegamento
si fa solo su fonti certe, mai per somiglianza:

- i fascicoli hanno lo stesso cliente (la raccolta propone solo quelli);
- l'atto dell'esecuzione (precetto, pignoramento, istanza) cita il decreto con numero e anno («decreto ingiuntivo
  n. 1109/2024») e l'ufficio che lo ha pronunciato;
- nel fascicolo del monitorio c'è il decreto con lo stesso numero e anno (e, se c'è, il provvedimento che lo dichiara
  esecutivo, art. 647 c.p.c.); nel fascicolo dell'esecuzione c'è l'atto di precetto che lo cita.

Modulo puro.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .testo import pulito, semplice

_RE_DECRETO = re.compile(r"decreto\s+ingiuntivo\s*(?:n\.?|nr\.?|numero|n°)\s*(\d{1,6})\s*/\s*(\d{4})", re.I)
_RE_ESECUTIVO = re.compile(r"dichiara\s+esecutiv\w*\s+il\s+decreto\s+ingiuntivo\s*(?:n\.?|numero|n°)\s*(\d{1,6})\s*/\s*(\d{4})", re.I)
_RE_PRECETTO = re.compile(r"\batto\s+di\s+precetto\b|\bprecetto\b[^.]{0,200}\bintima\b|\bintima\b[^.]{0,300}\bprecetto\b", re.I)
_RE_PIGNORAMENTO = re.compile(r"pignoramento\s+presso\s+terzi|atto\s+di\s+pignoramento|\bho\s+pignorato\b", re.I)
_PAROLE_UFFICIO = re.compile(r"(?:tribunale|giudice\s+di\s+pace|corte\s+d.appello)\s+(?:ordinario\s+|civile\s+)?di\s+([a-z' ]{3,30})", re.I)


def _citta(ufficio: str) -> str:
    m = _PAROLE_UFFICIO.search(semplice(ufficio))
    return m.group(1).strip().split()[0] if m else ""


def decreti_citati(testo: str, *, ufficio: str = "") -> set[tuple[str, str]]:
    """I decreti ingiuntivi citati con numero e anno; con ``ufficio``, solo se l'ufficio è nominato vicino."""
    citta = _citta(ufficio)
    esito = set()
    for m in _RE_DECRETO.finditer(str(testo or "")):
        intorno = semplice(testo[max(0, m.start() - 250):m.end() + 250])
        if citta and citta not in intorno:
            continue
        esito.add((str(int(m.group(1))), m.group(2)))
    return esito


def _decreto_del_fascicolo(documenti: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Il decreto ingiuntivo pronunciato (con «ingiunge») e, se c'è, il provvedimento che lo dichiara esecutivo."""
    decreti: dict[tuple[str, str], dict[str, Any]] = {}
    for doc in documenti:
        testo = str(doc.get("testo") or "")
        testa = semplice(testo[:400])
        m = _RE_DECRETO.search(testa)
        if m and re.search(r"\bingiunge\b", semplice(testo)):
            decreti.setdefault((str(int(m.group(1))), m.group(2)), {})["decreto"] = doc
    for doc in documenti:
        for m in _RE_ESECUTIVO.finditer(semplice(doc.get("testo") or "")):
            chiave = (str(int(m.group(1))), m.group(2))
            if chiave in decreti:
                decreti[chiave]["esecutorieta"] = doc
    return decreti


def _data_dell_atto(testo: str) -> str:
    """La data di pronuncia scritta in calce («PALMI, 20-12-2024»): l'ultima data del testo. La data del documento
    nel fascicolo può essere quella dell'importazione e non si usa."""
    from .testo import date_nel_testo

    date = date_nel_testo(str(testo or "")[-600:])
    return date[-1][2].isoformat() if date else ""


def _breve(doc: dict[str, Any] | None) -> dict[str, str]:
    if not doc:
        return {}
    return {"id": str(doc.get("id") or ""), "nome": str(doc.get("nome") or ""), "data": _data_dell_atto(doc.get("testo") or "")}


def titolo_nei_collegati(citanti: Iterable[Any], collegati: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """Il titolo esecutivo citato dagli atti dell'esecuzione e presente in un fascicolo collegato."""
    for collegato in collegati:
        decreti = _decreto_del_fascicolo(collegato.get("documenti") or [])
        for atto in citanti:
            for chiave in decreti_citati(atto.testo, ufficio=collegato.get("ufficio") or ""):
                trovato = decreti.get(chiave)
                if not trovato:
                    continue
                m = next(_RE_DECRETO.finditer(atto.testo))
                return {"fascicolo_id": collegato.get("id"), "rg": collegato.get("rg"), "ufficio": collegato.get("ufficio"),
                        "relazione": "titolo_esecutivo", "decreto_numero": "/".join(chiave),
                        "decreto": _breve(trovato.get("decreto")), "esecutorieta": _breve(trovato.get("esecutorieta")),
                        "citato_in": {"id": atto.id, "nome": atto.nome, "data": atto.data,
                                      "brano": pulito(atto.testo[max(0, m.start() - 120):m.end() + 160])}}
    return None


def esecuzione_nei_collegati(numero: tuple[str, str], ufficio: str, collegati: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """Il precetto (e il pignoramento) fondati sul decreto del monitorio, nel fascicolo collegato dell'esecuzione."""
    for collegato in collegati:
        precetto = pignoramento = None
        for doc in collegato.get("documenti") or []:
            testo = str(doc.get("testo") or "")
            if numero not in decreti_citati(testo, ufficio=ufficio):
                continue
            if precetto is None and _RE_PRECETTO.search(testo[:4000]) and not _RE_PIGNORAMENTO.search(testo[:600]):
                precetto = doc
            elif pignoramento is None and _RE_PIGNORAMENTO.search(testo[:600]):
                pignoramento = doc
        if precetto:
            return {"fascicolo_id": collegato.get("id"), "rg": collegato.get("rg"), "ufficio": collegato.get("ufficio"),
                    "relazione": "esecuzione", "decreto_numero": "/".join(numero),
                    "precetto": _breve(precetto), "pignoramento": _breve(pignoramento)}
    return None


def descrizione(collegamento: dict[str, Any]) -> str:
    """Il fascicolo collegato in chiaro: «fascicolo collegato RG 4202/2024, GIUDICE DI PACE DI PALMI»."""
    parti = [f"RG {collegamento['rg']}" if collegamento.get("rg") else "", str(collegamento.get("ufficio") or "")]
    return "fascicolo collegato " + ", ".join(p for p in parti if p) + f" (id {collegamento.get('fascicolo_id')})"


def numero_del_decreto(atti: Iterable[Any]) -> tuple[str, str] | None:
    """Il numero del decreto ingiuntivo pronunciato nella causa (dal decreto stesso)."""
    for atto in atti:
        if atto.autore == "giudice" and atto.testo and re.search(r"\bingiunge\b", semplice(atto.testo)):
            m = _RE_DECRETO.search(semplice(atto.testo[:400]))
            if m:
                return str(int(m.group(1))), m.group(2)
    return None


__all__ = ["decreti_citati", "descrizione", "esecuzione_nei_collegati", "numero_del_decreto", "titolo_nei_collegati"]
