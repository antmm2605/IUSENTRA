"""Installazione selettiva, con verifica ottimistica e ripristino dei file della pagina."""
import hashlib,json,os,shutil,subprocess,sys,time,tarfile
from pathlib import Path

root=Path('/opt/iusentra/repo')
def run(args,**kw):return subprocess.check_output(args,**kw).decode().strip()
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def inspect(manifest):
 assert run(['git','-C',str(root),'rev-parse','HEAD'])==manifest['base'],'Commit server cambiato'
 status=run(['git','-C',str(root),'status','--porcelain'])
 assert not status,'Sorgenti server modificati: riconciliare prima: '+status
 for e in manifest['files']:
  p=root/e['path'];assert (sha(p) if p.is_file() else None)==e['before'],'File server diverso: '+e['path']
 app=json.loads(run(['docker','inspect','iusentra-app']))[0]
 assert app['Config']['Image'].endswith(':'+manifest['base']),'Immagine attiva non corrispondente al commit: verificare prima'
 # Verify runtime backend against repository; do not assume checkout = running image.
 for e in manifest['files']:
  if e['before'] and e['path'].startswith('web/'):
   got=run(['docker','exec','iusentra-app','python','-c','import hashlib;from pathlib import Path;print(hashlib.sha256(Path('+repr('/app/'+e['path'])+').read_bytes()).hexdigest())'])
   assert got==e['before'],'Runtime differente: '+e['path']
 data=next(m['Source'] for m in app['Mounts'] if m['Destination']=='/data')
 project=app['Config']['Labels']['com.docker.compose.project']
 return {'base':manifest['base'],'image':app['Image'],'image_tag':app['Config']['Image'],'data':data,'project':project}

mode,folder=sys.argv[1],Path(sys.argv[2]).resolve()
manifest=json.loads((folder/'INSTALL_MANIFEST.json').read_text())
state=inspect(manifest)
if mode=='inspect':
 print(json.dumps({'preflight':'PASS','base':state['base'],'image':state['image'],'data_mount':state['data'],'project':state['project']}));sys.exit(0)
assert mode=='publish'
assert sha(folder/'codici_leggi.sqlite')==manifest['database_sha256']
for e in manifest['files']:assert sha(folder/'sources'/e['path'])==e['after']
compose=root/'deploy/hetzner/docker-compose.hetzner.yml'
cmd=['docker','compose','--project-name',state['project'],'--project-directory',str(compose.parent),'--env-file','/opt/iusentra/.env.hetzner','-f',str(compose)]
static_id=run(cmd+['ps','-q','static-assets']);assert static_id
static=json.loads(run(['docker','inspect',static_id]))[0]
others={x:run(cmd+['ps','-q',x]) for x in ['scheduler-worker','ocr-worker','ollama','redis','caddy']}
backup=Path('/opt/iusentra/backups')/('codici-leggi-'+time.strftime('%Y%m%dT%H%M%S'))
backup.mkdir(mode=0o700,parents=True,exist_ok=False)
library=Path(state['data'])/'normativa/codici_leggi.sqlite';library.parent.mkdir(parents=True,exist_ok=True)
saved=[]
for e in manifest['files']:
 p=root/e['path'];b=backup/'sources'/e['path'];b.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():shutil.copy2(p,b)
 saved.append((p,b,e['before'] is not None))
