# PAT: Formweb del Portale dell'Avvocato (nuovo SIGA): acquisizione per IUSENTRA

Consultazione in sola lettura del 25/09/2026, con la sessione dell'avvocato. Nessun deposito salvato, generato o inviato; nessun file caricato; nessun fascicolo di cliente aperto.

## 1. Base normativa e fonti

- Art. 136 c.p.a. (d.lgs. 104/2010) e d.P.C.M. 16/02/2016 n. 40: regole tecniche del processo amministrativo telematico.
- Regole tecnico-operative d.P.C.S. 2025, archiviate in `fonti_ufficiali/2026-08-24/pat-regole-tecnico-operative-2025.pdf`.
- Avviso del Segretariato generale 28/01/2026: dal 1° febbraio 2026 il Formweb è il canale ordinario e la PEC con i moduli XFA resta residuale.
- Portale dell'Avvocato `https://pe.prod.cloud.giustizia-amministrativa.it`, versione 1.15.0. Accesso con SPID, CIE o CNS. L'avvocato viene profilato da ReGIndE.
- Manuale «Portali Esterni nuovo SIGA-PAT», 53 pagine, archiviato in `fonti_ufficiali/2026-09-25/pat-manuale-portali-esterni-avvocato.pdf`.
- Video ufficiale «Form Web» e slide del webinar del 26/05/2025, dalla pagina «Istruzioni sintetiche e video» di giustizia-amministrativa.it.
- Moduli XFA ufficiali: ricorso e atto 4.02; istanza, richieste alla segreteria e rimborso 4.01. Si trovano in `pct/data/pat_moduli/` e da lì si leggono i codici SIGA.
- Foglio ufficiale «Excel_Parti.xlsx» (2025), in `pct/data/pat_moduli/Excel_Parti_2025.xlsx`.

## 2. Struttura del portale

| Menu | Voci | Note |
|---|---|---|
| Pagina iniziale | Calendario udienze | Mostra sede e sezione per ogni udienza. |
| Fascicoli | Elenco fascicoli, Udienze | La sede è obbligatoria (TAR, Consiglio di Stato o CGARS). Il dettaglio del fascicolo contiene: riepilogo, parti e difensori, atti, provvedimenti adottati, provvedimenti impugnati, discussioni, notifiche, avvisi, atto o documento successivo e la notifica per NRG. |
| Depositi | Elenco depositi, Nuovo deposito, Depositi in redazione | Filtri: tipologia (ricorsi, atti successivi, PSS/ante causam, richieste alla segreteria, ausiliari, rimborso) e stato (inviati, in elaborazione, depositati, rifiutati, in errore). Scaricabili: ricevuta di registrazione, ricevuta di ricezione e deposito originale. |
| Ricerche | Registro, Multicriterio, Parti, Provvedimenti, Atti, Ricorsi depositati | Per i ricorsi depositati la ricerca copre al massimo 180 giorni e non ha valore legale. |
| Collaboratori | Abilitazione con date di inizio e fine | — |

## 3. Nuovo deposito (Formweb)

Tipi di deposito, con il loro percorso sotto `#/depositi/nuovo/` e i passi iniziali:

| Tipo | Percorso | Passi iniziali |
|---|---|---|
| Ricorso | `ricorso` | Depositanti → Difensore → Autorità e primo ricorrente → Informazioni generali |
| Atto successivo | `atto-successivo` | 3 passi |
| Documento successivo | `documento-successivo` | 3 passi |
| Istanze al giudice | `istanze-giudice` | 3 passi |
| Richieste alla segreteria | `richieste-segreteria` | 2 passi |
| Successivo contributo unificato | `succ-contr-unificato` | 3 passi |
| Successivo notifiche | `succ-notifiche` | 3 passi |
| Rimborso del contributo unificato | `rimborso` | 3 passi |

- **Informazioni generali del ricorso.** Si indicano:
  - la sede;
  - se ci sono istanze ante causam;
  - la tipologia, cioè il tipo di ricorso, con le stesse voci e codici del modulo XFA (es. ORDINARIO = 1, ACCESSO AI DOCUMENTI = 85);
  - il finanziamento PNRR (art. 12-bis d.l. 68/2022);
  - l'oggetto, fino a 16.000 caratteri.

  La bozza si crea con «CONFERMA».
- **Schede del ricorso:**
  - Parti: ricorrenti, resistenti e controinteressati, con «Carica Excel» e «Scarica nominativi».
  - Ricorso, procura e allegati: ricorso, procura (con data, «a margine» e parti), atti impugnati (organo, tipologia, anno, numero oppure «non indicato») e documenti allegati (natura e descrizione fino a 150 caratteri, asseverazione).
  - Istanza di fissazione udienza.
  - Altre istanze.
  - Segnala istanze/domande.
  - Notifiche: parte notificata, data di invio, data di ricezione, modalità (PEC, posta, mani proprie, UNEP, altro) e copia informatica di relata e atto notificato.
  - Contributo unificato: non esente, esente, patrocinio a spese dello Stato, non dovuto oppure prenotazione a debito.
  - Ricorsi connessi.
