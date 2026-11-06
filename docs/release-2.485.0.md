# Release 2.485.0 — guide pratiche per tutte le materie, norme scelte per data, giurisprudenza da fonti certe, esito e rimedi

Richieste dell'avvocato del 06/11/2026:
- schede complete e professionali, non «di base»;
- guide per tutte le materie;
- norme vigenti, e il software deve sapere quale legge applicare in base alla data;
- la guida accompagna la pratica fino alla fine e ragiona sull'esito;
- le norme lette entrano nel registro del software.

Ogni norma è stata letta nel testo vigente dall'archivio Normattiva del software il 06/11/2026, oppure su Normattiva:
L. 18/1980 art. 1, art. 59 L. 69/2009 e art. 14 D.L. 669/1996.

## Schede completate

Nessuna scheda resta «di base». Prima di questa versione erano 99.
- **Pubblico impiego:** 20 schede costruite sulla scheda curata 222050, con le varianti per materia.
- **Lavoro privato e previdenza:** 8 schede: revocazione, condotta antisindacale, licenziamenti, dirigenti, cautelari e
  indennità di accompagnamento.
- **Decreto ingiuntivo per materia:** 28 schede. Indicano la mediazione a carico del ricorrente nell'opposizione
  (art. 5-bis D.Lgs. 28/2010), l'art. 63 disp. att. c.c. per il condominio, l'art. 447-bis c.p.c. per le locazioni,
  l'art. 642 c.p.c. per cambiali e assegni e l'art. 636 c.p.c. per i professionisti.
- **Altre 42 schede:** cautelari, possesso, sfratti per uso diverso, opposizioni esecutive, interdizione, divorzio,
  paternità, usucapione speciale, impresa, crisi, sanzioni, azioni di classe, equa riparazione ed esecuzioni.

## Guide nuove per le materie che mancavano

Le materie seguono l'elenco di `lex/normativa/materie.py`.
- **Penale (21):** querela, opposizione all'archiviazione, avviso ex art. 415-bis, opposizione al decreto penale,
  patteggiamento, abbreviato, messa alla prova, appello, cassazione, riesame e appello cautelare, revoca della misura,
  riesame del sequestro, restituzione nel termine, rescissione del giudicato, revisione, ingiusta detenzione, misure
  alternative, incidente di esecuzione, giustizia riparativa, ricorso immediato al giudice di pace. Il deposito avviene
  dal portale penale (art. 111-bis c.p.p.). L'art. 581, comma 1-ter, c.p.p. è indicato come abrogato dalla
  L. 114/2024.
- **Immigrazione (6):** protezione internazionale, espulsione, convalida del trattenimento, ricongiungimento,
  cittadinanza, discriminazione.
- **Professione forense (6):** liquidazione dei compensi, parere di congruità come titolo esecutivo (art. 7
  L. 49/2023), equo compenso, opposizione alla liquidazione nel patrocinio a spese dello Stato, ricorso al CNF, albo.
- **Privacy (4):** reclamo al Garante, ricorso contro il provvedimento del Garante, risarcimento del danno, diritti
  dell'interessato.
- **Ordinamento militare (3):** sanzione di corpo e ricorso gerarchico, procedimento disciplinare di stato, reato
  militare.
- **Procedura tributaria (6):** ricorso, sospensione, conciliazione, appello, cassazione, ottemperanza.
- **Procedura amministrativa (5):** ricorso al TAR, cautelare, appello al Consiglio di Stato, ottemperanza, silenzio.

## Norme scelte in base alla data

Una norma o un termine della scheda può dichiarare `vigente_dal` / `vigente_fino_al`. Una norma abrogata dichiara
`abrogata_da` (`pct/guida_pratica/vigenza.py`). Funzionamento:
- la guida usa la data dell'atto da compiere indicata nel fascicolo, oppure la data di oggi;
- mostra solo le norme in vigore in quel giorno;
- spiega la scelta in testa alle avvertenze e annuncia il prossimo cambio.

