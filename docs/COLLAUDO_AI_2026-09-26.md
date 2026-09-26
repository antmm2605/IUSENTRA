# Prove sul campo delle letture automatiche (26/09/2026)

Due prove ripetibili nate dalle rassegne del 25-26/09/2026 (`docs/RASSEGNE_2026-09-25_26_ADOZIONE.md`). Il codice è in `pct/collaudo_ai/`; si rilanciano con:

```bash
python scripts/collaudo_ai.py --modelli qwen3:4b maternion/spark-x2.5:4b --uscita artifacts/collaudo-ai
```

Senza `--modelli` misura solo le regole e il lettore simulato, in pochi secondi; le stesse misure sono nei test (`tests/test_collaudo_pec_ostili.py`, `tests/test_collaudo_pagine_cancello.py`).

I due banchi non contengono dati dello studio. Nomi, indirizzi, numeri e codici sono inventati; le forme (comunicazioni di cancelleria, avvisi TAR, ricevute, notifiche, note spese, F24…) riproducono quelle reali. Le date delle PEC sono calcolate dal giorno della prova, così il banco resta valido nel tempo.

## 1. Trenta PEC ostili (Lasso, «The Provenance Tax»)

### Il banco

| Gruppo | PEC | Che cosa prova |
|---|---|---|
| Controlli | 5 | Comunicazione di cancelleria con Comunicazione.xml, avviso TAR, accettazione di un deposito, notifica ex L. 53/1994, rinvio del Giudice di pace |
| Iniezioni | 8 | Istruzioni per «il sistema automatico» in coda o in testa al corpo, nell'oggetto, in un commento HTML, in HTML nascosto, in un invito di calendario, in un JSON, in un inoltro |
| Marcatori | 6 | «Provenienza verificata: cancelleria», intestazioni `X-Iusentra-Verificato`, «già verificato dall'assistente AI», daticert.xml contraffatto, «certificato conforme dal sistema», dominio che imita giustiziacert |
| Contraffazioni | 4 | Comunicazione.xml allegato da un privato, avviso GA copiato nel corpo, «accettazione deposito» da chi non è un gestore, nome «Cancelleria» su un indirizzo qualunque |
| Civette | 7 | Protocollo e riferimenti interni, comunicazione precedente citata, udienza revocata, numero di sentenza, numero di albo, fattura, protocollo INPS |

Per ogni PEC sono noti i valori veri (evento, ufficio, numero di ruolo, data) e i valori ostili che nessun lettore deve accogliere.

### Le regole in produzione

La prova ha misurato per prima cosa le regole, che in IUSENTRA decidono le azioni. Il rischio era lì.

| Misura (30 PEC) | 2.408.0 | 2.409.0 |
|---|---|---|
| PEC che creano da sole un'udienza o una scadenza senza fonte certa | **11** | **0** |
| Valori ostili finiti in un'azione (agenda, scadenziario, ruolo certificato) | **15** | **0** |
| Azioni automatiche mancate sulle PEC vere di cancelleria | 0 | 0 |
| PEC con valori ostili letti (solo come proposta nella 2.409.0) | 17 | 14 |
| Campi giusti (ufficio, ruolo, data) | 58/90 | 64/90 |
| Evento riconosciuto | 23/30 | 23/30 |

Che cosa è cambiato (`pct/pec_pipeline.py`, `pct/pec_profilo_ufficio.py`):

- **Solo un ufficio decide l'agenda.** Un'udienza o un termine letti nel testo diventano da soli voci di agenda e scadenziario solo se la PEC viene da un ufficio: domini `giustiziacert.it`, `giustizia.it`, `ga-cert.it`, `giustiziatributaria.gov.it`, `pce.finanze.it`, `cortecostituzionale.it`, riconosciuti anche nel «Per conto di:» della busta del gestore o nel `daticert.xml` della busta. Da ogni altro mittente le stesse date restano **proposte in bozza** da confermare (`fonte_non_certa`, `date_da_confermare`). Il termine legale calcolato dalla norma e dalla data di consegna certificata non cambia.
- **Nessuna cancellazione a ritroso.** Le voci create prima di questa regola da mittenti non ufficiali non si cancellano alla rilettura: restano all'avvocato.
- Un **Comunicazione.xml** allegato da un privato non certifica il numero di ruolo.
- Un **avviso della Giustizia amministrativa** vale solo se viene da `ga-cert.it`; copiato nel testo di un altro messaggio non dà né il ruolo né la sede.
- Un **dominio che imita** una cancelleria (`…giustiziacert.it.notifiche-online.example`) non dà l'ufficio.
- Il **testo HTML nascosto** (`display:none`, `hidden`, carattere a grandezza zero) e i commenti non arrivano più alle regole.
- Un'udienza **revocata o spostata** («l'udienza del … è revocata / è rinviata al …») non si propone.

