# Direttive salvate - notifiche legali PEC

Data consultazione: 24 maggio 2026. Aggiornamento operativo verificato il 26 maggio 2026.
Aggiornamento matrice probatoria: 2 giugno 2026.

Questo file conserva le direttive normative e tecniche usate dal software per il
flusso di notifica PEC, relata, firma digitale, allegati e deposito prova. Le
regole operative derivate sono implementate in `pct/notifiche_legali.py` e
protette dai test in `tests/test_notifiche_legali.py`.

Dal 2 giugno 2026 la prova di notifica è governata anche dalla matrice
obbligatoria salvata in
`docs/specs/ministero/NOTIFICHE_PEC_MATRICE_PROBATORIA_2026-06-02.md`.
`proof_bundle_id` non è prova sufficiente: il runtime deve validare
destinatario-per-destinatario e ricevuta-per-ricevuta, con PEC inviata,
relata, attestazioni, hash SHA-256, DatiAtto.xml quando dovuto, deposito prova
e audit come passaggi distinti.

## Fonti ufficiali consultate

| Ambito | Fonte | URL | Regola software |
| --- | --- | --- | --- |
| Notifica civile/amministrativa/stragiudiziale via PEC | Gazzetta Ufficiale, supplemento ordinario n. 38/L del 17 ottobre 2022, D.Lgs. 149/2022, note all'art. 12, art. 3-bis L. 53/1994 vigente | https://www.gazzettaufficiale.it/eli/gu/2022/10/17/243/so/38/sg/pdf | Oggetto PEC obbligatorio, uso di PEC da pubblici elenchi, atto allegato alla PEC, perfezionamento con RAC/RdAC, relata separata firmata digitalmente. |
| Attestazione di conformità civile | Gazzetta Ufficiale, supplemento ordinario n. 38/L del 17 ottobre 2022, art. 196-undecies disp. att. c.p.c. | https://www.gazzettaufficiale.it/eli/gu/2022/10/17/243/so/38/sg/pdf | Se la copia informatica è destinata alla notifica, l'attestazione di conformità viene inserita nella relazione di notificazione. |
| Specifiche tecniche DGSIA correnti | Ministero della giustizia, PST, Provvedimento DGSIA 7 agosto 2024 ex art. 34 D.M. 44/2011, efficace dal 30 settembre 2024, con rettifiche 16 settembre 2024 e 30 ottobre 2024 | https://pst.giustizia.it/PST/en/paginadettaglio.page?contentId=ACC3429 | Art. 21: PEC dell'ufficio e Comunicazione.xml; art. 22: avviso di disponibilità, URL sicuro e area download; art. 25: rilascio copie; art. 26: notificazioni avvocati, allegati, RAC/RdAC e DatiAtto.xml; art. 27: attestazione di conformità nella relata quando la copia è destinata alla notifica. |
| Matrice probatoria PEC/notifiche | Snapshot ufficiali 2 giugno 2026: PST specifiche 2024, L. 53/1994, D.P.R. 68/2005, D.M. 2 novembre 2005, CAD art. 48, ReGIndE, INI-PEC, INAD, XSD UNEP | `docs/specs/ministero/NOTIFICHE_PEC_MATRICE_PROBATORIA_2026-06-02.md` | Gli stati `PROOF_ACQUIRED`, `PROOF_DEPOSIT_REQUIRED` e `PROOF_DEPOSITED` richiedono bundle probatorio verificato, evidenze hashate, destinatari, domicilio digitale, PEC inviata, relata, ricevute positive per ogni destinatario, DatiAtto/deposito prova quando dovuti e audit. |
| Specifiche tecniche storiche | Ministero della giustizia, Provvedimento DGSIA 16 aprile 2014 e testo coordinato specifiche tecniche PCT | https://www.giustizia.it/giustizia/it/mg_1_8_1.wp?contentId=SDC1007352&facetNode_1=1_1%282014%29&facetNode_2=0_10&facetNode_3=0_10_37&facetNode_4=3_1_5&previsiousPage=mg_1_8 | Fonte storica sostituita dal provvedimento DGSIA 2024 per l'implementazione corrente; resta consultabile per compatibilità e confronto. |
| Notifica penale del difensore | Gazzetta Ufficiale, supplemento ordinario n. 38/L del 17 ottobre 2022 e supplemento straordinario n. 5 del 19 ottobre 2022, art. 56-bis disp. att. c.p.p. | https://www.gazzettaufficiale.it/eli/gu/2022/10/19/245/ss/5/sg/pdf | Relazione su documento informatico separato, sottoscritta con firma digitale o altra firma elettronica qualificata, allegata al messaggio; deposito di atto, relazione e ricevute. |
| Area web PST in caso di mancata notifica | L. 53/1994, art. 3-ter; nota DGSIA 14 novembre 2024 salvata in `docs/specs/ministero/prassi_notifiche/DGSIA_2024_11_12_istruzioni_modifiche_portale_area_web_notifiche.pdf` | https://www.ordineavvocatipavia.it/2025/02/05/attivazione-area-web-per-il-deposito-delle-notifiche-ai-sensi-dellart-3-ter-co-2-l-53-1994/ | Se la PEC non può essere eseguita o non ha esito positivo per causa imputabile al destinatario, il software prepara il percorso PST con atto/PEC, relata, avviso di mancata consegna EML e certificazione, senza dichiarare perfezionata la notifica quando la causa non è imputabile al destinatario. |
| Casistica operativa FIIF/ordini | Matrice FIIF/Ordine Pavia su artt. 137 c.p.c. e 3-ter L. 53/1994, salvata in `docs/specs/ministero/prassi_notifiche/FIIF_casistica_art_137_cpc_3ter_L53_area_web.pdf` | https://www.ordineavvocatipavia.it/wp-content/uploads/2025/02/Casistica-artt.-137-cpc-e-3-ter-co-2-3-L.-53-94.pdf | Fonte di prassi non sostitutiva della norma: distingue PEC funzionante, indirizzo assente/non PEC, casella satura, causa imputabile/non imputabile e casi art. 170/330 c.p.c. |
| Orario e perfezionamento PEC | Corte costituzionale, sentenza 75/2019 su art. 16-septies D.L. 179/2012; D.P.R. 68/2005 artt. 6 e 8 | https://www.cortecostituzionale.it/scheda-pronuncia/2019/75 | Per il notificante rileva la RAC anche nella fascia 21:00-24:00; per il destinatario resta la tutela oraria. Le notifiche automatiche 00:00-06:59 sono bloccate nel workflow salvo valutazione manuale. |
| Schemi XSD SICI aggiornati | Ministero della giustizia, PST, comunicazione software house 12 maggio 2026 e allegati salvati in `docs/specs/ministero/xsd/2026-05-12-sici/` | https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4871 | Gli schemi SICI 2026 restano disponibili offline per i controlli tecnici dei depositi collegati alla prova di notifica. La nota ufficiale indica modifica di `tipi-base.xsd` e dei codici oggetto, quindi ogni validazione DatiAtto/oggetto deve usare la fonte salvata più recente. |
| Timestamp verifica PEC e invio | Verifica del 26 maggio 2026 su L. 53/1994 art. 3-bis, D.L. 179/2012 art. 16-ter, Provvedimento DGSIA 7 agosto 2024 e Corte cost. 75/2019 | https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=094G0076&atto.dataPubblicazioneGazzetta=1994-01-26&bloccoAggiornamentoBreadCrumb=true&classica=true&dataVigenza=&generaTabId=true&qId=&tabID=&tipoDettaglio=multivigenza&title=lbl.dettaglioAtto ; https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=012G0201&atto.dataPubblicazioneGazzetta=2012-10-19&bloccoAggiornamentoBreadCrumb=true&classica=true&dataVigenza=&generaTabId=true&qId=&tabID=&tipoDettaglio=multivigenza&title=lbl.dettaglioAtto ; https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429 ; https://www.cortecostituzionale.it/scheda-pronuncia/2019/75 | Il campo visibile `Data e ora verifica PEC` è timestamp operativo di controllo del pubblico elenco e non sostituisce RAC/RdAC. Al click su invio PEC il software lo valorizza con data, ora, minuti e secondi locali se manca o se è in modalità automatica; il piano di invio usa `data_ora_invio_pec` per mostrare fascia oraria, scissione effetti e ricevute da conservare. |

