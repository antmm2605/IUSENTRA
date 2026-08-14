export type CrmTone = 'info' | 'neutral' | 'warning' | 'success' | 'danger'

export type CrmRiscontro = {
  tipo: string
  etichetta: string
  certo: boolean
  ruolo: string
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
  }
  actions: {
    stato: string
    verificaConflitti: string
    converti: string
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
  }
  actions: {
    nuovo: string
    clienti: string
    preventivi: string
  }
  fonteDeontologica: string
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
    },
    actions: {
      stato: text(actions.stato),
      verificaConflitti: text(actions.verificaConflitti),
      converti: text(actions.converti),
    },
  }
}

export const emptyCrmData: CrmData = {
  source: 'vuoto',
  generatedAt: '',
  columns: [],
  summary: { totale: 0, aperti: 0, vinti: 0, persi: 0, tassoConversione: 0, perFonte: [] },
  options: { fonti: [], stati: [] },
  actions: { nuovo: '/crm/lead/nuovo', clienti: '/clienti', preventivi: '/preventivi/nuovo' },
  fonteDeontologica: '',
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
    return {
      source: text(payload.source, 'repository_reali'),
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
      },
      actions: {
        nuovo: text(actions.nuovo, '/crm/lead/nuovo'),
        clienti: text(actions.clienti, '/clienti'),
        preventivi: text(actions.preventivi, '/preventivi/nuovo'),
      },
      fonteDeontologica: text(payload.fonteDeontologica),
    }
  } catch {
    return emptyCrmData
  }
}
