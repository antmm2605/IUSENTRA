# CLAUDE.md — Istruzioni per Claude Code

## Autorizzazioni generali

- **Procedi sempre senza chiedere conferma.** L'utente ha autorizzato tutte le operazioni in modo permanente.
- Commit, push, modifica file, creazione file: esegui direttamente.
- Branch di sviluppo: `claude/legal-electronic-filing-kIxcV`

## Commit e Push — REGOLA OBBLIGATORIA

**Al termine di ogni task o modifica, eseguire SEMPRE commit e push, senza eccezioni.**

Sequenza obbligatoria dopo ogni modifica:

```bash
git add <file-modificati>
git commit -m "descrizione task in italiano"
git push -u origin claude/legal-electronic-filing-kIxcV
git push origin claude/legal-electronic-filing-kIxcV:Codex/legal-electronic-filing-kIxcV 2>/dev/null || true
```

Regole:
- Non lasciare mai modifiche uncommittate alla fine di un task
- Il push su `claude/legal-electronic-filing-kIxcV` è obbligatorio e prioritario
- Il push su `Codex/legal-electronic-filing-kIxcV` va tentato sempre dopo; se restituisce 403 non bloccarsi
- Il branch `claude/` è la fonte di verità e viene sincronizzato esternamente su `Codex/`

## Deploy Hetzner automatico — REGOLA OBBLIGATORIA

**Ogni push sui branch ammessi (`claude/legal-electronic-filing-kIxcV` o `Codex/legal-electronic-filing-kIxcV`) deve produrre un deploy su Hetzner CPX42. Il task non e' chiuso finche' il deploy non e' completato con esito verde.**

Il workflow `.github/workflows/deploy-hetzner.yml` parte automaticamente ad ogni push sui due branch ammessi e si occupa di:
- backup preventivo di `/opt/iusentra/data`
- `git fetch + checkout` del commit pushato sul server Hetzner
- rebuild Docker (`--no-cache`) e restart dello stack
- verifiche `docker compose ps`, `curl /api/pronto`, `curl /legal-intelligence/`, `curl /legal-intelligence/ricerca`, `curl /ricerca-legale`
- skip automatico se il commit e' gia deployato (no-op idempotente)

Sequenza completa dopo ogni modifica (commit + push + verifica deploy):

1. Esegui la sequenza commit/push standard sopra.
2. Subito dopo il push, verifica la run del workflow:
   - apri https://github.com/antmm2605/iusentra/actions/workflows/deploy-hetzner.yml
   - identifica la run sull'ultimo commit
   - attendi l'esito (5-15 min): deve essere verde
3. Se il workflow fallisce, segnalalo all'utente con: step fallito, riga di errore, fix proposto. Non considerare il task chiuso.
4. Se Github Actions non puo' essere raggiunto (rete bloccata o token mancanti), segnalalo all'utente nel messaggio finale e proponi il fallback manuale (sequenza `ssh root@116.203.45.57 + bash deploy/hetzner/deploy.sh`).

Casi di mancato deploy automatico previsti dal workflow (non sono fallimenti):
- Commit gia deployato (es. push gemello claude/ → Codex/ subito dopo): lo step "Controlla commit gia deployato" salta backup e rebuild, il job termina in verde.
- Branch non ammesso: il workflow non si triggera per design.

Non eseguire MAI `bash deploy/hetzner/deploy.sh` o `git push` aggirando il workflow tranne nel fallback esplicito sopra: la pipeline GitHub Actions e' l'unico canale governato di deploy.

## Igiene repository — Regola obbligatoria

- Sulla macchina locale deve esistere **una sola copia attiva del progetto**: `D:\legale\IUSENTRA`.
- I **soli branch ammessi**, sia locali sia remoti, sono:
  - `claude/legal-electronic-filing-kIxcV`
  - `Codex/legal-electronic-filing-kIxcV`
- Worktree, cartelle duplicate, branch temporanei e cloni di supporto devono essere rimossi a fine lavoro.
- A fine task verificare sempre che i due branch ammessi puntino allo **stesso commit**.
- Per audit e cleanup usare lo script `scripts/repo_hygiene.ps1`.

## Progetto

**IUSENTRA** — gestionale per studi legali (Python/Flask).

- Backend: `pct/` — modelli dati e logica di business (61 moduli)
- Frontend: `web/app.py` (210+ route Flask) + `web/templates/` (177 template Jinja2) + `web/static/`
- Persistenza: file JSON per clienti, fascicoli, agenda, ecc. + SQLite per full-text search
- Stack: Python 3.12, Flask 3, Bootstrap 5, Bootstrap Icons, Gunicorn + gevent, Nginx
- Versione corrente: **2.79.1** (fonte di verità: `pct/__init__.py`)

## Modularizzazione governabile — Regola obbligatoria

- Ogni nuovo modulo o refactor deve produrre **codice governabile**, con responsabilità piccole e leggibili.
- Non è ammesso trasferire codice da un monolite a un nuovo file unico altrettanto esteso.
- Se una modifica tocca wiring Flask, servizi applicativi e logica di dominio, le parti vanno separate in moduli distinti.
- Struttura preferita:
  - `web/bootstrap/` per registrazioni, setup e integrazione Flask
  - `web/services/` per orchestrazione applicativa
  - `pct/` per regole di dominio e persistenza
- Un refactor non è considerato concluso se lascia un nuovo modulo ambiguo, multi-uso o difficile da testare.

## SCSS e UI responsive — Regola obbligatoria

- I nuovi stili UI non vanno inseriti nei template con blocchi `<style>` o con accumulo di `style="..."`, salvo casi eccezionali strettamente tecnici.
- Ogni nuova regola grafica deve vivere in `web/static/scss/` ed essere organizzata in moduli governabili:
  - `components/` per pattern condivisi
  - `pages/` per le viste specifiche
  - `mobile.scss` solo per adattamenti trasversali mobile/tablet
