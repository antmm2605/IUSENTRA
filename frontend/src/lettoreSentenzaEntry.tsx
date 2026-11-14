import { createRoot } from 'react-dom/client'
import LettoreSentenzaApp from './components/LettoreSentenzaApp'

const root = document.getElementById('lettore-sentenza-root')
if (root) createRoot(root).render(<LettoreSentenzaApp />)
