#!/usr/bin/env bash
# Installa sul server il pacchetto Normattiva preparato sul PC (scripts/lex_normattiva_locale.py pacchetto).
#
# Dal PC (WSL):
#   scp lex-fonti-AAAAMMGG-HHMM.tar.zst lex-fonti-AAAAMMGG-HHMM.tar.zst.sha256 UTENTE@SERVER:/opt/iusentra/import/
# Sul server:
#   sudo /opt/iusentra/repo/deploy/hetzner/carica_fonti_lex.sh --dry-run /opt/iusentra/import/lex-fonti-AAAAMMGG-HHMM.tar.zst
#   sudo /opt/iusentra/repo/deploy/hetzner/carica_fonti_lex.sh           /opt/iusentra/import/lex-fonti-AAAAMMGG-HHMM.tar.zst
# Tornare indietro a mano:
#   sudo /opt/iusentra/repo/deploy/hetzner/carica_fonti_lex.sh --ripristina /opt/iusentra/backups/fonti_lex_AAAAMMGG-HHMMSS
#
# Passi: checksum -> estrazione in cartella temporanea -> controllo SHA256SUMS interno -> stop scheduler-worker ->
# backup con data (hard link, nessuna copia se stesso disco) -> sostituzione con rename -> permessi -> riavvio ->
# controllo (conteggi + ricerca "art. 2043 c.c.") -> in caso di errore ripristino del backup.
set -euo pipefail

IUSENTRA_HOME="${IUSENTRA_HOME:-/opt/iusentra}"
DATA_DIR="${IUSENTRA_DATA_DIR:-${IUSENTRA_HOME}/data}"
REPO_DIR="${REPO_DIR:-${IUSENTRA_HOME}/repo}"
ENV_FILE="${IUSENTRA_ENV_FILE:-${IUSENTRA_HOME}/.env.hetzner}"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_DIR}/deploy/hetzner/docker-compose.hetzner.yml}"
BACKUP_ROOT="${IUSENTRA_FONTI_LEX_BACKUP_DIR:-${IUSENTRA_BACKUP_DIR:-${IUSENTRA_HOME}/backups}}"
DOCKER="${DOCKER:-docker}"
SERVIZIO_WORKER="${FONTI_LEX_SERVIZIO_WORKER:-scheduler-worker}"
SERVIZIO_APP="${FONTI_LEX_SERVIZIO_APP:-app}"
DB_NEL_CONTAINER="${FONTI_LEX_DB_CONTAINER:-/data/normativa/normattiva.sqlite}"
ATTESA_WORKER_S="${FONTI_LEX_ATTESA_WORKER_S:-120}"
QUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"

DRY_RUN=0
RIAVVIA_APP=1
PACCHETTO=""
RIPRISTINA_DA=""

uso() {
  cat >&2 <<USO
Uso: carica_fonti_lex.sh [--dry-run] [--non-riavviare-app] PACCHETTO.tar.zst
     carica_fonti_lex.sh --ripristina CARTELLA_BACKUP
  --dry-run            mostra cosa farebbe; verifica solo il checksum, non tocca nulla
  --non-riavviare-app  non riavvia il servizio '${SERVIZIO_APP}' (di default viene riavviato per riaprire il database)
  --ripristina DIR     rimette a posto un backup creato da questo script
USO
  exit "${1:-1}"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --non-riavviare-app) RIAVVIA_APP=0 ;;
    --ripristina) shift; RIPRISTINA_DA="${1:-}"; [ -n "$RIPRISTINA_DA" ] || uso 1 ;;
    -h|--help) uso 0 ;;
    -*) echo "Opzione sconosciuta: $1" >&2; uso 1 ;;
    *) [ -z "$PACCHETTO" ] || uso 1; PACCHETTO="$1" ;;
  esac
  shift
done
if [ -z "$RIPRISTINA_DA" ] && { [ -z "$PACCHETTO" ] || [ ! -f "$PACCHETTO" ]; }; then
  echo "Pacchetto non trovato: '${PACCHETTO}'" >&2
  uso 1
