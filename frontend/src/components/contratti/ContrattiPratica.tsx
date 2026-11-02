import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, Download, FileText, FolderInput, Save, Trash2 } from 'lucide-react'
import {
  ETICHETTE_STATO,
  anteprimaBozza,
  dataOraItaliana,
  eliminaPratica,
  getFamiglia,
  getPratica,
  salvaNelFascicolo,
  salvaPratica,
  urlBozzaDocx,
  urlNotaDocx,
  valutaFatti,
  type Bozza,
  type DatiPratica,
  type Decisione,
  type Famiglia,
  type Fatti,
  type Pratica,
  type Valutazione,
} from '../../contrattiData'
import { Badge } from '../../ui/Badge'
import { Button, ButtonLink } from '../../ui/Button'
import { EmptyState } from '../../ui/EmptyState'
import { LoadingState } from '../../ui/LoadingState'
import { Page } from '../../ui/Page'
import { Panel } from '../../ui/Panel'
import { TONO_STATO } from './ContrattiCatalogo'
import { BozzaAnteprima } from './BozzaAnteprima'
import { Controlli } from './Controlli'
import { PartiDati } from './PartiDati'
import { Questionario } from './Questionario'
import { SceltaFascicolo } from './SceltaFascicolo'
import { SchedaStato } from './SchedaStato'

const PASSI = [
  ['fatti', '1. Fatti'],
  ['parti', '2. Parti e dati'],
  ['controlli', '3. Controlli'],
  ['bozza', '4. Bozza'],
  ['scheda', '5. Scheda e stato'],
] as const

type Passo = (typeof PASSI)[number][0]
const TESTI_SCHEDA = ['funzione', 'parti', 'documentazione', 'esecuzione']

