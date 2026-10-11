import React from 'react'
import {createRoot} from 'react-dom/client'
import {OfflineWorkspace} from './features/offline/OfflineWorkspace.jsx'
createRoot(document.getElementById('offline-root')).render(<OfflineWorkspace />)
