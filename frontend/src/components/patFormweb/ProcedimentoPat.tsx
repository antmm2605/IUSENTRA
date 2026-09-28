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
  const [nonIndicato, setNonIndicato] = useState(Boolean(p.attoImpugnato?.nonIndicato))
  const [tipoAtto, setTipoAtto] = useState((p.attoImpugnato?.tipo || '').toUpperCase())
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
      versamento: { data: testo('versamentoData'), codiceTributo: testo('versamentoCodice'), numeroRiga: testo('versamentoRiga'), estremi: testo('versamentoEstremi'), importo: testo('versamentoImporto'), elementi: testo('versamentoElementi'), altroUfficio: f.get('versamentoAltroUfficio') === '1' },
      attoImpugnato: nonIndicato
        ? { nonIndicato: true }
        : { organo: testo('organo'), tipo: tipoAtto, altroTipo: testo('altroTipo'), numero: testo('numeroAtto'), anno: testo('annoAtto') },
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
  const versamento: NonNullable<Procedimento['versamento']> = p.versamento || {}
  return (
    <form className="iu-pat-procedimento" onSubmit={(e) => void salva(e)}>
      <section id="pat-ricorso">
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
      <section id="pat-atto-impugnato">
        <h5>Atto impugnato</h5>
        <label className="iu-pat-spunta"><input type="checkbox" checked={nonIndicato} onChange={(e) => setNonIndicato(e.target.checked)}/> Atto impugnato: non indicato/non conosciuto</label>
        {nonIndicato ? null : <div className="iu-pat-form">
          <label>Autorità emanante<input name="organo" defaultValue={impugnato.organo || ''} maxLength={120} placeholder="es. Comune di Palmi"/></label>
          <label>Tipo provvedimento
            <select value={tipoAtto} onChange={(e) => setTipoAtto(e.target.value)}>
              <option value="">Scegli</option>
              {(catalogo?.tipiAttoImpugnato || []).map((t) => <option key={t} value={t}>{t}</option>)}
            </select></label>
          {tipoAtto === 'ALTRO' ? <label>Tipo (se «ALTRO»)<input name="altroTipo" defaultValue={impugnato.altroTipo || ''} maxLength={60}/></label> : null}
          <label>Numero<input name="numeroAtto" defaultValue={impugnato.numero || ''} maxLength={20}/></label>
          <label>Anno<input name="annoAtto" inputMode="numeric" maxLength={4} pattern="[12][0-9]{3}" title="4 cifre, la prima 1 o 2" defaultValue={impugnato.anno || ''}/></label>
        </div>}
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
      <section id="pat-contributo">
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
        {cu === '' || cu === 'Non esente' ? (
          <div id="pat-versamento" className="iu-pat-versamento">
            <p className="iu-pat-nota">Se il contributo non è ancora pagato basta «Non esente». Se è pagato indica il versamento F24 (modalità unica dal 2018) e allega la quietanza nei Documenti come «Ricevuta contributo».</p>
            <div className="iu-pat-form">
              <label>Data del versamento<input type="date" name="versamentoData" defaultValue={versamento.data || ''}/></label>
              <label>Importo versato (€)<input name="versamentoImporto" inputMode="decimal" defaultValue={versamento.importo || ''} maxLength={20}/></label>
              <label>Estremi (protocollo telematico)<input name="versamentoEstremi" defaultValue={versamento.estremi || ''} maxLength={24} placeholder="i due campi dopo «PROTOCOLLO TELEMATICO»"/></label>
              <label>Numero riga F24<input name="versamentoRiga" inputMode="numeric" defaultValue={versamento.numeroRiga || '1'} maxLength={2}/></label>
              <label>Codice tributo
                <select name="versamentoCodice" defaultValue={versamento.codiceTributo || ''}>
                  <option value="">Scegli</option>
                  {(catalogo?.codiciTributo || []).map((c) => <option key={c.codice} value={c.codice}>{c.descrizione}</option>)}
                </select></label>
              <label>Elementi identificativi (CF o P.IVA di chi versa)<input name="versamentoElementi" defaultValue={versamento.elementi || ''} maxLength={17}/></label>
            </div>
            <label className="iu-pat-spunta"><input type="checkbox" name="versamentoAltroUfficio" value="1" defaultChecked={Boolean(versamento.altroUfficio)}/> Versamento eseguito presso un altro ufficio</label>
          </div>
        ) : null}
        {quadro.contributo.nota ? <p className="iu-pat-nota">{quadro.contributo.importo ? `Importo proposto € ${quadro.contributo.importo.toFixed(2).replace('.', ',')}. ` : ''}{quadro.contributo.nota}</p> : null}
      </section>
      <div className="iu-pat-barra">
        <button type="submit" className="iu-pat-primario"><Save size={15}/> Salva il procedimento</button>
        {stato ? <span role="status">{stato}</span> : null}
      </div>
    </form>
  )
}
