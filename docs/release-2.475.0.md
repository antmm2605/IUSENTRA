# 2.475.0 — PEC nei documenti del fascicolo in automatico; icona «Normativa» nel fascicolo

- **PEC → documenti del fascicolo** (`pct/pec_fascicolo_documenti/`): per ogni PEC collegata a un fascicolo (collegamento
  certificato, automatico del linker con ruolo, cliente e ufficio coincidenti, o confermato dall'avvocato) entrano nei
  documenti del fascicolo gli atti e i provvedimenti allegati (PDF, `.p7m` originale firmato, documenti anche dentro
  ZIP) e, per le notifiche, il file `.eml` e le ricevute di accettazione e di avvenuta consegna completa come prova
  (L. 53/1994 art. 3-bis; art. 19-bis Provv. DGSIA 16/04/2014), visibili al presidio delle notifiche. Provenienza
  scritta nel documento (Message-ID, mittente, data di consegna in ora italiana, nome originale, SHA-256), nessun
  doppione, scarti con il motivo (`daticert.xml`, involucri, XML tecnici). Recupero notturno delle PEC già collegate
  (corsia lunga, a lotti, riprendibile). Nei documenti: «da PEC del gg/mm/aaaa» con il collegamento alla PEC. Verifica
  sul server: `deploy/hetzner/verifica_pec_fascicolo.py` (solo conteggi). Ricevute di deposito non toccate.
- **Icona «Normativa» nel fascicolo** (`pct/normativa_fascicolo/`, `GET /api/v1/ui/fascicoli/<id>/normativa`): pannello con
  le norme della procedura e delle fasi, dei termini e delle udienze aperti e dei tipi di documento presenti, ciascuna
  con estratto ufficiale, link Normattiva, versione e motivo; testo integrale dall'archivio Normattiva di IUSENTRA quando
  presente; ricerca nell'archivio filtrata per materia della pratica.
