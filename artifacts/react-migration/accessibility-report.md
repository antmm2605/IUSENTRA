# Accessibility Report React

Generato: 2026-05-08

## Controlli applicati

- 2026-06-12: assistente vocale Studio 2.253.1. Il trigger topbar espone `aria-label`, `aria-expanded` e title; il pannello ha `aria-label`, stato con `role=status`, pulsanti con testo o label, input PIN mascherato con `inputMode=numeric`, campi cliente con label visibili, registro `Cosa ho ascoltato` leggibile e comandi raggruppati in `details/summary` nativi. Audit CDP su desktop/tablet/mobile: nessun pulsante vuoto, nessun testo pulsante tagliato, testi richiesti presenti, stato ascolto e conferma cliente leggibili. La prova visibile del microfono negato mostra un messaggio operativo e svuota il PIN senza salvare un profilo incompleto.
- 2026-06-04: editor Template Atti 2.249.14 verificato nel browser reale su desktop/tablet/mobile. I pulsanti icona della toolbar, le azioni campi, i tab Campi/Stile/Lex/Fonti/Controlli/Export, Lex diff accetta/rifiuta, import, export, compilazione multipla e firma espongono testo o `aria-label`/`title` operativo; i controlli restano raggiungibili dopo scroll e non producono sovrapposizioni.
- Nuovi componenti con `role=status`, `aria-live`, `aria-label` e focus ring compatibili con il design system.
- `IusErrorState` separa messaggio utente e dettagli tecnici espandibili.
- `IusWizardStepper` espone `aria-current` sul passo attivo.
- `IusChannelCard`, `IusMessageList` e `LexPanel` usano testo visibile, badge e label esplicite, non solo colore.
- 2026-05-09: passaggio browser reale sulle route `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` in desktop/tablet/mobile; titoli, link e pulsanti restano visibili e raggiungibili senza overflow orizzontale.
- 2026-05-11: `/fascicoli/nuovo` 2.216.0 usa `details`/`summary` nativi per rendere collassabili le sezioni del form, mantenendo titoli visibili, icone di supporto e input file con label testuali per documenti iniziali ed email EML.
- 2026-05-15: `Drawer` e `Modal` condivisi gestiscono focus iniziale, Tab trap, Escape, backdrop e ripristino focus; bottoni icona in TopBar, builder Sito Studio e admin hanno `aria-label`/`title`; le icone decorative sono escluse dal nome accessibile.
- 2026-05-15: audit visuale 2.236.4 conferma 92/92 controlli desktop/mobile senza redirect login, form POST HTML nel perimetro React, loading bloccato o overflow orizzontale.
- 2026-05-15: rifinitura 2.236.5 mantiene accessibilita' tastiera su Ricerca Studio senza mostrare scorciatoie tecniche come testo primario; lo stato ricerca usa `aria-label` professionale e il retry mobile `/soggetti/nuovo` conferma H1 e contenuto raggiungibili.
- 2026-05-15: Sito Studio Builder Pro 2.239.1 aggiunge label e title ai controlli icona del builder, compresi tab verticali, resize pannello, formattazione testo, allineamenti, device preview e azioni blocco/media. Il rich text resta limitato a corsivo, sottolineato, apice e pedice filtrati lato server; i menu tablet/mobile della preview restano visibili anche nei formati compatti.
- 2026-05-16: Ricerca Legale 2.239.3 usa `aria-label` per sezioni, percorso operativo, mappa fonti, risultati e scheda contesto; le tab hanno `aria-current`, le icone sono decorative dove opportuno e le azioni principali restano pulsanti/testi espliciti (`Leggi contesto`, `Cerca collegati`, `Fonte originale`).
- 2026-05-22: Preset grafico globale 2.248.12 aggiunge landmark e label ai blocchi centrali: `IusentraFiltersBar` ha `aria-label="Filtri principali"`, `IusentraContextFilters` ha `aria-label="Contesto filtri"`, DataSurface espone header/body/footer coerenti e le card laterali usano titolo, icona e contenuto sintetico. Browser desktop/tablet/mobile su Fascicoli conferma controlli e paginazione visibili senza overflow.

## Problemi corretti

- CTA legacy primarie rimosse dalle route promosse.
- Stati di compliance distinguono "Non verificato", "Fonte mancante", "Fallback attivo" e "Revisione manuale richiesta".

## Rischi residui

- Serve passaggio tastiera completo sulle route principali dopo build finale; il controllo visuale desktop/tablet/mobile e' stato completato per la tranche 2.210.0.
- Route rimaste legacy non sono coperte da questo hardening React.
