"""Proiezione offline degli AKN riscontrati nell'indice nativo candidato.
Da eseguire solo dopo conclusione import AKN, mai durante una ricerca web.
Non determina applicabilità sostanziale/processuale, non cancella versioni.
"""
from __future__ import annotations
import argparse
from collections import OrderedDict
from contextlib import closing
from datetime import date,datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import shutil
import sys
import time
import zipfile


def sha_file(path):
    before=path.stat()
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(8*1024*1024):digest.update(block)
    after=path.stat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
        raise ValueError('File modificato durante il riscontro SHA')
    return digest.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','versioni','candidato','archivi','rapporto','stato_importazione'):
        ap.add_argument('--'+name.replace('_','-'),dest=name,type=Path,required=True)
    ap.add_argument('--data',required=True)
    a=ap.parse_args();target=date.fromisoformat(a.data)
    if target.isoformat()!=a.data:raise ValueError('Data ISO canonica richiesta')
    if not a.versioni.is_file() or not a.candidato.is_file() or a.versioni.resolve()==a.candidato.resolve():
        raise ValueError('Sorgente e destinazione distinte e già presenti obbligatorie')
    if a.rapporto.exists():raise FileExistsError('Versionare il rapporto, non sovrascrivere prove')
    sys.path.insert(0,str(a.repo))
    from lex.normativa.versioni_akn import impronta_lettore
    from lex.normativa.normattiva_akn_importer import parse_akn
    from lex.normativa.normattiva_importer import insert_document,insert_articles_and_chunks,ensure_schema,migra_schema
    from lex.normativa.biblioteca.fabbisogno import norm_articolo
    from lex.ricerca_giuridica.indice_fts import sincronizza_fts
    reader=impronta_lettore()
    from lex.normativa.lettori_attestati import politica_lettori
    policy=politica_lettori(reader)
    readers=sorted(policy.lettori)
    gate=json.loads(a.stato_importazione.read_text())
    if gate.get('importazione_manifest_terminata') is not True or gate.get('lettore_sha256') not in policy.lettori:
        raise ValueError('Importazione delle catene non conclusa con il lettore attuale')
    if (gate.get('integrity_check')!='ok' or gate.get('foreign_key_check_ok') is not True
            or not isinstance(gate.get('sha256_db_finale'),str) or len(gate['sha256_db_finale'])!=64):
        raise ValueError('Integrità finale e SHA della cache non attestati')
    if sha_file(a.versioni)!=gate['sha256_db_finale']:
        raise ValueError('Cache sorgente diversa dal file finale verificato')
    a.rapporto.parent.mkdir(parents=True,exist_ok=True)
    log=a.rapporto.with_suffix('.jsonl');chunks=a.rapporto.with_suffix('.chunk.jsonl')
    if log.exists() or chunks.exists():raise FileExistsError('Log precedente presente: ripresa esplicita da valutare')
    result={'data_riferimento':a.data,'lettore_sha256':reader,'stato':'in_corso','documenti':0,
            'articoli':0,'chunk':0,'catene_senza_edizione_alla_data':0,'gia_proiettati':0,
            'applicabilita_al_fascicolo_certificata':False,'sorgente_in_sola_lettura':True}
    archives=OrderedDict();verified={};mapped_paths={}
    archive_root=a.archivi.resolve(strict=True)
    try:
        with closing(sqlite3.connect(a.versioni.resolve().as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(a.candidato)) as dst, log.open('x') as receipts, chunks.open('x') as jf:
            src.row_factory=sqlite3.Row
            # Budget esplicito e limitato: evitare continui spill casuali sul
            # deposito HDD senza ridurre durabilità o controlli delle fonti.
            src.execute('PRAGMA cache_size=-131072')
            dst.execute('PRAGMA cache_size=-131072')
            # Preferenza uguale al lettore nativo: ricezione più recente, poi
            # ricerca ufficiale puntuale rispetto a raccolta preconfezionata.
            chain_columns={r[1] for r in src.execute('PRAGMA table_info(normative_akn_chains)')}
            eligible='lettore_sha256=?';proof_args=[reader]
            if {'riscontro_lettore_sha256','riscontro_contenuti_sha256'}<=chain_columns:
                eligible+=" OR (riscontro_lettore_sha256=? AND length(riscontro_contenuti_sha256)=64 AND riscontro_contenuti_sha256 NOT GLOB '*[^0-9a-f]*')"
                proof_args.append(reader)
            base_clause='completa=1 AND lettore_sha256 IN ('+','.join('?' for _ in readers)+') AND acquisita_giorno_it>=?'
            base_args=[*readers,a.data]
            total=src.execute('SELECT count(*) FROM normative_akn_chains WHERE '+base_clause,base_args).fetchone()[0]
            count=src.execute('SELECT count(*) FROM normative_akn_chains WHERE '+base_clause+' AND ('+eligible+')',[*base_args,*proof_args]).fetchone()[0]
            result['catene_non_qualificate_escluse']=total-count
            chains=src.execute("""SELECT * FROM (
                SELECT *,ROW_NUMBER() OVER(PARTITION BY urn ORDER BY acquisita_giorno_it DESC,
                    CASE WHEN tipo_origine='ricerca_asincrona' THEN 0 ELSE 1 END,acquisita_utc DESC,id) rn
                FROM normative_akn_chains WHERE """+base_clause+' AND ('+eligible+')'+"""
                ) WHERE rn=1 ORDER BY zip_sha256,zip_path,id""",[*base_args,*proof_args]).fetchall()
            if not chains:raise ValueError('Nessuna catena qualificata: proiezione non avviata')
            if shutil.disk_usage(a.candidato.parent).free<a.candidato.stat().st_size+8*1024**3:
                raise RuntimeError('Spazio insufficiente per backup e proiezione: nessuna modifica al candidato')
            backup=a.candidato.with_name('normattiva-prima-proiezione-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.sqlite')
            last_progress=[0.0]
            def backup_progress(status,remaining,total):
                now=time.monotonic()
                if remaining and now-last_progress[0]<15:return
                last_progress[0]=now
                progress={'fase':'copia_SQLite_in_corso' if remaining else 'copia_SQLite_conclusa_SHA_pendente',
                          'sqlite_status':status,'pagine_residue':remaining,'pagine_totali':total,
                          'backup':str(backup),'utc':datetime.now(timezone.utc).isoformat()}
                from tools.riconvalida_cache_akn import atomic
                atomic(a.rapporto.with_suffix('.backup.json'),progress)
                print('BACKUP_SQLITE',json.dumps(progress),flush=True)
            with closing(sqlite3.connect(backup)) as saved:
                saved.execute('PRAGMA cache_size=-131072')
                dst.backup(saved,pages=8192,progress=backup_progress)
            result['backup_candidato']={'file':str(backup),'sha256':sha_file(backup)}
            ensure_schema(dst);migra_schema(dst);dst.commit()
            from lex.normativa.riferimenti_importazione import indicizza_storico
            result['riferimenti_precedenti_indicizzati']=indicizza_storico(dst)
            dst.commit()
            dst.execute('PRAGMA foreign_keys=ON');dst.execute('PRAGMA journal_mode=WAL')
            dst.execute('''CREATE TABLE IF NOT EXISTS normative_akn_projection(
                projection_sha256 TEXT PRIMARY KEY,chain_id TEXT NOT NULL,edition_id INTEGER NOT NULL,
                target_document_id INTEGER NOT NULL,zip_sha256 TEXT NOT NULL,xml_sha256 TEXT NOT NULL,
                lettore_sha256 TEXT NOT NULL,data_riferimento TEXT NOT NULL,provenienza_json TEXT NOT NULL)''');dst.commit()
            for chain in chains:
                editions=src.execute('SELECT * FROM normative_akn_editions WHERE chain_id=? AND dal<=? AND (al_escluso IS NULL OR al_escluso>?)',
                                     (chain['id'],a.data,a.data)).fetchall()
                if not editions:
                    result['catene_senza_edizione_alla_data']+=1
                    receipts.write(json.dumps({'chain_id':chain['id'],'urn':chain['urn'],'stato':'nessuna_edizione_nell_intervallo_richiesto'})+'\n');continue
                if len(editions)!=1:raise ValueError('Edizioni sovrapposte: non scegliere arbitrariamente')
                edition=editions[0]
                identity=hashlib.sha256((chain['id']+'|'+edition['xml_sha256']+'|'+a.data+'|'+reader).encode()).hexdigest()
                if dst.execute('SELECT 1 FROM normative_akn_projection WHERE projection_sha256=?',(identity,)).fetchone():
                    result['gia_proiettati']+=1;continue
                registered=chain['zip_path']
                if registered not in mapped_paths:
                    from pathlib import PureWindowsPath
                    if registered.startswith('/mnt/d/'):
                        relative=Path(registered).relative_to('/mnt/d/IUSENTRA/Normattiva/completamento-20261025')
                        path=(archive_root/relative).resolve(strict=True)
                    elif PureWindowsPath(registered).drive:
                        relative=PureWindowsPath(registered).relative_to(PureWindowsPath('D:/IUSENTRA/Normattiva/completamento-20261025'))
                        path=archive_root.joinpath(*relative.parts).resolve(strict=True)
                    else:
                        path=Path(registered).resolve(strict=True)
                    if not path.is_relative_to(archive_root):raise ValueError('Archivio sorgente fuori dal deposito autorizzato')
                    mapped_paths[registered]=path
                path=mapped_paths[registered]
                stat=path.stat();stamp=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
                if path not in verified:
                    if sha_file(path)!=chain['zip_sha256']:raise ValueError('ZIP sorgente alterato')
                    verified[path]=(stamp,chain['zip_sha256'])
                elif verified[path]!=(stamp,chain['zip_sha256']):raise ValueError('Archivio cambiato durante la proiezione')
                if path not in archives:
                    if len(archives)>=3:archives.popitem(last=False)[1].close()
                    archives[path]=zipfile.ZipFile(path)
                archives.move_to_end(path);archive=archives[path];info=archive.getinfo(edition['xml_entry'])
                if info.file_size>512*1024*1024:raise ValueError('XML oltre limite: nessun troncamento')
                # La rilettura diagnostica WSL ha incontrato Err12 sul read()
                # senza dimensione; leggere lo stesso membro in blocchi finiti.
                with archive.open(info) as source:
                    chunks=[]
                    while piece:=source.read(1024*1024):chunks.append(piece)
                raw=b"".join(chunks)
                if len(raw)!=info.file_size:raise ValueError("Dimensione XML discordante dal membro ZIP")
                if hashlib.sha256(raw).hexdigest()!=edition['xml_sha256']:raise ValueError('Payload XML diverso dalla catena verificata')
                doc=parse_akn(raw,zip_path=path,entry=edition['xml_entry'],collection_name='Normattiva AKN — edizione riscontrata al '+a.data,analizza_pertinenza=False)
                if doc.urn!=chain['urn'] or doc.redazione_id!=edition['espressione_dal']:
                    raise ValueError('Identità o versione del parser discordante dalla catena')
                expected=src.execute('SELECT numero,partizione,localizzatore_xml,sha256_testo FROM normative_akn_articles WHERE edition_id=? ORDER BY ordinal',(edition['id'],)).fetchall()
                actual=[(norm_articolo(x.article_number or ''),x.partizione,x.localizzatore_xml,hashlib.sha256(x.article_text.encode()).hexdigest()) for x in doc.articles]
                if actual!=[tuple(x) for x in expected]:raise ValueError('Articoli o partizioni divergono dal lettore verificato')
                from lex.normativa.qualita_testo import qualita_testo
                qualita_articoli=tuple(qualita_testo(x.article_text,solo_rubrica=x.solo_intestazione_xml) for x in doc.articles)
                # Una disposizione abrogata non cancella gli altri articoli
                # realmente acquisiti della stessa edizione ufficiale.
                ha_corpo=any(q=='testo_acquisito' for q in qualita_articoli)
                ha_corpo=ha_corpo or any(qualita_testo(x['testo'])=='testo_acquisito' for x in doc.componenti)
                if not doc.articles and doc.qualita_corpo=='testo_acquisito':ha_corpo=True
                if not ha_corpo:
                    result['edizioni_senza_testo_integrale']=result.get('edizioni_senza_testo_integrale',0)+1
                    receipts.write(json.dumps({'chain_id':chain['id'],'edition_id':edition['id'],'urn':chain['urn'],'stato':'nessun_corpo_integrale_nella_edizione_alla_data','qualita':doc.qualita_corpo,'xml_sha256':edition['xml_sha256']},ensure_ascii=False)+'\n');continue
                old=dst.execute('SELECT id,text_content FROM normative_documents WHERE xml_sha256=?',(doc.xml_sha256,)).fetchone()
                if old and old[1]!=doc.text_content:raise ValueError('Medesimo XML con corpo diverso: nessuna sovrascrittura')
                if not dst.in_transaction:dst.execute('BEGIN')
                document_id=old[0] if old else insert_document(dst,doc,store_full_text=True)
                if not document_id:raise ValueError('Documento non importabile dal proprietario nativo')
                articles,newchunks=insert_articles_and_chunks(dst,document_id,doc,jsonl_file=jf,max_chunk_chars=1800,only_relevant_articles=False,preserva_esistenti=True)
                coverage_end=min(edition['al_escluso'] or '9999-12-31',(date.fromisoformat(chain['acquisita_giorno_it'])+timedelta(days=1)).isoformat())
                provenance={'archivio_registrato':registered,'archivio_usato_per_proiezione':str(path),'chain_id':chain['id'],'zip_sha256':chain['zip_sha256'],'xml_sha256':edition['xml_sha256'],
                    'xml_decodificato_sha256':doc.xml_decodificato_sha256,'xml_entry':edition['xml_entry'],
                    'codifica_trasporto':doc.codifica_trasporto,'acquisita_utc':chain['acquisita_utc'],
                    'lettore_sha256':chain['lettore_sha256'],'lettore_proiezione_sha256':reader,
                    'politica_lettori_sha256':policy.manifest_sha256,'rapporto_compatibilita_sha256':policy.rapporto_sha256,
                    'versione_formale_dal':edition['dal'],'versione_formale_al_escluso':coverage_end,
                    'espressione_dal':edition['espressione_dal'],'vigenza_richiesta':a.data,'catena_ufficiale_completa':True,
                    'applicabilita_al_fascicolo_verificata':False,
                    'urn_originale_akn':getattr(doc,'urn_originale_akn',doc.urn),
                    'data_atto_riscontro':getattr(doc,'data_atto_riscontro',None),
                    'identita_pubblicazione':getattr(doc,'identita_pubblicazione',None),
                    'identita_metadata_non_datata':getattr(doc,'identita_non_datata',False)}
                stored_proof=json.loads(edition['identita_provenienza_json']) if 'identita_provenienza_json' in edition.keys() else {}
                if not isinstance(stored_proof,dict):raise ValueError('Provenienza identita non strutturata')
                packaging=stored_proof.get('ordine_fotogramma_riscontro')
                if packaging is not None:
                    if (not isinstance(packaging,dict) or packaging.get('entry')!=edition['xml_entry']
                            or packaging.get('payload_sha256')!=edition['xml_sha256']
                            or packaging.get('fotogramma')!=edition['dal']
                            or packaging.get('espressione')!=doc.redazione_id):
                        raise ValueError('Riscontro ordine della confezione discordante')
                    provenance['ordine_fotogramma_riscontro']=packaging
                for field in ('riscontro_lettore_sha256','riscontro_contenuti_sha256'):
                    if field in chain.keys() and chain[field]:
                        output_field={'riscontro_lettore_sha256':'lettore_riscontro_sha256',
                                      'riscontro_contenuti_sha256':'rilettura_catena_sha256'}[field]
                        provenance[output_field]=chain[field]
                dst.execute("UPDATE normative_chunks SET metadata_json=json_set(COALESCE(metadata_json,'{}'),'$.consultazione_provenienza',json(?)) WHERE document_id=?",
                            (json.dumps(provenance,ensure_ascii=False),document_id))
                result['articoli_senza_corpo_nell_edizione']=result.get('articoli_senza_corpo_nell_edizione',0)+sum(q!='testo_acquisito' for q in qualita_articoli)
                for ordinal,article in enumerate(doc.articles,1):
                    article_id=dst.execute('SELECT id FROM normative_articles WHERE article_key=?',
                                          (f'normattiva:{doc.xml_sha256}:art{ordinal}',)).fetchone()[0]
                    md=dict(provenance,partizione_xml=article.partizione,localizzatore_xml=article.localizzatore_xml)
                    quality=qualita_articoli[ordinal-1]
                    dst.execute("UPDATE normative_chunks SET metadata_json=json_set(COALESCE(metadata_json,'{}'),'$.consultazione_provenienza',json(?),'$.partizione_xml',?,'$.localizzatore_xml',?,'$.consultazione_senza_testo',json(?),'$.qualita_testo_riscontrata',?) WHERE article_id=? AND document_id=?",
                                (json.dumps(md,ensure_ascii=False),article.partizione,article.localizzatore_xml,json.dumps(quality!='testo_acquisito'),quality,article_id,document_id))
                dst.execute('INSERT INTO normative_akn_projection VALUES(?,?,?,?,?,?,?,?,?)',
                            (identity,chain['id'],edition['id'],document_id,chain['zip_sha256'],edition['xml_sha256'],reader,a.data,json.dumps(provenance,ensure_ascii=False)))
                result['documenti']+=1;result['articoli']+=articles;result['chunk']+=newchunks
                receipts.write(json.dumps({'projection_sha256':identity,'document_id':document_id,**provenance},ensure_ascii=False)+'\n')
                if result['documenti']%200==0:
                    dst.commit();receipts.flush();jf.flush();print('PROIEZIONE',json.dumps(result),flush=True)
            for source_path,(expected_stamp,_) in verified.items():
                final_stat=source_path.stat()
                if (final_stat.st_dev,final_stat.st_ino,final_stat.st_size,final_stat.st_mtime_ns,final_stat.st_ctime_ns)!=expected_stamp:
                    raise ValueError('Archivio modificato durante la proiezione: lotto non confermato')
            dst.commit();print('FTS_NATIVO_PROIEZIONE',flush=True)
            from dataclasses import asdict
            result['fts']=asdict(sincronizza_fts(dst))
            from lex.normativa.biblioteca.identita import indicizza_numeri_articolo
            result['indice_numeri_articolo']=indicizza_numeri_articolo(dst)
            dst.commit()
            result['stato']='proiezione_terminata';result['utc_fine']=datetime.now(timezone.utc).isoformat()
            a.rapporto.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result),flush=True)
    finally:
        for archive in archives.values():archive.close()


if __name__=='__main__':main()
