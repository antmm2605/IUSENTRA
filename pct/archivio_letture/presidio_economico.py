"""Una proiezione del CU dalle prove correnti, con tutte le fonti consultabili."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from pct.registro_letture.fatti_repository import Fatto
from pct.registro_letture.verifica_date import interpreta_data

UTILI = {"verificata", "corretta", "plausibile"}


def _prove(fatto: Fatto) -> dict[str, dict[str, str]]:
    return {str(p.get("codice")): p for p in fatto.prove if isinstance(p, dict)}


def _dettaglio(prove: dict[str, dict[str, str]], codice: str) -> str:
    return str(prove.get(codice, {}).get("dettaglio") or "")


def contributo_verificato(fatti: Iterable[Fatto]) -> dict[str, Any] | None:
    correnti = [f for f in fatti if f.verifica in UTILI and f.campo in {
        "contributo_unificato", "esenzione_cu_dichiarata", "pagamento_cu_non_verificato"}]
    if not correnti:
        return None
    fonti: list[dict[str, Any]] = []
    mancanti: list[str] = []
    versamenti: dict[str, Decimal] = {}
    senza_iuv: set[str] = set()
    importi_letti: list[str] = []
    dichiarazioni: list[tuple[Fatto, dict[str, Any]]] = []
    ricevute_valide: list[Fatto] = []
    identificativi: dict[str, set[tuple[str, ...]]] = {}
    for fatto in correnti:
        prove = _prove(fatto)
        fonte = {"fattoId": fatto.id, "documentoId": fatto.oggetto_id, "tipo": fatto.tipo,
                 "sha256": fatto.sha256, "campo": fatto.campo, "verifica": fatto.verifica,
                 "contesto": fatto.contesto, "prove": list(fatto.prove)}
        fonti.append(fonte)
        if fatto.campo == "esenzione_cu_dichiarata":
            try:
                dichiarazione = json.loads(_dettaglio(prove, "dichiarazione_economica"))
            except (ValueError, TypeError):
                dichiarazione = {}
            dichiarazioni.append((fatto, dichiarazione))
            continue
        if fatto.campo == "pagamento_cu_non_verificato":
            mancanti.append(_dettaglio(prove, "ricevuta_economica") or fatto.contesto)
            continue
        try:
            importo = Decimal(fatto.valore)
            if not importo.is_finite() or importo <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            mancanti.append("L'importo della ricevuta non è valido.")
            continue
        importi_letti.append(str(importo.quantize(Decimal("0.01"))))
        difetti = [str(prove.get(c, {}).get("dettaglio") or descrizione)
                   for c, descrizione in (
                       ("cliente_economico", "Nome e cognome del cliente non verificati nel contenuto."),
                       ("rg_economico", "Numero e anno RG non verificati nel contenuto."))
                   if prove.get(c, {}).get("esito") != "ok"]
        if fatto.verifica == "plausibile":
            difetti.append("Lettura ottica del pagamento da confermare con la fonte.")
        if _dettaglio(prove, "stato") != "pagato":
            difetti.append("Il documento non prova un pagamento eseguito.")
        if interpreta_data(_dettaglio(prove, "data")) is None:
            difetti.append("Data del pagamento assente o non valida nella prova.")
        if "ricevuta_economica" in prove and prove["ricevuta_economica"].get("esito") != "ok":
            difetti.append(_dettaglio(prove, "ricevuta_economica"))
        if not fatto.sha256:
            difetti.append("Impronta della fonte non disponibile.")
        if difetti:
            mancanti.extend(difetti)
            continue
        iuv = _dettaglio(prove, "iuv_economico")
        iur = tuple(sorted(set(v.strip() for v in _dettaglio(prove, "iur_economico").split(",") if v.strip())))
        chiave = "iuv:" + iuv + "|iur:" + ",".join(iur) if iuv else "sha:" + fatto.sha256
        if iuv:
            identificativi.setdefault(iuv, set()).add(iur)
        if not iuv:
            senza_iuv.add(chiave)
        if chiave in versamenti and versamenti[chiave] != importo:
            mancanti.append("La stessa ricevuta riporta importi discordanti nelle letture: verifica le fonti.")
        versamenti[chiave] = importo
        ricevute_valide.append(fatto)
    for gruppi in identificativi.values():
        if len(gruppi) > 1:
            if () in gruppi or any(set(a) & set(b) for a in gruppi for b in gruppi if a != b):
                mancanti.append("Ricevute con lo stesso IUV e identificativi di riscossione incompleti o sovrapposti: verifica le fonti prima di sommare.")
    if len(versamenti) > 1 and senza_iuv:
        mancanti.append("Più ricevute prive di un identificativo comune: verifica che siano versamenti distinti.")
    pagato = bool(versamenti) and not mancanti
    if not pagato and dichiarazioni:
        effettive = [(f, d) for f, d in dichiarazioni if d.get("tipo") == "autocertificazione"]
        principali = effettive or dichiarazioni
        fonte_principale = principali[0][0]
        mancanti.append("Esenzione dichiarata: verifica l'autocertificazione riferita alla pratica, l'ultima dichiarazione dei redditi e la sottoscrizione.")
        if not effettive:
            mancanti.append("Il richiamo all'esenzione nell'atto non dimostra da solo i requisiti reddituali.")
    else:
        fonte_principale = max(ricevute_valide, key=lambda f: (interpreta_data(_dettaglio(_prove(f), "data")), f.id)) if ricevute_valide else correnti[0]
    mancanti = list(dict.fromkeys(m for m in mancanti if m))
    return {
        "status": "pagato" if pagato else "da_registrare", "previsto": True, "pagato": pagato,
        "importo": float(sum(versamenti.values())) if pagato else None,
        "data_pagamento": _dettaglio(_prove(fonte_principale), "data") if pagato else "",
        "documento_id": fonte_principale.oggetto_id, "fattoId": fonte_principale.id,
        "richiedeConferma": not pagato, "fontiVerifica": fonti, "verificheMancanti": mancanti,
        "importiLetti": list(dict.fromkeys(importi_letti)),
        "note": "Versamento verificato sul contenuto, cliente e RG; copie della stessa ricevuta conteggiate una volta."
        if pagato else " ".join(mancanti),
    }
