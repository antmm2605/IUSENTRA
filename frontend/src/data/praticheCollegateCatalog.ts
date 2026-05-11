import praticheCollegateCatalog from '@iusentra-data/pratiche_collegate_catalog.json'
import codiciOggettoPstCatalog from '@iusentra-data/cataloghi/codici_oggetto_pst_ui.json'

export const NUOVO_FASCICOLO_LABELS = {
  title: 'Apertura nuovo fascicolo',
  subtitle: 'Compila i dati principali della pratica e collega il procedimento corretto.',
  sections: {
    datiGenerali: 'Dati generali',
    identificazioneGiudiziale: 'Identificazione giudiziale',
    annotazioni: 'Annotazioni',
  },
  fields: {
    pratica: 'Pratica',
    rifCartaceo: 'Rif. cartaceo',
    oggettoPratica: 'Oggetto pratica',
    praticheCollegate: 'Pratiche collegate',
    statoPratica: 'Stato della pratica',
    dataApertura: 'Data di apertura',
    dataArchiviazione: 'Data archiviazione',
    personalizzabile: 'Personalizzabile',
    annotazioni: 'Annotazioni',
    autoritaGiudiziaria: 'Autorità giudiziaria',
    numeroRuolo: 'Numero di ruolo',
    attorePrincipale: 'Attore principale',
    istruttorePmGip: 'Istruttore / P.M. / G.I.P.',
    cancelliere: 'Cancelliere',
    ctu: 'C.T.U.',
    ctp: 'C.T.P.',
  },
  actions: {
    salva: 'Salva fascicolo',
    elimina: 'Elimina',
    annulla: 'Annulla',
  },
} as const

export const STATI_PRATICA = [
  { value: 'bozza', label: 'Bozza' },
  { value: 'aperta', label: 'Aperta' },
  { value: 'in_istruttoria', label: 'In istruttoria' },
  { value: 'in_trattazione', label: 'In trattazione' },
  { value: 'sospesa', label: 'Sospesa' },
  { value: 'definita', label: 'Definita' },
  { value: 'archiviata', label: 'Archiviata' },
] as const

export type StatoPraticaValue = (typeof STATI_PRATICA)[number]['value']

export type PraticaCollegataItem = {
  codice: string
  label: string
  children?: PraticaCollegataItem[]
}

export type PraticaCollegataArea = {
  area: string
  label: string
  items: PraticaCollegataItem[]
}

export type PraticheCollegateCatalog = {
  versione: string
  fonte: {
    tipo: 'PST_XSD'
    nome: string
    percorso: string
    fileFontePrevalente: string
    url: string
    betaAmmessiProduzione: boolean
  }
  regolaDeposito: string
  areas: PraticaCollegataArea[]
}

export type PraticaCollegataFlat = PraticaCollegataItem & {
  area: string
  areaLabel: string
  parentCodice?: string
  parentLabel?: string
  registri?: string[]
  fileFonte?: string
}

export const PRATICHE_COLLEGATE_CATALOG = praticheCollegateCatalog as PraticheCollegateCatalog
export const PRATICHE_COLLEGATE = PRATICHE_COLLEGATE_CATALOG.areas

export type CodiceOggettoPstRecord = {
  codice: string
  descrizione: string
  descrizioniAlternative?: string[]
  registri: string[]
  area: string
  codicePadre: string
  descrizionePadre: string
  fileFonte: string
}

export type CodiciOggettoPstCatalog = {
  versione: string
  fonte: PraticheCollegateCatalog['fonte']
  supportoUi: {
    tipo: string
    descrizione: string
    righeCatalogoSupporto: number
  }
  totaleCodici: number
  records: CodiceOggettoPstRecord[]
}

export const CODICI_OGGETTO_PST_CATALOG = codiciOggettoPstCatalog as CodiciOggettoPstCatalog
export const CODICI_OGGETTO_PST = CODICI_OGGETTO_PST_CATALOG.records

export function flattenPraticheCollegate(): PraticaCollegataFlat[] {
  return PRATICHE_COLLEGATE.flatMap((area) =>
    area.items.flatMap((item) => {
      const parent: PraticaCollegataFlat = {
        ...item,
        area: area.area,
        areaLabel: area.label,
      }
      const children = (item.children || []).map((child) => ({
        ...child,
        area: area.area,
        areaLabel: area.label,
        parentCodice: item.codice,
        parentLabel: item.label,
      }))
      return [parent, ...children]
    }),
  )
}

export function flattenCodiciOggettoPst(): PraticaCollegataFlat[] {
  return CODICI_OGGETTO_PST.map((item) => ({
    codice: item.codice,
    label: item.descrizione,
    area: item.area,
    areaLabel: item.area,
    parentCodice: item.codicePadre,
    parentLabel: item.descrizionePadre,
    registri: item.registri,
    fileFonte: item.fileFonte,
  }))
}

const codiciOggettoIndex = new Map(CODICI_OGGETTO_PST.map((item) => [item.codice, item]))

export function findCodiceOggettoPst(codice: string): CodiceOggettoPstRecord | undefined {
  const needle = codice.trim()
  if (!needle) return undefined
  return codiciOggettoIndex.get(needle)
}

export function findPraticaCollegata(codice: string): PraticaCollegataFlat | undefined {
  const needle = codice.trim()
  if (!needle) return undefined
  const official = findCodiceOggettoPst(needle)
  if (official) {
    return {
      codice: official.codice,
      label: official.descrizione,
      area: official.area,
      areaLabel: official.area,
      parentCodice: official.codicePadre,
      parentLabel: official.descrizionePadre,
      registri: official.registri,
      fileFonte: official.fileFonte,
    }
  }
  return flattenPraticheCollegate().find((item) => item.codice === needle)
}

export function codiceOggettoPstSource(codice: string) {
  const official = findCodiceOggettoPst(codice)
  return {
    fonteCodiceOggetto: official ? CODICI_OGGETTO_PST_CATALOG.fonte.tipo : '',
    fileFonteCodiceOggetto: official?.fileFonte || '',
  }
}
