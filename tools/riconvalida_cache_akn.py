"""Riconvalida offline di una copia: mai modifica l'archivio originale."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import zipfile
import time
import signal
from lxml import etree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lex.normativa.riconvalida_akn import ArchivioRiscontrato, riconvalida_catena
from lex.normativa.versioni_akn import assicura_schema, impronta_lettore


def sha(path):
    with Path(path).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()


def atomic(path,value):
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    # Windows puo negare la sostituzione mentre un monitor legge lo stato.
    # Non cancellare la destinazione: conserva l ultimo stato e ritenta poco.
    for attempt in range(31):
        try:
            os.replace(temp,path)
            return
        except PermissionError:
            if attempt==30:raise
            time.sleep(0.1)


def archivio_locale(raw,root):
    if raw.startswith("/mnt/d/") and os.name=="nt":raw="D:/"+raw[len("/mnt/d/"):]
    elif raw[:3].lower() in ("d:/","d:\\") and os.name!="nt":raw="/mnt/d/"+raw[3:].replace("\\","/")
    path=Path(raw).resolve(strict=True)
    if not path.is_relative_to(root):raise ValueError("Archivio esterno al deposito autorizzato")
    return path



def riqualifica_metadati(conn, output, state, revision):
    """Nuovo lettore: conserva prove precedenti, ricontrolla tutto senza ricopiare i testi."""
    import re
    old=state.get("lettore_runtime","")
    if not re.fullmatch(r"[0-9a-f]{64}",str(state.get("originale_sha256",""))):
        raise ValueError("Sigillo originale assente nella ripresa")
    if not re.fullmatch(r"[0-9a-f]{64}",old) or not re.fullmatch(r"[0-9a-f]{64}",revision) or old==revision:
        raise ValueError("Cambio lettore non identificato")
    output=Path(output).resolve(strict=True)
    history=output/"storico-lettori"/(old[:12]+"-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    if not history.resolve().is_relative_to(output):raise ValueError("Storico fuori dal dossier")
    history.mkdir(parents=True,exist_ok=False)
    for name in ("stato.json","copia-verificata.json"):
        path=output/name
        if path.exists():shutil.copy2(path,history/name)
    journal=output/"qualificate.jsonl"
    # Soltanto gli attestati: articoli, testi, identita e versioni non cambiano.
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("UPDATE normative_akn_chains SET riscontro_lettore_sha256='',riscontro_contenuti_sha256='' WHERE riscontro_lettore_sha256<>'' OR riscontro_contenuti_sha256<>''")
        conn.commit()
    except BaseException:
        conn.rollback();raise
    if journal.exists():os.replace(journal,history/journal.name)
    result={"lettore_runtime":revision,"originale_sha256":state["originale_sha256"],
        "qualificate":0,"errori":{},"tutti_dati_completati":False,
        "precedente_lettore":old,"prove_precedenti":str(history),"ricontrollo_integrale_richiesto":True}
    atomic(output/"stato.json",result)
    return result


def main():
    if os.name=="nt" and hasattr(signal,"SIGBREAK"):
        signal.signal(signal.SIGBREAK,signal.default_int_handler)
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ("originale","candidato","gate","archivi","prove"):
        ap.add_argument("--"+key,type=Path,required=True)
    ap.add_argument("--esegui",action="store_true")
    ap.add_argument("--riprendi",action="store_true")
    ap.add_argument("--riqualifica-lettore",action="store_true",help="Ricontrolla una copia esistente con il nuovo lettore, conservando lo storico")
    args=ap.parse_args()
    if not args.esegui:raise ValueError("Richiesto --esegui: nessuna operazione implicita")
    if args.riqualifica_lettore and not args.riprendi:raise ValueError("Cambio lettore richiede --riprendi esplicito")
    original=args.originale.resolve(strict=True);target=args.candidato.resolve()
    root=args.archivi.resolve(strict=True);output=args.prove.resolve()
    if original==target or (target.exists() and os.path.samefile(original,target)):
        raise ValueError("Originale e candidato devono essere diversi")
    gate=json.loads(args.gate.read_text(encoding="utf-8-sig"))
    if (gate.get("importazione_manifest_terminata") is not True or gate.get("integrity_check")!="ok"
            or gate.get("foreign_key_check_ok") is not True or len(gate.get("sha256_db_finale",""))!=64):
        raise ValueError("Importazione non conclusa e sigillata")
    if any(original.with_name(original.name+suffix).exists() for suffix in ("-wal","-journal")):
        raise ValueError("Originale ancora in scrittura")
    output.mkdir(parents=True,exist_ok=True);target.parent.mkdir(parents=True,exist_ok=True)
    lock_path=output/"riconvalida.lock"
    lock=os.open(lock_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.write(lock,str(os.getpid()).encode());os.close(lock)
    source_stat=original.stat();revision=impronta_lettore();conn=None;archive=None
    state_path=output/"stato.json";copy_path=output/"copia-verificata.json"
    try:
        if target.exists():
            if not args.riprendi or not copy_path.exists() or not state_path.exists():
                raise ValueError("Candidato preesistente: nessuna sovrascrittura")
            copied=json.loads(copy_path.read_text());state=json.loads(state_path.read_text())
            if (copied.get("originale_sha256")!=gate["sha256_db_finale"] or copied.get("candidato")!=str(target)
                    or copied.get("originale")!=str(original) or copied.get("byte")!=source_stat.st_size
                    or state.get("originale_sha256")!=gate["sha256_db_finale"]):
                raise ValueError("Ripresa riferita a dati diversi")
            if state.get("lettore_runtime")!=revision:
                if not args.riqualifica_lettore:raise ValueError("Ripresa riferita a lettore diverso: ricontrollo esplicito necessario")
                reset=sqlite3.connect(target,timeout=30)
                try:state=riqualifica_metadati(reset,output,state,revision)
                finally:reset.close()
            elif args.riqualifica_lettore:
                raise ValueError("La copia usa gia il lettore corrente: usare la ripresa ordinaria")
        else:
            if args.riprendi:raise ValueError("Candidato della ripresa assente")
            if shutil.disk_usage(target.parent).free<source_stat.st_size+8*1024**3:
                raise ValueError("Spazio insufficiente per copia e margine")
            partial=target.with_name(target.name+".copia-in-corso")
            digest=hashlib.sha256()
            with original.open("rb") as src,partial.open("xb") as dst:
                while data:=src.read(4*1024**2):dst.write(data);digest.update(data)
            if digest.hexdigest()!=gate["sha256_db_finale"] or sha(partial)!=digest.hexdigest():
                raise ValueError("Copia o originale discordante: parziale conservato")
            os.replace(partial,target)
            atomic(copy_path,{"originale":str(original),"originale_sha256":digest.hexdigest(),
                "candidato":str(target),"sha256_copia_iniziale":digest.hexdigest(),"byte":source_stat.st_size})
            state={"lettore_runtime":revision,"originale_sha256":gate["sha256_db_finale"],
                "qualificate":0,"errori":{},"tutti_dati_completati":False}
        journal=output/"qualificate.jsonl"
        verified=set()
        if journal.exists():
            for line in journal.read_text(encoding="utf-8").splitlines():
                proof=json.loads(line)
                if proof.get("lettore_runtime")!=revision:raise ValueError("Journal di un altro lettore")
                verified.add(proof["chain_id"])
        state["qualificate"]=len(verified)
        conn=sqlite3.connect(target,timeout=30);conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL");conn.execute("PRAGMA cache_size=-1048576");conn.execute("PRAGMA temp_store=MEMORY");assicura_schema(conn);conn.commit()
        chains=conn.execute("SELECT id,zip_path,zip_sha256 FROM normative_akn_chains WHERE completa=1 ORDER BY zip_sha256,zip_path,rowid").fetchall()
        state["catene_da_esaminare"]=len(chains);atomic(state_path,state);current=None
        pending=[]
        def flush_proofs():
            conn.commit()
            if pending:
                with journal.open("a",encoding="utf-8") as stream:
                    for proof in pending:stream.write(json.dumps(proof,ensure_ascii=False)+"\n")
                    stream.flush();os.fsync(stream.fileno())
                verified.update(p["chain_id"] for p in pending);pending.clear()
                state["qualificate"]=len(verified)

        last_guard=0.0
        def checkpoint():
            nonlocal last_guard
            now=time.monotonic()
            if now-last_guard<5:return
            last_guard=now
            if (output/"arresto-richiesto.json").exists():
                raise RuntimeError("Arresto richiesto: checkpoint precedente conservato, transazione corrente non attestata")
            impronta_lettore.cache_clear()
            if impronta_lettore()!=revision:raise RuntimeError("Lettore cambiato: interrompere prima di altri attestati")

        for index,(chain,path,digest) in enumerate(chains,1):
            if chain in verified or chain in state["errori"]:continue
            if index%100==0:
                impronta_lettore.cache_clear()
                if impronta_lettore()!=revision:raise ValueError("Lettore cambiato durante la riconvalida")
                if shutil.disk_usage(target.parent).free<8*1024**3:raise ValueError("Margine disco insufficiente")
            key=(path,digest)
            if key!=current:
                if archive:archive.close()
                archive=ArchivioRiscontrato(archivio_locale(path,root),digest);current=key
            try:
                proof=riconvalida_catena(conn,chain_id=chain,archivio=archive,cartella_prove=output/"catene",commit=False,verifica_prosecuzione=checkpoint)
                pending.append(proof)
            except (ValueError,etree.XMLSyntaxError,zipfile.BadZipFile) as exc:
                state["errori"][chain]={"errore":str(exc),"zip_sha256":digest}
            if index%25==0:
                flush_proofs();atomic(state_path,state)
        flush_proofs()
        state["integrity_check"]=conn.execute("PRAGMA integrity_check").fetchone()[0]
        state["foreign_key_check_ok"]=not conn.execute("PRAGMA foreign_key_check").fetchmany(1)
        if state["integrity_check"]!="ok" or not state["foreign_key_check_ok"]:raise ValueError("Integrità candidato non superata")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)");conn.execute("PRAGMA journal_mode=DELETE");conn.close();conn=None
        current_stat=original.stat()
        if (current_stat.st_size,current_stat.st_mtime_ns)!=(source_stat.st_size,source_stat.st_mtime_ns):
            raise ValueError("Originale cambiato durante la lavorazione")
        state["sha256_candidato"]=sha(target);state["utc_fine"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
        state["riconvalida_terminata"]=True
        state["tutte_catene_riscontrate"]=not state["errori"] and len(verified)==len(chains)
        atomic(state_path,state)
        print(json.dumps({k:v for k,v in state.items() if k not in {"qualificate","errori"}},ensure_ascii=False))
    finally:
        if conn:conn.close()
        if archive:archive.close()
        lock_path.unlink()


if __name__=="__main__":main()