fi

log() { printf '[carica_fonti_lex] %s\n' "$*"; }
fail() { printf '[carica_fonti_lex] ERRORE: %s\n' "$*" >&2; exit 1; }
azione() {
  # Esegue il comando, oppure lo mostra soltanto con --dry-run.
  if [ "$DRY_RUN" = "1" ]; then
    printf '[dry-run] %s\n' "$*"
  else
    "$@"
  fi
}
compose() { "$DOCKER" compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }

NORMATIVA="${DATA_DIR}/normativa"
# Elementi sostituiti, relativi a <data>/normativa.
ELEMENTI_FILE=("normattiva.sqlite" "index/normattiva_chunks.jsonl")
ELEMENTO_DIR="vettori_normattiva"

tar_pacchetto() {
  local archivio="$1"; shift
  case "$archivio" in
    *.tar.zst) tar --zstd -f "$archivio" "$@" ;;
    *.tar.gz|*.tgz) tar -z -f "$archivio" "$@" ;;
    *) fail "formato non supportato: $archivio (usa .tar.zst o .tar.gz)" ;;
  esac
}

json_get() {
  python3 -c 'import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))' "$1"
}

SERVIZI_FERMATI=0
STAGING=""
BACKUP=""
SOSTITUITI=()   # elementi toccati dallo swap (per il ripristino automatico)

riavvia_servizi() {
  [ "$SERVIZI_FERMATI" = "1" ] || return 0
  log "riavvio ${SERVIZIO_WORKER}"
  compose up -d --no-deps "$SERVIZIO_WORKER" || log "ATTENZIONE: riavvio di ${SERVIZIO_WORKER} non riuscito"
  if [ "$RIAVVIA_APP" = "1" ]; then
    log "riavvio ${SERVIZIO_APP} per riaprire il database"
    compose restart "$SERVIZIO_APP" || log "ATTENZIONE: riavvio di ${SERVIZIO_APP} non riuscito"
  fi
  SERVIZI_FERMATI=0
}

rimuovi_sidecar_db() {
  # Un -wal/-shm del vecchio database danneggerebbe il nuovo.
  rm -f "${NORMATIVA:?}/normattiva.sqlite-wal" "${NORMATIVA:?}/normattiva.sqlite-shm" "${NORMATIVA:?}/normattiva.sqlite-journal"
}

copia_leggera() {
  # Hard link se possibile (nessuno spazio extra), altrimenti copia.
  cp -al "$1" "$2" 2>/dev/null || cp -a "$1" "$2"
}

ripristina_da_backup() {
  # $1 = cartella backup (contiene normativa/<elemento> e ELENCO.txt con "presente <rel>" / "nuovo <rel>")
  local dir="$1" tipo rel dest tmp
  [ -f "${dir}/ELENCO.txt" ] || fail "backup non valido: manca ${dir}/ELENCO.txt"
  log "ripristino da ${dir}"
  while IFS=' ' read -r tipo rel; do
    [ -n "${rel:-}" ] || continue
    dest="${NORMATIVA:?}/${rel}"
    tmp="${dest}.ripristino_${STAMP}"
    case "$tipo" in
      presente)
        mkdir -p "$(dirname "$dest")"
        copia_leggera "${dir}/normativa/${rel}" "$tmp"
        if [ -d "$tmp" ]; then
          if [ -e "$dest" ]; then mv -T "$dest" "${dest}.scartato_${STAMP}"; fi
          mv -T "$tmp" "$dest"
          rm -rf "${dest:?}.scartato_${STAMP}"
        else
          mv -f -T "$tmp" "$dest"
        fi
        ;;
      nuovo)
        rm -rf "${dest:?}"
        ;;
    esac
  done < "${dir}/ELENCO.txt"
  rimuovi_sidecar_db
}

