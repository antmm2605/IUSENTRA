"""Notizie utili dalle fonti istituzionali: acquisizione, archivio e pertinenza con i fascicoli.

Ogni notizia viene da un canale ufficiale pubblico (feed RSS dell'ente o pagina
istituzionale stabile) censito in `fonti.py` con URL, formato e data di verifica.
Del testo si conservano solo titolo, data, collegamento e la descrizione
pubblicata dall'ente: nessuna sintesi è scritta dal software.

Moduli:
- `fonti`: catalogo dei canali (ente, URL, formato, tipo, frequenza, verifica);
- `rete`: lettura limitata e sicura dei canali (timeout, host ammessi, dimensione);
- `feed`: lettura dei feed RSS/Atom in voci grezze;
- `adattatori`: dalle voci grezze di ciascun ente alla notizia normalizzata;
- `classifica`: tipo (norma, pronuncia, prassi, avviso PCT, notizia), materia e atti citati;
- `archivio`: archivio SQLite condiviso con deduplica e stato delle fonti;
- `giro`: aggiornamento delle fonti scadute, una fonte giù non ferma le altre;
- `alimentazione`: inoltro di norme, pronunce e prassi alla revisione degli aggiornamenti legali;
- `pertinenza`: collegamento ai fascicoli dello studio con il motivo.
"""
