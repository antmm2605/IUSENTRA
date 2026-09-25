import { useState } from 'react'
import { AlertTriangle, CalendarPlus, CheckCircle2, CircleDashed, Copy, ExternalLink, FileArchive } from 'lucide-react'
import { pttApi } from './pttApi'
import type { CatalogoPtt, Riga, Scheda, Termine } from './types'

const ICONE = {
  ok: <CheckCircle2 size={15} aria-label="Pronto"/>,
  manca: <AlertTriangle size={15} aria-label="Da indicare"/>,
  verifica: <AlertTriangle size={15} aria-label="Da verificare"/>,
  facoltativo: <CircleDashed size={15} aria-label="Facoltativo"/>,
}

function RigaNir({ riga }: { riga: Riga }) {
  const [copiato, setCopiato] = useState(false)
  const copia = async () => {
    try {
      await navigator.clipboard.writeText(riga.valore)
      setCopiato(true)
      window.setTimeout(() => setCopiato(false), 1500)
    } catch {
      setCopiato(false)
    }
  }
  return (
    <li className={`iu-pat-riga iu-pat-riga--${riga.stato}`}>
      <span className="iu-pat-riga__stato">{ICONE[riga.stato]}</span>
      <div className="iu-pat-riga__testo">
        <strong>{riga.etichetta}</strong>
        <span>{riga.valore}</span>
        {riga.nota ? <small>{riga.nota}</small> : null}
      </div>
      <div className="iu-pat-riga__azioni">
        {riga.copia ? <button type="button" onClick={() => void copia()} aria-label={`Copia ${riga.etichetta}`}><Copy size={14}/> {copiato ? 'Copiato' : 'Copia'}</button> : null}
      </div>
    </li>
  )
}

const giorni = (n: number) => n < 0 ? `scaduto da ${-n} giorni` : n === 0 ? 'scade oggi' : n === 1 ? 'domani' : `fra ${n} giorni`
const dataIt = (iso: string) => iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('it-IT') : ''

/** I termini che decorrono dalle date del procedimento, da portare nello scadenziario con un clic. */
export function TerminiPtt({ fascicoloId, termini }: { fascicoloId: string; termini: Termine[] }) {
  const [esito, setEsito] = useState<Record<string, string>>({})
  if (!termini.length) return null
  const registra = async (t: Termine) => {
    try {
      const r = await pttApi.termine(fascicoloId, t.id)
      setEsito((v) => ({ ...v, [t.id]: r.gia ? 'Già nello scadenziario' : 'Aggiunto allo scadenziario' }))
    } catch (e) {
      setEsito((v) => ({ ...v, [t.id]: e instanceof Error ? e.message : 'Non aggiunto' }))
    }
  }
  return (
    <ul className="iu-pat-elenco iu-ptt-termini">
      {termini.map((t) => (
        <li key={t.id} className={t.giorni <= 7 ? 'iu-ptt-termine--vicino' : ''}>
          <div>
            <strong>{t.titolo}: {dataIt(t.scadenza)} ({giorni(t.giorni)})</strong>
            <span>{t.norma}{t.perentorio ? ' · termine perentorio' : ''}</span>
          </div>
          <button type="button" onClick={() => void registra(t)}><CalendarPlus size={14}/> {esito[t.id] || 'Aggiungi allo scadenziario'}</button>
        </li>
      ))}
    </ul>
  )
}

/** La nota di iscrizione a ruolo da seguire nel SIGIT: stesse schede della NIR web, dati pronti da copiare. */
export function SchedaNir({ fascicoloId, scheda, catalogo, tipo, onTipo, termini }: {
  fascicoloId: string
  scheda: Scheda
  catalogo: CatalogoPtt | null
  tipo: string
  onTipo: (tipo: string) => void
  termini: Termine[]
}) {
  const totale = scheda.sezioni.reduce((n, s) => n + s.righe.filter((r) => r.stato !== 'facoltativo').length, 0)
  const pronti = scheda.sezioni.reduce((n, s) => n + s.righe.filter((r) => r.stato === 'ok').length, 0)
  return (
    <div className="iu-pat-scheda">
      <TerminiPtt fascicoloId={fascicoloId} termini={termini}/>
      <div className="iu-pat-tipi" role="radiogroup" aria-label="Tipologia di deposito PTT">
        {(catalogo?.depositi || []).map((d) => (
          <button key={d.id} type="button" role="radio" aria-checked={tipo === d.id} className={tipo === d.id ? 'is-attiva' : ''} onClick={() => onTipo(d.id)}>
            {d.nome}
          </button>
        ))}
      </div>
      <div className="iu-pat-avanzamento">
        <div>
          <strong>{scheda.nome}</strong>
          <span>{pronti} di {totale} dati pronti{scheda.mancanti.length ? ` · ${scheda.mancanti.length} da indicare` : ''}{scheda.daVerificare.length ? ` · ${scheda.daVerificare.length} da verificare` : ''}</span>
          <meter min={0} max={Math.max(totale, 1)} value={pronti} aria-label="Dati pronti per la NIR"/>
        </div>
        <div className="iu-pat-avanzamento__azioni">
          <a className="iu-pat-primario" href={pttApi.pacchetto(fascicoloId)} download><FileArchive size={15}/> Scarica i file pronti</a>
          <a className="iu-pat-primario" href={scheda.link} target="_blank" rel="noreferrer"><ExternalLink size={15}/> Apri il PTT</a>
        </div>
      </div>
      <ol className="iu-pat-sezioni">
        {scheda.sezioni.map((sezione, indice) => (
          <li key={sezione.titolo}>
            <h5><span>{indice + 1}</span>{sezione.titolo}</h5>
            <ul className="iu-pat-righe">
              {sezione.righe.map((riga, i) => <RigaNir key={`${riga.etichetta}-${i}`} riga={riga}/>)}
            </ul>
          </li>
        ))}
      </ol>
    </div>
  )
}
