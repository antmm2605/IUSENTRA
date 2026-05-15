# Motore Lex TTS Supertonic locale

## Scopo

La fase 3 collega il layer TTS raffinato di Lex a un engine Supertonic/ONNX locale e opzionale. Il contratto pubblico resta `window.PctLexVoice`: la chat Lex continua a chiamare la stessa facciata, mentre il registro TTS sceglie Supertonic solo quando asset e runtime sono pronti. In ogni altro caso resta attivo il fallback `speechSynthesis` del browser.

## Asset locali

Gli asset non sono inclusi nel repository. Copiarli in un bundle statico same-origin:

- `web/static/vendor/supertonic/manifest.json`
- `web/static/vendor/supertonic/onnx/duration_predictor.onnx`
- `web/static/vendor/supertonic/onnx/text_encoder.onnx`
- `web/static/vendor/supertonic/onnx/vector_estimator.onnx`
- `web/static/vendor/supertonic/onnx/vocoder.onnx`
- `web/static/vendor/supertonic/onnx/tts.json`
- `web/static/vendor/supertonic/onnx/unicode_indexer.json`
- `web/static/vendor/supertonic/voice_styles/F1.json`
- opzionale: `web/static/vendor/supertonic/voice_styles/M1.json`
- opzionale: `web/static/vendor/supertonic/onnxruntime-web/ort.min.js`
- opzionale: `web/static/vendor/supertonic/onnxruntime-web/*.wasm`

Le directory dei modelli e del runtime ONNX sono ignorate da Git per evitare commit di file pesanti o soggetti a licenze separate.

## Manifest

Usare `web/static/vendor/supertonic/manifest.example.json` come base:

```json
{
  "enabled": false,
  "basePath": "/static/vendor/supertonic",
  "onnxPath": "/static/vendor/supertonic/onnx",
  "onnxRuntimeScript": "/static/vendor/supertonic/onnxruntime-web/ort.min.js",
  "wasmPath": "/static/vendor/supertonic/onnxruntime-web/",
  "voiceStylesPath": "/static/vendor/supertonic/voice_styles",
  "defaultVoiceStyle": "F1.json",
  "fallbackVoiceStyle": "M1.json"
}
```

Per abilitare il motore, creare `manifest.json` con `enabled: true`. Tutti i path vengono accettati solo se same-origin; URL esterni o CDN non vengono usati.

## Fallback

Il caricamento avviene in preload. Se il manifest manca, e' disabilitato, manca ONNX Runtime, manca un modello o il backend WebGPU fallisce, il registro passa alla voce browser. Se WebGPU non riesce a creare le sessioni ONNX, il motore prova WASM. Se anche la sintesi Supertonic fallisce durante una lettura, il registro richiama il fallback browser senza bloccare Lex.

## Qualita e voce

Il motore applica i profili e i preset gia' definiti in:

- `web/static/js/lex-tts/voice-profiles.js`
- `web/static/js/lex-tts/quality-presets.js`
- `web/static/js/lex-tts/legal-speech-normalizer.js`

I parametri usati sono `totalStep`, `speed`, `silenceDuration` e `maxChunkChars`. La lingua `it-IT` viene mappata a `it` per l'input ONNX. Il testo viene normalizzato prima della sintesi per pronuncia legale, chunking e riduzione dei dati tecnici o sensibili.

## Privacy

La sintesi e' locale nel browser. Il testo legale non viene inviato a cloud o servizi esterni e non viene scritto nei log. Gli eventi di stato possono indicare backend, badge e tempi numerici di sintesi, ma non contengono il testo parlato.

## Licenza

L'integrazione non include modelli Supertonic e non copia codice sorgente del progetto esterno. Il codice di supporto IUSENTRA e' interno al repository; eventuali asset Supertonic o ONNX Runtime vanno installati rispettando le rispettive licenze. Il progetto Supertonic pubblico dichiara sample code MIT e modelli con licenza separata.

## Test manuali

1. Senza `manifest.json`, aprire Lex e verificare badge voce browser e lettura funzionante.
2. Con `manifest.json` disabilitato, confermare che non compaiano errori console e che la voce browser resti attiva.
3. Con asset e runtime locali, impostare `enabled: true`, aprire Lex e verificare badge `Supertonic WebGPU` o `Supertonic WASM`.
4. Leggere una frase con `art. 183 c.p.c.` e confermare pronuncia normalizzata.
5. Leggere una risposta lunga e verificare chunking, pause e UI reattiva.
6. Interrompere la lettura e verificare che `cancel()` fermi l'audio e liberi l'ObjectURL.
7. Rimuovere temporaneamente un modello ONNX e confermare fallback browser senza blocchi.
