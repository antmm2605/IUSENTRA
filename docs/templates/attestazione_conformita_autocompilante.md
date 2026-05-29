# Attestazione di conformità autocompilante

Template DOCX: `docs/templates/attestazione_conformita_autocompilante.docx`.

## Campi collegati al database

| Segnaposto | Fonte gestionale |
| --- | --- |
| `{{avvocato.full_name}}` | dati studio / profilo avvocato |
| `{{avvocato.codice_fiscale}}` | dati studio / profilo avvocato |
| `{{avvocato.foro}}` | dati studio / profilo avvocato |
| `{{documenti.elenco_attestazione}}` | documenti del fascicolo selezionati per notifica o attestazione |
| `{{procedimento.numero_rg}}` | fascicolo, numero R.G. |
| `{{procedimento.anno_rg}}` | fascicolo, anno R.G. |
| `{{notifica.luogo}}` | dati notifica o studio |
| `{{notifica.data}}` | data generazione attestazione |

## Regola operativa

Il generatore `pct.notifiche_legali.build_attestazione_conformita_payload`
compila il testo finale usando fascicolo, cliente, soggetti/parti, procedimento
e documenti. I documenti nativi, duplicati informatici, originali informatici o
già firmati digitalmente restano elencati ma non generano un'attestazione non
dovuta. I documenti estratti dal fascicolo informatico, ricevuti da
comunicazione di cancelleria o provenienti da scansione analogica richiedono
attestazione tracciata.

Se mancano campi essenziali, il payload restituisce `ok=false` e l'elenco
`missing_fields`; la UI deve chiedere integrazione allo studio prima di firma o
notifica.
