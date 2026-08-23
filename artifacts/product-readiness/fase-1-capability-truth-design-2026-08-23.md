# Fase 1 — Capability Truth Registry: disegno esecutivo

Data: 23/08/2026
Stato: disegno implementato e accettato localmente per la Fase 1; nessun flusso P0 viene promosso a completo da questo documento.

## Obiettivo verificabile

Creare un unico catalogo versionato delle 17 superfici P0 richieste, esporlo con un'API JSON autenticata e renderlo nella pagina React `Amministrazione` dello studio. Il catalogo deve rendere esplicito ciò che è provato, ciò che è solo implementato e ciò che non è ancora verificato. Una prova mancante non viene convertita in uno stato positivo.

Le superfici P0 iniziali sono: autenticazione e cambio tenant, apertura cliente, conflitto, preventivo, mandato, fascicolo, attività, documento, PEC, scadenza, deposito, ricevute, fattura, pagamento, portale, audit e chiusura fascicolo.

## Decisioni architetturali

| Decisione | Motivazione e presidio anti-regressione |
| --- | --- |
| Catalogo di prodotto nel codice versionato | La prontezza è metadato di rilascio, non dato operativo dello studio. La fonte autorevole sarà un catalogo Python immutabile; nessuna tabella SQLite/PostgreSQL, JSON tenant-aware o file di runtime viene introdotto. |
| Stato conservativo | `verificata` sarà possibile solo con prove correnti dichiarate. Per la prima generazione le prove mancanti restano `da verificare`, con prossima azione indicata per la Fase 2. |
| API propria e read-only | `GET /api/v1/ui/amministrazione/prontezza-prodotto` richiederà sessione e `utenti.leggi`, non conterrà segreti né dati di altri tenant e non eseguirà chiamate a provider, scansioni di filesystem o scritture. |
| Superficie full React esistente | La vista sarà una scheda di `/amministrazione?tab=prontezza-prodotto`, dentro `AmministrazionePage.tsx`. Non modifica né usa il fallback Jinja/SUPERADMIN. |
| Generazione riproducibile | Uno script genererà il dossier Markdown, la matrice di release e il changelog del registro dal medesimo catalogo; la verifica `--check` impedirà divergenze. L'azione menu sarà restituita dal bridge a partire dalla navigazione del catalogo. |
| Tele­matico riusato, non duplicato | Il registro generale referenzierà l'esistente `pct.telematico_truth_registry` per le prove e le dipendenze telematiche. Sentinella e fonti ufficiali rimangono il dominio della Fase 6. |

## Contratto dati

Ogni capability avrà almeno: identificativo, modulo, owner, stato, versione, feature flag, route, API, backend, operazioni disponibili, permessi, fonte dati/storage, test associati, ultima verifica, smoke browser, ambiente, prove CI/browser/provider, dipendenze esterne, limitazioni, rollback, incidenti aperti e prossima azione.

Le prove sono record strutturati con `kind`, `status`, `label`, `reference`, `lastVerified` e `note`. Gli stati possibili sono limitati e non promozionali: `verificata`, `parziale`, `da_verificare`, `bloccata`, `non_applicabile`. Un riferimento a un test esistente non equivale a un test superato; un provider non contattato resta `non verificato`.

La risposta API avrà un contratto esplicito: `ok`, `generatedAt`, `registryVersion`, `applicationVersion`, `scope`, `contracts`, `summary`, `capabilities`, `navigation` e `warnings`. Le date visibili saranno formattate dalla UI in `Europe/Rome`; un valore non disponibile sarà mostrato come `Non ancora verificato`, mai come data ISO grezza.

## Percorso di implementazione

