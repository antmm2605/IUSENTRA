# Valutazione Lex AI mobile e Qwen 3.5

Data valutazione: 2026-05-17.

## Sintesi

Il video indicato dall'utente presenta Qwen 3.5 come famiglia di modelli locali piccoli e multimodali, con tag adatti anche a macchine leggere. La verifica sulla libreria Ollama conferma la disponibilita di tag `qwen3.5` con varianti `0.8b`, `2b`, `4b`, `9b` e superiori, contesto dichiarato a 256K e input testo/immagine.

Per IUSENTRA la scelta professionale non è spostare fascicoli o modelli sul telefono. La strada sicura è usare mobile e tablet come client PWA autenticato, con Lex AI contestuale collegato al backend e al server di produzione IUSENTRA. Il dispositivo mobile apre Lex, invia la richiesta autenticata e riceve la risposta governata senza creare copie non presidiate dei dati legali.

## Decisione di prodotto

- Lex AI mobile deve essere accessibile dalla barra mobile React, con contesto della pagina corrente.
- Il widget Lex deve restare visibile e utilizzabile su tablet e mobile, sopra la navigazione inferiore.
- Qwen 3.5 viene aggiunto come scelta esplicita nelle impostazioni AI locale, ma non diventa default automatico finche' non abbiamo misure su qualita, latenza, RAM e stabilita.
- Il default automatico resta governato dal profilo del PC, cosi' non si rompe chi usa gia' Gemma o Qwen 2.5.

## Architettura consigliata

1. Mobile immediato: PWA IUSENTRA + pulsante Lex AI nella navigazione inferiore.
2. Runtime: modello sul server di produzione IUSENTRA; il PC dello studio resta un runtime locale opzionale e governato, non il requisito per mobile.
3. Contesto: route, fascicolo, posta, scadenze, documenti e ricerca legale passano dalla pipeline Lex esistente.
4. Privacy: niente dati cliente in notifiche push, niente cache operativa nel service worker, niente download silenzioso di fascicoli sul dispositivo mobile.
5. Evoluzione: solo dopo benchmark si puo' abilitare un micro-modello locale mobile per funzioni non sensibili, ad esempio dettatura, bozze temporanee o OCR di file scelti dall'utente.

## Miglioramento desktop

Qwen 3.5 e' utile come prova desktop per:

- PC con RAM sufficiente che vogliono un modello piu' capace di quelli ultra-leggeri.
- Analisi di immagini o documenti quando il runtime locale supporta correttamente la variante scelta.
- Benchmark comparativo su risposte legali, recupero da RAG, velocita e uso memoria.

La UI espone `Qwen 3.5 leggero` e `Qwen 3.5 avanzato` nelle impostazioni AI locale. La selezione e' volontaria: IUSENTRA non cambia modello in automatico senza controllo del PC.

## Aggiornamento 2.245.7

`/impostazioni?tab=ai` rileva ora telefono, tablet o PC usando i segnali disponibili nel browser: piattaforma, touch, dimensione schermo, RAM dichiarata, core e stima dello spazio disponibile. Se il dispositivo è mobile, IUSENTRA non promette installazione Ollama o download modelli: apre Lex AI e usa il language model, gli embedding e l'indice documenti sul server di produzione IUSENTRA.

Sul desktop resta attiva la preparazione guidata tramite Local Signer: il PC viene controllato, Ollama viene preparato quando manca e i modelli vengono scelti in base all'hardware. La UI mostra `EmbeddingGemma 300M` per la ricerca documenti invece del codice grezzo `embeddinggemma:300m`.

Qwen 3.5 include anche l'opzione `Qwen 3.5 minimo` per test su dispositivi leggeri. Gemini Embedding 2 resta un provider esterno separato: puo' migliorare il RAG multimodale, ma richiede autorizzazione privacy, chiave configurata e reindicizzazione completa del corpus interessato.

## Fonti verificate

- Video utente: https://www.youtube.com/watch?v=eAqv0EK4XUg
- Metadati YouTube oEmbed: https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=eAqv0EK4XUg&format=json
- Libreria ufficiale Ollama Qwen 3.5: https://ollama.com/library/qwen3.5
- Download ufficiale Ollama: https://ollama.com/download
- Libreria ufficiale Ollama EmbeddingGemma: https://ollama.com/library/embeddinggemma
- Documentazione Gemini embeddings: https://ai.google.dev/gemini-api/docs/embeddings
