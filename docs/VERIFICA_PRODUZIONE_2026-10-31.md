# Registro delle correzioni dalla verifica sul campo — app.iusentra.it, 31/10/2026

Giro in **sola lettura** dell'applicazione in produzione (utente amministratore dello studio, nessun salvataggio,
conferma, deposito o invio), per vedere come lavora davvero sui fascicoli e correggere ciò che sbaglia.
Nessun dato dei clienti: i fascicoli sono indicati con l'identificativo interno.

Strumenti: browser senza interfaccia (Playwright) con la sessione dell'utente e lettura delle stesse API delle
pagine (`/api/v1/ui/...`). Campione: Panoramica, Fascicoli, Scadenziario, Agenda, Casella PEC, Letture e
verifiche, Notifiche legali, fascicoli 916F1CAE, 9C089DF5, 58B19578, A8B49265.

**Versione in produzione al momento della verifica: 2.461.1.** Le versioni 2.463-2.464 non erano state
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
