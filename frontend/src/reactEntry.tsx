import React from 'react'
import ReactDOM from 'react-dom/client'
import type { ComponentType } from 'react'

type ReactEntryOptions = {
  root: HTMLElement
  shouldMountSupportOperator: boolean
}

export async function mountReactApp({ root, shouldMountSupportOperator }: ReactEntryOptions) {
  const reactRoot = ReactDOM.createRoot(root)
  const module = shouldMountSupportOperator ? await import('./components/SupportOperatorRoom') : await import('./app/App')
  const Component = resolveDefaultComponent(module)

  reactRoot.render(
    <React.StrictMode>
      <Component />
    </React.StrictMode>,
  )
}

function resolveDefaultComponent(module: unknown): ComponentType {
  const record = module as { default?: ComponentType; A?: ComponentType }
  const Component = record.default ?? record.A
  if (!Component) {
    throw new Error('Componente React operativo non trovato nel bundle.')
  }
  return Component
}
