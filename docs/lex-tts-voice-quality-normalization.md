# Qualita voce e normalizzazione legale Lex TTS

## Architettura

Lex continua a parlare attraverso `window.PctLexVoice`. La facciata usa moduli browser legacy, caricati in `base.html` prima del widget:

- `quality-presets.js`: preset `fast`, `balanced`, `high`.
- `voice-profiles.js`: profili voce italiani per Lex.
- `legal-speech-normalizer.js`: pulizia markdown, privacy, abbreviazioni legali, date, importi e chunking.
- `browser-speech-engine.js`: fallback nativo `speechSynthesis`.
- `supertonic-engine.js`: engine ONNX locale opzionale.
- `tts-engine-registry.js`: scelta engine e fallback.

## Profili voce

Profili disponibili:

- `lex-it-professional`: default, voce calma e professionale.
- `lex-it-reading`: lettura atti/documenti, piu' lenta e con pause piu' lunghe.
- `lex-it-brief`: sintesi breve, limite lettura piu' basso.
- `lex-it-accessibility`: accessibilita', velocita bassa e pronuncia piu' esplicita.

Ogni profilo definisce lingua, preferenza voce, rate, pitch, volume, limite automatico, dimensione chunk, pause, preferenza engine e preset qualita.

## Preset qualita

- `fast`: meno step, chunk piu' piccoli, utile su macchine lente.
- `balanced`: default, qualita e latenza equilibrate.
- `high`: piu' step e ritmo leggermente piu' lento, da usare solo quando richiesto.

Senza Supertonic i preset restano utili per voce browser, chunking, pause e limiti di lettura.

## Normalizzazione legale

Il normalizzatore:

- rimuove markdown, codice, link lunghi e markup non adatto alla voce;
- riduce codici fiscali, IBAN, UUID, hash, token e numeri tecnici lunghi;
- espande abbreviazioni come `art.`, `c.p.c.`, `Cass. civ.`, `Sez. Un.`, `D.Lgs.`, `R.G.N.R.`, `PCT`, `PST`, `PAT`, `PTT`, `CNF`, `CEDU`;
- converte date sicure come `15/05/2026` in `15 maggio 2026`;
- converte importi sicuri come `€ 1.250,50` in forma parlabile;
- spezza il testo per paragrafi e frasi, con limite prudente per l'italiano legale.

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
python -m pytest -q tests/test_lex_widget_contract.py tests/test_packaging_consistency.py --tb=short
```

## Aggiungere termini

Le abbreviazioni vivono in `expandLegalAbbreviations()` dentro `legal-speech-normalizer.js`. Aggiungere regole dal piu' specifico al piu' generico, con test JS che copra almeno input e output parlabile. Evitare espansioni aggressive quando una sigla puo' cambiare significato nel contesto.

## Evoluzione Supertonic

Il motore ONNX deve continuare a rispettare:

- asset solo same-origin;
- nessuna CDN produttiva;
- WebGPU con fallback WASM;
- fallback obbligatorio a `speechSynthesis`;
- nessun log del testo parlato;
- nessun modello ONNX pesante nel repository.
