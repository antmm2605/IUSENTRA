# Changelog

## 2.184.4 - 2026-04-25

- Reso lo Step 3 del wizard PST/PolisWeb resiliente agli errori di preview: timeout, SOAP Fault, Local Signer non raggiungibile e circuito aperto non bloccano piu' l'acquisizione ma attivano il fallback assistito con dati RG/ufficio/parti.
- Spostati i percorsi browser/Local Signer fuori dal circuit breaker server-side, cosi' una scelta operativa locale non viene trattata come errore ripetuto del portale.
- Aggiunti test anti-regressione per verificare che la preview PST via Local Signer non apra `portale:pst:preview` e che il template agganci il fallback assistito.

## 2.184.3 - 2026-04-25

- Integrata la nuova UI `/sigp-sync/` per consultare snapshot SIGP reali con layout dedicato a fascicolo, documenti, eventi, udienze, parti, comunicazioni e log.
- Collegata la UI al repository SIGP autorizzato gia' esistente, rimuovendo il flusso demo `Import test`/fixture previsto dallo scaffold esterno.
- Aggiunti test di route e snapshot per garantire che la pagina lavori su payload reali e non esponga endpoint demo.

## 2.184.2 - 2026-04-25

- Rimosso il fallback di lettura HTML della scheda SIGP/Giudice di Pace: IUSENTRA non effettua scraping di `sigp_infofascicolo.wp` e richiede dati ottenuti tramite PST/PdA/Model Office o Local Connector autorizzato.
- Aggiunta la sincronizzazione fascicolo telematico SIGP con mapper, repository SQLite/PostgreSQL, policy anti-scraping, endpoint `/sigp/sync/status` e `/sigp/sync/importa-payload`, senza fixture come sorgente dati.
- Persistiti snapshot completi del fascicolo SIGP: fascicolo, parti, eventi, udienze, documenti, provvedimenti e comunicazioni, con test anti-regressione su piu' di 8 documenti.

## 2.184.1 - 2026-04-25

- Arricchito il fallback SIGP/Giudice di Pace: quando il web service non espone righe, il Local Signer legge la scheda ufficiale autenticata `sigp_infofascicolo.wp` e popola in UI rito, materia, oggetto, giudice, stato, udienze, parti e difensori invece di mostrare una pratica vuota.
- Corretto il mapping del wizard PST per mantenere anche le controparti provenienti dalla scheda SIGP, con test anti-regressione sul fascicolo GDP `466/2023`.

## 2.184.0 - 2026-04-24

- Corretto il canale PST SIGP/Giudice di Pace: le ricerche esatte usano il registro `GDP`, il parametro `subpro` minuscolo richiesto dal proxy e un fallback operativo verso la scheda ufficiale autenticata quando il web service non espone righe.
- Allineata la matrice test portali per impedire regressioni su `JPW_SIGP`, `SUBPRO` e resolver uffici Giudice di Pace.
- Introdotto il modulo separato `Integrazione SIGP - Giudice di Pace` con registry XSD 2024-08-27, loader, validatore, builder XML, controlli di predeposito, API Flask e pagina UI dedicata.
- Aggiunti schemi SQL SQLite/PostgreSQL per versioni XSD, uffici, depositi, allegati e validazioni SIGP, mantenendo il primo rilascio su generazione XML e validazione senza invio ministeriale.

## 2.183.3 - 2026-04-24

- Corretta la regressione dell'installer Local Signer 1.6.10: i pacchetti Windows/macOS/Linux e i download online includono ora il modulo interno `local_signer_mod`, evitando il crash `ModuleNotFoundError` all'avvio su `127.0.0.1:27272`.
- Riallineato il payload QBuilder PST live: la ricerca per RG usa i parametri `anno`/`numero`, non invia piu' `subProc` vuoto sui registri che lo respingono, e mantiene `subProc` solo quando esiste un sotto-procedimento reale.
- Aggiunta una matrice di regressione sui canali telematici: PST `SICID`, `SIECIC`, `SIGP`, `CASSCI`, `CASSPE`, piu' PDP, PAT e PTT/SIGIT in ricerca/documenti.
- Aggiunti controlli di packaging per impedire che i moduli interni del Local Signer vengano esclusi nuovamente dagli installer o dalle route pubbliche di download.

## 2.183.2 - 2026-04-24

- Rafforzato il resolver PST/JPW degli uffici giudiziari: la cache si autoripara se perde metadati ministeriali, il Giudice di Pace di Palmi risolve correttamente su `JPW_SIGP` e la ricerca QBuilder invia sempre `subProc`.
- Aggiunto controllo giornaliero governato delle fonti ufficiali uffici con report JSON e Markdown leggibile, validazione del resolver PST e autoriparazione automatica prima del salvataggio.
- Allineato il Local Signer 1.6.10 al payload QBuilder server-side e reso il wizard PST resiliente alle SOAP Fault `SUBPRO`, mostrando acquisizione assistita invece di errore tecnico bloccante.

## 2.183.1 - 2026-04-24

- Reso il catalogo master una vista navigabile e ricercabile in `/template-atti/catalogo`: tab dedicata `Master professionale`, filtri per gruppo, conteggio dinamico e 420 card reali con ID, canale telematico e azione `Genera dal master`.

## 2.183.0 - 2026-04-24

- Integrato il catalogo master versionato dei template atti con 420 modelli e split governati `core`, `advanced`, `specialist` e `studio_interno`, esposti nel catalogo `/template-atti/catalogo` e collegati al runtime builtin senza perdere compatibilita' con i modelli storici.
- Aggiunto il gateway provider di Lex con policy local-first, stato diagnostico via API e guardrail privacy, cosi' i provider esterni restano separati dai dati sensibili e attivabili solo con configurazione esplicita.
- Rimosso il collo di bottiglia del fascicolo in Lex AI e Assistente locale: sezioni, documenti, agenda, scadenze, cancelleria e istanze non vengono piu' tagliati a 1/3/8 elementi; la reindicizzazione embedda tutti i chunk pending del fascicolo e il prompt riceve inventari completi con budget RAG dinamico.
- Rafforzato il download PST in modalita copia di consultazione: wizard, dettaglio fascicolo e server mantengono `scarica_originale_portale=false` per PST anche se il payload non invia l'opzione, con test anti-regressione sul percorso secondario `Naviga PST`.

## 2.182.24 - 2026-04-24

- Corretto il fallback di riconciliazione tenant su volumi Docker/Windows: quando il filesystem non consente di preservare timestamp/permessi con `copy2`, IUSENTRA copia comunque il contenuto applicativo senza generare errori di avvio su `tenant_user_directory`.

## 2.182.23 - 2026-04-24

- Rafforzato il recupero degli allegati PEC storici: le email gia' salvate con allegati senza file vengono rimesse nella coda IMAP anche se non sono tra gli ultimi messaggi sincronizzati, cosi' comunicazioni precedenti come quelle del 09/04/2026 non restano bloccate dal limite operativo degli ultimi messaggi.

## 2.182.22 - 2026-04-24

- Corretta la regressione degli allegati PEC storici: se un messaggio era gia' presente nello storico ma gli allegati avevano solo metadati e nessun file salvato, la sincronizzazione IMAP ora recupera nuovamente il messaggio e salva fisicamente gli allegati mancanti.
- La vista email non blocca piu' i PDF PEC etichettati dal provider come `application/octet-stream`: l'estensione `.pdf` viene riconosciuta come PDF visualizzabile, mentre XML/EML restano consultabili e firme tecniche come `.p7s` restano scaricabili.
- Aggiunti guardrail e test di regressione per impedire che gli allegati PEC tornino a essere solo nomi/dimensioni nel JSON senza `percorso_rel` valido.

## 2.182.21 - 2026-04-24

- Corretta la riconciliazione dei documenti PST gia' importati: il backfill non usa piu' un match lasco su `PORTALE_TELEMATICO`, ripara i documenti agganciandoli a `id_documento`, `id_cat`, `id_repeatto`, `msg_id`, nome originario e riferimento `pst:...` corretti, senza spalmare nome e metadati di una busta su tutte le altre.
- Il governo documentale compila automaticamente data, tag, classificazione, tipo atto e note con data italiana; i documenti gia' elaborati via OCR vengono contati anche dalla cache indicizzata e il worker marca il documento del fascicolo come OCR completato.
- Chiusi i fallback runtime che riaprivano `Permission denied` su PEC/email e import portale: `GestioneFascicoli` deriva cartelle scrivibili dal DB quando necessario e i runtime usano sempre path tenant-aware per documenti e archivio.

## 2.182.20 - 2026-04-24

- Corretta la regressione dello Step 7 del wizard di acquisizione portale: il log import finale non usa piu' un fallback relativo al repository che in Docker/Railway poteva finire in un path non scrivibile (`portale/import_log.json`), ma resta allineato al data root del portale.
- Il bootstrap runtime ancora insieme `PORTALE_DB`, `PORTALE_UPLOADS` e `PORTALE_IMPORT_LOG_DB`, cosi' se il portale usa `/data/portale/...` anche il log di acquisizione segue automaticamente lo stesso albero persistente e scrivibile.
- Per PST il download predefinito usa ora la copia di consultazione del portale con annotazioni ministeriali, non l'originale firmato del repository, sia nel wizard di acquisizione sia nel modal `Naviga PST`, con fallback server-side coerente anche se l'opzione non viene inviata.
- L'import PST riconcilia i file usando `id_documento`, `id_cat`, `id_repeatto`, `msg_id` e fallback nome+deposito, cosi' upload manuali, ZIP e download browser ereditano i metadati ufficiali del fascicolo e popolano automaticamente `Data`, `Tag`, classificazione e sezione di appartenenza nella UI.

## 2.182.18 - 2026-04-24

