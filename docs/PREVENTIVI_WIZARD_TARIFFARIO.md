# Preventivi wizard e tariffario

Il wizard preventivi usa il motore tariffario backend. Il frontend React non replica formule su importi tabellari, scaglioni, CPA, IVA, spese generali o maggiorazioni.

## Endpoint

- `GET /preventivi/wizard`
- `GET /api/v1/ui/preventivi/wizard`
- `POST /api/v1/ui/preventivi/wizard/calculate`
- `POST /api/v1/ui/preventivi/wizard/create`

Il fallback tecnico resta disponibile con `?_legacy=1`.

## Payload conservato

Il calcolo e la creazione preventivo conservano:

- regola tariffaria e codice regola;
- tabella applicata e label tabella;
- scaglione, inclusa fascia `Oltre EUR 520.000`;
- complessita, inclusa `molto_alta`;
- `audit_tariffario`;
- `reference_codes` e riferimenti normativi leggibili;
- `log_calcolo` sincronizzato per preventivo, accettazione, conferimento e flussi economici successivi.

I preventivi legacy senza audit continuano a essere caricati; quando e' possibile, il log viene arricchito in modo retrocompatibile.

## Creazione preventivo

La route `/api/v1/ui/preventivi/wizard/create` non crea bozze tabellari a zero quando il motore ha prodotto righe `motore` ma l'importo e' nullo. In quel caso ritorna un warning/blocco esplicito. Le voci manuali restano consentite solo come voci manuali non tabellari, chiaramente distinte dalla sorgente `motore`.

## UI

La UI mostra:

- tipologia pratica, regola, tabella, scaglione e grado/sede;
- badge `Snapshot esatto`, `Ricostruzione dichiarata`, `Fallback tecnico`, `Fascia alta`, `Valore indeterminabile`, `ADR`, `Compenso unico` o `Per fasi`;
- riferimenti normativi e audit nella sidebar;
- opzione `Molto alta`, descritta come valore indeterminabile parametrizzato oltre EUR 520.000.

La warning copy per `molto_alta` chiarisce che il valore e' parametrizzato e va verificato prima dell'invio al cliente.

## Mediazione DM 150/2023

Il wizard mantiene separati:

- compenso professionale ADR da tabella `A27`;
- costi organismo mediazione D.M. 150/2023, gia' gestiti dal runtime `web/services/mediazione_dm150_runtime.py`.

Non vengono duplicati importi o logiche del runtime ODM.

## Test

```bash
python -m pytest tests/test_preventivi_wizard_tariffario_audit.py -q
python -m pytest tests/test_react_preventivo_wizard_console.py -q
```
