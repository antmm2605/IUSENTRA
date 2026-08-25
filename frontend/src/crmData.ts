export type CrmTone = 'info' | 'neutral' | 'warning' | 'success' | 'danger'

export type CrmRiscontro = {
  tipo: string
  etichetta: string
  certo: boolean
  ruolo: string
}

export type CrmConflictClearance = {
  richiesta: boolean
  decisione: string
  convertibile: boolean
  label: string
}

export type CrmEthicalWall = {
  id: string
  attiva: boolean
  gestibile: boolean
  titolo: string
  motivazione: string
  label: string
  utentiAutorizzati: string[]
}

export type CrmAml = {
  available: boolean
  id: string
  status: string
  label: string
  inScope: boolean
  suggestedLevel: string
  selectedLevel: string
  renewalAt: string
  sourceOfTruth: string
  clientePep: boolean
  paeseAltoRischio: boolean
  prestazione: string
  descrizionePrestazione: string
  scopoNatura: string
  titolareEffettivo: { nome: string; codiceFiscale: string; criterio: string; note: string }
  note: string
  screening: { outcome: string; checkedAt: string; sourceUrl: string; sourceVersion: string; snapshotHash: string; matches: number }
  actions: { avvia: string; aggiorna: string; conferma: string; screening: string }
}

export type CrmLead = {
  id: string
  denominazione: string
  codiceFiscale: string
  partitaIva: string
  email: string
  telefono: string
  fonte: string
  fonteLabel: string
  materia: string
  esigenza: string
  stato: string
  referente: string
  note: string
  clienteId: string
  motivoPerso: string
  creatoIl: string
  conflitto: {
    verificato: boolean
    livello: string
    label: string
    tone: CrmTone
    riscontri: CrmRiscontro[]
    clearance: CrmConflictClearance
  }
  barrieraRiservatezza: CrmEthicalWall
  antiriciclaggio: CrmAml
  actions: {
    stato: string
    verificaConflitti: string
    aggiorna: string
    converti: string
    decisioneConflitto: string
    creaBarrieraRiservatezza: string
    aggiornaBarrieraRiservatezza: string
    revocaBarrieraRiservatezza: string
  }
}

export type CrmColumn = {
  stato: string
  label: string
  tone: CrmTone
  count: number
  leads: CrmLead[]
}

export type CrmData = {
  source: string
  sourceOfTruth: string
  generatedAt: string
  columns: CrmColumn[]
  summary: {
    totale: number
    aperti: number
    vinti: number
    persi: number
    tassoConversione: number
    perFonte: Array<{ fonte: string; label: string; count: number }>
  }
  options: {
    fonti: Array<{ value: string; label: string }>
    stati: Array<{ value: string; label: string; tone: CrmTone }>
    prestazioniAml: Array<{ value: string; label: string }>
    livelliAml: Array<{ value: string; label: string }>
    utentiAutorizzabili: Array<{ username: string; label: string }>
  }
  actions: {
    nuovo: string
    clienti: string
    preventivi: string
  }
  fonteDeontologica: string
  accesso: { operatore: string }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown, fallback = ''): string {
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (typeof value === 'number') return String(value)
  return fallback
}

function tone(value: unknown): CrmTone {
  const raw = text(value)
  return raw === 'info' || raw === 'warning' || raw === 'success' || raw === 'danger' ? raw : 'neutral'
}

