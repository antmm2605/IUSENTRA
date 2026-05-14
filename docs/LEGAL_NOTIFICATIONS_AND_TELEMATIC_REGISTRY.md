# Notifiche legali, prova notifica e registry procedimenti

Documento operativo per il modulo notifiche PEC ex L. 53/1994, comunicazioni cliente, deposito prova notifica e registry procedimenti telematici.

## Principi fail-closed

- Canale, portale, registro e procedimento devono essere espliciti e censiti.
- `pct`, `pst`, `pct_pst` e canali generici non selezionano automaticamente un profilo produttivo.
- Se il canale e' sconosciuto viene sollevata `UnknownChannelError`.
- Se il procedimento e' sconosciuto viene sollevata `UnknownProcedureError`.
- Se procedimento e motore deposito non coincidono viene sollevata `ProcedureProfileMismatchError`.
- `portal_upload` resta disponibile solo se richiesto come profilo manuale, non come fallback automatico.
- Nessuna notifica o deposito definitivo viene generato se i controlli essenziali sono incompleti.

## Differenza tra flussi

| Flusso | Operazione | Output | Blocchi principali |
| --- | --- | --- | --- |
| Notifica PEC L. 53/1994 | `notifica_pec_l53` | Oggetto PEC vincolato, relata separata, corpo PEC, checklist, log e piano output | Avvocato abilitato, PEC mittente validata, fonte pubblica PEC destinatario, data/ora verifica, relata firmata, ricevuta completa, documenti e attestazioni |
| Deposito prova notifica | controllo prova deposito | Evidence pack, distinta prova notifica e scheda esito | Atto, relata firmata, PEC inviata, RAC, RdAC completa e hash SHA-256 |
| Comunicazione cliente | `comunicazione_cliente_non_notifica` | Oggetto e corpo informativo cliente | Nessuna relata, nessun oggetto L. 53, nessun trattamento come notifica |
| Area web PST notifica fallita | workflow manuale PST | Evidence pack per causa imputabile al destinatario | Valutazione avvocato obbligatoria, avviso mancata consegna, nessuna dichiarazione di perfezionamento se la causa non e' imputabile al destinatario |

## Notifica PEC L. 53/1994

Il motore ammesso e' `pct.notifiche_legali.validate_legal_notification`.

Requisiti bloccanti:

- `operazione = notifica_pec_l53`;
- mittente avvocato abilitato;
- PEC mittente presente, censita e validata;
- PEC destinatario presente;
- PEC destinatario estratta da pubblico elenco;
- fonte PEC destinatario indicata;
- data e ora verifica PEC indicate;
- oggetto PEC esatto: `notificazione ai sensi della legge n. 53 del 1994`;
- relata generata come documento separato;
- relata firmata digitalmente;
- ricevuta richiesta completa;
- almeno un documento allegato;
- uno o piu' documenti possono essere selezionati dal fascicolo e vengono riportati automaticamente nell'elenco allegati della relata;
- origine di ogni documento riconosciuta;
- attestazione di conformita' presente quando richiesta.

Errori principali:

- `OPERATION_REQUIRED`;
- `AVVOCATO_ABILITATO_REQUIRED`;
- `PEC_MITTENTE_VALIDATA_REQUIRED`;
- `PEC_DESTINATARIO_FONTE_REQUIRED`;
- `PEC_DESTINATARIO_VERIFICA_REQUIRED`;
- `L53_SUBJECT_REQUIRED`;
- `RELATA_SEPARATA_REQUIRED`;
- `RELATA_FIRMATA_REQUIRED`;
- `RICEVUTA_COMPLETA_REQUIRED`;
- `ATTESTAZIONE_REQUIRED`.

Il modulo legacy `pct.notifica.py` resta importabile per compatibilita', ma ogni chiamata produttiva solleva `LegacyNotificaTelematicaDeprecata`.

## Attestazioni di conformita'

Origini che non richiedono attestazione:

- `nativo_digitale`;
- `firmato_digitalmente`;
- `originale_informatico`;
- `duplicato_informatico`.

Origini che richiedono attestazione:

- `copia_fascicolo_informatico`;
- `comunicazione_cancelleria`;
- `scansione_analogico`;
- attestazione multipla quando piu' documenti richiedono dichiarazioni coordinate.

