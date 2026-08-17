# Controllo Studio - verifica operativa del 17 agosto 2026

## Perimetro

La pagina precedentemente denominata `Regia Operativa` è stata resa un quadro operativo unico per scadenze, notifiche legali, comunicazioni, parcelle e incassi. L'intervento non modifica i flussi di deposito, notifica o invio PEC e non introduce mutazioni automatiche degli stati.

## Dati e azioni

- I presidi delle notifiche sono letti dal repository tenant-aware già usato dal relativo flusso e mostrano stato, avanzamento e prossima azione registrata.
- Parcelle e incassi usano lo stesso payload applicativo della pagina `Incassi e pagamenti`, con importi e date formattati per l'interfaccia italiana.
- Le azioni rapide aprono i flussi reali per preparare una notifica, creare una fattura, registrare un incasso e lavorare i pagamenti aperti.
- Le righe restano collegamenti alle pagine proprietarie: la pagina di controllo non duplica regole e non salva dati propri.

## Verifiche automatiche

- `python -m pytest tests/test_regia_controllo_studio.py tests/test_dashboard_panoramica.py tests/test_terminology_aliases.py tests/test_utf8_integrity.py -q`: 12 test superati.
- `npm --prefix frontend run typecheck`: superato.
- `python -m compileall pct web -q`: superato.
- `git diff --check`: superato, salvo avvisi di normalizzazione CRLF su file già presenti.

## Copia locale reale

La copia Docker su `http://127.0.0.1:8080` è stata ricostruita. Il container applicativo risultava `healthy` e `/api/pronto` ha risposto con `ok: true` e orario `Europe/Rome`.

La verifica visiva materiale nel browser integrato non è stata completata: il componente Windows necessario al controllo del browser ha restituito `helper_unknown_error: setup refresh had errors`. Per la regola anti falso-verde, il collaudo visivo resta esplicitamente non verificato su macchina reale; build e test automatici non lo sostituiscono.

## Presidio anti-regressione

`tests/test_regia_controllo_studio.py` verifica la lettura dei presidi notifica, la lista economica, i payload vuoti in errore e la presenza delle azioni principali nella superficie React.
