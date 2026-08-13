# Antiriciclaggio avvocati — D.Lgs. 231/2007 e fonti CNF

Consultazione ufficiale eseguita il 13 agosto 2026. Questo documento salva le
regole usate dal software per l'adeguata verifica della clientela negli studi
legali. Non sostituisce la valutazione professionale dell'avvocato sul caso
concreto.

## Fonti ufficiali consultate

- `https://www.consiglionazionaleforense.it/web/cnf-news/-/644565`
  (Regole tecniche CNF ex art. 11 c.2 D.Lgs. 231/2007, approvate il 20/09/2019)
- `https://www.consiglionazionaleforense.it/documents/20182/644108/Criteri+e+metodologie.pdf`
  (CNF, «Criteri e metodologie di analisi e valutazione del rischio», ex artt.
  15 cc. 1-2, 19 c.2 e 23 c.3 — copia versionata in
  `fonti_ufficiali/2026-08-13/CNF_Criteri_metodologie_antiriciclaggio_adeguata_verifica.pdf`)

## Regole accertate dal D.Lgs. 231/2007

- **Ambito per gli avvocati (art. 3 c.4 lett. c)**: obblighi quando si compiono
  in nome o per conto del cliente operazioni finanziarie o immobiliari, o si
  assiste nella progettazione/realizzazione di: trasferimento di diritti reali
  su immobili o attività economiche; gestione di denaro, strumenti finanziari o
  beni; apertura/gestione di conti bancari, libretti o conti titoli;
  organizzazione degli apporti per costituire/gestire/amministrare società;
  costituzione/gestione/amministrazione di società, enti, trust o soggetti
  giuridici analoghi.
- **Esclusione difensiva (art. 17 c.7)**: niente obblighi per le informazioni
  ricevute nell'esame della posizione giuridica o nella difesa/rappresentanza
  in giudizio, incluse le consulenze su come promuovere o evitare un
  procedimento.
- **Contenuto dell'adeguata verifica (art. 18)**: identificazione cliente ed
  eventuale esecutore; identificazione del titolare effettivo; scopo e natura
  del rapporto; controllo costante nel corso del rapporto.
- **Titolare effettivo (art. 20)**: proprietà diretta o indiretta > 25% del
  capitale; in mancanza, controllo dei voti/influenza dominante; in ultima
  istanza, poteri di rappresentanza legale, amministrazione o direzione.
- **Verifica semplificata (art. 23)** in presenza di basso rischio; **verifica
  rafforzata (artt. 24-25)** in presenza di rischio elevato: clienti PEP
  (art. 1 c.2 lett. dd), paesi terzi ad alto rischio, ecc.
- **Conservazione (artt. 31-32)**: documenti, dati e informazioni conservati
  per **10 anni** dalla cessazione del rapporto o dall'esecuzione
  dell'operazione.
- **Astensione (art. 42)** quando l'adeguata verifica non è possibile.

## Metodologia CNF («Criteri e metodologie», 2019)

Il documento CNF propone un **modello esemplificativo** (non vincolante nei
valori) di profilatura del rischio:

- indici di rischio raggruppati in **3 macro-aree**: (1) cliente — identità,
  titolare effettivo, PEP, precedenti, collaborazione; (2) tipologia di
  servizi/operazioni e metodi di pagamento; (3) area geografica — paesi a
  sanzioni/embarghi, presidi antiriciclaggio, corruzione;
- **punteggio da 1 a 5** per ciascun indice (1 = rischio pressoché inesistente,
  2 = basso, 3 = medio/moderato, 4 = moderato/alto, 5 = elevato e palese);
- somma dei punteggi per macro-area e **totale complessivo** → basso rischio →
  verifica **semplificata**; rischio elevato → verifica **rafforzata**;
- ogni studio definisce la propria procedura di profilatura («imporre un
  modello predefinito risulterebbe improprio»): le soglie numeriche NON sono
  fissate dal CNF.
- soggetti storicamente a basso rischio (banche, Poste, SIM, SGR, SICAV,
  assicurazioni ramo vita, fiduciarie ex art. 199 c.2 TUF, PA…) restano tali
  salvo fattori concreti di alto rischio.

## Implementazione IUSENTRA

`pct/antiriciclaggio.py`:

- catalogo prestazioni **in ambito** art. 3 c.4 lett. c con esclusione
  dell'attività difensiva pura (art. 17 c.7): la scheda dichiara sempre se la
  prestazione rientra o meno negli obblighi;
- griglia di profilatura con le 3 macro-aree CNF e punteggi 1-5 per indice;
- classificazione del rischio con **soglie di default dichiarate come prassi
  configurabile dello studio** (non come norma): la decisione finale sul
  livello di verifica resta all'avvocato, che può motivare uno scostamento;
- scadenza del controllo costante proposta in base al livello (prassi
  configurabile); conservazione decennale calcolata ex art. 31;
- persistenza JSON tenant-aware, eventi audit.

Il software non esegue segnalazioni UIF (art. 35): registra la valutazione e
ricorda l'obbligo quando il rischio è elevato.
