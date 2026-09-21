# PagoPA: punto di ripresa vincolante

## Prove già accettate, da non ripetere

Il cliente ha completato il pagamento dell'avviso 330008103520209603:
avviso € 21,50, conferma checkout € 21,78. Sono già documentati CAPTCHA,
trasporto del modulo, generazione dell'avviso, conservazione nel fascicolo
0BAABCE0 e checkout ufficiale. Non creare altri avvisi e non ripetere pagamenti.
Le prove editor/documenti sono in `pytest-documenti-pagopa-20260921.md`.

## Passaggi residui

- Precompilazione di nominativo e codice fiscale dall'anagrafica anche senza
  calcolo CU precedente: adattatore aggiunto; verifica della sola modifica nuova.
- Acquisizione RT: il proxy già archivia una RT scaricata con IUV e importo
  coerenti. La ricevuta del caso concreto non è ancora acquisita.
- Consolidamento del codice corretto server, CI e deploy verificato.
- Segnalazione OpenAI dopo la chiusura operativa, come richiesto.

Il servizio sperimentale `pagopa_pst_receipts.py` non è collegato: usa lettura
HTML automatica, vietata dalle istruzioni del repository. Non attivarlo.
Il canale applicativo ufficiale è `downloadRicevuta`, tramite servizi PST/PdA;
non sono ammesse interrogazioni periodiche continue. Fonte: Ministero,
«PDA – Flussi pagamento telematico tramite PST», versione 6.3, pp. 5–6:
https://pst.giustizia.it/PST/resources/cms/documents/PDA__Flussi_pagamento_telematico_tramite_PST_vers._6.3.pdf
WSDL già versionato: `A1_WSDL_CATALOG_v1.52/WSDL/Altri Servizi/Pagamenti Telematici/ServiziConsultazionePagamentiTelematici.wsdl`.

Il controllo CI rimasto aperto sulla proforma è stato corretto solo nel test:
client embedding controllato, lettura e persistenza reali, coda verificata vuota.
Singolo test e Ruff superati. Nessuna modifica al comportamento applicativo.

Hotfix precompilazione: prima della copia confrontata l'impronta del modulo API
con il container attivo; originale conservato in
`/opt/iusentra/backups/pagopa-prefill-20260921`. Ricaricamento graduale Gunicorn,
nessuna modifica ai dati dello studio. Firma, busta e PEC non modificati.

Individuata divergenza sorgenti/bundle: il commit di copia runtime aveva tolto
dal TSX l'integrazione PagoPaAvvisiPanel, pur conservandola nel bundle servito.
Ripristinato il solo diff di integrazione per preservare la UI alla prossima build.

Stato: aperto. Non ancora verificato su macchina reale per le modifiche nuove;
nessuna dichiarazione di deploy concluso o RT acquisita.

## Aggiornamento materiale del 21/09/2026, ore 22:21

Nel browser Chrome reale, fascicolo 0BAABCE0 in produzione, il modulo mostra
ora nominativo e codice fiscale compilati automaticamente dall'anagrafica.
Nessun invio del modulo e nessun nuovo pagamento. Corrette l'iniezione del
bridge nelle risposte XHTML e la compatibilità degli eventi con gli script
PST; compilazione dopo l'inizializzazione del modulo, solo sui campi vuoti.
Il singolo test proxy aggiornato per XHTML passa. La precedente prova del
pagamento resta valida: non è stata ripetuta.

La RT del caso concreto resta da acquisire; il codice fiscale debitore
dell'avviso recuperato non è presente nel dato storico. Non viene inventato
né sostituito silenziosamente con quello dell'anagrafica attuale.

## RT acquisita il 21/09/2026, ore 22:28

Il riepilogo originale `03-riepilogo-avviso.png`, già registrato durante la
prova del cliente, contiene il codice fiscale del debitore. Usato quel dato
per la ricerca assistita nel browser reale, il PST restituisce l'avviso con
stato «Disponibile» e collegamento «Download ricevuta». Nessuno scraping HTML.

Il proxy rifiutava i due endpoint ufficiali XML/PDF della RT: aggiunti alla
lista esatta dei percorsi consentiti, senza aprire altri endpoint del portale.
La RT originale scaricata è stata verificata e archiviata automaticamente:
documento `2278E1C7`, IUV `30008103520209603`, importo € 21,50,
avviso `330008103520209603`, stato SQL `ricevuta_acquisita`.
Non è stato effettuato un nuovo pagamento. Questa evidenza supera i precedenti
paragrafi che indicavano la RT ancora mancante. Il deploy resta da chiudere.
