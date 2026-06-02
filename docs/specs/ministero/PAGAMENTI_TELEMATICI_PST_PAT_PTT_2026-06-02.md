# Pagamenti telematici PST, PAT e PTT

Consultazione ufficiale eseguita il 2 giugno 2026. Questo documento salva le
regole usate dal software per riconoscere e guidare contributo unificato,
diritti, spese e pagamenti telematici. Non sostituisce la verifica
professionale sull'importo dovuto, sulle esenzioni e sul caso concreto.

## Fonti ufficiali consultate

PST/PCT e pagoPA:

- `https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC433&modelId=12`
- `https://pst.giustizia.it/PST/resources/cms/documents/PagTel_Vademecum_unico.pdf`
- `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3099`
- `https://pst.giustizia.it/PST/resources/cms/documents/PDA__Flussi_pagamento_telematico_tramite_PST_vers._6.3.pdf`
- `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3076`
- `https://servizipst.giustizia.it/PST/it/pagopa.wp`

PAT/SIGA:

- `https://www.giustizia-amministrativa.it/faq-nuovo-portale`
- `https://www.giustizia-amministrativa.it/documents/20142/0/nsiga_4464814.pdf/c42a271a-c265-a3e1-d248-59c7be3d5f58?t=1611836199000`

PTT/SIGIT:

- `https://www.mef.gov.it/ufficio-stampa/comunicati/2019/documenti/prot._5764-19_Circolare_PTT_4-7-2019.pdf`
- `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/most-viewed`
- `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3016`
- `https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3059`
- `https://sigit.giustiziatributaria.gov.it/Sigit/index.do`

## Regole accertate PST/PCT

Il pagamento telematico tramite PST può avvenire da area riservata, da Punto di
Accesso o da area pubblica pagoPA per utenti non registrati. La prova tecnica
usabile nei servizi telematici è la ricevuta telematica `RT.xml`; il promemoria
PDF non sostituisce la RT quando il deposito richiede la ricevuta telematica.

Il software registra i seguenti codici di riscossione pubblicati nelle fonti
PST:

- `CONTRIB`: contributo unificato;
- `DIRCANC`: diritti di cancelleria;
- `DIRCOPIA`: diritti di copia;
- `CONTRBENI`: contributo pubblicazione avviso vendita;
- `UNPIG`: spese di notifica per pignoramento UNEP;
- `UNNOT`: spese di notifica UNEP.

Gli stati di pagamento gestiti sono:

- `DISPONIBILE`: pagamento concluso con RT positiva;
- `USATO`: ricevuta già utilizzata;
- `OK_PSP`: pagamento in attesa della RT dal prestatore di servizi di pagamento;
- `RIMBORSATO`: pagamento rimborsato.

Il software non deve interrogare il PST in polling continuo e non deve salvare
PIN, credenziali, sessioni CNS/CIE/SPID o dati portale. Se il pagamento è
frazionato devono essere conservate e inoltrate tutte le ricevute telematiche
riferite ai versamenti.

## Regole accertate PAT/SIGA

Per il PAT il pagamento del contributo unificato è trattato come quietanza F24
Elide da registrare nel deposito. I dati minimi da presidiare sono:

- data del versamento;
- estremi del versamento;
- importo versato;
- codice tributo;
- numero riga;
- elementi identificativi;
- copia informatica della quietanza.

Le istruzioni PAT pubblicano i codici `GA01`, `GA02`, `GA03`, `GA04`, `GA05` e
richiedono attenzione al numero riga quando l'F24 contiene più righe. Il
software deve chiedere revisione professionale per importo, esenzione,
riferimento ad altro ufficio e coerenza con il deposito.

## Regole accertate PTT/SIGIT

Per il processo tributario telematico la circolare MEF sul pagoPA CUT indica due
flussi:

- pagamento contestuale tramite link ricevuto nella PEC con numero `RGR/RGA`;
- pagamento successivo dall'Area personale del PTT, sempre con riferimento al
  numero `RGR/RGA`.

La fonte MEF indica l'abbinamento automatico del pagamento al ricorso o
all'appello. Il software non deve inventare un allegato sostitutivo quando il
SIGIT associa direttamente il pagamento; deve invece registrare il dato
operativo e chiedere conferma se manca il numero `RGR/RGA` o se il pagamento non
risulta riconciliato.

## Implementazione IUSENTRA

Le policy runtime vivono in `legal_deposit/payment_policies.py`.

Mappatura:

- `pst_pagopa_cu_diritti_spese`: PCT/SICID, PCT/SIECIC, SIGP/GDP e UNEP;
- `pat_f24_elide_contributo_unificato`: PAT/SIGA;
- `ptt_cut_pagopa`: PTT/SIGIT.

Ogni policy dichiara fonti ufficiali, documenti prova, codici riscossione,
campi richiesti e azione consigliata in caso di ricevuta mancante. Il validatore
di deposito guidato usa queste policy per produrre avvisi operativi invece di
messaggi generici.

## Calcolo importi e limiti prudenziali

Il software calcola il contributo unificato quando la fonte normativa salvata e
i dati inseriti consentono una regola certa: scaglione o importo fisso,
tipologia, grado, eventuale riduzione, maggiorazione o raddoppio.

Quando invece mancano dati del caso concreto, esenzioni, dichiarazioni di
valore, qualificazione del rito o informazioni necessarie al pagamento, il
software deve mostrare un warning professionale configurabile e non un importo
presunto. Il pagamento telematico resta governato dalla policy del canale:
PST/PCT con RT.xml, PAT/SIGA con quietanza F24 Elide, PTT/SIGIT con CUT pagoPA
collegato a RGR/RGA.
