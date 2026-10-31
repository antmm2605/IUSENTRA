# Verifica sul campo di app.iusentra.it — 31/10/2026

Giro in **sola lettura** dell'applicazione in produzione (utente amministratore dello studio, nessun salvataggio,
conferma, deposito o invio), per vedere come lavora davvero sui fascicoli e correggere ciò che sbaglia.
Nessun dato dei clienti in questo documento: fascicoli indicati con l'identificativo interno.

Strumenti: browser senza interfaccia (Playwright) con la sessione dell'utente; lettura delle stesse API che
usano le pagine (`/api/v1/ui/...`). Campione: Panoramica, Fascicoli, Scadenziario, Agenda, Casella PEC,
Letture e verifiche, Notifiche legali e quattro fascicoli (916F1CAE, 9C089DF5, 58B19578, A8B49265).

## 1. Panoramica

| Visto | Cosa fa il software | Esito | Rimedio |
|---|---|---|---|
| «PEC da leggere: 833 — oggi» | conta le PEC della casella con il flag «non letta» | **fuorviante**: quasi tutte sono ricevute di accettazione/consegna ed esiti già presi in carico dal presidio (stato `already_presided`) | il riquadro diventa «PEC da esaminare» e conta solo le PEC non aperte e non ancora presidiate |
| Costruzione della pagina 3,7 s, di cui 2,0 s per la posta | lettura dell'intera casella a ogni costruzione | lenta | da ottimizzare (punto 6) |
| Azioni urgenti 6, fascicoli aperti 308, scadenze urgenti 11 | — | coerenti | — |

## 2. Letture e verifiche (motori di lettura)

| Visto | Cosa fa il software | Esito | Rimedio |
|---|---|---|---|
| Panoramica letture: «336 fascicoli fermi, 0 da leggere» | considera «fermo» un fascicolo quando il giro è chiuso | **falso**: solo 1.684 documenti su 12.404 sono letti con il motore corrente; 277 fascicoli sono fermi alla lettura del 17/09/2026 (motore v7) | la panoramica distingue «da aggiornare» (letto con regole superate) da «fermo» |
| Pagina del fascicolo: «29 documenti su 29 da leggere» | confronta con la versione corrente del motore | corretta, ma il ciclo non rilegge: per scelta, il cambio di motore non riavvia la lettura | **decisione dell'avvocato**: rilettura notturna graduale dai testi già estratti (nessun OCR, nessun file riaperto) |
| Fatti respinti dal collaudo: 40-60% dei fatti in tre fascicoli | collaudo automatico (calendario, ancoraggio, orizzonte) | da approfondire: molte date di documenti storici | — |

Conseguenza: i miglioramenti delle ultime settimane (natura documentale, precedenti giurisprudenziali, parti,
importi, ricevute del contributo, identità) non sono arrivati alla maggior parte dei fascicoli.

## 3. Scadenziario e agenda

| Visto | Cosa fa il software | Esito | Rimedio |
|---|---|---|---|
| Fascicolo 9C089DF5: tre voci per il termine 127-ter del 17/12/2026 | l'archivio consegna un fatto per ogni copia del provvedimento (allegato PEC e documento) | **doppioni** | le scadenze automatiche dello stesso giorno e dello stesso adempimento restano una voce; le voci manuali non si toccano |
| Fascicolo 58B19578: due «Termine del 07/03/2027» | idem | **doppione** | idem |
| Fascicolo 916F1CAE: udienza del 24/11 ore 09:30 due volte (documenti + PEC) | ogni fonte crea la propria voce d'agenda | **doppione** | regola unica dell'udienza equivalente (stesso fascicolo/RG, giorno, ora compatibile) |
| Fascicolo A8B49265: «Opposizione alla trattazione scritta», perentoria, al 14/04/2027 | rinomina qualsiasi voce il cui testo citi opposizione e trattazione scritta | **errore giuridico di presentazione**: è l'udienza sostituita dalle note; il termine di opposizione è di 5 giorni dalla comunicazione (art. 127-ter, comma 2, c.p.c.) | il titolo spetta solo al termine di opposizione, non all'udienza |

I doppioni già presenti nei dati restano finché non si riuniscono: serve un giro di riconciliazione (da fare).

## 4. Presidio notifiche

| Visto | Cosa fa il software | Esito | Rimedio |
|---|---|---|---|
| Sentenze dei Tribunali di Vicenza e Cosenza «da notificare» in fascicoli di Locri e Palmi | esclude i precedenti solo se la lettura ha registrato la natura «precedente giurisprudenziale» | **errore**: i fascicoli letti con il motore v7 non hanno quel fatto | un provvedimento di un altro ufficio (dal nome del file) è giurisprudenza prodotta |
| «Ricorso … (originale notificato)» proposto come da notificare | la prova di notifica non è stata letta (motore v7) | da verificare dopo la rilettura | rilettura (vedi §2) |

## 5. Catalogo dei documenti

**In produzione gira la versione 2.461.1**: le versioni 2.463-2.464 (catalogo dai 1.320 modelli, contributo
unificato solo con prova del pagamento, ricevute PEC riconosciute prima della seconda lettura) non sono state
distribuite perché il deploy del 29/10 si era fermato su un turno CI oltre il tempo.

| Visto (fascicolo A8B49265, causa di lavoro) | Con la versione attuale |
|---|---|
| «Ricorso.PDF», «Ricorso (originale notificato).pdf» → «Contributo unificato / pagamento» (95) | «Ricorso in materia di lavoro (art. 414 c.p.c.)» |
| PEC «DEPOSITO TELEMATICO: Ricorso …» → «Contributo unificato / pagamento» | «PEC di deposito telematico» |
| Ricevuta «ACCETTAZIONE: Notificazione L. 53/1994» → «Accettazione con beneficio d'inventario» (seconda lettura) | «Ricevuta PEC di accettazione» |
| Ricorso depositato → «Ricorso al TAR» (seconda lettura) | «Ricorso in materia di lavoro (art. 414 c.p.c.)» |
| Sentenze di altri uffici → «Sentenza» | precedente (dal contenuto e, ora, dal nome) |

Rimedio: il deploy unico; il cambio di versione del catalogo (v32) fa riclassificare i documenti.

## 6. Lettura del fascicolo e regia

| Visto | Esito | Rimedio |
|---|---|---|
| A8B49265: fase «chiusa — pratica definito» con prossima udienza il 14/04/2027 e nessuna incoerenza | **errore**: stato e udienza si contraddicono senza avviso | incoerenza dichiarata («verificare se la causa è pendente o se l'udienza va tolta»); testo «pratica definita» |
| Regia: «PROFILO_DA_CONFERMARE», completamento 0% | coerente con il profilo non confermato | — |
