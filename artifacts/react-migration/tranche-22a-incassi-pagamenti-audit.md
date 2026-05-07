# Tranche 22A - Audit incassi e pagamenti

## Route legacy
- `/incassi-pagamenti`: superficie pagamenti/incassi, protetta da login e permessi economici.
- `/impostazioni/pagamenti`: configurazione provider legacy, mantenuta legacy/protetta.
- `/fatturazione`: archivio economico collegato a parcelle e stati pagamento.

## Contratto legacy rilevato
- Capture non autenticata: redirect a login, coerente con sessione obbligatoria.
- Handler Flask collegati: `web/blueprints/pagamenti.py` per link/checkout/webhook, `web/blueprints/fatturazione.py` per stato parcella/incasso.
- Template legacy: template pagamenti/fatturazione esistenti, non rimossi.
- POST legacy presenti: creazione link pagamento da parcella, cambio stato parcella, webhook provider.

## Strutture dati
- Incasso: parcella pagata, metodo pagamento, data pagamento, cliente e importo gia calcolato.
- Pagamento: link pagamento con parcella, cliente, importo, stato, provider pubblico, scadenza, data pagamento.
- Stati: `ATTESO`, `PAGATO`, `FALLITO`, `SCADUTO`, `ANNULLATO`; parcelle `EMESSA`, `PAGATA`, `SCADUTA`, `ANNULLATA`.
- Provider: Stripe, PayPal, Satispay, SumUp, bonifico; configurazioni riservate restano backend/legacy.
- Webhook: presenti nel legacy provider, non migrati in React.
- Link pagamento: generati/recuperati dal backend; React non chiama provider esterni.

## Gap per react_operational_full
- Esporre GET JSON reale per dashboard incassi.
- Esporre POST JSON solo per azioni legacy supportate: registra incasso, stato pagamento, link pagamento.
- Redigere stato provider senza segreti.
- Aggiornare UI React con loading/saving/success/error/empty state.
- Manifest/check anti-mascheramento da aggiornare.
