# Lettura delle rappresentazioni alternative MIME

Fonte tecnica ufficiale: [RFC 2046, sezione 5.1.4](https://www.rfc-editor.org/rfc/rfc2046#section-5.1.4).
Consultazione: 07/10/2026. Ambito: sola lettura del corpo MIME nel lettore React;
non cambia firma, classificazione, trasporto, ricevute o invio SMTP locale.

Le parti `multipart/alternative` rappresentano lo stesso contenuto in forme
alternative e sono ordinate per fedeltà crescente. Il lettore sceglie l'ultima
rappresentazione supportata non vuota, compreso HTML dentro `multipart/related`.
Non concatena versioni equivalenti né corregge parole inventando lettere mancanti.
Le parti `multipart/mixed`, messaggi allegati e allegati testuali restano distinti.
Gli originali EML conservano byte e impronte; nessuna riscrittura dei messaggi.

Caso locale osservato: in alcune PEC il testo semplice contiene già una sequenza
di sostituzione nel file originale, mentre l'alternativa HTML contiene l'accento
corretto. La lettura deve usare quella rappresentazione integra dello stesso MIME.
Il confronto con il backup accettato è documentato nel rapporto della tranche;
le funzioni di invio e firma sono escluse dalla modifica.