function leadFrom(value: unknown): CrmLead | null {
  if (!isRecord(value) || !text(value.id)) return null
  const conflitto = isRecord(value.conflitto) ? value.conflitto : {}
  const clearance = isRecord(conflitto.clearance) ? conflitto.clearance : {}
  const aml = isRecord(value.antiriciclaggio) ? value.antiriciclaggio : {}
  const barriera = isRecord(value.barrieraRiservatezza) ? value.barrieraRiservatezza : {}
  const amlActions = isRecord(aml.actions) ? aml.actions : {}
  const screening = isRecord(aml.screening) ? aml.screening : {}
  const titolare = isRecord(aml.titolareEffettivo) ? aml.titolareEffettivo : {}
  const actions = isRecord(value.actions) ? value.actions : {}
  return {
    id: text(value.id),
    denominazione: text(value.denominazione, 'Contatto'),
    codiceFiscale: text(value.codiceFiscale),
    partitaIva: text(value.partitaIva),
    email: text(value.email),
    telefono: text(value.telefono),
    fonte: text(value.fonte, 'altro'),
    fonteLabel: text(value.fonteLabel, 'Altro'),
    materia: text(value.materia),
    esigenza: text(value.esigenza),
    stato: text(value.stato, 'NUOVO'),
    referente: text(value.referente),
    note: text(value.note),
    clienteId: text(value.clienteId),
    motivoPerso: text(value.motivoPerso),
    creatoIl: text(value.creatoIl),
    conflitto: {
      verificato: Boolean(conflitto.verificato),
      livello: text(conflitto.livello),
      label: text(conflitto.label, 'Verifica da eseguire'),
      tone: tone(conflitto.tone),
      riscontri: Array.isArray(conflitto.riscontri)
        ? conflitto.riscontri
            .map((r) => isRecord(r) ? {
              tipo: text(r.tipo),
              etichetta: text(r.etichetta),
              certo: Boolean(r.certo),
              ruolo: text(r.ruolo),
            } : null)
            .filter((r): r is CrmRiscontro => Boolean(r))
        : [],
      clearance: {
        richiesta: Boolean(clearance.richiesta),
        decisione: text(clearance.decisione),
        convertibile: Boolean(clearance.convertibile),
        label: text(clearance.label),
      },
    },
    barrieraRiservatezza: {
      id: text(barriera.id),
      attiva: Boolean(barriera.attiva),
      gestibile: Boolean(barriera.gestibile),
      titolo: text(barriera.titolo),
      motivazione: text(barriera.motivazione),
      label: text(barriera.label, 'Nessuna barriera informativa attiva'),
      utentiAutorizzati: Array.isArray(barriera.utentiAutorizzati)
        ? barriera.utentiAutorizzati.map((item) => text(item)).filter(Boolean)
        : [],
    },
    antiriciclaggio: {
      available: Boolean(aml.available),
      id: text(aml.id),
      status: text(aml.status, 'NON_AVVIATA'),
      label: text(aml.label, 'Non avviata'),
      inScope: aml.inScope === undefined ? true : Boolean(aml.inScope),
      suggestedLevel: text(aml.suggestedLevel),
      selectedLevel: text(aml.selectedLevel),
      renewalAt: text(aml.renewalAt),
      sourceOfTruth: text(aml.sourceOfTruth),
      clientePep: Boolean(aml.clientePep),
      paeseAltoRischio: Boolean(aml.paeseAltoRischio),
      prestazione: text(aml.prestazione),
      descrizionePrestazione: text(aml.descrizionePrestazione),
      scopoNatura: text(aml.scopoNatura),
      titolareEffettivo: {
        nome: text(titolare.nome),
        codiceFiscale: text(titolare.codice_fiscale ?? titolare.codiceFiscale),
        criterio: text(titolare.criterio),
        note: text(titolare.note),
      },
      note: text(aml.note),
      screening: {
        outcome: text(screening.outcome),
        checkedAt: text(screening.checkedAt),
        sourceUrl: text(screening.sourceUrl),
        sourceVersion: text(screening.sourceVersion),
        snapshotHash: text(screening.snapshotHash),
        matches: Number(screening.matches) || 0,
      },
      actions: {
        avvia: text(amlActions.avvia),
        aggiorna: text(amlActions.aggiorna),
        conferma: text(amlActions.conferma),
        screening: text(amlActions.screening),
      },
    },
    actions: {
      stato: text(actions.stato),
      verificaConflitti: text(actions.verificaConflitti),
      aggiorna: text(actions.aggiorna),
      converti: text(actions.converti),
      decisioneConflitto: text(actions.decisioneConflitto),
      creaBarrieraRiservatezza: text(actions.creaBarrieraRiservatezza),
      aggiornaBarrieraRiservatezza: text(actions.aggiornaBarrieraRiservatezza),
      revocaBarrieraRiservatezza: text(actions.revocaBarrieraRiservatezza),
    },
  }
}