- Corretta una regressione nella schermata `Impostazioni -> Firma Digitale`: se l'avvocato sceglie `Token USB (Aruba Key)` il pannello non marca piu' come errore il fatto che il container remoto non veda libreria o token, perche' quel controllo appartiene al `Local Signer` sul PC locale.
- Introdotto un canale operativo esplicito per `PKCS#11 via Local Signer`, riusato dal runtime telematico per non ricadere piu' in modalita demo quando l'utente ha selezionato il token USB ma la verifica reale deve avvenire dal browser desktop.
- Il pulsante `Verifica token collegato` non interroga piu' il server Railway: controlla direttamente `http://127.0.0.1:27272/ping`, quindi restituisce lo stato reale del `Local Signer` e del token sul computer dell'avvocato.
- Aggiunti test di regressione sul canale operativo PKCS#11, sul rendering della pagina impostazioni firma e sullo script JS che deve verificare il `Local Signer` locale invece dell'endpoint server.

## 2.182.17 - 2026-04-24

- Integrati sulla linea principale i fix ancora utili della PR remota rimasta indietro rispetto ai branch ufficiali: i test di bootstrap runtime ora dichiarano in modo esplicito il contesto single-tenant o JSON quando dipendono da quei default, cosi' non tornano flaky al variare della configurazione di ambiente.
- Corretto il test dell'editor atti che puntava a un path Windows hardcoded fuori repository: ora risolve i template dalla root reale del progetto, quindi la suite resta portabile e non si rompe quando il clone vive in una cartella diversa.
- Snellito il manager utenti root nei test di strategia storage evitando il passaggio del backend studio fuori contesto request, cosi' il riallineamento del branch `claude/fix-legal-filing-issues-eW926` sulla testa corrente entra senza trascinarsi assunzioni obsolete.

## 2.182.16 - 2026-04-24

- Corretta una regressione runtime del dettaglio fascicolo emersa nel container Python 3.12: il worker non va piu' in crash durante il boot per una forward reference tipizzata nel merge del catalogo portale, quindi il fix sul governo documentale e' ora davvero servito in app e non solo coperto dai test locali.

## 2.182.15 - 2026-04-24

- Il governo documentale del fascicolo compila ora automaticamente i metadati ufficiali dei documenti portale anche quando i file erano gia' presenti localmente: il dettaglio fascicolo riallinea il catalogo dal core telematico e popola deposito, classificazione e riferimenti documento senza intervento manuale.
- `sincronizza_deposito_portale` non duplica piu' i lotti generici creati in precedenza quando arriva il catalogo ufficiale: riconosce i documenti gia' agganciati per overlap forte su nomi e riferimenti, riusa il deposito locale corretto e arricchisce i documenti collegati.
- Il flusso di import dei file portale evita di creare nuovi vuoti di metadati: quando il download include gia' identificativi e classificazione, i documenti sfusi vengono convertiti direttamente in depositi ufficiali con collegamento e metadati completi invece di restare in un lotto cieco.
- Aggiunti test di regressione su deposito generico riassorbito dal catalogo ufficiale, backfill automatico dal core telematico nella pagina fascicolo, riepilogo documentale e wiring bootstrap, cosi' il contatore `Da riallineare` non torna piu' a salire per questi casi.

## 2.182.14 - 2026-04-23

- Lex AI usa ora contesti strutturati reali per `studio_operativo`, `fascicolo_intelligence`, `conformita_fascicolo` ed `economico`, riusando direttamente `WorkspaceIntelligenteService`, `Responsabile di conformita'`, `preventivi`, `conferimenti` e `fatturazione` invece di limitarsi a riepiloghi testuali fragili.
- Il retrieval applicativo di Lex espone adesso sorgenti operative e di compliance governate: le risposte di `cabina`, `next_action`, `economico` e `compliance` nascono da dati runtime veri dello studio e non da placeholder generici.
- Corretto anche il contesto anagrafico e agenda del fascicolo: Lex risolve finalmente cliente e parti processuali dal fascicolo aperto e aggancia appuntamenti collegati anche tramite `id_cliente`, numero o `RG`, evitando vuoti artificiali nel RAG.
- Rafforzato il provider deterministico con risposte professionali e task-aware su cabina operativa, presidio economico e conformita' del fascicolo, con nuovi test di regressione che bloccano il ritorno dei vecchi vuoti di contesto.

## 2.182.13 - 2026-04-23

- Lex AI non tronca piu' il contesto documentale del fascicolo a 8 elementi: `load_document_context` e il retrieval documentale leggono ora tutto l'archivio del fascicolo aperto, cosi' pratiche con decine di allegati non perdono piu' contesto nel RAG.
- Estratta in `pct/fascicolo_workspace.py` la classificazione condivisa delle sezioni del fascicolo (`attivita' processuali`, `documenti fascicolo`, `udienze e scadenze`, `comunicazioni di cancelleria`, `istanze`), riusata sia dal runtime UI sia da Lex per evitare disallineamenti futuri tra pagina fascicolo e assistente.
- Il contesto strutturato di Lex espone ora anche `fascicolo_sezioni`, con conteggi e voci per sezione, e il retrieval fascicolo pubblica riepiloghi e voci rilevanti delle stesse sezioni, cosi' Lex puo' rispondere sul fascicolo usando la stessa tassonomia che l'utente vede nell'interfaccia.
- Rafforzati i test di Lex per coprire fascicoli con piu' di 8 documenti e workspace completi con attivita', udienze/scadenze, comunicazioni e istanze, prevenendo il ritorno del limite rigido nei prossimi commit.

## 2.182.12 - 2026-04-23

- Resa stabile la disciplina dei due branch gemelli: il workflow `.github/workflows/sync-claude-to-codex.yml` specchia ora automaticamente sia `Codex/legal-electronic-filing-kIxcV` verso `claude/legal-electronic-filing-kIxcV` sia il percorso inverso, evitando riallineamenti manuali ripetuti dopo ogni push.
- Introdotti hook Git versionati in `.githooks/` con autosync locale dei branch ammessi dopo `commit`, `checkout`, `merge` e `rewrite`, cosi' i due branch locali non divergono piu' tra loro durante il lavoro quotidiano.
- `scripts/repo_hygiene.ps1` esegue ora anche il bootstrap di `safe.directory`, installa `core.hooksPath=.githooks` e ripulisce le configurazioni branch orfane, mentre i test di governance controllano esplicitamente questi guardrail per impedire regressioni future.

## 2.182.11 - 2026-04-23

- Riallineato il motore di autenticazione e i runtime tenant-aware per evitare regressioni nei test completi: i permessi di piattaforma restano segregati, i tenant caricati da archivio SQL recuperano correttamente lo `slug` di studio e il layout base non va piu' in errore quando la pagina espone configurazioni locali.
- I flussi `PDP Penale` e `Centro Servizi Telematici` tornano a usare i rispettivi archivi dedicati (`pdp_penale.db` e `workflow.db`) invece dello `studio.db` generico, cosi' i casi, i documenti e gli allineamenti di portale vengono letti e scritti nel dominio corretto.
- Lo scadenziario in ambiente di test usa di nuovo il suo archivio dedicato quando configurato su file JSON, evitando disallineamenti tra le azioni della UI e i controlli che rileggono le scadenze salvate.
- Ripristinata la password iniziale `admin` solo per i test automatici del gestionale che creano il primo amministratore senza bootstrap esplicito, lasciando invariata la generazione casuale della password temporanea negli altri contesti.

## 2.182.10 - 2026-04-23

- Applicati in sequenza i pacchetti `repo hardening`, `repo refactor`, `repo local signer`, `repo 95` e `repo 100` con integrazione coerente sulla struttura reale del progetto.
- Aggiunti i nuovi strumenti di presidio `check_local_signer_boundaries`, `check_lex_quality_gates`, `check_performance_budget` e `check_release_readiness`, insieme ai test dedicati e ai workflow overlay di qualita' e readiness.
- Il `Local Signer` adotta ora i moduli separati `local_signer_mod` per sicurezza/origini, cache AI, facciata AI e bootstrap server, mantenendo la logica AI gia' operativa nel file principale tramite delega incrementale invece di sostituirla con stub vuoti.
- Introdotte anche le guide operative e la documentazione di maturita' (`LEX`, `performance`, osservabilita', multi-studio, release train e checklist di esercizio) previste dai pacchetti strutturali.

## 2.182.9 - 2026-04-23

- Chiusa la tranche di hardening repository richiesta nel bundle senza deviazioni: `pyproject.toml` riallineato a Python `3.12`, `setup.py` governato dal manifest condiviso, `SECURITY.md` e `CONTRIBUTING.md` riscritti in modo coerente con il prodotto e introdotti `constraints` globali per stabilizzare installazioni locali, CI e deploy.
- Rafforzata la pipeline GitHub Actions con controllo baseline Python, sincronizzazione packaging, installazione con `constraints`, gate coverage critico al `65%` e ambiente test coerente anche per `E2E smoke` e `Local Signer / PKCS#11`.
- Corrette le regressioni che facevano fallire la CI reale: `asn1crypto` rientra ora negli extra PDF usati dai job signer, `PYTHONPATH` e packaging sono coerenti nei job smoke, la fixture `admin/database` autentica davvero l'utente nel canale usato dall'app e il bridge HTTP di Lex non forza piu' percorsi guidati quando la richiesta e' di ricerca giuridica o richiede fonti esterne rigorose.
- La firma visibile su PDF non degrada piu' su timbro generico sotto pytest con warning severi: la fusione pagina usa ora un percorso compatibile con `pypdf` senza innescare deprecazioni trattate come errore in CI.

## 2.182.8 - 2026-04-22

