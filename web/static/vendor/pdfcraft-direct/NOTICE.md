# PDFCraft Direct Editor

Componente indipendente da PDFCraftTool/pdfcraft, revisione
`0503080d60a337e40cc9888a749890ff49ed6b11`.

Sorgente originale: https://github.com/PDFCraftTool/pdfcraft

Il componente e le modifiche a questo componente sono distribuiti secondo
GNU AGPL-3.0, riportata in LICENSE. La licenza proprietaria della restante
applicazione non sostituisce quella di questi file.

Modifiche IUSENTRA del 21 ottobre 2026: protocollo di scambio esplicito con
l'applicazione ospitante, conferma persistente del salvataggio e isolamento
del contesto del browser. Il componente scambia soltanto il documento PDF
selezionato e, su scelta dell’utente, immagini e caratteri letti localmente dal PC; non accede a sessioni, database o API dello studio.

I sorgenti JavaScript, gli stili e il motore WASM del componente sono forniti
in questa directory. La copia originale e la provenienza sono conservate nel
manifest degli asset. Questi file non costituiscono una prova di equivalenza
grafica o funzionale, che richiede il collaudo dei documenti.