- **Azioni:**
  - «Salva bozza»: la bozza resta disponibile 60 giorni.
  - «Anteprima riepilogo»: evidenzia in rosso le sezioni obbligatorie mancanti.
  - «Genera riepilogo»: crea il PDF con, per ogni file, il nome e il «Codice HASH» (SHA-256 esadecimale maiuscolo).
  - Il riepilogo si firma digitalmente.
  - «Invia deposito»: si carica il riepilogo firmato e si invia. Al termine compare l'identificativo del deposito.
- **Controlli del portale sui file** (codice della 1.15.0):
  - nome del file senza estensione: solo `A-Z a-z 0-9 _`, spazi e `ÄäÖöÜüß`;
  - estensioni ordinarie: `.pdf .txt .xml .jpg .jpeg .gif .tiff .tif .eml .msg .zip .rar`;
  - per atto e riepilogo: `.pdf .txt .rtf .zip .rar`;
  - avviso sopra i 150 caratteri di nome;
  - al massimo 5 file per caricamento;
  - numero e peso complessivo li fornisce il server durante la bozza.

## 4. Come funziona in IUSENTRA (2.403.0)

Il portale non offre un canale per i gestionali. IUSENTRA prepara e verifica, mentre compilazione e invio restano all'avvocato.

- **Apertura del fascicolo** amministrativo, completa o «Fascicolo Veloce»: il pannello «Procedimento amministrativo (PAT)» chiede:
  - la sede, scritta come nel portale e proposta automaticamente dall'ufficio indicato;
  - il tipo di ricorso;
  - la posizione dell'assistito;
  - l'NRG;
  - il contributo unificato.

  Con il veloce si apre subito la sezione del fascicolo.
- **Sezione «Deposito amministrativo (PAT)» del fascicolo**:
  - **Prepara il deposito**: scheda per ognuno degli 8 tipi, nell'ordine del portale. Ogni riga dice se il dato è pronto, manca o va verificato, e ha il pulsante «Copia». Da qui si apre il Formweb direttamente sul tipo scelto e si scarica il pacchetto dei file.
  - **Procedimento**: sede, tipo di ricorso o di appello, NRG, oggetto, PNRR, ante causam, cassazionista (Consiglio di Stato e CGARS), atto impugnato, istanze da segnalare, contributo. Il contributo è proposto secondo l'art. 13 c. 6-bis d.P.R. 115/2002 con il calcolatore già presente; le esenzioni vengono dal modulo ufficiale.
  - **Parti**: il ruolo per il Formweb è proposto così (l'avvocato può cambiarlo o escludere la parte):
    - amministrazioni opposte all'assistito: resistenti;
    - privati: controinteressati.

    Il foglio ufficiale Excel è pronto per ricorrenti, resistenti e controinteressati.
  - **Documenti**: ruolo del file (atto, procura, allegato, notifica, contributo, escluso), nome accettato dal Formweb, descrizione fino a 150 caratteri, firma PAdES richiesta per atto e procura. Il pacchetto zip contiene i file rinominati e un indice con l'impronta SHA-256.
  - **Verifica e depositi**: il riepilogo generato dal Formweb si carica prima dell'invio.
    - IUSENTRA confronta le impronte con i file del fascicolo e segnala i file cambiati o estranei.
    - Controlla la firma: PAdES o CAdES.
    - Salva il riepilogo nel fascicolo, escluso dai file da depositare.
    - Registra il deposito.

    Stato e identificativo si aggiornano con quanto mostra il portale.
- **Pagina /pat**:
  - fascicoli amministrativi con i dati della bozza ancora da indicare e l'ultimo deposito;
  - raggiungibilità del Portale dell'Avvocato, verificata leggendo solo pagine pubbliche e tenuta in cache 10 minuti;
  - collegamenti rapidi al Formweb.

  Il vecchio modulo XFA per il deposito via PEC resta come «canale residuale», chiuso per impostazione (`/pat?modulo=pec` lo apre).
- **Codice**:
  - dominio in `pct/pat_formweb/`: regole, catalogo, archivio, parti, foglio Excel, contributo, scheda, riepilogo;
  - servizi in `web/services/pat_formweb_*.py`;
  - API in `/api/v1/ui/amministrativo` (`web/blueprints/api_v1_amministrativo.py`);
  - interfaccia in `frontend/src/components/patFormweb/`;
  - test in `tests/test_pat_formweb.py` e `tests/test_pat_formweb_api.py`.

## 5. Punti aperti

- Le schede dei depositi diversi dal ricorso si vedono solo dopo aver salvato una bozza. Per rispetto del vincolo di sola lettura non sono state aperte. La scheda IUSENTRA per quei tipi segue i dati dei moduli ufficiali corrispondenti.
- Le liste dei codificati del portale (`anagrafica/v1/tipologie-*`) richiedono il token della sessione e non sono state lette. Si usano le stesse liste dei moduli XFA ufficiali.
