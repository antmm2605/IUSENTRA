import { useState } from 'react'
import { AlertTriangle, BookOpen, CheckCircle2, ExternalLink, FileText, MessageSquare, Plus, Scale, Trash2 } from 'lucide-react'
import { dataIt, type Fonte, type SchedaUdienza, type TermineAssegnato } from './preparazioneUdienzaTipi'

export type Azioni = {
  salvaCampi: (passo: number, campi: Record<string, unknown>, conferma?: boolean) => Promise<void>
  azione: (azione: string, corpo: Record<string, unknown>) => Promise<Record<string, unknown>>
  occupato: boolean
}

function Norma({ fonte }: { fonte: Fonte }) {
  if (!fonte?.norma) return <span className="iu-pu-norma is-operativa">Controllo operativo</span>
  return (
    <details className="iu-pu-norma">
      <summary><BookOpen size={12}/> {fonte.norma}</summary>
      <p>{fonte.estratto}</p>
      {fonte.url ? <a href={fonte.url} target="_blank" rel="noreferrer">Testo vigente su Normattiva <ExternalLink size={11}/></a> : null}
    </details>
  )
}

function Testo({ nome, etichetta, valore, righe = 4, suggerimento, passo, a }: { nome: string; etichetta: string; valore: string; righe?: number; suggerimento: string; passo: number; a: Azioni }) {
  const [testo, setTesto] = useState(valore)
  return (
    <label className="iu-pu-campo"><span>{etichetta}</span>
      <textarea rows={righe} value={testo} placeholder={suggerimento} onChange={(e) => setTesto(e.target.value)}
        onBlur={() => { if (testo !== valore) void a.salvaCampi(passo, { [nome]: testo }) }}/>
    </label>
  )
}

