"""Recupero puntuale di norme pubbliche tramite il motore di acquisizione nativo.

Non contiene casi del banco. La richiesta contiene soltanto identita normative,
mai nomi, fatti o testi riservati. Si usa nel comando applicativo, mai nelle GET.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

from pct.legal_update_job_queue import LegalUpdateJobQueue

from .acquisizione import acquisisci
from .fabbisogno import Riferimento
from .identita import risolvi_articolo
from .lettura import leggi_articoli
from .riferimenti import FonteAtto, fonte_per_chiave


def recupera(db: Path, richieste: list[dict], *, data_riferimento: date, cartella: Path,
             acquisitore=None) -> dict:
    """Ogni richiesta e tipizzata; backup/versioni/FTS spettano all'importatore.

    Una richiesta gia presente non scarica nuovamente. Le impronte di approvazione
    del fascicolo non vengono prodotte da questa funzione.
    """
    if len(richieste) > 20:
        raise ValueError("Troppi riferimenti in un singolo recupero")
    queue = LegalUpdateJobQueue(Path(cartella)/"acquisizioni.sqlite")
    queue.recover_stale_running()
    acquisitore = acquisitore or acquisisci
    results = []
    failed_acts = set()
    for ref in richieste:
        identity = {"chiave":ref["chiave"],"articolo":ref["articolo"],"edizione":data_riferimento.isoformat()}
        read_ref={"chiave":identity["chiave"],"articolo":identity["articolo"],"data_riferimento":data_riferimento.isoformat()}
        read = leggi_articoli(db,[read_ref])
        if read["lettura_completa"]:
            # Chiude soltanto la richiesta già accodata per lo stesso articolo e
            # la stessa edizione. Nessuna scansione o nuovo job per un cache hit.
            canonical = read["articoli"][0]["chiave"]
            for key_name in dict.fromkeys([identity["chiave"], canonical]):
                payload = dict(identity, chiave=key_name, data_riferimento=data_riferimento.isoformat())
                dedupe = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                with queue.connect() as connection:
                    pending = connection.execute(
                        "SELECT job_id FROM legal_update_jobs WHERE dedupe_key=? AND source_code='normativa_puntuale' AND item_kind='articolo' AND status='queued'",
                        (dedupe,),
                    ).fetchall()
                for job_row in pending:
                    queue.complete(job_row["job_id"], result={"gia_presente":True,
                        "impronte":[a["sha256_testo"] for a in read["articoli"]]})
            results.append({"riferimento":identity,"stato":"gia_presente","lettura":read});continue
        # Gli alias tipizzati possono corrispondere a chiavi storiche N/AAAA.
        # La partizione canonica viene dall'articolo gia censito, non dal modello.
        with sqlite3.connect(Path(db).resolve().as_uri()+"?mode=ro",uri=True) as conn:
            previous=risolvi_articolo(conn,{"chiave":ref["chiave"],"articolo":ref["articolo"]})
        canonical=ref["chiave"]
        known_urn=""
        if len(previous)==1:
            canonical=previous[0][0]["collection_name"].removeprefix("Lex fonti: ")
            known_urn=previous[0][0].get("urn") or ""
        source = fonte_per_chiave(canonical)
        if source.tipo=="non_deducibile" and known_urn.startswith("urn:nir:"):
            source=FonteAtto(canonical,"normattiva",urn=known_urn)
        identity["chiave"]=canonical
        if source.tipo == "non_deducibile":
            results.append({"riferimento":identity,"stato":"identita_non_deducibile"});continue
        payload = dict(identity,data_riferimento=data_riferimento.isoformat())
        key = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        job = queue.enqueue(source_code="normativa_puntuale",item_kind="articolo",payload=payload,
                            dedupe_key=key,max_attempts=2,timeout_seconds=180)
        act_key = (source.urn or source.celex, data_riferimento.isoformat())
        if act_key in failed_acts:
            results.append({"riferimento":identity,"stato":job.status,"job_id":job.job_id,
                            "dettaglio":"Un solo tentativo di rete per atto ed edizione nel medesimo lotto; richiesta preservata"})
            continue
        claimed = queue.claim(job.job_id,worker_id="normativa-puntuale")
        if claimed is None:
            results.append({"riferimento":identity,"stato":job.status,"job_id":job.job_id});continue
        try:
            req = Riferimento("ricerca_puntuale",canonical,ref["articolo"],"richiesta normativa","ricerca")
            report = acquisitore(Path(db),Path(cartella)/"pacchetti"/job.job_id,
                                 oggi=date.today(),versione_al=data_riferimento,riferimenti=[req],fonti_note={canonical:source})
            fresh = leggi_articoli(db,[{"chiave":identity["chiave"],"articolo":identity["articolo"],"data_riferimento":data_riferimento.isoformat()}])
            if not fresh["lettura_completa"]:
                raise ValueError("La fonte acquisita non contiene un riscontro univoco dell'articolo richiesto")
            queue.complete(job.job_id,result={"rapporto":report.to_dict(),"impronte":[a["sha256_testo"] for a in fresh["articoli"]]})
            results.append({"riferimento":identity,"stato":"acquisito","job_id":job.job_id,"lettura":fresh})
        except (OSError,ValueError,RuntimeError) as exc:
            failed_acts.add(act_key)
            failed = queue.fail(job.job_id,error=str(exc))
            results.append({"riferimento":identity,"stato":failed.status,"job_id":job.job_id,"errore":failed.last_error})
    return {"esiti":results}


def riprendi_pendenti(db: Path, cartella: Path, *, limite: int = 20) -> list[dict]:
    """Ripresa notturna dei soli oggetti accodati: nessuna scansione delle leggi."""
    path=Path(cartella)/"acquisizioni.sqlite"
    if not path.is_file():return []
    queue=LegalUpdateJobQueue(path);queue.recover_stale_running()
    results=[]
    for job in queue.list_jobs(status="queued",limit=min(max(limite,1),20)):
        payload=job.payload or {}
        when=date.fromisoformat(payload["data_riferimento"])
        recovered=recupera(db,[{"chiave":payload["chiave"],"articolo":payload["articolo"]}],
                           data_riferimento=when,cartella=cartella)["esiti"]
        results.extend({k:v for k,v in item.items() if k!="lettura"} for item in recovered)
    return results
