#!/usr/bin/env python3
"""Riconvalida SQL delle sentenze: ripresa dal registro nativo, nessun invio o archivio ZIP."""
import argparse,json,sys,time,uuid,shutil
from datetime import datetime,timezone
from pathlib import Path
from web.app import create_app
from pct.tenant import GestioneTenant
from web.services.fascicoli_presidi_runtime import _active_tenants,_attach_tenant_context
from web.helpers import get_fascicoli
from web.services.sentenza_archiviazione_runtime import controlla_fascicolo

parser=argparse.ArgumentParser()
parser.add_argument('--tenant',required=True)
parser.add_argument('--fascicolo',default='')
parser.add_argument('--apply',action='store_true')
parser.add_argument('--force',action='store_true')
parser.add_argument('--limit-per-fascicolo',type=int,default=25)
parser.add_argument('--report',required=True)
parser.add_argument('--backup-dir',default='')
parser.add_argument('--backup-manifest',default='')
args=parser.parse_args()
if not 1 <= args.limit_per_fascicolo <= 100000: parser.error('Limite non valido.')
if args.apply and not (args.backup_dir or args.backup_manifest): parser.error('Prima di applicare è obbligatoria una copia coerente: specificare --backup-dir o --backup-manifest verificabile.')
run_id=uuid.uuid4().hex
app=create_app();studio=next((s for s in _active_tenants(app) if s.slug==args.tenant),None)
if studio is None: raise SystemExit('Studio attivo non trovato.')
output=Path(args.report);output.parent.mkdir(parents=True,exist_ok=True)
totals={'fascicoli':0,'checked':0,'changed':0,'errors':0,'missing_inventory':0}
with output.open('a',encoding='utf-8') as report:
 with app.test_request_context('/__riconvalida/sentenze-archivio'):
  _attach_tenant_context(GestioneTenant(registry_path=app.config['TENANTS_REGISTRY']),studio)
  manager=get_fascicoli()
  if manager._studio_db is None: raise RuntimeError('Fonte SQL non disponibile.')
  if args.apply:
   from web.services.archivio_letture_runtime import registro_corrente
   from web.services.sentenza_economic_runtime import _repo
   from deploy.hetzner.backup_structured import _backup_sqlite,_sha256
   repos=(manager._studio_db,registro_corrente(),_repo())
   if args.backup_manifest:
    manifest_path=Path(args.backup_manifest).resolve();manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('tenant_id')!=studio.slug or not manifest.get('entries'):raise RuntimeError('Backup non riferibile allo studio corrente.')
    for entry in manifest['entries']:
     source=Path(entry['file']).resolve()
     if not source.is_file() or _sha256(source)!=entry['sha256']:raise RuntimeError('Impronta del backup non verificata.')
    if set(manifest.get('components',[]))!={'fascicoli','registro_letture','economico'}:raise RuntimeError('Backup incompleto per le componenti modificate.')
   else:
    if any(getattr(r,'backend_kind','sqlite')!='sqlite' for r in repos):raise RuntimeError('Per PostgreSQL occorre il manifest della copia coerente nativa del database: nessun backup SQLite viene dichiarato equivalente.')
    destination=Path(args.backup_dir).resolve()/('sentenze-'+run_id);destination.mkdir(parents=True,exist_ok=False)
    sources=[Path(r.db_path) for r in repos]
    if shutil.disk_usage(destination).free<sum(p.stat().st_size for p in sources)*1.1+1024**3:raise RuntimeError('Spazio insufficiente per il backup coerente: nessuna riconvalida applicata.')
    entries=[]
    for source in sources:
     target=destination/source.name
     entry=_backup_sqlite(source,target);entry['file']=str(target);entries.append(entry)
    manifest={'tenant_id':studio.slug,'source_of_truth':'sqlite','components':['fascicoli','registro_letture','economico'],'created_at':datetime.now(timezone.utc).isoformat(),'entries':entries}
    manifest_path=destination/'manifest.json';manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
   print('BACKUP_VERIFIED',str(manifest_path),flush=True)
  ids=[args.fascicolo] if args.fascicolo else sorted(f.id for f in manager.tutti(archiviati=True))
  print('BEGIN',json.dumps({'tenant':args.tenant,'fascicoli':len(ids),'apply':args.apply,'source_of_truth':getattr(manager._studio_db,'backend_kind','sqlite'),'run_id':run_id}),flush=True)
  for fid in ids:
   start=time.monotonic()
   try:
    result=controlla_fascicolo(fascicolo_id=fid,limit=args.limit_per_fascicolo,apply=args.apply,force=args.force,actor='riconvalida-sentenze-automatica')
    result['run_id']=run_id
    result['elapsed_ms']=round((time.monotonic()-start)*1000)
    if result['pending']==0 and result['checked']==0:
     from web.services.archivio_letture_runtime import registro_corrente,tenant_corrente
     if not registro_corrente().oggetti(tenant_corrente(),fid):
      result['missing_inventory']=True;totals['missing_inventory']+=1
    totals['checked']+=result['checked'];totals['changed']+=result['changed'];totals['errors']+=len(result['errors'])
   except Exception as exc:
    result={'fascicolo_id':fid,'error':str(exc)};totals['errors']+=1
   totals['fascicoli']+=1
   report.write(json.dumps(result,ensure_ascii=False)+'\n');report.flush()
   print('PROGRESS',json.dumps({'fascicolo':fid,**totals}),flush=True)
  report.write(json.dumps({'run_id':run_id,'totals':totals},ensure_ascii=False)+'\n');report.flush()
  print('END',json.dumps(totals),flush=True)
