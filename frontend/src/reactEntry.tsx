import React from 'react'
import ReactDOM from 'react-dom/client'
import type { ComponentType } from 'react'
import App from './app/App'
import SupportOperatorRoom from './components/SupportOperatorRoom'

type ReactEntryOptions = {
  root: HTMLElement
  shouldMountSupportOperator: boolean
  shouldMountSupportCustomer?: boolean
  shouldMountPiattaforma?: boolean
  shouldMountAccesso?: boolean
  shouldMountPortaleToken?: boolean
  shouldMountPagamento?: boolean
}

export async function mountReactApp({
  root,
  shouldMountSupportOperator,
  shouldMountSupportCustomer = false,
  shouldMountPiattaforma = false,
  shouldMountAccesso = false,
  shouldMountPortaleToken = false,
  shouldMountPagamento = false,
}: ReactEntryOptions) {
  const reactRoot = ReactDOM.createRoot(root)
  // Le applicazioni fuori dalla cornice dello studio sono chunk separati,
  // caricati solo quando servono: le pagine dello studio non li scaricano.
  const selected: unknown = shouldMountPiattaforma
    ? await import('./components/PiattaformaApp')
    : shouldMountSupportCustomer
      ? await import('./components/SupportCustomerRoom')
      : shouldMountAccesso
        ? await import('./components/AccessoApp')
        : shouldMountPortaleToken
          ? await import('./components/PortaleTokenApp')
          : shouldMountPagamento
            ? await import('./components/PagamentoLinkApp')
            : shouldMountSupportOperator ? SupportOperatorRoom : App
  const Component = resolveDefaultComponent(selected)

  reactRoot.render(
    <React.StrictMode>
      <Component />
    </React.StrictMode>,
  )
}

function resolveDefaultComponent(component: unknown): ComponentType {
  const record = component as { default?: ComponentType; A?: ComponentType }
  const Component = typeof component === 'function' ? component as ComponentType : record.default ?? record.A
  if (!Component) {
    throw new Error('Componente React operativo non trovato nel bundle.')
  }
  return Component
}
