"""Read-only inventory: outputs counts/schema, never document text or personal names."""
import subprocess,json
code=r'''
import os,json,sqlite3,hashlib,collections
from pathlib import Path
roots=[p for p in [Path('/data'),Path('/app/data')] if p.exists()]
extensions=collections.Counter();databases=[];errors=[];files=0
for root in roots:
 for parent,dirs,names in os.walk(root):
  dirs[:]=[d for d in dirs if d not in {'normativa','normattiva','cortecost','ollama','models','__pycache__','node_modules','backups'}]
  for name in names:
   p=Path(parent)/name;files+=1;ext=p.suffix.lower();extensions[ext]+=1
   if ext not in {'.sqlite','.sqlite3','.db'}:continue
   entry={'path_id':hashlib.sha256(str(p).encode()).hexdigest()[:16],'root':str(root),'tables':[]}
   try:
    c=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True,timeout=2)
    names_db=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for table in names_db:
     if not any(s in table.lower() for s in ['fascic','pratic','document','atto','dataset','lex','feedback','editor']):continue
     quoted='"'+table.replace('"','""')+'"'
     columns=[r[1] for r in c.execute('PRAGMA table_info('+quoted+')')]
     count=c.execute('SELECT COUNT(*) FROM '+quoted).fetchone()[0]
     entry['tables'].append({'name':table,'columns':columns,'rows':count})
    c.close();databases.append(entry)
   except Exception as e:errors.append({'path_id':entry['path_id'],'error_type':type(e).__name__})
   if files>=100000:break
  if files>=100000:break
print(json.dumps({'files_scanned':files,'extensions':dict(extensions),'databases':databases,'errors':errors,'postgres_configured':any(os.environ.get(k,'').startswith('postgres') for k in ['DATABASE_URL','SQLALCHEMY_DATABASE_URI']),'document_contents_exported':False,'server_modified':False}))
'''
r=subprocess.run(['docker','exec','-i','iusentra-app','python','-'],input=code,text=True,capture_output=True,timeout=150)
if r.returncode:print(json.dumps({'error':'Inventario container non riuscito','exit_code':r.returncode}));raise SystemExit(r.returncode)
print(r.stdout)