Esempio tributario: fino al 31/12/2026 si applica il D.Lgs. 546/1992; dal 1° gennaio 2027 il D.Lgs. 175/2024 (art. 131,
decorrenza; art. 130, abrogazione del D.Lgs. 546/1992).

## Articoli abrogati nelle schede esistenti

Le schede citavano articoli abrogati: sono state rilette tutte.
- **Articoli abrogati:** ora portano l'atto abrogante letto nell'archivio. La guida non li mostra per gli atti di oggi.
- **Articoli sostitutivi certi:** dove c'è, è aggiunto accanto. Corrispondenze:
  - art. 710 c.p.c. → art. 473-bis.29;
  - art. 711 → art. 473-bis.51;
  - art. 736-bis → art. 473-bis.71;
  - art. 720-bis → art. 473-bis.58;
  - art. 712 → art. 473-bis.52;
  - art. 336-bis c.c. → art. 473-bis.4 c.p.c.;
  - art. 337-octies c.c. → art. 473-bis.10 c.p.c.;
  - artt. 342-bis e 342-ter c.c. → artt. 473-bis.69 e 473-bis.70 c.p.c.;
  - art. 375 c.c. → art. 374 c.c.;
  - art. 2409 c.c. → art. 2396-quater c.c. (D.Lgs. 47/2026).
- **Riferimenti con la fonte sbagliata:** 30 riferimenti ricavati dal titolo della pratica e attribuiti per errore
  al c.p.c. ora indicano la fonte giusta (L. 184/1983, c.c., c.p., D.Lgs. 142/2015…).
- **Altre leggi abrogate:**
  - art. 23 L. 689/1981 → art. 6 D.Lgs. 150/2011;
  - art. 4 L. 898/1970 → art. 473-bis.12 c.p.c.;
  - rito della L. 92/2012 → art. 441-bis c.p.c.;
  - art. 100 L.F. → art. 98 L.F. e art. 206 CCII.

## Suggerimento della guida dal fascicolo

Il suggerimento automatico cercava solo nei codici ministeriali del civile. Ora funziona così:
- per i fascicoli penali, amministrativi e tributari cerca tra le guide interne della stessa materia;
- negli altri casi cerca tra le guide interne quando il catalogo ufficiale non dà risultati;
- ogni guida ha parole chiave d'uso in studio («custodia cautelare», «avviso di accertamento», «sospensiva»);
- l'avviso sul deposito ora dipende dalla materia, per esempio il portale penale per il penale e gli organi indicati per
  il Garante o il CNF.

## Esito della sentenza e rimedi (`pct/percorso_pratica/`)

- **Esito:** `esito.py` legge dal dispositivo:
  - l'esito (accoglimento, rigetto, parziale, inammissibilità, improcedibilità, estinzione, incompetenza, difetto di
    giurisdizione);
  - le spese (condanna, compensazione, distrazione, importo; un importo illeggibile resta vuoto);
  - le frasi della motivazione che spiegano un esito sfavorevole.
- **Rimedi:** `rimedi.py` indica:
  - se la causa è vinta, i passi per ottenere quanto deciso: notifica, Avvocatura e 120 giorni contro lo Stato, precetto,
    ottemperanza, spese distratte;
  - se è persa, le impugnazioni con termini e norme e le ipotesi difensive legate alla ragione della decisione:
    prescrizione → art. 2943 c.c.; prove → art. 437 c.p.c.; incompetenza → art. 50; giurisdizione → art. 59
    L. 69/2009; spese compensate → art. 92 c.p.c.
- **Prova sulla sentenza Alessi (Velletri, 07/10/2026):** accoglimento favorevole alla ricorrente, spese € 250,00 con
  distrazione, ottemperanza per l'obbligo di emettere i buoni.

## Giurisprudenza solo da fonti certe