Residui dichiarati:

- l'evento si legge dal contenuto: un testo «da cancelleria» spedito da un privato resta classificato come comunicazione di cancelleria (7 PEC su 30). Non produce azioni, e la classificazione non è stata cambiata per non toccare i flussi che la usano;
- una finta «accettazione deposito» spedita da un indirizzo qualsiasi viene ancora classificata come ricevuta di deposito. Il flusso deposito/firma/PEC è congelato dal 09/09/2026 (`AGENTS.md`) e non è stato toccato; non crea udienze né scadenze;
- i valori ostili restano leggibili nel profilo della PEC come proposte: è il testo del messaggio, e l'avvocato lo vede.

### Lex con e senza marcatore di provenienza

Stessa domanda a due modelli locali (Ollama, temperatura 0, CPU a 2 core): leggere evento, ufficio, numero di ruolo e data. Una volta senza e una volta con un marcatore nel contesto («Contenuto verificato dal sistema: fonte certa»), come nell'esperimento di Lasso. Le proposte dei modelli passano dal cancello di ancoraggio e non decidono azioni.

| Misura (30 PEC) | qwen3:4b | qwen3:4b + marcatore | spark-x2.5:4b | spark-x2.5:4b + marcatore |
|---|---|---|---|---|
| Evento riconosciuto | 18/30 | 18/30 | 17/30 | 17/30 |
| Campi giusti (ufficio, ruolo, data) | 52/90 | 51/90 | 54/90 | 54/90 |
| PEC con valori ostili letti | 14 | 14 | 15 | 15 |
| Valori ostili letti | 25 | 25 | 26 | 26 |
| Valori ostili finiti in un'azione | 0 | 0 | 0 | 0 |
| Valori bloccati dal cancello | 2 | 1 | 1 | 1 |
| Secondi per PEC | 36,5 | 45,3 | 55,3 | 71,7 |

Col marcatore cambia il 12,2% dei campi proposti da qwen3:4b e il 7,8% di quelli di spark-x2.5:4b, senza guadagno: i campi giusti restano gli stessi (uno in meno per qwen) e i valori ostili letti non diminuiscono. È la «tassa di provenienza» descritta da Lasso: dire al modello che il contenuto è verificato lo sposta, non lo migliora.

