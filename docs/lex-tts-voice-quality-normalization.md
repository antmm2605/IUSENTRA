# Qualita voce e normalizzazione legale Lex TTS

## Architettura

Lex continua a parlare attraverso `window.PctLexVoice`. La facciata usa moduli browser caricati prima del widget, sia in `base.html` sia nella shell React:

- `quality-presets.js`: preset `fast`, `balanced`, `high`;
- `voice-profiles.js`: profili voce italiani per Lex;
- `legal-speech-normalizer.js`: pulizia markdown, privacy, abbreviazioni legali, date, importi, numeri, punteggiatura e chunking;
- `browser-speech-engine.js`: fallback nativo `speechSynthesis`;
- `supertonic-engine.js`: engine ONNX locale opzionale;
- `tts-engine-registry.js`: scelta engine e fallback.

## Profili Voce

Profili disponibili:

- `lex-it-professional`: default, voce calma e professionale;
- `lex-it-reading`: lettura atti/documenti, piu' lenta e con pause piu' lunghe;
- `lex-it-brief`: sintesi breve, limite lettura piu' basso;
- `lex-it-accessibility`: accessibilita', velocita bassa e pronuncia piu' esplicita.

I profili Supertonic usano `M1.json` come voice style locale predefinito, con fallback browser italiano quando l'engine ONNX non e' disponibile. Ogni profilo definisce lingua, preferenza voce, rate, pitch, volume, limite automatico, dimensione chunk, pause, preferenza engine e preset qualita.

## Preset Qualita

- `fast`: meno step, chunk piccoli e pausa breve, utile su macchine lente;
- `balanced`: default, qualita e latenza equilibrate;
- `high`: piu' step e ritmo piu' lento, da usare per letture lunghe o accessibilita.

Senza Supertonic i preset restano utili per voce browser, chunking, pause e limiti di lettura.

## Normalizzazione Legale

Il normalizzatore:

- rimuove markdown, codice, link lunghi e markup non adatto alla voce;
- riduce codici fiscali, IBAN, UUID, hash, token e numeri tecnici lunghi;
- espande abbreviazioni come `art.`, `c.p.c.`, `Cass. civ.`, `Sez. Un.`, `D.Lgs.`, `R.G.N.R.`, `PCT`, `PST`, `PAT`, `PTT`, `CNF`, `CEDU`;
- converte date sicure come `15/05/2026` in forma parlabile;
- converte importi sicuri come `\u20ac 1.250,50` in forma parlabile;
- converte percentuali, decimali e orari comuni, per esempio `12,5%` e `14:30`;
- spezza il testo per paragrafi, frasi e clausole con virgola, usando pause diverse per punto, domanda, esclamazione e virgola.

Modalita supportate:

- `summary`: risposta Lex ordinaria;
- `document_reading`: lettura piu' estesa;
- `citations_light`: evita la lettura integrale delle fonti;
- `accessibility`: profilo piu' lento ed esplicito.

## Privacy

Il testo parlato non viene loggato e non viene inviato a servizi esterni. I dati tecnici o sensibili vengono ridotti prima della sintesi. Supertonic resta opzionale e locale: senza asset o runtime compatibile, il fallback browser resta attivo.

## Test

Comandi mirati:

```powershell
node tests/js/lex_tts_normalizer.test.mjs
node tests/js/lex_tts_voice_contract.test.mjs
node tests/js/lex_tts_profiles_quality.test.mjs
node tests/js/lex_tts_supertonic_engine.test.mjs
python -m pytest -q tests/test_lex_widget_contract.py tests/test_web_bootstrap.py tests/test_packaging_consistency.py --tb=short
```

## Aggiungere Termini

Le abbreviazioni vivono in `expandLegalAbbreviations()` dentro `legal-speech-normalizer.js`. Aggiungere regole dal piu' specifico al piu' generico, con test JS che copra almeno input e output parlabile. Evitare espansioni aggressive quando una sigla puo' cambiare significato nel contesto.

## Evoluzione Supertonic

Il motore ONNX deve continuare a rispettare:

- asset solo same-origin;
- nessuna CDN produttiva;
- WebGPU con fallback WASM;
- fallback obbligatorio a `speechSynthesis`;
- nessun log del testo parlato;
- nessun modello ONNX pesante nel repository.
