import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { CalendarClock, FileSearch } from 'lucide-react'
import { getScadenziarioPage, type ScadenziarioRow } from '../scadenziarioData'
import { formatDateIt } from '../formatting'
import { OperationalModal } from './OperationalModal'
import { SourceDocumentModal, SourceDocumentReader, type SourceDocument } from './SourceDocumentModal'
import VerificaNotifichePanel from './VerificaNotifichePanel'
import PresidioDetailDrawer from '../features/notifiche-legali/components/PresidioDetailDrawer'
import '../features/notifiche-legali/PresidiNotifiche.css'
import ControlloStudioAgendaDetail from './ControlloStudioAgendaDetail'
import type { Azione, Voce } from './ControlloStudioPage'

export default function ControlloStudioDetail({ voce, azione, onClose, onUpdated, onFatto }: {
  voce: Voce; azione?: Azione; onClose: () => void; onUpdated: () => void; onFatto: (voce: Voce, azione: Azione) => void
}) {
  const [row, setRow] = useState<ScadenziarioRow | null>(null)
  const [errore, setErrore] = useState('')
  const [source, setSource] = useState<SourceDocument | null>(null)
  const [tab, setTab] = useState('pec')
  useEffect(() => {
    if (voce.area !== 'scadenze') return
    let active = true
    const id = voce.id.replace(/^scadenza-/, '')
    void getScadenziarioPage({ focusId: id, compact: true, includeCalculator: false, view: 'tutte' })
      .then((data) => {
        if (!active) return
        const selected = data.items.find((item) => item.id === id)
        if (selected) setRow(selected)
        else setErrore('Il termine non è disponibile. Aggiorna il quadro dello studio.')
      }).catch(() => { if (active) setErrore('Il termine non si è caricato. Chiudi e riprova.') })
    return () => { active = false }
  }, [voce.area, voce.id])
  if (voce.area === 'agenda') return <ControlloStudioAgendaDetail voce={voce} azione={azione} onClose={onClose} onUpdated={onUpdated}/>
  if (voce.area === 'comunicazioni') return createPortal(<OperationalModal open ariaLabel="PEC selezionata"
    eyebrow="Comunicazione selezionata" title={voce.titolo} subtitle={voce.fascicolo?.etichetta || voce.dettaglio}
    onClose={onClose} actions={voce.fascicolo?.id ? <>
      <button type="button" aria-pressed={tab === 'pec'} onClick={() => setTab('pec')}>Leggi la PEC</button>
      <button type="button" aria-pressed={tab === 'notifiche'} onClick={() => setTab('notifiche')}>Verifica notifiche del fascicolo</button>
    </> : undefined} bodyClassName={tab === 'notifiche' ? 'iu-cs-dettaglio' : ''}>
    {tab === 'notifiche' ? <VerificaNotifichePanel fascicoloId={voce.fascicolo.id}/> : <SourceDocumentReader
      href={voce.azioni.find((a) => a.principale)?.href || ''} label={voce.titolo}/>}
  </OperationalModal>, document.body)
  if (voce.area === 'notifiche') return <PresidioDetailDrawer
    id={voce.id.replace(/^presidio-/, '')} onClose={onClose} onUpdated={onUpdated}/>
  const completa = voce.azioni.find((a) => Boolean(a.endpoint))
  return <>
    {createPortal(<OperationalModal open ariaLabel="Dettaglio del termine" eyebrow={<><CalendarClock size={15}/> Termine selezionato</>}
      title={voce.titolo} subtitle={voce.fascicolo?.etichetta} onClose={onClose} bodyClassName="iu-cs-dettaglio">
      {errore ? <p role="alert">{errore}</p> : !row ? <p role="status">Caricamento del termine…</p> : <>
        <dl className="iu-cs-dettaglio__fatti">
          <div><dt>Cliente</dt><dd>{row.clientLabel || 'Da collegare'}</dd></div>
          <div><dt>Fascicolo</dt><dd>{row.fascicoloLabel || 'Non collegato'}</dd></div>
          <div><dt>Quando</dt><dd>{formatDateIt(row.date)} · {row.daysLabel}</dd></div>
          <div><dt>Tipo</dt><dd>{row.typeLabel}{row.peremptory ? ' · Perentorio' : ''}</dd></div>
          <div><dt>Stato</dt><dd>{row.statusLabel}</dd></div>
          <div><dt>Ufficio</dt><dd>{row.officeLabel || 'Non indicato'}</dd></div>
        </dl>
        <p className="iu-cs-dettaglio__note">{row.detailDescription || row.description || 'Nessuna nota aggiuntiva.'}</p>
        {row.type.toUpperCase() === 'NOTIFICA' && row.fascicoloId ? <VerificaNotifichePanel fascicoloId={row.fascicoloId}/> : null}
        {row.sourceHref ? <button type="button" className="iu-cs-aggiorna" onClick={() => setSource({
          href: row.sourceHref, label: row.sourceLabel || 'Fonte del termine', context: row.fascicoloLabel,
        })}><FileSearch size={16}/> Leggi la fonte</button> : <p>Fonte documentale non collegata: verifica il termine nel fascicolo.</p>}
        {completa && !['COMPLETATO', 'ANNULLATO'].includes(row.status) ? <button type="button" className="iu-cs-aggiorna"
          onClick={() => onFatto(voce, completa)}>{completa.etichetta}</button> : null}
      </>}
    </OperationalModal>, document.body)}
    <SourceDocumentModal source={source} onClose={() => setSource(null)}/>
  </>
}
