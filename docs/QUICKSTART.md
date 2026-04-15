# Quickstart HACS

## Obiettivo

Questa guida porta un ambiente locale da zero a un primo login verificato, con bootstrap sicurezza coerente con la repo.

## Prerequisiti

- Python 3.12 se avvii senza Docker
- Docker Desktop se usi il flusso consigliato
- Git

## Avvio consigliato con Docker

```bash
cp .env.example .env
docker compose build --no-cache
docker compose up -d
```

Il compose locale avvia:

- `app` per il traffico web
- `scheduler-worker` per i job periodici
- `ocr-worker` per OCR e indicizzazione asincrona

URL utili:

- [http://localhost](http://localhost)
- [http://localhost:8080](http://localhost:8080)
- [http://localhost/login](http://localhost/login)

## Bootstrap admin

Il bootstrap non usa piu' credenziali fisse.

- Se imposti `PCT_BOOTSTRAP_ADMIN_PASSWORD`, HACS usa quella password temporanea.
- Se non la imposti, HACS genera una password casuale al primo avvio.
- La password temporanea viene salvata in `data/auth/bootstrap_admin.json`.
- Al primo accesso il cambio password e' obbligatorio.

## Bootstrap studi e storage

Negli ambienti multi-tenant il passo successivo corretto e' entrare nel pannello `SUPERADMIN` e creare lo studio scegliendo la strategia storage:

- `JSON` per tenant piccoli o installazioni molto leggere
- `SQLite` per tenant locali robusti con `studio.db`
- `PostgreSQL` per tenant cloud/distribuiti con configurazione esterna

Se scegli `PostgreSQL`, dopo la creazione vai nel dettaglio storage dello studio e completa host, porta, database, credenziali e test connessione.

## Secret e sicurezza minima

- `.env.example` contiene solo placeholder neutri.
- `PCT_SECRET_KEY` va impostata in `.env` per un ambiente stabile.
- Se resta vuota o placeholder, HACS usa una chiave effimera e lo segnala.
- `PCT_API_V1_ALLOWED_ORIGINS` va valorizzata solo se davvero esponi l'API verso frontend esterni.

## Smoke test minimo

Dopo l'avvio verifica:

```bash
python - <<'PY'
from web.app import create_app
app = create_app({"TESTING": True})
client = app.test_client()
print(client.get("/login").status_code)
PY
```

Valore atteso: `200`.

Controlla anche che i worker siano partiti correttamente:

```bash
docker compose logs --tail=20 scheduler-worker
docker compose logs --tail=20 ocr-worker
```

Per una verifica tecnica completa del runtime puoi usare anche:

- [http://localhost/admin/osservabilita](http://localhost/admin/osservabilita)
- [http://localhost/api/metriche/runtime](http://localhost/api/metriche/runtime)

## Suite locale rapida

```bash
python -m pytest tests/test_auth.py tests/test_web_bootstrap.py tests/test_web_security.py -q
```

## PKCS#11 su Windows

Su Windows il probing PKCS#11 e' passivo di default: HACS verifica la presenza della DLL senza interrogare il provider in modo aggressivo durante i controlli di sola disponibilita'.

Override opzionale:

```bash
PCT_PKCS11_ACTIVE_PROBE=1
```

Usalo solo se devi fare diagnostica mirata del token e sai che il middleware installato e' stabile.
