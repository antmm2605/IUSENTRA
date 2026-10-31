# Traduzione locale dei provvedimenti

Traduzione di servizio in italiano, non ufficiale e non asseverata, affiancata all'originale. Nessuna approvazione giuridica viene aggiunta. Testi e riferimenti originali rimangono conservati; gli avvisi sono visibili.

## Componenti verificabili

- Tencent Hy-MT2-7B-GGUF, revisione `ab8472660ac61fac25f1af43fac2599d52a8a775`, Q4_K_M, Apache-2.0.
- `Hy-MT2-7B-Q4_K_M.gguf`: 4.624.648.896 byte, SHA-256 `9f96256500f3fc1ab4d64336b58f52a949a95ad7516b0c229476eef782f9f77b`.
- llama.cpp b12020, commit `0ec4027a2a0183de87c007069adddc06e665f7de`; archivio CPU SHA-256 `1b69032f9ab60dc6aa909689fda941fa1b9162f6ab46b863582d5649d96ac6be`.
- Fonti: https://github.com/Tencent-Hunyuan/Hy-MT2 e https://github.com/ggml-org/llama.cpp/releases/tag/b12020 .

Il launcher verifica ogni file del runtime e l'intero modello prima dell'avvio. Nessun download avviene dalle richieste web. Il Compose richiede l'immagine applicativa verificata e tre mount tecnici. Non monta archivi dello studio, credenziali, socket Docker o dispositivi di firma; non espone porte. Usa rete `none`, filesystem di sistema in sola lettura, CPU limitata, nessuna GPU.

## Attivazione governata

Prima dell'attivazione servono backup coerente del corpus con ripristino provato, budget disco per modello/runtime/backup e verifica della RAM per un processo limitato a 9 GiB. Acquisire e verificare i componenti fissati sopra; nessun recupero di versioni arbitrarie.

La cartella privata del socket deve essere raggiungibile dall'app come `/data/runtime/traduzione/motore.sock` e dal solo traduttore come `/run/translation`. Consentire l'accesso ai soli UID applicativi autorizzati. Impostare `IUSENTRA_VERIFIED_IMAGE`, `IUSENTRA_TRANSLATION_MODEL`, `IUSENTRA_TRANSLATION_RUNTIME`, `IUSENTRA_TRANSLATION_SOCKET_DIRECTORY` nel contesto protetto Compose, poi eseguire `docker compose -f deploy/translation/compose.yml up -d`. Il Compose dell'app non viene modificato. Verificare salute, isolamento, traduzione reale nel lettore e riapertura dalla cache senza una nuova inferenza prima di attestare l'attivazione. Non usare proxy TCP esterni.

## Versioni e ripresa

Ricevute e segmenti normalizzati risiedono nello stesso SQLite proprietario del corpus, collegati alla sentenza e all'impronta della versione originale. Nessuna fonte duplicata o persistenza JSON. Una GET non traduce o acquisisce documenti. La traduzione parte esplicitamente; i segmenti riusciti restano salvati. Un errore richiede ripresa esplicita, conservando i precedenti. Un originale modificato produce una versione distinta; un cambio del motore non ritraduce un originale già completato. I riferimenti protetti devono coincidere: nessuna sostituzione autonoma di TUE con TFUE. Gli avvisi numerici non sono una verifica di equivalenza giuridica.

Le lingue dichiarate dal modello non sono tutte collaudate. Registrare separatamente prove e limiti. Una traduzione non può alimentare citazioni o massime come se fosse una fonte ufficiale.
