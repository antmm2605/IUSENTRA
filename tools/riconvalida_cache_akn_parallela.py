"""Confronti paralleli in sola lettura, un solo coordinatore scrive attestati.
Riutilizza esclusivamente la copia gia verificata dalla procedura sequenziale.
"""
from pathlib import Path
import argparse,concurrent.futures,datetime,json,os,shutil,sqlite3,sys,time,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lxml import etree
from lex.normativa.riconvalida_akn import ArchivioRiscontrato,riconvalida_catena
from lex.normativa.versioni_akn import impronta_lettore
from tools.riconvalida_cache_akn import atomic,archivio_locale,sha
_WORKER={}
class ArchivioDelegato:
    def __init__(self,token):
        self.path=Path(token['path']).resolve(strict=True);self.sha256=token['sha256'];self.expected=tuple(token['stat'])
        self.verifica_stabilita();self.zip=zipfile.ZipFile(self.path)
    def verifica_stabilita(self):
        s=self.path.stat()
        if (s.st_size,s.st_mtime_ns,s.st_ino)!=self.expected:raise RuntimeError('Primario cambiato rispetto alla rilettura SHA del coordinatore')
    def close(self):self.zip.close()
def init_worker(target,output,revision):
    conn=sqlite3.connect(Path(target).as_uri()+'?mode=ro',uri=True,timeout=30)
    conn.execute('PRAGMA query_only=ON');conn.execute('PRAGMA cache_size=-65536');conn.execute('PRAGMA temp_store=MEMORY')
    _WORKER.update(conn=conn,output=Path(output),revision=revision,archive=None,key=None,last=0.0)
def guard_worker():
    now=time.monotonic()
    if now-_WORKER['last']<5:return
    _WORKER['last']=now
    if (_WORKER['output']/'arresto-richiesto.json').exists():raise RuntimeError('Arresto richiesto, nessun attestato aggiunto dal worker')
    impronta_lettore.cache_clear()
    if impronta_lettore()!=_WORKER['revision']:raise RuntimeError('Lettore cambiato durante il confronto')