- **Citazioni false tolte dalle guide.** Le guide contenevano 1.461 citazioni di giurisprudenza, molte inventate:
  «Cass. SU 14897/2021» compariva 531 volte e «Cass. SU 9876/2023» 275, ma non esistono. Ogni citazione è stata cercata
  nelle fonti del software:
  - la Cassazione 2021-2026 nell'archivio SentenzeWeb, per numero, anno, sezione e pertinenza alla scheda;
  - la Cassazione anteriore al 2021, la Corte di giustizia UE e l'Adunanza plenaria, se una decisione ufficiale
    dell'archivio le richiama;
  - la Corte costituzionale nel suo archivio di open data.

  Restano 113 citazioni verificate, con il collegamento e la prova della verifica; 1.348 sono uscite.
- **Controllo anche all'apertura della guida.** Le citazioni escono dai riferimenti normativi e vanno nella sezione
  «Giurisprudenza verificata» (`pct/guida_pratica/giurisprudenza_scheda.py`,
  `web/services/guida_giurisprudenza_runtime.py`). Funzionamento:
  - è mostrata solo quella che risulta nell'archivio;
  - le altre sono contate e non mostrate come fonte;
  - accanto, le decisioni che applicano le norme della scheda: prima quelle che ne applicano di più, poi le Sezioni Unite,
    poi le più recenti.

## Alimentazione dell'archivio di giurisprudenza

Decisione dell'avvocato del 06/11/2026: l'alimentazione gira in locale 24 ore su 24; online si pubblica l'archivio completo
e l'acquisizione resta spenta.
- **Lettore delle citazioni** (`pct/giurisprudenza_citazioni.py`). Dal testo di ogni decisione registra nelle tabelle
  dell'archivio, finora vuote:
  - le norme applicate (codici e leggi, con comma e lettera);
  - i precedenti richiamati (Cassazione, anche con la data prima del numero, e Corte costituzionale).

  La lettura è incrementale: ogni decisione è segnata con la versione del lettore.
- **Lavoro «Alimentazione continua della giurisprudenza»**, ogni ora, solo con
  `IUSENTRA_ALIMENTAZIONE_GIURISPRUDENZA=continua` (`pct/giurisprudenza_alimentazione.py`). Fa:
  - l'acquisizione incrementale da SentenzeWeb;
  - il recupero dei testi in oscuramento, con numero per giro configurabile (`IUSENTRA_SENTENZEWEB_RECUPERO_PER_GIRO`;
    prima erano 25 per notte con 86.132 in coda);
  - la riparazione dei collegamenti;
  - la lettura delle citazioni nell'archivio Cassazione e negli archivi degli studi.
- **Collegamenti riparati.** 6.703 decisioni avevano come collegamento l'indirizzo di una pagina di elenco di
  SentenzeWeb, salvato da una versione precedente dell'importatore; ora puntano alla singola decisione.
- **Verifica del server del 06/11/2026.** Il corpus SentenzeWeb è presente ma non collegato
  (`IUSENTRA_SENTENZEWEB_DIRECTORY` vuota), quindi la Cassazione online non è in uso. Da impostare in sola lettura al deploy.

## Correzione del termine lungo (difetto della 2.484.0)

Il ricalcolo del termine lungo dalla data di decisione scritta nella sentenza (art. 327 c.p.c.) leggeva i testi passando
solo l'identificativo del fascicolo. La lettura falliva in silenzio, con un solo avviso nel registro, e la bozza restava
contata dalla comunicazione. Ora si passa il fascicolo vero (`web/services/termine_lungo_runtime.py`, test
`tests/test_termine_lungo_testi_fascicolo.py`). Sulla copia locale il termine di Alessi (RG 2539/2025) è passato dall'08/04
al 07/04/2027.

## La causa decisa: fase, esito e passi successivi (verifica a vista del fascicolo Alessi)