if [ -n "$RIPRISTINA_DA" ]; then
  [ -d "$RIPRISTINA_DA" ] || fail "cartella backup non trovata: $RIPRISTINA_DA"
  log "ripristino manuale da ${RIPRISTINA_DA}"
  if [ "$DRY_RUN" = "1" ]; then
    log "[dry-run] ferma ${SERVIZIO_WORKER}, rimette gli elementi elencati sotto, riavvia"
    cat "${RIPRISTINA_DA}/ELENCO.txt"
    exit 0
  fi
  compose stop "$SERVIZIO_WORKER"; SERVIZI_FERMATI=1
  ripristina_da_backup "$RIPRISTINA_DA"
  riavvia_servizi
  log "ripristino completato"
  exit 0
fi

# ---------------------------------------------------------------------------------------------- #
# 1. Checksum del pacchetto
# ---------------------------------------------------------------------------------------------- #
mkdir -p "$IUSENTRA_HOME" 2>/dev/null || true
if command -v flock >/dev/null 2>&1 && exec 9>"${IUSENTRA_HOME}/.carica_fonti_lex.lock" 2>/dev/null; then
  flock -n 9 || fail "un'altra esecuzione di carica_fonti_lex.sh e' in corso"
fi

SIDECAR="${PACCHETTO}.sha256"
[ -f "$SIDECAR" ] || fail "manca il file di checksum ${SIDECAR} (copialo insieme al pacchetto)"
log "verifica checksum SHA-256 di $(basename "$PACCHETTO")"
( cd "$(dirname "$PACCHETTO")" && sha256sum -c "$(basename "$SIDECAR")" ) || fail "checksum del pacchetto NON valido: copia danneggiata, ricopiare"

META="$(tar_pacchetto "$PACCHETTO" -x -O --occurrence=1 PACCHETTO.json)" || fail "PACCHETTO.json non leggibile"
N_DOC="$(printf '%s' "$META" | json_get 'd["conteggi"]["documenti"]')"
N_ART="$(printf '%s' "$META" | json_get 'd["conteggi"]["articoli"]')"
N_CHUNK="$(printf '%s' "$META" | json_get 'd["conteggi"]["chunk"]')"
CON_VETTORI="$(printf '%s' "$META" | json_get '1 if d["vettori"].get("presente") else 0')"
RIGHE_VETTORI="$(printf '%s' "$META" | json_get 'd["vettori"].get("righe", -1) if d["vettori"].get("presente") else -1')"
CON_JSONL="$(printf '%s' "$META" | json_get '1 if d.get("con_jsonl") else 0')"
BYTE_TOTALI="$(printf '%s' "$META" | json_get 'sum(f["byte"] for f in d["file"])')"
CREATO="$(printf '%s' "$META" | json_get 'd["creato"]')"
log "pacchetto del ${CREATO}: ${N_DOC} documenti, ${N_ART} articoli, ${N_CHUNK} chunk, vettori=${CON_VETTORI}, jsonl=${CON_JSONL}, ${BYTE_TOTALI} byte decompressi"

# Spazio: estrazione (1x); il backup usa hard link (0x se stesso disco).
mkdir -p "$NORMATIVA" 2>/dev/null || true
DISPONIBILE="$(df -PB1 "$DATA_DIR" 2>/dev/null | awk 'NR==2{print $4}')"
NECESSARIO=$(( BYTE_TOTALI + BYTE_TOTALI / 10 ))
if [ -n "${DISPONIBILE:-}" ] && [ "$DISPONIBILE" -lt "$NECESSARIO" ]; then
  fail "spazio insufficiente in ${DATA_DIR}: disponibili ${DISPONIBILE} byte, servono circa ${NECESSARIO}"
fi

STAGING="${NORMATIVA}/.carica_fonti_lex_${STAMP}"
BACKUP="${BACKUP_ROOT}/fonti_lex_${STAMP}"