export function ContrattiPratica({ praticaId }: { praticaId: string }) {
  const [pratica, setPratica] = useState<Pratica | null>(null)
  const [famiglia, setFamiglia] = useState<Famiglia | null>(null)
  const [errore, setErrore] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [fatti, setFatti] = useState<Fatti>({})
  const [dati, setDati] = useState<DatiPratica>({})
  const [decisioni, setDecisioni] = useState<Record<string, Decisione>>({})
  const [meta, setMeta] = useState({ titolo: '', cliente: '', fascicolo_id: '', note: '', stato: 'bozza' })
  const [valutazione, setValutazione] = useState<Valutazione | null>(null)
  const [bozza, setBozza] = useState<Bozza | null>(null)
  const [passo, setPasso] = useState<Passo>('fatti')
  const [modificata, setModificata] = useState(false)
  const [occupato, setOccupato] = useState(false)
  const caricata = useRef(false)

  const applica = useCallback((p: Pratica) => {
    setPratica(p)
    setFatti(p.fatti || {})
    setDati(p.dati || {})
    setDecisioni(p.decisioni || {})
    setMeta({ titolo: p.titolo, cliente: p.cliente || '', fascicolo_id: p.fascicolo_id || '', note: p.note || '', stato: p.stato })
    setModificata(false)
  }, [])

  useEffect(() => {
    let attivo = true
    getPratica(praticaId).then(async (risposta) => {
      if (!attivo) return
      if (!risposta.ok || !risposta.pratica) { setErrore(risposta.message || 'Pratica non trovata.'); return }
      applica(risposta.pratica)
      setValutazione(risposta.valutazione || null)
      setBozza(risposta.bozza || null)
      const f = await getFamiglia(risposta.pratica.contratto_id)
      if (attivo) setFamiglia(f)
      caricata.current = true
    })
    return () => { attivo = false }
  }, [praticaId, applica])

  useEffect(() => {
    if (!caricata.current || !pratica) return
    const timer = window.setTimeout(() => {
      valutaFatti(pratica.contratto_id, fatti).then((esito) => { if (esito.ok) setValutazione(esito) })
      anteprimaBozza(pratica.contratto_id, dati, fatti).then((esito) => { if (esito.ok && esito.bozza) setBozza(esito.bozza) })
    }, 350)
    return () => window.clearTimeout(timer)
  }, [fatti, dati, pratica])

  useEffect(() => {
    const avviso = (evento: BeforeUnloadEvent) => { if (modificata) { evento.preventDefault(); evento.returnValue = '' } }
    window.addEventListener('beforeunload', avviso)
    return () => window.removeEventListener('beforeunload', avviso)
  }, [modificata])

  const modifica = <T,>(setter: (valore: T) => void) => (valore: T) => { setter(valore); setModificata(true); setMessaggio('') }

  async function salva(stato?: string): Promise<boolean> {
    if (!pratica) return false
    setOccupato(true)
    setErrore('')
    const pulisci = (righe?: string[]) => (righe || []).map((r) => r.trim()).filter(Boolean)
    const corpo = { ...meta, stato: stato || meta.stato, fatti, decisioni, dati: { ...dati, premesse: pulisci(dati.premesse), allegati: pulisci(dati.allegati) } }
    const esito = await salvaPratica(pratica.id, corpo)
    setOccupato(false)
    if (!esito.ok || !esito.pratica) { setErrore(esito.message || 'Salvataggio non riuscito.'); return false }
    applica(esito.pratica)
    setValutazione(esito.valutazione || null)
    setBozza(esito.bozza || null)
    setMessaggio(stato ? `Stato aggiornato: ${ETICHETTE_STATO[stato] || stato}.` : 'Pratica salvata.')
    return true
  }

  async function nelFascicolo() {
    if (!pratica) return
    if (modificata && !(await salva())) return
    setOccupato(true)
    const esito = await salvaNelFascicolo(pratica.id)
    setOccupato(false)
    if (!esito.ok) { setErrore(esito.message || 'Salvataggio nel fascicolo non riuscito.'); return }
    setMessaggio(`Bozza salvata nel fascicolo come «${esito.documento?.nome}».`)
    const aggiornata = await getPratica(pratica.id)
    if (aggiornata.ok && aggiornata.pratica) applica(aggiornata.pratica)
  }

  async function elimina() {
    if (!pratica || !window.confirm('Eliminare definitivamente questa pratica contrattuale? I documenti già salvati nel fascicolo restano.')) return
    const esito = await eliminaPratica(pratica.id)
    if (esito.ok) window.location.assign('/contratti')
    else setErrore(esito.message || 'Eliminazione non riuscita.')
  }

  const indietro = <ButtonLink tone="neutral" href="/contratti"><ArrowLeft size={16} aria-hidden="true" /> Contratti</ButtonLink>
  if (errore && !pratica) return <Page title="Pratica contrattuale" actions={indietro}><EmptyState title="Pratica non disponibile" message={errore} /></Page>
  if (!pratica || !famiglia) return <Page title="Pratica contrattuale" actions={indietro}><LoadingState title="Caricamento della pratica" /></Page>
  if (!famiglia.ok) return <Page title="Pratica contrattuale" actions={indietro}><EmptyState title="Contratto non più in catalogo" message={famiglia.message} /></Page>

  const v = valutazione
  const valutatiTutti = !!v && v.punti_avvocato.every((p) => decisioni[p.id]?.valutato)
  const approvabile = !!v && !v.bloccanti.length && valutatiTutti && !v.domande_aperte.length && !v.controlli_sospesi.length && !bozza?.da_completare.length
  const testiScheda = Object.fromEntries(TESTI_SCHEDA.map((k) => [k, String(fatti[k] ?? '')]))
  const domandeSpecifiche = famiglia.contratto.domande
  const totaleDomande = domandeSpecifiche.length + famiglia.domande_comuni.length
  const aperte = v?.domande_aperte.length ?? totaleDomande

  return (
    <Page
      title={meta.titolo || pratica.contratto_nome}
      subtitle={`${pratica.contratto_nome} · creata il ${dataOraItaliana(pratica.creata_il)}`}
      actions={<>{indietro}<Badge tone={TONO_STATO[meta.stato] || 'neutral'}>{ETICHETTE_STATO[meta.stato]}</Badge></>}
      className="iu-ctr"
    >
      <div className="iu-ctr-layout">
        <div className="iu-ctr-principale">
          <nav className="iu-ctr-passi" aria-label="Passaggi della pratica">
            {PASSI.map(([id, etichetta]) => (
              <button key={id} type="button" className={passo === id ? 'is-attivo' : ''} aria-current={passo === id ? 'step' : undefined} onClick={() => setPasso(id)}>{etichetta}</button>
            ))}
          </nav>
          {passo === 'fatti' ? (
            <Panel title="Fatti dell'operazione" subtitle="Le risposte determinano la variante, i controlli e le clausole. Le domande senza risposta restano evidenziate.">
              <Questionario titolo={`Domande specifiche: ${pratica.contratto_nome}`} domande={domandeSpecifiche} fatti={fatti} onChange={modifica(setFatti)} />
              <Questionario titolo="Domande comuni a tutti i contratti" domande={famiglia.domande_comuni} fatti={fatti} onChange={modifica(setFatti)} />
            </Panel>
          ) : null}
          {passo === 'parti' ? (
            <Panel title="Parti ed elementi del contratto" subtitle="I dati mancanti restano segnaposti visibili nella bozza: nessun valore viene inventato.">
              <PartiDati ruoli={famiglia.ruoli} campi={famiglia.campi} dati={dati} onChange={modifica(setDati)} />
            </Panel>
          ) : null}
          {passo === 'controlli' ? (
            <Panel title="Controlli giuridici" subtitle="Bloccanti, valutazioni riservate all'avvocato, adempimenti e forma richiesta.">
              <Controlli valutazione={v} decisioni={decisioni} onDecisione={(id, d) => modifica(setDecisioni)({ ...decisioni, [id]: d })} />
            </Panel>
          ) : null}
          {passo === 'bozza' ? (
            <Panel
              title="Bozza del contratto"
              subtitle={bozza?.da_completare.length ? `${bozza.da_completare.length} elementi da completare, evidenziati nel testo.` : 'Nessun segnaposto aperto.'}
              actions={<>
                <ButtonLink tone="neutral" href={urlBozzaDocx(pratica.id)} aria-disabled={modificata}><Download size={16} aria-hidden="true" /> Word</ButtonLink>
                <ButtonLink tone="neutral" href={urlNotaDocx(pratica.id)}><FileText size={16} aria-hidden="true" /> Nota avvocato</ButtonLink>
              </>}
            >
              {modificata ? <p className="iu-ctr-avviso">Modifiche non salvate: l'anteprima è aggiornata, il file Word riflette l'ultima versione salvata.</p> : null}
              <BozzaAnteprima bozza={bozza} />
            </Panel>
          ) : null}
          {passo === 'scheda' ? (
            <Panel title="Scheda di controllo e stato">
              <SchedaStato pratica={pratica} valutazione={v} testi={testiScheda} onTesto={(chiave, valore) => modifica(setFatti)({ ...fatti, [chiave]: valore })} />
            </Panel>
          ) : null}
        </div>

        <aside className="iu-ctr-riepilogo" aria-label="Riepilogo della pratica">
          <Panel title="Riepilogo">
            <dl className="iu-ctr-contatori">
              <div className={aperte ? 'is-attenzione' : 'is-ok'}><dt>Domande aperte</dt><dd>{aperte}/{totaleDomande}</dd></div>
              <div className={v?.bloccanti.length ? 'is-errore' : 'is-ok'}><dt>Bloccanti</dt><dd>{v?.bloccanti.length ?? '—'}</dd></div>
              <div className={valutatiTutti ? 'is-ok' : 'is-attenzione'}><dt>Valutazioni avvocato</dt><dd>{v ? `${v.punti_avvocato.filter((p) => decisioni[p.id]?.valutato).length}/${v.punti_avvocato.length}` : '—'}</dd></div>
              <div className={bozza?.da_completare.length ? 'is-attenzione' : 'is-ok'}><dt>Da completare</dt><dd>{bozza?.da_completare.length ?? '—'}</dd></div>
            </dl>
            {v?.forma.richiede_pubblico_ufficiale ? <p className="iu-ctr-avviso">Stipula davanti a notaio o pubblico ufficiale.</p> : null}
            <div className="iu-ctr-form">
              <label><span>Titolo</span><input type="text" value={meta.titolo} maxLength={200} onChange={(e) => { const t = e.currentTarget.value; modifica(setMeta)({ ...meta, titolo: t }) }} /></label>
              <label><span>Cliente</span><input type="text" value={meta.cliente} maxLength={200} onChange={(e) => { const t = e.currentTarget.value; modifica(setMeta)({ ...meta, cliente: t }) }} /></label>
              <SceltaFascicolo valore={meta.fascicolo_id} onChange={(id) => modifica(setMeta)({ ...meta, fascicolo_id: id })} />
              <label><span>Note interne</span><textarea rows={3} value={meta.note} onChange={(e) => { const t = e.currentTarget.value; modifica(setMeta)({ ...meta, note: t }) }} /></label>
            </div>
            {errore ? <p className="iu-ctr-errore" role="alert">{errore}</p> : null}
            {messaggio ? <p className="iu-ctr-successo" role="status">{messaggio}</p> : null}
            <div className="iu-ctr-azioni">
              <Button type="button" onClick={() => { void salva() }} disabled={occupato || !modificata} aria-busy={occupato}><Save size={16} aria-hidden="true" /> {modificata ? 'Salva modifiche' : 'Salvata'}</Button>
              {meta.stato === 'bozza' ? <Button type="button" tone="warning" disabled={occupato} onClick={() => { void salva('in_revisione') }}>Invia in revisione</Button> : null}
              {meta.stato === 'in_revisione' || meta.stato === 'bozza' ? (
                <Button type="button" tone="success" disabled={occupato || !approvabile} title={approvabile ? '' : 'Per approvare: questionario completo, nessun bloccante, valutazioni registrate e bozza senza elementi da completare'} onClick={() => { void salva('approvato') }}>Approva il testo</Button>
              ) : null}
              {meta.stato === 'approvato' ? <Button type="button" tone="primary" disabled={occupato} onClick={() => { void salva('firmato') }}>Segna come firmato</Button> : null}
              {meta.stato === 'firmato' ? <Button type="button" tone="neutral" disabled={occupato} onClick={() => { void salva('archiviato') }}>Archivia</Button> : null}
              {meta.stato !== 'bozza' ? <Button type="button" tone="neutral" disabled={occupato} onClick={() => { void salva('bozza') }}>Riporta in bozza</Button> : null}
              <Button type="button" tone="neutral" disabled={occupato || !meta.fascicolo_id} title={meta.fascicolo_id ? '' : 'Collega prima un fascicolo'} onClick={() => { void nelFascicolo() }}><FolderInput size={16} aria-hidden="true" /> Salva nel fascicolo</Button>
              <Button type="button" tone="danger" disabled={occupato} onClick={() => { void elimina() }}><Trash2 size={16} aria-hidden="true" /> Elimina</Button>
            </div>
            <p className="iu-ctr-nota">Ultimo salvataggio: {dataOraItaliana(pratica.aggiornata_il)}</p>
          </Panel>
        </aside>
      </div>
    </Page>
  )
}