Nel controllo a vista della copia locale il fascicolo Alessi risultava «in trattazione» anche dopo la sentenza
n. 1674/2026, e la guida suggeriva ancora di «verificare la competenza». Le cause:
- **Ruolo nella forma estesa.** Il lettore del numero di ruolo non riconosceva la forma dell'epigrafe delle sentenze di
  tribunale «nella causa iscritta al n. 2539, del Ruolo Generale Affari Contenziosi dell'anno 2025». Senza ruolo la
  sentenza non era riconosciuta come pronunciata nella causa. Ora la forma estesa e le varianti si leggono
  (`pct/archivio_letture/estrazione_ruolo.py`).
- **Esito come fatto dell'archivio.** Il motore documenti registra l'esito della sentenza e le spese letti dal
  dispositivo (`pct/archivio_letture/estrazione_esito.py`). La nuova versione del motore rilegge i documenti già letti.
- **Percorso nella Lettura del fascicolo.** Con la causa decisa la Lettura calcola l'esito per il cliente dal suo ruolo
  nella causa e i passi successivi (`pct/fascicolo_lettura/percorso.py`):
  - **causa vinta:** notifica della sentenza, Avvocatura e 120 giorni contro lo Stato, precetto, ottemperanza, spese
    distratte;
  - **causa persa:** appello o ricorso con i termini, e le ipotesi difensive.
- **Guida allineata alla Lettura.** La guida prende la fase reale dalla Lettura già pronta, senza rileggere documenti,
  e mostra la sezione «Dopo la sentenza». «Prima cosa da fare» diventa il primo passo del percorso
  (`web/services/guida_fase_runtime.py`).

## Scheda 222050 completata

- **Nuove voci della scheda.** Aggiunte «Tipologie di intervento», «Legittimati attivi» e «Legittimati passivi», con gli
  artt. 45, 52 e 63 D.Lgs. 165/2001, l'art. 11 R.D. 1611/1933 e l'art. 417-bis c.p.c.
- **Carta del docente.** Aggiunto l'art. 1, comma 121, L. 107/2015 nel testo vigente letto nell'archivio Normattiva del
  software (edizione del 26/10/2026). La Carta spetta al docente di ruolo, ai supplenti annuali su posto vacante e
  disponibile e fino al termine delle attività didattiche, e al personale educativo, fino a 500 euro per anno
  scolastico.

## Fase della pratica nella guida senza attese

La fase e il percorso arrivano da `/api/v1/ui/fascicoli/<id>/guida-pratica/fase`. Se la Lettura non è pronta, la fase
si prepara in sfondo e la pagina la richiede di nuovo: la guida si apre subito e una richiesta lunga non viene più
interrotta dal limite di tempo del server.

## Cerca norme e sentenze: la norma citata per prima

- **Nuovo nome.** La pagina «Ricerca Legale» si chiama «Cerca norme e sentenze». Il sottotitolo spiega cosa si trova
  e come si scrive una citazione.
- **Norma citata.** Se l'avvocato scrive gli estremi, il software apre l'articolo e il comma vigenti dall'archivio
  Normattiva e li mostra come primo risultato «Norma citata». Esempi: «art. 1 comma 121 L. 107/2015»,
  «legge 13 luglio 2015, n. 107», «art. 52, comma 5, d.lgs. 165/2001». Il modulo è
  `web/services/ricerca_legale_norma_citata.py`.
- **Atto senza articolo.** Se la citazione indica solo l'atto e alcune parole (per esempio «carta elettronica docente
  legge 107 2015»), il software sceglie il comma che contiene quelle parole e scrive di verificarlo.
- **Atto non in archivio.** Se l'atto manca dall'archivio, il software lo dice e offre il collegamento a Normattiva:
  non mostra norme estranee al suo posto.
- **Ricerca per estremi dell'atto.** Nuovi campi: tipo di atto, numero, anno, articolo e comma, con il pulsante
  «Apri la norma».
- **Velocità.** La ricerca tra le pronunce della Cassazione con «almeno un termine» (OR) si esegue solo se quella con
  tutti i termini non riempie la pagina. Una ricerca libera passa da circa 92 secondi a circa 10 alla prima apertura.
