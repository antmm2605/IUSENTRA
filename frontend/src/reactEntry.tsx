import React from 'react'
import ReactDOM from 'react-dom/client'
import type { ComponentType } from 'react'
import App from './app/App'
import SupportOperatorRoom from './components/SupportOperatorRoom'

type ReactEntryOptions = {
  root: HTMLElement
  shouldMountSupportOperator: boolean
}

export async function mountReactApp({ root, shouldMountSupportOperator }: ReactEntryOptions) {
  const reactRoot = ReactDOM.createRoot(root)
  const Component = resolveDefaultComponent(shouldMountSupportOperator ? SupportOperatorRoom : App)

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
