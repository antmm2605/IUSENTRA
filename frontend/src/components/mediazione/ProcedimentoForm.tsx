import { ActionButton as Button } from './ActionButton'
import { formatDateIt, formatDateTimeIt } from '../../formatting'
import type { Document, Preview, Procedure, Row } from './types'
import { modes, regimes, states, text } from './types'
import { AllegatiMediazione } from './AllegatiMediazione'
import { DocumentoMediazione } from './DocumentoMediazione'

const documents: [string, string][] = [
  ['istanza_documento', 'Istanza da depositare / depositata'],
  ['delega_documento', 'Delega / procura'], ['pagamento_documento', 'Prova del pagamento'],
]
const checks: [string, string][] = [
  ['competenza_verificata', 'Ho verificato competenza territoriale ed eventuale accordo derogatorio.'],
  ['informativa_avvocato', 'Ho verificato l’informativa dell’avvocato al cliente.'],
  ['assistenza_verificata', 'Ho verificato assistenza legale, partecipazione personale ed eventuali deleghe.'],
  ['riservatezza_verificata', 'Ho verificato privacy, riservatezza e documenti da comunicare all’organismo.'],
  ['modulo_verificato', 'Ho verificato modulistica, regolamento e istruzioni dell’organismo scelto.'],
  ['patrocinio_richiesto', 'È richiesto il patrocinio a spese dello Stato: verificare ammissione e documentazione.'],
]