- Rimesso in sicurezza l'accesso ai dati di studio sui tenant SQLite: se la modalita' `WAL` non e' disponibile sul volume dati, il motore passa automaticamente a una modalita' compatibile invece di far esplodere pagine come `Panoramica studio`, `Fascicolo` e superfici amministrative collegate.
- Rafforzato anche il gestore utenti dei tenant: se il backend SQL dello studio non e' disponibile, il sistema ripiega in modo governato sull'archivio locale utenti e audit, evitando errori interni sulle pagine di amministrazione e autenticazione.
- Lex AI non lascia piu' passare risposte artificiose o da "esempio di chatbot" sui fascicoli e sulle ricerche legali: le richieste sul fascicolo passano su un percorso guidato piu' concreto, mentre le risposte giuridiche prive di base verificata vengono degradate con prudenza invece di essere mostrate come buone.
- Ridotta anche la verbosita' inutile delle fonti mostrate da Lex nei percorsi operativi: sulle richieste di studio vengono evidenziati solo i riferimenti davvero utili alla risposta, non liste tecniche poco leggibili.

## 2.182.7 - 2026-04-22

- Alleggerito davvero l'avvio nel cloud gestito: in ambiente Railway/Render il bootstrap pesante dei registri dati, della governance installazione e dei tenant legacy non viene piu' eseguito prima che il servizio dichiari la propria disponibilita', ma solo quando serve davvero.
- Ridotto l'avvio predefinito di Gunicorn a un solo processo applicativo, coerente con il motore `gevent`, cosi' il cloud non raddoppia inutilmente il lavoro iniziale sul volume dati durante il primo avvio.
- Il controllo permessi sul volume dati non scandisce piu' in profondita' l'albero `/data` nei cloud gestiti: verifica solo i punti essenziali e lascia partire subito il servizio.
- Railway ha ora una finestra di controllo iniziale piu' ampia (`300s`) per gestire con margine i volumi gia' popolati senza dichiarare prematuramente il servizio non disponibile.

## 2.182.6 - 2026-04-22

- Allineato l'avvio cloud alla porta assegnata dal provider: Gunicorn ascolta ora su `PORT` quando Railway la imposta, mantenendo `8080` come fallback locale. Questo evita controlli iniziali falliti con messaggio `service unavailable` pur in presenza di applicazione corretta.
- Il controllo di prontezza del contenitore usa la stessa porta effettiva del servizio, cosi' il presidio iniziale non resta piu' legato a una porta fissa solo locale.

## 2.182.5 - 2026-04-22

- Alleggerito l'avvio cloud del container: il bootstrap dei permessi sul volume dati non scandisce piu' ricorsivamente tutto `/data` prima di avviare l'applicazione, evitando partenze lente su Railway con archivi gia' popolati.
- Introdotto il controllo di prontezza leggero `/api/pronto`, usato ora sia dall'immagine Docker sia dal deploy Railway e dal compose locale per verificare che la cabina sia pronta senza aspettare controlli piu' pesanti.
- Railway usa ora una finestra iniziale piu' ampia per il primo controllo di avvio, cosi' l'istanza non viene dichiarata non pronta mentre completa il bootstrap iniziale del volume.

## 2.182.4 - 2026-04-22

- Riallineato il Dockerfile al deploy Railway: rimossa la direttiva `VOLUME`, non supportata dal builder Railway, lasciando la persistenza governata dal volume del servizio e dal percorso runtime `/data`.
- Rafforzata anche la salute dei servizi locali: `scheduler-worker` e `ocr-worker` non ereditano piu' un controllo pensato per l'interfaccia web, ma avranno un controllo dedicato coerente con il loro ruolo.

## 2.182.3 - 2026-04-22

- Chiusa la leggibilita' del menu laterale: le voci principali e i collegamenti recenti non vengono piu' tagliati su una sola riga, ma si adattano su due righe con sidebar piu' ampia e spaziatura coerente.
- La navigazione laterale conserva una lettura chiara anche su etichette piu' lunghe come `Cabina Intelligente`, `Tutti i Fascicoli` e i riferimenti recenti di fascicolo o cliente, evitando ellissi premature che rendevano il menu poco usabile.
- Ripuliti diversi testi utente ancora troppo tecnici: `dashboard`, `console`, `wizard`, `workflow`, `runtime`, `fallback` ed `endpoint` vengono ora mostrati con un linguaggio piu' vicino al lavoro di studio (`panoramica`, `cabina`, `percorso guidato`, `percorso operativo`, `motore locale`, `via alternativa`, `indirizzo del servizio`).

## 2.182.2 - 2026-04-22

