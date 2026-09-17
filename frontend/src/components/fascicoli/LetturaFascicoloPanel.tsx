import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BookOpen, Calculator, ChevronDown, ChevronUp, ExternalLink, Landmark, RefreshCw, Scale, ShieldCheck } from 'lucide-react'
import { Badge } from '../dashboard'
import { formatDateIt } from '../../formatting'
import { SourceDocumentModal, type SourceDocument } from '../SourceDocumentModal'
import { LettureFascicoloSection } from './LettureFascicoloSection'
import {
  etichettaFase,
  etichettaUrgenza,
  hrefCalcoloTermine,
  normeDelPasso,
  passiOrdinati,
  presidiCards,
  riassuntoStatoPassi,
  righeEconomico,
  righeVerifiche,
  tonoFase,
  type FonteLettura,
  type LetturaFascicolo,
  type PassoLettura,
  type SchedaProcedurale,
} from './letturaFascicolo'
import './letturaFascicolo.css'

const EVENTI_VISIBILI = 6

function isScheda(valore: SchedaProcedurale | Record<string, never> | undefined): valore is SchedaProcedurale {
  return Boolean(valore && Array.isArray((valore as SchedaProcedurale).fasi))
}

// La lettura del fascicolo: che cosa tratta, che cosa è stato fatto, a che
// punto siamo e che cosa fare adesso, con la norma di ogni passo. I dati
// arrivano da /api/v1/ui/fascicoli/<id>/lettura (cache breve lato server):
// il pannello li mostra, non li calcola.
export function LetturaFascicoloPanel({
  fascicoloId,
  onError,
  onReady,
}: {
  fascicoloId: string
  onError?: (message: string) => void
  onReady?: () => void
}) {
  const [lettura, setLettura] = useState<LetturaFascicolo | null>(null)
  const [loading, setLoading] = useState(false)
  const [registroRevision, setRegistroRevision] = useState(0)
  const [error, setError] = useState('')
  const [fontiAperte, setFontiAperte] = useState<Set<number>>(() => new Set())
  const [tuttiGliEventi, setTuttiGliEventi] = useState(false)
  const [schedeAperte, setSchedeAperte] = useState(false)

  const load = useCallback(async (aggiorna = false) => {
    if (!fascicoloId) return
    setLoading(true)
    setError('')
    try {
      const url = `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/lettura${aggiorna ? '?aggiorna=1' : ''}`
      const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      const payload = await response.json().catch(() => ({})) as { ok?: boolean; lettura?: LetturaFascicolo; errore?: string }
      if (!response.ok || !payload.ok || !payload.lettura) throw new Error(payload.errore || 'Lettura del fascicolo non disponibile.')
      setLettura(payload.lettura)
      if (aggiorna) setRegistroRevision((value) => value + 1)
      setFontiAperte(new Set())
      onReady?.()
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Lettura del fascicolo non disponibile.'
      setError(message)
      onError?.(message)
    } finally {
      setLoading(false)
    }
  }, [fascicoloId, onError, onReady])

  useEffect(() => { void load() }, [load])

  // I presìdi stanno verificando in sfondo: si rilegge una volta, dopo qualche secondo.
  const inCorso = Boolean(lettura?.verifiche?.in_corso)
  useEffect(() => {
    if (!inCorso) return undefined
    const timer = globalThis.setTimeout(() => { void load() }, 9000)
    return () => globalThis.clearTimeout(timer)
  }, [inCorso, load])

  const passi = useMemo(() => (lettura ? passiOrdinati(lettura) : []), [lettura])
  const cards = useMemo(() => (lettura ? presidiCards(lettura) : []), [lettura])
  const verifiche = useMemo(() => righeVerifiche(lettura?.verifiche), [lettura])
  const economico = useMemo(() => (lettura ? righeEconomico(lettura.economico) : []), [lettura])
  const eventi = useMemo(() => {
    if (!lettura) return []
    const tutti = [...lettura.cronologia].reverse()
    return tuttiGliEventi ? tutti : tutti.slice(0, EVENTI_VISIBILI)
  }, [lettura, tuttiGliEventi])

  if (!lettura && loading) return <p className="iu-fas-lettura__state"><RefreshCw className="iu-spin" size={15}/> Lettura del fascicolo in corso…</p>
  if (!lettura) {
    return (
      <p className="iu-fas-lettura__state iu-fas-lettura__state--error" role="alert">
        <AlertTriangle size={15}/> {error || 'Lettura del fascicolo non disponibile.'}
        <button type="button" className="iu-fas-lettura__retry" disabled={loading} onClick={() => void load(true)}><RefreshCw size={14}/> Riprova</button>
      </p>
    )
  }

  const fase = lettura.fase
  const testata = lettura.intestazione

  return (
    <div className="iu-fas-lettura" aria-busy={loading}>
      <header className="iu-fas-lettura__header">
        <div className="iu-fas-lettura__fase">
          <Badge tone={tonoFase(fase.codice)}>{etichettaFase(fase.codice)}</Badge>
          <h3>{fase.descrizione.charAt(0).toUpperCase() + fase.descrizione.slice(1)}</h3>
          {fase.prove.length ? <p>Lo dicono: {fase.prove.join('; ')}.</p> : null}
          {fase.prossima_udienza ? <p><strong>Prossimo appuntamento o termine:</strong> {fase.prossima_udienza}</p> : null}
          {fase.incoerenze.map((voce) => <p className="iu-fas-lettura__attenzione" key={voce}><AlertTriangle size={14}/> {voce}.</p>)}
        </div>
        <div className="iu-fas-lettura__header-actions">
          <span>Letta il {lettura.generata_il}{testata.rg ? ` · RG ${testata.rg}` : ''}</span>
          <button type="button" disabled={loading} onClick={() => void load(true)} title="Ricostruisce la lettura dai dati correnti del fascicolo"><RefreshCw className={loading ? 'iu-spin' : ''} size={15}/> Aggiorna</button>
        </div>
      </header>
      {error ? <p className="iu-fas-lettura__state iu-fas-lettura__state--error" role="alert"><AlertTriangle size={15}/> {error}</p> : null}

      <section className="iu-fas-lettura__passi" aria-label="Prossimi passaggi del fascicolo">
        <div className="iu-fas-lettura__section-head">
          <h4><Scale size={16}/> Prossimi passaggi</h4>
          {lettura.stato_passi.attivi ? <span>{riassuntoStatoPassi(lettura)}</span> : null}
        </div>
        {!lettura.stato_passi.attivi ? (
          <p className="iu-fas-lettura__nessun-passo">{lettura.stato_passi.motivo}</p>
        ) : passi.length ? (
          <ol className="iu-fas-lettura__lista">
            {passi.filter((passo) => !passo.scaduto).map((passo, indice) => (
              <PassoRow key={`${passo.azione}-${indice}`} passo={passo} indice={indice} fontiAperte={fontiAperte.has(indice)} onToggleFonti={() => setFontiAperte((current) => { const next = new Set(current); if (next.has(indice)) next.delete(indice); else next.add(indice); return next })}/>
            ))}
          </ol>
        ) : (
          <p className="iu-fas-lettura__nessun-passo">Nessun adempimento risulta aperto: il fascicolo è allineato.</p>
        )}
        {passi.some((passo) => passo.scaduto) ? (
          <details className="iu-fas-lettura__scaduti">
            <summary>Scadenze passate da verificare ({passi.filter((passo) => passo.scaduto).length})</summary>
            <p>Controlla il documento e l’eventuale adempimento già eseguito prima di aggiornare lo stato.</p>
            <ol className="iu-fas-lettura__lista">
              {passi.filter((passo) => passo.scaduto).map((passo, indice) => (
                <PassoRow key={`${passo.azione}-${indice}`} passo={passo} indice={indice} fontiAperte={fontiAperte.has(indice + 100)} onToggleFonti={() => setFontiAperte((current) => { const next = new Set(current); if (next.has(indice + 100)) next.delete(indice + 100); else next.add(indice + 100); return next })}/>
              ))}
            </ol>
          </details>
        ) : null}
        {lettura.stato_passi.attivi && lettura.stato_passi.motivo ? <p className="iu-fas-lettura__nota">{lettura.stato_passi.motivo}</p> : null}
      </section>

      <section className="iu-fas-lettura__presidi" aria-label="Presìdi del fascicolo">
        {cards.map((card) => (
          <a className={`iu-fas-lettura__card is-${card.tono}`} href={card.href} key={card.id}>
            <span>{card.titolo}</span>
            <strong>{card.valore}</strong>
            <small>{card.nota}</small>
          </a>
        ))}
      </section>

      <div className="iu-fas-lettura__colonne">
        <section className="iu-fas-lettura__blocco" aria-label="Di che cosa tratta il fascicolo">
          <h4>Di che cosa tratta</h4>
          {lettura.oggetto.oggetto_dichiarato ? <p><strong>Oggetto:</strong> {lettura.oggetto.oggetto_dichiarato}</p> : null}
          {lettura.oggetto.domanda ? (
            <blockquote>
              <span>Domanda, dal testo di «{lettura.oggetto.domanda.etichetta}»{lettura.oggetto.domanda.data ? ` (${formatDateIt(lettura.oggetto.domanda.data)})` : ''}:</span>
              «{lettura.oggetto.domanda.petitum}»
            </blockquote>
          ) : lettura.oggetto.atti_principali.length ? (
            <p>Atti principali: {lettura.oggetto.atti_principali.map((atto) => atto.etichetta).join(', ')}. La domanda non è ancora stata isolata con una citazione verificata.</p>
          ) : !lettura.oggetto.oggetto_dichiarato ? (
            <p>L'oggetto non è indicato e nessun atto principale è catalogato: la materia va dichiarata.</p>
          ) : null}
          {testata.cliente || testata.controparte ? <p><strong>Parti:</strong> {[testata.cliente, testata.controparte].filter(Boolean).join(' contro ')}{testata.ufficio ? ` · ${testata.ufficio}` : ''}{testata.valore_causa ? ` · valore ${testata.valore_causa}` : ''}</p> : null}
        </section>

        <section className="iu-fas-lettura__blocco" aria-label="Eventi e attività">
          <h4>Eventi e attività</h4>
          {eventi.length ? (
            <ul className="iu-fas-lettura__eventi">
              {eventi.map((evento, indice) => (
                <li key={`${evento.data}-${evento.titolo}-${indice}`}>
                  <time>{evento.data_it || 'senza data'}</time>
                  <span><b>{evento.categoria}</b> {evento.titolo}{evento.esito ? ` — ${evento.esito}` : ''}</span>
                </li>
              ))}
            </ul>
          ) : <p>Nessuna attività, deposito o notifica risulta registrata.</p>}
          {lettura.cronologia.length > EVENTI_VISIBILI ? (
            <button type="button" className="iu-fas-lettura__link" onClick={() => setTuttiGliEventi((current) => !current)}>
              {tuttiGliEventi ? <><ChevronUp size={14}/> Mostra gli ultimi {EVENTI_VISIBILI}</> : <><ChevronDown size={14}/> Mostra tutti ({lettura.cronologia.length})</>}
            </button>
          ) : null}
        </section>
      </div>

      <section className="iu-fas-lettura__verifiche" aria-label="Verifiche automatiche dei presìdi">
        <div className="iu-fas-lettura__section-head">
          <h4><ShieldCheck size={16}/> Verifiche automatiche dei presìdi</h4>
          <span>{lettura.verifiche?.in_corso ? 'in corso…' : lettura.verifiche?.eseguita_il_it ? `eseguite il ${lettura.verifiche.eseguita_il_it}` : 'partono all\'apertura del fascicolo e si ripetono ogni 15 minuti'}</span>
        </div>
        {verifiche.length ? (
          <ul className="iu-fas-lettura__verifiche-lista">
            {verifiche.map((riga) => <li className={`is-${riga.tono}`} key={riga.presidio}><strong>{riga.presidio}</strong><span>{riga.esito}</span></li>)}
          </ul>
        ) : <p className="iu-fas-lettura__nota">{lettura.verifiche?.in_corso ? 'Ricevute dei depositi, PEC per ruolo e assistito, presidi notifica e documenti da leggere: i presìdi controllano ora, senza compiti per te.' : 'I presìdi controllano ricevute, PEC, notifiche e documenti da soli: qui compare che cosa hanno fatto.'}</p>}
        {lettura.conoscenza.lacune?.length ? (
          <ul className="iu-fas-lettura__conoscenza">
            {lettura.conoscenza.lacune.map((voce) => <li key={`${voce.tipo}-${voce.chiave}`}><b>Conoscenza da completare · {voce.tipo}</b> {voce.descrizione}</li>)}
          </ul>
        ) : null}
      </section>

      <LettureFascicoloSection key={fascicoloId} fascicoloId={fascicoloId} refreshKey={registroRevision} onAggiornato={() => void load()}/>

      <section className="iu-fas-lettura__blocco iu-fas-lettura__economico" aria-label="Presidio economico del fascicolo">
        <div className="iu-fas-lettura__section-head">
          <h4><Landmark size={16}/> Presidio economico</h4>
          <a className="iu-fas-lettura__link" href="/fatturazione">Apri Fatturazione</a>
        </div>
        {economico.length ? (
          <dl className="iu-fas-lettura__economico-righe">
            {economico.map((riga) => <div className={riga.tono ? `is-${riga.tono}` : ''} key={riga.etichetta}><dt>{riga.etichetta}</dt><dd>{riga.valore}{riga.nota ? <small>{riga.nota}</small> : null}</dd></div>)}
          </dl>
        ) : <p>Nessun dato economico collegato al fascicolo.</p>}
      </section>

      {lettura.lacune.length ? (
        <section className="iu-fas-lettura__lacune" aria-label="Lacune da colmare">
          <h4><AlertTriangle size={15}/> Lacune da colmare</h4>
          <ul>{lettura.lacune.map((voce) => <li key={voce}>{voce}.</li>)}</ul>
        </section>
      ) : null}

      <section className="iu-fas-lettura__schede" aria-label="Fasi e termini del procedimento">
        <button type="button" className="iu-fas-lettura__schede-toggle" aria-expanded={schedeAperte} onClick={() => setSchedeAperte((current) => !current)}>
          <BookOpen size={16}/> Fasi, termini e norme del procedimento
          <small>rito, deposito e notifiche di questa pratica, con le fonti ufficiali verificate</small>
          {schedeAperte ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
        </button>
        {schedeAperte ? (
          <div className="iu-fas-lettura__schede-body">
            {isScheda(lettura.conoscenza.rito) ? <Scheda scheda={lettura.conoscenza.rito} tipo="rito"/> : null}
            {isScheda(lettura.conoscenza.deposito) ? <Scheda scheda={lettura.conoscenza.deposito} tipo="deposito"/> : null}
            {lettura.conoscenza.notifiche.map((scheda) => <Scheda scheda={scheda} tipo="notifica" key={scheda.canale || scheda.nome}/>)}
          </div>
        ) : null}
      </section>
    </div>
  )
}

function PassoRow({ passo, indice, fontiAperte, onToggleFonti }: { passo: PassoLettura; indice: number; fontiAperte: boolean; onToggleFonti: () => void }) {
  const urgenza = passo.scaduto ? { etichetta: 'Scaduta da verificare', tono: 'warning' as const } : etichettaUrgenza(passo.urgenza)
  const norma = normeDelPasso(passo)
  const calcolo = hrefCalcoloTermine(passo)
  return (
    <li className={`iu-fas-lettura__passo is-${urgenza.tono}`}>
      <span className="iu-fas-lettura__numero">{indice + 1}</span>
      <div className="iu-fas-lettura__passo-copy">
        <div className="iu-fas-lettura__passo-titolo">
          <Badge tone={urgenza.tono}>{urgenza.etichetta}{passo.entro ? ` · ${passo.scaduto ? 'il' : 'entro'} ${passo.entro}` : ''}</Badge>
          {passo.href ? <a href={passo.href}>{passo.azione}</a> : <strong>{passo.azione}</strong>}
        </div>
        {passo.motivo ? <p>{passo.motivo}.</p> : null}
        <div className="iu-fas-lettura__chips">
          {passo.fonte ? <em>{passo.fonte}</em> : null}
          {norma ? <button type="button" className="iu-fas-lettura__norma" aria-expanded={fontiAperte} onClick={onToggleFonti} title="Mostra le fonti ufficiali"><Scale size={12}/> {norma}</button> : null}
          {calcolo ? <a className="iu-fas-lettura__calcolo" href={calcolo}><Calculator size={12}/> Calcola il termine</a> : null}
        </div>
        {fontiAperte && passo.fonti.length ? <FontiList fonti={passo.fonti}/> : null}
      </div>
    </li>
  )
}

function FontiList({ fonti }: { fonti: FonteLettura[] }) {
  const [source, setSource] = useState<SourceDocument | null>(null)
  return (
    <>
      <SourceDocumentModal source={source} onClose={() => setSource(null)} />
      <ul className="iu-fas-lettura__fonti">
        {fonti.map((fonte) => (
          <li key={fonte.id}>
            <b>{fonte.norma}</b> — {fonte.titolo}
            {fonte.estratto ? <span>{fonte.estratto}</span> : null}
            <small>{fonte.verifica} · {fonte.reader_url ? <button type="button" onClick={() => setSource({href: fonte.reader_url!, label: fonte.norma, context: fonte.titolo})}>Leggi il testo ufficiale</button> : fonte.url.startsWith('https://') ? <a href={fonte.url} target="_blank" rel="noopener noreferrer">Fonte ufficiale <ExternalLink size={11}/></a> : null}</small>
          </li>
        ))}
      </ul>
    </>
  )
}

function Scheda({ scheda, tipo }: { scheda: SchedaProcedurale; tipo: 'rito' | 'deposito' | 'notifica' }) {
  const normaDi = useMemo(() => new Map(scheda.fonti.map((fonte) => [fonte.id, fonte])), [scheda.fonti])
  const norme = (ids: string[]) => ids.map((id) => normaDi.get(id)?.norma).filter(Boolean).join('; ')
  return (
    <article className="iu-fas-lettura__scheda">
      <h5><span>{tipo === 'rito' ? 'Rito' : tipo === 'deposito' ? 'Deposito' : 'Notifica'}</span> {scheda.nome}</h5>
      <p>{scheda.base}</p>
      <ol>
        {scheda.fasi.map((fase) => (
          <li key={fase.codice}>
            <strong>{fase.nome}</strong>
            {fase.descrizione ? <span>{fase.descrizione}</span> : null}
            {fase.prova ? <small>Prova: {fase.prova}</small> : null}
            {fase.fonti?.length ? <small>{norme(fase.fonti)}</small> : null}
            {fase.adempimenti?.length ? (
              <ul>
                {fase.adempimenti.map((adempimento) => (
                  <li key={adempimento.azione}>
                    <b>{adempimento.azione}</b>{adempimento.parte ? ` (${adempimento.parte})` : ''}: {adempimento.termine}
                    <small>{norme(adempimento.fonti)}{adempimento.template ? <> · <a href={`/strumenti-legali?strumento=termini-processuali&template=${encodeURIComponent(adempimento.template)}`}><Calculator size={11}/> calcola</a></> : null}</small>
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ol>
      {scheda.tempistiche?.length ? (
        <dl>
          {scheda.tempistiche.map((voce) => <div key={voce.evento}><dt>{voce.evento}</dt><dd>{voce.termine}<small>{norme(voce.fonti)}</small></dd></div>)}
        </dl>
      ) : null}
      <FontiList fonti={scheda.fonti}/>
    </article>
  )
}

export default LetturaFascicoloPanel
