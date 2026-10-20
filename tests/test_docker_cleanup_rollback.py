"""La pulizia ripetuta conserva il ripristino fuori dall'ambiente del deploy."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_due_pulizie_conservano_ripristino_persistente(tmp_path):
    bash = shutil.which('bash')
    if not bash or os.name == 'nt':
        pytest.skip('Guardrail shell nel container Linux nativo')
    repository = tmp_path / 'repo'
    repository.mkdir()
    tools = tmp_path / 'bin'
    tools.mkdir()
    removed = tmp_path / 'removed.txt'
    rollback, obsolete = 'b' * 40, 'c' * 40
    (tmp_path / '.iusentra-rollback-image').write_text(f'iusentra-app:{rollback}\n')
    docker = tools / 'docker'
    docker.write_text("""#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
with open(os.environ['CALLS'],'a') as f:f.write(' '.join(args)+chr(10))
if args[:2]==['ps','-aq']:
    pass
elif args and args[0]=='ps':
    print('iusentra-app:'+('a'*40))
elif args and args[0]=='images':
    for char in 'abc':print('iusentra-app'+chr(9)+char*40+chr(9)+'sha256:'+char*64)
elif args[:2]==['image','rm']:
    with open(os.environ['REMOVED'],'a') as f:f.write(args[2]+chr(10))
""")
    docker.chmod(0o755)
    environment = dict(os.environ, PATH=str(tools)+os.pathsep+os.environ['PATH'], REMOVED=str(removed), CALLS=str(tmp_path / 'calls.txt'), IUSENTRA_REPO_DIR=str(repository))
    environment.pop('IUSENTRA_DOCKER_KEEP_REFS', None)
    environment.pop('IUSENTRA_DOCKER_CACHE_IDS', None)
    environment.pop('IUSENTRA_DOCKER_ROLLBACK_IMAGE_FILE', None)
    source = Path(__file__).resolve().parents[1] / 'deploy/hetzner/cleanup_docker_images.sh'
    script = tmp_path / 'cleanup.sh'
    script.write_text(source.read_text(), encoding='utf-8', newline='\n')
    for _ in range(2):
        result = subprocess.run([bash,str(script)],cwd=repository,env=environment,capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
    assert removed.read_text().splitlines() == [f'iusentra-app:{obsolete}'] * 2

    before = removed.read_text()
    (tmp_path / '.iusentra-rollback-image').write_text('postgres:foreign-project')
    rejected = subprocess.run([bash,str(script)],cwd=repository,env=environment,capture_output=True,text=True)
    assert rejected.returncode != 0
    assert removed.read_text() == before

    calls = Path(environment['CALLS'])
    assert not any('prune' in call for call in calls.read_text().splitlines())
    original_calls = calls.read_text()
    environment['IUSENTRA_DOCKER_CACHE_IDS'] = 'not-a-cache;foreign'
    invalid = subprocess.run([bash, str(script)], cwd=repository, env=environment, capture_output=True, text=True)
    assert invalid.returncode != 0
    assert calls.read_text() == original_calls
    (tmp_path / '.iusentra-rollback-image').write_text(f'iusentra-app:{rollback}\n')
    environment['IUSENTRA_DOCKER_CACHE_IDS'] = 'ownedcache1234567890'
    scoped = subprocess.run([bash, str(script)], cwd=repository, env=environment, capture_output=True, text=True)
    assert scoped.returncode == 0, scoped.stderr
    pruning = [call for call in calls.read_text().splitlines() if 'prune' in call]
    assert pruning == ['buildx prune --all --force --filter id=ownedcache1234567890']
