# Dipendenze Dependabot — 30/09/2026

## Stato operativo

Correzione locale predisposta per la versione 2.434.1. **Lavoro aperto: non verificato su macchina reale; nessun commit, push o deploy di questa correzione.**

La lettura autenticata degli avvisi GitHub ha restituito 20 avvisi aperti (6 alti, 11 moderati, 3 bassi), tutti su `pnpm-lock.yaml`, invece dei 14 indicati nel messaggio iniziale. Il branch predefinito è `claude/legal-electronic-filing-kIxcV`; revisione analizzata: `1d9bf127bde01c23be7e854c0752629f8d5669c2`.

Fonte: https://github.com/antmm2605/IUSENTRA/security/dependabot

## Correzione mirata

| Pacchetto | Versione precedente nel lockfile | Versione predisposta | Avvisi aperti interessati |
|---|---|---|---|
| fast-uri | 3.1.6 | 3.1.8 | 80, 65, 61 |
| ip-address | 10.3.1 | 10.7.1 | 79, 78, 64, 63 |
| brace-expansion | 5.0.9 | 5.0.12 | 77, 76, 75 |
| undici | 7.29.0 | 7.29.1 | 74, 73, 72, 71, 70, 69, 68, 67, 66, 62 |

Aggiornati gli override di `pnpm-workspace.yaml` e quelli del manifest frontend; rigenerato `pnpm-lock.yaml` con pnpm 11.22.0, senza aggiornare altre dipendenze. Installazione successiva con lockfile congelato. Versione allineata in `pct/__init__.py`, `setup.py`, `Dockerfile`, `railway.toml`, `frontend/package.json` e OpenAPI; changelog aggiornato.

Non sono state modificate logica applicativa, schema SQL, API operative, componenti React, bundle distribuito, Local Signer, firma, deposito o PEC. Il confronto preliminare delle impronte con `D:/legale/backups/IUSENTRA/deposito-accettato-20260909_195010/source-manifest.json` ha rilevato differenze già presenti sui manifest e file di versione rispetto al backup del 09/09/2026. Non è stato eseguito alcun ripristino della baseline né attribuita a questa correzione la parità con quella versione storica.

## Valutazione statica degli avvisi

Le versioni vulnerabili erano presenti nel grafo Node. I collegamenti osservati includono `shadcn` e `@dotenvx/dotenvx` per undici, `ajv` per fast-uri, `express-rate-limit` e `socks` per ip-address, `minimatch` per brace-expansion. Nessun import applicativo diretto individuato nelle sorgenti React esaminate. Il Dockerfile distingue il builder Node dal runtime Python e `.dockerignore` esclude `node_modules`.

Questa evidenza non dimostra né esclude la sfruttabilità di ogni API vulnerabile attraverso gli strumenti di sviluppo e tutte le configurazioni supportate. Ciascuno dei 20 avvisi resta quindi classificato `needs_review`, con confidenza media: è certa la presenza della versione, ma non è dimostrata la catena completa da input di un attore meno privilegiato all'effetto dell'advisory. Nessun avviso è stato chiuso o ignorato manualmente su GitHub. Il dettaglio individuale e la graduatoria provvisoria sono conservati nell'artefatto gestito Codex Security `artifacts/dependabot-20260930-triage.json`.

## Controlli tecnici eseguiti

- `pnpm install --lockfile-only --ignore-scripts`: esito positivo, politiche supply-chain su 744 voci rispettate.
- `pnpm install --frozen-lockfile --ignore-scripts`: esito positivo; quattro pacchetti scaricati, grafo coerente con il lockfile.
- `pnpm audit --json`: zero vulnerabilità info/basse/moderate/alte/critiche su 744 dipendenze, comprese quelle di sviluppo; rieseguito dopo il bump.
- `pnpm --filter @iusentra/studio typecheck`: esito positivo.
- `pnpm --filter @iusentra/studio test`: 80 test JavaScript superati, nessuno saltato; contratti React, hook, notifiche, design system, assistente, Legal Skills e copertura delle pagine Storybook superati.
- Build Vite verso una directory temporanea di verifica: 2.517 moduli, 3,68 secondi, budget asset rispettato. Non sostituisce il bundle operativo né la prova locale 8080.
- `pnpm --filter @iusentra/studio test:storybook`: prima esecuzione fallita perché mancava il Chromium richiesto. Installato con il comando ufficiale Playwright, poi rilanciato: 18 file e 100 test superati, 20,58 secondi. Prova sintetica, non accettazione reale.
- `python tools/sync_packaging_files.py --check`: packaging flat sincronizzato.
- `python tools/check_python_baseline.py`: configurazione Python 3.12 coerente; esecuzione locale su Python 3.14.
- Ruff E9/F63/F7/F82 sui file Python di versione modificati: esito positivo.
- `python tools/check_repo_governance.py`: esito positivo, inclusa integrità UTF-8 dei testi governati.
- `python -m pytest -q tests/test_packaging_consistency.py --tb=short`: 10 test superati dopo il consolidamento motivato del manifest PAdES; insieme alla verifica eIDAS, 15 test superati. Altri 17 test PKCS#11 e formati eIDAS superati.

## Verifica materiale locale e preparazione del rilascio

Il 30/09/2026 il canale browser nativo ha ripreso a funzionare dopo il riavvio di Codex: inventario e scheda integrata reale accessibili. L'utente ha effettuato personalmente l'accesso locale, senza comunicare la password. Copia Docker aggiornata su `127.0.0.1:8080`, readiness 2.434.1 e container healthy.

Prova nella scheda visibile: Panoramica caricata su dati presenti (14 fascicoli e 121 PEC da leggere), navigazione con click al menu Fascicoli, elenco dei 14 fascicoli, apertura del caso controllato FF8E5A4B, espansione Documenti e atti, caricamento del catalogo SQL e apertura di `ricorso_originale_collaudo.pdf` nel lettore interno. Verificato il contenuto della pagina PDF e chiusura della preview. Scroll al centro e fondo della Panoramica e del fascicolo; viste mobile 390 x 844 e tablet 768 x 1024, con ripristino desktop. Prove JPEG conservate nel backup locale `igiene-20260930-dipendenze/prove-browser`.

Questa prova riguarda navigazione e lettura dopo l'aggiornamento delle dipendenze. Non certifica firma con token, PIN, deposito o invio PEC, che non sono stati eseguiti o modificati. Non è un audit funzionale completo di ogni area del prodotto.

Igiene: 2.134 file non tracciati classificati come output, backup, bundle storici, script temporanei o dati runtime, conservati con SHA-256 verificato in `D:/legale/backups/IUSENTRA/igiene-20260930-dipendenze/manifest.json`. Gli asset non tracciati sono stati confrontati con i riferimenti dei bundle tracciati: nessuno è richiesto dal bundle operativo. Configurazione personale `.codex/hooks.json` conservata in sede ed esclusa soltanto dall'indice locale. Report CI storici copiati nel medesimo backup e riallineati a HEAD; test archivio letture riallineato nei soli terminatori dopo confronto del contenuto invariato. Nessun dato sotto `data/`, volume o documento operativo cancellato.

## Verifiche successive ancora richieste

Prima della chiusura: commit e push dei branch gemelli, gate GitHub del nuovo SHA, conferma della chiusura automatica degli avvisi Dependabot, deploy Hetzner con backup e guardia sorgenti, readiness e container app unico, pulizia immagini ufficiale e riallineamento locale finale. Il branch remoto protetto resta escluso da ogni aggiornamento.
