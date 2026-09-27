import React from 'react'
import ReactDOM from 'react-dom/client'
import type { ComponentType } from 'react'
import App from './app/App'
import SupportOperatorRoom from './components/SupportOperatorRoom'

type ReactEntryOptions = {
  root: HTMLElement
  shouldMountSupportOperator: boolean
  shouldMountPiattaforma?: boolean
}

export async function mountReactApp({ root, shouldMountSupportOperator, shouldMountPiattaforma = false }: ReactEntryOptions) {
  const reactRoot = ReactDOM.createRoot(root)
  // Il pannello di piattaforma si carica solo quando serve: gli studi non lo scaricano.
  const selected: unknown = shouldMountPiattaforma
    ? await import('./components/PiattaformaApp')
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
