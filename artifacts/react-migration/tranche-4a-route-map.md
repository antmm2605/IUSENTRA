# Tranche 4A - mappa route legacy

Generato: 2026-05-06

Nota operativa: il comando richiesto con `rg` ha restituito `rg.exe: Accesso negato` su questa workstation; l'analisi e' stata completata con `Select-String` PowerShell sui percorsi `web`, `pct` e `tests`, piu' ispezione diretta di `app.url_map`.

## /backup

- Handler legacy: [web/bootstrap/backup_routes.py](../../web/bootstrap/backup_routes.py)
- Funzione GET: `lista_backup`
- Template: `web/templates/backup/lista.html`
- Repository/manager: `pct.backup.GestioneBackup` tramite `get_backup()`
- Permessi: gate API React richiede `backup.leggi`; il POST legacy conserva la policy esistente.
- Form presenti:
  - `POST /backup/esegui`
  - `POST /backup/<id_bk>/verifica`
  - `POST /backup/<id_bk>/elimina`
  - `GET/POST /backup/<id_bk>/ripristina`
- Token CSRF: i template legacy usano form standard; React invia form HTML tramite `LegacyPostForm` e lascia il valore al runtime condiviso se presente nella meta.
- Download/export: `GET /backup/<id_bk>/scarica`
- Azioni distruttive: elimina backup e ripristina backup restano legacy.
- Dati sensibili: il record legacy contiene percorso file server-side; il bridge React espone solo nome file, dimensione, stato, data e link legacy.
- Decisione: sbloccabile come GET React full per `/backup`; ogni subpath `/backup/*`, download, verifica, elimina e ripristina resta legacy.

## /sito-studio

- Handler legacy: [web/blueprints/studio_site.py](../../web/blueprints/studio_site.py)
- Funzione GET: `dashboard`
- Template: `web/templates/studio_site/dashboard.html`
- Repository/manager: `web.services.studio_site_runtime.build_studio_site_dashboard_payload`, `StudioSiteRepository`
- Permessi: `site_admin_identity_or_403`, permesso `admin.configura`
- Form presenti nel dashboard:
  - eliminazione pagine/articoli/servizi/professionisti/sedi/regole agenda via POST legacy
  - link a builder, impostazioni sito, redazione AI, anteprima e prenotazioni
- Token CSRF: form legacy standard dove previsto dai template.
- Download/export: non emersi nella dashboard.
- Azioni distruttive: eliminazioni contenuti e pubblicazione restano legacy o builder legacy.
- Dati sensibili: la dashboard mostra contenuti pubblici, stato sito, contatti e prenotazioni; il bridge seleziona solo campi pubblici o gia' visibili e non serializza configurazioni riservate.
- Decisione: sbloccabile come dashboard React full per GET `/sito-studio`, con scritture e builder lasciati ai percorsi legacy.

## /sito-studio/contatti

- Handler legacy: [web/blueprints/studio_site.py](../../web/blueprints/studio_site.py)
- Funzione GET: `contact_submissions`
- Template: `web/templates/studio_site/contact_submissions.html`
- Repository/manager: `StudioSiteRepository.list_contact_submissions`, payload dashboard Sito Studio
- Permessi: `site_admin_identity_or_403`, permesso `admin.configura`
- Form presenti:
  - `POST /sito-studio/contatti/<submission_id>/crea-cliente`
- Token CSRF: form legacy standard; React usa `LegacyPostForm` e non intercetta il submit.
- Download/export: non presenti.
- Azioni distruttive: nessuna distruzione diretta; conversione contatto in cliente potenziale resta POST legacy auditato.
- Dati sensibili: richieste contatto e recapiti reali, gia' visibili nel template legacy; accesso riservato ad admin configurazione.
- Decisione: sbloccabile come React full per GET `/sito-studio/contatti`; gestione lead resta legacy.

## /sito-studio/builder

- Handler legacy: [web/blueprints/studio_site_builder.py](../../web/blueprints/studio_site_builder.py)
- Funzione GET: `builder`
- Template: `web/templates/studio_site/builder.html`
- Repository/manager: `build_builder_payload`, `save_design_settings`, `publish_page_blocks`, `restore_design_revision`, asset runtime
- Permessi: `site_admin_identity_or_403`, permesso `admin.configura`
- Form/azioni presenti:
  - `POST /sito-studio/builder/applica-template`
  - `POST /sito-studio/builder/salva-design`
  - `POST /sito-studio/builder/genera-automaticamente`
  - `POST /sito-studio/builder/valida`
  - `POST /sito-studio/api/pages/<page_id>/blocks`
  - `POST /sito-studio/api/pages/<page_id>/publish`
  - `POST /sito-studio/api/revisions/<revision_id>/restore`
  - upload asset e delete asset
- Token CSRF: form legacy/API builder esistenti.
- Download/export: anteprima e asset; nessun nuovo download React.
- Azioni distruttive: restore revisione e delete asset.
- Dati sensibili: impostazioni editor, asset e pubblicazione tecnica.
- Decisione: deve restare legacy in 4A.

## /studio

- Handler legacy: [web/blueprints/terminology_aliases.py](../../web/blueprints/terminology_aliases.py)
- Funzione GET: `studio`
- Template: nessuno diretto; redirect a `telematico_dashboard`
- Repository/manager: superficie operativa telematica gia' esistente
- Permessi: ereditati dal target legacy
- Form/POST/download: non diretti sull'alias; il target contiene flussi operativi non oggetto della tranche.
- Dati sensibili: puo' aprire aree operative studio/telematico.
- Decisione: resta legacy; non si migra in questa PR.

## /impostazioni

- Handler legacy: [web/blueprints/impostazioni.py](../../web/blueprints/impostazioni.py)
- Funzione GET/POST: `index`
- Template: `web/templates/impostazioni/index.html`
- Repository/manager: `pct.config_studio.GestioneConfigStudio`, runtime locale AI, PEC/SMTP/firma/scheduler
- Permessi: login richiesto; sezioni sensibili gestite dai template legacy
- Form presenti:
  - `POST /impostazioni` per tab studio, PEC, firma, SMTP, WhatsApp, scheduler, AI
  - `POST /impostazioni/test/pec-smtp`
  - `POST /impostazioni/test/pec-imap`
  - `POST /impostazioni/test/smtp`
  - `POST /impostazioni/test/smtp-imap`
  - `POST /impostazioni/test/whatsapp`
  - `POST /impostazioni/pec/local-smtp-payload`
- Token CSRF: form standard legacy.
- Download/export: setup Local Signer per Windows/macOS/Linux e guide firma.
- Azioni distruttive: aggiornamento configurazioni e test canali sensibili.
- Dati sensibili: PEC, SMTP, firma digitale, WhatsApp, AI locale e Local Signer.
- Decisione: resta legacy, incluso `?tab=firma`.