- Gli entrypoint compilati restano quelli caricati dalla UI (`app.scss`, `design-system.scss`, `mobile.scss`, `editor-word.scss`, `portal.scss`): non creare file SCSS orfani non inclusi nel bundle.
- Dopo modifiche SCSS, verificare sempre la compilazione CSS nel flusso Docker locale della release.
- La UI deve essere responsive su desktop, tablet e mobile, con card compatte, senza spazi morti e con messaggi utente professionali in lingua italiana.

## AI locale — Regola obbligatoria

- Il runtime AI locale (`Ollama`) va sempre trattato come **runtime sullo stesso host che esegue IUSENTRA**, non come componente distribuito al browser del cliente.
- Strategia preferita:
  - Windows self-hosted → provisioning automatico del pacchetto standalone ufficiale sullo stesso host
  - altri host/server → guida chiara e non bloccante, senza installazioni opache dal browser
- Nessuna funzione core del gestionale deve bloccarsi se l'AI locale non è disponibile.

## Railway CLI — Regola obbligatoria

- L'ambiente è abilitato anche alla **Railway CLI** con accesso operativo.
- Quando un problema si manifesta solo su Railway o in modo diverso rispetto a `localhost`, la verifica deve includere anche il servizio online tramite Railway CLI.
- Controlli minimi da fare nei casi rilevanti:
  - shell del container Railway
  - log del servizio
  - stato e contenuto del volume `/data`
  - variabili/runtime effettivi in produzione
  - risposta reale delle route online coinvolte
- Per differenze ambiente locale/produzione, non considerare concluso un fix finché non è stato verificato anche online quando Railway è raggiungibile.

## Architettura del progetto

```
iusentra/
├── pct/                    # Pacchetto Python core (logica di business)
├── web/
│   ├── app.py              # Flask app (210+ route, ~9200 righe)
│   ├── templates/          # 177 template Jinja2 organizzati per feature
│   └── static/             # CSS/SCSS/JS/icone/manifest PWA
├── tests/                  # 34 moduli di test (pytest)
├── tools/                  # Local signer per Windows/Mac/Linux
├── scripts/                # Script di build e utilità
├── Dockerfile              # Build multi-stage (builder → sass → runtime)
├── docker-compose.yml      # Stack locale (Flask + Nginx)
├── nginx.conf              # Reverse proxy, gzip, SSE
├── railway.toml            # Deploy Railway.app
├── render.yaml             # Deploy Render.com
├── vercel.json             # Deploy Vercel (serverless)
├── wsgi.py                 # Entry point WSGI
└── setup.py                # Packaging Python
```

### Moduli principali in pct/

