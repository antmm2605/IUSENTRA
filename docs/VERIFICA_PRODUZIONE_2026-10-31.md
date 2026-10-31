# Registro delle correzioni dalla verifica sul campo — app.iusentra.it, 31/10/2026

Giro in **sola lettura** dell'applicazione in produzione (utente amministratore dello studio, nessun salvataggio,
conferma, deposito o invio), per vedere come lavora davvero sui fascicoli e correggere ciò che sbaglia.
Nessun dato dei clienti: i fascicoli sono indicati con l'identificativo interno.

Strumenti: browser senza interfaccia (Playwright) con la sessione dell'utente e lettura delle stesse API delle
pagine (`/api/v1/ui/...`). Campione: Panoramica, Fascicoli, Scadenziario, Agenda, Casella PEC, Letture e
verifiche, Notifiche legali, fascicoli 916F1CAE, 9C089DF5, 58B19578, A8B49265.

**Versione in produzione al momento della verifica: 2.461.1.** Giro completo del pomeriggio (V18-V29): 94 pagine React su computer e telefono, 8 schede di fascicolo con tutte le schede interne, 40 PEC di sentenza lette alla fonte; solo lettura, scritture bloccate dal browser di prova. Le versioni 2.463-2.464 non erano state
distribuite (deploy del 29/10 fermo su un turno CI oltre il tempo).

## Registro dei punti

Stati: **corretto** = correzione fatta e provata con un test che riproduce il caso; **da verificare in
produzione** = da ricontrollare su app.iusentra.it dopo il deploy; **da fare** = non ancora corretto.