def confronta(job):
    chain,token=job;guard_worker()
    key=(token['path'],token['sha256'],tuple(token['stat']))
    if _WORKER['key']!=key:
        if _WORKER['archive']:_WORKER['archive'].close()
        _WORKER['archive']=ArchivioDelegato(token);_WORKER['key']=key
    try:
        proof=riconvalida_catena(_WORKER['conn'],chain_id=chain,archivio=_WORKER['archive'],cartella_prove=_WORKER['output']/'catene',commit=False,attesta_sql=False,verifica_prosecuzione=guard_worker,massimo_xml_byte=64*1024**2)
        return {'proof':proof}
    except (ValueError,etree.XMLSyntaxError,zipfile.BadZipFile) as exc:
        return {'chain_id':chain,'error':str(exc),'zip_sha256':token['sha256']}
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('originale','candidato','gate','archivi','prove'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--workers',type=int,default=4);ap.add_argument('--esegui',action='store_true');ap.add_argument('--riprendi',action='store_true');a=ap.parse_args()
    if not a.esegui or not a.riprendi or not 1<=a.workers<=4:raise ValueError('Richiesta ripresa esplicita, massimo quattro processi')
    original=a.originale.resolve(strict=True);target=a.candidato.resolve(strict=True);root=a.archivi.resolve(strict=True);output=a.prove.resolve(strict=True)
    if os.path.samefile(original,target):raise ValueError('Candidato uguale all originale')
    gate=json.loads(a.gate.read_text(encoding='utf-8-sig'));statepath=output/'stato.json';state=json.loads(statepath.read_text(encoding='utf-8'));copy=json.loads((output/'copia-verificata.json').read_text(encoding='utf-8'))
    revision=impronta_lettore();source_stat=original.stat()
    if gate.get('importazione_manifest_terminata') is not True or gate.get('integrity_check')!='ok' or gate.get('foreign_key_check_ok') is not True:raise ValueError('Originale non sigillato')
    if state.get('lettore_runtime')!=revision or state.get('originale_sha256')!=gate.get('sha256_db_finale') or copy.get('originale_sha256')!=gate.get('sha256_db_finale') or copy.get('byte')!=source_stat.st_size or copy.get('originale')!=str(original) or copy.get('candidato')!=str(target):raise ValueError('Ripresa riferita a copia o lettore diversi')
    if (output/'arresto-richiesto.json').exists():raise ValueError('Richiesta di arresto presente: archiviare prima di riprendere')
    lock=output/'riconvalida.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    conn=None;archive=None
    try:
        verified={};journal=output/'qualificate.jsonl'
        if journal.exists():
            for line in journal.read_text(encoding='utf-8').splitlines():
                p=json.loads(line)
                if p.get('lettore_runtime')!=revision or p['chain_id'] in verified:raise ValueError('Journal non univoco o di altro lettore')
                verified[p['chain_id']]=p['sha256']
        conn=sqlite3.connect(target,timeout=30);conn.execute('PRAGMA foreign_keys=ON');conn.execute('PRAGMA journal_mode=WAL');conn.execute('PRAGMA cache_size=-262144');conn.execute('PRAGMA temp_store=MEMORY')
        stored=dict(conn.execute('SELECT id,riscontro_contenuti_sha256 FROM normative_akn_chains WHERE riscontro_lettore_sha256=?',(revision,)))
        if any(stored.get(k)!=v for k,v in verified.items()):raise ValueError('Journal e attestati SQL discordanti')
        chains=conn.execute('SELECT id,zip_path,zip_sha256 FROM normative_akn_chains WHERE completa=1 ORDER BY zip_sha256,zip_path,rowid').fetchall()
        groups={}
        for chain,path,digest in chains:
            if chain not in verified and chain not in state['errori']:groups.setdefault((path,digest),[]).append(chain)
        state.update(qualificate=len(verified),catene_da_esaminare=len(chains),modalita='quattro confronti RO, singolo writer SQL',workers=a.workers,pid=os.getpid(),riconvalida_terminata=False);atomic(statepath,state)
        pending=[]
        def flush():
            conn.commit()
            if pending:
                with journal.open('a',encoding='utf-8') as f:
                    for p in pending:f.write(json.dumps(p,ensure_ascii=False)+'\n')
                    f.flush();os.fsync(f.fileno())
                verified.update({p['chain_id']:p['sha256'] for p in pending});pending.clear()
            state['qualificate']=len(verified);state['utc_avanzamento']=datetime.datetime.now(datetime.timezone.utc).isoformat();atomic(statepath,state)
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,initializer=init_worker,initargs=(str(target),str(output),revision)) as pool:
            for (path,digest),ids in groups.items():
                if (output/'arresto-richiesto.json').exists():raise RuntimeError('Arresto richiesto al coordinatore')
                impronta_lettore.cache_clear()
                if impronta_lettore()!=revision:raise RuntimeError('Lettore cambiato prima nuovo archivio')
                if shutil.disk_usage(target.parent).free<8*1024**3:raise RuntimeError('Spazio insufficiente')
                archive=ArchivioRiscontrato(archivio_locale(path,root),digest)
                st=archive.stat;token={'path':str(archive.path),'sha256':digest,'stat':[st.st_size,st.st_mtime_ns,st.st_ino]}
                archiveproof={'lettore':revision,**token,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};d=output/'archivi-riletti';d.mkdir(exist_ok=True);atomic(d/(digest+'.json'),archiveproof)
                iterator=iter(ids);active=set()
                def fill():
                    while len(active)<a.workers*2:
                        chain=next(iterator,None)
                        if chain is None:break
                        active.add(pool.submit(confronta,(chain,token)))
                fill()
                while active:
                    ready,active=concurrent.futures.wait(active,return_when=concurrent.futures.FIRST_COMPLETED)
                    for future in ready:
                        result=future.result()
                        if 'proof' in result:
                            p=result['proof']
                            if p['lettore_runtime']!=revision:raise RuntimeError('Prova di altro lettore')
                            conn.execute('UPDATE normative_akn_chains SET riscontro_lettore_sha256=?,riscontro_contenuti_sha256=? WHERE id=?',(revision,p['sha256'],p['chain_id']));pending.append(p)
                        else:state['errori'][result['chain_id']]={'errore':result['error'],'zip_sha256':result['zip_sha256']}
                        if len(pending)>=25:flush()
                    fill()
                archive.verifica_stabilita();archive.close();archive=None;flush()
        flush();state['fase']='integrita_finale';atomic(statepath,state)
        state['integrity_check']=conn.execute('PRAGMA integrity_check').fetchone()[0];state['foreign_key_check_ok']=not conn.execute('PRAGMA foreign_key_check').fetchmany(1)
        if state['integrity_check']!='ok' or not state['foreign_key_check_ok']:raise ValueError('Gate integrita non superato')
        conn.execute('PRAGMA wal_checkpoint(TRUNCATE)');conn.execute('PRAGMA journal_mode=DELETE');conn.close();conn=None
        s=original.stat()
        if (s.st_size,s.st_mtime_ns)!=(source_stat.st_size,source_stat.st_mtime_ns):raise RuntimeError('Originale modificato')
        state['fase']='SHA_finale';atomic(statepath,state);state['sha256_candidato']=sha(target);state['utc_fine']=datetime.datetime.now(datetime.timezone.utc).isoformat();state['riconvalida_terminata']=True;state['tutte_catene_riscontrate']=not state['errori'] and len(verified)==len(chains);atomic(statepath,state)
        print(json.dumps({k:v for k,v in state.items() if k!='errori'}),flush=True)
    finally:
        if conn:conn.close()
        if archive:archive.close()
        lock.unlink()
if __name__=='__main__':main()
