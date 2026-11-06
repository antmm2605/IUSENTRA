# Release 2.484.0 — termine lungo prudente, testo integro delle sentenze, catalogo riallineato, notifica della sentenza e guida pratica

Collaudo da avvocato del fascicolo Alessi II c. MIM (RG 2539/2025, Tribunale di Velletri, lavoro), 06/11/2026: le
correzioni valgono per tutti i fascicoli e tutte le materie.

## Termine lungo dalla decisione quando il deposito non è certo

Una sentenza comunicata senza data certa di deposito (né dal portale, né da un timbro «pubblicata il») aveva la
scadenza contata dal giorno della comunicazione di cancelleria, che arriva dopo. Per Alessi la scadenza era
l'08/04/2027, ma la sentenza ex art. 429 c.p.c. è stata decisa e firmata il 07/10/2026 («ha pronunciato in pari data»,
«Velletri, 7 ottobre 2026 Il giudice»).

Ora la bozza si conta dalla data della decisione scritta nella sentenza del fascicolo. La pubblicazione (art. 133
c.p.c.) non può precedere la decisione, quindi la scadenza (art. 327 c.p.c.) non è mai successiva a quella vera: per
Alessi diventa il 07/04/2027. Restano l'avviso «data di deposito non certa» e la riconvalida, finché arriva la data
certa del deposito, che prevale. Se le decisioni lette sono più d'una o lontane dalla comunicazione, non si sceglie.
File: `pct/termine_lungo_sentenza.py` (`data_decisione`), `pct/riconvalida_termine_lungo.py`.

## Testo integro degli allegati PEC

Il testo di ogni allegato era tagliato a 20.000 caratteri. Il dispositivo, le spese liquidate e la data in calce di
una sentenza lunga si perdevano (Alessi: 35.000 caratteri). Il limite ora è 400.000 caratteri, come difesa da allegati
anomali. I 195 allegati già tagliati (160 PEC) si rileggono con `python -m scripts.rileggi_allegati_pec_tagliati
--tenant <slug>`, poi si ripassano le PEC. Il testo tagliato non viene più riusato per allegati identici
(`pct/pec_pipeline.py`).

## Udienze impossibili

Una vecchia lettura aveva preso la data di nascita della cliente («nata il 30/05/1990») per un'udienza. La
riconciliazione delle letture storiche ora annulla, con il motivo, le udienze rilevate automaticamente con data
anteriore all'anno di iscrizione a ruolo: una causa non ha udienze prima di esistere
(`web/services/rettifiche_letture_storiche.py`).

## Catalogo: conferme fatte con regole superate

Le classificazioni automatiche confermate in blocco prima della revisione delle regole del 04/11/2026 restavano
sbagliate per sempre. Per esempio: contratti di lavoro come «Decreto», precedenti allegati come sentenze della causa,
PEC di deposito come «Lettera». Una correzione scritta a mano dall'avvocato non si tocca mai. Una conferma di una
proposta automatica, invece, si ricontrolla quando cambiano le regole. Se il contenuto indica con sicurezza (almeno
95%) un'altra voce, la conferma torna proposta con la spiegazione: «Regole aggiornate: confermato il 14/09/2026 come
«Decreto»; ora il contenuto indica «Contratto di lavoro»». Decide l'avvocato; altrimenti la conferma resta.
Misura sulla copia dello studio: 99 conferme, 24 proposte di correzione, controllate a campione
(`pct/document_intelligence/catalog_pipeline.py`, `web/services/catalogo_archivio_runtime.py`).

## Notifica della sentenza

- Destinatari: solo le parti nominate nella sentenza (non, ad esempio, l'istituto scolastico citato nel ricorso).
- Parte contumace: notifica alla parte personalmente (art. 292 c.p.c.). Per lo Stato, presso l'Avvocatura del
  distretto del giudice che ha pronunciato (art. 11 R.D. 1611/1933).
- Avvertenza: dalla notifica decorrono il termine breve (artt. 325 e 434 c.p.c.) e, contro una pubblica
  amministrazione condannata a pagare somme, i 120 giorni prima di precetto ed esecuzione (art. 14 D.L. 669/1996,
  testo vigente letto su Normattiva il 06/11/2026).
- File: `pct/obblighi_notifica.py`, `web/services/obblighi_notifica_runtime.py`. Nuove norme nel registro: artt. 292
  e 431 c.p.c., art. 14 D.L. 669/1996, art. 112 c.p.a., artt. 9 e 30 D.P.R. 115/2002.

## Guida pratica

- **Checklist e fase:** la checklist riconosce procura, contratti e documento d'identità tra i documenti del
  fascicolo. Con la causa già iscritta a ruolo la checklist di redazione non blocca più e la guida lo spiega.
- **Copertura onesta:** le schede che si dichiarano «classificazione di base» lo mostrano.
- **Fonti per parole intere:** «tar» non è più trovato in «notare», «pensione» in «sospensione». Spariscono appalti,
  edilizia e IMU dalle schede che non c'entrano.
- **Sezione fiscale curata:** non viene più sostituita da quella generica.
- **Scheda 222050** (pubblico impiego, retribuzione) scritta per intero, con:
  - rito, competenza (art. 413 c.p.c.) e 17 norme verificate;
  - termini con i giorni (415, 416, 434, 327, art. 14 D.L. 669/1996);
  - nessuna mediazione obbligatoria (art. 5 D.Lgs. 28/2010) e conciliazione facoltativa (art. 410);
  - contributo unificato (art. 9, comma 1-bis);
  - anticipazione forfettaria con l'abrogazione della L. 319/1958 dal 01/01/2027.

Test: `tests/test_riconvalida_termine_lungo.py`, `tests/test_pec_allegati_testo_integro.py`,
`tests/test_reading_archive_consistency.py`,
`tests/test_fascicolo_document_catalog_pipeline.py`, `tests/test_obblighi_notifica.py`, `tests/test_guida_pratica_service.py`.
