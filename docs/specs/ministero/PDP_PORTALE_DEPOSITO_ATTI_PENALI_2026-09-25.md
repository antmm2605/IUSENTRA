# Portale Deposito atti Penali (PDP) e servizi penali del PST — acquisizione per IUSENTRA

Acquisizione del 25/09/2026, fatta dall'area riservata del PST con sessione avvocato (manuale utente online del PDP, 64 pagine lette) e dalle fonti normative già archiviate in `docs/specs/ministero/`. Le tabelle ufficiali Atto-Ufficio-Soggetto sono trascritte in `fonti_ufficiali/2026-09-25/pdp_relazioni_atto_ufficio_soggetto.json`.

## 1. Base normativa

| Fonte | Che cosa stabilisce |
|---|---|
| art. 111-bis c.p.p.; art. 87 co. 6-bis e 6-ter D.Lgs. 150/2022 | deposito telematico obbligatorio degli atti penali, nel portale individuato da DGSIA |
| D.M. 29/12/2023 n. 217, art. 3, modificato da D.M. 206/2024, D.M. 206/2025 (G.U. 302 del 31/12/2025) e D.M. 114/2026 | uffici e date da cui il PDP è l'unico canale |
| Provvedimento DGSIA 11/07/2023 (`Specifiche_Tecniche_PPT_11.07.2023_post_DM_2023_signed.pdf`) | accesso, formati, limiti, stati del deposito, ricevute |
| art. 16 co. 4 D.M. 44/2011; art. 16 co. 6 e 8 D.L. 179/2012; art. 20 D.M. 44/2011 | avvisi degli atti depositati in cancelleria quando la PEC al difensore non viene consegnata |

**Il deposito è eseguito al rilascio della ricevuta di accettazione del PDP; è tempestivo se avviene entro le ore 24 del giorno di scadenza** (art. 87 co. 6-bis D.Lgs. 150/2022).

Calendario vigente (fonte secondaria, da confermare sul testo del D.M. 114/2026 prima di codificarlo):
- già obbligatorio: Procura della Repubblica, GIP/GUP, Tribunale;
- dal 1/7/2027 Corte d'Appello e Procura Generale; dal 1/1/2028 Giudice di Pace e Cassazione; dal 2029 minori ed esecuzione; dal 2030 Sorveglianza e procedimenti speciali;
- negli uffici non ancora obbligati restano PEC o carta; la costituzione di parte civile **in udienza** resta cartacea.

## 2. Accesso

- Solo dal PST, area riservata, con **smart card o SPID** (art. 4 provv. DGSIA).
- Solo iscritti ReGInDE come avvocato, praticante abilitato, o Avvocatura dello Stato.
- **Non esiste un'interfaccia per programmi esterni né un canale PEC**: il deposito è una maschera web compilata dall'avvocato. Nessun gestionale può depositare al posto suo.
- Nelle Preferenze l'avvocato imposta l'ufficio di destinazione di default e una **email ordinaria** (validata con codice) su cui ricevere gli esiti.

## 3. Modello del portale

### 3.1 Procedimento autorizzato

È il cuore del penale telematico e **non esiste nel civile**.

- Un procedimento è «autorizzato» quando nel registro dell'ufficio (Re.Ge.WEB/SICP) c'è il **codice fiscale dell'avvocato** associato ad almeno un soggetto rappresentato (art. 6 provv. DGSIA).
- Ci si arriva in due modi: nomina depositata dal PDP e **accettata**, oppure nomina inserita a mano dalla cancelleria (fiducia o ufficio) e recuperata con **«Aggiorna elenco»** (richiesta asincrona a Re.Ge.WEB per distretto).
- Solo sui procedimenti autorizzati si depositano gli **atti successivi**.
- Per ogni procedimento il portale mostra: numeri di registro e uffici attraversati, magistrato, soggetti rappresentati (iniziali, dettaglio con ruolo), elenco depositi, **stato del procedimento** (per imputato: QGF, sentenze con grado/numero/data, impugnazioni) e **storico udienze** (data e ora, tipo ufficio, aula, luogo, causale). Stato e udienze sono disponibili dagli uffici dibattimentali in poi.
- Tutti gli elenchi (procedimenti, depositi, solleciti, denunce, certificati, stato procedimento, udienze) si **esportano in .xlsx**.

### 3.2 Identificazione del procedimento e dell'ufficio

- Ufficio: tipo ufficio, distretto, circondario/circolo, sede.
- Procedimento: ufficio registro, numero, anno, registro, sede ufficio.
- Magistrato: facoltativo; da elenco dell'ufficio o digitato.
- Uffici del PDP (colonne della tabella ufficiale): PM, GIP, DIB, CAS, CAP, CASAP; per il Giudice di Pace PM, GDPC, GDP, AppGdP; poi PGCAP e RIE (Riesame).

