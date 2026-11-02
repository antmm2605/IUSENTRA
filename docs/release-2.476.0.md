# IUSENTRA 2.476.0 — verifica a vista del 02/11/2026

Correzioni nate dal giro visivo completo su PC e telefono (fascicolo reale RG 2539/2025, pagina Contratti) e dalle
segnalazioni dell'avvocato.

## PEC collegate al fascicolo con certezza: tre controlli

- Nuova regola `pct/pec_collegamento_certo.py`: una PEC si collega con certezza a un fascicolo solo quando coincidono
  numero di ruolo con anno, nome e cognome del cliente e stesso ufficio giudiziario, e un solo fascicolo li soddisfa
  (stato `ruolo_cliente_ufficio_verificati`, tra i collegamenti certificati). Più fascicoli o un controllo mancante:
  nessun collegamento certo, resta la proposta. Base: art. 16 D.L. 179/2012; D.M. 44/2011.
- Riconvalida dello storico a lotti (`pct/pec_collegamento_certo_riconvalida.py`) dentro il recupero notturno: le PEC
  rimaste «proposte», «RG non sufficiente», «identità incompleta» o senza candidato si ricontrollano; collegate con
  certezza, gli allegati non già presenti e l'.eml entrano nel fascicolo con il flusso già esistente.
- Diagnosi della verifica sul server (`deploy/hetzner/verifica_pec_fascicolo.py`): solo conteggi per esito.

## Sentenza: definizione del fascicolo e crediti del capo spese come proposte da confermare

- `pct/sentenza_conclusiva.py`: la proposta nasce solo da un dispositivo che decide la causa; mai per sentenze non
  definitive o parziali, rimessione in istruttoria, separata ordinanza, cassazione con rinvio. Spese compensate
  ammesse (artt. 91, 92, 93, 132 c.p.c.; art. 88 c.p.a.).
- Pannello «Letture e verifiche» del fascicolo: riquadro «Proposte dalla sentenza da confermare» con «Conferma
  definizione / Respingi» e, per i crediti del capo spese, «Conferma credito / Respingi / Genera parcella».
- Riconoscimento anche dalle etichette del catalogo e dal testo, non solo dal tipo assegnato dal nome del file.

## Scadenze proposte già decorse

- `pct/proposte_decorse.py`: le proposte 127-ter (opposizione, note scritte) decorse senza conferma si chiudono come
  «Proposta superata» con traccia; quelle perentorie che possono comportare decadenza restano in un unico riquadro
  «Termini proposti già decorsi — verifica dell'avvocato» (art. 127-ter c.p.c.; artt. 152-155 c.p.c.).

## Interfaccia

- Contratti: campi del Riepilogo dentro la scheda, pulsanti disattivati riconoscibili, «Avvia pratica» allineato,
  menu «Area» e passi della pratica corretti su telefono, bozza non giustificata su telefono, scheda in colonna e
  titoli italiani delle clausole negoziabili.
- Modifica fascicolo: uno stato operativo importato fuori elenco resta selezionato (prima il menu mostrava «Bozza» e il
  salvataggio la scriveva sul fascicolo).
- Verifiche documentali: la finestra si apre da sola solo per verifiche non lette mai mostrate prima, non più a ogni
  pagina.
