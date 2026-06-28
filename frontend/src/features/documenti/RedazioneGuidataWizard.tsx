import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, BookOpenCheck, CheckCircle2, FileWarning, FolderOpen, Scale, Sparkles, UserRound } from 'lucide-react'
import { Badge } from '../../ui/Badge'
import { Button } from '../../ui/Button'
import { EmptyState } from '../../ui/EmptyState'
import { LoadingState } from '../../ui/LoadingState'
import {
  generaRedazioneAtto,
  getRedazioneAnteprima,
  getRedazioneClienti,
  getRedazioneContesto,
  getRedazioneFascicoli,
  type RedazioneAnteprima,
  type RedazioneCliente,
  type RedazioneContesto,
  type RedazioneFascicolo,
} from '../../redazioneAttiData'
import { formatEuroIt } from '../../formatting'

type PassoWizard = 1 | 2 | 3 | 4

const PASSI: Array<{ numero: PassoWizard; titolo: string }> = [
  { numero: 1, titolo: 'Cliente' },
  { numero: 2, titolo: 'Fascicolo' },
  { numero: 3, titolo: 'Tipo atto' },
  { numero: 4, titolo: 'Campi e normativa' },
]

function IntestazionePassi({ passo }: { passo: PassoWizard }) {
  return (
    <ol className="iu-rg-steps" aria-label="Passi della redazione guidata">
      {PASSI.map((voce) => (
        <li
          key={voce.numero}
          className={voce.numero === passo ? 'iu-rg-step is-active' : voce.numero < passo ? 'iu-rg-step is-done' : 'iu-rg-step'}
          aria-current={voce.numero === passo ? 'step' : undefined}
        >
          <span className="iu-rg-step__num">{voce.numero < passo ? <CheckCircle2 size={16} aria-hidden="true" /> : voce.numero}</span>
          <span>{voce.titolo}</span>
        </li>
      ))}
    </ol>
  )
}

function PassoCliente({
  onSeleziona,
}: {
  onSeleziona: (cliente: RedazioneCliente) => void
}) {
  const [clienti, setClienti] = useState<RedazioneCliente[]>([])
  const [errore, setErrore] = useState('')
  const [ricerca, setRicerca] = useState('')
  const [caricamento, setCaricamento] = useState(true)

  useEffect(() => {
    getRedazioneClienti()
      .then((esito) => {
        setClienti(esito.clienti)
        setErrore(esito.errore)
      })
      .finally(() => setCaricamento(false))
  }, [])

  const filtrati = useMemo(() => {
    const chiave = ricerca.trim().toLowerCase()
    if (!chiave) return clienti
    return clienti.filter((cliente) =>
      cliente.label.toLowerCase().includes(chiave) || cliente.codiceFiscale.toLowerCase().includes(chiave),
    )
  }, [clienti, ricerca])

  if (caricamento) return <LoadingState title="Caricamento clienti" message="Recupero anagrafiche reali dello studio." />
  if (errore) return <EmptyState title="Clienti non disponibili" message={errore} />
  if (!clienti.length) {
    return <EmptyState title="Nessun cliente in archivio" message="Registra prima il cliente: la redazione parte sempre dai dati reali." />
  }

  return (
    <div className="iu-rg-panel">
      <label className="iu-rg-search">
        <span>Cerca cliente</span>
        <input
          type="search"
          value={ricerca}
          onChange={(event) => setRicerca(event.target.value)}
          placeholder="Nome, denominazione o codice fiscale"
          aria-label="Cerca cliente"
        />
      </label>
      <div className="iu-rg-cards" role="list">
        {filtrati.map((cliente) => (
          <button type="button" className="iu-rg-card iu-od-focus-ring" key={cliente.id} onClick={() => onSeleziona(cliente)} role="listitem">
            <UserRound size={18} aria-hidden="true" />
            <span className="iu-rg-card__body">
              <strong>{cliente.label}</strong>
              <small>
                {cliente.tipo === 'PERSONA_GIURIDICA' ? 'Persona giuridica' : 'Persona fisica'}
                {cliente.codiceFiscale ? ` - C.F. ${cliente.codiceFiscale}` : ''}
              </small>
            </span>
            <Badge tone={cliente.fascicoli ? 'primary' : 'neutral'}>
              {cliente.fascicoli === 1 ? '1 fascicolo' : `${cliente.fascicoli} fascicoli`}
            </Badge>
          </button>
        ))}
        {!filtrati.length ? <EmptyState title="Nessun cliente corrisponde alla ricerca" /> : null}
      </div>
    </div>
  )
}

