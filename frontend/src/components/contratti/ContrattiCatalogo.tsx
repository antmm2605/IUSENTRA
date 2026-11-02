import { useEffect, useMemo, useState } from 'react'
import { BookOpenCheck, FilePlus2, FileSignature, Landmark, Scale, Search } from 'lucide-react'
import {
  ETICHETTE_FORMA,
  ETICHETTE_QUALIFICAZIONE,
  ETICHETTE_STATO,
  dataItaliana,
  dataOraItaliana,
  getCatalogo,
  getPratiche,
  type Catalogo,
  type SintesiPratica,
} from '../../contrattiData'
import { Badge, type BadgeTone } from '../../ui/Badge'
import { EmptyState } from '../../ui/EmptyState'
import { LoadingState } from '../../ui/LoadingState'
import { Page } from '../../ui/Page'
import { Panel } from '../../ui/Panel'

export const TONO_STATO: Record<string, BadgeTone> = {
  bozza: 'neutral',
  in_revisione: 'warning',
  approvato: 'success',
  firmato: 'primary',
  archiviato: 'info',
}

function normalizza(testo: string): string {
  return testo.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
}

function Pratiche({ pratiche }: { pratiche: SintesiPratica[] | null }) {
  if (pratiche === null) return <LoadingState title="Caricamento delle pratiche" />
  if (!pratiche.length) {
    return <EmptyState title="Nessuna pratica contrattuale" message="Scegli un contratto dal catalogo qui sotto per avviare la prima pratica guidata." />
  }
  return (
    <ul className="iu-ctr-pratiche">
      {pratiche.map((pratica) => (
        <li key={pratica.id}>
          <a href={`/contratti/pratiche/${pratica.id}`} className="iu-ctr-pratica">
            <span className="iu-ctr-pratica__titolo">{pratica.titolo}</span>
            <span className="iu-ctr-pratica__meta">{pratica.contratto_nome}{pratica.cliente ? ` · ${pratica.cliente}` : ''}</span>
            <span className="iu-ctr-pratica__piede">
              <Badge tone={TONO_STATO[pratica.stato] || 'neutral'}>{ETICHETTE_STATO[pratica.stato] || pratica.stato}</Badge>
              <small>Aggiornata il {dataOraItaliana(pratica.aggiornata_il)}</small>
            </span>
          </a>
        </li>
      ))}
    </ul>
  )
}

function RegoleComuni({ catalogo }: { catalogo: Catalogo }) {
  const regole = catalogo.regole_comuni
  return (
    <div className="iu-ctr-regole">
      <details>
        <summary><Scale size={16} aria-hidden="true" /> Regole comuni a tutti i contratti ({regole.regole_comuni.length})</summary>
        <table className="iu-ctr-tabella">
          <tbody>{regole.regole_comuni.map(([voce, norma]) => <tr key={voce}><td>{voce}</td><td>{norma}</td></tr>)}</tbody>
        </table>
      </details>
      <details>
        <summary><Landmark size={16} aria-hidden="true" /> Dimensione internazionale</summary>
        <table className="iu-ctr-tabella">
          <tbody>{regole.dimensione_internazionale.map(([voce, norma]) => <tr key={voce}><td>{voce}</td><td>{norma}</td></tr>)}</tbody>
        </table>
      </details>
      <details>
        <summary><BookOpenCheck size={16} aria-hidden="true" /> Novità normative 2026 ({regole.novita_2026.length})</summary>
        <ul className="iu-ctr-novita">
          {regole.novita_2026.map((novita) => (
            <li key={novita.id}><strong>{novita.titolo}</strong><span>{novita.norma}</span><small>Decorrenza: {dataItaliana(novita.decorrenza)}</small></li>
          ))}
        </ul>
      </details>
    </div>
  )
}