Se manca attestazione testuale o dichiarazione esplicita tracciata, il flusso si blocca con `ATTESTAZIONE_REQUIRED`.

## Template relata

Il catalogo vive in `pct/data/notifiche_legali_templates.json` e contiene almeno i modelli 01-34 richiesti:

01 `RELATA_PEC_BASE`, 02 `RELATA_A_DIFENSORE_COSTITUITO`, 03 `RELATA_A_CONTROPARTE_PERSONALMENTE`, 04 `RELATA_A_IMPRESA_SOCIETA`, 05 `RELATA_A_PROFESSIONISTA_INIPEC`, 06 `RELATA_A_PUBBLICA_AMMINISTRAZIONE`, 07 `RELATA_A_CURATORE_COMMISSARIO_LIQUIDATORE`, 08 `RELATA_PROVVEDIMENTO_GIUDICE`, 09 `RELATA_SENTENZA_TERMINE_BREVE`, 10 `RELATA_DECRETO_INGIUNTIVO`, 11 `RELATA_TITOLO_ESECUTIVO_PRECETTO`, 12 `RELATA_ATTO_STRAGIUDIZIALE`, 13 `RELATA_RINNOVO_NOTIFICA`, 14 `RELATA_INTEGRAZIONE_CONTRADDITTORIO`, 15 `RELATA_CHIAMATA_TERZO`, 16 `RELATA_RIASSUNZIONE`, 17 `RELATA_APPELLO_IMPUGNAZIONE`, 18 `RELATA_RECLAMO_CAUTELARE`, 19 `RELATA_SFRATTO_CONVALIDA`, 20 `RELATA_PIGNORAMENTO_PRESSO_TERZI`, 21 `RELATA_INTERVENTO_ESECUZIONE`, 22 `RELATA_OPPOSIZIONE_DECRETO_INGIUNTIVO`, 23 `RELATA_OPPOSIZIONE_ESECUTIVA`, 24 `RELATA_FAMIGLIA_PERSONE_MINORI`, 25 `RELATA_PROVVEDIMENTO_URGENTE`, 26 `RELATA_ACCORDO_TRANSAZIONE_STRAGIUDIZIALE`, 27 `CORPO_PEC_STANDARD`, 28 `CHECKLIST_PRE_INVIO`, 29 `LOG_GENERAZIONE_RELATA`, 30 `SCHEDA_ESITO_NOTIFICA`, 31 `DISTINTA_PROVA_NOTIFICA`, 32 `COMUNICAZIONE_CLIENTE_NON_NOTIFICA`, 33 `NOTA_MANCATA_CONSEGNA`, 34 `WORKFLOW_DEPOSITO_AREA_WEB_PST`.

Ogni template dichiara:

- id stabile, codice, label e categoria;
- campi obbligatori;
- blocchi condizionali;
- regole di validazione;
- `human_review_required`;
- output previsto;
- compatibilita' con ruoli destinatario e origini documento.

## Evidence pack

Per ogni notifica/deposito il pacchetto prova contiene:

- atto notificato;
- allegati;
- relata firmata se notifica;
- PEC inviata;
- RAC;
- RdAC completa;
- avvisi di errore o mancata consegna;
- log JSON;
- hash SHA-256;
- distinta prova notifica;
- scheda esito.

Gli elementi essenziali senza file o hash bloccano il controllo prova con `EVIDENCE_PACK_REQUIRED`.

## Limiti PTT/SIGIT

Il profilo `ptt_sigit` applica:

- massimo 10 MB per singolo file;
- massimo 50 file;
- massimo 50 MB totali;
- nome file massimo 100 caratteri;
- PDF/A-1a o PDF/A-1b;
- firma digitale quando richiesta.

PDF/A mancante o non valido blocca il deposito. Un file firmato `.p7m` di cui non e' verificabile automaticamente il PDF/A richiede revisione manuale tracciata.

## Registry procedimenti supportati

Il registry ufficiale vive in `legal_deposit/procedure_registry.py`.

PCT/SICID:
`PCT_SICID_CIVILE_ORDINARIO`, `PCT_SICID_LAVORO`, `PCT_SICID_PREVIDENZA`, `PCT_SICID_FAMIGLIA`, `PCT_SICID_MINORI`, `PCT_SICID_VOLONTARIA_GIURISDIZIONE`, `PCT_SICID_IMMIGRAZIONE`, `PCT_SICID_DECRETO_INGIUNTIVO`, `PCT_SICID_OPPOSIZIONE_DI`, `PCT_SICID_APPELLO`, `PCT_SICID_RECLAMO`, `PCT_SICID_CAUTELARE`.