## Regole runtime salvate

- Il trigger per un provvedimento dell'ufficio da notificare nasce dalla PEC
  dell'ufficio giudiziario, non dalla semplice presenza del documento nel
  fascicolo o dai soli metadati del portale.
- La PEC dell'ufficio deve essere conservata come evidenza originale: Message-ID,
  file `.eml` e SHA-256 quando disponibili.
- Il link al Portale Servizi deve essere precompilato con ufficio, fascicolo,
  numero R.G., anno R.G. e, quando nota, denominazione del documento.
- L'acquisizione deve riguardare il singolo documento comunicato e deve evitare
  duplicati con stesso identificativo portale, nome o hash.
- La relata deve essere generata come documento informatico separato e firmata
  prima dell'invio PEC.
- Il documento che il Local Signer deve selezionare automaticamente è
  `relata_notifica.pdf`; l'esito firma è `relata_notifica.pdf.p7m` in CAdES o
  `relata_notifica_firmata.pdf` in PAdES.
- Il provvedimento scaricato dal portale viene allegato alla PEC come documento
  notificato. Non viene rifirmato automaticamente dall'avvocato salvo direttiva
  specifica che lo classifichi come atto da sottoscrivere autonomamente.
- Se il provvedimento è copia informatica o documento acquisito, l'attestazione
  di conformità viene inserita nella relata firmata quando richiesta.
