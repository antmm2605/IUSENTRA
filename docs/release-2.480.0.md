# IUSENTRA 2.480.0 — semaforo dei motori, sequenza notturna, AI locale con un modello (03/11/2026)

- Semaforo dei motori (`pct/semaforo_motori/`): un solo motore pesante alla volta su tutto il server, giorno e notte;
  coda per priorità (documenti caricati dall'avvocato, PEC, poi la sequenza logica); si libera da solo se un processo
  muore; console Pianificazioni «In corso / in coda». Le richieste web non aspettano mai.
- Sequenza notturna dalle 21:30 alle 07:30 (`pct/scheduler_notturno/`, `docs/SEQUENZA_NOTTURNA.md`): PEC → collegamento
  ai fascicoli → OCR → letture e sentenze → scadenze, notifiche, economia → Lex e AI → fonti normative → manutenzione;
  un passo dopo l'altro, controllo della memoria, ripresa la notte dopo.
- AI locale (decisioni dell'avvocato): seconda lettura del catalogo solo di notte; un solo modello caricato e scaricato
  dopo 2 minuti; modello di riserva se il principale fallisce, con esito nel registro; limite di memoria solo per Ollama.
