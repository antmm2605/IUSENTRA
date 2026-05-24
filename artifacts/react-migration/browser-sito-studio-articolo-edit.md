# Verifica browser modifica articolo Sito Studio

Data: 2026-05-24

Route verificata: `/sito-studio/articoli/2/modifica`

Ambiente locale: Flask isolato su `http://127.0.0.1:8099`, dati temporanei sotto `%TEMP%`, rate limit disabilitato solo per evitare falsi positivi sul caricamento asset durante il test CDP.

## Esito

| Viewport | Shell React | API articolo | Form reale | Salva articolo | Overflow | Console | Testi tecnici visibili |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Desktop 1440x1000 | OK | 200 OK | OK | 1 comando | No | 0 errori | 0 |
| Tablet 1024x768 | OK | 200 OK | OK | 1 comando | No | 0 errori | 0 |
| Mobile 390x844 | OK | 200 OK | OK | 1 comando | No | 0 errori | 0 |

## Dati controllati

- `#root` presente e route servita dalla shell React.
- Titolo pagina `Modifica articolo Sito Studio` visibile.
- API `/api/v1/ui/sito-studio/articoli/2/modifica` autenticata con articolo reale, senza `notFound`.
- Campo titolo coerente con il valore API: `Articolo di verifica React 1`.
- Testo principale caricato nel form, 75 caratteri.
- Nessun overflow orizzontale nei tre viewport.
- Nessun errore console dopo il riavvio locale con rate limit disabilitato.
- Nessun testo tecnico vietato visibile tra etichette, pannelli e azioni.

## Nota di regressione evitata

Durante la verifica il normalizzatore frontend traduceva anche i campi modificabili dell'articolo. La correzione separa i dati editabili dai testi di interfaccia: titoli, sommari, autore, categoria, corpo e SEO restano valori reali del repository; la pulizia dei termini tecnici continua solo su etichette, messaggi e azioni.