- **Archivio caricato all'avvio.** Lo scheduler legge in sfondo l'archivio Normattiva e i codici, così la prima ricerca
  non attende il disco (`pct/preriscaldamento_archivi.py`). Si attiva solo con `IUSENTRA_PRERISCALDA_ARCHIVI=1`.
- **Materia.** Le schede dell'archivio Normattiva non mostrano più come materia le parole chiave assegnate in
  automatico all'importazione: per la L. 107/2015 compariva «crisi_impresa_societario».
- **Riconoscimento degli estremi.** «L. 107/2015» e «legge 107/2015» ora sono riconosciuti come estremi.

## Nomi chiari nel menu

Regola dell'avvocato: ogni voce deve dire cosa si trova cliccando. Ho rivisto le voci del menu della barra laterale
React e della navigazione storica, e i titoli delle pagine. Le voci cambiate sono:

| Prima | Ora |
|---|---|
| Studio | Dati e organizzazione dello studio |
| Controllo Studio | Priorità dello studio |
| Ricerca Studio | Cerca nello studio |
| Timesheet | Ore lavorate |
| Preparazione Udienza Guidata | Prepara l'udienza |
| Archivio | Fascicoli archiviati |
| Acquisizione incarichi | Nuovi incarichi in arrivo |
| Anagrafica (clienti) | Elenco clienti |
| Anagrafica (soggetti) | Elenco soggetti e parti |
| Messaggi | SMS e WhatsApp |
| Nuovo SMS/WA | Nuovo SMS o WhatsApp |
| Centro Servizi Telematici | Tutti i depositi telematici |
| PolisWeb / PST | Civile: PolisWeb e PST |
| PDP Penale | Penale: portale PDP |
| PAT Amministrativo | Amministrativo: PAT (TAR) |
| PTT Tributario | Tributario: PTT |
| Tribunali / PEC | Uffici giudiziari e loro PEC |
| Checklist deposito | Controlli prima del deposito |
| Calcolo Tariffario | Calcolo compensi forensi |
| Editor professionale | Editor di atti e documenti |
| Editor libero | Scrivi su foglio bianco |
| Redazione Atti | Atti da modello |
| Legal Skills | Procedure guidate |
| Apprendimento Lex | Cosa sta imparando Lex |
| Regia Agentica | Lavori automatici di Lex |
| Archivio Giurisprudenza | Archivio sentenze per corte |
| Utility | Calcolatori (interessi, CU, onorari) |
| Builder Sito | Costruisci le pagine del sito |
| Redazione AI Sito | Testi del sito con Lex |
| Contatti Sito | Richieste arrivate dal sito |
| Canali SdI | Fatture elettroniche (SdI) |
| Sincronizzazione Calendari | Collega Google o Outlook |
| Registro Attività | Registro attività degli utenti |
| Database | Database (tecnico) |
| Registro GDPR | Privacy: registro dei trattamenti |

La voce «Controlli Atti» nel gruppo Scadenze era un doppione della stessa pagina ed è stata tolta. Gli indirizzi delle
pagine non cambiano.

## Registro delle fonti

`pct/procedura_fasi/fonti_guide_20261106.py` contiene 265 norme nuove: il registro passa a 400 voci. Ogni voce ha l'inizio letterale del testo
vigente, il collegamento a Normattiva (EUR-Lex per il Reg. UE 2016/679) e la data di verifica. Le voci già presenti non
si ripetono.

## Test

- `tests/test_guida_pratica_vigenza.py`: norme per data, suggerimento per materia.
- `tests/test_percorso_pratica.py`: esito e rimedi, compreso il caso di dispositivo e spese del tipo Alessi.
- `tests/test_giurisprudenza_citazioni.py`, `tests/test_giurisprudenza_alimentazione.py`,
  `tests/test_giurisprudenza_scheda.py`, `tests/test_guida_giurisprudenza_runtime.py`: lettore, alimentazione, verifica e
  pagina.
- `tests/test_procedura_fasi.py`: il registro ammette EUR-Lex per gli atti dell'Unione europea.
