# Visual audit 2.245.5 - Presidio Lex nelle pagine studio

Data: 2026-05-17

Server locale temporaneo isolato su `http://127.0.0.1:8092`, con sessione
autenticata di verifica e dati runtime in `%TEMP%`.

| Route | Viewport | Esito | Evidenza |
| --- | --- | --- | --- |
| `/ricerca-legale` | 1440x1100 | OK | `ricerca-legale-desktop.png`, pagina React con `Presidio Lex AI`, `Archivi ufficiali locali` e `Funzioni Lex avanzate`. |
| `/ricerca-legale` | 390x900 | OK | `ricerca-legale-mobile.png`, layout mobile non vuoto e senza overflow orizzontale visibile nello screenshot. |
| `/giurisprudenza/` | 1440x1100 | OK | `giurisprudenza-desktop.png`, pagina React con `Citazioni e fonti verificate`, Cassazione e fonti con etichette operative. |
| `/giurisprudenza/` | 390x900 | OK | `giurisprudenza-mobile.png`, layout mobile non vuoto e pannelli leggibili. |

Controlli API:

- `GET /api/v1/ui/ricerca-legale`: presenti `archivi_ufficiali`,
  `lex_presidio` e `ai_avanzata`.
- `GET /api/v1/ui/giurisprudenza`: presenti `citazioni_verificate`,
  `lex_presidio`, `archivi_ufficiali` e `ai_avanzata`.

Controllo immagini: tutti gli screenshot hanno dimensione attesa e valori
pixel non uniformi, quindi non sono catture bianche o schermate vuote.
