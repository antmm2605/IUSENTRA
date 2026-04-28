# Deposito telematico: preparazione autonoma con validazione consapevole

IUSENTRA prepara il deposito in modo guidato e tracciabile, ma non sostituisce mai la validazione finale dell'avvocato.

## Principio operativo

Il software puo':
- selezionare documenti e allegati;
- eseguire precontrolli deterministici;
- generare manifest e pacchetto locale;
- proporre firma secondo la policy del canale;
- inviare tramite canale abilitato o guidare l'upload manuale;
- monitorare ricevute, errori e scarti.

L'avvocato deve sempre visualizzare il riepilogo e confermare consapevolmente prima di firma o invio reale.

## Profili canale

I profili sono definiti in `legal_deposit.policies` e distinguono regole tecniche e limiti:

- `pct_pst`: PCT/PST civile, busta e PEC di deposito.
- `pec_stragiudiziale`: invio PEC ordinario con ricevute.
- `notifiche_pec`: notifiche via PEC, separate dalla PEC stragiudiziale.
- `pat_siga`: amministrativo, preparazione/upload guidato.
- `ptt_sigit`: tributario, preparazione/upload guidato.
- `pdp_penale`: Processo Penale Telematico tramite PDP/PST.
- `upload_manuale_guidato`: pacchetto e checklist per upload non automatizzabile.
- `portal_upload`: profilo generico di fallback per portali.

Ogni profilo dichiara: firma richiesta, formato firma, XML/metadati, PDF/A, dimensioni, ricevute attese e se l'upload finale resta manuale.

## Palmi e PDP penale

La regola locale del Tribunale di Palmi e' configurata in `legal_rules/ppt_office_rules.json`.

Il sistema:
- raccomanda PAdES `.pdf`;
- segnala avviso forte su CAdES `.p7m`;
- non dichiara il `.p7m` illegittimo, perche' il profilo nazionale PDP resta configurato come ammissivo per PAdES e CAdES;
- salva la fonte interna della regola nel campo `local_office_rule_source`.

Per altri uffici italiani, la regola resta configurabile e non viene estesa automaticamente senza fonte locale o nazionale verificata.

## Controllo altri uffici

Il registro include anche uffici verificati senza estendere l'avviso forte Palmi:

- Locri: fonte ufficiale Procura di Locri, PAdES e CAdES ammessi.
- Taranto: fonte ufficiale Procura di Taranto, PAdES e CAdES ammessi.
- Bari: fonte ufficiale Procura di Bari, PAdES o CAdES ammessi; PEC residuale solo se PDP inagibile.

Queste regole confermano il comportamento nazionale prudente: fuori da una regola locale specifica, il sistema non blocca CAdES e non presenta PAdES come unico formato legittimo.

## PDP/PST e APP

Nel penale, PDP/PST sono trattati come canali del difensore. APP e' indicato come sistema interno degli uffici giudiziari e non viene presentato come canale operativo del difensore.

## Sicurezza

- Nessun PIN token viene salvato.
- Nessuna credenziale PEC viene loggata.
- In sviluppo/test nessun invio reale parte senza feature flag espliciti.
- I file sono validati prima del pacchetto.
- Il manifest contiene hash SHA-256 e risultati dei controlli.