- Dopo l'invio si conservano PEC inviata, RAC e RdAC completa in originale
  digitale; questi elementi alimentano il deposito prova e i riferimenti in
  DatiAtto.xml.
- Gli stati prova notifica non sono più validati da una singola riga in
  `evidence_documents`: il software dereferenzia
  `notification_proof_bundles`, `notification_evidence_links`,
  `notification_recipients`, `notification_receipts`,
  `notification_relata`, `notification_proof_deposits` e
  `notification_dati_atto_receipt_refs`.
- `Data e ora verifica PEC` resta visibile nel percorso di notifica, viene
  alimentata automaticamente dall'orologio locale con precisione al secondo e
  rappresenta il momento operativo di verifica dell'indirizzo nel pubblico
  elenco. Non sostituisce le ricevute PEC: al momento dell'invio restano
  decisive PEC inviata, RAC e RdAC completa.
- Se la notifica PEC non può essere eseguita o non ha esito positivo per causa
  imputabile al destinatario, il software prepara il percorso area web PST ex
  art. 3-ter con atto/PEC, relata, avviso di mancata consegna EML e
  certificazione; se la causa non è imputabile al destinatario, non dichiara la
  notifica perfezionata e propone canale alternativo.
- L'orario di invio è controllato: fascia ordinaria 07:00-20:59, fascia
  21:00-23:59 con scissione degli effetti secondo Corte cost. 75/2019, fascia
  00:00-06:59 bloccata nel workflow automatico salvo conferma manuale fuori
  automatismo.

## Regola di manutenzione

Ogni aggiornamento futuro deve:

1. aggiungere o aggiornare qui la fonte normativa/tecnica;
2. indicare data di consultazione, ambito e limite della regola;
3. aggiornare le costanti o fixture runtime;
4. aggiungere test di regressione sulla casistica toccata;
5. aggiornare il PDF guida se la procedura visibile all'avvocato cambia.
