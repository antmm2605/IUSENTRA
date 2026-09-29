/** Dati di esempio per le storie di Controllo Studio e Preparazione udienza (nessun dato reale). */

const fascicolo = { id: 'f1', etichetta: 'R.G. 1234/2026 — Bianchi c. Condominio Aurora', href: '/fascicoli/f1' }

export function elencoUdienzePayload() {
  return {
    ok: true,
    puoModificare: true,
    riepilogo: { settimana: 2, daPreparare: 1, preparate: 1 },
    fascicoli: [{ value: 'f1', label: fascicolo.etichetta }],
    udienze: [
      {
        idAppuntamento: 'a1', idFascicolo: 'f1', titolo: 'Udienza Bianchi c. Condominio Aurora', dataOra: '2026-09-30T10:00:00',
        quando: 'Domani alle 10:00', luogo: 'Tribunale di Bari, aula 3', cliente: 'Mario Bianchi', giudice: 'Dott.ssa Neri',
        fascicolo, stato: 'Da preparare', passiFatti: 0, href: '',
      },
      {
        idAppuntamento: 'a2', idFascicolo: 'f1', titolo: 'Udienza di rinvio — Bianchi c. Condominio Aurora', dataOra: '2026-10-03T11:30:00',
        quando: 'Tra 4 giorni, alle 11:30', luogo: 'Tribunale di Bari, aula 7', cliente: 'Mario Bianchi', giudice: 'Dott.ssa Neri',
        fascicolo, stato: 'In preparazione', passiFatti: 2, href: '/wizard-pro/s1/step/3',
      },
    ],
    concluse: [],
  }
}

export function schedaUdienzaPayload() {
  const fonte = { norma: 'art. 183 c.p.c.', estratto: 'Le parti devono comparire personalmente.', url: 'https://www.normattiva.it/' }
  return {
    ok: true, puoModificare: true, id: 's1', titolo: 'Udienza R.G. 1234/2026 — Bianchi c. Condominio Aurora', stato: '1 di 5 passi',
    completata: false, passoCorrente: 1,
    passi: [
      { n: 1, chiave: 'quadro', titolo: 'Quadro della causa', descrizione: 'Dati dell\'udienza, termini aperti e verifiche di legge.', fatto: true },
      { n: 2, chiave: 'documenti', titolo: 'Documenti', descrizione: 'Cosa portare o avere pronto.', fatto: false },
      { n: 3, chiave: 'strategia', titolo: 'Strategia', descrizione: 'Argomenti, richieste al giudice ed eccezioni.', fatto: false },
      { n: 4, chiave: 'partenza', titolo: 'Prima di uscire', descrizione: 'Cliente avvisato, collegamento o trasferta.', fatto: false },
      { n: 5, chiave: 'esito', titolo: 'Esito', descrizione: 'Rinvio, termini assegnati, nota nel fascicolo.', fatto: false },
    ],
    udienza: {
      dataOra: '2026-09-30T10:00:00', quando: 'Domani alle 10:00', luogo: 'Tribunale di Bari, aula 3', ufficio: 'Tribunale di Bari',
      giudice: 'Dott.ssa Neri', sezione: '', rg: '1234/2026', collegamento: '', agendaHref: '/agenda',
    },
    causa: { cliente: 'Mario Bianchi', controparte: 'Condominio Aurora', avvocatoControparte: '', oggetto: 'Infiltrazioni e risarcimento danni', fascicolo, idCliente: 'c1' },
    termini: [{ titolo: 'Deposito memoria 171-ter n. 2', data: '2026-10-01', perentorio: true, href: '/scadenziario' }],
    attivita: [],
    tipoUdienza: 'prima_comparizione',
    tipi: [
      { value: 'prima_comparizione', label: 'Prima comparizione e trattazione (art. 183 c.p.c.)', senzaPresenza: false },
      { value: 'altra', label: 'Altra udienza', senzaPresenza: false },
    ],
    verifiche: [{ id: 'comparizione_cliente', testo: 'Il cliente sa che deve comparire personalmente', fatta: true, fonte }],
    avvisoAssenza: { testo: 'Se nessuna parte compare, il giudice fissa una nuova udienza.', fonte: { norma: 'art. 309 c.p.c.', estratto: '', url: '' } },
    documenti: [{ indice: 0, etichetta: 'Atto di citazione', stato: 'pronto', statoEtichetta: 'Pronto', firmato: false, href: '' }],
    campi: {},
    esito: { valore: '', rinvioData: '', rinvioOra: '', noteVerbale: '', azioni: '', termini: [], rinvioAgendaHref: '' },
    esiti: [{ value: 'rinvio', label: 'Rinvio' }, { value: 'riserva', label: 'Riserva' }],
    messaggioClienteHref: '/messaggi/nuovo',
  }
}

export function controlloStudioPayload() {
  const azione = (etichetta: string, href: string, principale = false) => ({ etichetta, href, endpoint: '', conferma: '', principale })
  return {
    ok: true, oggi: '2026-09-29', urgenti: 1, fonti_non_disponibili: [],
    riepilogo: '1 termine scaduto da verificare e 1 udienza fra oggi e domani.',
    aree: [
      { area: 'scadenze', etichetta: 'Scadenze', totale: 1, urgenti: 1 },
      { area: 'agenda', etichetta: 'Udienze e appuntamenti', totale: 1, urgenti: 0 },
      { area: 'notifiche', etichetta: 'Notifiche', totale: 0, urgenti: 0 },
      { area: 'comunicazioni', etichetta: 'Comunicazioni', totale: 0, urgenti: 0 },
      { area: 'incassi', etichetta: 'Incassi', totale: 0, urgenti: 0 },
    ],
    fasce: [
      { fascia: 'scaduto', etichetta: 'Scaduto: da recuperare subito' }, { fascia: 'oggi', etichetta: 'Oggi' },
      { fascia: 'domani', etichetta: 'Domani' }, { fascia: 'settimana', etichetta: 'Nei prossimi 7 giorni' },
      { fascia: 'prossimi', etichetta: 'Entro 30 giorni' }, { fascia: 'senza_data', etichetta: 'Senza data' },
    ],
    voci: [
      {
        id: 'scadenza-1', area: 'scadenze', area_etichetta: 'Scadenze', titolo: 'Notifica atto di precetto', dettaglio: 'termine perentorio',
        data: '2026-09-28', ora: '', gravita: 'critica', etichetta: 'Scaduto da ieri', fascicolo, importo: 0, fascia: 'scaduto',
        azioni: [azione('Apri il termine', '/scadenziario', true)],
      },
      {
        id: 'agenda-1', area: 'agenda', area_etichetta: 'Udienze e appuntamenti', titolo: 'Udienza Bianchi c. Condominio Aurora',
        dettaglio: 'Tribunale di Bari, aula 3', data: '2026-09-30', ora: '10:00', gravita: 'alta', etichetta: 'Udienza · da preparare',
        fascicolo, importo: 0, fascia: 'domani', azioni: [azione("Prepara l'udienza", '/wizard-pro/', true), azione('Apri in agenda', '/agenda')],
      },
    ],
    incassi: { da_incassare: 1200, scaduto: 0, parcelle_scadute: 0, incassato_mese: 0 },
  }
}
