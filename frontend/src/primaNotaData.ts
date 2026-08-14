export type PrimaNotaMovimento = {
  id: string
  data: string
  tipo: string
  importo: number
  importoLabel: string
  categoria: string
  categoriaLabel: string
  controparte: string
  causale: string
  metodo: string
  documento: string
  fascicoloId: string
  parcellaId: string
  note: string
  stornabile: boolean
  actions: { storna: string }
}

export type PrimaNotaData = {
  source: string
  generatedAt: string
  filters: { dal: string; al: string; tipo: string }
  summary: {
    incassi: number
    incassiLabel: string
    pagamenti: number
    pagamentiLabel: string
    saldo: number
    saldoLabel: string
    movimenti: number
    perCategoria: Array<{ categoria: string; label: string; importo: number; importoLabel: string }>
  }
  movimenti: PrimaNotaMovimento[]
  options: {
    categorieIncasso: Array<{ value: string; label: string }>
    categoriePagamento: Array<{ value: string; label: string }>
    metodi: Array<{ value: string; label: string }>
  }
  actions: { registra: string; riconcilia: string; esporta: string }
  avvertenza: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown, fallback = ''): string {
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (typeof value === 'number') return String(value)
  return fallback
}

function option(value: unknown): { value: string; label: string } | null {
  return isRecord(value) ? { value: text(value.value), label: text(value.label) } : null
}

export const emptyPrimaNotaData: PrimaNotaData = {
  source: 'vuoto',
  generatedAt: '',
  filters: { dal: '', al: '', tipo: '' },
  summary: { incassi: 0, incassiLabel: '€ 0,00', pagamenti: 0, pagamentiLabel: '€ 0,00', saldo: 0, saldoLabel: '€ 0,00', movimenti: 0, perCategoria: [] },
  movimenti: [],
  options: { categorieIncasso: [], categoriePagamento: [], metodi: [] },
  actions: { registra: '/prima-nota/registra', riconcilia: '/prima-nota/riconcilia-parcelle', esporta: '/prima-nota/esporta.csv' },
  avvertenza: '',
}

export async function getPrimaNotaPage(params?: Record<string, string>): Promise<PrimaNotaData> {
  try {
    const search = new URLSearchParams(params || {})
    const response = await fetch(`/api/v1/ui/prima-nota${search.toString() ? `?${search}` : ''}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyPrimaNotaData
    const payload = await response.json() as Record<string, unknown>
    const filters = isRecord(payload.filters) ? payload.filters : {}
    const summary = isRecord(payload.summary) ? payload.summary : {}
    const options = isRecord(payload.options) ? payload.options : {}
    const actions = isRecord(payload.actions) ? payload.actions : {}
    return {
      source: text(payload.source, 'repository_reali'),
      generatedAt: text(payload.generatedAt),
      filters: { dal: text(filters.dal), al: text(filters.al), tipo: text(filters.tipo) },
      summary: {
        incassi: Number(summary.incassi) || 0,
        incassiLabel: text(summary.incassiLabel, '€ 0,00'),
        pagamenti: Number(summary.pagamenti) || 0,
        pagamentiLabel: text(summary.pagamentiLabel, '€ 0,00'),
        saldo: Number(summary.saldo) || 0,
        saldoLabel: text(summary.saldoLabel, '€ 0,00'),
        movimenti: Number(summary.movimenti) || 0,
        perCategoria: Array.isArray(summary.perCategoria)
          ? summary.perCategoria
              .map((r) => isRecord(r) ? { categoria: text(r.categoria), label: text(r.label), importo: Number(r.importo) || 0, importoLabel: text(r.importoLabel) } : null)
              .filter((r): r is { categoria: string; label: string; importo: number; importoLabel: string } => Boolean(r))
          : [],
      },
      movimenti: Array.isArray(payload.movimenti)
        ? payload.movimenti
            .map((m) => isRecord(m) && text(m.id) ? {
              id: text(m.id),
              data: text(m.data),
              tipo: text(m.tipo),
              importo: Number(m.importo) || 0,
              importoLabel: text(m.importoLabel),
              categoria: text(m.categoria),
              categoriaLabel: text(m.categoriaLabel),
              controparte: text(m.controparte),
              causale: text(m.causale),
              metodo: text(m.metodo),
              documento: text(m.documento),
              fascicoloId: text(m.fascicoloId),
              parcellaId: text(m.parcellaId),
              note: text(m.note),
              stornabile: Boolean(m.stornabile),
              actions: { storna: text(isRecord(m.actions) ? m.actions.storna : '', `/prima-nota/${text(m.id)}/storna`) },
            } : null)
            .filter((m): m is PrimaNotaMovimento => Boolean(m))
        : [],
      options: {
        categorieIncasso: Array.isArray(options.categorieIncasso) ? options.categorieIncasso.map(option).filter((o): o is { value: string; label: string } => Boolean(o)) : [],
        categoriePagamento: Array.isArray(options.categoriePagamento) ? options.categoriePagamento.map(option).filter((o): o is { value: string; label: string } => Boolean(o)) : [],
        metodi: Array.isArray(options.metodi) ? options.metodi.map(option).filter((o): o is { value: string; label: string } => Boolean(o)) : [],
      },
      actions: {
        registra: text(actions.registra, '/prima-nota/registra'),
        riconcilia: text(actions.riconcilia, '/prima-nota/riconcilia-parcelle'),
        esporta: text(actions.esporta, '/prima-nota/esporta.csv'),
      },
      avvertenza: text(payload.avvertenza),
    }
  } catch {
    return emptyPrimaNotaData
  }
}