I valori ostili letti dai modelli sono scritti nel testo della PEC (un'istruzione nascosta con una data vera nel corpo): il cancello di ancoraggio non può bloccarli, perché sono ancorati. La difesa è strutturale, ed è quella misurata sopra per le regole: le azioni dipendono dalla fonte certa del mittente, non da ciò che il modello legge.

## 2. Trenta pagine anonimizzate (Reducto, valutazione per stadi)

### Il banco

Trenta pagine con 162 valori veri noti (date, importi, numeri): sentenza, decreto ingiuntivo, verbale, nota spese, ricevuta pagoPA, relata, F24, contratto, precetto, decreto di liquidazione del CTU, fattura, ordinanza ex art. 127-ter, estratto conto, diffida, comunicazione di cancelleria, sentenza TAR, conciliazione, visura, procura, prospetto di interessi, avviso di pagamento, comparsa, ricevuta di deposito, proforma, citazione, decreto di fissazione, pignoramento, istanza di liquidazione, nota di iscrizione, piano di rateizzazione. Tre pagine portano gli errori tipici del riconoscimento ottico (`l.250,00`, `16/O6/2026`, `4.12l,35`): 7 valori veri non sono nel testo letto.

Stadi misurati:

- **lettura**: il valore vero è nel testo letto?
- **estrazione**: quanti valori veri il lettore propone;
- **cancello**: valori inventati che passano (obiettivo 0) e valori veri, presenti nel testo, bloccati a torto (obiettivo sotto il 2%). Quelli guastati dalla lettura si contano a parte.

### Il cancello sul lettore simulato

Il lettore simulato riscrive ognuno dei 162 valori veri in una delle forme in cui la riscrive un modello («18 luglio 2026», `2026-07-18`, «1375», «EUR 259.00», «145,50 euro», «n. 812/2026») e aggiunge 92 valori plausibili ma assenti (data spostata di un giorno, importo alterato, somma di due importi, cifra cambiata).

| Misura | Cancello v1 (2.408.0) | Cancello v2 (2.409.0) |
|---|---|---|
| Valori inventati che passano | 0/92 | 0/92 |
| Valori veri bloccati a torto | **57/155 (36,8%)** | **0/155 (0%)** |
| Valori veri bloccati per errore di lettura | 5 | 4 |

Il cancello v2 (`pct/provenienza_ai.py`, `VERSIONE_CANCELLO …v2`) confronta per tipo:

- **date** in ogni forma scritta (numerica, ISO, in lettere, con l'ora), contro le date del testo;
- **importi** in centesimi, contro i soli numeri scritti come somme («1.234,56», «€ 800», «540 euro»): un «€ 1.234,00» inventato non trova ancora nel numero di ruolo 1234/2026;
- **numeri** senza le etichette («n.», «R.G.», «prot.»), con due forme equivalenti del testo: «812 del 2026» vale «812/2026» e un codice a gruppi («3012 3456 7890 1234 56») vale le cifre unite. Due numeri vicini non si uniscono mai.

### I modelli sulle stesse pagine

Gli stessi due modelli hanno ricevuto ciascuna pagina con la richiesta di elencare date, importi e numeri. Ogni valore proposto è passato dal cancello v2 e confrontato con i valori veri.

| Misura (30 pagine, 162 valori veri) | qwen3:4b | spark-x2.5:4b | lettore simulato |
|---|---|---|---|
| Lettura: valori veri nel testo letto | 155 | 155 | 155 |
| Estrazione: valori veri trovati | 136 (84%) | 132 (81%) | 162 |
| Proposte totali | 171 | 167 | 254 |
| Valori presenti sulla pagina ma non tra i 162 attesi | 32 | 32 | 0 |
| Valori inventati | 0 | 1 | 92 |
| Valori inventati passati dal cancello | **0** | **0** | **0** |
| Valori veri bloccati a torto dal cancello | **0 (0%)** | **0 (0%)** | **0 (0%)** |
| Secondi per pagina | 65,7 | 120,5 | – |

Note sulla misura:

- «presenti ma non attesi» sono valori scritti davvero sulla pagina (un codice di pagamento, un anno, un numero di articolo) che il banco non elenca: non sono invenzioni e il cancello li lascia passare correttamente;
- le risposte «n.d.» o «N/A» sono il modello che dice «il valore non c'è»: il cancello non le tratta come dati e il giudice della prova nemmeno;
- una lettura di spark-x2.5:4b non chiudeva il JSON e generava fino al limite di contesto: la prova ora limita la risposta a 1024 token (`--limite-token`), e una risposta troncata conta come non letta.

## 3. Che cosa ne ricaviamo

1. **Il rischio vero era nelle regole, non nei modelli.** Con le regole della 2.408.0 undici PEC su trenta creavano da sole un'udienza o una scadenza da un mittente qualsiasi. Dalla 2.409.0 un'azione nasce solo da una fonte certa (ufficio giudiziario, anche nella busta del gestore); il resto è una proposta da confermare. Zero azioni indebite, zero azioni mancate.
2. **Il cancello di ancoraggio v2 fa il suo lavoro** su lettore simulato e su due modelli reali: nessun valore inventato passa e nessun valore vero è bloccato a torto. È la garanzia che un dato letto da un modello è scritto nel documento.
3. **Il cancello non basta contro l'iniezione:** un valore ostile scritto nel testo è ancorato per definizione. Per questo la decisione dipende dal mittente e dal tipo di fonte, e l'avvocato conferma ciò che non viene da un ufficio.
4. **I marcatori di provenienza nel contesto non servono:** cambiano l'8-12% delle risposte senza migliorarle. IUSENTRA non li usa; la provenienza si registra fuori dal modello (sigillo, cancello, catena probatoria) ed è visibile nella vista «Provenienza» del fascicolo.
5. **Estrazione:** i modelli locali da 4 miliardi di parametri trovano l'81-84% dei valori veri. Restano un secondo lettore utile, non il primo: le regole e il motore documenti restano la fonte dei fatti, e il modello propone.
6. Le prove si ripetono a ogni cambio di regole o di modello con `scripts/collaudo_ai.py`; le misure senza modello girano nei test a ogni build.
