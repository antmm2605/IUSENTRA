# Procedura notifiche legali

## Aggiornamento 30/07/2026 - Attestazione modificabile e allegata alla PEC

Correzione limitata al perimetro notifica L. 53/1994, senza modifiche al deposito:

- l'attestazione di conformità nella pagina React `/notifiche-legali` è modificabile integralmente dall'avvocato;
- il salvataggio conserva la bozza dell'attestazione per la notifica corrente e aggiorna subito l'anteprima visibile;
- il PDF dell'attestazione non viene proposto come download operativo dalla UI notifiche: viene generato e salvato direttamente nei documenti del fascicolo tramite `salva_documento_fascicolo`;
- quando la notifica richiede attestazione, il piano PEC locale inserisce automaticamente il PDF salvato tra gli allegati della PEC insieme alla relata firmata e ai documenti da notificare;
- il testo modificato dall'avvocato viene rispettato anche dal generatore PDF, mantenendo le interruzioni di riga del testo salvato.
- i campi tecnici del modello già coperti dal flusso guidato (`avvocato`, `procedimento`, `RG`, `tipo provvedimento`, date e oggetto PEC) non vengono più mostrati come `Dati del modello scelto`;
- gli stessi campi vengono filtrati anche dal payload `template_fields`, così valori vuoti o duplicati non possono sovrascrivere i dati reali di fascicolo, notifica e documenti.

Guardrail eseguiti senza invio PEC reale:

- `python -m pytest tests/test_notifiche_legali.py -q`;
- `python -m pytest tests/test_regia_ui_react.py -q`;
- `python -m pytest tests/test_regia_ui_react.py::test_ui_notifiche_relata_firma_solo_con_prova_tecnica -q`;
- `npm --prefix frontend run build`.

Verifica reale locale su `127.0.0.1:8080`:

- pratica `2026/002`, destinatari manuali Codex già presenti nella notifica;
- documenti selezionati: `SentenzaDefinitiva_33581101.pdf` e `VerbaleUdienza_33393309.pdf`;
- click su `Salva nel fascicolo` ha prodotto `Attestazione_di_conformita_1025_2026.pdf` dentro il fascicolo;
- dopo reload e selezione dei documenti, il blocco `Dati del modello scelto` non è ricomparso;
- click su `Salva nel fascicolo` ha confermato l'attestazione nel fascicolo;
- click su `Controlla relata` e poi `Invia PEC` ha generato solo il `PIANO PEC LOCALE PRONTO`, senza invio PEC reale e senza SMTP server-side;
- il piano contiene `relata_notifica.pdf.p7m`, sentenza, verbale udienza e attestazione di conformità come allegati;
- nessun blocco `Invio PEC bloccato`, `bloccante` o `mancante` visibile nel piano PEC locale;
- la relata indica `Sentenza` per `SentenzaDefinitiva_33581101.pdf` e `Verbale di udienza` per `VerbaleUdienza_33393309.pdf`, senza trasformare il verbale in sentenza;
- l'attestazione contiene la dichiarazione cumulativa con `Sentenza, emessa dal Tribunale di Palmi Sez. CIVILE in data 08/01/2026` e `Verbale di udienza, estratto dal fascicolo informatico del Tribunale di Palmi Sez. CIVILE in data 16/12/2025`;
- audit visibile con data italiana `30/07/2026 23:04`, senza timestamp UTC raw.
