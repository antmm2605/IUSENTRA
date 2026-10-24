"""Presidio delle norme delle schede dei modelli d'atto.

Ogni notte, dopo l'aggiornamento della biblioteca normativa:
- ``verifica``: ogni norma citata da una scheda (base normativa e campi obbligatori) e' cercata nell'edizione vigente
  della biblioteca; si registrano testo, impronta SHA-256, URL ufficiale, abrogazione totale o di commi;
- ``repository``: stato per norma (impronta corrente e impronta approvata dall'avvocato) e proposte di revisione;
- ``proposte``: una norma cambiata, abrogata o assente genera una proposta motivata, con le differenze di testo;
  nessuna scheda cambia da sola: decide l'avvocato, e l'approvazione vale solo per l'impronta esaminata.

Base: art. 20 CAD (integrita' del testo); D.M. 44/2011 e c.p.c. per i requisiti dei singoli atti dichiarati nelle
schede. Le schede restano la fonte della struttura; questo pacchetto ne controlla le norme, non le riscrive.
"""
