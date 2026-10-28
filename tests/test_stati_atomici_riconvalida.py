"""Il monitor non deve far perdere il checkpoint SQL persistito."""
import json
import pytest
from tools import riconvalida_cache_akn as modulo

def test_negazione_transitoria_conserva_ultimo_stato_e_riprova(tmp_path,monkeypatch):
 path=tmp_path/'stato.json';path.write_text('{"prima":true}')
 real=modulo.os.replace;calls=[]
 def replace(src,dst):
  calls.append(1)
  if len(calls)<3:
   assert json.loads(path.read_text())=={'prima':True}
   raise PermissionError('file temporaneamente aperto')
  real(src,dst)
 monkeypatch.setattr(modulo.os,'replace',replace)
 monkeypatch.setattr(modulo.time,'sleep',lambda _:None)
 modulo.atomic(path,{'dopo':True})
 assert len(calls)==3
 assert json.loads(path.read_text())=={'dopo':True}
 assert not path.with_suffix('.json.tmp').exists()

def test_negazione_persistente_non_cancella_ultimo_stato(tmp_path,monkeypatch):
 path=tmp_path/'stato.json';path.write_text('{"prima":true}')
 def denied(*_):raise PermissionError('vietato')
 monkeypatch.setattr(modulo.os,'replace',denied)
 monkeypatch.setattr(modulo.time,'sleep',lambda _:None)
 with pytest.raises(PermissionError):modulo.atomic(path,{'dopo':True})
 assert json.loads(path.read_text())=={'prima':True}
 assert json.loads(path.with_suffix('.json.tmp').read_text())=={'dopo':True}
