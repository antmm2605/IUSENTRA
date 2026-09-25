"""Dati dei moduli PAT XFA: il pacchetto «datasets» come lo salva Adobe Reader.

I moduli di deposito della Giustizia amministrativa (ModuloDepositoRicorso,
ModuloDepositoAtto, …) sono PDF XFA con diritti d'uso di Adobe Reader
(firma UR3: compilazione, allegati incorporati, salvataggio). Chi li compila
non tocca il modello (pacchetto «template»): scrive i valori nel pacchetto
«datasets» e salva in aggiornamento incrementale, così la firma UR3 resta
valida e il modulo si apre in Reader con «Carica ricorso», «Carica documento»
e il salvataggio attivi. Il modulo va poi firmato PAdES con gli allegati
dentro (regole tecnico-operative PAT, d.P.C.S. 2025; art. 136 c.p.a.).

Qui c'è il legame fra modello e dati secondo le regole XFA di associazione
normale: un sottomodulo con nome è un gruppo di dati, uno senza nome è
trasparente, un campo o un gruppo di opzioni è un valore, ciò che ha
``bind match="none"`` (i pulsanti) non ha dati, ``match="dataRef"`` punta al
percorso indicato. Le istanze ripetute sono gruppi omonimi nell'ordine del
modulo.
"""

from __future__ import annotations

import copy
from typing import Iterator
from xml.etree import ElementTree as ET

NS_DATI = "http://www.xfa.org/schema/xfa-data/1.0/"
CONTENITORI = {"subform", "subformSet", "area"}
DA_SALTARE = {"pageSet", "proto", "variables", "draw", "occur", "bind", "event", "script", "calculate", "validate",
              "value", "items", "caption", "ui", "font", "margin", "para", "border", "assist", "traversal", "keep",
              "breakBefore", "breakAfter", "overflow", "desc", "extras", "setProperty", "connect", "format", "speak"}


def _nome_locale(tag: object) -> str:
    return tag.split("}", 1)[-1] if isinstance(tag, str) else ""


def _figli(elemento: ET.Element, nome: str) -> Iterator[ET.Element]:
    return (figlio for figlio in elemento if _nome_locale(figlio.tag) == nome)


def _associazione(elemento: ET.Element) -> tuple[str, str]:
    bind = next(_figli(elemento, "bind"), None)
    if bind is None:
        return "once", ""
    return bind.get("match") or "once", bind.get("ref") or ""


def valore(campo: ET.Element) -> str:
    """Il valore scritto nel campo del modello (testo, numero o data)."""
    nodo = next(_figli(campo, "value"), None)
    if nodo is None:
        return ""
    for figlio in nodo:
        if figlio.text and figlio.text.strip():
            return figlio.text.strip()
    return ""


def _valori_opzione(campo: ET.Element) -> list[str]:
    elenchi = list(_figli(campo, "items"))
    salvati = next((items for items in elenchi if items.get("save") == "1"), elenchi[0] if elenchi else None)
    return [figlio.text or "" for figlio in salvati] if salvati is not None else []


def _valore_gruppo(gruppo: ET.Element) -> str:
    for campo in _figli(gruppo, "field"):
        scelto = valore(campo)
        if scelto:
            opzioni = _valori_opzione(campo)
            return scelto if not opzioni or scelto in opzioni else opzioni[0]
    return ""


def _percorso(radice: ET.Element, ref: str) -> ET.Element:
    parti = [parte for parte in ref.removeprefix("$record.").removeprefix("$data.").removeprefix("$.").split(".") if parte]
    if parti and parti[0] == _nome_locale(radice.tag):
        parti = parti[1:]
    nodo = radice
    for parte in parti:
        trovato = next((figlio for figlio in nodo if figlio.tag == parte), None)
        nodo = trovato if trovato is not None else ET.SubElement(nodo, parte)
    return nodo


def _dati_da(elemento: ET.Element, gruppo: ET.Element, radice: ET.Element) -> None:
    for figlio in elemento:
        tipo = _nome_locale(figlio.tag)
        if tipo in DA_SALTARE or not tipo:
            continue
        corrispondenza, ref = _associazione(figlio)
        nome = figlio.get("name") or ""
        if tipo in CONTENITORI:
            if tipo == "subform" and nome and corrispondenza not in {"none", "global"}:
                _dati_da(figlio, ET.SubElement(gruppo, nome), radice)
            else:
                _dati_da(figlio, gruppo, radice)
        elif tipo in {"field", "exclGroup"} and nome and corrispondenza != "none":
            testo = valore(figlio) if tipo == "field" else _valore_gruppo(figlio)
            nodo = _percorso(radice, ref) if corrispondenza == "dataRef" and ref else ET.SubElement(gruppo, nome)
            nodo.text = testo


