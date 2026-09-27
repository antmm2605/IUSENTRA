# Sito di vendita IUSENTRA

Sito statico di presentazione commerciale (HTML + CSS + JS, nessuna dipendenza né build).
È **separato dal gestionale**: non fa parte dell'immagine Docker, non viene pubblicato
dal deploy Hetzner e non va messo sul server di produzione dell'applicazione.

## File

| File | Contenuto |
|---|---|
| `index.html` | Pagina unica: apertura, problema, funzioni, passi, conformità, prezzi, domande, demo |
| `assets/stile.css` | Stile (colori da `DESIGN.md`: legal-night, institutional-blue, judicial-gold) |
| `assets/app.js` | Animazioni degli schizzi e controllo del modulo demo |
| `favicon.svg` | Icona del sito |
| `costruisci_anteprima.py` | Crea una pagina unica autonoma per l'anteprima: `python3 costruisci_anteprima.py` |

Per vederlo in locale basta aprire `index.html` nel browser.

## Da completare prima della messa online

- **Prezzi** dei piani Avvocato e Studio (ora `€ —`, classe `segnaposto`).
- **Email commerciale** (ora `commerciale@iusentra.it`, da confermare).
- **Invio del modulo demo**: `assets/app.js` controlla i campi ma non invia nulla; collegarlo al servizio scelto (email, CRM o modulo esterno).
- **Informativa privacy** da collegare alla casella di consenso del modulo.
- **Dominio e hosting** statico (qualsiasi hosting di file statici va bene).

Le schermate sono illustrazioni disegnate in HTML con dati di esempio: nessun dato reale di studi o clienti.
I riferimenti normativi mostrati (D.M. 44/2011, art. 171-ter c.p.c., D.M. 55/2014 aggiornato dal D.M. 147/2022, ecc.)
corrispondono alle basi normative dichiarate in `CLAUDE.md`.
