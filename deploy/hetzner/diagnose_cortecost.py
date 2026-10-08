import subprocess,json
code=r'''
import os,json,sqlite3,hashlib,collections,time
from pathlib import Path
target='f3f202cf10017e5e';found=None
for parent,dirs,names in os.walk('/data'):
 dirs[:]=[d for d in dirs if d not in {'normativa','normattiva','cortecost','ollama','models','__pycache__','node_modules','backups'}]
 for name in names:
  p=Path(parent)/name
  if p.suffix.lower() in {'.sqlite','.sqlite3','.db'} and hashlib.sha256(str(p).encode()).hexdigest()[:16]==target:found=p;break
 if found:break
assert found
c=sqlite3.connect('file:'+str(found)+'?mode=ro',uri=True,timeout=3)
deadline=time.monotonic()+20
c.set_progress_handler(lambda: int(time.monotonic()>deadline),10000)
report={'db_id':target,'groups':{},'json_schemas':{},'server_modified':False}
queries={
'documenti_stati':'SELECT status,COUNT(*) FROM fascicolo_documenti_ai GROUP BY status',
'atti_editor_stati':'SELECT status,COUNT(*) FROM fascicolo_editor_ai_atti GROUP BY status',
'testi_estrazione':'SELECT extraction_engine,COUNT(*) FROM fascicolo_documenti_ai_testi GROUP BY extraction_engine',
'atti_classificati':'SELECT document_nature,document_label,status,COUNT(*) FROM document_catalog_assignments GROUP BY document_nature,document_label,status ORDER BY COUNT(*) DESC LIMIT 60',
'fascicoli_con_testi':'SELECT COUNT(*),COUNT(DISTINCT fascicolo_id) FROM fascicolo_documenti_ai_testi'}
for key,q in queries.items():
 deadline=time.monotonic()+20
 try:report['groups'][key]=c.execute(q).fetchall()
 except Exception as e:report['groups'][key]={'error_type':type(e).__name__}
for table,col in [('fascicoli','documenti_json'),('fascicoli','dati_json'),('case_document_contexts','context_json')]:
 deadline=time.monotonic()+10
 try:
  rows=c.execute('SELECT '+col+' FROM '+table+' WHERE '+col+" IS NOT NULL AND "+col+"!='' LIMIT 5").fetchall();shapes=[]
  for row in rows:
   d=json.loads(row[0]);first=d[0] if isinstance(d,list) and d else d;shapes.append({'type':type(d).__name__,'keys':list(first)[:60] if isinstance(first,dict) else [],'length':len(d) if isinstance(d,(dict,list)) else 0})
  report['json_schemas'][table+'.'+col]=shapes
 except Exception as e:report['json_schemas'][table+'.'+col]={'error_type':type(e).__name__}
print(json.dumps(report))
'''
r=subprocess.run(['docker','exec','-i','iusentra-app','python','-'],input=code,text=True,capture_output=True,timeout=150)
if r.returncode:
 print(json.dumps({'metadata_diagnostic_error':r.returncode,'stderr':r.stderr[-2000:]}));raise SystemExit(r.returncode)
print(r.stdout)
