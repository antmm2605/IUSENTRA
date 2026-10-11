import { createPortal } from 'react-dom'
import { useState } from 'react'
import { OperationalModal } from '../OperationalModal'
import { SourceDocumentReader } from '../SourceDocumentModal'
import type { OrganismDetail } from './types'
import { publicModule } from './publicModule'
import { ActionButton as Button } from './ActionButton'

/** Consultazione anonima; soltanto le risorse verificate possono entrare nella pratica. */
export function OrganismoWebsite({ organism, url, dirty, busy, saved, canWrite, acquire, close }: {
  organism: OrganismDetail; url: string; dirty: boolean; busy: boolean; saved: boolean; canWrite: boolean
  acquire: (url: string) => Promise<boolean>; close: () => void
}) {
  const [error, setError] = useState('')
  const [acquiring, setAcquiring] = useState(false)
  const [pages, setPages] = useState([url])
  const currentUrl = pages[pages.length - 1]
  const wordModule = /\.docx?(?:[?#]|$)/i.test(currentUrl) ? publicModule(currentUrl, organism.risorse).resource : null
  const follow = (target: string) => {
    const { file, resource } = publicModule(target, organism.risorse)
    if (!file) {
      try {
        const address = new URL(target)
        if (!['https:', 'http:'].includes(address.protocol) || address.username || address.password) {
          setError('Collegamento pubblico non valido. Nessun dato della pratica è stato inviato.')
          return true
        }
        setError('')
        setPages(previous => previous[previous.length - 1] === target ? previous : [...previous, target])
      } catch { setError('Collegamento pubblico non valido.') }
      return true
    }
    if (!resource) {
      setError('Questo file non risulta fra le risorse verificate dell’organismo. Aggiorna il controllo delle fonti prima di acquisirlo nel fascicolo.')
      return true
    }
    if (busy || acquiring) return true
    if (!canWrite) {
      setError('Puoi consultare le fonti; il tuo profilo non consente di acquisire documenti nel fascicolo.')
      return true
    }
    if (dirty || !saved) {
      setError('Salva prima il procedimento con l’organismo scelto; poi puoi acquisire il modulo nel fascicolo.')
      return true
    }
    setError('')
    setAcquiring(true)
    void acquire(resource.url).then(ok => {
      if (ok) close()
      else setError('Acquisizione non confermata. Il procedimento conserva il motivo dell’errore; puoi chiudere questa finestra e riprovare.')
    }).catch(() => setError('Connessione interrotta: acquisizione non confermata. Riprova senza modificare il documento originale.'))
      .finally(() => setAcquiring(false))
    return true
  }
  return createPortal(<OperationalModal open title={organism.nome} eyebrow="Sito dell’organismo"
    ariaLabel="Sito dell’organismo di mediazione" boxClassName="iu-source-reader-box"
    onClose={() => { if (!acquiring) close() }}>
    {error ? <p role="alert">{error}</p> : null}
    {acquiring ? <p role="status">Acquisizione del modulo nel fascicolo…</p> : null}
    {pages.length > 1 ? <Button disabled={acquiring} onClick={() => { setError(''); setPages(previous => previous.slice(0, -1)) }}>Indietro nel sito</Button> : null}
    {wordModule ? <section aria-label="Modulo Word dell’organismo">
      <h3>{wordModule.label || 'Modulo Word'}</h3>
      <p>Acquisisci l’originale nel fascicolo, poi usa «Prepara copia Word da compilare» per aprire una copia modificabile nell’editor.</p>
      <Button disabled={busy || acquiring || !canWrite || dirty || !saved}
        onClick={() => follow(currentUrl)}>Acquisisci modulo nel fascicolo</Button>
      {dirty || !saved ? <p>Salva prima il procedimento con l’organismo scelto.</p> : null}
      {!canWrite ? <p>Il tuo profilo non consente di acquisire documenti nel fascicolo.</p> : null}
    </section> : <SourceDocumentReader href={`/api/v1/ui/document-reader/web?${new URLSearchParams({ url: currentUrl })}`}
      label={organism.nome} onPublicLink={follow}/>}
  </OperationalModal>, document.body)
}
