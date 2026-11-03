"""Collegamento certo al fascicolo delle notifiche L. 53/1994 già inviate dallo studio e delle loro ricevute.

* ``daticert``: il destinatario della ricevuta riletto dai dati di certificazione del gestore (daticert.xml).
* ``regola``: le tre fonti nell'ordine di certezza (.eml nel fascicolo, messaggio originale/stesso invio,
  ruolo + cliente + ufficio di ``pct.pec_collegamento_certo``); fail-closed su più fascicoli.

Base normativa: art. 3-bis L. 53/1994 (prova della notifica: ricevute di accettazione e di avvenuta consegna);
art. 6 D.P.R. 68/2005 (ricevute PEC e dati di certificazione).
"""