| N. | Problema visto in produzione | Correzione | Prova reale (test) | Stato |
|---|---|---|---|---|
| V1 | «PEC da leggere: 833 — oggi»: quasi tutte ricevute ed esiti già presidiati | il riquadro conta solo le PEC non aperte e non ancora prese in carico («PEC da esaminare») | `tests/test_dashboard_pec_da_esaminare.py` | corretto · da verificare in produzione |
| V2 | Panoramica letture «336 fermi, 0 da leggere» mentre solo 1.684 documenti su 12.404 sono letti dal motore corrente | stato «da aggiornare» per i fascicoli letti con un motore superato | `tests/test_letture_panoramica.py::test_un_fascicolo_letto_con_regole_superate_non_e_fermo` | corretto · da verificare in produzione |
| V3 | 277 fascicoli fermi alla lettura del 17/09/2026: le regole nuove non arrivano ai documenti già letti | rilettura notturna graduale (00-06, 2 fascicoli ogni 10 minuti) dai soli testi salvati, decisioni dell'avvocato conservate | `tests/test_rilettura_notturna_catena.py` (catena completa con PDF veri, 8,5 s), `tests/test_riletture_graduali.py`, `tests/test_archivio_letture_runtime.py::test_rilettura_superati_dai_testi_salvati_senza_riaprire_file` | corretto · da verificare in produzione (contatore «da aggiornare» che scende ogni notte) |
| V4 | 9C089DF5: tre voci per il termine 127-ter del 17/12/2026; 58B19578: due «Termine del 07/03/2027» | le scadenze automatiche dello stesso giorno e adempimento restano una voce (anche da copie diverse del provvedimento) | `tests/test_agenda_eventi_equivalenti.py::test_stesso_termine_da_due_copie_del_provvedimento_resta_una_scadenza`; nessun doppione nella prova V3 | corretto · da verificare in produzione |
| V5 | 916F1CAE: udienza del 24/11 ore 09:30 due volte (documenti + PEC) | regola unica dell'udienza equivalente in PEC, archivio, conferma proposte, PDP | `tests/test_agenda_eventi_equivalenti.py` | corretto · da verificare in produzione |
| V6 | Doppioni già presenti nei dati (V4, V5) | giro periodico che annulla con nota «Riunita a …» i soli doppioni automatici aperti (scadenze stesso giorno e adempimento, udienze stesso giorno e ora compatibile), conserva la voce più precisa e sposta i collegamenti; manuali e assegnate non si toccano (`pct/riunione_doppioni.py`) | `tests/test_riunione_doppioni.py` (casi di produzione: triplo 127-ter, doppio 07/03, udienza PEC+documenti) | corretto · da verificare in produzione |
| V7 | A8B49265: udienza in trattazione scritta intitolata «Opposizione alla trattazione scritta» e perentoria | il titolo spetta solo al termine di 5 giorni dalla comunicazione (art. 127-ter, comma 2, c.p.c.) | test esistenti dello scadenziario e dell'agenda | corretto · da verificare in produzione |
| V8 | Sentenze di Vicenza e Cosenza «da notificare» in fascicoli di Locri e Palmi | provvedimento di altro ufficio (dal nome del file) = precedente giurisprudenziale | `tests/test_agenda_eventi_equivalenti.py::test_sentenza_di_altro_ufficio_dal_nome_e_un_precedente`; prova V3 | corretto · da verificare in produzione |
| V9 | Ricorso e PEC di deposito classificati «Contributo unificato / pagamento»; ricevuta PEC come «Accettazione con beneficio d'inventario»; ricorso di lavoro come «Ricorso al TAR» | già corretto nelle versioni 2.463-2.464 non distribuite; versione del catalogo v32 per riclassificare | casi riprodotti con il risolutore attuale (esiti corretti) | corretto · **richiede il deploy** |
| V10 | A8B49265: fase «chiusa» con udienza futura il 14/04/2027, nessuna incoerenza | incoerenza dichiarata; testo «pratica definita» | `tests/test_fascicolo_lettura.py::test_fascicolo_chiuso_con_udienza_futura_e_incoerente` | corretto · da verificare in produzione |
| V11 | «Ricorso (originale notificato)» proposto come da notificare | dipende dalla rilettura (V3): la prova di notifica non era stata letta dal motore v7 | — | da verificare dopo V3 |
| V12 | Panoramica costruita in 3,7 s, di cui 2,0 s per la posta | — | — | **da fare** (punto 6 del piano) |
| V13 | 40-60% dei fatti respinti dal collaudo in tre fascicoli | — | — | **da analizzare** |
| V15 | A8B49265: liquidazione delle spese presa dalla sentenza di Vicenza (precedente) | regola unica dei precedenti (fatto letto o nome del file con altro ufficio) per notifiche, economia della sentenza e importi | `tests/test_rilettura_notturna_catena.py::test_precedente_di_altro_ufficio_fuori_da_notifiche_ed_economia` | corretto · da verificare in produzione |
| V16 | A8B49265: contributo «da registrare» con la ricevuta telematica nel fascicolo | per la ricevuta telematica XML senza ruolo né ufficio in contrasto, RG e ufficio si riscontrano se compaiono cliente o codice fiscale (`identita_ricevuta_prima_del_ruolo`); il riuso dello IUV resta segnalato | `tests/test_ricevuta_prima_del_ruolo.py` | corretto · da verificare in produzione (dopo la rilettura del fascicolo) |
| V14 | Versione in produzione 2.461.1 | deploy unico con tutti i controlli verdi | gate locale e CI | **da fare** |
| V17 | Lavoro presente solo sul PC dell'avvocato (copie WSL non pubblicate) | inventario in sola lettura dal PC; recuperati documenti «Codici e leggi», nota 2.458.1 e copia `openga-validazione` 2.461.2 (fusione a tre vie, impronta dell'archivio verificata); il resto era già in main in versione più recente | 144 test della copia passati dopo la fusione; gate locale | corretto · **richiede il deploy** |
| V18 | Deploy bloccato dal 29/10: la rimisura della copertura della versione accettata (2.461.1) supera 5 minuti nella parte 6; CodeQL segnala un'espressione regolare quadratica sul mittente | baseline con 10 minuti (la candidata resta a 5); scansione lineare dell'indirizzo | `tests/test_notifiche_ricevute.py::test_indirizzo_del_mittente_lineare_anche_su_intestazioni_costruite_ad_arte` | corretto · richiede il deploy (2.466.1) |
| V19 | Notifiche legali: 18 s per aprire l'elenco, che riallineava 50 presìdi dello studio a ogni consultazione | l'elenco è una sola lettura; il riallineamento avviene quando nel fascicolo entra un documento o una PEC, solo per i suoi presìdi (a evento, non a orario: indicazione dell'avvocato) | `tests/test_notification_presidia_reconcile_runtime.py` | corretto · richiede il deploy (2.467.0) |
| V20 | 31 proposte «Impugnazione sentenza - termine lungo» su 40 calcolate dalla ricezione della PEC (la comunicazione non fa decorrere il termine); il lettore delle date prendeva i precedenti citati nella sentenza allegata | per sentenze ed estinzioni: data dell'evento del registro, testo della comunicazione o timbro della sentenza con lo stesso numero; mai la ricezione, mai un precedente citato | `tests/test_pec_change_receipt.py`, `tests/test_termine_lungo_sentenza.py` (casi dalle PEC reali) | corretto · richiede il deploy (2.467.0): ordine delle fonti certe = data evento del registro → sentenza nel fascicolo telematico (PST) → testo della comunicazione → timbro della sentenza con lo stesso numero; senza fonte certa decide l'avvocato (avviso «data di deposito non certa»), e la bozza si corregge da sola quando arriva la copia dal portale (`tests/test_riconvalida_termine_lungo.py`). Simulazione sulle 40 bozze reali: 2 corrette (scadenza tardiva di un giorno: RG 806/2026 e 537/2026), 3 confermate, 35 da giudicare |
| V21 | Scheda fascicolo: circa 25 chiamate all'apertura (una per scheda, anche non aperta): lettura 10,4 s, documenti 7,6 s, provenienza AI 5,9 s; cambio scheda 2-9 s | — | — | **da fare**: caricare ogni scheda quando viene aperta |
| V22 | Controllo delle modifiche (`sync/revisions`) ogni 2 s anche con la pagina in secondo piano | — | — | **da fare**: sospendere quando la scheda del browser non è visibile |
| V23 | Pagine lente: Ricerca legale 8,4 s, Servizi telematici 7,5 s, Template atti 6,8 s, Database 8,9 s | — | — | **da analizzare** |
| V24 | Scadenziario: 658 KB a ogni apertura, di cui 335 KB di calcolatore e 63 KB di guardiano | — | — | **da fare**: calcolatore e guardiano su richiesta |
| V25 | Dati tecnici mostrati all'avvocato: JSON grezzo (Audit, Registro attività), dizionario Python (Ricerca legale), date ISO «2026-10-31T14:43:41Z» (Template atti, Redazione atti, Giurisprudenza, Tribunali) | — | — | **da fare** |
| V26 | Testi in inglese («Failed to fetch», «Mirror: OK», «Calendar Sync», «Open Data») e accenti mancanti («gia», «piu») in circa 50 testi | — | — | **da fare** |
| V27 | Telefono: campi di ricerca alti 25 px e caselle di spunta 13-18 px; nella lista fascicoli il pulsante copre la terza scadenza e la barra in basso taglia «Ricerca» | — | — | **da fare** |
| V28 | Scadenze passate ancora aperte (10 «scadute da chiudere», es. deposito note 127-ter del 06/10) e conteggio diverso tra Fascicoli (9) e Scadenziario (10) | — | — | **da analizzare**: chiusura automatica quando il deposito risulta dai documenti |
| V29 | La Panoramica, a ogni apertura, avvia l'aggiornamento delle notizie (POST) | — | — | **da analizzare** |
| V30 | In 6 presìdi di notifica su 6 la sentenza o il decreto arrivati con la PEC di cancelleria non erano nel fascicolo: letture, obblighi di notifica ed economia lavoravano su precedenti importati | il PDF del giudice (anche dentro lo zip) entra nel fascicolo come **copia informativa** (fonte PEC_CANCELLERIA, impronta SHA-256, una sola volta) e avvia la lettura; la copia da notificare resta quella scaricata dal Portale dei Servizi Telematici | `tests/test_pec_change_receipt.py::test_il_provvedimento_della_comunicazione_entra_nel_fascicolo_una_volta` | corretto · richiede il deploy (2.467.0) |
| V31 | RG 538/2026: appuntamenti del 2023-2024 in un fascicolo con ruolo del 2026 | — | — | **da analizzare** (collegamento errato di eventi d'agenda) |
| V32 | Scadenze procedurali superate dalla sentenza restano aperte (RG 2848/2026: note del 09/10, sentenza del 12/10) | — | — | **da fare**: proporre all'avvocato la chiusura «superata dalla sentenza del …» (non chiudere da soli: conta se l'adempimento è stato fatto) |
| V33 | Decreto con ordine di notificazione riconosciuto (RG 1084/2026) ma nessuna scadenza della notifica proposta | — | — | **da fare**: termine dal testo del decreto (fonte certa) o di legge (es. art. 415 c.p.c. nel rito del lavoro), altrimenti decide l'avvocato |
| V34 | Promemoria vecchi in agenda («Classifica PEC e conferma adempimenti» del 2024-2025) | — | — | **da analizzare** |
| V35 | Modello di catalogazione: Qwen addestrato 86% sui 271 disaccordi (regole 13%), 95% in verifica (regole 100%); 37 risposte illeggibili; Qwen di partenza misurato allo 0% per un difetto di lettura della voce; Spark non ancora misurato; addestramento su etichette superate | lettura tollerante della voce, risposte integrali salvate; misure di partenza di Qwen e Spark in corso sul PC; nuovo addestramento di **entrambi** sul pacchetto rifatto con il catalogo aggiornato (vedi `tools/addestramento_catalogo/LEGGIMI.md`, sezione 9) | `tests/test_addestramento_catalogo.py` | **in corso** · il modello non si adotta finché non batte le regole sui casi decisi dall'avvocato |

## Dettaglio delle osservazioni

### Panoramica
Azioni urgenti 6, fascicoli aperti 308, scadenze urgenti 11: coerenti. Casella PEC: 2.049 messaggi, 970 in
arrivo, 833 non aperti, 471 collegati in automatico ai fascicoli.

### Letture e verifiche
La pagina del singolo fascicolo dice correttamente «29 documenti su 29 da leggere» (confronto con la versione
corrente); la panoramica li diceva fermi. Per scelta progettuale il cambio di motore non riavviava la lettura:
ora la rilettura avviene di notte, a piccoli gruppi.

### Catalogo (fascicolo A8B49265, causa di lavoro)

| In produzione (2.461.1) | Con la versione attuale |
|---|---|
| «Ricorso.PDF», «Ricorso (originale notificato).pdf» → «Contributo unificato / pagamento» (95) | «Ricorso in materia di lavoro (art. 414 c.p.c.)» |
| PEC «DEPOSITO TELEMATICO: Ricorso …» → «Contributo unificato / pagamento» | «PEC di deposito telematico» |
| Ricevuta «ACCETTAZIONE: Notificazione L. 53/1994» → «Accettazione con beneficio d'inventario» | «Ricevuta PEC di accettazione» |
| Ricorso depositato → «Ricorso al TAR» | «Ricorso in materia di lavoro (art. 414 c.p.c.)» |
| Sentenze di altri uffici → «Sentenza» | precedente giurisprudenziale |

### Regia
«PROFILO_DA_CONFERMARE», completamento 0%: coerente con il profilo non confermato.