function PassoFascicolo({
  cliente,
  onSeleziona,
}: {
  cliente: RedazioneCliente
  onSeleziona: (fascicolo: RedazioneFascicolo) => void
}) {
  const [fascicoli, setFascicoli] = useState<RedazioneFascicolo[]>([])
  const [errore, setErrore] = useState('')
  const [caricamento, setCaricamento] = useState(true)

  useEffect(() => {
    setCaricamento(true)
    getRedazioneFascicoli(cliente.id)
      .then((esito) => {
        setFascicoli(esito.fascicoli)
        setErrore(esito.errore)
      })
      .finally(() => setCaricamento(false))
  }, [cliente.id])

  if (caricamento) return <LoadingState title="Caricamento fascicoli" message={`Fascicoli associati a ${cliente.label}.`} />
  if (errore) return <EmptyState title="Fascicoli non disponibili" message={errore} />
  if (!fascicoli.length) {
    return <EmptyState title="Nessun fascicolo per questo cliente" message="Apri prima il fascicolo: l'atto deve restare collegato alla pratica reale." />
  }

  return (
    <div className="iu-rg-panel">
      <p className="iu-rg-hint">Fascicoli di <strong>{cliente.label}</strong>: la selezione carica automaticamente parti, ufficio, R.G., valore e allegati.</p>
      <div className="iu-rg-cards" role="list">
        {fascicoli.map((fascicolo) => (
          <button type="button" className="iu-rg-card iu-od-focus-ring" key={fascicolo.id} onClick={() => onSeleziona(fascicolo)} role="listitem">
            <FolderOpen size={18} aria-hidden="true" />
            <span className="iu-rg-card__body">
              <strong>{fascicolo.numero ? `${fascicolo.numero} - ` : ''}{fascicolo.titolo || 'Fascicolo'}</strong>
              <small>
                {[fascicolo.materia, fascicolo.ufficio, fascicolo.rg ? `R.G. ${fascicolo.rg}` : '', fascicolo.controparte ? `c/ ${fascicolo.controparte}` : '']
                  .filter(Boolean)
                  .join(' - ') || 'Dati di dettaglio nel passo successivo'}
              </small>
            </span>
            <Badge tone="neutral">{fascicolo.stato || 'Aperto'}</Badge>
          </button>
        ))}
      </div>
    </div>
  )
}

function RigaDato({ etichetta, valore, mancante }: { etichetta: string; valore: string; mancante: boolean }) {
  return (
    <div className={mancante ? 'iu-rg-dato is-missing' : 'iu-rg-dato'}>
      <span>{etichetta}</span>
      <strong>{mancante ? 'Non presente' : valore}</strong>
    </div>
  )
}

