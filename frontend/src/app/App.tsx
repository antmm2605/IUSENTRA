import LegacyOperationalShell from '../App'
import { AppProviders } from './providers'

export default function App() {
  return (
    <AppProviders>
      <LegacyOperationalShell />
    </AppProviders>
  )
}