### 3.3 Soggetti e ruoli

Ruoli: indagato/imputato/responsabile amministrativo, persona offesa, parte civile, civilmente obbligato, responsabile civile, terzo interessato.

- Ogni deposito è fatto **nell'interesse di soggetti precisi** e riporta le loro iniziali. Il PDP associa in automatico i soggetti del ruolo ammesso e l'avvocato può deselezionarli.
- Il ruolo filtra gli atti (es. remissione di querela solo persona offesa; elezione/dichiarazione di domicilio, abbreviato, oblazione, patteggiamento, messa alla prova solo indagato/imputato).
- Controllo non bloccante sulla data di nascita (minore).

### 3.4 Catalogo degli atti

- **Atti principali** (menu Depositi): nomina difensore/legale; costituzione di parte civile, del responsabile civile e del civilmente obbligato; intervento del responsabile civile; intervento di ente esponenziale; denuncia, querela, istanza di procedimento, deposito integrazione; rescissione del giudicato, revisione e riparazione per ingiusta detenzione (queste tre solo presso la CAP, con procura speciale obbligatoria).
- **Atti successivi**: 169 tipi nella tabella ufficiale.
- **Filtri**: ammissibili solo se la tabella Atto-Ufficio **e** la tabella Atto-Ruolo lo consentono. In più: ricerca testuale e filtro per **fase**.
- Nei procedimenti avocati dalla PG, presso la PGCAP si depositano gli atti del PM tranne la richiesta di avocazione.

### 3.5 Composizione del deposito