# ---------------------------------------------------------------------------------------------- #
# Dry-run: solo il piano
# ---------------------------------------------------------------------------------------------- #
if [ "$DRY_RUN" = "1" ]; then
  log "DRY-RUN: nessuna modifica. Cosa farei:"
  log "contenuto del pacchetto:"
  tar_pacchetto "$PACCHETTO" -t | sed 's/^/    /'
  azione tar_pacchetto "$PACCHETTO" -x -p -C "$STAGING"
  azione compose stop "$SERVIZIO_WORKER"
  azione mkdir -p "$BACKUP"
  for rel in "${ELEMENTI_FILE[@]}" "$ELEMENTO_DIR"; do
    if [ -e "${NORMATIVA}/${rel}" ]; then
      azione cp -al "${NORMATIVA}/${rel}" "${BACKUP}/normativa/${rel}"
    else
      log "(${rel}: non esiste ora, verra' creato)"
    fi
  done
  azione mv -f -T "${STAGING}/normativa/normattiva.sqlite" "${NORMATIVA}/normattiva.sqlite"
  if [ "$CON_VETTORI" = "1" ]; then
    azione mv -T "${STAGING}/normativa/${ELEMENTO_DIR}" "${NORMATIVA}/${ELEMENTO_DIR}"
  fi
  azione chown -R --reference "$NORMATIVA" "${NORMATIVA}/normattiva.sqlite"
  azione compose up -d --no-deps "$SERVIZIO_WORKER"
  if [ "$RIAVVIA_APP" = "1" ]; then azione compose restart "$SERVIZIO_APP"; fi
  azione compose exec -T "$SERVIZIO_WORKER" python - --db "$DB_NEL_CONTAINER" --documenti "$N_DOC" --articoli "$N_ART" --chunk "$N_CHUNK" --righe-vettori "$RIGHE_VETTORI"
  log "se il controllo fallisce: ripristino automatico da ${BACKUP}"
  exit 0
fi

# ---------------------------------------------------------------------------------------------- #
# 2. Estrazione in cartella temporanea (stesso filesystem dei dati: rename atomici)
# ---------------------------------------------------------------------------------------------- #
pulisci() {
  local codice=$?
  if [ "$codice" -ne 0 ] && [ "${#SOSTITUITI[@]}" -gt 0 ] && [ -n "$BACKUP" ] && [ -f "${BACKUP}/ELENCO.txt" ]; then
    log "ERRORE (codice ${codice}): ripristino del backup ${BACKUP}"
    ripristina_da_backup "$BACKUP" || log "RIPRISTINO FALLITO: ripristinare a mano con --ripristina ${BACKUP}"
    SERVIZI_FERMATI=1   # riavvia di nuovo worker e app sui file ripristinati
  fi
  if [ "$SERVIZI_FERMATI" = "1" ]; then riavvia_servizi; fi
  if [ -n "$STAGING" ]; then rm -rf "${STAGING:?}"; fi
  return "$codice"
}
trap pulisci EXIT

log "estrazione in ${STAGING}"
mkdir -p "$STAGING"
tar_pacchetto "$PACCHETTO" -x -p -C "$STAGING"
( cd "$STAGING" && sha256sum --quiet -c SHA256SUMS ) || fail "SHA256SUMS interno non valido: pacchetto corrotto"
[ -f "${STAGING}/normativa/normattiva.sqlite" ] || fail "il pacchetto non contiene normativa/normattiva.sqlite"
if [ "$CON_VETTORI" = "1" ] && [ ! -f "${STAGING}/normativa/${ELEMENTO_DIR}/meta.json" ]; then
  fail "il pacchetto dichiara i vettori ma ${ELEMENTO_DIR}/meta.json manca"
fi

# Permessi e proprietario come gli altri dati.
RIFERIMENTO="$NORMATIVA"
if [ ! -e "$RIFERIMENTO" ]; then RIFERIMENTO="$DATA_DIR"; fi
if ! chown -R --reference "$RIFERIMENTO" "${STAGING}/normativa" 2>/dev/null; then
  [ "$(stat -c %u "$RIFERIMENTO")" = "$(id -u)" ] || fail "impossibile impostare il proprietario come ${RIFERIMENTO} (eseguire con sudo)"
