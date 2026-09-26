"""Prove sul campo delle letture automatiche: PEC ostili e pagine anonimizzate.

Due banchi di prova ripetibili, nati dalle rassegne del 25-26/09/2026:

- `pec_ostili`: 30 PEC anonimizzate costruite per ingannare chi legge
  (istruzioni nascoste, marcatori di provenienza, mittenti contraffatti,
  numeri e date civetta). Si misurano le regole in produzione e, a parte, un
  modello locale con e senza marcatore di provenienza nel contesto (Lasso,
  «The Provenance Tax»).
- `pagine_anonime`: 30 pagine italiane anonimizzate con i valori veri noti,
  per misurare il cancello di ancoraggio stadio per stadio (Reducto, «From
  Ingestion to Agents»): quanti valori inventati passano e quanti valori veri
  vengono bloccati a torto.

I banchi non contengono dati dello studio: nomi, codici e numeri sono
inventati. Le misure con i modelli si lanciano con `scripts/collaudo_ai.py`.
"""
