import { IusStatusBadge } from './IusStatusBadge'

export type IusDocumentStatus =
  | 'pronto'
  | 'da_firmare'
  | 'pdfa_mancante'
  | 'ocr_mancante'
  | 'non_verificato'
  | 'deposito_pronto'
  | 'errore'

const labels: Record<IusDocumentStatus, string> = {
  pronto: 'Pronto',
  da_firmare: 'Firma mancante',
  pdfa_mancante: 'PDF/A mancante',
  ocr_mancante: 'OCR non eseguito',
  non_verificato: 'Non verificato',
  deposito_pronto: 'Pronto al deposito',
  errore: 'Da correggere',
}

const tones: Record<IusDocumentStatus, 'success' | 'warning' | 'danger' | 'info' | 'neutral'> = {
  pronto: 'success',
  da_firmare: 'warning',
  pdfa_mancante: 'warning',
  ocr_mancante: 'info',
  non_verificato: 'neutral',
  deposito_pronto: 'success',
  errore: 'danger',
}

export function IusDocumentStatusBadge({ status }: { status: IusDocumentStatus }) {
  return <IusStatusBadge tone={tones[status]}>{labels[status]}</IusStatusBadge>
}
