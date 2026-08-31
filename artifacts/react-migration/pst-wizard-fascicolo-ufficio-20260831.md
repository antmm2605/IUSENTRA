# Allineamento PST Wizard e Fascicolo d’ufficio

Data: 31/08/2026 · fuso orario Europe/Rome.

## Correzione applicata

Il pannello `Fascicolo d’ufficio` interroga il Local Signer con un solo lotto
`/pst/ricerca-snapshot`, identico per campi ministeriali al contratto usato dal
Wizard: ufficio, numero e anno R.G., ruolo, certificato, sessione, servizio,
registro, tabella ministeriale e flag `search_only=false`,
`include_full_snapshot=true`, `single_interactive_batch=true`.

La risoluzione del servizio ora parte dal fascicolo. Per il fascicolo Lavoro
del Tribunale di Vicenza, R.G. 1084/2026, il profilo risultante è:

- servizio PST: `JPW_SIL_DISTR`;
- tabella ministeriale: `SICID_LAVORO`;
- registro: `LAV`.

Il valore predefinito dell’ufficio rimane un fallback soltanto se il
fascicolo non contiene alcun rito o registro riconoscibile. Non viene
modificato il comportamento del Wizard.

## Verifiche tecniche eseguite

- typecheck React completato;
- contratto del pannello per lotto diretto, selezione, copia/originale e
  avanzamento per documento;
- deduzione Vicenza/Lavoro dal fascicolo locale;
- matrice di dieci tabelle PST del resolver;
- verifica del container locale `iusentra-app` healthy e del resolver in
  esecuzione.

## Prova reale

Il Wizard ha avuto esito positivo sul catalogo reale. La prova reale del
pannello Fascicolo d’ufficio non è stata eseguita il 31/08/2026 perché il
certificato CNS non era disponibile sulla macchina; il cliente dovrà aprire
`/fascicoli/A1FB22FE#documenti`, scegliere **Visualizza fascicolo** e inserire
il PIN una sola volta. L’esito atteso è il catalogo completo restituito dal
medesimo profilo Lavoro del Wizard.