fi
chmod -R u+rwX,go-rwx "${STAGING}/normativa"

# ---------------------------------------------------------------------------------------------- #
# 3. Stop worker, backup, sostituzione atomica
# ---------------------------------------------------------------------------------------------- #
log "stop ${SERVIZIO_WORKER}"
compose stop "$SERVIZIO_WORKER"
SERVIZI_FERMATI=1

mkdir -p "${BACKUP}/normativa/index"
ELENCO=""
for rel in "${ELEMENTI_FILE[@]}" "$ELEMENTO_DIR"; do
  if [ -e "${NORMATIVA}/${rel}" ]; then
    copia_leggera "${NORMATIVA}/${rel}" "${BACKUP}/normativa/${rel}"
    ELENCO+="presente ${rel}"$'\n'
  else
    ELENCO+="nuovo ${rel}"$'\n'
  fi
done
printf '%s' "$ELENCO" > "${BACKUP}/ELENCO.txt"
log "backup in ${BACKUP}"

mkdir -p "${NORMATIVA}/index"
SOSTITUITI+=("normattiva.sqlite")
mv -f -T "${STAGING}/normativa/normattiva.sqlite" "${NORMATIVA}/normattiva.sqlite"
rimuovi_sidecar_db
if [ "$CON_JSONL" = "1" ] && [ -f "${STAGING}/normativa/index/normattiva_chunks.jsonl" ]; then
  mv -f -T "${STAGING}/normativa/index/normattiva_chunks.jsonl" "${NORMATIVA}/index/normattiva_chunks.jsonl"
fi
if [ "$CON_VETTORI" = "1" ]; then
  SOSTITUITI+=("$ELEMENTO_DIR")
  if [ -e "${NORMATIVA}/${ELEMENTO_DIR}" ]; then mv -T "${NORMATIVA}/${ELEMENTO_DIR}" "${NORMATIVA}/${ELEMENTO_DIR}.vecchio_${STAMP}"; fi
  mv -T "${STAGING}/normativa/${ELEMENTO_DIR}" "${NORMATIVA}/${ELEMENTO_DIR}"
  rm -rf "${NORMATIVA:?}/${ELEMENTO_DIR:?}.vecchio_${STAMP}"
fi
log "file sostituiti"

# ---------------------------------------------------------------------------------------------- #
# 4. Riavvio e controllo
# ---------------------------------------------------------------------------------------------- #
riavvia_servizi
log "attesa del servizio ${SERVIZIO_WORKER} (max ${ATTESA_WORKER_S}s)"
ATTESA=0
until [ -n "$(compose ps --status running -q "$SERVIZIO_WORKER" 2>/dev/null)" ]; do
  ATTESA=$((ATTESA + 2))
  [ "$ATTESA" -le "$ATTESA_WORKER_S" ] || fail "${SERVIZIO_WORKER} non e' ripartito"
  sleep 2
done
log "controllo: conteggi e ricerca 'art. 2043 c.c.'"
compose exec -T "$SERVIZIO_WORKER" python - --db "$DB_NEL_CONTAINER" \
  --documenti "$N_DOC" --articoli "$N_ART" --chunk "$N_CHUNK" --righe-vettori "$RIGHE_VETTORI" \
  < "${QUI}/verifica_fonti_lex.py" || fail "controllo post-caricamento fallito"

SOSTITUITI=()   # tutto ok: niente ripristino
trap - EXIT
rm -rf "${STAGING:?}"
log "completato. Backup precedente: ${BACKUP}"
log "Per tornare indietro: $0 --ripristina ${BACKUP}"
log "Dopo qualche giorno senza problemi, liberare spazio eliminando la cartella ${BACKUP}"