| Modulo | Responsabilità |
|--------|---------------|
| `fascicoli.py` | Fascicoli, documenti, attività processuali, `EsitoDepositoPCT` |
| `clienti.py` | Anagrafica clienti, contatti, documenti identità |
| `soggetti.py` | Parti processuali, avvocati, testimoni |
| `agenda.py` | Appuntamenti, calendario, export iCal |
| `scadenziario.py` | Scadenze, calcolo termini, notifiche |
| `deposito.py` | Logica deposito civile/penale, state machine |
| `busta.py` | Busta telematica `.enc` (ZIP + DatiAtto.xml) |
| `firma.py` | Firma CAdES/PAdES digitale |
| `firma_pkcs11.py` | Firma via smart card (Aruba Key, PKCS#11) |
| `pec.py` | Client PEC (SMTP/IMAP), invio + polling ricevute |
| `polisWeb.py` | Integrazione portale PST/polisWeb (civile) |
| `pdp.py` | Integrazione PDP REST API (penale, D.Lgs. 150/2022) |
| `pat.py` | Integrazione PAT SOAP/SIGA (amministrativo) |
| `reginde.py` | Lookup ReGINde — PEC tribunali |
| `uffici_giudiziari.py` | Bundle 648 uffici giudiziari italiani |
| `messaggi.py` | Messaggistica multi-canale (email/SMS/WhatsApp/PEC) |
| `fatturazione.py` | Parcelle, fatture, pagamenti |
| `preventivi.py` | Preventivi e wizard tariffe |
| `pagamenti.py` | Stripe, SumUp — checkout pagamenti |
| `auth.py` | Autenticazione, ruoli, 2FA/TOTP, audit log |
| `condivisione.py` | Cartelle condivise, link temporanei, portale cliente |
| `backup.py` | Backup/ripristino dati JSON |
| `config_studio.py` | Configurazione studio (PEC, SMTP, API key) |
| `scheduler.py` | Task scheduling (APScheduler) |
| `search_index.py` | Ricerca full-text SQLite FTS5 + cache OCR |
| `ocr.py` | OCR documenti (pytesseract + pdfplumber) |
| `reports.py` | Generazione PDF (ReportLab) |
| `privacy.py` | Registro trattamenti GDPR |
| `tenant.py` | Multi-tenant SaaS — isolamento dati per studio |
| `legal_intelligence.py` | Ricerca giurisprudenza e normativa |
| `normative_tables.py` | Database norme italiane |
| `template_atti.py` | Template atti legali |
| `compilatore_atti.py` | Compilazione automatica atti da template |
| `calendar_sync.py` | Sincronizzazione iCal (Google Calendar/Outlook) |
| `portale.py` | Portale self-service per clienti |
| `workflow_onboarding.py` | Onboarding nuovi clienti |

### Struttura template web/templates/

```
templates/
├── base.html                    # Layout base (navbar, footer mobile, SSE)
├── home.html                    # Dashboard statistiche
├── auth/                        # Login, 2FA, profilo, gestione utenti
├── fascicoli/                   # Lista, form, dettaglio, documenti, wizard, editor
├── clienti/                     # Lista, form, dettaglio, cartella, faldone, portale
├── agenda.html / calendario.html
├── scadenziario/                # Lista, form, dettaglio
├── messaggi/                    # Lista, form, dettaglio
├── fatturazione/                # Lista, form, dettaglio
├── preventivi/                  # Lista, wizard tariffe
├── backup/                      # Lista, ripristino
├── polisWeb.html / polisWeb_documenti.html
├── pdp.html / pdp_documenti.html
├── pat.html / pat_documenti.html
├── soggetti/                    # Lista, form, dettaglio
├── admin/                       # Dashboard, database, studi (multi-tenant)
├── impostazioni/                # Impostazioni, calendario sync
├── privacy/                     # Registro GDPR
├── checklist/ template_atti/ wizard_pro/
├── legal_intelligence/ strumenti_legali/
├── statistiche/ email/ notifiche/ pagamenti/ portale/
└── includes/                    # _fascicolo_banner.html, _ufficio_picker.html
```

### Dipendenze principali

| Libreria | Uso |
|----------|-----|
| `flask>=3.0` | Web framework |
| `cryptography>=41` | AES-256-GCM, gestione certificati |
| `pyhanko>=0.20` | Firma PAdES PDF |
| `reportlab>=4.0` | Generazione PDF |
| `lxml>=4.9` | XML/HTML parsing (DatiAtto.xml) |
| `pdfplumber>=0.10` | Estrazione testo PDF |
| `pytesseract>=0.3.10` | OCR documenti |
| `mammoth>=1.6` | Conversione DOCX→HTML |
| `zeep>=4.2` | SOAP/WSDL client (portali giudiziari) |
| `apscheduler>=3.10` | Scheduling task |
| `twilio>=8.0` | WhatsApp/SMS |
| `stripe>=7.0` | Pagamenti carta |
| `gunicorn>=23` + `gevent>=24` | WSGI server async (SSE) |

## Regola obbligatoria — Portale Servizi Telematici

**Qualsiasi implementazione che coinvolga i portali telematici (PST/polisWeb, PDP, PAT) deve sempre rispettare le regole impartite dal Portale Servizi Telematici del Ministero della Giustizia.**

Regole chiave:
- **Vista documenti a buste (accordion)**: i documenti vanno sempre raggruppati per `id_deposito` — stessa UX per PST/polisWeb, PDP e PAT. Ogni busta è un accordion collassabile con i file della busta dentro.
- **Download non autonomo**: il gestionale mostra l'elenco degli atti ma non può scaricare documenti in autonomia — il download richiede sessione autenticata via browser sul portale ufficiale.
  - PST → `pst.giustizia.it` (autenticazione: CNS/CIE/SPID)
  - PDP → `appweb.giustizia.it` (autenticazione: CNS/CIE)
  - PAT → `giustizia-amministrativa.it/pac` (autenticazione: CNS/CIE/SPID)
- **Campi obbligatori nei modelli documento**: ogni `DocumentoXxx` (PST, PDP, PAT) deve avere `id_deposito` e `tipo_atto` per supportare la vista a buste.
- **Logica di raggruppamento nelle route**: le route `*/documenti` devono sempre costruire la lista `depositi` (dict con `id_deposito`, `tipo_atto`, `data_deposito`, `mittente`, `documenti[]`) ordinata per data decrescente, e passare sia `documenti` (lista flat) sia `depositi` (lista raggruppata) al template.
- **Fallback chiave raggruppamento**: se `id_deposito` è vuoto, usare `f"__{data_deposito}__{mittente}"` come chiave di raggruppamento.

## Script di simulazione e test — Riferimento rapido

Tutti gli script sono nella directory `tests/` ed eseguibili con `python -m pytest tests/<file> -v`.

### `tests/test_simulazione_deposito.py` — Simulazione deposito telematico (39 test)
**Riusabile per**: verificare che invio, accettazione e controllo siano conformi al PST dopo ogni modifica ai portali.

| Classe | Cosa testa |
|--------|------------|
| `TestPCTBusta` | Creazione busta `.enc`, struttura `DatiAtto.xml`, hash SHA-256, tag `Attoprincipale` |
| `TestPCTStateMachine` | Tutti i 7 stati (`INVIATO → ACCETTATO_PEC → CONSEGNATO → WARN_CONTROLLI → ERRORE_CONTROLLI → ACCETTATO_CANCELLERIA → RIFIUTATO_CANCELLERIA`) |
| `TestPCTInvioPEC` | Invio PEC mockato con struttura risposta conforme |
| `TestPDPDeposito` | Ciclo completo deposito penale: invio → accettazione PEC → controlli automatici → esito procura |
| `TestPATDeposito` | Ciclo completo deposito amministrativo: invio → accettazione PEC → controlli SIGA → esito segreteria TAR |
| `TestCoerenzaPortali` | Uniformità struttura risposta PDP/PAT, parità campi DocumentoPDP/PAT con DocumentoPolisWeb |

**Per rilanciare la simulazione completa:**
```bash
python -m pytest tests/test_simulazione_deposito.py -v
```

**Per simulare solo un portale:**
```bash
python -m pytest tests/test_simulazione_deposito.py::TestPDPDeposito -v
python -m pytest tests/test_simulazione_deposito.py::TestPATDeposito -v
python -m pytest tests/test_simulazione_deposito.py::TestPCTBusta -v
```

### Tutti i moduli di test (34 file)

| File | Cosa testa |
|------|------------|
| `test_busta.py` | Busta telematica: creazione, verifica, allegati, hash |
| `test_pec.py` | Client PEC: invio, ricevute, validazione |
| `test_fascicoli.py` | Modello fascicolo: EsitoDepositoPCT, stati, serializzazione |
| `test_reginde.py` | ReGINde: ricerca uffici, PEC tribunali |
| `test_agenda.py` | Appuntamenti: creazione, CRUD, export iCal |
| `test_auth.py` | Autenticazione, ruoli, 2FA/TOTP, permessi |
| `test_backup.py` | Backup/ripristino dati |
| `test_calendar_sync.py` | Sincronizzazione iCal — Google Calendar/Outlook |
| `test_clienti.py` / `test_clienti_workflow.py` | Anagrafica clienti, workflow onboarding |
| `test_compilatore_atti.py` | Compilazione automatica atti da template |
| `test_condivisione.py` | Cartelle condivise, link temporanei |
| `test_config_studio_smtp.py` | Configurazione studio — SMTP/PEC |
| `test_conformita_pst.py` | Conformità PST D.M. 44/2011 |
| `test_database.py` | Operazioni database, migrazioni |
| `test_legal_intelligence.py` | Ricerca giurisprudenza e normativa |
| `test_local_signer.py` | Firma locale documenti |
| `test_messaggi.py` | Messaggistica multi-canale |
| `test_motore_preventivo.py` | Motore calcolo preventivi |
| `test_normative_tables.py` | Database norme italiane |
| `test_polisweb.py` | Integrazione PolisWeb |
| `test_portale_economici.py` | Portale self-service clienti |
| `test_preventivi_wizard.py` | Wizard preventivi |
| `test_profili.py` | Profili utente e ruoli |
| `test_reports.py` | Generazione PDF report |
| `test_scadenziario.py` | Scadenze, calcolo termini |
| `test_search_index.py` | Ricerca full-text SQLite FTS5 |
| `test_simulazione_deposito.py` | Simulazione deposito telematico (39 test, vedi sopra) |
| `test_strumenti_legali.py` | Strumenti legali |
| `test_sync.py` | Sincronizzazione dati real-time |
| `test_tariffario.py` | Tariffario professionale |
| `test_template_atti_editor.py` | Editor template atti |
| `test_workflow_onboarding.py` | Workflow onboarding clienti |

**Esegui tutti i test del progetto:**
```bash
python -m pytest tests/ -v
```

**Esegui un singolo modulo:**
```bash
python -m pytest tests/test_fascicoli.py -v
```

---

## Conformità Portale Servizi Telematici — Stato attuale

**Versione 2.79.1 — Conformità: ~98%** (idonea per produzione)

### Conforme ✅
| Componente | Norma | Dettaglio |
|-----------|-------|-----------|
| `DatiAtto.xml` struttura | D.M. 44/2011 Allegato 2 | Namespace, tag `Attoprincipale` (corretto), hash SHA-256, IdBusta, DataDeposito ISO8601 |
| Busta `.enc` (ZIP) | D.M. 44/2011 art. 14 | ZIP contenente DatiAtto.xml + atti firmati; il `.enc` è il formato "busta" (envelope), non richiede cifratura separata — il canale PEC garantisce integrità |
| Oggetto PEC | D.M. 44/2011 art. 14 c.3 | `"DEPOSITO TELEMATICO - {TipoAtto} - RG {n}/{anno}"` — riconosciuto automaticamente dal sistema PST |
| Firma CAdES-BES | D.M. 44/2011 art. 12 | PKCS#7, hash SHA-256, detached, estensione `.p7m`, chain certificati inclusa |
| Verifica scadenza certificato | D.M. 44/2011 art. 12 | Pre-deposito: blocca se certificato scaduto, avviso a 30 giorni |
| PDP REST API | D.Lgs. 150/2022 + D.M. 217/2023 | Endpoint `/depositi`, multipart/form-data, mTLS (P12/PEM), risposta JSON |
| PAT SOAP SIGA | D.P.C.M. 16/02/2016 + D.P.C.S.G.A. 28/07/2021 | WSDL `depositoAtto`, atto in base64, autenticazione mTLS |
| Stato machine PCT | D.M. 44/2011 flusso 4 fasi | 7 stati, serializzazione JSON, `from_dict` per ripristino |
| Ricevute PEC (IMAP) | D.M. 44/2011 art. 15 | Polling accettazione + consegna, timeout 5 min |

### Parziale / Note ⚠️
| Aspetto | Nota |
|---------|------|
| **RFC 3161 Timestamp CAdES** | Opzionale per civile, consigliato per penale. Non implementato: il timestamp viene garantito dalla ricevuta PEC (valore legale equivalente per D.M. 44/2011). |
| **Validazione PDF/A** | Il sistema non verifica che i PDF da firmare siano PDF/A-1b (requisito per deposito). Responsabilità dell'avvocato caricare PDF/A corretti. |
| **IndiceDeposito.xml** | Non incluso nella busta. Il `DatiAtto.xml` funge da indice per D.M. 44/2011 base. Alcune corti possono richiedere file indice separato (variante regionale). |

### Regole invarianti da rispettare ad ogni modifica
1. **Mai cambiare il tag** `<Attoprincipale>` in `busta.py` — il vecchio `<AttoprincipAle>` era errato
2. **Oggetto PEC** deve sempre iniziare con `"DEPOSITO TELEMATICO"` (riconosciuto dal parser PST)
3. **Verifica scadenza certificato** deve essere chiamata prima di qualsiasi firma in `DepositoCivile.deposita()`
4. **Risposta `deposita_atto`** deve sempre contenere: `codiceEsito`, `idDeposito`, `dataDeposito`, `stato`, `ricevutaAccettazione`, `esitoControlli`, `esitoCancelleria` — sia per PDP che per PAT

## Local Signer — Eseguibili per utenti finali

**L'utente non sa installare Python o eseguire script.** Gli eseguibili vanno sempre rigenerati quando `tools/local_signer.py` o `tools/requirements_local_signer.txt` cambiano.

### File distribuiti in `tools/dist/`

| File | Piattaforma | Come l'utente lo esegue |
|------|-------------|------------------------|
| `SetupLocalSigner-<ver>.cmd` | **Windows** | Doppio clic (CMD auto-estraente offline, non richiede internet) |
| `InstallaLocalSigner-<ver>.command` | **macOS** | Doppio clic in Finder (richiede internet per scaricare dipendenze) |
| `InstallaLocalSigner-<ver>.run` | **Linux** | `bash InstallaLocalSigner-<ver>.run` in terminale (richiede internet) |

### Come rigenerare gli eseguibili

```bash
cd /opt/iusentra/repo
python3 tools/build_dist.py
```

Con URL personalizzato (es. istanza Railway diversa da quella di default):
```bash
python3 tools/build_dist.py --base-url https://mio-server.example.com
```

Solo macOS + Linux (salta Windows, più veloce):
```bash
python3 tools/build_dist.py --no-windows
```

### Regola obbligatoria — quando rigenerare

**Rigenerare SEMPRE** `tools/dist/` nei seguenti casi:
1. Modifica a `tools/local_signer.py` (qualsiasi patch)
2. Modifica a `tools/requirements_local_signer.txt`
3. Modifica a `tools/installa_local_signer_locale.ps1`
4. Bump di versione del Local Signer (`VERSION` in `local_signer.py`)

Dopo la rigenerazione, committare tutti i file in `tools/dist/` insieme alla modifica sorgente.

### Istruzioni da dare all'utente (copia-incolla)

**Windows:**
> Scarica `SetupLocalSigner-X.Y.Z.cmd`, fai doppio clic. L'installazione è automatica e non richiede internet. Se Windows SmartScreen mostra un avviso, clicca "Ulteriori informazioni" → "Esegui comunque".

**Mac:**
> Scarica `InstallaLocalSigner-X.Y.Z.command`, aprilo con doppio clic dal Finder. Se macOS blocca il file, vai in **Preferenze di Sistema → Privacy e Sicurezza** e clicca "Apri comunque".

**Linux:**
> Scarica `InstallaLocalSigner-X.Y.Z.run`, apri un terminale nella stessa cartella ed esegui: `bash InstallaLocalSigner-X.Y.Z.run`

Dopo l'installazione su tutte le piattaforme: tornare su IUSENTRA → Impostazioni → Firma digitale e cliccare **"Riverifica"**.

## Convenzioni

- Messaggi di commit in italiano, descrittivi
- Nessuna dipendenza esterna aggiunta senza necessità
- Mantenere coerenza visiva con Bootstrap 5 e le classi già usate nel progetto

## Modularizzazione governabile — REGOLA OBBLIGATORIA

- Ogni nuova funzionalità o refactor deve produrre **codice governabile**, quindi moduli piccoli, leggibili e con responsabilità chiare.
- **Non è ammesso** spostare logica da un monolite a un nuovo file grande equivalente: se un modulo cresce, va ulteriormente suddiviso in componenti gestibili.
- La separazione va mantenuta per livelli:
  - `web/bootstrap/` → wiring Flask, registrazioni, hook, bootstrap
  - `web/services/` → logica applicativa trasversale e servizi UI/runtime
  - `pct/` → dominio e logica di business legale/PCT
- Prima di aggiungere nuovo codice in `web/app.py`, verificare sempre se può vivere in un modulo dedicato.

## UI italiana e date — REGOLA OBBLIGATORIA

- Tutto il testo visibile in UI deve essere in **lingua italiana**. Evitare etichette miste come `Dashboard`, `Logout`, `Sync`, `Runtime: missing` quando sono esposte all'utente finale.
- Tutte le date/ore **esposte in UI** devono usare formati italiani tramite i filtri template condivisi (`fmt_data`, `fmt_dataora`, `fmt_data_estesa`, ecc.), non `strftime('%B')` o `strftime('%A')` direttamente nei template.
- Eccezione consentita: i valori tecnici per campi HTML `type=\"date\"`, `datetime-local`, attributi `data-*`, API o payload macchina possono restare in formato ISO.

## Versioning — REGOLA OBBLIGATORIA

**Ad ogni implementazione (nuova funzionalità, bug fix, qualsiasi modifica al codice) eseguire SEMPRE il bump di versione e aggiornare tutti e quattro i file:**

| File | Campo | Esempio |
|---|---|---|
| `pct/__init__.py` | `__version__ = "X.Y.Z"` | unica fonte di verità |
| `setup.py` | `version="X.Y.Z"` | package Python |
| `Dockerfile` | `LABEL … version="X.Y.Z"` | immagine Docker |
| `railway.toml` | `#  version: X.Y.Z` | trigger redeploy Railway |

**La versione web è automaticamente sincronizzata** — `web/app.py` importa `pct.__version__` come `APP_VERSION` (riga 102) e la espone nel template `base.html` tramite `{{ app_version }}`. Non esiste una versione web separata.

**Schema SemVer:**
- `MAJOR.MINOR.PATCH`
- Patch (+0.0.1): bug fix, correzioni dati, aggiornamenti documentazione
- Minor (+0.1.0): nuova funzionalità retrocompatibile
- Major (+1.0.0): breaking change

**Deploy — Docker locale (REGOLA OBBLIGATORIA):**
- Dopo ogni bump di versione, ricostruire e riavviare il Docker locale con:
  ```bash
  cd /opt/iusentra/repo
  docker compose build --no-cache
  docker compose up -d
  ```
- Eseguire **sempre** `--no-cache` per garantire che la nuova versione del codice sia inclusa nell'immagine (il layer del codice si aggiorna solo con rebuild).
- Verificare che il container sia tornato healthy prima di considerare il deploy completato:
  ```bash
  docker compose ps          # Status deve essere "healthy"
  docker compose logs --tail=20 app   # Controllare errori di avvio
  ```
- URL locale: `http://localhost` (via Nginx) oppure `http://localhost:8080` (diretto Gunicorn).

**Deploy — Railway (produzione online):**
- Il deploy su Railway avviene dopo il bump di versione e il push sul branch.
- Ad ogni release va aggiornata anche la versione sul pannello Railway (variabile d'ambiente o redeploy dell'immagine).
- Versione corrente in produzione: **2.79.1**

## Note tecniche

- **`web/app.py` — variabile `oggi` nei `render_template`**: passare **sempre** `oggi=date.today()` (oggetto `date`), **mai** `oggi=date.today().isoformat()` (stringa). `base.html` riga 350 chiama `oggi.strftime('%d/%m/%Y')` che è un metodo di `date`/`datetime`, non di `str` → se si passa la stringa si ottiene `AttributeError: 'str' object has no attribute 'strftime'`. I campi `min="{{ oggi }}"` degli input HTML `type="date"` ricevono comunque il formato corretto perché `str(date.today())` restituisce `YYYY-MM-DD`.

- **`web/app.py` — `SECRET_KEY`**: quando si imposta `app.secret_key`, impostare sempre anche `app.config["SECRET_KEY"] = app.secret_key`. La funzione `get_condivisioni()` usa `app.config["SECRET_KEY"]` e senza questa riga solleva `KeyError` causando un 500.

- **`web/app.py` — Route API senza try/except → 500 generico**: le route `/api/uffici`, `/api/uffici/stato`, `/api/uffici/aggiorna` **non hanno l'handler di errore HTTP** del Flask (a differenza di `/polisWeb`, `/polisWeb/ricerca`, `/polisWeb/documenti` che usano già try/except). Se lanciano un'eccezione non catturata, Flask risponde con "500 — Errore interno". Regola:
  - **Ogni route `/api/*` deve avere `try/except Exception`** e restituire JSON con HTTP 200 (o 4xx) — mai lasciare propagare l'eccezione al gestore Flask 500.
  - Esempio pattern corretto:
    ```python
    try:
        ...logica...
        return jsonify(risultato)
    except Exception as e:
        app.logger.exception("Errore nome_route: %s", e)
        return jsonify({"errore": str(e)}), 200  # o jsonify([]) per liste
    ```
  - Il 500 si manifesta tipicamente **dopo aggiornamenti al bundle uffici** (`pct/uffici_giudiziari.py`): `polisWeb.html` chiama `/api/uffici/stato` al caricamento e `/api/uffici?q=...` durante l'autocomplete — se il bundle lancia un'eccezione in quelle route, il template carica correttamente ma il badge e l'autocomplete generano 500.

- **`polisWeb` — ricerca uffici giudiziari**:
  - Il form (`polisWeb.html`) invia il **codice** ufficio nel campo hidden `name="tribunale"` (es. `0580010`), **non il nome**.
  - La route `polisWeb_ricerca` riceve il codice e deve risolvere il nome con:
    ```python
    _uff = next((u for u in get_gestore(cache_path).carica() if u.get("codice") == tribunale), None)
    tribunale_sel_nome = _uff["nome"] if _uff else tribunale
    ```
  - **NON usare** `cerca_ufficio_giudiziario(tribunale, ...)` per risolvere il nome: quella funzione cerca per testo nel nome, non per codice → restituisce `None` quando riceve un codice numerico.
  - `ricerca_fascicoli(tribunale=codice)` accetta sia codice che nome (il client reale usa `_risolvi_codice_ufficio` che riconosce `str.isdigit()`).
  - Il demo client (`_ClientPolisWebDemo`) usa `_nome_ufficio_demo(codice)` per risolvere il nome leggibile dal codice tramite `get_gestore().carica()`.

- **Uffici giudiziari — regole di consistenza del bundle** (`pct/uffici_giudiziari.py`):

  **Formato nomi** (helper `_t`, `_ca`, `_pr`, ecc.):
  - Tribunale → `"Tribunale di {città}"`
  - Corte d'Appello → `"Corte d'Appello di {città}"` (distretto == città)
  - Procura → `"Procura della Repubblica di {città}"` (generate auto da `_genera_procure`)
  - Procura Generale → `"Procura Generale di {città}"` (distretto == città)
  - Trib. Minorenni → `"Tribunale per i Minorenni di {città}"`
  - Trib. Sorveglianza → `"Tribunale di Sorveglianza di {città}"`
  - Corte d'Assise → `"Corte d'Assise di {città}"`
  - Giudice di Pace → `"Ufficio del Giudice di Pace di {città}"`
  - TAR → `"TAR {nome-regione-o-sezione}"`

  **Regole invarianti** (controllare dopo ogni modifica al bundle):
  1. **Slug PEC tutto minuscolo**: `tribunale.milano@giustiziapec.it` ✓ — `tribunale.reggioEmilia@…` ✗
  2. **Corte d'Appello**: `distretto` deve coincidere con la città nel nome
  3. **Procura Generale**: `distretto` deve coincidere con la città nel nome
  4. **Nessun codice duplicato** tra tutti gli uffici del bundle completo
  5. **Nessun nome duplicato** tra tutti gli uffici del bundle completo
  6. **Uffici geograficamente corretti**: es. Crotone → distretto Catanzaro, non Lecce
  7. **Codici standard**: 7 cifre per uffici ordinari, prefisso `T` per TAR, `CDS` per Consiglio di Stato

  **Script di verifica** (eseguire dopo modifiche al bundle):
  ```bash
  python3 - <<'EOF'
  import sys; sys.path.insert(0, '.')
  from pct.uffici_giudiziari import _build_bundle_completo, TIPI_UFFICIO
  from collections import Counter
  import re
  bundle = _build_bundle_completo()
  problemi = []
  dup_cod = {k for k,v in Counter(u['codice'] for u in bundle).items() if v>1}
  [problemi.append(f"CODICE-DUP {c}") for c in dup_cod]
  dup_nomi = {k for k,v in Counter(u['nome'] for u in bundle).items() if v>1}
  [problemi.append(f"NOME-DUP '{n}'") for n in dup_nomi]
  for u in bundle:
      slug = u.get('pec','').split('@')[0]
      if any(c.isupper() for c in slug):
          problemi.append(f"PEC-MAIUSC {u['codice']} {u['nome']} → {u['pec']}")
      if not u.get('distretto','').strip():
          problemi.append(f"DISTRETTO-VUOTO {u['codice']} {u['nome']}")
      if u['tipo'] == 'CORTE_APPELLO':
          citta = u['nome'].replace("Corte d'Appello di ","")
          if citta.lower() != u['distretto'].lower():
              problemi.append(f"CA-DISTRETTO {u['codice']} nome={u['nome']} dist={u['distretto']}")
      if u['tipo'] == 'PROCURA_GENERALE':
          citta = u['nome'].replace("Procura Generale di ","")
          if citta.lower() != u['distretto'].lower():
              problemi.append(f"PG-DISTRETTO {u['codice']} nome={u['nome']} dist={u['distretto']}")
  print(f"Uffici: {len(bundle)}  Problemi: {len(problemi)}")
  [print(f"  {p}") for p in problemi]
  EOF
  ```

  **Badge autocomplete** (`polisWeb.html`, funzione JS `seleziona(u)`):
  - Il badge mostra `u.nome` direttamente — **NON** aggiungere il prefisso `${label}: ` perché il tipo è già incluso in `u.nome` (es. "Tribunale di Milano").
  - Il distretto `(${u.distretto})` può apparire in parentesi per indicare il distretto di appartenenza (es. "Tribunale di Reggio Calabria (Catanzaro)" è **corretto**: Reggio Calabria appartiene al distretto Catanzaro).

  **Valore inviato dai form** (differenze per sezione app):
  - `polisWeb.html`: campo hidden invia `u.codice` (es. `0580010`)
  - `fascicoli/form.html`, `form_appuntamento.html`, `clienti/form.html`: `<select>` invia `u.nome` (es. `"Tribunale di Milano"`)

  **Verifica visiva dopo ogni modifica al bundle** — pannello admin in `polisWeb.html`:
  - Il badge "N uffici · aggiornati" (verde) è visibile solo agli admin.
  - Cliccandolo si apre il pannello con il **breakdown per tipo** (Tribunali, Procure, G.d.P., ecc.).
  - Dopo ogni modifica al bundle, cliccare **"Ricarica bundle"** per rigenerare la cache dal codice aggiornato (senza attendere TTL né fonti remote).
  - Valori attesi a bundle v1.0.2: 648 uffici totali — GDP: 155, TRIBUNALE: 146, PROCURA: 147, CORTE_APPELLO: 23, PROCURA_GENERALE: 23, SORVEGLIANZA: 26, TM: 26, TAR: 31, CORTE_ASSISE: 69.
  - Se i numeri non corrispondono dopo "Ricarica bundle", il deploy non ha incluso le modifiche a `pct/uffici_giudiziari.py`.

  **Auto-upgrade automatico** (`GestoreUfficiGiudiziari.carica()`):
  - Se la cache su disco ha **meno uffici del bundle interno**, `carica()` rigenera automaticamente la cache dal bundle al primo accesso dopo il redeploy.
  - Questo risolve il caso in cui Railway (o qualsiasi server) abbia una cache salvata da sorgente remota (PST/URL esterno) con meno uffici di quanti ne ha il bundle aggiornato.
  - Il log mostra: `Auto-upgrade cache uffici: N (cache) < M (bundle) → rigenero`
  - **Non modificare questa logica**: è la salvaguardia principale contro dati incompleti su produzione.

- **Mobile — Modal visualizzatore documenti** (`fascicoli/dettaglio.html`, `#modalVisualizzatore`):
  - Il modal deve avere **sempre** `modal-fullscreen-sm-down` per occupare tutto lo schermo su mobile.
  - Il `modal-content` deve avere `display:flex;flex-direction:column` affinché il body con l'iframe possa espandersi con `flex:1`.
  - Struttura corretta:
    ```html
    <div class="modal-dialog modal-xl modal-fullscreen-sm-down" style="max-width:95vw;height:92vh;margin:.5rem auto">
      <div class="modal-content" style="height:100%;display:flex;flex-direction:column">
        <div class="modal-header py-2">…</div>
        <div class="modal-body p-0" style="flex:1 1 auto;overflow:hidden;display:flex;flex-direction:column">
          <iframe … style="width:100%;flex:1;border:0;min-height:0"></iframe>
        </div>
      </div>
    </div>
    ```
  - **Senza `display:flex` sul `modal-content`**: il `flex:1` sul modal-body non funziona → l'iframe collassa a altezza 0 → maschera apparentemente vuota/troppo piccola.

- **Mobile — Modal Bootstrap: z-index backdrop e posizionamento**:
  - I modal devono essere **figli diretti del `<body>`**, non annidati dentro `#main` o altri container con `position:relative/absolute` → altrimenti il backdrop Bootstrap non copre correttamente tutta la pagina e il modal può apparire parzialmente nascosto o in posizione errata.
  - Regola: tutti i `<div class="modal fade" …>` vanno inseriti **in fondo al file HTML, fuori da qualsiasi wrapper**.

- **Mobile — footer navbar fisso e scroll**:
  - Il footer di navigazione mobile (`base.html`) usa `position:fixed;bottom:0` con `z-index:1030`.
  - Il contenuto principale `#main` deve avere `padding-bottom` sufficiente (≥ 70px) per non essere coperto dal footer.
  - Su iOS Safari il `100vh` include la barra URL → usare `min-height: -webkit-fill-available` come fallback per i modal fullscreen.

- **Mobile — Dropdown tagliati da `overflow:hidden` su `#main`**:
  - Su mobile `#main` è `position:fixed` con `overflow-y:auto; overflow-x:hidden` (vedi `app.css` riga ~614). Qualsiasi `position:absolute` dentro `#main` — inclusi i Bootstrap dropdown-menu — viene **clippato** ai bordi del container e risulta invisibile o troncato.
  - **Sintomo**: cliccando un dropdown (es. "Esporta") appare un rettangolo bianco vuoto invece dei voci del menu.
  - **Fix obbligatorio**: inizializzare i dropdown via JavaScript con `popperConfig: { strategy: 'fixed' }` — Popper usa `position:fixed` e aggira il clipping. Il fix globale è già in `base.html` (script alla fine del `<body>`):
    ```javascript
    new bootstrap.Dropdown(el, { popperConfig: { strategy: 'fixed' } });
    ```
  - **Regola**: ogni volta che si aggiunge un nuovo dropdown dentro `#main`, verificare che venga inizializzato dallo script globale (`[data-bs-toggle="dropdown"]` auto-rilevato). Non serve azione manuale se l'attributo standard è presente.
  - **Non usare** `data-bs-display="static"` come workaround: disabilita il posizionamento dinamico di Popper e il menu appare sempre in posizione fissa rispetto al pulsante, ignorando i bordi del viewport.

- **Mobile — pulsanti azione documento** (`fascicoli/dettaglio.html`, sezione atti):
  - I pulsanti (Visualizza, Scarica, Firma, Elimina) nelle card documento su mobile erano non cliccabili a causa di un overlay trasparente generato da un elemento parent con `pointer-events` errato.
  - Verificare sempre che i bottoni nelle card abbiano `position:relative;z-index` superiore a eventuali pseudo-elementi `::after` del container.
  - I titoli delle sezioni (es. "Atti") non devono sovrapporsi ai pulsanti: usare `d-flex align-items-center justify-content-between` per header sezione + pulsante "Aggiungi".

## Infrastruttura Docker

**Build multi-stage `Dockerfile`:**
1. **Stage 1 — builder**: compila pacchetti Python con gcc (incluso psycopg2, cryptography, lxml)
2. **Stage 2 — sass-builder**: compila SCSS → CSS con dart-sass v1.83.0
3. **Stage 3 — runtime**: immagine minimale `python:3.12-slim` con:
   - `tesseract-ocr` + lingua italiana (OCR)
   - `poppler-utils`, `ghostscript` (elaborazione PDF)
   - `libpcsclite1`, `opensc` (smart card PKCS#11)
   - Gunicorn con worker gevent per SSE/long-polling

**Variabili d'ambiente chiave (`.env.example`):**
```
PCT_SECRET_KEY          # Chiave sessione Flask
PCT_DOC_KEY             # Chiave AES-256-GCM per documenti (opzionale)
PCT_DATA_DIR            # Root directory dati JSON (/data)
PCT_MULTITENANT         # Abilita multi-tenant SaaS
SMTP_HOST/PORT/USER/PASS # Email uscita
PEC_HOST/PORT/USER/PASS  # PEC studio
TWILIO_*                # WhatsApp/SMS via Twilio
STRIPE_SECRET_KEY        # Pagamenti Stripe
OLLAMA_URL               # AI locale (opzionale)
STUDIO_NOME / STUDIO_CF / STUDIO_PIVA  # Dati studio
```

## Gruppi di route web/app.py

| Prefisso | Funzionalità |
|----------|-------------|
| `/fascicoli` | CRUD fascicoli, documenti, deposito PCT, wizard atti |
| `/clienti` | Anagrafica clienti, cartelle, portale self-service |
| `/agenda` | Calendario appuntamenti, import/export iCal |
| `/scadenziario` | Scadenze, calcolo termini legali |
| `/messaggi` | Messaggistica multi-canale |
| `/fatturazione` | Parcelle, fatture, export PDF |
| `/preventivi` | Preventivi, wizard tariffe |
| `/pagamenti` | Checkout Stripe/SumUp |
| `/polisWeb` | Portale civile PST — ricerca fascicoli + documenti |
| `/pdp` | Portale penale PDP — depositi |
| `/pat` | Portale amministrativo PAT/TAR |
| `/sigit` | Verifica firma digitale SIGIT |
| `/backup` | Backup e ripristino dati |
| `/impostazioni` | Configurazione studio, calendario sync |
| `/api/` | Endpoint JSON (statistiche, ricerca, sync, OCR) |
| `/admin/` | Pannello admin multi-tenant |
| `/auth/` | Login, logout, 2FA, profilo, utenti |
| `/privacy/` | Registro trattamenti GDPR |
| `/cal/<token>/` | Feed iCal pubblici condivisibili |
| `/sw.js` | Service Worker PWA |

## Multi-tenant

- Attivato con `PCT_MULTITENANT=true` in `.env`
- Ogni studio ha i propri file JSON isolati in `PCT_DATA_DIR/<studio_id>/`
- Registro studi in `tenant.py` (`GestioneTenant`)
- Pannello admin: `/admin/studi_lista`, `/admin/studio_nuovo`, `/admin/studio_dettaglio`
- `TenantAccessor` garantisce che ogni richiesta acceda solo ai dati del proprio studio

## Sicurezza

- **AES-256-GCM**: documenti cifrati su disco se `PCT_DOC_KEY` è impostata
- **CAdES/PAdES**: firma digitale PKCS#7 + smart card PKCS#11
- **2FA/TOTP**: Google Authenticator compatibile (`auth.py`)
- **Audit log**: ogni azione su dati sensibili registrata in `EventoAudit`
- **GDPR**: registro trattamenti dati in `privacy.py`, informative PDF per clienti
- **Session cookie**: `SECRET_KEY` + `SESSION_COOKIE_SECURE=True` in produzione
- **mTLS**: connessioni PDP/PAT autenticate con certificato client (P12/PEM)
