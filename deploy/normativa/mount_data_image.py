"""Monta esclusivamente l'immagine dati configurata; mai crea o formatta dischi."""
from pathlib import Path
import argparse,json,subprocess,time,fcntl

def run(*args):
 return subprocess.run(args,text=True,capture_output=True,check=True).stdout

def dispositivi_immagine(image):
 matches=[]
 identity=image.stat()
 for backing in Path('/sys/block').glob('loop*/loop/backing_file'):
  try:
   candidate=Path(backing.read_text().strip())
   stat=candidate.stat()
  except FileNotFoundError:
   continue
  if (stat.st_dev,stat.st_ino)==(identity.st_dev,identity.st_ino):
   matches.append('/dev/'+backing.parent.parent.name)
 return sorted(matches)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--check',action='store_true');args=parser.parse_args()
 cfg=json.loads(Path(args.config).read_text());image=Path(cfg['image']);target=Path(cfg['target']);expected=cfg['uuid']
 if not image.is_absolute() or not target.is_absolute() or not isinstance(expected,str) or not expected:raise ValueError('Configurazione dati non valida')
 deadline=time.monotonic()+(0 if args.check else 120)
 while not image.is_file():
  if time.monotonic()>=deadline:raise RuntimeError('Immagine dati non disponibile; nessun archivio vuoto creato')
  time.sleep(2)
 image=image.resolve(strict=True)
 # Lock globale fra namespace: il file deve essere sullo stesso filesystem radice.
 lock=open('/run/lock/iusentra-normativa-image.lock','a')
 fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
 devices=dispositivi_immagine(image)
 if len(devices)>1:raise RuntimeError('Immagine associata a piu loop device: ripristino verificato necessario, nessun mount')
 if not target.is_dir():raise RuntimeError('Punto di mount non predisposto')
 target=target.resolve(strict=True)
 probe=subprocess.run(['findmnt','--json','--mountpoint',str(target),'--output','SOURCE,FSTYPE'],text=True,capture_output=True)
 if probe.returncode:
  if args.check:raise RuntimeError('Archivio dati non montato')
  actual=run('blkid','-p','-s','UUID','-o','value',str(image)).strip()
  if actual!=expected:raise RuntimeError('UUID immagine discordante; nessun mount')
  if any(target.iterdir()):raise RuntimeError('Punto di mount non vuoto: nessun occultamento di dati')
  if devices:
   device=devices[0]
  else:
   device=run('losetup','--find','--show','--nooverlap',str(image)).strip()
  if dispositivi_immagine(image)!=[device]:raise RuntimeError('Associazione loop non univoca: nessun mount')
  # Montare lo STESSO block device riusa il superblock anche fra namespace.
  run('mount','-t','ext4',device,str(target))
  probe=subprocess.run(['findmnt','--json','--mountpoint',str(target),'--output','SOURCE,FSTYPE'],text=True,capture_output=True,check=True)
 rows=json.loads(probe.stdout)['filesystems']
 if len(rows)!=1 or rows[0]['fstype']!='ext4':raise RuntimeError('Mount inatteso')
 device=rows[0]['source']
 if dispositivi_immagine(image)!=[device]:raise RuntimeError('Vista montata non univoca')
 loops=json.loads(run('losetup','--json','--list',device)).get('loopdevices',[])
 if len(loops)!=1 or Path(loops[0]['back-file']).resolve()!=image:raise RuntimeError('Immagine del mount discordante')
 if run('blkid','-s','UUID','-o','value',device).strip()!=expected:raise RuntimeError('UUID mount discordante')
 print(json.dumps({'stato':'montato_verificato','image':str(image),'target':str(target),'uuid':expected,'nessuna_formattazione':True}))

if __name__=='__main__':main()
