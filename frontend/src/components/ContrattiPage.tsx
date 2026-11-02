import { rottaContratti } from '../contrattiData'
import { EmptyState } from '../ui/EmptyState'
import { Page } from '../ui/Page'
import { ContrattiCatalogo } from './contratti/ContrattiCatalogo'
import { ContrattiNuovo } from './contratti/ContrattiNuovo'
import { ContrattiPratica } from './contratti/ContrattiPratica'
import './ContrattiPage.css'

export function ContrattiPage({ percorso }: { percorso?: string } = {}) {
  const rotta = rottaContratti(percorso ?? window.location.pathname)
  if (!rotta) return <Page title="Contratti"><EmptyState title="Pagina non trovata" message="Torna al catalogo dei contratti." /></Page>
  if (rotta.modo === 'nuovo') return <ContrattiNuovo contrattoId={rotta.contrattoId} />
  if (rotta.modo === 'pratica') return <ContrattiPratica praticaId={rotta.praticaId} />
  return <ContrattiCatalogo />
}
