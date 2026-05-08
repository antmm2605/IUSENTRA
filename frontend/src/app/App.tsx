import LegacyOperationalShell from '../App'
import { AppProviders } from './providers'
import '../styles/iusentra-design-system.css'

export default function App() {
  return (
    <AppProviders>
      <LegacyOperationalShell />
    </AppProviders>
  )
}