export const emptyCrmData: CrmData = {
  source: 'vuoto',
  sourceOfTruth: '',
  generatedAt: '',
  columns: [],
  summary: { totale: 0, aperti: 0, vinti: 0, persi: 0, tassoConversione: 0, perFonte: [] },
  options: { fonti: [], stati: [], prestazioniAml: [], livelliAml: [], utentiAutorizzabili: [] },
  actions: { nuovo: '/crm/lead/nuovo', clienti: '/clienti', preventivi: '/preventivi/nuovo' },
  fonteDeontologica: '',
  accesso: { operatore: '' },
}

export async function getCrmPage(): Promise<CrmData> {
  try {
    const response = await fetch('/api/v1/ui/crm', {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyCrmData
    const payload = await response.json() as Record<string, unknown>
    const summary = isRecord(payload.summary) ? payload.summary : {}
    const options = isRecord(payload.options) ? payload.options : {}
    const actions = isRecord(payload.actions) ? payload.actions : {}
    const accesso = isRecord(payload.accesso) ? payload.accesso : {}
    return {
      source: text(payload.source, 'repository_reali'),
      sourceOfTruth: text(payload.sourceOfTruth),
      generatedAt: text(payload.generatedAt),
      columns: Array.isArray(payload.columns)
        ? payload.columns
            .map((column) => isRecord(column) ? {
              stato: text(column.stato),
              label: text(column.label, text(column.stato)),
              tone: tone(column.tone),
              count: Number(column.count) || 0,
              leads: Array.isArray(column.leads)
                ? column.leads.map(leadFrom).filter((lead): lead is CrmLead => Boolean(lead))
                : [],
            } : null)
            .filter((column): column is CrmColumn => Boolean(column && column.stato))
        : [],
      summary: {
        totale: Number(summary.totale) || 0,
        aperti: Number(summary.aperti) || 0,
        vinti: Number(summary.vinti) || 0,
        persi: Number(summary.persi) || 0,
        tassoConversione: Number(summary.tassoConversione) || 0,
        perFonte: Array.isArray(summary.perFonte)
          ? summary.perFonte
              .map((f) => isRecord(f) ? { fonte: text(f.fonte), label: text(f.label), count: Number(f.count) || 0 } : null)
              .filter((f): f is { fonte: string; label: string; count: number } => Boolean(f))
          : [],
      },
      options: {
        fonti: Array.isArray(options.fonti)
          ? options.fonti.map((f) => isRecord(f) ? { value: text(f.value), label: text(f.label) } : null).filter((f): f is { value: string; label: string } => Boolean(f))
          : [],
        stati: Array.isArray(options.stati)
          ? options.stati.map((s) => isRecord(s) ? { value: text(s.value), label: text(s.label), tone: tone(s.tone) } : null).filter((s): s is { value: string; label: string; tone: CrmTone } => Boolean(s))
          : [],
        prestazioniAml: Array.isArray(options.prestazioniAml)
          ? options.prestazioniAml.map((item) => isRecord(item) ? { value: text(item.value), label: text(item.label) } : null).filter((item): item is { value: string; label: string } => Boolean(item && item.value))
          : [],
        livelliAml: Array.isArray(options.livelliAml)
          ? options.livelliAml.map((item) => isRecord(item) ? { value: text(item.value), label: text(item.label) } : null).filter((item): item is { value: string; label: string } => Boolean(item && item.value))
          : [],
        utentiAutorizzabili: Array.isArray(options.utentiAutorizzabili)
          ? options.utentiAutorizzabili.map((item) => isRecord(item) ? { username: text(item.username), label: text(item.label, text(item.username)) } : null).filter((item): item is { username: string; label: string } => Boolean(item && item.username))
          : [],
      },
      actions: {
        nuovo: text(actions.nuovo, '/crm/lead/nuovo'),
        clienti: text(actions.clienti, '/clienti'),
        preventivi: text(actions.preventivi, '/preventivi/nuovo'),
      },
      fonteDeontologica: text(payload.fonteDeontologica),
      accesso: { operatore: text(accesso.operatore) },
    }
  } catch {
    return emptyCrmData
  }
}