export function ContrattiCatalogo() {
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null)
  const [pratiche, setPratiche] = useState<SintesiPratica[] | null>(null)
  const [area, setArea] = useState('')
  const [ricerca, setRicerca] = useState('')
  const [soloGuidati, setSoloGuidati] = useState(false)

  useEffect(() => {
    let attivo = true
    getCatalogo().then((dati) => { if (attivo) setCatalogo(dati) })
    getPratiche().then((dati) => { if (attivo) setPratiche(dati.ok ? dati.pratiche : []) })
    return () => { attivo = false }
  }, [])

  const aree = useMemo(() => {
    if (!catalogo?.ok) return []
    const chiave = normalizza(ricerca.trim())
    return catalogo.aree
      .filter((voce) => !area || voce.id === area)
      .map((voce) => ({
        ...voce,
        voci: voce.voci.filter((c) => (!soloGuidati || c.guidato) && (!chiave || normalizza(`${c.nome} ${c.riferimenti.join(' ')}`).includes(chiave))),
      }))
      .filter((voce) => voce.voci.length)
  }, [catalogo, area, ricerca, soloGuidati])

  const trovati = aree.reduce((somma, voce) => somma + voce.voci.length, 0)

  return (
    <Page
      title="Contratti"
      subtitle="Catalogo della contrattualistica dello studio: scegli il contratto, rispondi alle domande guidate e ottieni controlli, bozza e scheda pronti per la revisione."
      className="iu-ctr"
    >
      <Panel title="Pratiche contrattuali" subtitle="Le redazioni in corso, con lo stato di revisione.">
        <Pratiche pratiche={pratiche} />
      </Panel>

      <Panel title="Catalogo dei contratti" subtitle={catalogo?.ok ? `${catalogo.totale} contratti in ${catalogo.aree.length} aree · ricognizione normativa al ${dataItaliana(catalogo.data_ricognizione)}` : undefined}>
        {!catalogo ? <LoadingState title="Caricamento del catalogo" /> : null}
        {catalogo && !catalogo.ok ? <EmptyState title="Catalogo non disponibile" message={catalogo.message} /> : null}
        {catalogo?.ok ? (
          <>
            <p className="iu-ctr-avviso">
              Lo studio redige e negozia il testo; quando la legge richiede atto pubblico, scrittura autenticata, autorizzazioni o
              trascrizione, la scheda lo segnala. I riferimenti normativi vanno verificati sulla fonte ufficiale vigente
              (<a href={catalogo.fonte_ufficiale_consultazione} target="_blank" rel="noreferrer">Normattiva</a>) prima dell'uso.
            </p>
            <RegoleComuni catalogo={catalogo} />
            <div className="iu-ctr-filtri">
              <label className="iu-ctr-cerca">
                <Search size={16} aria-hidden="true" />
                <input type="search" value={ricerca} placeholder="Cerca contratto o norma (es. locazione, 1742, franchising)" aria-label="Cerca nel catalogo" onChange={(evento) => { const valore = evento.currentTarget.value; setRicerca(valore) }} />
              </label>
              <label>
                <span>Area</span>
                <select value={area} onChange={(evento) => { const valore = evento.currentTarget.value; setArea(valore) }}>
                  <option value="">Tutte le aree</option>
                  {catalogo.aree.map((voce) => <option key={voce.id} value={voce.id}>{voce.titolo} ({voce.voci.length})</option>)}
                </select>
              </label>
              <label className="iu-ctr-check">
                <input type="checkbox" checked={soloGuidati} onChange={(evento) => { const valore = evento.currentTarget.checked; setSoloGuidati(valore) }} />
                <span>Solo con questionario specifico</span>
              </label>
            </div>
            <p className="iu-ctr-conteggio" aria-live="polite">{trovati} contratti trovati</p>
            {!trovati ? <EmptyState title="Nessun contratto corrisponde ai filtri" message="Modifica la ricerca: per operazioni non tipizzate usa i contratti atipici (art. 1322 c.c.)." /> : null}
            {aree.map((voce) => (
              <section key={voce.id} className="iu-ctr-area" aria-labelledby={`area-${voce.id}`}>
                <h3 id={`area-${voce.id}`}>{voce.titolo}</h3>
                <div className="iu-ctr-griglia">
                  {voce.voci.map((c) => (
                    <a key={c.id} href={`/contratti/nuovo/${c.id}`} className="iu-ctr-card">
                      <span className="iu-ctr-card__nome"><FileSignature size={16} aria-hidden="true" />{c.nome}</span>
                      <span className="iu-ctr-card__norme">{c.riferimenti.slice(0, 3).join(' · ')}</span>
                      <span className="iu-ctr-card__badge">
                        <Badge tone="neutral">{ETICHETTE_QUALIFICAZIONE[c.qualificazione] || c.qualificazione}</Badge>
                        {c.guidato ? <Badge tone="primary">Questionario specifico</Badge> : null}
                        {c.pubblico_ufficiale ? <Badge tone="warning">{ETICHETTE_FORMA[c.forma]}</Badge> : null}
                      </span>
                      <span className="iu-ctr-card__azione"><FilePlus2 size={14} aria-hidden="true" /> Avvia pratica</span>
                    </a>
                  ))}
                </div>
              </section>
            ))}
          </>
        ) : null}
      </Panel>
    </Page>
  )
}
