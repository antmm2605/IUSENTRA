#!/usr/bin/env bash
# Dati pubblici e contenitore separati; nessuna modifica ai volumi degli studi.
set -euo pipefail
expected_sha="${1:?SHA richiesto}"
bundle="${2:?Pacchetto richiesto}"
[[ "$expected_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(git rev-parse HEAD)" = "$expected_sha"
exec 9>/opt/iusentra/deploy.lock
flock -n 9 || { echo "Un altro rilascio è in corso" >&2; exit 1; }
python3 - <<'PYTEST'
import shutil
from pathlib import Path
if shutil.disk_usage('/opt/iusentra').free < 12 * 1024**3:
    raise SystemExit('Margine disco insufficiente: nessun dato viene cancellato')
info=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
if int(info['MemAvailable'].split()[0]) < 5*1024**2:
    raise SystemExit('Memoria libera insufficiente: gli altri processi restano intatti')
PYTEST
root="/opt/iusentra/openga/r6-${expected_sha}"
mkdir -p /opt/iusentra/openga
if [ ! -f "$root/INSTALLATO.json" ]; then
  python3 deploy/openga/install.py "$bundle" "$root"
fi
image="iusentra-openga:${expected_sha}"
docker build --label "io.iusentra.component=openga" --label "org.opencontainers.image.revision=$expected_sha" -t "$image" -f deploy/openga/Dockerfile .
network=$(docker inspect iusentra-app | python3 -c 'import sys,json; n=list(json.load(sys.stdin)[0]["NetworkSettings"]["Networks"]); print(next(x for x in n if "audit" not in x))')
name="iusentra-openga-${expected_sha:0:12}"
if ! docker container inspect "$name" >/dev/null 2>&1; then
  docker run -d --name "$name" --label io.iusentra.component=openga --label "org.opencontainers.image.revision=$expected_sha" --restart unless-stopped \
    --network "$network" --network-alias openga-candidate --read-only --cap-drop ALL --security-opt no-new-privileges --cpus 4 --memory 6g \
    --tmpfs /tmp:rw,noexec,nosuid,size=128m -e LEX_EMBED_URL=http://ollama:11434 -e LEX_EMBED_MODEL=embeddinggemma:300m \
    -v "$root/catalogo:/catalogo:ro" -v "$root/modello:/modello:ro" "$image"
fi
# La ricerca reale verifica anche revisione embedding, pesi, indice e classificatore.
docker exec -i "$name" python - <<'PYTEST'
import json,time,urllib.request
query="TAR L'Aquila: copie dei documenti comunali accessibili soltanto pagando quaranta euro per ciascun atto."
body=json.dumps({'q':query,'semantica':True}).encode()
t=time.perf_counter()
request=urllib.request.Request('http://127.0.0.1:8092/search',body,{'Content-Type':'application/json'})
result=json.load(urllib.request.urlopen(request,timeout=120))
assert result['ok'] and result['semantic_available'] and result['evidence_scope']=='metadata_only', result.get('message')
assert any(r['decisione_id']=='004|SENTENZA BREVE|2022|202200025' for r in result['risultati'])
assert len(result['risultati'])<=10
print(json.dumps({'ricerca_reale':'ok','secondi':round(time.perf_counter()-t,3),'risultati':len(result['risultati']),'scope':'metadata_only','training':False}))
PYTEST
# Solo dopo il riscontro positivo si sposta l'alias; vecchi contenitori conservati per ripristino.
for old in $(docker ps -q --filter label=io.iusentra.component=openga); do
  if [ "$(docker inspect -f '{{.Name}}' "$old")" != "/$name" ]; then
    docker network disconnect "$network" "$old" || true
    docker stop "$old"
  fi
done
docker network disconnect "$network" "$name"
docker network connect --alias openga-search "$network" "$name"
docker exec iusentra-app python -c "import urllib.request,json; r=json.load(urllib.request.urlopen('http://openga-search:8092/health',timeout=10)); assert r['configured']; print(r)"
printf 'Motore OpenGA attivato per %s; corpus degli studi preservati.\n' "$expected_sha"