function QuadroContesto({ contesto }: { contesto: RedazioneContesto }) {
  const fascicolo = contesto.fascicolo
  const chiavi: Array<[string, string]> = [
    ['ufficioGiudiziario', 'Ufficio giudiziario'],
    ['rg', 'R.G.'],
    ['giudice', 'Giudice'],
    ['materia', 'Materia'],
    ['oggetto', 'Oggetto'],
    ['valoreCausa', 'Valore causa'],
    ['prossimaUdienza', 'Prossima udienza'],
  ]
  return (
    <section className="iu-rg-contesto" aria-label="Dati reali del fascicolo">
      <div className="iu-rg-contesto__col">
        <h4>Dal fascicolo</h4>
        {chiavi.map(([chiave, fallback]) => {
          const campo = fascicolo[chiave]
          if (!campo) return null
          return <RigaDato key={chiave} etichetta={campo.etichetta || fallback} valore={campo.valore} mancante={campo.mancante} />
        })}
        <RigaDato
          etichetta="Contributo unificato (D.P.R. 115/2002)"
          valore={contesto.contributoUnificato.totale !== null ? `${formatEuroIt(contesto.contributoUnificato.totale)} - ${contesto.contributoUnificato.descrizione}` : ''}
          mancante={!contesto.contributoUnificato.disponibile}
        />
      </div>
      <div className="iu-rg-contesto__col">
        <h4>Parti</h4>
        {contesto.cliente ? (
          <RigaDato etichetta={`Assistito${contesto.cliente.personaGiuridica ? ' (persona giuridica)' : ''}`} valore={contesto.cliente.denominazione.valore} mancante={contesto.cliente.denominazione.mancante} />
        ) : null}
        {contesto.controparti.map((parte, indice) => (
          <RigaDato key={`${parte.id || indice}`} etichetta={`Controparte${contesto.controparti.length > 1 ? ` ${indice + 1}` : ''}`} valore={parte.denominazione.valore} mancante={parte.denominazione.mancante} />
        ))}
        {!contesto.controparti.length ? <RigaDato etichetta="Controparte" valore="" mancante /> : null}
        {contesto.difensori.map((parte, indice) => (
          <RigaDato key={`dif-${parte.id || indice}`} etichetta="Difensore controparte" valore={parte.denominazione.valore} mancante={parte.denominazione.mancante} />
        ))}
        {contesto.allegati.length ? (
          <p className="iu-rg-hint">{contesto.allegati.length === 1 ? '1 allegato collegato' : `${contesto.allegati.length} allegati collegati`} al fascicolo.</p>
        ) : null}
      </div>
    </section>
  )
}

