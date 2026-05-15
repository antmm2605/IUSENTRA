# Integrazione TTS Supertonic per Lex

## Architettura

Il TTS di Lex resta esposto solo da `window.PctLexVoice`. Il flusso chat non cambia:
`pct-lex-assistant.js` continua a chiamare `voice.speak(...)`, mentre la facciata voce decide se usare il registro TTS o il fallback browser.

Moduli caricati prima della facciata:

- `web/static/js/lex-tts/quality-presets.js`: preset di latenza/qualita condivisi.
- `web/static/js/lex-tts/voice-profiles.js`: profili voce italiani per Lex.
- `web/static/js/lex-tts/legal-speech-normalizer.js`: pulizia testo, privacy, abbreviazioni legali e chunking.
- `web/static/js/lex-tts/browser-speech-engine.js`: engine `speechSynthesis` nativo.
- `web/static/js/lex-tts/supertonic-engine.js`: predisposizione same-origin per Supertonic/ONNX.
- `web/static/js/lex-tts/tts-engine-registry.js`: scelta engine e fallback.

## Asset Supertonic

Gli asset non sono inclusi nel repository. Vanno copiati sotto:

- `web/static/vendor/supertonic/manifest.json`
- `web/static/vendor/supertonic/onnx/duration_predictor.onnx`
- `web/static/vendor/supertonic/onnx/text_encoder.onnx`
- `web/static/vendor/supertonic/onnx/vector_estimator.onnx`
- `web/static/vendor/supertonic/onnx/vocoder.onnx`
- `web/static/vendor/supertonic/onnx/tts.json`
- `web/static/vendor/supertonic/onnx/unicode_indexer.json`
- `web/static/vendor/supertonic/voice_styles/F1.json`

Usare `web/static/vendor/supertonic/manifest.example.json` come base. Il runtime produttivo non contiene URL esterni hardcoded.

## Abilitazione

Il manifest reale deve impostare:

```json
{
  "enabled": true,
  "basePath": "/static/vendor/supertonic",
  "onnxPath": "/static/vendor/supertonic/onnx",
  "voiceStylesPath": "/static/vendor/supertonic/voice_styles",
  "defaultVoiceStyle": "F1.json",
  "fallbackVoiceStyle": "M1.json"
}
```

Se il manifest manca o `enabled` e' `false`, Lex usa automaticamente la voce browser.

## Fallback e privacy

Il testo resta nel browser dell'utente e non viene inviato a servizi esterni. Se Supertonic non e' presente, non e' pronto o fallisce, il registro passa a `speechSynthesis` senza bloccare Lex. Il normalizzatore non logga il testo parlato e riduce codici fiscali, IBAN, UUID, hash, token e URL lunghi prima della lettura.

## Licenza

Questa fase non importa codice sorgente Supertonic. L'integrazione e' ispirata all'architettura pubblica del progetto Supertonic, che dichiara sample code MIT e modelli con licenza separata. Se in futuro si adatta codice sostanziale dal progetto, conservare copyright e licenza nel file interessato.

## Test manuali

1. Aprire una pagina autenticata con Lex.
2. Verificare che il widget si apra e che il badge mostri `Voce browser` o `Voce pronta`.
3. Fare una domanda con risposta breve contenente `art. 183 c.p.c.` e ascoltare la lettura.
4. Fare una risposta lunga e verificare che venga letta solo la sintesi iniziale.
5. Disattivare la voce dal pulsante volume e verificare che la preferenza resti salvata.
6. Usare il microfono e confermare che la dettatura continui a funzionare.
