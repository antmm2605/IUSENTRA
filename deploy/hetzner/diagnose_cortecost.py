from pathlib import Path
import json,hashlib
auth=Path('/root/.ssh/authorized_keys');marker='codex-lex-export-20261008'
lines=auth.read_text().splitlines(keepends=True);removed=[s for s in lines if marker in s]
assert len(removed)<=1
if removed:
 assert removed[0].startswith('restrict,command="python3 /opt/iusentra/import/lex-training-export-20261008/export.py" ssh-ed25519 ')
 temp=auth.with_name('authorized_keys.lex-export-cleanup');assert not temp.exists()
 temp.write_text(''.join(s for s in lines if marker not in s));temp.chmod(0o600);temp.replace(auth)
directory=Path('/opt/iusentra/import/lex-training-export-20261008');script=directory/'export.py'
if script.exists():script.unlink()
if directory.exists():directory.rmdir()
assert marker not in auth.read_text()
print(json.dumps({'temporary_export_key_removed':True,'removed_keys':len(removed),'temporary_script_removed':not script.exists(),'production_code_modified':False}))
