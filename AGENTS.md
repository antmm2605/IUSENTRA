# AGENTS.md — Istruzioni per Codex

## Autorizzazioni generali

- **Procedi sempre senza chiedere conferma.** L'utente ha autorizzato tutte le operazioni in modo permanente.
- Commit, push, modifica file, creazione file: esegui direttamente.
- Branch di sviluppo: `Codex/legal-electronic-filing-kIxcV`
- **Branch remoto da sincronizzare sempre insieme al branch di sviluppo:** `claude/legal-electronic-filing-kIxcV`

## Igiene repository — Regola obbligatoria

- Sulla macchina locale deve esistere **una sola copia attiva del progetto**: `D:\legale\hacs`.
- **Worktree, cartelle duplicate, cloni temporanei e versioni parallele** del repository devono essere rimossi a fine lavoro.
- I **soli branch ammessi**, sia locali sia remoti, sono:
  - `Codex/legal-electronic-filing-kIxcV`
  - `claude/legal-electronic-filing-kIxcV`
- Non creare branch aggiuntivi per task temporanei. Tutto il lavoro deve confluire nel branch di sviluppo corrente e venire sincronizzato anche sul branch gemello.
- A fine implementazione verificare sempre che:
  - `git worktree list` mostri solo `D:\legale\hacs`
  - `git branch --all` mostri solo i due branch ammessi più `origin/HEAD`
  - i due branch locali e i due branch remoti puntino allo **stesso commit**
- Per enforcement e cleanup usare lo script: `scripts/repo_hygiene.ps1`

## Progetto

**HACS** — gestionale per studi legali (Python/Flask).

- Backend: `pct/` — modelli dati e logica di business
- Frontend: `web/app.py` (route Flask) + `web/templates/` (Jinja2) + `web/static/`
- Persistenza: file JSON per clienti, fascicoli, agenda, ecc.
- Stack: Python 3, Flask, Bootstrap 5, Bootstrap Icons

## Modularizzazione governabile — Regola obbligatoria

- Ogni nuovo modulo o refactor deve produrre **codice governabile**, quindi con responsabilità piccole e confini chiari.
- È vietato spostare logica da `web/app.py` o da un monolite esistente dentro un nuovo file unico altrettanto grande.
- Quando una feature nuova ha più responsabilità, va divisa **subito** in più moduli gestibili, ad esempio:
  - `bootstrap/` per wiring Flask, registrazioni e setup
  - `services/` per orchestrazione applicativa
  - `pct/` per logica di dominio
- Ogni estrazione deve preferire moduli focalizzati e testabili, invece di helper generici pieni di funzioni eterogenee.
- Se un modulo cresce troppo o mescola routing, configurazione, template context e logica business, va ulteriormente spezzato prima di considerare il lavoro concluso.

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

### Altri test utili per il deposito

| File | Cosa testa |
|------|------------|
| `tests/test_busta.py` | Busta telematica: creazione, verifica, allegati, hash |
| `tests/test_pec.py` | Client PEC: invio, ricevute, validazione |
| `tests/test_fascicoli.py` | Modello fascicolo: EsitoDepositoPCT, stati, serializzazione |
| `tests/test_reginde.py` | ReGINde: ricerca uffici, PEC tribunali |

**Esegui tutti i test del progetto:**
```bash
python -m pytest tests/ -v
```

---

## Conformità Portale Servizi Telematici — Stato attuale

**Versione 2.5.2 — Conformità: ~98%** (idonea per produzione)

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

## SCSS e UI responsive — REGOLA OBBLIGATORIA

- I nuovi stili UI non vanno inseriti nei template con blocchi `<style>` o con accumulo di `style="..."`, salvo casi eccezionali strettamente tecnici.
- Ogni nuova regola grafica deve vivere in `web/static/scss/` ed essere organizzata in moduli **governabili**:
  - `components/` per pattern condivisi
  - `pages/` per le viste specifiche
  - `mobile.scss` solo per adattamenti trasversali mobile/tablet
- Gli entrypoint compilati restano quelli caricati dalla UI (`app.scss`, `design-system.scss`, `mobile.scss`, `editor-word.scss`, `portal.scss`): non creare file SCSS orfani non inclusi nel bundle.
- Dopo modifiche SCSS, verificare sempre la compilazione CSS nel flusso Docker locale obbligatorio della release.
- La UI deve essere progettata in modo **responsive** per desktop, tablet e mobile, con card compatte, gerarchia chiara e senza spazi morti.
- I feedback utente per azioni completate, errori, avvisi o stati intermedi devono usare messaggi professionali, chiari e in italiano.

## Versioning — REGOLA OBBLIGATORIA

**Ad ogni implementazione (nuova funzionalità, bug fix, qualsiasi modifica al codice) eseguire SEMPRE il bump di versione e aggiornare tutti e quattro i file:**

| File | Campo | Esempio |
|---|---|---|
| `pct/__init__.py` | `__version__ = "X.Y.Z"` | unica fonte di verità |
| `setup.py` | `version="X.Y.Z"` | package Python |
| `Dockerfile` | `LABEL … version="X.Y.Z"` | immagine Docker |
| `railway.toml` | `#  version: X.Y.Z` | trigger redeploy Railway |

**La versione web è automaticamente sincronizzata** — `web/app.py` importa `pct.__version__` come `APP_VERSION` (riga 102) e la espone nel template `base.html` tramite `{{ app_version }}`. Non esiste una versione web separata.

**Sincronizzazione obbligatoria locale / GitHub / Railway:**
- Dopo ogni modifica completata, la copia locale deve coincidere con il branch GitHub di lavoro e con la release destinata a Railway.
- Non lasciare mai commit solo in locale: eseguire sempre `git push` del branch di lavoro.
- Eseguire sempre anche il push dello stesso commit su `claude/legal-electronic-filing-kIxcV` oltre che su `Codex/legal-electronic-filing-kIxcV`.
- Se Railway è collegato a un branch remoto diverso dal branch locale corrente, riallineare anche quel branch remoto allo stesso commit della copia locale.
- Considerare il lavoro concluso solo quando risultano allineati:
  - file locali
  - branch GitHub di lavoro
  - branch remoto `claude/legal-electronic-filing-kIxcV`
  - branch remoto usato da Railway
  - `railway.toml` con la stessa versione del codice locale

**Local Signer — REGOLA OBBLIGATORIA:**
- Ad ogni release del `Local Signer`, generare sempre contestualmente i pacchetti versionati per **Windows, macOS e Linux** nella cartella `tools/dist`.
- I nomi file devono includere sempre la versione del signer (es. `SetupLocalSigner-1.5.5.exe`).
- I pacchetti finali distribuiti all'utente devono essere presentati come **eseguibili**, non come semplici script:
  - Windows → `.exe`
  - macOS → installer eseguibile `.command`
  - Linux → installer eseguibile `.run`
- Il punto ufficiale e permanente di distribuzione dei pacchetti è:
  `https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma`

**Schema SemVer:**
- `MAJOR.MINOR.PATCH`
- Patch (+0.0.1): bug fix, correzioni dati, aggiornamenti documentazione
- Minor (+0.1.0): nuova funzionalità retrocompatibile
- Major (+1.0.0): breaking change

**Deploy — Docker locale (REGOLA OBBLIGATORIA):**
- Dopo ogni bump di versione, ricostruire e riavviare il Docker locale con:
  ```bash
  cd /home/user/hacs
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
- Versione corrente in produzione: **1.1.2**

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
