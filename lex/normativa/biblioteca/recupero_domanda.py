"""Recupero automatico del riferimento esatto nel comando autenticato di Lex.

Le GET di consultazione non acquisiscono nulla; non vengono trasmessi fatti o
nomi a fonti pubbliche. Il recupero usa soltanto tipo/numero/anno/articolo.
"""
from __future__ import annotations

from datetime import date,datetime
from pathlib import Path
import sqlite3
import re
from zoneinfo import ZoneInfo

from .recupero import recupera


def assicura_biblioteca(db: Path) -> None:
    if db.is_file():return
    from lex.normativa.normattiva_importer import ensure_schema,migra_schema
    from lex.ricerca_giuridica.indice_fts import sincronizza_fts

    db.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db) as c:
        ensure_schema(c);migra_schema(c);sincronizza_fts(c)


def riferimento_domanda(domanda: str) -> dict | None:
    from lex.testi_ufficiali import CODICI,riconosci_articolo

    ref=riconosci_articolo("testo "+domanda)
    if ref is None:return None
    if ref.urn:
        found=next((c for c in CODICI if c.urn==ref.urn),None)
        keys={"cc":"codice_civile","cpc":"codice_procedura_civile","cpp":"codice_procedura_penale","cp":"codice_penale","cost":"costituzione"}
        key=keys.get(found.chiave) if found else None
    else:
        tipo,anno,numero=ref.urn_parti
        prefix={"stato:legge":"legge","decreto.legislativo":"dlgs","decreto.legge":"dl","presidente.repubblica:decreto":"dpr"}.get(tipo)
        key=f"{prefix}_{numero}_{anno}" if prefix else None
    return {"chiave":key,"articolo":ref.chiave} if key else None


def recupera_nel_comando(domanda: str) -> dict | None:
    from flask import g,has_request_context,request

    if not has_request_context() or request.method!="POST":return None
    if re.search(r"\b(?:solo|soltanto)\s+(?:l[’']?\s*)?(?:archivio|biblioteca|locale)\b", domanda, re.IGNORECASE):
        return None
    user=g.get("utente_corrente")
    check=getattr(user,"ha_permesso",lambda _p:False)
    if not (check("ai.usa") or check("fascicoli.leggi")):return None
    ref=riferimento_domanda(domanda)
    if not ref:return None
    from lex.retrieval.normativa_catalog import library_path,runtime_general_path

    db=library_path(runtime_general_path());assicura_biblioteca(db)
    explicit=re.search(r"(?:vigente|versione|testo)\s+(?:alla\s+data\s+del|al)\s+(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})",domanda,re.IGNORECASE)
    when=datetime.now(ZoneInfo("Europe/Rome")).date()
    if explicit:
        value=explicit[1]
        when=datetime.strptime(value,"%d/%m/%Y").date() if "/" in value else date.fromisoformat(value)
    result=recupera(db,[ref],data_riferimento=when,cartella=db.parent/"recuperi_normativi")
    for item in result["esiti"]:
        if item["stato"] in {"gia_presente","acquisito"} and item.get("lettura",{}).get("articoli"):
            return {"db":db,"articolo":item["lettura"]["articoli"][0],"data_riferimento":when.isoformat()}
    return None
