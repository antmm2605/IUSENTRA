# 2.467.1 — Elenco dei fascicoli sempre disponibile

- L'elenco dei fascicoli non si svuota più quando la lettura automatica di documenti e PEC sta
  aggiornando il catalogo (V46): risponde con tutti i fascicoli e indica quanti sono in aggiornamento.
  Prima bastava un solo aggiornamento in sospeso per lasciare la pagina vuota, soprattutto dopo un deploy.
- Se il catalogo è davvero in riallineamento dopo un riavvio, la pagina attende fino a circa un minuto
  invece di arrendersi dopo meno di un secondo.
- La preparazione del catalogo durante il deploy non fallisce più per gli aggiornamenti in corso.
- La verifica della biblioteca normativa dopo il deploy riprova la ricerca semantica se Ollama è ancora
  occupato dal modello di Lex appena provato.