export function ProcedimentoForm({ value, change, docs, preview }: {
  value: Procedure; change: (patch: Partial<Procedure>) => void; docs: Document[]; preview: (doc: Preview) => void
}) {
  const field = (key: string, label: string, type = 'text') => <label key={key}>{label}<input type={type} value={text(value, key)} onChange={(e) => change({ [key]: e.target.value })} /></label>
  const area = (key: string, label: string) => <label key={key}>{label}<textarea rows={3} value={text(value, key)} onChange={(e) => change({ [key]: e.target.value })} /></label>
  const select = (key: string, label: string, options: Record<string, string>) => <label>{label}<select value={text(value, key)} onChange={(e) => change({ [key]: e.target.value })}>{Object.entries(options).map(([v, title]) => <option key={v} value={v}>{title}</option>)}</select></label>
  const docSelect = (label: string, selected: string, update: (id: string) => void) => {
    return <DocumentoMediazione label={label} selected={selected} update={update} docs={docs} preview={preview} />
  }
  const updateRow = (key: 'parti' | 'incontri' | 'proroghe', index: number, patch: Row) => change({ [key]: value[key].map((row, i) => i === index ? { ...row, ...patch } : row) })
  const removeRow = (key: 'parti' | 'incontri' | 'proroghe', index: number) => change({ [key]: value[key].filter((_, i) => i !== index) })
  const rowField = (key: 'parti' | 'incontri' | 'proroghe', index: number, name: string, label: string, type = 'text') => {
    const raw = value[key][index][name] || ''
    const visible = type === 'datetime-local' ? raw.slice(0, 16) : raw
    return <label key={name}>{label}<input type={type} value={visible} onChange={(e) => updateRow(key, index, { [name]: e.target.value })} /></label>
  }
  return <>
    <section className="iu-mediazione-block"><h3>Procedimento</h3>
      {field('titolo', 'Titolo')}
      <div className="iu-mediazione-grid">{select('regime', 'Tipo di mediazione', regimes)}{select('modalita', 'Modalità', modes)}{select('stato', 'Stato da registrare', states)}</div>
      <p>Le modalità telematiche e da remoto richiedono l’accordo e le condizioni previste dagli artt. 8-bis e 8-ter. Il salvataggio non invia l’istanza.</p>
      {area('oggetto', 'Oggetto della controversia')}{area('ragioni', 'Ragioni della pretesa')}{area('competenza', 'Competenza territoriale / accordo derogatorio')}
      <div className="iu-mediazione-grid">{field('valore', 'Valore della controversia (€)')}<label className="iu-mediazione-check"><input type="checkbox" checked={Boolean(value.valore_indeterminabile)} onChange={(e) => change({ valore_indeterminabile: e.target.checked, valore: e.target.checked ? '' : value.valore })} />Valore indeterminabile</label></div>
    </section>
    <section className="iu-mediazione-block"><h3>Parti e difensori</h3><p>I dati proposti provengono dal fascicolo: completali e controllali prima di comunicarli all’organismo.</p>
      {value.parti.map((_, i) => <fieldset key={i}><legend>Parte {i + 1}</legend><div className="iu-mediazione-grid">
        {rowField('parti', i, 'nome', 'Nome / denominazione')}
        <label>Ruolo<select value={value.parti[i].ruolo} onChange={(e) => updateRow('parti', i, { ruolo: e.target.value })}><option value="istante">Istante</option><option value="invitata">Invitata</option><option value="aderente">Aderente</option></select></label>
        {rowField('parti', i, 'codice_fiscale', 'Codice fiscale / P. IVA')}{rowField('parti', i, 'indirizzo', 'Indirizzo')}
        {rowField('parti', i, 'pec', 'PEC', 'email')}{rowField('parti', i, 'email', 'Email', 'email')}
        {rowField('parti', i, 'difensore', 'Difensore')}{rowField('parti', i, 'rappresentante', 'Rappresentante / delegato')}
      </div><Button onClick={() => removeRow('parti', i)}>Rimuovi parte {i + 1}</Button></fieldset>)}
      <Button onClick={() => change({ parti: [...value.parti, { nome: '', ruolo: 'invitata' }] })}>Aggiungi parte</Button>
    </section>
    <section className="iu-mediazione-block"><h3>Verifiche professionali</h3>{checks.map(([key, label]) => <label className="iu-mediazione-check" key={key}><input type="checkbox" checked={Boolean(value[key])} onChange={(e) => change({ [key]: e.target.checked })} />{label}</label>)}</section>
    <section className="iu-mediazione-block"><h3>Preparazione dei documenti</h3>
      <p>I moduli dell’ente si scelgono nella sezione «Moduli dell’organismo acquisiti». Qui colleghi i documenti effettivi del procedimento, dopo averne controllato il contenuto. La presenza di un documento nel fascicolo non ne attesta l’idoneità.</p>
      <div className="iu-mediazione-grid">{documents.map(([key, label]) => <div key={key}>{docSelect(label, text(value, key), (id) => change({ [key]: id }))}</div>)}</div>
      {value.modulo_fonte ? <p>Modulo acquisito per organismo n. {value.modulo_fonte.organismo_numero} il {formatDateTimeIt(value.modulo_fonte.acquisito_il)}: <a href={value.modulo_fonte.url} target="_blank" rel="noopener noreferrer">fonte originale</a>.</p> : null}
      <AllegatiMediazione docs={docs} selected={value.allegati_documenti || []} change={(ids) => change({ allegati_documenti: ids })} preview={preview} />
    </section>
    {value.regime === 'demandata' || text(value, 'data_ordinanza') || text(value, 'ordinanza_documento') ? <section className="iu-mediazione-block"><h3>Mediazione disposta dal giudice</h3><p>Collega soltanto il provvedimento che dispone la mediazione, non una qualsiasi ordinanza del fascicolo.</p>{docSelect('Ordinanza che dispone la mediazione', text(value, 'ordinanza_documento'), (id) => change({ ordinanza_documento: id }))}{field('data_ordinanza', 'Data di deposito dell’ordinanza che dispone la mediazione', 'date')}</section> : null}
    <details className="iu-mediazione-block" open={['depositata', 'in_corso', 'accordo', 'mancato_accordo'].includes(value.stato) || Boolean(value.data_deposito)}><summary>Deposito presso l’organismo — dopo la trasmissione</summary><p>Compila questi dati solo dopo il deposito effettivo sul portale o sul canale indicato dall’ente. Salvare una bozza in IUSENTRA non equivale a depositarla.</p>{docSelect('Ricevuta di deposito presso l’organismo', text(value, 'ricevuta_documento'), (id) => change({ ricevuta_documento: id }))}<div className="iu-mediazione-grid">{field('data_deposito', 'Data effettiva di deposito della domanda', 'date')}{field('protocollo', 'Numero assegnato dall’organismo')}{field('mediatore', 'Mediatore designato dall’organismo')}</div></details>
    <section className="iu-mediazione-block"><h3>Incontri</h3>
      {value.incontri.map((_, i) => <fieldset key={i}><legend>Incontro {i + 1}</legend><div className="iu-mediazione-grid">{rowField('incontri', i, 'data_ora', 'Data e ora italiana', 'datetime-local')}{rowField('incontri', i, 'luogo', 'Luogo / collegamento')}{rowField('incontri', i, 'presenze', 'Partecipazioni effettive')}{rowField('incontri', i, 'note', 'Annotazioni')}</div>{docSelect('Verbale dell’incontro', value.incontri[i].verbale_documento || '', (id) => updateRow('incontri', i, { verbale_documento: id }))}<Button onClick={() => removeRow('incontri', i)}>Rimuovi incontro {i + 1}</Button></fieldset>)}
      <Button onClick={() => change({ incontri: [...value.incontri, { data_ora: '', luogo: '' }] })}>Aggiungi incontro</Button>
    </section>
    <section className="iu-mediazione-block"><h3>Durata e proroghe</h3>
      <p>Termine ordinario: sei mesi, senza sospensione feriale. Proroghe scritte anteriori alla scadenza, al massimo tre mesi ciascuna; una sola per i casi giudiziali previsti dall’art. 6. Verifica il regime transitorio per procedimenti storici.</p>
      {value.calendario?.scadenza ? <p>Scadenza calcolata sui dati salvati: <strong>{formatDateIt(String(value.calendario.scadenza))}</strong>. Primo incontro: {formatDateIt(String(value.calendario.primo_incontro_da || ''))} – {formatDateIt(String(value.calendario.primo_incontro_entro || ''))}, salvo diversa concorde indicazione delle parti.</p> : null}
      {value.proroghe.map((_, i) => <fieldset key={i}><legend>Proroga {i + 1}</legend><div className="iu-mediazione-grid">{rowField('proroghe', i, 'data_accordo', 'Data dell’accordo scritto', 'date')}{rowField('proroghe', i, 'scadenza', 'Nuova scadenza', 'date')}{docSelect('Accordo di proroga', value.proroghe[i].documento || '', (id) => updateRow('proroghe', i, { documento: id }))}{docSelect('Comunicazione al giudice, quando prevista', value.proroghe[i].comunicazione_giudice_documento || '', (id) => updateRow('proroghe', i, { comunicazione_giudice_documento: id }))}</div><Button onClick={() => removeRow('proroghe', i)}>Rimuovi proroga {i + 1}</Button></fieldset>)}
      <Button onClick={() => change({ proroghe: [...value.proroghe, { data_accordo: '', scadenza: '' }] })}>Aggiungi proroga</Button>
    </section>
    <details className="iu-mediazione-block" open={['accordo', 'mancato_accordo', 'ritirata'].includes(value.stato)}><summary>Conclusione della mediazione — verbale ed eventuale accordo</summary><p>Il verbale conclusivo è quello della mediazione, non il verbale di un’udienza giudiziaria. L’accordo si collega soltanto se raggiunto e sottoscritto.</p>{docSelect('Verbale conclusivo della mediazione', text(value, 'verbale_documento'), (id) => change({ verbale_documento: id }))}{docSelect('Accordo di mediazione sottoscritto', text(value, 'accordo_documento'), (id) => change({ accordo_documento: id }))}{field('data_chiusura', 'Data di conclusione', 'date')}{area('esito_note', 'Esito, adempimenti successivi e condizioni di esecutività da verificare')}</details>
    <section className="iu-mediazione-block"><h3>Note dello studio</h3>{area('note_riservate', 'Note riservate dello studio — escluse dalle bozze per l’organismo')}</section>
  </>
}
