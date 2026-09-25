import { useEffect, useMemo, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { penaleApi } from './penaleApi'
import { DatiAtto } from './DatiAtto'
import { DocumentiDeposito } from './DocumentiDeposito'
import { SceltaAtto } from './SceltaAtto'
import type { AttoCatalogo, FileScelto, Quadro, SchedaAtto } from './types'

type Props = { fascicoloId: string; quadro: Quadro; onSalvato: (depositoId: string) => void; onDocumenti: () => Promise<void> | void }

const PROCURE = new Set(['PM-U', 'PM-G'])

/** Preparazione del deposito in quattro passi, con i controlli del PDP prima di aprire il portale. */
export function NuovoDeposito({ fascicoloId, quadro, onSalvato, onDocumenti }: Props) {
  const [ufficio, setUfficio] = useState(quadro.procedimento.ufficio)
  const [soggetti, setSoggetti] = useState<string[]>(quadro.soggetti.map((s) => s.id))
  const [atto, setAtto] = useState<AttoCatalogo | null>(null)
  const [scheda, setScheda] = useState<SchedaAtto | null>(null)
  const [contestuali, setContestuali] = useState<Array<{ codice: string; nome: string }>>([])
  const [file, setFile] = useState<FileScelto[]>([])
  const [dati, setDati] = useState<Record<string, string>>({})
  const [procura, setProcura] = useState(false)
  const [lavoro, setLavoro] = useState(false)
  const [errore, setErrore] = useState('')
  const ruoli = useMemo(() => quadro.soggetti.filter((s) => soggetti.includes(s.id)).map((s) => s.ruolo), [quadro.soggetti, soggetti])
  const chiaveRuoli = ruoli.join(',')

  useEffect(() => {
    if (!atto) { setScheda(null); return }
    let attivo = true
    penaleApi.scheda(atto.codice, ufficio, chiaveRuoli.split(',').filter(Boolean)).then((r) => {
      if (!attivo) return
      setScheda(r.atto); setContestuali(r.contestuali)
      if (r.atto.ruoli) setSoggetti((prima) => prima.filter((id) => r.atto.ruoli?.includes(quadro.soggetti.find((s) => s.id === id)?.ruolo || '')))
    }).catch((e: unknown) => { if (attivo) setErrore(e instanceof Error ? e.message : 'Scheda dell’atto non disponibile.') })
    return () => { attivo = false }
  }, [atto, ufficio, chiaveRuoli, quadro.soggetti])

  const abilitanteRichiesto = Boolean(atto && ['P02', 'P49'].includes(atto.codice) && PROCURE.has(ufficio) && !quadro.avvisoIndagini)
  const prepara = async () => {
    if (!atto) return
    setLavoro(true); setErrore('')
    try {
      const esito = await penaleApi.prepara(fascicoloId, { atto: atto.codice, ufficio, soggetti, file, dati, procuraSpeciale: procura })
      onSalvato(esito.deposito.id)
    } catch (e) { setErrore(e instanceof Error ? e.message : 'Preparazione non riuscita.') } finally { setLavoro(false) }
  }
  const idonei = (ruolo: string) => !scheda?.ruoli || scheda.ruoli.includes(ruolo)

  return (
    <div className="iu-pdp-nuovo">
      <section className="iu-pdp-passo">
        <h4><span>1</span> Ufficio e soggetti rappresentati</h4>
        <div className="iu-pdp-riga">
          <label>Ufficio di destinazione
            <select value={ufficio} onChange={(e) => { setUfficio(e.target.value); setAtto(null) }}>
              <option value="">Scegli</option>
              {quadro.uffici.map((u) => <option key={u.codice} value={u.codice}>{u.descrizione}</option>)}
            </select>
          </label>
        </div>
        {quadro.soggetti.length ? (
          <div className="iu-pdp-soggetti">
            {quadro.soggetti.map((s) => (
              <label key={s.id} className={`iu-pdp-spunta${idonei(s.ruolo) ? '' : ' is-escluso'}`}>
                <input type="checkbox" checked={soggetti.includes(s.id)} disabled={!idonei(s.ruolo)}
                  onChange={(e) => setSoggetti((prima) => e.target.checked ? [...prima, s.id] : prima.filter((id) => id !== s.id))}/>
                {s.nome} <small>{s.ruoloEtichetta}{idonei(s.ruolo) ? '' : ' · non ammesso per questo atto'}</small>
              </label>
            ))}
          </div>
        ) : <p className="iu-pdp-avviso">Aggiungi i soggetti rappresentati nella scheda «Procedimento e soggetti».</p>}
      </section>
      <section className="iu-pdp-passo">
        <h4><span>2</span> Atto</h4>
        <SceltaAtto fascicoloId={fascicoloId} quadro={quadro} ufficio={ufficio} soggetti={soggetti} scelto={atto?.codice || ''}
          onScegli={(a) => { setAtto(a); setDati({}); setProcura(false) }}/>
      </section>
      {atto && scheda ? (
        <>
          <section className="iu-pdp-passo">
            <h4><span>3</span> Documenti · {scheda.menu || scheda.nome}</h4>
            <DocumentiDeposito fascicoloId={fascicoloId} documenti={quadro.documenti} scelti={file} contestuali={contestuali}
              ammetteContestuali={scheda.contestuali} abilitanteRichiesto={abilitanteRichiesto} onCambia={setFile} onCaricato={onDocumenti}/>
          </section>
          {scheda.campi.length || scheda.procuraSpeciale ? (
            <section className="iu-pdp-passo">
              <h4><span>4</span> Dati dell’atto</h4>
              <DatiAtto scheda={scheda} dati={dati} procura={procura} onDati={setDati} onProcura={setProcura}/>
            </section>
          ) : null}
          <div className="iu-pdp-azioni">
            <button type="button" className="iu-pdp-primario" disabled={lavoro || !file.length} onClick={() => void prepara()}>
              <ShieldCheck size={16}/> {lavoro ? 'Controllo in corso…' : 'Controlla e prepara per il PDP'}
            </button>
            <small>Firma, formato, dimensioni, soggetti e dati vengono verificati come fa il portale. Nulla viene inviato.</small>
          </div>
        </>
      ) : null}
      {errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : null}
    </div>
  )
}
