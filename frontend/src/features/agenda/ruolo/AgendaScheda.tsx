import { useEffect, useState, type ReactNode } from 'react'
import { apiJson, apiPostJson } from '../../../lib/apiClient'
import type { AgendaEvent } from '../../../agendaData'
import { ETICHETTE_GENERE, contestoImpegno, genereImpegno, giornoEsteso, senzaOra, titoloImpegno } from './agendaRuoloModel'

type Proposta = {
  id: string
  titolo: string
  dataEtichetta: string
  perentorio: boolean
  spiegazione: string
  confermaHref: string
  scartaHref: string
}

type Lavorazione = {
  ok: boolean
  message?: string
  arrivo: string
  prova: { prova?: string; pecHref?: string; mimeHref?: string }
  proposte: Proposta[]
  collegamento: { link?: string; piattaforma?: string; idRiunione?: string; codice?: string }
  notificaHref: string
  fascicoloHref: string
  collegaPec?: {
    fascicoloId?: string; fascicolo?: string; motivo?: string; azione?: string; scegliHref?: string
    cliente?: string; rg?: string; alternative?: Array<{ id: string; fascicolo: string }>; nuovoFascicoloHref?: string
  }
  prossimo: string
}

type Esito = 'confermata' | 'scartata' | 'errore'

const VUOTA: Lavorazione = { ok: false, arrivo: '', prova: {}, proposte: [], collegamento: {}, notificaHref: '', fascicoloHref: '', prossimo: '' }

type Props = {
  event: AgendaEvent | null
  /** Le altre azioni sull'impegno (preparazione, promemoria, timesheet, scadenza collegata, Lex). */
  azioni?: ReactNode
  /** Apre il documento d'origine (il provvedimento nella PEC) nel visualizzatore. */
  onOpenSource: (event: AgendaEvent) => void
  onChanged: () => void
}

function quando(event: AgendaEvent): string {
  return `${giornoEsteso(event.date)}${senzaOra(event) ? ', entro la giornata' : ` ore ${event.timeLabel}`}`
}