function PassoTipoAtto({
  contesto,
  onSeleziona,
}: {
  contesto: RedazioneContesto
  onSeleziona: (modelCode: string, nome: string) => void
}) {
  const [areaCatalogo, setAreaCatalogo] = useState('')
  const areaSelezionata = contesto.catalogo.find((gruppo) => gruppo.area === areaCatalogo) || null

  return (
    <div className="iu-rg-panel">
      <QuadroContesto contesto={contesto} />
      <h4 className="iu-rg-subtitle"><Sparkles size={16} aria-hidden="true" /> Atti suggeriti dal fascicolo</h4>
      {contesto.suggerimenti.length ? (
        <div className="iu-rg-cards" role="list">
          {contesto.suggerimenti.map((suggerimento) => (
            <button
              type="button"
              className="iu-rg-card iu-rg-card--suggest iu-od-focus-ring"
              key={suggerimento.code}
              onClick={() => onSeleziona(suggerimento.code, suggerimento.name)}
              role="listitem"
            >
              <Scale size={18} aria-hidden="true" />
              <span className="iu-rg-card__body">
                <strong>{suggerimento.name}</strong>
                <small>{suggerimento.areaLabel}</small>
                <ul className="iu-rg-motivi">
                  {suggerimento.motivi.slice(0, 3).map((motivo) => <li key={motivo}>{motivo}</li>)}
                </ul>
              </span>
              <Badge tone="primary">Consigliato</Badge>
            </button>
          ))}
        </div>
      ) : (
        <EmptyState title="Nessun suggerimento automatico" message="Scegli il tipo di atto dal catalogo completo qui sotto." />
      )}
      <h4 className="iu-rg-subtitle"><BookOpenCheck size={16} aria-hidden="true" /> Catalogo completo</h4>
      <div className="iu-rg-catalogo">
        <label>
          <span>Area</span>
          <select value={areaCatalogo} onChange={(event) => setAreaCatalogo(event.target.value)} aria-label="Area del catalogo atti">
            <option value="">Seleziona area</option>
            {contesto.catalogo.map((gruppo) => (
              <option value={gruppo.area} key={gruppo.area}>{gruppo.label} ({gruppo.modelli.length})</option>
            ))}
          </select>
        </label>
        {areaSelezionata ? (
          <div className="iu-rg-catalogo__list" role="list">
            {areaSelezionata.modelli.map((modello) => (
              <button type="button" className="iu-rg-chip iu-od-focus-ring" key={modello.code} onClick={() => onSeleziona(modello.code, modello.name)} role="listitem">
                {modello.name}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function PassoAnteprima({
  modelCode,
  modelName,
  fascicoloId,
  clienteId,
  onGenerato,
}: {
  modelCode: string
  modelName: string
  fascicoloId: string
  clienteId: string
  onGenerato: (editorUrl: string) => void
}) {
  const [anteprima, setAnteprima] = useState<RedazioneAnteprima | null>(null)
  const [caricamento, setCaricamento] = useState(true)
  const [valori, setValori] = useState<Record<string, string>>({})
  const [esclusi, setEsclusi] = useState<Set<string>>(new Set())
  const [errore, setErrore] = useState('')
  const [richiedeConfermaBozza, setRichiedeConfermaBozza] = useState(false)
  const [richiedeConfermaAvvisi, setRichiedeConfermaAvvisi] = useState(false)
  const [generazione, setGenerazione] = useState(false)

  useEffect(() => {
    setCaricamento(true)
    getRedazioneAnteprima(modelCode, fascicoloId, clienteId)
      .then((esito) => {
        setAnteprima(esito)
        setErrore(esito.ok ? '' : esito.errore)
        setValori({})
        setEsclusi(new Set())
      })
      .finally(() => setCaricamento(false))
  }, [modelCode, fascicoloId, clienteId])

  if (caricamento) return <LoadingState title="Compilazione automatica" message="Lettura dei dati reali di fascicolo, cliente e parti." />
  if (!anteprima || (!anteprima.ok && errore)) {
    return <EmptyState title="Anteprima non disponibile" message={errore || 'Riprova dalla selezione del tipo atto.'} />
  }

  const aggiornaValore = (name: string, value: string) => {
    setValori((correnti) => ({ ...correnti, [name]: value }))
  }

  const genera = (confermaBozza: boolean, confermaAvvisi: boolean) => {
    setGenerazione(true)
    setErrore('')
    const riferimentiSelezionati = anteprima.riferimenti
      .filter((riferimento) => !esclusi.has(riferimento.id))
      .map((riferimento) => ({
        ambito: riferimento.ambito,
        riferimento: riferimento.riferimento,
        rubrica: riferimento.rubrica,
        motivo: riferimento.motivo,
      }))
    generaRedazioneAtto({
      modelCode,
      fascicoloId,
      clienteId,
      valori,
      riferimenti: riferimentiSelezionati,
      confermaBozza,
      confermaAvvisi,
    })
      .then((esito) => {
        if (esito.ok && esito.editorUrl) {
          onGenerato(esito.editorUrl)
          return
        }
        setRichiedeConfermaBozza(esito.richiedeConfermaBozza)
        setRichiedeConfermaAvvisi(esito.richiedeConfermaAvvisi)
        setErrore(esito.errore || 'Generazione non completata.')
      })
      .finally(() => setGenerazione(false))
  }

  const mancantiNonCompilati = anteprima.campiMancanti.filter((campo) => !(valori[campo.name] || '').trim())

  return (
    <div className="iu-rg-panel">
      <p className="iu-rg-hint">
        Modello selezionato: <strong>{modelName || anteprima.model.name}</strong>. I campi sotto sono gia' compilati con i dati reali; i mancanti restano evidenziati e puoi completarli ora.
      </p>
      <section aria-label="Campi compilati dai dati reali">
        <h4 className="iu-rg-subtitle"><CheckCircle2 size={16} aria-hidden="true" /> Campi compilati automaticamente ({anteprima.campiTrovati.length})</h4>
        <div className="iu-rg-trovati">
          {anteprima.campiTrovati.map((campo) => (
            <details className="iu-rg-trovato" key={campo.name}>
              <summary>
                <span>{campo.label}</span>
                <strong>{campo.value.length > 90 ? `${campo.value.slice(0, 90)}...` : campo.value}</strong>
                {campo.fonte ? <Badge tone="success">{campo.fonte}</Badge> : null}
              </summary>
              <textarea
                value={valori[campo.name] ?? campo.value}
                onChange={(event) => aggiornaValore(campo.name, event.target.value)}
                rows={3}
                aria-label={`Modifica ${campo.label}`}
              />
            </details>
          ))}
          {!anteprima.campiTrovati.length ? <EmptyState title="Nessun campo precompilabile" message="Il fascicolo non contiene ancora dati utilizzabili per questo modello." /> : null}
        </div>
      </section>
      <section aria-label="Campi mancanti">
        <h4 className="iu-rg-subtitle iu-rg-subtitle--warn"><FileWarning size={16} aria-hidden="true" /> Campi mancanti ({anteprima.campiMancanti.length})</h4>
        {anteprima.campiMancanti.length ? (
          <div className="iu-rg-mancanti">
            {anteprima.campiMancanti.map((campo) => (
              <label className="iu-rg-mancante" key={campo.name}>
                <span>{campo.label}</span>
                {campo.type === 'richtext' || campo.type === 'textarea' ? (
                  <textarea
                    value={valori[campo.name] ?? ''}
                    onChange={(event) => aggiornaValore(campo.name, event.target.value)}
                    rows={3}
                    placeholder={campo.motivo || 'Dato non presente nel fascicolo'}
                  />
                ) : (
                  <input
                    type={campo.type === 'date' || campo.type === 'number' ? campo.type : 'text'}
                    value={valori[campo.name] ?? ''}
                    onChange={(event) => aggiornaValore(campo.name, event.target.value)}
                    placeholder={campo.motivo || 'Dato non presente nel fascicolo'}
                  />
                )}
              </label>
            ))}
          </div>
        ) : (
          <p className="iu-rg-hint">Tutti i campi del modello risultano compilati dai dati reali.</p>
        )}
      </section>
      <section aria-label="Riferimenti normativi suggeriti">
        <h4 className="iu-rg-subtitle"><Scale size={16} aria-hidden="true" /> Riferimenti normativi ({anteprima.riferimenti.length})</h4>
        <p className="iu-rg-hint">Suggeriti in base a tipo atto, materia e condizioni rilevate nel fascicolo. Deseleziona quelli non pertinenti: confluiranno nella sezione in diritto e restano modificabili nell'editor.</p>
        <div className="iu-rg-riferimenti">
          {anteprima.riferimenti.map((riferimento) => (
            <label className="iu-rg-riferimento" key={riferimento.id}>
              <input
                type="checkbox"
                checked={!esclusi.has(riferimento.id)}
                onChange={(event) => {
                  setEsclusi((correnti) => {
                    const prossimi = new Set(correnti)
                    if (event.target.checked) prossimi.delete(riferimento.id)
                    else prossimi.add(riferimento.id)
                    return prossimi
                  })
                }}
              />
              <span className="iu-rg-riferimento__body">
                <strong>{riferimento.riferimento}</strong>
                <em>{riferimento.rubrica}</em>
                <small>{riferimento.motivo}</small>
              </span>
              <Badge tone={riferimento.ambito === 'processuale' ? 'info' : 'neutral'}>
                {riferimento.ambito === 'processuale' ? 'Processuale' : 'Sostanziale'}
              </Badge>
            </label>
          ))}
          {!anteprima.riferimenti.length ? <p className="iu-rg-hint">Nessun riferimento collegato a questo modello nel registro normativo.</p> : null}
        </div>
      </section>
      {errore ? <p className="iu-rg-errore" role="alert">{errore}</p> : null}
      <div className="iu-rg-azioni">
        <Button type="button" tone="primary" onClick={() => genera(false, false)} disabled={generazione}>
          {generazione ? 'Generazione in corso...' : 'Genera atto e apri editor'}
          <ArrowRight size={16} aria-hidden="true" />
        </Button>
        {richiedeConfermaBozza && mancantiNonCompilati.length ? (
          <Button type="button" tone="neutral" onClick={() => genera(true, true)} disabled={generazione}>
            Crea comunque bozza con {mancantiNonCompilati.length === 1 ? '1 dato mancante evidenziato' : `${mancantiNonCompilati.length} dati mancanti evidenziati`}
          </Button>
        ) : null}
        {richiedeConfermaAvvisi && !richiedeConfermaBozza ? (
          <Button type="button" tone="neutral" onClick={() => genera(false, true)} disabled={generazione}>
            Conferma gli avvisi e crea bozza di lavoro
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function RedazioneGuidataWizard() {
  const [passo, setPasso] = useState<PassoWizard>(1)
  const [cliente, setCliente] = useState<RedazioneCliente | null>(null)
  const [fascicolo, setFascicolo] = useState<RedazioneFascicolo | null>(null)
  const [contesto, setContesto] = useState<RedazioneContesto | null>(null)
  const [contestoCaricamento, setContestoCaricamento] = useState(false)
  const [modello, setModello] = useState<{ code: string; name: string } | null>(null)

  const selezionaFascicolo = (voce: RedazioneFascicolo) => {
    if (!cliente) return
    setFascicolo(voce)
    setContesto(null)
    setContestoCaricamento(true)
    setPasso(3)
    getRedazioneContesto(voce.id, cliente.id)
      .then(setContesto)
      .finally(() => setContestoCaricamento(false))
  }

  const indietro = () => {
    if (passo === 4) {
      setModello(null)
      setPasso(3)
    } else if (passo === 3) {
      setFascicolo(null)
      setContesto(null)
      setPasso(2)
    } else if (passo === 2) {
      setCliente(null)
      setPasso(1)
    }
  }

  return (
    <section className="iu-rg iu-od-card" aria-label="Nuova redazione guidata">
      <header className="iu-rg-head">
        <div>
          <p className="iu-redazione-eyebrow">Nuova redazione</p>
          <h2>Dal fascicolo reale all'atto pronto nell'editor</h2>
          <span>
            {cliente ? `Cliente: ${cliente.label}` : 'Seleziona il cliente per iniziare'}
            {fascicolo ? ` - Fascicolo: ${fascicolo.numero || fascicolo.titolo}` : ''}
            {modello ? ` - Atto: ${modello.name}` : ''}
          </span>
        </div>
        {passo > 1 ? (
          <Button type="button" tone="neutral" onClick={indietro}>
            <ArrowLeft size={16} aria-hidden="true" />
            Indietro
          </Button>
        ) : null}
      </header>
      <IntestazionePassi passo={passo} />
      {passo === 1 ? (
        <PassoCliente
          onSeleziona={(voce) => {
            setCliente(voce)
            setPasso(2)
          }}
        />
      ) : null}
      {passo === 2 && cliente ? <PassoFascicolo cliente={cliente} onSeleziona={selezionaFascicolo} /> : null}
      {passo === 3 ? (
        contestoCaricamento || !contesto ? (
          <LoadingState title="Lettura del fascicolo" message="Estrazione di parti, ufficio, valore causa, allegati e condizioni." />
        ) : contesto.ok ? (
          <PassoTipoAtto
            contesto={contesto}
            onSeleziona={(code, name) => {
              setModello({ code, name })
              setPasso(4)
            }}
          />
        ) : (
          <EmptyState title="Contesto non disponibile" message={contesto.errore} />
        )
      ) : null}
      {passo === 4 && modello && fascicolo && cliente ? (
        <PassoAnteprima
          modelCode={modello.code}
          modelName={modello.name}
          fascicoloId={fascicolo.id}
          clienteId={cliente.id}
          onGenerato={(editorUrl) => {
            window.location.assign(editorUrl)
          }}
        />
      ) : null}
    </section>
  )
}
