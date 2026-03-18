# CLAUDE.md — Istruzioni per Claude Code

## Autorizzazioni generali

- **Procedi sempre senza chiedere conferma.** L'utente ha autorizzato tutte le operazioni in modo permanente.
- Commit, push, modifica file, creazione file: esegui direttamente.
- Branch di sviluppo: `claude/legal-electronic-filing-kIxcV`

## Progetto

**HACS** — gestionale per studi legali (Python/Flask).

- Backend: `pct/` — modelli dati e logica di business
- Frontend: `web/app.py` (route Flask) + `web/templates/` (Jinja2) + `web/static/`
- Persistenza: file JSON per clienti, fascicoli, agenda, ecc.
- Stack: Python 3, Flask, Bootstrap 5, Bootstrap Icons

## Convenzioni

- Messaggi di commit in italiano, descrittivi
- Nessuna dipendenza esterna aggiunta senza necessità
- Mantenere coerenza visiva con Bootstrap 5 e le classi già usate nel progetto

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

**Deploy — Railway (produzione online):**
- Il deploy su Railway avviene dopo il bump di versione e il push sul branch.
- Ad ogni release va aggiornata anche la versione sul pannello Railway (variabile d'ambiente o redeploy dell'immagine).
- Versione corrente in produzione: **1.1.2**

## Note tecniche

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