export function AgendaScheda({ event, azioni, onOpenSource, onChanged }: Props) {
  const [lavorazione, setLavorazione] = useState<Lavorazione | null>(null)
  const [esiti, setEsiti] = useState<Record<string, Esito>>({})
  const [occupata, setOccupata] = useState('')
  const [collegata, setCollegata] = useState<'' | 'ok' | 'errore'>('')
  const [versione, setVersione] = useState(0)

  useEffect(() => {
    if (!event) return
    const controllo = new AbortController()
    setLavorazione(null)
    setEsiti({})
    setCollegata('')
    const parametri = new URLSearchParams({ id: event.id })
    if (event.matterId) parametri.set('fascicolo', event.matterId)
    void apiJson<Lavorazione>(`/api/v1/ui/agenda/lavorazione?${parametri.toString()}`, VUOTA,
      { signal: controllo.signal, activity: 'Preparazione della scheda…' })
      .then((risposta) => { if (!controllo.signal.aborted) setLavorazione({ ...VUOTA, ...risposta }) })
    return () => controllo.abort()
  }, [event?.id, versione])

  if (!event) {
    return <aside className="iu-ruolo-scheda" aria-label="Lavorazione dell'impegno">
      <p className="iu-ruolo-scheda__vuota">Seleziona un impegno per vedere il lavoro preparato dal software.</p>
    </aside>
  }

  const genere = genereImpegno(event)
  const { cliente, resto } = contestoImpegno(event)
  const proposte = lavorazione?.proposte || []
  const aperte = proposte.filter((p) => !esiti[p.id] || esiti[p.id] === 'errore')
  const remoto = lavorazione?.collegamento?.link ? lavorazione.collegamento : event.remoteHearingUrl
    ? { link: event.remoteHearingUrl, piattaforma: event.remoteHearingPlatform, idRiunione: event.remoteHearingMeetingId, codice: event.remoteHearingPasscode }
    : null

  const agisci = async (proposta: Proposta, azione: 'conferma' | 'scarta') => {
    setOccupata(proposta.id)
    const url = azione === 'conferma' ? proposta.confermaHref : proposta.scartaHref
    const corpo = azione === 'scarta' ? { motivo: 'Scartata dall’avvocato dalla scheda dell’agenda' } : {}
    const risposta = await apiPostJson<{ ok?: boolean }>(url, corpo, { ok: false })
    setEsiti((attuali) => ({ ...attuali, [proposta.id]: risposta.ok ? (azione === 'conferma' ? 'confermata' : 'scartata') : 'errore' }))
    setOccupata('')
    if (risposta.ok) onChanged()
  }

  const collega = async (fascicoloId?: string) => {
    const proposta = lavorazione?.collegaPec
    const scelto = fascicoloId || proposta?.fascicoloId
    if (!proposta?.azione || !scelto) return
    setOccupata('collegamento')
    const risposta = await apiPostJson<{ ok?: boolean }>(proposta.azione, { fascicolo_id: scelto }, { ok: false })
    setOccupata('')
    setCollegata(risposta.ok ? 'ok' : 'errore')
    if (risposta.ok) { onChanged(); setVersione((v) => v + 1) }
  }

  const confermaTutte = async () => {
    for (const proposta of aperte) await agisci(proposta, 'conferma')
  }

  return (
    <aside className={`iu-ruolo-scheda iu-ruolo-scheda--${genere}`} aria-label="Lavorazione dell'impegno">
      <div className="iu-ruolo-scheda__scorre">
        <header className="iu-ruolo-scheda__testa">
          <div className="iu-ruolo-scheda__tipo">{ETICHETTE_GENERE[genere]} · {quando(event)}</div>
          <h2>{titoloImpegno(event, { conTipo: true })}</h2>
          <div className="iu-ruolo-contesto">{cliente ? <b>{cliente}</b> : null}{cliente && resto ? ' · ' : ''}{resto}</div>
        </header>

        {lavorazione === null ? <p className="iu-ruolo-prossimo" role="status">Preparazione della scheda…</p> : null}

        {lavorazione?.arrivo || lavorazione?.prova?.prova ? (
          <section className="iu-ruolo-sezione" aria-label="Cosa è arrivato">
            <h3>Cosa è arrivato</h3>
            {lavorazione.arrivo ? <p>{lavorazione.arrivo}</p> : null}
            {lavorazione.prova?.prova ? <div className="iu-ruolo-prova">{lavorazione.prova.prova}</div> : null}
            <div className="iu-ruolo-azioni iu-ruolo-azioni--fonte">
              {event.sourceHref ? <button type="button" className="is-principale" onClick={() => onOpenSource(event)}>Leggi il provvedimento</button> : null}
              {lavorazione.prova?.pecHref ? <a href={lavorazione.prova.pecHref}>Apri la PEC</a> : null}
              {lavorazione.prova?.mimeHref ? <a href={lavorazione.prova.mimeHref} download>Scarica l’originale</a> : null}
            </div>
          </section>
        ) : null}

        {lavorazione?.collegaPec?.azione ? (
          <section className="iu-ruolo-sezione" aria-label="Collegamento al fascicolo">
            <h3>Collegamento al fascicolo</h3>
            {collegata === 'ok' ? <p className="iu-ruolo-esito is-ok">PEC collegata: il messaggio originale è conservato tra i documenti del fascicolo.</p>
              : lavorazione.collegaPec.fascicoloId ? <>
                <p>Il software propone il fascicolo <b>{lavorazione.collegaPec.fascicolo}</b>{lavorazione.collegaPec.motivo ? ` (${lavorazione.collegaPec.motivo})` : ''}.</p>
                <div className="iu-ruolo-azioni">
                  <button type="button" className="is-principale" disabled={Boolean(occupata)} onClick={() => void collega()}>Collega al fascicolo</button>
                  {lavorazione.collegaPec.scegliHref ? <a href={lavorazione.collegaPec.scegliHref}>Scegli un altro fascicolo</a> : null}
                  {collegata === 'errore' ? <span className="iu-ruolo-esito is-errore" role="alert">Collegamento non riuscito: riprova o scegli dalla PEC.</span> : null}
                </div>
              </> : lavorazione.collegaPec.alternative?.length ? <>
                <p>Più fascicoli aperti di <b>{lavorazione.collegaPec.cliente}</b>: indica quello della causa{lavorazione.collegaPec.rg ? ` RG ${lavorazione.collegaPec.rg}` : ''}.</p>
                {lavorazione.collegaPec.alternative.map((alternativa) => (
                  <div className="iu-ruolo-bozza" key={alternativa.id}>
                    <span>{alternativa.fascicolo}</span>
                    <div className="iu-ruolo-azioni"><button type="button" disabled={Boolean(occupata)} onClick={() => void collega(alternativa.id)}>Collega</button></div>
                  </div>
                ))}
                {collegata === 'errore' ? <span className="iu-ruolo-esito is-errore" role="alert">Collegamento non riuscito: riprova.</span> : null}
              </> : <>
                <p>{lavorazione.collegaPec.cliente
                  ? <>Nello studio non c’è un fascicolo aperto di <b>{lavorazione.collegaPec.cliente}</b>{lavorazione.collegaPec.rg ? <> per la causa RG {lavorazione.collegaPec.rg}</> : null}: la causa va aperta o collegata dall’avvocato.</>
                  : 'Nessun fascicolo certo per questa PEC: va scelto dall’avvocato.'}</p>
                <div className="iu-ruolo-azioni">
                  {lavorazione.collegaPec.scegliHref ? <a href={lavorazione.collegaPec.scegliHref}>Scegli il fascicolo dalla PEC</a> : null}
                  <a className="is-principale" href={lavorazione.collegaPec.nuovoFascicoloHref || "/fascicoli/nuovo"}>Apri il fascicolo della nuova causa</a>
                </div>
              </>}
          </section>
        ) : null}

        {remoto ? (
          <section className="iu-ruolo-sezione" aria-label="Collegamento all'udienza">
            <h3>Collegamento all’udienza</h3>
            <dl className="iu-ruolo-dati">
              <dt>Data e ora</dt><dd>{quando(event)}</dd>
              <dt>Link</dt><dd><a href={remoto.link} target="_blank" rel="noreferrer">{remoto.piattaforma && !/^altra$/i.test(remoto.piattaforma) ? `Entra su ${remoto.piattaforma}` : 'Entra nella riunione'}</a></dd>
              {remoto.idRiunione ? <><dt>ID riunione</dt><dd>{remoto.idRiunione}</dd></> : null}
              {remoto.codice ? <><dt>Codice</dt><dd>{remoto.codice}</dd></> : null}
            </dl>
          </section>
        ) : null}

        {proposte.length ? (
          <section className="iu-ruolo-sezione" aria-label="Termini proposti">
            <h3>{genere === 'notifica' ? 'Adempimenti proposti' : 'Termini proposti'}</h3>
            {proposte.map((proposta) => {
              const esito = esiti[proposta.id]
              return (
                <div key={proposta.id} className={`iu-ruolo-proposta ${esito === 'confermata' ? 'is-confermata' : esito === 'scartata' ? 'is-scartata' : ''}`}>
                  <div className="iu-ruolo-proposta__riga"><strong>{proposta.titolo}</strong><span className="iu-ruolo-proposta__data">{proposta.dataEtichetta}</span></div>
                  {proposta.spiegazione ? <div className="iu-ruolo-proposta__perche">{proposta.perentorio ? 'Termine perentorio. ' : ''}{proposta.spiegazione}</div> : null}
                  {esito === 'confermata' ? <div className="iu-ruolo-azioni"><span className="iu-ruolo-esito is-ok">Confermato: la scadenza è operativa in agenda</span></div>
                    : esito === 'scartata' ? <div className="iu-ruolo-azioni"><span className="iu-ruolo-esito is-no">Scartato, con il motivo registrato</span></div>
                      : <div className="iu-ruolo-azioni">
                        <button type="button" className="is-principale" disabled={Boolean(occupata)} onClick={() => void agisci(proposta, 'conferma')}>Conferma</button>
                        <a href={`/scadenziario/${encodeURIComponent(proposta.id)}/modifica`}>Modifica</a>
                        <button type="button" disabled={Boolean(occupata)} onClick={() => void agisci(proposta, 'scarta')}>Scarta</button>
                        {esito === 'errore' ? <span className="iu-ruolo-esito is-errore" role="alert">Operazione non riuscita: riprova.</span> : null}
                      </div>}
                </div>
              )
            })}
          </section>
        ) : null}

        {lavorazione?.notificaHref ? (
          <section className="iu-ruolo-sezione" aria-label="Notifica">
            <h3>Notifica</h3>
            <div className="iu-ruolo-azioni"><a href={lavorazione.notificaHref}>Apri la notifica e le ricevute</a></div>
          </section>
        ) : null}

        {lavorazione?.prossimo ? <p className="iu-ruolo-prossimo"><b>Prossimo passo:</b> {lavorazione.prossimo}</p> : null}
        {lavorazione && !lavorazione.ok && lavorazione.message ? <p className="iu-ruolo-prossimo" role="alert">{lavorazione.message}</p> : null}
        {azioni ? <section className="iu-ruolo-sezione" aria-label="Altre azioni"><h3>Altre azioni</h3>{azioni}</section> : null}
      </div>
      <div className="iu-ruolo-scheda__piede">
        {lavorazione?.fascicoloHref || event.matterId
          ? <a href={lavorazione?.fascicoloHref || `/fascicoli/${encodeURIComponent(event.matterId)}`}>Apri il fascicolo</a>
          : <button type="button" disabled>Nessun fascicolo</button>}
        <button type="button" className="is-oro" disabled={!aperte.length || Boolean(occupata)} onClick={() => void confermaTutte()}>
          {aperte.length ? (aperte.length === 1 ? 'Conferma la proposta' : `Conferma tutte (${aperte.length})`) : 'Niente da confermare'}
        </button>
      </div>
    </aside>
  )
}
