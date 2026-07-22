# Registro fonti e criteri del presidio notifiche

Data di prima compilazione: 20/07/2026  
Ambito: PEC, notifiche legali, provvedimenti, udienze, Agenda e Scadenziario.  
Stato: fonte di lavoro versionata; ogni nuova regola automatica deve aggiungere o aggiornare una riga.

## Scopo

Questo registro impedisce che il presidio trasformi parole chiave o consuetudini in decisioni giuridiche. Una regola applicata dal software deve sempre identificare la fonte, il rito, il fatto generatore, la prova richiesta, il limite e il comportamento prudente quando l'informazione non è completa.

Le Guide Pratiche, gli studi professionali e i repertori sono fonti-radar: fanno emergere fattispecie, documenti, varianti e controlli. Non sono sufficienti da soli per abilitare una scadenza perentoria, dichiarare una notifica eseguita o chiudere un presidio.

## Principi invarianti

1. Una comunicazione della cancelleria è fonte dell'evento, non prova di una notifica di parte.
2. Una sentenza con formula `definitivamente decidendo` non è per questo già passata in giudicato.
3. Il termine breve civile non nasce dalla sola comunicazione del deposito: occorre la notificazione della sentenza nei termini e con la prova prescritta.
4. RAC e RdAC devono essere collegate allo stesso invio, atto e destinatario; la sola RAC non chiude la prova verso il destinatario.
5. Rito civile, lavoro, amministrativo, penale e tributario sono canali distinti: non si trasferiscono automaticamente termini, forma di deposito o stato della prova.
6. Se fonte, fatto generatore, destinatario o prova sono ambigui, il motore crea una revisione professionale e non una falsa certezza.

## Fonti primarie e relativo uso nel software

