# PTT: Processo Tributario Telematico sul SIGIT, acquisizione per IUSENTRA

Sono state consultate solo pagine pubbliche, il 25/09/2026. Nell'area riservata non è stato fatto nessun accesso e nessun deposito.

## 1. Fonti ufficiali

- **Normativa**:
  - D.Lgs. 546/1992: art. 4 (competenza), art. 12 (valore della lite), art. 16-bis (tutto telematico, c. 3 come riformato dal D.Lgs. 220/2023), art. 18 (firma a pena di inammissibilità), art. 21 (60 giorni per il ricorso), art. 22 (costituzione entro 30 giorni dalla notifica del ricorso), art. 23 (controdeduzioni entro 60 giorni).
  - D.M. 23/12/2013 n. 163.
  - Decreto direttoriale 4/8/2015 (specifiche tecniche), modificato dai d.d. 28/11/2017 e 21/4/2023 (in vigore dal 15/5/2023: PAdES accanto a CAdES, formato EML, firma facoltativa sugli allegati).
  - Obbligo del PTT per i ricorsi notificati dal 1/7/2019 (art. 16 d.l. 119/2018).
  - Il Testo unico D.Lgs. 175/2024 si applica dal 1/1/2027.
- **Contributo unificato tributario (CUT)**: art. 13 c. 6-quater d.P.R. 115/2002 (scaglioni 30/60/120/250/500/1.500 €), aumento della metà ex c. 3-bis.
- **Documenti DGT archiviati** in `fonti_ufficiali/2026-09-25/`:
  - Istruzioni operative PTT maggio 2023 (Appendici A, B, C);
  - NIR delle CGT di primo e secondo grado (Tabella A natura giuridica, Tabella B atti impugnati, materie e tributi);
  - nota deposito sentenza notificata;
  - istruzioni della piattaforma incassi per il CUT.
- **Notizia DGT del 4/6/2026**: file fino a 50 MB, deposito fino a 100 MB, 50 file; aggiunta la voce «procura-nomina del difensore».
- **Sedi**: 103 Corti di primo grado e 36 di secondo grado (21 sedi principali e 15 sezioni staccate), con PEC e codice ufficio per l'F23 presi dalla pagina di ogni Corte su dgt.mef.gov.it. Sono in `pct/data/ptt/sedi_cgt.json`.
  - Province senza una Corte propria: BT va a Bari, FM ad Ascoli Piceno, MB a Milano.
- **Portale**:
  - area riservata `https://sigit.finanze.it/NIRWeb/login.jsp` (SPID, CIE, CNS o credenziali dopo la registrazione);
  - Telecontenzioso `https://sigit.finanze.it/Sigit/index.do`;
  - numero verde 800.051.052.
  - Il SIGIT non offre servizi per i gestionali (Circolare 1/DF 2019, §6.2).

## 2. Il flusso nel SIGIT