PCT/SIECIC:
`PCT_SIECIC_ESECUZIONE_MOBILIARE`, `PCT_SIECIC_ESECUZIONE_IMMOBILIARE`, `PCT_SIECIC_PIGNORAMENTO_PRESSO_TERZI`, `PCT_SIECIC_INTERVENTO_CREDITORE`, `PCT_SIECIC_OPPOSIZIONE_ESECUTIVA`, `PCT_SIECIC_PROCEDURE_CONCORSUALI`, `PCT_SIECIC_CRISI_IMPRESA`.

SIGP/GDP:
`SIGP_GDP_ATTO_INTRODUTTIVO`, `SIGP_GDP_ATTO_SUCCESSIVO`, `SIGP_GDP_OPPOSIZIONE_SANZIONE`, `SIGP_GDP_DECRETO_INGIUNTIVO`, `SIGP_GDP_SINCRONIZZAZIONE_FASCICOLO`.

UNEP:
`UNEP_RICHIESTA_NOTIFICA`, `UNEP_RICHIESTA_ESECUZIONE`, `UNEP_RICHIESTA_492_BIS`, `UNEP_RESTITUZIONE_SOMME`, `UNEP_INTEGRAZIONE_PAGAMENTO`, `UNEP_PAGAMENTO_RICHIESTA`.

PAT:
`PAT_RICORSO_INTRODUTTIVO`, `PAT_ATTO_SUCCESSIVO`, `PAT_MOTIVI_AGGIUNTI`, `PAT_ISTANZA_CAUTELARE`, `PAT_MEMORIA`, `PAT_DOCUMENTI`, `PAT_RICHIESTA_SEGRETERIA`, `PAT_AUSILIARIO_GIUDICE`, `PAT_PARTE_NON_RITUALE`, `PAT_ISTANZA_ANTE_CAUSAM`, `PAT_RICHIESTA_RIMBORSO`.

PTT/SIGIT:
`PTT_RICORSO`, `PTT_APPELLO`, `PTT_CONTRODEDUZIONI`, `PTT_MEMORIA`, `PTT_DOCUMENTI`, `PTT_ISTANZA`, `PTT_DEPOSITO_SUCCESSIVO`, `PTT_CUT_PAGOPA`, `PTT_CONSULTAZIONE_FASCICOLO`, `PTT_TELECONTENZIOSO`, `PTT_UDIENZA_A_DISTANZA`.

PDP:
`PDP_DEPOSITO_ATTO_PENALE`, `PDP_ATTO_SUCCESSIVO`, `PDP_RICHIESTA_ACCESSO_ATTI`, `PDP_CONSULTAZIONE_FASCICOLO_PM`, `PDP_AVVISI_ATTI_CANCELLERIA`.

PST area web e altri portali:
`PST_AREA_WEB_NOTIFICA_MANCATA_CAUSA_DESTINATARIO`, `PST_AREA_WEB_DEPOSITO_ATTO_NOTIFICATO`, `PST_AREA_WEB_PERFEZIONAMENTO_NOTIFICA`, `TRIBUNALE_ONLINE_VOLONTARIA_GIURISDIZIONE`, `LSG_PATROCINIO_SPESE_STATO`, `LSG_DIFENSORE_UFFICIO`, `LSG_ISTANZA_LIQUIDAZIONE`, `PVP_PUBBLICAZIONE_AVVISO`, `CLASS_ACTION_AZIONE_CLASSE`, `CLASS_ACTION_ADESIONE`.

## Aggiungere nuovi procedimenti

1. Aggiungere una voce a `PROCEDURE_REGISTRY` con id stabile e tutti i campi obbligatori.
2. Associare il `deposit_engine` a un profilo esistente in `legal_deposit.policies`, oppure creare un nuovo profilo esplicito.
3. Non usare `portal_upload` come fallback automatico.
4. Aggiungere test per id sconosciuto, mismatch portale/registro/motore, documenti obbligatori e regole PDF/A/firma/pagamento.
5. Aggiornare questo documento e i test mirati prima del deploy.
