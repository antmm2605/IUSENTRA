# 2.470.14 — Termine lungo accanto alle sentenze nel presidio notifiche; una discordanza falsa in meno

- Presidio notifiche: le sentenze da valutare mostravano «Nessun termine espresso» anche quando lo scadenziario
  conteneva già il termine lungo d'impugnazione (art. 327 c.p.c.) proposto dalla PEC di cancelleria che comunica il
  deposito: il presidio riconosceva solo quello calcolato dal fascicolo telematico. Ora riconosce anche la proposta
  della PEC (codice CIV_APPELLO_LUNGO) e mostra data, stato della bozza e norma; il termine breve resta quello che
  decorre dalla notificazione (art. 325 c.p.c.; nel rito del lavoro art. 434, comma 2). Test in
  `tests/test_notification_legal_terms.py`.
- Discordanze: un titolo professionale davanti al nome («Ass. Ed.») e un frammento d'indirizzo («Int.3 P.2») letti
  accanto alla parte producevano «Nome e cognome discordanti». Un nome con cifre o parole di una sola lettera non è
  confrontabile. Le discordanze già registrate con la regola superata non si mostrano più. Test in
  `tests/test_confronto_cliente.py`.
- Contiene la 2.470.13 (registro delle letture sotto carico, salute dello scheduler dopo il deploy).