if library.exists():shutil.copy2(library,backup/'codici_leggi.sqlite')
override=compose.parent/'docker-compose.codici-leggi.yml'
if override.exists():shutil.copy2(override,backup/'override.yml')
(backup/'state.json').write_text(json.dumps({'app_image':state['image'],'static_image':static['Image'],'others':others,'files':manifest['files']},indent=2))
shutil.copytree(root/'web/static/react',backup/'react')
# Derive from the actual production image, retaining every unrelated runtime file.
runtime=folder/'runtime';runtime.mkdir(exist_ok=True)
lines=['ARG BASE','FROM ${BASE}','USER root']
for e in manifest['files']:
 if e['path'].startswith(('web/blueprints/','web/bootstrap/','lex/normativa/')):
  p=runtime/e['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(folder/'sources'/e['path'],p)
  lines.append('COPY '+e['path']+' /app/'+e['path'])
shutil.copytree(folder/'react',runtime/'react',dirs_exist_ok=True)
lines+=['COPY react/ /app/web/static/react/','USER iusentra']
(runtime/'Dockerfile').write_text('\n'.join(lines)+'\n')
tag='iusentra-codici-leggi:'+manifest['build_id']
assert run(['docker','image','inspect','--format','{{.Id}}',state['image_tag']])==state['image']
subprocess.run(['docker','build','--build-arg','BASE='+state['image_tag'],'-t',tag,str(runtime)],check=True)
# Second check immediately before any application source is replaced.
assert inspect(manifest)['image']==state['image']
try:
 for e in manifest['files']:
  p=root/e['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(folder/'sources'/e['path'],p)
 shutil.copytree(folder/'react',root/'web/static/react',dirs_exist_ok=True)
 shutil.copy2(folder/'codici_leggi.sqlite',library);library.chmod(0o644)
 override.write_text('services:\n  app:\n    image: '+tag+'\n  static-assets:\n    image: '+tag+'\n')
 subprocess.run(cmd+['-f',str(override),'up','-d','--no-deps','--no-build','app','static-assets'],check=True)
 ready=False
 for i in range(60):
  health=run(['docker','inspect','--format','{{.State.Health.Status}}','iusentra-app'])
  if health=='healthy':ready=True;break
  time.sleep(3)
 assert ready,'Applicazione non pronta'
 check='''from pathlib import Path
from lex.normativa.consultazione import catalogo,articoli,dettaglio
from flask import Flask
from web.blueprints.api_v1_ricerca_legale import _normativa_db
d=Path("/data/normativa/codici_leggi.sqlite")
with Flask("verifica_codici").app_context():
    assert _normativa_db()==d, "API collegata ad archivio diverso"
a=catalogo(d)
assert len(a)==162 and sum(x["articles"] for x in a)==28209 and sum(x["category"]=="Codici" for x in a)==31
for label,number,minimum in [("Codice civile","2043",100),("Codice penale","416-bis",1801),("Codice di procedura penale","464",1801)]:
    act=next(x for x in a if x["label"]==label)
    r=articoli(d,act=act["id"],article=number);assert r["total"]==1
    item=dettaglio(d,r["items"][0]["id"]);assert len(item["text"])>=minimum
    print(label,number,len(item["text"]),"caratteri integrali")
print("162 raccolte, 31 codici, 28209 articoli; archivio API verificato")'''
 print(run(['docker','exec','iusentra-app','python','-c',check]))
 for service,cid in others.items():assert run(cmd+['ps','-q',service])==cid,'Servizio estraneo riavviato: '+service
 for e in manifest['files']:assert sha(root/e['path'])==e['after']
 print(json.dumps({'publish':'PASS','image':tag,'backup':str(backup),'other_services_preserved':True,'production_head_unchanged':True,'ai_archive_unchanged':True}))
except Exception:
 for p,b,existed in saved:
  if existed:shutil.copy2(b,p)
  elif p.exists():p.unlink()
 shutil.copytree(backup/'react',root/'web/static/react',dirs_exist_ok=True)
 if (backup/'codici_leggi.sqlite').exists():shutil.copy2(backup/'codici_leggi.sqlite',library)
 elif library.exists():library.unlink()
 # Restore service images directly; preserve the former override if one existed.
 override.write_text('services:\n  app:\n    image: '+state['image']+'\n  static-assets:\n    image: '+static['Image']+'\n')
 subprocess.run(cmd+['-f',str(override),'up','-d','--no-deps','--no-build','app','static-assets'],check=True)
 if (backup/'override.yml').exists():shutil.copy2(backup/'override.yml',override)
 print('Ripristino della pagina eseguito; controllare readiness e manifest React.');raise
