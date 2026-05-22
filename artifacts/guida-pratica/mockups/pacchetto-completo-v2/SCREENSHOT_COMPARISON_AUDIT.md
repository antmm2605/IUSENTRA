# Audit confronto screenshot Guida Pratica

Data audit: 22 maggio 2026.

Scopo: impedire che l'implementazione usi screenshot precedenti o salti un passaggio del flusso approvando.

## Esito sintetico

- Sequenza canonica: `pacchetto-completo-v2`.
- Sequenza precedente confrontata: `pacchetto-completo-v1`.
- Viewport usato: `1600x900`.
- Screenshot rigenerati correttamente con una pagina browser nuova per ogni passaggio.
- Nota di controllo: una prima rigenerazione cambiava solo l'hash della URL e produceva duplicati; è stata scartata e rifatta correttamente.

## Confronto passaggio per passaggio

| Passaggio | Screenshot v2 canonico | Differenza rispetto a v1 | Decisione |
|---|---|---|---|
| 1. Apertura | `apertura.png` | Nessuna differenza visiva intenzionale. | Mantiene il fascicolo come punto di partenza. |
| 2. Guida nascosta | `nascosta.png` | Nessuna differenza visiva intenzionale. | Conferma che la guida è opzionale e non blocca il fascicolo. |
| 3. Guida ora | `ora.png` | Nessuna differenza visiva intenzionale. | Mantiene piano assistito compatto. |
| 4. Contesto e termini | `contesto.png` | Nessuna differenza visiva intenzionale. | Mantiene sezioni compatte per contesto, termini e Lex. |
| 5. Anteprima modifica | `editor.png` | Aggiornato. | Aggiunti template filtrato dalla pratica, caricamento automatico, motivazione guida, import PDF/Word, documento avvocato facoltativo. |
| 6. Rientro completato | `completato.png` | Nessuna differenza visiva intenzionale. | Conferma rientro nel fascicolo e aggiornamento Lex. |

## File superati archiviati

- `pacchetto-completo-v2/_superati/editor-esatto-senza-template-import.png`: vecchia immagine dell'editor prima della decisione su template filtrato e import PDF/Word.

## Regola per Codex prima di implementare

Prima di toccare codice reale, confrontare il componente finale con:

1. `SCREENSHOT_REGISTRY.md`;
2. tutti i sei PNG canonici di `pacchetto-completo-v2`;
3. il modello PDF reso in `template-layout-model`;
4. lo screenshot del campo `Qualifica professionale` in `impostazioni-patrocinante`.

Se una schermata reale diverge, non dichiarare completato: correggere o documentare la differenza e farla approvare.
