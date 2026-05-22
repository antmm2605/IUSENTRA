# Check no fake React full

Generato: 2026-05-15T12:13:18.632Z

Violazioni: 0

Nessuna route piena risulta mascherata da legacy.

## Aggiornamento 2.248.12 - 2026-05-22

Il preset grafico globale non promuove route finte: la pagina Fascicoli usa API
e dati reali già presenti, mentre il lavoro grafico centralizza struttura,
token, DataSurface e SupportRail. `/sito-studio/builder` resta esplicitamente
fuori dal preset e non viene mascherato da shell alternativa.

## Aggiornamento 2.243.4 - 2026-05-16

`/ricerca-legale/mediazione` e `/legal-intelligence/mediazione` confermate come
superfici React operative con dati reali: API autenticata 3.038 schede, 3.035
righe ministeriali importate, nessun fallback mock/demo. Il test
`test_mediazione_importata_non_viene_deduplicata_come_solo_link` blocca il
ritorno alla pagina di soli collegamenti.

## Aggiornamento 2.239.1 - 2026-05-15

`/sito-studio/builder` confermato come superficie React operativa: le azioni di
pagine, blocchi, media, tema, conformita', AI e pubblicazione usano API reali,
non placeholder. Il gate `node frontend\scripts\check-react-contracts.mjs`, il
route gate e l'audit CDP builder sono verdi.
