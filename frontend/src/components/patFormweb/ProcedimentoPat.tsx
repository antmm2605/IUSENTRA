import { useState, type FormEvent } from 'react'
import { Save } from 'lucide-react'
import type { CatalogoPat, Procedimento, QuadroPat } from './types'

const POSIZIONI = [['ricorrente', 'Ricorrente'], ['resistente', 'Resistente'], ['controinteressato', 'Controinteressato'], ['interveniente', 'Interveniente']]

/** I dati del procedimento che il Formweb chiede alla creazione della bozza e nelle schede del ricorso. */
export function ProcedimentoPat({ quadro, catalogo, onSalva }: {
  quadro: QuadroPat
  catalogo: CatalogoPat | null
  onSalva: (dati: Record<string, unknown>) => Promise<void>
}) {
  const p = quadro.procedimento
  const [sede, setSede] = useState(p.sede || '')
  const [cu, setCu] = useState(p.cuTipologia || '')
  const [tipo, setTipo] = useState(p.tipoRicorso || '')
  const [istanze, setIstanze] = useState<string[]>(p.istanze || [])
  const [stato, setStato] = useState('')
  const ambito = catalogo?.sedi.find((s) => s.codice === sede)?.ambito || ''
  const appello = ambito === 'CDS' || ambito === 'CGARS'
  const tipi = (appello ? catalogo?.tipiRicorsoCds : catalogo?.tipiRicorsoTar) || []
  const esenzioni = (appello ? catalogo?.esenzioniCds : catalogo?.esenzioniTar) || []
  const appalti = tipo === '95' || tipo === 'Y5'

  const salva = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    const f = new FormData(evento.currentTarget)
    const testo = (n: string) => String(f.get(n) || '').trim()
    const dati: Record<string, unknown> = {
      sede, tipoRicorso: tipo, nrg: testo('nrg'), posizione: testo('posizione'), oggetto: testo('oggetto'),
      pnrr: f.get('pnrr') === '1', anteCausam: f.get('anteCausam') === '1', cassazionista: f.get('cassazionista') === '1',
      cuTipologia: cu, esenzione: testo('esenzione'), valore: testo('valore'), istanze,
      attoImpugnato: { organo: testo('organo'), tipo: testo('tipoAtto'), numero: testo('numeroAtto'), anno: testo('annoAtto') },
    }
    setStato('Salvataggio…')
    try {
      await onSalva(dati)
      setStato('Dati del procedimento salvati.')
    } catch (e) {
      setStato(e instanceof Error ? e.message : 'Salvataggio non riuscito.')
    }
  }
  const impugnato: Procedimento['attoImpugnato'] = p.attoImpugnato || {}
  return (
    <form className="iu-pat-procedimento" onSubmit={(e) => void salva(e)}>
      <section>
        <h5>Autorità e ricorso</h5>
        <div className="iu-pat-form">
          <label>Sede (come nel portale)
            <select value={sede} onChange={(e) => { setSede(e.target.value); setTipo('') }}>
              <option value="">Scegli la sede</option>
              {(catalogo?.sedi || []).map((s) => <option key={s.codice} value={s.codice}>{s.descrizione}</option>)}
            </select></label>
          <label>Posizione dell'assistito
            <select name="posizione" defaultValue={p.posizione || 'ricorrente'}>{POSIZIONI.map(([v, e]) => <option key={v} value={v}>{e}</option>)}</select></label>
          <label>{appello ? 'Tipo di appello' : 'Tipo di ricorso'}
            <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">Scegli</option>
              {tipi.map((t) => <option key={t.codice} value={t.codice}>{t.descrizione}</option>)}
            </select></label>
          <label>NRG (se già iscritto)<input name="nrg" inputMode="numeric" defaultValue={p.nrg || ''} placeholder="es. 202600123" maxLength={9}/></label>
          {appalti ? <label>Valore della controversia (€)<input name="valore" inputMode="decimal" defaultValue={p.valore ?? ''}/></label> : null}
        </div>
        <label className="iu-pat-largo">Oggetto (come da epigrafe)<textarea name="oggetto" rows={3} maxLength={16000} defaultValue={p.oggetto || ''}/></label>
        <div className="iu-pat-spunte">
          <label className="iu-pat-spunta"><input type="checkbox" name="pnrr" value="1" defaultChecked={Boolean(p.pnrr)}/> Finanziamento PNRR (art. 12-bis d.l. 68/2022)</label>
          <label className="iu-pat-spunta"><input type="checkbox" name="anteCausam" value="1" defaultChecked={Boolean(p.anteCausam)}/> Istanze ante causam presenti</label>
          {appello ? <label className="iu-pat-spunta"><input type="checkbox" name="cassazionista" value="1" defaultChecked={Boolean(p.cassazionista)}/> Difensore cassazionista</label> : null}
        </div>
      </section>
      <section>
        <h5>Atto impugnato</h5>
        <div className="iu-pat-form">
          <label>Autorità emanante<input name="organo" defaultValue={impugnato.organo || ''} placeholder="es. Comune di Palmi"/></label>
          <label>Tipologia<input name="tipoAtto" defaultValue={impugnato.tipo || ''} placeholder="es. DELIBERA"/></label>
          <label>Numero<input name="numeroAtto" defaultValue={impugnato.numero || ''}/></label>
          <label>Anno<input name="annoAtto" inputMode="numeric" maxLength={4} defaultValue={impugnato.anno || ''}/></label>
        </div>
      </section>
      <section>
        <h5>Istanze e domande da segnalare</h5>
        <div className="iu-pat-istanze">
          {(catalogo?.istanze || []).map((voce) => (
            <label key={voce} className="iu-pat-spunta">
              <input type="checkbox" checked={istanze.includes(voce)} onChange={(e) => setIstanze((v) => e.target.checked ? [...v, voce] : v.filter((x) => x !== voce))}/> {voce}
            </label>
          ))}
        </div>
      </section>
      <section>
        <h5>Contributo unificato</h5>
        <div className="iu-pat-form">
          <label>Tipologia
            <select value={cu} onChange={(e) => setCu(e.target.value)}>
              <option value="">Scegli</option>
              {(catalogo?.contributo || []).map((c) => <option key={c} value={c}>{c}</option>)}
            </select></label>
          {cu === 'Esente' ? (
            <label>Tipo di esenzione
              <select name="esenzione" defaultValue={p.esenzione || ''}>
                <option value="">Scegli</option>
                {esenzioni.map((e) => <option key={e.codice} value={e.descrizione}>{e.descrizione}</option>)}
              </select></label>
          ) : null}
        </div>
        {quadro.contributo.nota ? <p className="iu-pat-nota">{quadro.contributo.importo ? `Importo proposto € ${quadro.contributo.importo.toFixed(2).replace('.', ',')}. ` : ''}{quadro.contributo.nota}</p> : null}
      </section>
      <div className="iu-pat-barra">
        <button type="submit" className="iu-pat-primario"><Save size={15}/> Salva il procedimento</button>
        {stato ? <span role="status">{stato}</span> : null}
      </div>
    </form>
  )
}
