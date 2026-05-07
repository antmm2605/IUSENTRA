# Local Deep Research in IUSENTRA

Questa integrazione esegue Local Deep Research come sidecar Docker opzionale,
senza fondere la codebase esterna dentro IUSENTRA. Il percorso e' pensato per
ricerche pubbliche: normativa, dottrina, giurisprudenza pubblica, news
giuridiche e analisi di scenario con citazioni.

Fonti tecniche verificate:

- API Quick Start ufficiale LDR: https://github.com/LearningCircuit/local-deep-research/blob/main/docs/api-quickstart.md
- Docker Compose ufficiale LDR: https://github.com/LearningCircuit/local-deep-research/blob/main/docker-compose.yml

## File coinvolti

- `docker-compose.ldr.yml`: overlay Compose con `local-deep-research` e `searxng`.
- `.env.ldr.example`: variabili locali, senza credenziali reali.
- `lex/integrations/local_deep_research_client.py`: client HTTP governato per Lex.

## Avvio locale

```bash
cp .env.ldr.example .env.ldr
```

In `.env.ldr` scegliere un modello compatibile con la macchina:

```env
LDR_LLM_MODEL=gemma3:4b
```

Avviare IUSENTRA, Ollama e Local Deep Research:

```bash
docker compose --env-file .env --env-file .env.ldr \
  --profile ollama-sidecar --profile ldr \
  -f docker-compose.yml -f docker-compose.ldr.yml up -d
```

Scaricare il modello scelto:

```bash
docker exec iusentra-ollama ollama pull "$LDR_LLM_MODEL"
```

Aprire:

```text
http://localhost:5000
```

Creare il primo utente LDR, poi compilare in `.env.ldr`:

```env
LDR_USERNAME=<utente-ldr>
LDR_PASSWORD=<password-ldr>
```

Dopo il primo utente, disabilitare le registrazioni impostando nel servizio
`local-deep-research`:

```yaml
LDR_APP_ALLOW_REGISTRATIONS: "false"
```

## Collegamento a Lex

Il client usa il flusso HTTP documentato da LDR:

- `GET /auth/login` e `POST /auth/login` per sessione e CSRF;
- `GET /auth/csrf-token` per il token API;
- `POST /api/start_research`;
- `GET /api/research/{id}/status`;
- `GET /api/report/{id}`.

Test dal container app:

```bash
docker compose --env-file .env --env-file .env.ldr \
  --profile ollama-sidecar --profile ldr \
  -f docker-compose.yml -f docker-compose.ldr.yml exec app python - <<'PY'
from lex.integrations.local_deep_research_client import LocalDeepResearchClient

client = LocalDeepResearchClient()
report = client.research_and_wait(
    "Aggiornamenti recenti sulla mediazione civile obbligatoria in Italia",
    iterations=1,
)

print(report.get("summary") or report)
PY
```

## Policy di sicurezza

Il sidecar non deve diventare un canale libero per dati dello studio. Il client
Lex blocca di default query con email, codice fiscale, partita IVA, telefono,
IBAN, numero RG, fascicoli, clienti, controparti, procure o documenti allegati.

Usare LDR per:

- ricerche pubbliche;
- fonti normative e istituzionali;
- dottrina e news giuridiche;
- scenario analysis non identificativa.

Non usare LDR per:

- fascicoli, clienti, controparti, RG, CF, IBAN;
- atti o allegati interni;
- credenziali, PIN CNS/CIE/SPID o sessioni di portale;
- dati che devono restare nel retrieval tenant-aware di IUSENTRA.

`LDR_ALLOW_SENSITIVE=1` esiste solo come opt-in tecnico esplicito e non va usato
senza policy di studio, consenso e redazione preventiva.

## Note Docker

Ollama non ha autenticazione applicativa. In `docker-compose.yml` il sidecar
Ollama e' esposto solo su `127.0.0.1:11434`; se i container sono gli unici
client, si puo' rimuovere del tutto la porta host.

I dati runtime LDR e SearXNG stanno sotto:

```text
${IUSENTRA_DATA_DIR:-./data}/local-deep-research
${IUSENTRA_DATA_DIR:-./data}/searxng
```

In produzione Hetzner usare `/opt/iusentra/data` tramite `IUSENTRA_DATA_DIR`.
Il deploy standard non abilita il profilo `ldr`: l'attivazione va fatta solo
quando lo studio decide di governare anche questo sidecar.
