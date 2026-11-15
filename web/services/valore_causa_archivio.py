"""Valore dichiarato all'iscrizione, dai testi del fascicolo già in archivio."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from pct.registro_letture.fatti_repository import Fatto
from web.services.contributo_stato_runtime import href_documento

CAMPO_VALORE = "valore_dichiarato_iscrizione"
_VERSIONE = "valore-iscrizione:v1"
_NOTA = re.compile(r"\bnota\s+d(?:i\s+|[’']\s*)iscrizione\s+a\s+ruolo\b", re.I)
_NUMERO = r"(?:[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)(?:,[0-9]{2})?"
_VALORE = re.compile(rf"\bvalore\s+dell[ae]\s+(?:controversia|causa|lite)\s*[:=]\s*(?:€\s*|euro\s+)?({_NUMERO})(?![\d.,])", re.I)
_DOMANDA = re.compile(rf"\b(?:somma|importo)\s+di\s+(?:€\s*|euro\s+)({_NUMERO})(?![\d.,])", re.I)
_DEPOSITO_ATTO = re.compile(r"deposito telematico\s*:\s*(?:ricorso|(?:atto di )?citazione|atto introduttivo)\b", re.I)
_RG = re.compile(r"\br\.?\s*g\.?\s*[:n. ]*([0-9]+)\s*[/\-–]\s*([0-9]{4})\b", re.I)


def _normalizza(valore: Any) -> str:
    return " ".join(re.findall(r"\w+", str(valore or "").casefold()))


def _importi(pattern: re.Pattern[str], testo: str) -> set[Decimal]:
    return {Decimal(v.replace(".", "").replace(",", ".")) for v in pattern.findall(testo)}


def _identita(testo: str, ufficio: str, cliente: str) -> bool:
    normalizzato = f" {_normalizza(testo)} "
    parole = _normalizza(cliente).split()
    return bool(ufficio and f" {ufficio} " in normalizzato and len(parole) >= 2
                and any(f" {nome} " in normalizzato for nome in (" ".join(parole), " ".join(reversed(parole)))))


def registra_valore_iscrizione(fascicolo: Any, registro: Any, tenant: str) -> int:
    """Riusa il testo salvato all'arrivo delle fonti, con riscontro di ruolo nel deposito."""
    note = [d for d in fascicolo.documenti if _NOTA.search(str(d.nome))]
    fid = str(fascicolo.id)
    if not note:
        return 0
    precedenti = {f.oggetto_id: f for f in registro.fatti(tenant, fid, campo=CAMPO_VALORE, verifiche=None)}
    from web.services.archivio_letture_runtime import testi_indice_archivio

    oggetti = {o.oggetto_id: o for o in registro.oggetti(tenant, fid) if o.tipo == "documento" and o.presente}
    testi = testi_indice_archivio(fascicolo)
    ruolo = (str(fascicolo.numero_rg or "").lstrip("0"), str(fascicolo.anno_rg or ""))
    ufficio = _normalizza(fascicolo.tribunale)
    cliente = str(fascicolo.nome_cliente or "")
    depositi = {}
    for documento in fascicolo.documenti:
        oid = str(documento.id)
        testo = testi.get(oid, "")
        nome = str(documento.nome)
        if oid not in oggetti or not _DEPOSITO_ATTO.search(nome) or not testo:
            continue
        ruoli = {(n.lstrip("0"), anno) for n, anno in _RG.findall(nome)}
        if ruolo in ruoli and _identita(testo, ufficio, cliente):
            depositi[oid] = _importi(_DOMANDA, testo)
    scritti = 0
    for nota in note:
        oid = str(nota.id)
        oggetto = oggetti.get(oid)
        if oggetto is None:
            continue
        testo = " ".join(testi.get(oid, "").split())
        valori = _importi(_VALORE, testo)
        fatti = []
        if len(valori) == 1 and _NOTA.search(testo[:500]) and _identita(testo, ufficio, cliente):
            valore = next(iter(valori))
            ruoli = {(n.lstrip("0"), anno) for n, anno in _RG.findall(testo[:850])}
            conferme = sorted(ref for ref, importi in depositi.items() if valore in importi and ref != oid)
            if valore > 0 and (ruoli == {ruolo} or (not ruoli and conferme)):
                fonti = {ref: oggetti[ref].impronta for ref in [oid, *conferme]}
                fatti.append(Fatto(
                    categoria="importo", campo=CAMPO_VALORE, valore=f"{valore:.2f}",
                    etichetta="Valore dichiarato all'iscrizione", verifica="verificata",
                    origine="nota_iscrizione_ruolo", prove=[{"impronte_documenti": fonti}],
                ))
        precedente = precedenti.get(oid)
        if precedente and fatti and precedente.sha256 == oggetto.impronta and precedente.prove == fatti[0].prove and precedente.valore == fatti[0].valore:
            continue
        if precedente is None and not fatti:
            continue
        esito = registro.registra_fatti(tenant, fid, oggetto, "documenti", fatti, versione=_VERSIONE, campo=CAMPO_VALORE)
        scritti += esito["nuovi"] + esito["aggiornati"] + esito["rimossi"]
    return scritti


def valore_iscrizione(fascicolo: Any, fatti: list[Any], oggetti: list[Any]) -> dict[str, Any]:
    """Proietta l'esito registrato, a parità di fonti, senza leggere gli atti."""
    documenti = {str(d.id): d for d in fascicolo.documenti}
    impronte = {o.oggetto_id: o.impronta for o in oggetti if o.presente and o.tipo == "documento"}
    fonti = {}
    for fatto in fatti:
        if fatto.campo != CAMPO_VALORE or fatto.verifica not in {"verificata", "corretta"}:
            continue
        if fatto.oggetto_id not in documenti or impronte.get(fatto.oggetto_id) != fatto.sha256:
            continue
        for prova in fatto.prove:
            attese = prova.get("impronte_documenti") or {}
            if attese and all(sha and impronte.get(ref) == sha for ref, sha in attese.items()):
                fonti[fatto.oggetto_id] = fatto.valore
    if not fonti or len(set(fonti.values())) != 1:
        return {}
    oid, importo = next(iter(sorted(fonti.items())))
    registrato = getattr(fascicolo, "valore_causa", None)
    if registrato and Decimal(str(registrato)) != Decimal(importo):
        return {}
    return {"importo": float(importo), "documento": {
        "id": oid, "nome": documenti[oid].nome, "href": href_documento(str(fascicolo.id), oid),
    }}