| Chiave | Fonte ufficiale | Regola applicabile | Limite operativo obbligatorio |
|---|---|---|---|
| `cpc.sentenza.comunicazione` | [Art. 133 c.p.c. e testo vigente del c.p.c.](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443) | Comunicazione del deposito della sentenza: esame del provvedimento, non termine breve automatico | non creare termine art. 325 da XML/PEC di cancelleria soltanto |
| `cpc.impugnazioni` | [Artt. 285, 324-327 c.p.c.](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443) | distinguere notifica sentenza, termine breve, termine lungo e giudicato | notificazione, perfezionamento, destinatario e prova devono risultare dal fascicolo/PEC |
| `cpc.127bis_127ter` | [D.Lgs. 149/2022 e testo vigente c.p.c.](https://www.gazzettaufficiale.it/atto/serie_generale/caricaArticoloDefault/originario?atto.codiceRedazionale=22G00159&atto.dataPubblicazioneGazzetta=2022-10-17&atto.tipoProvvedimento=DECRETO+LEGISLATIVO) | udienza da remoto/trattazione scritta, richiesta o opposizione, note | quando il documento contiene una sentenza decisoria, le regole 127-ter non generano una falsa opposizione residua |
| `cpc.rinvii_memorie_prove` | [Artt. 171-bis, 171-ter, 183, 210 e 421 c.p.c.](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443) | rinvio/fissazione udienza, memorie, esibizioni e regolarizzazioni | sono attività/termini processuali, non notifiche salvo ordine espresso |
| `cpc.lavoro_sentenza` | [L. 533/1973, art. 429 c.p.c.](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=073U0533&atto.dataPubblicazioneGazzetta=1973-09-13&qId=&tipoDettaglio=multivigenza) | sentenza nel rito lavoro e fase decisoria | una sentenza a verbale prevale sulla classificazione come sola udienza o trattazione scritta |
| `cpc.lavoro_esecuzione_appello` | [Artt. 430, 431 e 433 c.p.c.](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443) | deposito, esecutività provvisoria e appello nel lavoro | esecutorietà provvisoria non equivale a giudicato; ogni termine richiede il relativo fatto generatore |
| `cpc.monitorio` | [Artt. 641-645 c.p.c.](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443) | decreto ingiuntivo, notifica, inefficacia e opposizione | il lato assistito decide se presidiare notifica del decreto oppure opposizione; verifica dei termini speciali obbligatoria |
| `cpc.cautelare_esecuzione` | [Artt. 479-481, 615, 617 e 669-terdecies c.p.c.](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443) | titolo/precetto, opposizioni esecutive e reclamo cautelare | non segnare una procedura esecutiva pronta senza titolo, precetto e rispettive prove quando richieste |
| `l53.pec.notifica` | [PST Ministero - notificazioni via PEC ex L. 53/1994](https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC432&modelId=12) | oggetto PEC, atto, procura, relata separata firmata, RAC, RdAC completa e deposito della prova | una comunicazione D.L. 179/2012 dell'ufficio non è una notifica L. 53 dell'avvocato |
| `l53.pec.comunicazioni_ufficio` | [PST Ministero - comunicazioni/notificazioni telematiche dell'ufficio](https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC431&modelId=12) | distinguere l'avviso di cancelleria dai documenti/receipts dello studio | estrarre l'evento contenuto, ma non inventare relata o ricevute di parte |
| `scuola.carta_docente` | [L. 107/2015, art. 1](https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=15G00122&atto.dataPubblicazioneGazzetta=2015-07-15&bloccoAggiornamentoBreadCrumb=true&classica=true&dataVigenza=&generaTabId=true&qId=c793b688-d8be-46f8-8554-18de7a041b5e&tabID=0.7342511807781263&tipoDettaglio=vigente&title=lbl.dettaglioAtto) e [CGUE C-450/21](https://infocuria.curia.europa.eu/tabs/redirect/juris/liste.jsf?num=C-450%2F21) | riconoscere condanne Carta docente e separare annualità, adempimento e spese processuali | la sentenza non prova l'avvenuto accredito; creare monitoraggio dell'adempimento, non incasso fittizio |
| `amministrativo.pat` | [Codice del processo amministrativo - D.Lgs. 104/2010](https://www.gazzettaufficiale.it/sommario/codici/processoAmministrativo) e [documentazione PAT ufficiale](https://www.giustizia-amministrativa.it/documents/20142/80293801/PAT%2BIstruzioni%2Bper%2BCompilazione%2BModuli%2BDeposito%2Bv9.6.1.pdf/a6915702-14e9-9ef8-341a-732b28976bb9?t=1749058391879) | canale PAT distinto per ricorso, notifica, deposito, memorie e udienze | se manca un ruleset PAT specifico, stato `amministrativo_pat_da_verificare`, mai termine civile di comodo |
| `penale.pdp` | [PST - deposito atti giudiziari](https://servizipst.giustizia.it/PST/it/pst_1_2.wp), [PST - PDP](https://pst.giustizia.it/PST/page/it/avvocati_consultazione_da_remoto_dei_fascicoli_del_pm?contentId=NWS2339&modelId=4), [Procura di Padova - indicazioni PDP](https://procura-padova.giustizia.it/it/deposito_atti_penali.page) | canale PDP per atti e depositi penali; separazione dalla PEC civile | PEC può essere inefficace fuori dalle deroghe applicabili; non simulare un deposito PDP o una notifica penale |
| `civile.mora_prescrizione` | [Codice civile, artt. 1219, 2943 e 2953](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262) | eventuale messa in mora, interruzione prescrizione e giudicato | generare solo presidio da valutare: efficacia, prescrizione e natura dell'obbligazione richiedono dati/fonte completi |

## Fonti-radar interne e professionali

| Fonte | Funzione ammessa | Funzione non ammessa |
|---|---|---|
| Guida Pratica IUSENTRA | inventario di riti, atti, termini, allegati, avvertimenti e casi; supporto al recupero dal fascicolo | sostituire il codice ufficiale del fascicolo o rendere perentorio un termine non validato |
| AvvocatoAndreani e altri studi/repertori | rilevare casi pratici, check-list, alternative di rimedio, parole o documenti da intercettare | essere unica fonte di un automatismo legale |
| PDF/PEC/fascicolo dello studio | accertare fatti, date, parti, attestazioni e prove del caso concreto | dedurre una regola generale senza riscontro normativo |

## Campi minimi di ogni regola eseguibile

```text
id_regola, versione, fonte, articolo, rito/canale, evento_generatore,
evidenze_minime, dati_indispensabili, dies_a_quo, durata, natura_termine,
azione_agenda, azione_scadenziario, azione_presidio, stato_prova,
esclusioni, confidenza, revisione_umana, comportamento_se_dato_manca.
```

Nessuna regola che manca di `fonte`, `evento_generatore`, `evidenze_minime` o `comportamento_se_dato_manca` può creare automaticamente un termine decadenziale, una dichiarazione di notifica eseguita o una chiusura definitiva.

## Collegamento obbligatorio tra regole e fonti

Le chiavi eseguibili del rulepack sono censite in
`pct/data/legal_sources_registry.json`, sezione `notification_sources`. Dal
20/07/2026 il caricamento del rulepack verifica che ogni `legal_sources` sia
presente in quel catalogo: una fonte mancante ferma il caricamento e il test
di regressione. Per il caso sentenza/impugnazioni sono registrate almeno le
chiavi `src.it.cpc.art133`, `src.it.cpc.art285`, `src.it.cpc.art324`,
`src.it.cpc.art325`, `src.it.cpc.art326`, `src.it.cpc.art327`,
`src.it.cpc.art429`, `src.it.cpc.art431`, `src.it.cpc.art91`,
`src.it.cpc.art93` e `src.it.l107_2015.art1c121`.

Lo stato `acquisition_required` non autorizza un automatismo nuovo: indica
che l'URL ufficiale e il suo ambito sono stati censiti, ma prima della
promozione di una nuova regola perentoria occorre salvare e verificare lo
snapshot ufficiale con hash SHA-256. Il controllo separa quindi due domande:
la regola cita una fonte identificata? La copia locale della fonte e' stata
verificata?

## Manutenzione

- A ogni modifica normativa, riforma o nuova prassi ministeriale: verificare la fonte primaria, aggiornare data/versione e aggiungere test del caso precedente e del caso nuovo.
- A ogni nuovo scenario trovato nelle Guide o nella pratica dello studio: registrarlo dapprima come caso-radar, poi promuoverlo a regola soltanto dopo validazione.
- Il job di validazione usa le regole già compilate e materializza l'esito. Le pagine React non consultano né scansionano le fonti durante il caricamento.
