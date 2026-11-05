# Release 2.482.0 — notifiche che nascono dalle comunicazioni ricevute, in tutte le materie

Richiesta dell'avvocato del 05/11/2026: riconoscere dalle comunicazioni ricevute ogni notifica dovuta per legge e
sapere, sempre con la norma, che cosa fare; lavorarla dall'agenda.

1. **Nuovi decreti riconosciuti** (`pct/provvedimenti/tipi.py`) con i loro termini (`pct/data/provvedimenti_regole_v2026_11.json`):
   appello del lavoro (art. 435 c.p.c.: notifica entro 10 giorni dalla comunicazione del decreto e almeno 25 giorni prima
   dell'udienza), procedimento semplificato (art. 281-undecies c.p.c.: almeno 40 giorni liberi; costituzione 10 giorni
   prima), giudice di pace penale su ricorso immediato (art. 27 D.Lgs. 274/2000: almeno 20 giorni prima dell'udienza).
2. **Che cosa comporta la notifica** (`pct/notifiche_obblighi/`): per ogni termine di notifica (415, 435, 281-undecies,
   473-bis.14, 643-644, intimazione dei testimoni, 27 D.Lgs. 274/2000, termine assegnato dal giudice) atti, destinatari,
   a cura di chi, presso chi e come (Avvocatura dello Stato, registro PA, procuratore costituito, pubblici elenchi,
   ufficiale giudiziario), avvertenze (giorni liberi, estero, ore 21 della PEC) e deposito dopo la notifica.
3. **Agenda** — nella scheda di lavorazione ogni termine di notifica mostra «Notifica da eseguire» con le norme e
   «Prepara la notifica», che apre le notifiche legali sul fascicolo.
4. **Fonti** — 32 norme aggiunte al registro con il testo vigente letto dall'archivio Normattiva del software il
   05/11/2026 (`pct/procedura_fasi/fonti_notifiche.py`): c.p.c., c.p.p. e disp. att., D.Lgs. 274/2000, c.p.a., D.Lgs.
   175/2024, D.Lgs. 14/2019, L. 53/1994.

Collaudo sui 1.784 testi reali dello studio: 81 decreti ex art. 415 riconosciuti, termini di notifica proposti per tutti i
decreti del giudice (i 4 senza termine sono ricorsi dello studio che citano l'art. 415); nessun falso riconoscimento dei
nuovi tipi.

Test: `tests/test_notifiche_obblighi.py`.