- **«Invio NIR – Ricorso – Altri Atti»**: ricorso, appello, controdeduzioni, altri atti processuali (Appendice C), nota di deposito documenti.
- **Schede della NIR web per il ricorso**: Dati generali, Ricorrenti, Rappresentanti, Difensori, Domicilio eletto, Parti resistenti, Atti impugnati (con materia, tributo, anno, valore), Documenti allegati (prima l'atto principale firmato), Contributo unificato, Validazione («Valida», dopo non più modificabile) e Trasmissione.
- **Ricevute**:
  - la ricevuta di trasmissione arriva a video e via PEC;
  - entro 24 ore arriva la PEC con l'esito e il numero RGR/RGA;
  - gli stati della NIR sono: Trasmessa, Depositata, Acquisita, con anomalia, Rigettata.
- **Regole sui file**:
  - **Atti**: PDF/A-1a o 1b nativo, firmato CAdES o PAdES.
  - **Allegati**: firma facoltativa. Formati ammessi: BMP, EML, XML, GIF, JPEG, XLS/XLSX, DOC/DOCX, ODT, PDF, PNG, TIFF. Si conservano a norma solo PDF/A, TIFF ed EML.
  - **Non ammessi**: ZIP.
  - **Nomi**: fino a 100 caratteri.
  - **Anomalie bloccanti dopo la trasmissione**: elementi attivi e collegamenti ipertestuali.

## 3. Come funziona in IUSENTRA (2.406.0)

- **Apertura del fascicolo tributario**, completa o «Fascicolo Veloce». Il pannello «Procedimento tributario (PTT)» chiede:
  - la Corte, proposta dall'ufficio indicato;
  - la posizione della parte;
  - atto impugnato, numero, ufficio, data di notifica e periodo;
  - il valore della lite, con il CUT mostrato subito;
  - la data di notifica del ricorso;
  - il numero di ruolo, se già iscritto;
  - la modalità di trattazione.

  Con il fascicolo veloce si apre la sezione PTT. La Corte vale come autorità giudiziaria e per l'ente impositore basta il nome.
- **Sezione «Deposito tributario (PTT)» del fascicolo**:
  - **Prepara il deposito**: le schede della NIR, nell'ordine del SIGIT e per ogni tipologia di deposito, con il pulsante «Copia». In testa ci sono i termini (art. 21, 22, 23) con «Aggiungi allo scadenziario», che non crea doppioni.
  - **Nota di iscrizione**:
    - Corte (con PEC e codice F23);
    - numero di ruolo, notifica del ricorso, trattazione, sospensione, prova testimoniale;
    - atto principale (Appendice A) o atto processuale (Appendice C);
    - sentenza impugnata per l'appello;
    - atti impugnati (Tabella B), con valore della lite, materia e tributo;
    - CUT calcolato per atto e sommato, con modalità di pagamento (F23 codice 171T e codice ufficio, pagoPA, contrassegno, prenotazione a debito).
  - **Documenti**:
    - ruolo (atto principale, allegato, non depositare);
    - tipologia dell'Appendice B proposta dal nome;
    - descrizione di 70 caratteri per «ALTRI DOCUMENTI»;
    - controlli al caricamento (firma dell'atto, formato, ZIP, nome, dimensione);
    - «Controlla i file come il SIGIT»: PDF/A, elementi attivi e collegamenti, letti con pypdf solo su richiesta;
    - limiti del deposito;
    - pacchetto zip in ordine, con un indice delle impronte SHA-256.
  - **Depositi**: si registrano stato della NIR, identificativo della ricevuta e RGR/RGA, anche per i depositi già fatti.
  - **Parti**:
    - ricorrente = cliente, con la natura della Tabella A letta dalla forma giuridica;
    - resistenti = controparti, con il tipo di ente dell'elenco SIGIT quando il nome lo dice senza ambiguità (l'agente della riscossione resta da scegliere).
- **Pagina /sigit**:
  - fascicoli tributari ordinati per termine in scadenza, con i dati mancanti e lo stato della NIR;
  - raggiungibilità dell'area riservata, verificata leggendo solo la pagina pubblica, con cache di 10 minuti;
  - collegamenti a Telecontenzioso, consultazione pubblica, registrazione e assistenza.
  - Sotto restano acquisizione e controlli del canale.
- **Fascicolo**: il riquadro «Servizi telematici» di un fascicolo tributario porta al PTT, a /sigit e al Telecontenzioso.
- **Correzione**: «tributario» contiene «tar». Nell'elenco e nel dettaglio dei fascicoli, nell'onboarding da preventivo e nell'import QuickOrganizer i fascicoli tributari risultavano amministrativi. Ora «tar» si riconosce solo come parola intera, e il tributario viene riconosciuto prima.
- **Codice**:
  - dominio in `pct/ptt_sigit/`;
  - servizi in `web/services/ptt_sigit_*.py`;
  - API in `/api/v1/ui/tributario`;
  - interfaccia in `frontend/src/components/pttSigit/`;
  - test in `tests/test_ptt_sigit.py` e `tests/test_ptt_sigit_api.py`.

## 4. Punti aperti

- Nessun decreto formalizza ancora i limiti di 50/100 MB del 4/6/2026: si applicano come li pubblica il DGT.
- Le ricevute PEC del PTT non vengono ancora lette in automatico. Stato e RGR si registrano a mano: serve un esempio reale di ricevuta e di esito.
- La sezione staccata di Livorno compare nell'elenco per regione ma non nella tabella delle sezioni staccate del DGT: va verificata.
