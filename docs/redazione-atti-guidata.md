# Redazione Atti guidata — dal fascicolo reale all'editor

Flusso completo della pagina `/redazione-atti`: l'avvocato parte dal cliente
reale, sceglie il fascicolo, riceve il tipo di atto suggerito, vede i campi
gia' compilati dai dati del gestionale e i campi mancanti, seleziona i
riferimenti normativi e genera l'atto direttamente nell'editor professionale
collegato al fascicolo. Nessun dato viene inventato: i campi assenti sono
evidenziati come `DATO MANCANTE` e mai riempiti con valori finti.

## Flusso utente

1. **Cliente** — elenco reale da `pct/clienti.py` con conteggio fascicoli attivi.
2. **Fascicolo** — solo i fascicoli del cliente selezionato (`GestioneFascicoli.tutti(id_cliente=...)`).
3. **Tipo atto** — quadro del contesto reale (ufficio, R.G., giudice, materia,
   oggetto, valore causa, contributo unificato, parti, allegati, condizioni) +
   suggerimenti motivati + catalogo completo per scelta manuale.
4. **Campi e normativa** — campi trovati (con fonte del prefill), campi
   mancanti compilabili a mano, riferimenti normativi selezionabili
   (processuali/sostanziali con motivazione).
5. **Genera** — validazione, controlli normativi (gate Cartabia/compliance
   esistenti), creazione documento nel fascicolo via
   `create_editor_draft` e apertura dell'editor Word-like
   (`/fascicoli/<id>/documenti/<id>/editor`) con salvataggio, versioni,
   export PDF/DOCX gia' disponibili.

## Moduli

| Modulo | Responsabilita' |
|---|---|
| `pct/redazione_contesto.py` | Estrazione del contesto reale di fascicolo/cliente/parti/studio con tracciabilita' fonte (`tabella`, `id`, `campo`), condizioni contestuali rilevate dai dati (mediazione, caparra, preliminare, ...), contributo unificato ex art. 13 D.P.R. 115/2002 dal valore causa, anteprima campi trovati/mancanti, marcatori `[DATO MANCANTE: ...]`. |
| `pct/redazione_suggerimenti.py` | Suggerimento del tipo atto: pratica collegata (`PRATICA_TO_MODELS`), parole chiave del fascicolo, coerenza materia (`TipoFascicolo` → aree compilatore), fase (R.G. presente = endoprocessuale). Ogni suggerimento espone i motivi in italiano. |
| `pct/redazione_normativa.py` | Registro riferimenti normativi articolo-per-articolo (fonte, articolo, rubrica, ambito processuale/sostanziale, motivo, URL Normattiva) collegati ai modelli del compilatore. Seed con basi consolidate (c.p.c., c.c., c.p.p., c.p.a., d.lgs. 28/2010, L. 392/1978, L. 604/1966, d.lgs. 546/1992, ...) + override di studio in JSON (upsert/disattivazione, mai distruttivo sui seed). I riferimenti condizionali entrano solo se la condizione risulta dal fascicolo. |
| `web/services/react_redazione_guidata_bridge.py` | Payload del wizard (clienti, fascicoli, contesto, anteprima) e preparazione della generazione (prefill + valori avvocato + validazione + marcatori). |
| `web/blueprints/api_v1_react.py` | Endpoint `/api/v1/ui/redazione-atti/*` (vedi sotto). |
| `frontend/src/features/documenti/RedazioneGuidataWizard.tsx` | Wizard React a 4 passi integrato in `RedazioneAttiPage.tsx`. |

## Endpoint

| Endpoint | Metodo | Funzione |
|---|---|---|
| `/api/v1/ui/redazione-atti/clienti` | GET | Clienti reali selezionabili |
| `/api/v1/ui/redazione-atti/clienti/<id>/fascicoli` | GET | Fascicoli del cliente |
| `/api/v1/ui/redazione-atti/fascicoli/<id>/contesto` | GET | Contesto + suggerimenti + catalogo |
| `/api/v1/ui/redazione-atti/anteprima/<model_code>` | GET | Campi trovati/mancanti + normativa |
| `/api/v1/ui/redazione-atti/genera` | POST | Validazione, compliance, creazione documento, URL editor |
| `/api/v1/ui/redazione-atti/normativa/<model_code>` | GET | Riferimenti per modello (con condizioni fascicolo) |
| `/api/v1/ui/redazione-atti/normativa` | POST | Upsert/disattiva/riattiva riferimento (manutenzione studio, audit) |

Tutti gli endpoint richiedono sessione utente (`_richiedi_auth`) e verificano
che il fascicolo appartenga al cliente dichiarato
(`verifica_fascicolo_del_cliente`). La generazione passa dai gate di
conformita' esistenti (`analyze_template_compliance` /
`enforce_generation_gate`) e dall'audit probatorio (`emit_act_generated`).

## Regole sui dati mancanti

- Campo obbligatorio vuoto e nessuna conferma → la generazione si ferma e
  restituisce `errors` + `campiMancanti` (`richiedeConfermaBozza: true`).
- Con conferma esplicita → bozza di lavoro con marcatore visibile
  `[DATO MANCANTE: <etichetta>]`, evidenziato nell'editor come
  `<mark class="iu-dato-mancante">`.
- Il contributo unificato senza valore causa resta «non determinabile»: mai
  stimato.

## Storage

- Override normativa studio: `REDAZIONE_NORMATIVA_DB`
  (default `./template_atti/riferimenti_normativi.json`).
- Documento generato: nel fascicolo (cifrato come gli altri documenti), con
  versioni, firma e export PDF/DOCX dell'editor esistente.

## Verifica manuale

1. Aprire `/redazione-atti` → il wizard «Nuova redazione» e' in cima.
2. Selezionare un cliente reale → compaiono solo i suoi fascicoli.
3. Selezionare il fascicolo → quadro dati reali (ufficio dal fascicolo, mai
   richiesto di nuovo) + suggerimenti motivati.
4. Scegliere l'atto suggerito (o dal catalogo) → campi compilati con fonte,
   mancanti evidenziati, riferimenti normativi spuntabili.
5. «Genera atto e apri editor» → l'editor Word-like si apre con il testo reale
   (niente `{{placeholder}}`), il documento e' nel fascicolo.
6. Test automatici: `python -m pytest tests/test_redazione_guidata.py -v`
   (incluso il percorso HTTP end-to-end `test_flusso_completo_http_dal_cliente_all_editor`).