def datasets(modello: ET.Element) -> bytes:
    """Il pacchetto «datasets» con i valori presenti nel modello compilato."""
    principale = next((f for f in modello if _nome_locale(f.tag) == "subform" and f.get("name")), None)
    if principale is None:
        raise ValueError("Il modulo PAT non ha il sottomodulo principale.")
    contenitore = ET.Element(f"{{{NS_DATI}}}datasets")
    radice = ET.SubElement(ET.SubElement(contenitore, f"{{{NS_DATI}}}data"), principale.get("name") or "")
    _dati_da(principale, radice, radice)
    ET.register_namespace("xfa", NS_DATI)
    return ET.tostring(contenitore, encoding="utf-8", xml_declaration=False)


def _massimo(sottomodulo: ET.Element) -> int:
    """Quante istanze del sottomodulo ammette il modello (``occur max``; -1 vuol dire senza limite)."""
    occur = next(_figli(sottomodulo, "occur"), None)
    massimo = int((occur.get("max") if occur is not None else None) or 1)
    return 10_000 if massimo < 0 else massimo


def _unisci(elemento: ET.Element, gruppo: ET.Element | None, radice: ET.Element) -> None:
    usati: dict[str, int] = {}

    def prossimo(nome: str) -> ET.Element | None:
        if gruppo is None:
            return None
        omonimi = [figlio for figlio in gruppo if figlio.tag == nome]
        indice = usati.get(nome, 0)
        usati[nome] = indice + 1
        return omonimi[indice] if indice < len(omonimi) else None

    for figlio in list(elemento):
        tipo = _nome_locale(figlio.tag)
        if tipo in DA_SALTARE or not tipo:
            continue
        corrispondenza, ref = _associazione(figlio)
        nome = figlio.get("name") or ""
        if tipo == "subform" and nome and corrispondenza not in {"none", "global"}:
            disponibili = [] if gruppo is None else [g for g in gruppo if g.tag == nome][usati.get(nome, 0):]
            istanze: list[ET.Element | None] = list(disponibili[: _massimo(figlio)]) or [None]
            usati[nome] = usati.get(nome, 0) + len([i for i in istanze if i is not None])
            posizione = list(elemento).index(figlio)
            for numero, dati in enumerate(istanze):
                copia = figlio if numero == 0 else copy.deepcopy(figlio)
                if numero:
                    elemento.insert(posizione + numero, copia)
                _unisci(copia, dati, radice)
        elif tipo in CONTENITORI:
            _unisci(figlio, gruppo, radice)
        elif tipo in {"field", "exclGroup"} and nome and corrispondenza != "none":
            dati = _percorso(radice, ref) if corrispondenza == "dataRef" and ref else prossimo(nome)
            testo = (dati.text or "") if dati is not None else ""
            campi = [figlio] if tipo == "field" else list(_figli(figlio, "field"))
            for campo in campi:
                scritto = testo if tipo == "field" else (testo if testo in _valori_opzione(campo)[:1] else "")
                spazio = campo.tag[: campo.tag.index("}") + 1] if campo.tag.startswith("{") else ""
                nodo = next(_figli(campo, "value"), None)
                if nodo is None:
                    nodo = ET.SubElement(campo, f"{spazio}value")
                testo_nodo = next(iter(nodo), None)
                if testo_nodo is None:
                    testo_nodo = ET.SubElement(nodo, f"{spazio}text")
                testo_nodo.text = scritto


def modello_compilato(modello: ET.Element, pacchetto_dati: bytes) -> ET.Element:
    """Il modello con i valori del pacchetto «datasets», come lo mostra Reader dopo l'unione."""
    risultato = copy.deepcopy(modello)
    dati = ET.fromstring(pacchetto_dati)
    radice_dati = next((figlio for figlio in next(iter(dati), ET.Element("x"))), None)
    principale = next((f for f in risultato if _nome_locale(f.tag) == "subform" and f.get("name")), None)
    if principale is None or radice_dati is None:
        return risultato
    _unisci(principale, radice_dati, radice_dati)
    return risultato


__all__ = ["NS_DATI", "datasets", "modello_compilato", "valore"]