| Parte | Firma | Note |
|---|---|---|
| Atto principale (uno, salvo eccezioni) | obbligatoria, PAdES-BES o CAdES-BES | PDF nativo A4, non scansione; firma valida e non revocata; **almeno una firma del CF dell'avvocato collegato** (AdS: qualsiasi avvocato dello Stato) |
| Atti contestuali (con nomina/costituzione; «Programma di trattamento» con l'istanza di messa alla prova) | obbligatoria | tipo scelto dalla lista già filtrata |
| Atto abilitante (solo nomina in Procura) | non richiesta | necessario se nel fascicolo non c'è avviso 408, 411 o 415-bis; «oggetto» obbligatorio |
| Allegati | non richiesta | pdf, p7m, immagini, audio, video, rtf, txt, xml, eml/msg, zip/rar/arj; «oggetto» obbligatorio |

- **Limiti**: 50 MB per file e 500 MB per deposito (art. 5 co. 6 provv. DGSIA). Nome del file e oggetto: massimo 100 caratteri. Nessuna password sui file. Scansioni solo per allegati, bianco e nero a 200 dpi.
- **Procura speciale**: per dichiarazione ed elezione di domicilio, rescissione, revisione e riparazione serve la spunta «atto comprensivo di procura speciale / già in atti», altrimenti la procura va allegata. Per denuncia e querela serve la spunta «comprensivo di nomina e/o procura speciale», altrimenti è obbligatorio un allegato.

### 3.6 Dati strutturati richiesti da alcuni atti

| Atto | Dati da inserire |
|---|---|
| Patteggiamento | tipo pena (reclusione o arresto) con anni/mesi/giorni; pena pecuniaria (multa o ammenda) con importo in euro a 2 decimali; sospensione condizionale sì/no |
| Oblazione | tipo di oblazione e importo proposto |
| Giudizio abbreviato | semplice o condizionato |
| Memorie art. 415-bis | «contiene istanza di interrogatorio» sì/no |
| Impugnazione | appello o ricorso per cassazione, numero e anno della sentenza |
| Nomina CTP, ricusazione/nomina perito, esclusione parte civile | anagrafica del CTP, del perito o della parte civile |
| Ricusazione del giudice | magistrato (precompilato se monocratico) |
| Revoca di altro difensore | codice fiscale dell'avvocato revocato |
| Costituzione di parte civile (atto successivo) | reati per cui ci si costituisce |
| Elezione/dichiarazione di domicilio | domicilio per ogni soggetto, o «presso il legale» |
| Denuncia/querela | denunciante e persona offesa (fisica o giuridica, con residenza, domicili, PEC, recapiti); denunciato; urgente; EPPO (invio anche alla Procura europea); **violenza di genere** con luogo, figli, armi e rapporto autore-vittima |
| Certificato ex art. 335 c.p.p. | solo Procura; un solo soggetto; «comprensivo di mandato» (altrimenti mandato allegato) |

### 3.7 Stati del deposito e ricevute

Stati (art. 7 co. 4 provv. DGSIA):

1. **Inviato**
2. **In transito** — da qui il PDP cancella i dati personali (art. 9)
3. **In fase di verifica** — nell'accesso agli atti anche con nota «presa in carico»
4. **Accolto** — per denuncia e querela significa procedimento iscritto
5. **Rigettato**, con motivazione
6. **Errore tecnico** — il deposito va ripetuto

Ricevute:
- **Ricevuta di deposito** (testo verificato il 25/09/2026 su una ricevuta reale, PDF IronPdf con testo nativo): «IDENTIFICATIVO AAAA/NNNNNNN … L'avvocato NOME CF ha inviato all'ufficio UFFICIO in data GG/MM/AAAA alle ore HH:MM:SS, in relazione al procedimento: REGISTRO NOTI PM nr. N/AAAA, indirizzato al Magistrato …, l'atto di TIPO ATTO, nell'interesse dei seguenti soggetti rappresentati, in qualità di RUOLO: SOGGETTI con nr. N allegati», con il richiamo all'art. 87 co. 6-bis. **Non riporta impronte hash** (il manuale le cita, la ricevuta reale no).
- **Ricevuta di esito**: «Il deposito con IDENTIFICATIVO …, inviato all'ufficio … in data … alle ore …, è stato rifiutato|accettato in data … alle ore … con la seguente motivazione: …». L'esito arriva anche all'email ordinaria impostata nelle Preferenze.
- Endpoint del portale (sessione dell'avvocato): `pratiche/ricevuta/{0|1|2}/{identificativoPratica}` e `pratiche/ricevuta-esito/{0|1|2}/{identificativoPratica}`.
- **Sollecito**: possibile su una nomina «in verifica». Ha un suo elenco.

### 3.8 Accesso agli atti

- Richiesta (art. 116 c.p.p.) presso PM o DIB.
- Se accolta, compare un link valido **3 giorni** e la **password arriva via PEC** all'indirizzo ReGInDE. È l'unico caso in cui il penale fa arrivare documenti al difensore.
- Il respingimento può essere anche automatico, per disallineamento dei sistemi di cancelleria.

## 4. Altri servizi penali del PST

- **Proc. Penali – Avvisi degli atti depositati in cancelleria** (`/PST/AvvisiPenale`).
  - Quando la PEC di una notifica al difensore non viene consegnata per causa sua (casella piena o non valida), la notifica si perfeziona **con il deposito in cancelleria** (art. 16 co. 6 D.L. 179/2012). Il PST pubblica un avviso con i soli estremi del procedimento e delle parti (art. 16 co. 4 D.M. 44/2011).
  - L'elenco è per codice fiscale dell'avvocato. Il 25/09/2026 per l'utente collegato risultava vuoto («Non ci sono risultati»).
  - **Conseguenza per lo studio**: una casella PEC satura produce notifiche perfezionate senza che l'avvocato le riceva. L'art. 20 D.M. 44/2011 gli impone spazio disco adeguato e avvisi di saturazione.
- **Consultazione SIUS distrettuali** (esecuzione e sorveglianza), **Portale Notifiche**, **Portale VPDF**: individuati nella home del PST, non ancora analizzati.

## 5. Differenze dal civile

| | Civile (PCT) | Penale (PDP) |
|---|---|---|
| Canale | busta `.enc` firmata inviata via PEC (D.M. 44/2011 art. 14) | maschera web nel portale, niente busta né DatiAtto.xml |
| Chi deposita | anche un software per conto dell'avvocato (redattore) | solo l'avvocato autenticato nel portale |
| Esiti | 4 PEC: accettazione, consegna, controlli, cancelleria | 6 stati sul portale, ricevuta di deposito ed esito da scaricare, email ordinaria facoltativa |
| Momento del deposito | ricevuta di avvenuta consegna | ricevuta di accettazione del PDP |
| Legittimazione | la parte costituita deposita nel suo RG | serve il **procedimento autorizzato** (CF in Re.Ge.WEB) |
| Ufficio | ufficio e numero di ruolo | ufficio preciso (PM, GIP, DIB, …) e registro; il procedimento cambia numero passando fra uffici |
| Parte | l'avvocato difende la parte | ogni deposito è legato a soggetti e ruoli; il catalogo dipende dal ruolo |
| Composizione | atto principale e allegati | principale, contestuali, abilitante, allegati, eventuale procura speciale |
| Consultazione | fascicolo informatico completo | stato del procedimento, udienze ed elenchi esportabili in xlsx; atti solo con accesso agli atti (link di 3 giorni e password via PEC) |

## 6. IUSENTRA prima della 2.401.0

- `pct/pdp.py` — `ClientPDP.deposita_atto` presuppone `POST {appweb.giustizia.it/snt}/depositi` con risposta `codiceEsito` ed esiti PEC in «fasi 4-7». **Nessuna di queste cose esiste nel PDP**: è lo schema civile trasposto. L'invio resta bloccato da `ensure_direct_portal_verified("pdp")`.
- `pct/pdp_penale_workflow.py` (SQLite) conteneva già `criminal_cases`, eventi, documenti, `criminal_access_requests` (password PEC e scadenza del download), task e PEC collegate: è la base su cui si innesta il deposito.
- CLAUDE.md e AGENTS.md descrivevano il PDP come «REST API /depositi, multipart, mTLS»: corretti nella 2.401.0.

## 7. Come funziona in IUSENTRA (2.401.0)

Implementato in `pct/penale_pdp/` (dominio), `web/services/penale_pdp_*.py`, API `/api/v1/ui/penale/*` e sezione «Deposito penale (PDP)» del fascicolo penale.

Principio: IUSENTRA **prepara, controlla, registra e sorveglia**. Il deposito resta un gesto dell'avvocato nel PDP.

1. **Catalogo ufficiale** in `pct/data/cataloghi/`, caricato dal JSON delle tabelle.
   - `atti_ammessi(ufficio, ruoli)` restituisce solo gli atti che entrambe le tabelle consentono. Per la PGCAP vale la regola dell'avocazione.
   - Per ogni atto: gruppo (principale o successivo), dati strutturati richiesti (§3.6), obbligo di procura speciale, atti contestuali ammessi.
2. **Procedimento penale del fascicolo.**
   - Registri per ufficio (il numero cambia passando da PM a GIP a DIB).
   - Soggetti rappresentati con ruolo.
   - Stato «autorizzato» (sì/no, con fonte: nomina accolta o aggiornamento dall'elenco).
   - Magistrato.
3. **Preparazione del deposito.**
   - Composizione: principale, contestuali, abilitante, allegati.
   - Controlli prima dell'invio: PDF nativo A4, firma PAdES/CAdES valida, firmatario uguale al CF dell'avvocato, 50/500 MB, nome file e oggetto entro 100 caratteri, niente password, formati ammessi.
   - Atto abilitante richiesto se la nomina va in Procura e non risulta un avviso 408, 411 o 415-bis.
   - Scheda con i dati da ricopiare nella maschera del PDP, nell'ordine del portale.
4. **Registrazione dell'esito.**
   - Caricata la ricevuta di deposito (PDF), IUSENTRA legge identificativo, avvocato e CF, ufficio, data e ora, procedimento, atto, soggetti e numero degli allegati, e li confronta con il deposito preparato (la ricevuta non ha impronte).
   - Una ricevuta con identificativo diverso da quello già registrato viene respinta: va caricata sul deposito giusto.
   - Caricata la ricevuta di esito, aggiorna lo stato fra i sei ufficiali.
   - Il deposito fa fede dalla ricevuta di accettazione: il presidio delle scadenze usa quella data e le ore 24.
5. **Import degli export xlsx** del PDP (procedimenti autorizzati, depositi, stato del procedimento, storico udienze).
   - È l'unica via per portare in IUSENTRA udienze, sentenze e impugnazioni senza trascriverle.
   - Le udienze vanno in agenda; gli stati dei depositi e i procedimenti diventano fascicoli collegati.
6. **Accesso agli atti** (esiste già): allineare gli stati ai sei ufficiali, compresa la «presa in carico».
7. **Presidio della PEC per gli avvisi in cancelleria.**
   - Allarme su casella vicina alla saturazione (IMAP QUOTA) e su ogni mancata consegna di una notifica penale.
   - Promemoria di controllare «Avvisi degli atti depositati in cancelleria» sul PST.
8. **Calendario degli obblighi** per ufficio e data (§1), così IUSENTRA indica se per quell'ufficio il canale è PDP, PEC o carta.

Punti aperti:
- confermare il calendario sul testo del D.M. 114/2026;
- ottenere un export xlsx reale del PDP (procedimenti autorizzati e depositi): il lettore segue le intestazioni di colonna viste nel portale, ma il file non è stato scaricato;
- analizzare SIUS, Portale Notifiche e VPDF.

## 8. Collaudo senza invio (25/09/2026)

Svolto nel PDP 6.11.10 con la sessione dell'avvocato, in sola lettura: nessun invio, nessun caricamento, nessun file scaricato su disco.

| Verifica | Esito |
|---|---|
| Catalogo `pdp_atti_penali.json` contro `codificati/tipi-atto` dal vivo | identico: 170 atti, stessa impronta (codice, fase, uffici) |
| Ricevuta di deposito reale (identificativo 2023/0582463) letta nel browser | testo nativo con ToUnicode; formato riportato al §3.7; **nessun hash** → confronto ridisegnato sui campi della ricevuta |
| Ricevuta di esito reale dello stesso deposito | «è stato rifiutato … motivazione: Ufficio destinatario non coerente» |
| Causa del rigetto | nomina con registro PM inviata al Tribunale ordinario: IUSENTRA ora avvisa prima (`UFFICIO_NON_COERENTE`) e il confronto della ricevuta segnala l'ufficio |
| Maschera «Ufficio Destinazione» | la scheda IUSENTRA indica Distretto, Circondario/Circolo e Sede con le scritture del PDP (vedi §9), Sede ufficio e Tipo legale |
| Avvisi degli atti depositati in cancelleria | vuoto per il CF collegato; IUSENTRA misura la casella PEC con IMAP QUOTA (solo comandi di lettura: CAPABILITY, LOGIN, GETQUOTAROOT, LOGOUT, verificati con un server IMAP di prova) e rimanda all'elenco del PST |

I test `tests/test_penale_pdp.py` riproducono le due ricevute con l'impaginazione reale (parole spezzate dalla crenatura) e nomi di fantasia.

## 9. Sedi, accesso agli atti e apertura del fascicolo (2.402.0)

Collaudo in sola lettura sul PDP 6.11.10 (GET sui codificati, nessun invio, nessun caricamento).

**Catalogo delle sedi.** `pct/data/cataloghi/pdp_sedi_penali.json` salva dai codificati del portale
(`distretti`, `circondari?codiceTipoUfficioAmbito=…&codiceDistretto=…`,
`sediuffici?codiceTipoUfficioAmbito=…&codiceCircondario=…`) i 140 circondari delle 26 corti d'appello con le sedi di Procura (PM-U) e Tribunale
dibattimento (DIB-U); il PDP elenca 30 distretti, ma le sezioni distaccate (Bolzano, Sassari, Taranto)
ed EPPO non hanno circondari propri per PM-U: Bolzano, per esempio, sta nel distretto TRENTO, nella scrittura del portale («BOLZANO/BOZEN», «PROCURA DELLA
REPUBBLICA DI REGGIO DI CALABRIA»). Il codice sede della Procura coincide con il codice ministeriale
dell'ufficio (es. 08005702100, Procura di Palmi). `pct/penale_pdp/sede.py` riconosce l'ufficio del
fascicolo in quest'ordine: codice ministeriale, comune del tribunale (Massa Carrara → MASSA), tribunali
soppressi dal D.Lgs. 155/2012 verso il circondario che li ha accorpati (Chiavari → GENOVA, Caserta →
SANTA MARIA CAPUA VETERE), nome del circondario o della sede (Napoli Nord prima di Napoli). Per i nomi
«X ex Y» conta l'ufficio attuale. Tutti i 169 tribunali del bundle trovano la sede; per GIP, minori e
Procura generale la sede non è nel catalogo e resta «da scegliere sul PDP».

**Accesso agli atti in React.** La scheda «Accesso agli atti» della sezione Deposito penale del
fascicolo (`/fascicoli/<id>?pdp=accesso#penale-pdp`) sostituisce la vecchia pagina
`/fascicoli/<id>/penale/pdp` nei collegamenti: richiesta (art. 116 c.p.p.), atto generato in PDF, PEC con
link e password (link valido 3 giorni, §3.8), import del pacchetto scaricato, documenti collegati,
attività e cronologia. Le azioni chiamano le stesse funzioni di rotta già collaudate
(`web/bootstrap/fascicoli_pdp_routes.py`), che restano invariate.

**Apertura del fascicolo penale.** Nel nuovo fascicolo di tipo Penale, completo o «Fascicolo Veloce»,
il pannello «Procedimento penale (PDP)» chiede i dati delle maschere «Ufficio Destinazione» e
«Identificazione Procedimento» (ufficio, registro, numero e anno, magistrato, ruolo dell'assistito,
altro soggetto, procedimento già autorizzato) e mostra subito distretto → circondario → sede da
scegliere sul PDP per l'ufficio indicato. Nel veloce penale controparte e codice fiscale non sono
obbligatori (nel penale la parte avversa non è una controparte civile) e alla creazione si apre
direttamente la sezione Deposito penale.