- Chiusa la governance packaging/deploy che restava ancora troppo fragile: introdotti `packaging_manifest.py`, `pyproject.toml`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md` e lo script `tools/sync_packaging_files.py`, cosi' versione e dipendenze non restano piu' duplicate in piu' file scollegati.
- `setup.py` non mantiene piu' liste hardcoded: legge ora versione da `pct/__init__.py`, runtime requirements da `requirements/base.txt` e gli extra ufficiali da `requirements/pdf.txt`, `requirements/pades.txt`, `requirements/pkcs11.txt`.
- I file flat `requirements.txt` e `requirements-dev.txt` sono ora generati in modo rigoroso dal manifest requirements, con check automatico in CI per impedire nuove divergenze tra locale, container e pipeline GitHub.
- Rafforzata la CI: packaging sync check, lint Ruff piu' severo sui moduli governati, gate mypy sui boundary packaging, coverage minima sui moduli critici (`auth`, `storage`, `lex`, `telematico`) ed E2E smoke su pull request, piu' workflow notturno separato per la suite E2E completa.
- Riallineato il backend PostgreSQL al toolchain attuale: `psycopg2-binary` passa a `2.9.11`, coerente tra manifest e requirements flat.
- Corretto un difetto reale del corpus giurisprudenziale: query FTS con date e punteggiatura (`sentenza n. 8785 del 08/04/2026`) non generano piu' `fts5: syntax error`, ma vengono normalizzate prima della ricerca.
- Sul caso operativo `vorrei fare un preventivo`, Lex conferma ora nel runtime reale il comportamento atteso: risposta workflow-aware, `fallback_triggered=False`, `web_fallback_used=False`, affidabilita' alta e sole fonti di studio realmente pertinenti.

## 2.182.1 - 2026-04-22

- Corretto il comportamento di Lex sui workflow operativi con una `via di mezzo` governata: `preventivo`, `tariffario`, `fattura`, `cabina` e `prossima azione` usano prima il contesto studio e i moduli interni, senza trascinare automaticamente dentro fonti legali e motori di ricerca non pertinenti.
- Il retrieval bounded di Lex puo' ora seminare evidenze dal `contesto studio` gia' costruito da IUSENTRA, cosi' il workflow economico non parte piu' da zero e non degrada su fonti decorative quando il repository interno ha gia' elementi utili.
- Il router delle fonti non aggiunge piu' in automatico `NormativeSource`, `GiurisprudenzaSource` e `LegalIntelligenceSource` a una semplice richiesta tipo `vorrei fare un preventivo`, salvo quando la domanda diventa davvero normativa o richiede fonti ufficiali forti.
- L'affidabilita' e i gap di evidenza sono ora workflow-aware: le richieste legali strette continuano a richiedere fonti ufficiali e confronto forte, mentre i workflow economici non vengono piu' penalizzati con warning tipo `mancano fonti ufficiali` quando la risposta e' solo operativa.
- Riallineato il packaging runtime: `setup.py` include ora anche `sqlalchemy` e `PyMySQL`, usa la stessa versione di `psycopg2-binary` di `requirements.txt`, e il `Dockerfile` esegue il runtime con bootstrap sicuro del volume `/data`, drop privilegiato verso `iusentra` quando il mount lo consente, fallback esplicito a `root` sui bind mount incompatibili, `HEALTHCHECK` e volume dati esplicito.
- Aggiunti test automatici dedicati su source routing economico, seed del contesto studio nel retrieval, payload HTTP bounded e coerenza packaging/versioning.

## 2.182.0 - 2026-04-22

- Integrato in Lex il catalogo governato delle fonti `aperte / con registrazione / partner / riservate / portale istituzionale`, caricato da registry YAML e agganciato davvero a retrieval, source policy, evidence pack, guardrail e payload finale del widget.
- I domini del kit non restano piu' `unknown`: la source policy riconosce ora anche fonti come `INI-PEC`, `Registro Imprese`, `PST / ReGIndE / PdA`, `PAT / SIGA` e `PTT / SIGIT`, distinguendo autorita' della fonte e modalita' di accesso.
- Il fallback web ufficiale cerca solo dove ha senso: per le fonti `partner` o `riservate` Lex non inventa risultati pubblici, ma espone gap di copertura, badge di accesso, warning sulle credenziali necessarie e prossime azioni operative.
- Il widget chat mostra ora anche il profilo di accesso delle fonti (`source_access_label`, `Credenziali`, `Riservata`), cosi' l'operatore capisce perche' una fonte non e' interrogabile via web pubblico.
- Aggiunte regressioni automatiche dedicate su registry, source policy, fallback partner/riservato, orchestrator retrieval e bridge HTTP di Lex.

## 2.181.0 - 2026-04-22

- Introdotto il modulo nativo `Sito Studio`, con dashboard tenant-aware, branding, pagine a blocchi, articoli, servizi, professionisti, sedi, contatti, agenda pubblica e sito web pubblicabile senza CMS esterno.
- Aggiunta la superficie pubblica `/web/<public_slug>/` e la console piattaforma `Piattaforma -> Siti studio`, con repository SQL dedicato sia `SQLite` sia `PostgreSQL`, asset tenant-aware e bootstrap automatico del sito studio dal profilo del tenant.
- Le sezioni pubbliche `Strumenti legali`, `Applicazioni` e `News giuridiche strutturate` sono ora governate da flag espliciti dell'amministratore del sito: restano nascoste e rispondono `404` finche' non vengono attivate da `Sito Studio -> Impostazioni`.
- Chiusa la filiera `prenotazione pubblica -> approvazione studio -> agenda`: le richieste sito si sincronizzano davvero in agenda tenant-aware e la migrazione legacy verso `studio.db` riallinea ora correttamente le colonne `dati_json` richieste dai moduli runtime.
- Rafforzata la migrazione SQLite unificata: le tabelle core legacy (`fascicoli`, `appuntamenti`, `scadenze`, `messaggi`, `utenti`) includono ora `dati_json` gia' nello schema base e nel payload migrato, con riallineamento automatico post-migrazione.

## 2.180.1 - 2026-04-22

- La console `Piattaforma -> Assistenza remota` permette ora al `SUPERADMIN` di configurare direttamente da UI i parametri operativi del modulo: `STUN`, `TURN`, secret condiviso, TTL, durata token WebSocket e `SUPPORT_ADVANCED_URL_TEMPLATE`.
- Il runtime applica subito i valori salvati senza restart manuale e li persiste nella configurazione piattaforma, cosi' i warning di readiness non restano piu' messaggi senza azione possibile.
- Il secret TURN non viene sovrascritto se il campo resta vuoto in modifica, e il modulo continua a bloccare l'escalation avanzata solo quando manca davvero la configurazione necessaria.

## 2.180.0 - 2026-04-22

- Introdotto il modulo `Assistenza remota cliente` governato solo dal `SUPERADMIN`, con console piattaforma dedicata (`/admin/supporto-remoto`), creazione sessione da dashboard studio, scheda cliente e dettaglio fascicolo.
- Aggiunta la filiera completa WebRTC per supporto remoto: link cliente firmato, stanza operatore, signaling WebSocket, condivisione schermo, microfono opzionale, chat tecnica, audit leggibile, consensi espliciti e chiusura sessione tracciata.
- Creato il repository SQL governato del dominio `support_remote` con schema dedicato sia `SQLite` sia `PostgreSQL`, senza fallback invisibili su JSON.
- Integrato l'aggancio al controllo remoto avanzato esterno: l'operatore puo' richiedere l'escalation, il cliente deve approvarla in modo esplicito e il runtime la blocca se `SUPPORT_ADVANCED_URL_TEMPLATE` non e' configurato.
- Allineato il runtime locale e containerizzato: `Sock` inizializzato nella factory Flask, WebSocket registrato nel wiring applicativo, reverse proxy Nginx configurato per `/support/ws/`, percorso persistente `PCT_SUPPORT_DB` e documentazione operativa dedicata.

## 2.179.3 - 2026-04-22

- Corretto il comportamento reale del widget Lex sulla chat operativa: le richieste di `preventivo`, `tariffario`, `fatturazione`, `telematico`, `fascicolo` e `ricerca legale` non restano piu' affidate a prompt generici, ma passano direttamente al bounded workflow governato anche dalla UI `/api/assistente/*`.
- Il bridge HTTP di Lex trasferisce ora davvero il contesto di studio alla pipeline bounded (`messaggi`, `focus`, `profilo richiesta`, `execution policy`, `source policy`) e, quando il contesto interno non basta, abilita in modo esplicito il fallback di ricerca web ufficiale invece di lasciare la risposta nel vago.
- Rafforzato il profilo richiesta economica: `preventivo guidato`, `tariffario e compensi`, `fatturazione/parcelle/pagamenti` hanno ora intenti distinti e portano Lex sul percorso giusto senza risposte meta o simulate.
- Migliorata la risposta deterministica economica: su richieste come `vorrei fare un preventivo` Lex apre il percorso corretto, distingue preventivo/tariffario/fattura e chiede solo i dati davvero necessari per proseguire.
- Aggiunta una cintura di sicurezza lato prompt e lato widget per impedire output meta del tipo `ecco una risposta`, `motivazione`, `simulazione di chatbot` o scaffolding simili.

## 2.179.2 - 2026-04-22

- Rafforzato Lex dove mancava ancora la parte piu' operativa: il retrieval usa ora una cache TTL tenant-aware, cosi' richieste ripetute dello stesso studio riusano il pacchetto evidenze senza rilanciare inutilmente tutte le sorgenti e dichiarano sempre `cache hit` e `ttl` nel payload finale.
- Aggiunti property test veri sulla source policy e sui guardrail legali di Lex (`tier`, ordinamento score, ranking e blocco PDF/sentenze non verificate), con `hypothesis` come dipendenza dev esplicita e governata.
- Chiuso il presidio dei canali telematici esterni con circuit breaker dedicati per ricerca e anteprima portali, messaggi operativi leggibili e nuova diagnostica `PORTAL_CIRCUIT_OPEN` dentro observability.
- Rafforzata la governance storage senza refactor distruttivi: il factory `core_storage_backend` valida ora un contratto minimo comune del backend strutturato tenant-aware prima di usarlo a runtime.

## 2.179.1 - 2026-04-22

- Corretto il `500` reale della sezione `Checklist Atti` sui template stragiudiziali a canale `PEC`, in particolare sul dettaglio built-in `Atto di messa in mora`.
- Riallineato il mapping degli endpoint operativi checklist: il canale `PEC` usa ora l'endpoint Flask reale `lista_messaggi` invece del vecchio alias `messaggi`.
- Aggiunta una salvaguardia nella route `checklist_dettaglio` che normalizza gli alias legacy degli endpoint operativi e impedisce nuovi `BuildError` in render Jinja se un nome route storico non e' piu' registrato.
- Aggiunta regressione HTTP sul template built-in `builtin-tmp-str-008` per garantire che il dettaglio risponda `200` e che il pulsante `Apri canale operativo` punti davvero a `/messaggi`.

## 2.179.0 - 2026-04-22

- Introdotta l'architettura governata `Product Pack / Studio Local Pack / Update Pack`, con bootstrap installazione idempotente, identita' macchina, chiavi per installazione e manifest separati per prodotto, tenant e aggiornamenti.
- Aggiunta la cabina piattaforma `Piattaforma -> Pack installazione` (`/admin/installazione-pack`), riservata al `SUPERADMIN`, con rigenerazione manifest, stato servizi locali e repository SQL/PostgreSQL dei pack.
- Creati repository SQL espliciti per i manifest dei pack, con schema dedicato sia SQLite/SQL locale sia PostgreSQL (`installation_product_pack_manifest`, `installation_studio_local_pack_manifest`, `installation_update_pack_manifest`).
- Estesa la struttura tenant-aware con la root `studio_data/` e sottodirectory governate per `db`, `vectors`, `memory`, `documents`, `attachments`, `audit`, `backups`, `cache`, `jobs` e `keys`.
- Corrette due incoerenze reali di piattaforma: il `SUPERADMIN` puo' usare anche la superficie legacy `/admin/database`, e il registro `Audit` riconcilia i fascicoli sul tenant attivo usando i percorsi request-aware invece della configurazione globale.
- Riallineate le regressioni di bootstrap web e tenant-aware alla separazione vera tra piattaforma e studio, preservando test pubblici PWA, login tenant, audit storico e nuova superficie pack.

## 2.178.13 - 2026-04-22

- Chiarita la configurazione del runtime AI locale nelle `Impostazioni`: il campo non viene piu' presentato come semplice URL, ma come `Prefisso API del runtime locale`, per evitare ambiguita' quando si apre manualmente Ollama dal browser.
- Aggiunto nel pannello AI il controllo rapido `Apri controllo /api/version`, che compone automaticamente l'endpoint corretto a partire dal prefisso configurato e aggiorna anche il promemoria inline visibile all'operatore.
- Rafforzata la regressione statica della tab `AI Locale` per impedire il ritorno di etichette fuorvianti o la perdita del controllo guidato verso `/api/version`.

## 2.178.12 - 2026-04-22

- Introdotto un layer governabile di resilienza runtime con circuit breaker condivisi per `Ollama` e `PEC / IMAP`, cosi' i runtime esterni instabili non vengono martellati all'infinito e restituiscono messaggi operativi leggibili.
- Rafforzata l'osservabilita': il pannello `admin/osservabilita` e il payload `/admin/system-health` leggono ora anche il circuito `PEC / IMAP`, mentre il runtime AI locale espone lo stato del proprio breaker insieme alla diagnostica del provider.
- Aggiunto logging strutturato con masking automatico di CF, email, IBAN e telefoni, attivabile in JSON in produzione senza introdurre dipendenze extra.
- Riallineati i workflow AI che chiamano Ollama (`Lex`, `Coverage AI`, `Update Intelligence`) al client condiviso, evitando path divergenti tra runtime locale e motori assistiti.
- Estesa la suite con test dedicati su logging sensibile, circuit breaker runtime, degrado observability e invarianti deterministici della source policy di Lex.

## 2.178.11 - 2026-04-22

- Integrato il bundle `Lex` con router applicativo piu' ricco, provider deterministico locale per i workflow operativi (`cabina`, `economico`, `telematico_status`, `compliance`, `next_action`) e registry provider riallineato ai nuovi contratti.
- Il retrieval Lex ora attiva davvero il fallback verso fonti ufficiali esterne quando l'evidenza interna non basta, confronta le fonti con trust/freshness/context fit/consensus ed espone nel payload finale `official_sources`, `coverage_gaps`, `fallback_triggered`, `compared_sources` ed `evidence_sufficient`.
- Rafforzati i guardrail legali: le richieste di sentenze, riferimenti puntuali e PDF vengono degradate o bloccate se non emergono riferimenti verificati, invece di completarsi in modo plausibile.
- Aggiunti test dedicati per i 5 scenari chiave del bundle (`sentenza con numero/PDF`, `normativa con fallback ufficiale`, `errore telematico`, `riassunto fascicolo`, `caso economico preventivo/tariffario/fattura`) e riallineata la suite Lex ai nuovi workflow.

## 2.178.10 - 2026-04-20

- Corrette le date nella pagina `Email`: l'elenco e il dettaglio usano ora i filtri condivisi italiani e non mostrano piu' formati `mm/dd`.
- Rafforzato il matching PEC/fascicoli: le notifiche dal canale giustizia (`giustiziacert`, `Notificazione ai sensi del D.L. 179/2012`) vengono collegate correttamente alle comunicazioni di cancelleria del fascicolo.
- `Auto-esiti` non consuma piu' in modo definitivo le PEC PST non abbinate: restano rielaborabili ai click successivi finche' non trovano il deposito giusto.
- `Sincronizza PEC` dalla pagina fascicolo lavora sul fascicolo corrente, espone le PEC in attesa di abbinamento e ricarica la vista anche quando trova comunicazioni gia' presenti per mostrare davvero la sezione aggiornata.

## 2.178.9 - 2026-04-20

- Corretto il flusso `Email`: la sincronizzazione IMAP e il polling PEC ora usano un timeout esplicito, così il pulsante `Aggiorna` non resta più indefinitamente in `Sync` quando il server PEC non risponde.
- Aggiunta la route reale `/email/api/stats`, già richiesta dalla shell UI, per eliminare i `404` silenziosi sul badge posta e riallineare la pagina `Email` al runtime effettivo.
- La pagina `Email` gestisce ora timeout, warning e messaggi operativi leggibili lato browser sia su `Aggiorna` sia su `Auto-esiti`, senza spinner infiniti o esiti muti.
- Corretto il `cockpit fascicolo`: i pulsanti `Apri scheda`, `Apri workflow`, `Apri controllo`, `Apri documenti` e `Apri deposito` attivano davvero il tab corretto anche quando il wiring Bootstrap non si innesca in automatico.
- Aggiunte regressioni eseguibili su timeout IMAP, warning della route `/email/sincronizza`, route `/email/api/stats` e attivazione della cabina fascicolo.

## 2.178.8 - 2026-04-20

- Alleggerito il runtime locale multi-tenant: il bootstrap legacy, la riconciliazione storage e il bootstrap dei moduli dati non vengono piu' rieseguiti a ogni richiesta della stessa sessione tenant-aware.
- Le richieste statiche (`/static/...`) vengono escluse dal bootstrap tenant, evitando il collo di bottiglia che rallentava caricamento di CSS, JavaScript e panoramica generale.
- Aggiunte regressioni automatiche per bloccare il ritorno del bootstrap tenant su asset statici e per garantire che la preparazione del tenant avvenga una sola volta per worker.

## 2.178.7 - 2026-04-20

- Corretto il parser JavaScript del `Wizard preventivi`: alcune espressioni introdotte nella tranche precedente mescolavano `??` e `||` nella stessa riga, bloccando l'inizializzazione completa della pagina e lasciando vuoti i filtri di `Classificazione tassonomica` e le altre superfici guidate del wizard.
- Il wizard ora usa un helper esplicito per scegliere i valori economici della bozza senza rompere il parsing del browser, mantenendo la correzione sulle `Spese generali` dentro `Anticipazioni art. 15`.
- Aggiunta regressione statica sul template per impedire il ritorno di espressioni JavaScript non valide nelle sezioni critiche del preventivo guidato.

## 2.178.6 - 2026-04-20

- Corretto il `Wizard preventivi` sulla bozza economica: quando il flag `Spese generali ex art. 2 D.M. 55/2014` e' attivo, il suo importo non viene piu' inglobato nella riga `Compenso professionale`, ma confluisce nel riepilogo `Anticipazioni art. 15` della bozza come richiesto dal flusso operativo.
- Allineato anche il salvataggio finale del preventivo: il wizard persiste il totale anticipazioni della bozza tramite campo dedicato, cosi' il dettaglio preventivo non diverge piu' da quanto l'operatore ha visto nel riepilogo prima della creazione.
- Aggiunte regressioni eseguibili per calcolo wizard e generazione preventivo, in modo da bloccare il ritorno del bug su `Spese generali` e `Anticipazioni art. 15`.

## 2.178.5 - 2026-04-20

- Il `Quadro intelligente fascicolo` usa ora controlli reali sul fascicolo corrente invece delle vecchie percentuali statiche: anagrafica, documenti, metadati ufficiali di portale, scadenze rispetto alla data odierna, udienze storiche non riallineate e coerenza tra stato della pratica e provvedimenti presenti.
- La regia del fascicolo non propone piu' mosse fuorvianti come `Udienza da portale` su pratiche con udienze ormai storiche: le scadenze vengono mostrate come future oppure scadute, e i provvedimenti finali presenti nel fascicolo entrano nella valutazione operativa.
- I documenti acquisiti dal portale telematico riportano ora davvero nome ufficiale, classificazione, tipo atto, mittente, identificativi del deposito e riferimenti del portale anche sui fascicoli gia' scaricati, grazie alla riconciliazione automatica al primo accesso del dettaglio.
- Il caricamento manuale memorizza il nome originale del file e la UI documento espone metadati ufficiali e origine del documento, cosi' la sezione documentale del fascicolo resta leggibile e verificabile.
- Il presidio intelligente riconosce come chiusa anche una pratica legacy che serializza lo stato come stringa `DEFINITO` o `ARCHIVIATO`, e non duplica piu' gli stessi provvedimenti quando il portale li ha fatti entrare piu' volte nel fascicolo.
- Rafforzato il matching PEC e `Auto-esiti`: oltre al numero RG usa anche nominativo cliente, controparte, oggetto e tribunale, migliorando l'associazione di comunicazioni di cancelleria e aggiornamenti deposito sul fascicolo corretto.

## 2.178.4 - 2026-04-20

- Completato il supporto ufficiale ai costi organismo mediazione ex `D.M. 24 ottobre 2023, n. 150` in `Wizard preventivi` e `Console tariffaria`: regime volontaria / obbligatoria-demandata, esito del primo incontro o degli incontri successivi, maggiorazione art. 31, comma 3 e costo organismo che entra davvero nel totale operativo.
- Corretto il wiring del wizard sulle tipologie a `compenso unico`: la UI non mostra piu' checkbox fasi fuorvianti e le classificazioni tassonomiche aggiuntive usano le fasi reali della pratica collegata.
- Pulite le fonti normative collegate a mediazione e tassonomia, con URL Gazzetta ufficiale corretti (`23G00163`) e tabella normativa `mediazione_costi_odm_dm150` resa disponibile anche nella console tariffaria.
- Aggiunte regressioni eseguibili su calcolo D.M. 150/2023, seed normativo, route wizard e route tariffario per impedire ritorni ai vecchi bug su totale invariato, placeholder indicativi e riferimenti normativi errati.

## 2.178.3 - 2026-04-20

- Rifinito il `Wizard preventivi` con microcopy coerente, stato inline persistente al posto dei vecchi `alert()` browser, messaggi di validazione piu' chiari e ricalcolo guidato e debounced per fasi, ADR, accessori, classificazioni tassonomiche e opzioni fiscali.
- Rafforzata la percezione di performance e coerenza: il wizard ora riusa i fetch di calcolo gia' eseguiti per accessori e classificazioni, mostra feedback immediato mentre aggiorna la bozza e riduce i ricalcoli ripetuti durante la stessa sessione.
- Migliorata la `Console tariffaria` con indicazione esplicita del motore di calcolo attivo, distinzione chiara tra spese generali incluse o escluse e submit con stato di elaborazione visibile.
- Resi i log di `preventivi` e `tariffario` piu' leggibili e narrativi: le operazioni principali raccontano utente, motore, regola, fase e risultato invece di limitarsi a messaggi tecnici di errore.

## 2.178.2 - 2026-04-20

- Corretto davvero il flusso `Preventivi -> Wizard` sui toggle economici: fasi selezionate, spese generali e altri flag booleani incidono ora in modo coerente sia nel calcolo live sia nel salvataggio finale, senza effetti fantasma dovuti ai campi hidden `0/1`.
- Il wizard puo' creare davvero il cliente minimale durante l'inserimento rapido e persiste le `classificazioni tassonomiche` ripetibili anche nei repository SQL/PostgreSQL, con conteggio dedicato e righe aggiuntive di compenso nella bozza.
- Rafforzata la console `Tariffario Forense`: il form route-side rispetta davvero il toggle `Spese generali 15%` e la UI continua a distinguere correttamente `compenso unico` per i profili che lo prevedono.
- Aggiornate le migrazioni SQL e PostgreSQL del dominio preventivi e aggiunte regressioni eseguibili su wizard, repository e route tariffario per impedire ritorni ai vecchi bug di calcolo.

## 2.178.1 - 2026-04-20

- Corretto il `Crash test operativo` nel runtime reale: se il container non ha `pytest`, il motore non fallisce piu' per dipendenza di sviluppo mancante ma usa controlli operativi interni equivalenti per dati sporchi, workflow cliente -> incasso, pipeline AI, publish sicuro, migrazione con rollback e observability azionabile.
- Mantenuta la tracciabilita' con i golden path ufficiali: le fasi continuano a puntare ai test E2E dichiarati nel repo, ma la produzione puo' eseguire gli stessi controlli in modo autonomo e spiegabile.
- Aggiunta copertura automatica sul fallback runtime del crash test, cosi' il comportamento resta dimostrabile sia in CI sia nel container di deploy.

## 2.178.0 - 2026-04-20

- Introdotta la cabina `Piattaforma -> Crash test operativo`, con report reale delle fasi critiche di una giornata di studio, checklist finale `si/no`, ticket di riparazione persistiti e lettura diretta dello stato sistema.
- Aggiunta la filiera governata `pct/operational_resilience.py` + repository SQL/PostgreSQL dedicato per report crash test, ticket di repair e backup blindati, con schema esplicito sia SQLite sia PostgreSQL.
- Aggiunti i comandi ufficiali `iusentra crash-test-operativo` e `iusentra backup-blindato` per eseguire fuori dalla UI il crash test e il piano backup completo + incrementale.
- Il scheduler esegue ora autotest di riparazione alle `07:00`, `13:30`, `19:30` e backup blindato alle `23:50`, iterando sui tenant attivi senza fallback nascosti.
- Estesa la coverage E2E con `tests/e2e/test_operational_crash_day.py` e `tests/test_operational_resilience.py`, che presidiano dati sporchi, failure del publish SQL, osservabilita' azionabile, repository operativi e superficie admin.
- Aggiornate README e documentazione tecnica con guida dedicata al crash test operativo, alle destinazioni backup locale/cloud e alle nuove variabili `PCT_BACKUP_LOCAL_MIRROR_DIR`, `PCT_BACKUP_SECONDARY_MIRROR_DIR`, `PCT_BACKUP_SECONDARY_LABEL`.

## 2.177.0 - 2026-04-20

- `/applicazioni` e' stata trasformata da catalogo di scorciatoie a **workspace operativo reale**, coerente con `/strumenti-legali`: la voce selezionata si apre ora nella stessa pagina con contesto fascicolo, form inline, KPI, tabelle risultato e CTA verso il dominio reale.
- Introdotta una filiera governabile dedicata per il runtime applicazioni: `pct/applicazioni_runtime.py` risolve il tipo di modulo e normalizza i risultati, mentre `web/services/applicazioni_runtime.py` costruisce i pannelli veri per tool, template, economico, telematico, lookup, rassegna, giurisprudenza e utility.
- Le vecchie schede dettaglio non sono piu' una falsa applicazione autonoma: `/applicazioni/<id>` reindirizza ora al workspace attivo e la UI espone davvero i moduli correlati, senza fermarsi a un elenco di link.
- Aggiornati template, SCSS ufficiale e test di route/comportamento per presidiare il nuovo golden path del workspace applicazioni.

## 2.176.0 - 2026-04-19

- Allineata davvero `Checklist Atti` al catalogo professionale di `Template Atti`: la checklist non si ferma piu' a 30 schede curate ma ingloba anche tutte le checklist derivate dai `288` template built-in del workspace atti.
- La copertura tra le due superfici e' ora verificabile: `288/288` template professionali e `25/25` tassonomie `area -> branca -> sottobranca` del catalogo template risultano presenti anche in `/checklist`.
- Estesa la UI della checklist con messaggio di copertura reale del catalogo professionale, badge del nuovo canale `Workflow misto / redazione professionale` e dettaglio operativo arricchito con il profilo del template derivato.
- Aggiornati dominio, route e test per presidiare rami prima scoperti come `Procure e deleghe`, `UNEP e notificazioni`, `Societario`, `Immigrazione e cittadinanza` e tutte le altre varianti del catalogo atti.

## 2.175.1 - 2026-04-19

- `admin/utenti-piattaforma` e' diventata una console operativa completa per gli account globali: ora il `SUPERADMIN` puo' modificare davvero nome, email e stato degli account piattaforma senza passare dagli studi.
- La piattaforma puo' ora generare o sostituire il `SUPERADMIN` in modo governato: il nuovo account nasce solo a livello piattaforma, il ruolo resta unico e il precedente titolare viene declassato al ruolo scelto.
- Aggiunto il trasferimento esplicito del ruolo `SUPERADMIN` tra account globali esistenti, con chiusura pulita della sessione uscente e messaggio di riallineamento professionale.
- Estesa la copertura automatica con test di dominio e route per generazione, trasferimento e modifica degli account piattaforma.

## 2.175.0 - 2026-04-19

- Ridisegnata la superficie `Checklist Atti` come catalogo professionale strutturato per `area -> branca -> sottobranca`, con filtri reali, metriche operative e copertura estesa a lavoro, famiglia, penale operativo, amministrativo avanzato, esecuzioni e ADR.
- Portato il catalogo checklist a `30` template reali, includendo nuovi flussi per impugnazione licenziamento, separazione consensuale, divorzio congiunto, modifica condizioni familiari, opposizione esecutiva, motivi aggiunti TAR, appello al Consiglio di Stato, memoria ex art. 415-bis c.p.p., dissequestro, negoziazione assistita e diffida stragiudiziale.
- Corretto il naming delle cartelle: la data usa ora sempre il formato italiano filesystem-safe `gg-mm-aaaa`, coerente tra dominio, dettaglio checklist e wizard.
- Ripulite le viste checklist da testi corrotti e grouping povero, con nuova UI responsive governata da SCSS dedicato e test di regressione su dominio e route.

## 2.174.3 - 2026-04-19

- Reso il `Registro Attivita'` piu' spiegabile sui fascicoli storici: la pagina segnala ora se il riferimento e' attivo, riconciliato verso un fascicolo corrente oppure solo storico, invece di mostrare soltanto un ID apparentemente "sparito".
- Introdotta una riconciliazione automatica degli eventi fascicolo tramite documenti univoci presenti nel dettaglio audit, cosi' un vecchio ID puo' essere collegato al fascicolo corrente dopo migrazione o ricreazione del record.
- Aggiunta regressione UI sul caso `vecchio ID fascicolo -> nuovo fascicolo corrente`, per evitare che il registro torni a sembrare incoerente dopo riallineamenti storage o import storici.

## 2.174.2 - 2026-04-19

- Il `SUPERADMIN` di piattaforma non vede piu' la shell operativa di studio quando non e' in impersonazione: la navigazione principale mostra solo la superficie piattaforma e le route non piattaforma lo riportano al pannello admin, eliminando l'ambiguita' tra app di studio e cabina superadmin.
- `admin/utenti-piattaforma` non si limita piu' a segnalare le anomalie: ora permette di spostare davvero un account globale non `SUPERADMIN` dentro uno studio, preservando credenziali, stato attivo, storico accessi e audit.
- Introdotto il trasferimento governato degli utenti tra repository auth, con import strutturato nel tenant di destinazione e rimozione forzata del record globale anomalo solo durante il trasferimento amministrativo.

## 2.174.1 - 2026-04-19

- Chiusa davvero la separazione tra `SUPERADMIN` di piattaforma e gestione utenti legacy di studio: le route `/utenti`, `/utenti/nuovo`, `/utenti/<id>/modifica`, `/profili`, `/audit` e `/utenti/<id>/permessi` reindirizzano ora il `SUPERADMIN` verso `admin/utenti-piattaforma`.
- La schermata legacy `Nuovo utente` non mostra piu' il ruolo `SUPERADMIN` e il backend rifiuta in modo esplicito ogni tentativo di forzarlo via POST, cosi' uno studio non puo' piu' creare o promuovere il superadmin nemmeno da percorsi diretti.
- Rimossa anche l'ambiguita' di navigazione: il menu amministrativo tenant non viene piu' mostrato al `SUPERADMIN`, che usa solo la superficie piattaforma dedicata.

## 2.174.0 - 2026-04-19

- Resi ufficiali i tre golden path certificati di prodotto con nomi stabili e dimostrabili: `tests/e2e/test_studio_reale_flow.py`, `tests/e2e/test_ai_pipeline_full.py` e `tests/e2e/test_tenant_migration_full.py`, collegati alla CLI `iusentra golden-path`, alla governance prodotto e alla documentazione E2E.
- Blindata la migrazione `zero-risk`: ogni esecuzione persistente genera ora anche uno `snapshot pre-migrazione` fisico nel backup tenant-aware, espone un `diff_summary.by_domain` leggibile e salva nel report il contesto di rollback con comando guidato.
- Introdotto il rollback ufficiale `iusentra migrate --tenant=<slug> --rollback`, che ripristina il backend precedente dal report reale senza fallback invisibili e persiste un artefatto di rollback dedicato.
- Rafforzata l'osservabilita' operativa con tassonomia errori normalizzata (`OCR_TIMEOUT`, `OCR_QUEUE_OVERFLOW`, `AI_MODEL_UNAVAILABLE`, `TENANT_DB_ERROR`, `MIGRATION_FAILED`) e nuovo endpoint JSON `/admin/system-health` con stato sintetico di scheduler, OCR, AI e database.
- Estesa la governance della `Coverage AI`: il dettaglio draft espone ora anche policy di autopublish e blocco `ai_governance`, cosi' review, publish SQL e audit umano risultano ancora piu' spiegabili.

## 2.173.1 - 2026-04-19

- Corretto il disallineamento tra `storage_key` canonico e cartella legacy basata su `slug`: la riconciliazione tenant-aware e' ora bidirezionale e ripopola anche l'alias storico quando il dato autorevole esiste gia' nel tenant canonico, evitando l'effetto falso di fascicoli o clienti "spariti".
- La `Copertura AI` mostra ora come nome autorevole dello studio il tenant di piattaforma e, se `config/studio.json` contiene un nome interno diverso, lo espone solo come `configurazione interna studio`.
- Il dettaglio studio superadmin mostra il percorso storage canonico reale invece del vecchio `./data/tenants/{slug}/`, cosi' non confonde piu' slug legacy e root effettiva del tenant.

## 2.173.0 - 2026-04-19

- Resi i `golden path ufficiali` ancora piu' dimostrabili: la CLI `iusentra golden-path` salva ora sia report JSON sia report leggibile Markdown, mentre la governance prodotto mostra esplicitamente il percorso del report eseguibile.
- Blindata la `Coverage AI` con audit review forte su SQLite e PostgreSQL: motivo decisione, firma reviewer, diff tra draft originale e versione corrente, storico revisioni persistito e publish SQL tracciato.
- Rafforzato l'`Assistente migrazione` con `snapshot pre-migrazione` e `log operativo`, cosi' il report racconta davvero precheck, passaggi eseguiti, failure mode e recovery guidato.
- Estesa l'osservabilita' con `messaggio operatore` e remediation piu' azionabile per HTTP, OCR, worker OCR, AI locale, storage e capability prodotto.
- Aggiunti test E2E ufficiali dedicati su studio, Coverage AI e migrazione tenant completa per rendere i flussi core dimostrabili e ripetibili.

## 2.172.0 - 2026-04-19

- Ridisegnato il dettaglio fascicolo come `cabina operativa` professionale: la vista include ora i tab `Cabina`, `Quadro intelligente`, `Workflow -> incasso`, `Controllo economico`, `Governo documentale` e `Deposito e conformita'`.
- Il fascicolo unifica davvero le superfici gia' esistenti nello stesso centro di lavoro, con riepilogo del prossimo passo, KPI rapidi, workflow economico, controllo documentale e presidio del deposito senza duplicare pagine sparse.
- Aggiornati SCSS governati, test UI/route e documentazione prodotto per rendere il nuovo cockpit parte ufficiale del golden path operativo.

## 2.171.9 - 2026-04-19

- Corretto il resolver auth multi-tenant della piattaforma: il `SUPERADMIN` globale non legge piu' il ruolo dal `studio.db` locale del tenant, ma usa solo la persistenza auth di piattaforma, evitando 403 e incoerenze tra account root e storage del singolo studio.
- La superficie `admin/utenti-piattaforma` e le route superadmin restano ora separate dagli utenti tenant-aware anche quando sul SQL locale esiste un record storico `admin` con ruolo diverso.
- Aggiunta regressione sul caso sporco `JSON piattaforma = SUPERADMIN` ma `SQLite locale = AMMINISTRATORE`, per evitare di tornare a mostrare permessi tenant al superadmin di piattaforma.

## 2.171.8 - 2026-04-19

- Chiuso il modello di piattaforma in modo piu' professionale: il `SUPERADMIN` ha ora una superficie dedicata `admin/utenti-piattaforma`, separata dagli utenti tenant-aware degli studi, con reset password governato e controlli sulle anomalie globali.
- `Aggiornamenti legali` mostra come nome autorevole dello studio il tenant registrato in piattaforma e, se lo `studio.json` interno usa un nome diverso, lo espone solo come configurazione interna per evitare l'effetto "nuovo studio fantasma" nel pannello superadmin.
- Corretto il bootstrap auth multi-tenant: il riallineamento dell'unico `SUPERADMIN` di piattaforma avviene ora dentro l'application context Flask, quindi il runtime non resta incoerente all'avvio.

## 2.171.7 - 2026-04-19

- Blindata la separazione tra piattaforma e tenant: `SUPERADMIN` e' ora un ruolo unico di piattaforma, non puo' appartenere a uno studio e non puo' essere creato o promosso dai flussi tenant-aware.
- `Update Intelligence` del superadmin e' diventato davvero tenant-aware: dashboard, fonti, staging, analisi, review, archive e API operano sullo studio selezionato e non su un archivio globale implicito.
- Aggiunto bootstrap controllato dei dati legacy `legal_updates` dalla root storica verso il repository del tenant selezionato, con UI e documentazione allineate alla regola "uno studio, un backend, un archivio strutturato".

## 2.171.6 - 2026-04-19

- Introdotti i `golden path ufficiali` come capability eseguibile di primo livello: la CLI `iusentra golden-path` esegue le suite ufficiali, persiste un report leggibile e la pagina `admin/governance` mostra stato `pass/fail` dei flussi core business, migrazione tenant, Coverage AI, Update Intelligence e telematico.
- Blindato ulteriormente l'`Assistente migrazione`: il report persistito include ora `diff pre/post`, evidenza di `tenant sporco`, failure mode classificati e postura di rollback/recovery guidata, poi la UI li rende leggibili senza ricostruzioni manuali.
- Rafforzata l'osservabilita' operativa con tassonomia esplicita (`HTTP`, `OCR`, `WORKER`, `AI`, `STORAGE`, `PRODUCT`), soglie operative e remediation guidata direttamente nella dashboard admin.

## 2.171.5 - 2026-04-19

- La pagina `admin/governance` distingue ora in modo esplicito tra `backend strutturato effettivo dello studio` e `capability tecnica della piattaforma`, evitando di confondere il runtime reale del tenant con la parity teorica dei domini.
- Aggiunto selettore studio tenant-aware nella governance prodotto, con riepilogo del backend effettivo, regola di lettura corretta ed eccezioni architetturali esplicite per filesystem, telematico e AI locale.
- Estesi i test e la documentazione per chiarire che uno studio in SQLite deve governare tutti i dati strutturati su SQL locale e uno studio in cutover reale deve governarli tutti su PostgreSQL.

## 2.171.4 - 2026-04-19

- L'`Assistente migrazione` non resta piu' agganciato a un report vecchio rimasto nella sessione del browser: se nel backup esiste un report piu' recente per lo stesso studio, la pagina usa quello.
- Corretto il caso in cui, dopo un rerun pulito della migrazione, la UI continuava a mostrare warning storici o percorsi di report obsoleti pur avendo gia' un report piu' nuovo e coerente.
- Aggiunta regressione sul confronto tra report di sessione e ultimo report reale disponibile nel backup tenant-aware.

## 2.171.3 - 2026-04-19

- Corretto il `500` di `/admin/assistente-migrazione` che compariva dopo una migrazione reale quando il report piu' recente conteneva metadata descrittivi (`db_path`, `backend_kind`, firme sorgente) dentro le statistiche repository PostgreSQL.
- La pagina migrazione ora tollera report runtime completi e continua a renderizzare domini, repository e riepilogo finale senza trattare i campi testuali come conteggi numerici.
- Aggiunto test di regressione sul caso del report PostgreSQL tenant-aware con statistiche miste numeriche e descrittive.

## 2.171.2 - 2026-04-19

- Rafforzata l'osservabilita' operativa: `/admin/osservabilita` segnala ora degradi reali su endpoint `5xx`, OCR, runtime AI locale e storage, con indicazioni concrete su come intervenire.
- Estesi i test end-to-end delle superfici nuove (`Assistente migrazione`, `Copertura AI`, `Update Intelligence`, `News giuridiche`) per verificare copy italiana, raggiungibilita' admin e coerenza UI come unico prodotto.
- Aggiunto un presidio sul cutover tenant-aware: se la migrazione PostgreSQL fallisce, il tenant non attiva il backend esterno e resta sul backend corrente senza cutover parziale.
- Aggiornate README e documentazione tecnica E2E/observability per chiarire i criteri di chiusura dei flussi critici e del failure handling.

## 2.171.1 - 2026-04-19

- L'`Assistente migrazione dati` espone ora l'ultima esecuzione reale direttamente in `/admin/assistente-migrazione`, con riepilogo domini core, repository SQL, controlli di consistenza ed errori veri del cutover.
- In caso di fallimento, la UI non si limita piu' a un flash temporaneo: mantiene il contesto dell'errore, indica il target richiesto e suggerisce passi concreti per la risoluzione.
- Aggiornata la documentazione storage per chiarire che la superficie admin di migrazione mostra report reali e non solo workflow descrittivi.

## 2.171.0 - 2026-04-19

- L'`Assistente migrazione dati` esegue ora il cutover completo del tenant, non solo del core `studio.db`: include `template atti`, `legal intelligence`, `giurisprudenza`, `repository telematico`, `workspace intelligence`, `Update Intelligence` e `Coverage AI`.
- Il repository `Update Intelligence` ha ora parita' reale anche su PostgreSQL tenant-aware, con schema dedicato, scritture runtime compatibili e replica strutturata di fonti, staging, analisi, review, archivio normativo, giurisprudenza, prassi, news e audit.
- La migrazione verso SQLite non richiede piu' l'unlink fisico di `studio.db`: il target viene rigenerato in-place, cosi' il cutover non si rompe quando il file esiste gia' o e' aperto dal runtime locale.
- Risolta la collisione tra `audit_log` core e audit del motore aggiornamenti sul PostgreSQL condiviso del tenant, usando una tabella dedicata per il dominio `Update Intelligence`.
- Aggiornate matrice storage, piano di migrazione e README per riflettere il fatto che il percorso ufficiale `JSON -> SQLite -> PostgreSQL` copre davvero tutti i domini migrabili del tenant.

## 2.170.6 - 2026-04-18

- Chiusa la parita' SQL della `Copertura AI`: il modulo usa ora anche `SQLite locale` come backend reale tenant-aware, invece di bloccarsi sui soli tenant PostgreSQL.
- Il tenant selezionato dalla UI prevale finalmente sul tenant di sessione, cosi' dashboard, review e publish operano davvero sullo studio scelto dal superadmin.
- La coverage crea e usa schema SQL reale anche su `studio.db`, quindi audit, gap queue, draft v2, review e publish SQL possono funzionare anche negli studi locali senza PostgreSQL esterno.
- Aggiornati messaggi UI e documentazione per distinguere chiaramente backend `SQLite locale` e `PostgreSQL tenant-aware`.

## 2.170.5 - 2026-04-18

- Corretta l'acquisizione HTML paginata delle fonti giuridiche: la pipeline `Update Intelligence` non tronca piu' artificialmente a 40 risultati e segue anche le pagine aggiuntive dei portali con navigazione `frame3_item`, cosi' sorgenti come Cassazione possono acquisire tutti i documenti disponibili.
- Riallineata la `Copertura AI` al backend reale dello studio: dashboard e selettore mostrano ora il nome studio configurato e il backend effettivo `PostgreSQL tenant-aware`, invece di lasciare la UI ancorata al vecchio `JSON` del registry storico.
- Riscritta la schermata `Review copertura AI` con guida operativa, autoselezione della prima bozza, stati vuoti comprensibili, contesto di retrieval visibile e gestione errori piu' chiara, per evitare schermate apparentemente vuote o incomprensibili.

## 2.170.4 - 2026-04-18

- La pagina `/admin/aggiornamenti-legali/fonti` espone ora una guida fissa e responsiva ai campi del form, con significato operativo di `codice`, `categoria`, `classe`, `parser`, `tipo`, `ufficiale` e `attiva`.
- Aggiunti esempi pronti per Corte Costituzionale, Cassazione Massimario, Cassazione - Terza Sezione Civile e Giustizia Amministrativa, cosi' il form resta autosufficiente anche senza documentazione esterna.
- Rafforzati placeholder e microtesti del form per evitare errori di coerenza tra nome fonte, URL e codice tecnico.

## 2.170.3 - 2026-04-18

- Chiusa davvero la console `Copertura AI`: il backend coverage seleziona automaticamente il tenant unico attivo oppure lo studio scelto dalla UI, invece di restare dipendente da un `g.tenant` implicito.
- Aggiunto il riuso del PostgreSQL tenant-aware anche per configurazioni legacy con credenziali studio gia' presenti ma `db_config.mode` storico non ancora riallineato, senza attivare fallback fittizi sul core storage.
- Dashboard e review queue ora espongono lo studio selezionato, propagano `tenant_slug` su azioni e API, e mostrano correttamente `DB configurato: si` quando il backend coverage reale e' risolvibile.

## 2.170.2 - 2026-04-18

- La pipeline `Coverage AI` non dipende piu' solo da variabili `LEGAL_COVERAGE_DB_*`: quando il tenant usa gia' PostgreSQL, dashboard, review e publish SQL agganciano automaticamente il backend studio reale.
- Chiusa la parity SQL/PostgreSQL dei repository rimasti aperti per `template atti`, `legal intelligence`, `giurisprudenza`, `repository telematico` e `workspace intelligence`, mantenendo JSON come export o bootstrap controllato.
- Aggiunti repository runtime dedicati per stato editor, snapshot intelligence e corpus strutturati, con test di roundtrip e aggiornamento della matrice storage e della documentazione coverage.

## 2.170.1 - 2026-04-18

- Resa finalmente visibile la console del motore `IUSENTRA Update Intelligence`: link esplicito nel menu superadmin `Piattaforma -> Update Intelligence`.
- Aggiunti ingressi rapidi in `Motori Legali` e nella pagina `News giuridiche` per aprire direttamente dashboard aggiornamenti, fonti ufficiali, acquisizione, analisi AI, coda revisioni e archivio strutturato.
- Estesi i test per verificare che un superadmin autenticato veda davvero i collegamenti del motore in sidebar e nelle superfici `Motori Legali`.

## 2.170.0 - 2026-04-18

- Completato il motore `IUSENTRA Update Intelligence` anche sul piano operativo visibile: gestore fonti, area di acquisizione documenti, analisi AI, archivio strutturato e audit navigabili da interfaccia admin.
- Aggiunte le route e le API per gestione fonti, fetch mirato, rianalisi manuale di documenti raw, review `edit-and-approve`, consultazione di normative, versioni, giurisprudenza, prassi, news e audit.
- Resa esplicita la logica di popolamento: scansione batch, fetch per singola fonte, rianalisi del singolo documento e pubblicazione guidata.
- Estesi i test di regressione su superfici admin, API del motore e form operativi del modulo.

## 2.169.0 - 2026-04-18

- Introdotto `IUSENTRA Update Intelligence`, il motore di monitoraggio normativo, giurisprudenziale e di prassi con pipeline `fonte -> acquisizione -> analisi AI -> matching -> revisione -> pubblicazione`.
- Aggiunto l'archivio strutturato dedicato `legal_updates.db` con tabelle per fonti, raw documents, documenti normalizzati, analisi AI, normative versionate, giurisprudenza, prassi, news, coda revisioni e audit.
- Le fonti ufficiali iniziali includono Gazzetta Ufficiale, Normattiva, dati.normattiva.it, Corte costituzionale, Cassazione Massimario, Giustizia Amministrativa, EUR-Lex, Agenzia delle Entrate e Ministero del Lavoro.
- Disponibili la dashboard admin `/admin/aggiornamenti-legali`, la coda revisioni `/admin/aggiornamenti-legali/review` e la pagina utente `/legal-intelligence/news`.
- Aggiunto il comando CLI `iusentra aggiornamenti-legali` e i job scheduler dedicati per eseguire la scansione periodica delle fonti.

## 2.168.0 - 2026-04-18

- Estesa la parita' storage reale su SQLite e PostgreSQL anche ai moduli economici: `preventivi`, `conferimenti`, `timesheet`, `fatturazione` e `pagamenti`.
- Il cutover ufficiale `JSON -> SQLite -> PostgreSQL` migra ora anche preventivi, parcelle, link pagamento e configurazione pagamenti con report di consistenza.
- Il workflow `cliente -> preventivo -> conferimento -> fascicolo -> attivita' -> parcella -> incasso` e' ora raccontato e verificato come capability di prodotto, non solo come somma di moduli.
- Aggiunti il comando CLI `iusentra demo-check`, la card dashboard `Studio reale in 5 minuti` e il riepilogo timesheet -> parcella per guidare l'onboarding operativo.
- Riallineati README, matrice storage, guida deploy e disciplina release alla nuova realta' del prodotto e alla repo `antmm2605/IUSENTRA`.

## 2.167.0 - 2026-04-18

- Lex ora profila in modo deterministico il tipo di richiesta prima di rispondere, distinguendo normativa, giurisprudenza, drafting, sintesi fascicolo, checklist operative e spiegazioni per cliente.
- Introdotto il `Source Policy System` modulare con ranking per tier, modalita' `strict / balanced / broad`, valutazione delle fonti interne ed esterne e riepilogo prudenziale dell'affidabilita'.
- Il contesto assistente passa al runtime AI anche `request_profile`, `source_policy_summary`, `source_mode`, confidenza e motivazione, compreso il ramo di arresto prudenziale quando mancano fonti forti.
- Il widget Lex mostra in UI l'affidabilita' della risposta e preserva correttamente fonti, citazioni e metadati preparati dal server anche nel flusso companion locale.
- Aggiunto il modulo compatibile `ai_lex_sources.py` e la documentazione tecnica `docs/LEX_SOURCE_POLICY_SYSTEM.md` per integrare il sistema senza dipendere da un file monolitico.
- Rafforzati i test su source policy, contesto assistente, grounding, widget e compatibilita' pubblica del modulo.

## 2.166.0 - 2026-04-18

- Introdotto il modulo `timesheet` con UI dedicata, filtri, cambio stato e collegamento a cliente e fascicolo.
- Le superfici `Panoramica`, `Cartella cliente` e `Fascicolo` espongono ora KPI economici, workflow cliente -> incasso e indicazioni operative condivise.
- Rafforzato il governo documentale del fascicolo con tagging, aggiornamento metadati, ricerca full-text contestuale e riepilogo versioni/OCR/portale.
- Estesa la migrazione storage per includere il timesheet in modo retrocompatibile anche sui tenant legacy privi del path dedicato.
- Aggiunti test di dominio e di superficie per timesheet, dashboard economica, workflow operativo e document management.

## 2.165.0 - 2026-04-17

- Portato PostgreSQL a backend reale tenant-aware in lettura e scrittura per utenti, clienti, fascicoli, agenda e scadenziario.
- Introdotto il cutover ufficiale `JSON -> SQLite -> PostgreSQL` con report di consistenza persistito sotto `backup/` del tenant.
- Runtime storage aggiornato per bloccare fallback invisibili a JSON quando PostgreSQL e' backend core attivo.
- Pannello admin storage riallineato con test connessione, attivazione esplicita e tracciamento ultimo report di migrazione.
- Aggiunto il comando CLI ufficiale `iusentra migrate --to=postgres --tenant=<slug-tenant>`.
- Rafforzati i test su runtime PostgreSQL, governance storage, migrazione con report e comando CLI.

## 2.164.4 - 2026-04-17

- Riallineato il blocco "Clausola per la risoluzione delle controversie" del `preventivo guidato` al form classico di creazione preventivo.
- Nel wizard la sezione ora espone lo stesso copy professionale, il presidio consumatore, il ripristino del testo standard e la stessa resa della fonte modello usata nel conferimento.
- Rafforzati i test del wizard per bloccare regressioni visive e di flusso sul passaggio preventivo -> conferimento.

## 2.161.0 - 2026-04-17

- Introdotto il catalogo centrale della piattaforma legale operativa con 22 procedure derivate da wave1 e wave2 della tassonomia legale.
- Preventivi, conferimenti, fascicoli e parcelle ora persistono il profilo procedurale condiviso con canale, registro e workflow operativo.
- Workflow onboarding/commerciale e repository strutturato allineati alla nuova procedura operativa, con propagazione fino al fascicolo e alla fatturazione.
- Contesto economico e documentazione di prodotto aggiornati per associare in modo esplicito tariffario, parcella e fattura alla stessa procedura operativa.

## 2.156.0 - 2026-04-16

- CI resa indipendente da branch hardcoded e rafforzata con workflow dedicati per CodeQL, dependency review, `pip-audit` e SBOM.
- Wiring Flask dei blueprint portato su registro dichiarativo in `web/bootstrap/blueprint_registry.py`.
- Scheduler irrobustito: avvio consentito solo su worker dedicato o override esplicito.
- Contesto Lex arricchito con l’headline del cockpit `Motori Legali`, così l’assistente riceve anche il quadro operativo del dominio legale.
- Packaging dipendenze riorganizzato sotto `requirements/` con separazione tra runtime base e sviluppo.
- Documentazione di prodotto completata con matrice storage, disciplina di release e changelog.




