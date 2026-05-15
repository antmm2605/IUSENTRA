# Accessibility Report React

Generato: 2026-05-08

## Controlli applicati

- Nuovi componenti con `role=status`, `aria-live`, `aria-label` e focus ring compatibili con il design system.
- `IusErrorState` separa messaggio utente e dettagli tecnici espandibili.
- `IusWizardStepper` espone `aria-current` sul passo attivo.
- `IusChannelCard`, `IusMessageList` e `LexPanel` usano testo visibile, badge e label esplicite, non solo colore.
- 2026-05-09: passaggio browser reale sulle route `/deposito/checklist`, `/strumenti-legali` e `/strumenti-operativi` in desktop/tablet/mobile; titoli, link e pulsanti restano visibili e raggiungibili senza overflow orizzontale.
- 2026-05-11: `/fascicoli/nuovo` 2.216.0 usa `details`/`summary` nativi per rendere collassabili le sezioni del form, mantenendo titoli visibili, icone di supporto e input file con label testuali per documenti iniziali ed email EML.
- 2026-05-15: `Drawer` e `Modal` condivisi gestiscono focus iniziale, Tab trap, Escape, backdrop e ripristino focus; bottoni icona in TopBar, builder Sito Studio e admin hanno `aria-label`/`title`; le icone decorative sono escluse dal nome accessibile.
- 2026-05-15: audit visuale 2.236.4 conferma 92/92 controlli desktop/mobile senza redirect login, form POST HTML nel perimetro React, loading bloccato o overflow orizzontale.
- 2026-05-15: rifinitura 2.236.5 mantiene accessibilita' tastiera su Ricerca Studio senza mostrare scorciatoie tecniche come testo primario; lo stato ricerca usa `aria-label` professionale e il retry mobile `/soggetti/nuovo` conferma H1 e contenuto raggiungibili.

## Problemi corretti

- CTA legacy primarie rimosse dalle route promosse.
- Stati di compliance distinguono "Non verificato", "Fonte mancante", "Fallback attivo" e "Revisione manuale richiesta".

## Rischi residui

- Serve passaggio tastiera completo sulle route principali dopo build finale; il controllo visuale desktop/tablet/mobile e' stato completato per la tranche 2.210.0.
- Route rimaste legacy non sono coperte da questo hardening React.
