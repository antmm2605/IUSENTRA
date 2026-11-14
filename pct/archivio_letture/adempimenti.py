"""Prove già lette: non deduce un adempimento dalla sola scadenza trascorsa."""
from __future__ import annotations
import re
from typing import Any, Iterable


def perentorieta_documentata(fatto: Any) -> bool:
    if fatto.verifica not in {"verificata", "corretta"} or fatto.campo != "termine":
        return False
    if any(p.get("codice") == "perentorieta_documentata" and p.get("esito") == "ok" for p in fatto.prove):
        return True
    # L'attributo deve riguardare proprio la data di questo fatto, non un'altra
    # data citata nello stesso estratto (per esempio la sottoscrizione). La regola è
    # quella del termine scritto (pct/provvedimenti/termine_scritto, artt. 152-153 c.p.c.):
    # «termine perentorio del 16.12.2026» è perentorio come «… fino al …» (collaudo 10/11/2026).
    from pct.provvedimenti.termine_scritto import perentorio_dichiarato

    token = str(fatto.valore_letto or "").strip()
    contesto = " ".join(str(fatto.contesto or "").split())
    for trovato in re.finditer(re.escape(token), contesto) if token else ():
        if not contesto[trovato.end():trovato.end() + 1].isdigit() and perentorio_dichiarato(contesto, trovato.start(), trovato.end()):
            return True
    return False


def prove_note_depositate(fatti: Iterable[Any]) -> list[dict[str, Any]]:
    """Un provvedimento attesta il deposito e rinvia a una nuova data.

    Richiede un unico precedente termine per note nel medesimo oggetto e
    nella medesima impronta. Se il collegamento è ambiguo non conclude nulla.
    """
    gruppi: dict[tuple[str, str, str], list[Any]] = {}
    for f in fatti:
        if f.verifica not in {"verificata", "corretta"} or f.campo != "termine" or not f.sha256:
            continue
        if not any(p.get("codice") == "modalita_note" and p.get("esito") == "ok" for p in f.prove):
            continue
        gruppi.setdefault((f.tipo, f.oggetto_id, f.sha256), []).append(f)
    prove = []
    for (tipo, oid, sha), gruppo in gruppi.items():
        for esito in gruppo:
            testo = " ".join(esito.contesto.casefold().split())
            if not re.search(r"in esito al deposito (?:di|delle) note scritte.{0,50}rinvia", testo):
                continue
            precedenti = [f for f in gruppo if f.posizione < esito.posizione and f.valore[:10] < esito.valore[:10] and re.search(r"dà atto che l[’']udienza", f.contesto, re.I)]
            giorni = {f.valore[:10] for f in precedenti}
            if len(giorni) != 1:
                continue
            prove.append({"giorno": next(iter(giorni)), "nuovo_termine": esito.valore[:10], "tipo": tipo, "oggetto_id": oid, "sha256": sha, "fatti": sorted({esito.id, *(f.id for f in precedenti)}), "estratto": esito.contesto})
    return prove
