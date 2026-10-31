# 2.467.0 — Fonti certe dalla PEC al fascicolo

Rilascio nato dalla verifica sulle PEC reali e sui fascicoli collegati (registro `docs/VERIFICA_PRODUZIONE_2026-10-31.md`, V19-V35).

- **Termine lungo (art. 327 c.p.c.) solo da fonte certa (V20)**: data dell'evento nel registro di cancelleria, sentenza nel fascicolo telematico (data del portale), testo della comunicazione, timbro della sentenza con lo stesso numero; mai la data di ricezione della PEC né quella di un precedente citato. Le bozze già calcolate dalla comunicazione si ricalcolano dal deposito o restano all'avvocato con l'avviso «data di deposito non certa», e si correggono da sole quando arriva la copia dal portale.
- **Provvedimento della PEC di cancelleria nel fascicolo (V30)**: il PDF del giudice entra tra i documenti come copia informativa, con provenienza e impronta, una sola volta, e avvia la lettura; la copia da notificare resta quella scaricata dal Portale dei Servizi Telematici.
- **Notifiche legali a evento (V19)**: l'elenco è una sola lettura; il riallineamento con le prove avviene quando nel fascicolo entra un documento o una PEC, solo per i suoi presìdi.
- **Testi italiani (V25-V26)**: accenti corretti in circa 40 testi; date e ore italiane al posto del formato tecnico in Template atti e Redazione atti.
- **Modello di catalogazione (V35)**: lettura tollerante della voce e risposte integrali nelle misure sul PC.
- **Lavoro**: regola obbligatoria in `AGENTS.md` (fonti certe, catena PEC-fascicolo, lavoro a evento, registro continuo); gate locale con blocchi del Pytest core in parallelo.

## Calcoli certi e collaudo normativo dei calcolatori (V37-V38)

- Lex risponde ai calcoli con i calcolatori di Strumenti legali: riconosce lo strumento, prende i dati
  dalla domanda dichiarando le ipotesi, chiede i dati mancanti con il messaggio del calcolatore e
  riporta risultato, dettaglio, note, avvertenze e fonti ufficiali (`lex/calcoli_certi`).
- Lex usa solo i calcolatori **collaudati sulla norma**: casi di riferimento ricavati dal testo
  ufficiale e confrontati con il software a ogni avvio (`pct/calcolatori/collaudo.py`,
  `pct/calcolatori/collaudo_casi/*.json`); per gli altri indica lo strumento senza dare numeri.
- Corretti dal collaudo: ravvedimento operoso (1/15 esatto), rateazione delle imposte (0,18% sulla
  seconda rata), imposta di registro (separazione e divorzio esenti; decreto ingiuntivo non esecutivo),
  pignoramento delle pensioni (doppio dell'assegno sociale, minimo 1.000 euro), usura (nessun verdetto
  senza il decreto del trimestre), variazioni ISTAT a un decimale, improcedibilità con motivazione
  contestuale, pena nei riti alternativi, custodia cautelare (interrogatorio a 10 giorni per le misure
  non carcerarie, proroga dei festivi), prescrizione civile (art. 2963, c. 3, c.c.), CTU (mezza
  vacazione), indennità di licenziamento (Corte cost. 118/2025), TFR, categoria F/7, quote di riserva,
  diffamazione, successione legittima (artt. 571 e 582 c.c.).
- Danno biologico: la tabella unica nazionale usa la tavola 1.B vigente alla data di liquidazione
  (D.M. MIMIT 10/12/2025 e 28/09/2026) e riproduce tutte le celle pubblicate nell'allegato II;
  usufrutto con il saggio minimo del 2,5%. Entrambi sono ora fra i collaudati usati da Lex.
- Lex assegna date, età, punti e giorni al campo che la domanda nomina; un numero ambiguo lo chiede.
- Il «Maggior danno da svalutazione» diventa «Rivalutazione e interessi sui crediti di valore»
  (Cass. SS.UU. 1712/1995), con la variazione ISTAT a un decimale e l'avviso sui debiti di valuta
  (art. 1224, c. 2, c.c.; Cass. SS.UU. 19499/2008). È fra i collaudati usati da Lex.
- Interessi legali e mora commerciale con la serie storica completa dai testi ufficiali: saggio legale
  dal 1942, mora D.Lgs. 231/2002 dall'08/08/2002 (riferimento BCE +7 fino al 2012, +8 dal 2013), ogni
  periodo con decreto o comunicato in Gazzetta. Prima i calcoli su crediti anteriori al 2024 coprivano
  solo gli ultimi anni.
- Mora commerciale: nuovo campo «Data del contratto». Per i contratti anteriori al 2013 la maggiorazione
  resta di 7 punti anche nei semestri successivi (art. 3 D.Lgs. 192/2012); i contratti anteriori
  all'08/08/2002 sono fuori dal decreto (art. 11). Se la data manca, il calcolo lo segnala.
- Collaudati anche la rivalutazione su media annua ISTAT (variazione a un decimale), la tabella ISTAT
  (indice come pubblicato, con la base 2025 dal 2026, e campo «Fino all'anno»), la tabella dei tassi e
  gli uffici competenti.
- Contributi Cassa Forense collaudati sul Regolamento unico (G.U. 238/2024) e sulla tabella dei minimi:
  corretti i valori 2025 (aliquota 16%, minimi 2.750 e 350 euro, maternità 57,65) e il metodo
  (soglia di copertura, tetto con 3% oltre, minimi ridotti, pensionati, soglia dei 10 euro); la
  maternità 2026 non ancora pubblicata è segnalata e il totale è provvisorio.
- Mantenimento e lite temeraria sono ora stime motivate, non formule: presupposti, conti e valutazioni
  separati, scheda di calcolo e tre stati (dati insufficienti, stima da verificare, proposta validata).
  Mantenimento in tre percorsi (figli art. 337-ter, separazione art. 156, divorzio art. 5 L. 898/1970);
  lite temeraria con comma 3 secondo l'Osservatorio di Milano 2024, prospetto danni dei commi 1-2 e
  comma 4 a favore della Cassa delle ammende per i procedimenti instaurati dopo il 28/02/2023.
- Strumenti legali è solo React: la vecchia vista Jinja è stata eliminata.

## Udienze passate e agenda del fascicolo (V28, V40)

- Regola unica (`pct/scadenze_stato.py`) per scadenziario, viste e barra in alto: un'udienza passata
  è «esito da registrare», non «scaduta»; nuova vista e riquadro dedicati.
- L'esito si registra da solo quando la cancelleria lo comunica (`pct/esito_udienza.py`): rinvio,
  provvedimento o sentenza letti dalla PEC dal giorno dell'udienza in poi; nota con la fonte.
- Agenda del fascicolo: scadenze e appuntamenti in un'unica linea del tempo, gli stessi dell'agenda
  principale.

## Indici ISTAT automatici (V39)

- Gli indici FOI si scaricano dal servizio ufficiale ISTAT (esploradati.istat.it) nel lavoro notturno
  delle tabelle normative, solo se manca un mese già pubblicato; controlli su valori, continuità e
  rettifiche. Prova reale del 31/10/2026: luglio, agosto e settembre 2026 importati.