export function PassoQuadro({ s, a }: { s: SchedaUdienza; a: Azioni }) {
  return (
    <div className="iu-pu-passo">
      <div className="iu-pu-fatti">
        <div><span>Cliente</span><strong>{s.causa.cliente || '—'}</strong></div>
        <div><span>Controparte</span><strong>{s.causa.controparte || 'Non indicata nel fascicolo'}</strong>{s.causa.avvocatoControparte ? <small>{s.causa.avvocatoControparte}</small> : null}</div>
        <div><span>Oggetto</span><strong>{s.causa.oggetto || '—'}</strong></div>
        <div><span>Giudice</span><strong>{s.udienza.giudice || '—'}</strong>{s.udienza.sezione ? <small>Sezione {s.udienza.sezione}</small> : null}</div>
      </div>

      <section className="iu-pu-blocco">
        <h3><Scale size={15}/> Tipo di udienza e verifiche di legge</h3>
        <select value={s.tipoUdienza} disabled={!s.puoModificare} onChange={(e) => void a.salvaCampi(1, { tipo_udienza: e.target.value })}>
          <option value="">Scegli il tipo di udienza</option>
          {s.tipi.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        {s.verifiche.length ? (
          <ul className="iu-pu-verifiche">
            {s.verifiche.map((v) => (
              <li key={v.id} className={v.fatta ? 'is-fatta' : ''}>
                <label><input type="checkbox" checked={v.fatta} disabled={!s.puoModificare || a.occupato}
                  onChange={(e) => void a.azione('verifica', { id: v.id, fatta: e.target.checked })}/><span>{v.testo}</span></label>
                <Norma fonte={v.fonte}/>
              </li>
            ))}
          </ul>
        ) : s.tipoUdienza ? <p className="iu-pu-nota">Nessuna verifica di legge specifica per questo tipo di udienza.</p> : <p className="iu-pu-nota">Scegliendo il tipo compaiono le verifiche previste dalla legge, con il testo della norma.</p>}
        <p className="iu-pu-avviso"><AlertTriangle size={14}/> <span>{s.avvisoAssenza.testo}</span> <Norma fonte={s.avvisoAssenza.fonte}/></p>
      </section>

      <div className="iu-pu-colonne">
        <section className="iu-pu-blocco">
          <h3>Termini aperti del fascicolo</h3>
          {s.termini.length ? <ul className="iu-pu-lista">{s.termini.map((t) => (
            <li key={t.href}><a href={t.href}>{t.titolo}</a><span>{dataIt(t.data)}{t.perentorio ? ' · perentorio' : ''}</span></li>
          ))}</ul> : <p className="iu-pu-nota">Nessun termine aperto.</p>}
        </section>
        <section className="iu-pu-blocco">
          <h3>Ultime attività</h3>
          {s.attivita.length ? <ul className="iu-pu-lista">{s.attivita.map((t, i) => (
            <li key={`${t.data}-${i}`}><strong>{t.titolo}</strong><span>{dataIt(t.data)}{t.descrizione ? ` · ${t.descrizione}` : ''}</span></li>
          ))}</ul> : <p className="iu-pu-nota">Nessuna attività registrata nel fascicolo.</p>}
        </section>
      </div>
      <Testo nome="step1_note" etichetta="Appunti sulla causa" valore={String(s.campi.step1_note || '')} passo={1} a={a}
        suggerimento="Punti da ricordare: cosa ha detto il cliente, cosa è cambiato dall'ultima udienza, cosa chiede il giudice."/>
    </div>
  )
}

export function PassoDocumenti({ s, a }: { s: SchedaUdienza; a: Azioni }) {
  const [extra, setExtra] = useState('')
  const utili = s.documenti.filter((d) => d.stato !== 'non_necessario')
  const pronti = utili.filter((d) => d.stato === 'pronto').length
  return (
    <div className="iu-pu-passo">
      <p className="iu-pu-conteggio"><strong>{pronti} di {utili.length}</strong> documenti pronti{utili.length && pronti === utili.length ? ' — tutto pronto' : ''}.</p>
      <ul className="iu-pu-documenti">
        {s.documenti.map((d) => (
          <li key={d.indice} className={`is-${d.stato}`}>
            <div><FileText size={15}/><span>{d.etichetta}{d.firmato ? <small> · firmato</small> : null}</span></div>
            <div className="iu-pu-segmenti" role="group" aria-label={`Stato di ${d.etichetta}`}>
              {[['da_portare', 'Da preparare'], ['pronto', 'Pronto'], ['non_necessario', 'Non serve']].map(([valore, etichetta]) => (
                <button type="button" key={valore} aria-pressed={d.stato === valore} disabled={!s.puoModificare || a.occupato}
                  onClick={() => void a.azione('documento', { indice: d.indice, stato: valore })}>{etichetta}</button>
              ))}
            </div>
            {d.href ? <a href={d.href} target="_blank" rel="noreferrer">Apri</a> : <span/>}
          </li>
        ))}
      </ul>
      {s.puoModificare ? (
        <div className="iu-pu-aggiungi">
          <input value={extra} placeholder="Altro da portare (es. originale del contratto, fascicolo di parte cartaceo)" onChange={(e) => setExtra(e.target.value)}/>
          <button type="button" disabled={!extra.trim() || a.occupato} onClick={() => void a.azione('documento-extra', { etichetta: extra }).then((r) => { if (r.ok) setExtra('') })}><Plus size={14}/> Aggiungi</button>
        </div>
      ) : null}
    </div>
  )
}

export function PassoStrategia({ s, a }: { s: SchedaUdienza; a: Azioni }) {
  return (
    <div className="iu-pu-passo iu-pu-griglia-testi">
      <Testo nome="argomenti_principali" etichetta="Argomenti da sostenere" valore={String(s.campi.argomenti_principali || '')} passo={3} a={a}
        suggerimento="I punti forti, nell'ordine in cui li esporrai."/>
      <Testo nome="richieste_giudice" etichetta="Richieste al giudice" valore={String(s.campi.richieste_giudice || '')} passo={3} a={a}
        suggerimento="Istanze istruttorie, termini, rinvio, ammissione di testi o CTU."/>
      <Testo nome="eccezioni_da_sollevare" etichetta="Eccezioni" valore={String(s.campi.eccezioni_da_sollevare || '')} passo={3} a={a}
        suggerimento="Eccezioni da sollevare o da contrastare."/>
      <Testo nome="note_preparazione" etichetta="Se la controparte…" valore={String(s.campi.note_preparazione || '')} passo={3} a={a}
        suggerimento="Risposte pronte alle mosse prevedibili della controparte."/>
    </div>
  )
}

export function PassoPartenza({ s, a }: { s: SchedaUdienza; a: Azioni }) {
  const pronti = s.documenti.filter((d) => d.stato === 'pronto').length
  const utili = s.documenti.filter((d) => d.stato !== 'non_necessario').length
  const voce = (campo: string, testo: string, dettaglio: React.ReactNode) => (
    <li className={s.campi[campo] ? 'is-fatta' : ''}>
      <label><input type="checkbox" checked={Boolean(s.campi[campo])} disabled={!s.puoModificare || a.occupato}
        onChange={(e) => void a.salvaCampi(4, { [campo]: e.target.checked })}/><span>{testo}</span></label>
      <small>{dettaglio}</small>
    </li>
  )
  return (
    <div className="iu-pu-passo">
      <ul className="iu-pu-verifiche">
        {voce('precheck_cliente_notificato', 'Cliente avvisato di data, ora e luogo', <a href={s.messaggioClienteHref}><MessageSquare size={12}/> Scrivi al cliente</a>)}
        {voce('precheck_docs_pronti', 'Documenti pronti', `${pronti} di ${utili} segnati come pronti`)}
        {voce('precheck_trasporto_ok', s.udienza.collegamento ? 'Collegamento da remoto verificato' : 'Trasferta organizzata',
          s.udienza.collegamento ? <a href={s.udienza.collegamento} target="_blank" rel="noreferrer">Apri il collegamento</a> : (s.udienza.luogo || 'Luogo da indicare in agenda'))}
        {voce('precheck_firma_ok', 'Dispositivo di firma con me, per depositi o verbali telematici', 'Smart card o firma remota')}
      </ul>
      <Testo nome="precheck_note" etichetta="Promemoria" valore={String(s.campi.precheck_note || '')} righe={3} passo={4} a={a}
        suggerimento="Es. parcheggio, aula spostata, collega che sostituisce."/>
    </div>
  )
}

export function PassoEsito({ s, a }: { s: SchedaUdienza; a: Azioni }) {
  const [esito, setEsito] = useState(s.esito.valore)
  const [rinvioData, setRinvioData] = useState(s.esito.rinvioData)
  const [rinvioOra, setRinvioOra] = useState(s.esito.rinvioOra || '09:00')
  const [note, setNote] = useState(s.esito.noteVerbale)
  const [azioniDopo, setAzioniDopo] = useState(s.esito.azioni)
  const [termini, setTermini] = useState<TermineAssegnato[]>(s.esito.termini.length ? s.esito.termini : [])
  const bloccato = !s.puoModificare
  if (s.completata) {
    return (
      <div className="iu-pu-passo">
        <p className="iu-pu-fatto"><CheckCircle2 size={18}/> Esito registrato: <strong>{s.esiti.find((e) => e.value === s.esito.valore)?.label}</strong>
          {s.esito.rinvioData ? <> al {dataIt(s.esito.rinvioData)} alle {s.esito.rinvioOra}</> : null}</p>
        <div className="iu-pu-azioni-esito">
          {s.esito.rinvioAgendaHref ? <a className="iu-pu-btn" href={s.esito.rinvioAgendaHref}>Apri l'udienza di rinvio</a> : null}
          {s.messaggioClienteHref ? <a className="iu-pu-btn" href={s.messaggioClienteHref}>Informa il cliente</a> : null}
        </div>
        {s.esito.termini.length ? <ul className="iu-pu-lista">{s.esito.termini.map((t) => <li key={`${t.descrizione}-${t.data}`}>{t.id_scadenza ? <a href={`/scadenziario/${encodeURIComponent(t.id_scadenza)}/modifica`}><strong>{t.descrizione}</strong></a> : <strong>{t.descrizione}</strong>}<span>{dataIt(t.data)}{t.perentorio ? ' · perentorio' : ''}</span></li>)}</ul> : null}
        {s.esito.noteVerbale ? <p className="iu-pu-nota">{s.esito.noteVerbale}</p> : null}
        {s.esito.azioni ? <p className="iu-pu-nota">{s.esito.azioni}</p> : null}
      </div>
    )
  }
  return (
    <div className="iu-pu-passo">
      <div className="iu-pu-esiti" role="group" aria-label="Esito dell'udienza">
        {s.esiti.map((e) => <button type="button" key={e.value} aria-pressed={esito === e.value} disabled={bloccato} onClick={() => setEsito(e.value)}>{e.label}</button>)}
      </div>
      {esito === 'rinvio' ? (
        <div className="iu-pu-riga">
          <label className="iu-pu-campo"><span>Rinvio al</span><input type="date" value={rinvioData} onChange={(e) => setRinvioData(e.target.value)}/></label>
          <label className="iu-pu-campo"><span>Ore</span><input type="time" value={rinvioOra} onChange={(e) => setRinvioOra(e.target.value)}/></label>
          <p className="iu-pu-nota">L'udienza di rinvio viene inserita in agenda e diventa la prossima udienza del fascicolo.</p>
        </div>
      ) : null}
      <section className="iu-pu-blocco">
        <h3>Termini assegnati dal giudice</h3>
        {termini.map((t, i) => (
          <div className="iu-pu-riga" key={i}>
            <label className="iu-pu-campo is-largo"><span>Adempimento</span><input value={t.descrizione} placeholder="Es. deposito note scritte" disabled={Boolean(t.id_scadenza)}
              onChange={(e) => setTermini(termini.map((x, j) => (j === i ? { ...x, descrizione: e.target.value } : x)))}/></label>
            <label className="iu-pu-campo"><span>Entro il</span><input type="date" value={t.data} disabled={Boolean(t.id_scadenza)}
              onChange={(e) => setTermini(termini.map((x, j) => (j === i ? { ...x, data: e.target.value } : x)))}/></label>
            <label className="iu-pu-spunta"><input type="checkbox" checked={t.perentorio} disabled={Boolean(t.id_scadenza)}
              onChange={(e) => setTermini(termini.map((x, j) => (j === i ? { ...x, perentorio: e.target.checked } : x)))}/><span>Perentorio</span></label>
            {!t.id_scadenza ? <button type="button" className="iu-pu-icona" aria-label="Togli il termine" onClick={() => setTermini(termini.filter((_, j) => j !== i))}><Trash2 size={14}/></button> : null}
          </div>
        ))}
        {!bloccato ? <button type="button" className="iu-pu-btn" onClick={() => setTermini([...termini, { descrizione: '', data: '', perentorio: false }])}><Plus size={14}/> Aggiungi un termine</button> : null}
        <p className="iu-pu-nota">Ogni termine diventa una scadenza del fascicolo, con gli avvisi dello scadenziario.</p>
      </section>
      <label className="iu-pu-campo"><span>Cosa è successo in udienza</span><textarea rows={4} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Sintesi del verbale: dichiarazioni, provvedimenti, riserve."/></label>
      <label className="iu-pu-campo"><span>Cosa fare adesso</span><textarea rows={3} value={azioniDopo} onChange={(e) => setAzioniDopo(e.target.value)} placeholder="Es. informare il cliente, preparare le memorie, contattare il CTU."/></label>
      {!bloccato ? (
        <button type="button" className="iu-pu-btn is-primario" disabled={!esito || a.occupato || (esito === 'rinvio' && !rinvioData)}
          onClick={() => void a.azione('esito', { esito, rinvioData, rinvioOra, noteVerbale: note, azioni: azioniDopo, termini })}>Registra l'esito</button>
      ) : null}
    </div>
  )
}