1. Aggiungere `pct/capability_truth_registry.py` con dataclass/enum, catalogo delle 17 capability P0, validazione e builder read-only.
2. Aggiungere `scripts/react-migration/generate_capability_truth_registry.py` che materializza documentazione, matrice release e changelog sotto `artifacts/product-readiness/`; usare `--check` nei test.
3. Estendere il bridge `react_amministrazione_bridge` con il payload minimale del registro e con l'azione di menu generata. Esporre la rotta API con le stesse regole RBAC dell'area Amministrazione.
4. Estendere `amministrazioneData.ts`, creare il client isolato `productReadinessData.ts` e aggiornare `AmministrazionePage.tsx`: overview sintetica, elenco denso ma leggibile, dettaglio espandibile per ogni capability, stati loading/errore/vuoto/permesso e layout mobile senza scroll orizzontale della pagina.
5. Aggiungere test unitari del catalogo, test di contratto API/RBAC, test del generatore e test frontend mirati; aggiornare OpenAPI e inventario test.
6. Ricostruire la copia Docker reale senza cache, verificare `/api/pronto`, usare browser reale su `127.0.0.1:8080` con click, scroll completo, desktop/tablet/mobile, hover e controllo visivo; poi commit, push gemello e deploy Hetzner sullo stesso commit.

## Progetto della vista

- Schermata: `Amministrazione → Prontezza prodotto`, raggiungibile dall'azione `Apri prontezza prodotto`.
- Utente: amministratore dello studio con `utenti.leggi`; nessun dato personale, PEC, certificato, token o dato di un altro tenant è incluso.
- Gerarchia: titolo e nota di verità; KPI dei 17 flussi; avvisi non promozionali; cards/righe P0 con stato, owner, ultima prova e prossimo passo; dettaglio con route/API/storage/permessi/test/dipendenze/limiti/rollback/incidenti.
- Stati: caricamento con `LoadingState`; errore controllato con messaggio italiano; assenza dati con `EmptyState`; permesso negato senza fallback simulato.
- Prestazioni: il catalogo è in memoria del processo e comprende solo 17 record; nessun I/O provider/SQL/ricorsivo avviene durante il rendering o l'API.

IMPECCABLE_PREFLIGHT: context=pass product=pass command_reference=not_required shape=not_required image_gate=skipped:nessuna risorsa grafica necessaria per registro operativo mutation=open.

## File previsti, rischi e collaudo

| Ambito | File previsti | Rischio | Contromisura |
| --- | --- | --- | --- |
| Modello | `pct/capability_truth_registry.py`, test dedicato | stato falsamente positivo | validazione degli stati e test che vieta la promozione senza prova corrente |
| API | `web/services/react_amministrazione_bridge.py`, `web/blueprints/api_v1_react.py`, OpenAPI | esposizione eccessiva o RBAC incoerente | payload globale privo di segreti, sessione + `utenti.leggi`, test 401/403/200 |
| UI | `frontend/src/amministrazioneData.ts`, `frontend/src/productReadinessData.ts`, `frontend/src/components/AmministrazionePage.tsx/.css` | layout lento o non responsivo | lazy page invariata, 17 record, layout CSS responsive e verifica reale |
| Artefatti | script generatore e documenti in `artifacts/product-readiness` | deriva tra UI e dossier | unica fonte Python, `--check` e test di generazione |

Non saranno toccati dati tenant, migrazioni SQLite/PostgreSQL, chiavi, credenziali, canali PEC, Local Signer, invii, provider esterni o la superficie SUPERADMIN. Qualunque modifica ai dati operativi appartiene alle fasi successive e richiederà il doppio controllo SQLite/PostgreSQL.

## Criteri di accettazione della Fase 1

1. Il catalogo contiene esattamente le 17 capability P0 e tutti i campi obbligatori.
2. UI, API, documentazione, matrice di release, changelog e azione menu provengono dallo stesso catalogo.
3. Nessuna capability senza prova corrente è etichettata come verificata o completa.
4. API e UI mantengono RBAC, tenant isolation, testo italiano/UTF-8 e date Europe/Rome.
5. Test mirati, typecheck, build e performance smoke passano senza regressioni.
6. La prova finale è effettuata nella copia Docker reale su `127.0.0.1:8080`, con click e risultati osservabili, prima del rilascio Hetzner.
