import { Lock, PencilLine, ShieldAlert, UserCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { IusStatusBadge } from '@/components/iusentra'
import { NormativeArticleLink } from '@/components/NormativeArticleLink'
import { formatDateIt } from '@/formatting'
import type { Passaggio } from '../types'
import type { BozzaNote } from '../api'
import { ApriBozzaNote } from './ApriBozzaNote'

const TONO_STATO: Record<string, 'success' | 'info' | 'warning' | 'danger' | 'neutral'> = {
  eseguito: 'success',
  proposto: 'info',
  da_confermare: 'warning',
  da_chiedere: 'danger',
  escluso_dallo_studio: 'neutral',
}

const VINCOLI: Record<string, string> = {
  termine_perentorio: 'termine perentorio',
  deposito_non_autonomo: 'deposito riservato al difensore',
  conferma_avvocato: 'decisione riservata all’avvocato',
}

function valoreVisibile(valore: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(valore) ? formatDateIt(valore, valore) : valore
}

// Un passaggio: che cosa ha fatto il software, con quale regola, norma, prove
// e dati; accanto, le regole dello studio applicate o rifiutate.
export function PassaggioCard({ passaggio, onCorreggi, bozza, fascicoloId }: {
  passaggio: Passaggio
  onCorreggi?: (passaggio: Passaggio) => void
  bozza?: BozzaNote
  fascicoloId?: string
}) {
  const campi = Object.entries(passaggio.campi)
  const campiBozza = bozza?.campi_da_completare ?? []
  const campiDagliAtti = campiBozza.filter((campo) => campo !== 'data dell’atto')
  return (
    <li className={`iu-passaggio is-${passaggio.stato}`}>
      <div className="iu-passaggio__testa">
        <IusStatusBadge tone={TONO_STATO[passaggio.stato] || 'neutral'}>{passaggio.statoEtichetta}</IusStatusBadge>
        <strong className="iu-passaggio__titolo">{passaggio.titolo}</strong>
        {bozza && fascicoloId ? <ApriBozzaNote fascicoloId={fascicoloId} chiave={passaggio.chiave} documentoId={bozza.documento_id} /> : null}
        {onCorreggi ? (
          <Button type="button" variant="outline" size="sm" onClick={() => onCorreggi(passaggio)} aria-label={`Correggi la regola del passaggio «${passaggio.titolo}»`}>
            <PencilLine data-icon="inline-start" />
            Correggi la regola
          </Button>
        ) : null}
      </div>
      <p className="iu-passaggio__regola">
        <span>Regola del software</span> {passaggio.regola.descrizione}
        {passaggio.confidenza !== null ? <em> · affidabilità {Math.round(passaggio.confidenza * 100)}%</em> : null}
      </p>
      {bozza?.documento && fascicoloId ? (
        <p>Provvedimento · <a href={`/fascicoli/${encodeURIComponent(fascicoloId)}/documenti/${encodeURIComponent(bozza.documento_id)}/visualizza`}>{bozza.documento}</a>{bozza.sezione_provvedimento ? ` · ${bozza.sezione_provvedimento}` : ''}</p>
      ) : null}
      {campiDagliAtti.length > 0 && fascicoloId ? (
        <p>Da completare prima del PDF ({campiDagliAtti.join(', ')}).{' '}
          {bozza?.ricorso_da_acquisire ? (
            <>Acquisisci «{bozza.ricorso_da_acquisire.atto}». La cancelleria ha accettato la busta {bozza.ricorso_da_acquisire.busta}
              {bozza.ricorso_da_acquisire.data ? ` del ${valoreVisibile(bozza.ricorso_da_acquisire.data)}` : ''}.</>
          ) : null}{' '}
          <a href={`/fascicoli/${encodeURIComponent(fascicoloId)}#documenti`}>Apri gli atti del fascicolo</a>.
        </p>
      ) : null}
      {passaggio.norme.length ? (
        <p className="iu-passaggio__norme">
          <span>Norma</span>{' '}
          {passaggio.norme.map((norma, indice) => (
            <span key={norma.id}>
              {indice ? '; ' : ''}
                {norma.reader_url
                  ? <a href={norma.reader_url} target="_blank" rel="noreferrer" title={norma.verifica || norma.titolo}>{norma.norma}</a>
                  : norma.url ? <NormativeArticleLink url={norma.url} article={norma.norma}>{norma.norma}</NormativeArticleLink> : norma.norma}
            </span>
          ))}
        </p>
      ) : null}
      {passaggio.prove.length || passaggio.dati.length || campi.length ? (
        <dl className="iu-passaggio__dettagli">
          {passaggio.prove.map((prova, indice) => (
            <div key={`p${indice}`}><dt>Letto in {prova.fonte || prova.tipo}</dt><dd>«{prova.estratto}»</dd></div>
          ))}
          {passaggio.dati.map((dato) => (
            <div key={`d${dato.etichetta}`}><dt>{dato.etichetta}</dt><dd>{valoreVisibile(dato.valore)}{dato.fonte ? <small> ({dato.fonte})</small> : null}</dd></div>
          ))}
          {campi.map(([nome, campo]) => (
            <div key={`c${nome}`}>
              <dt>{campo.vincolato ? <Lock size={12} aria-label="fissato dalla norma" /> : null} {campo.etichetta}</dt>
              <dd>
                {valoreVisibile(campo.valore)}
                {campo.valoreSoftware ? <small> (il software proponeva {valoreVisibile(campo.valoreSoftware)})</small> : null}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
      {passaggio.vincoli.length ? (
        <p className="iu-passaggio__vincoli"><Lock size={13} /> {passaggio.vincoli.map((vincolo) => VINCOLI[vincolo] || vincolo).join(' · ')}</p>
      ) : null}
      {passaggio.regoleStudioApplicate.map((regola) => (
        <p className="iu-passaggio__studio" key={`a${regola.id}`}>
          <UserCheck size={14} /> <strong>{regola.etichetta}</strong> — {regola.descrizione}
          {regola.autore ? ` (${regola.autore})` : ''}
          {regola.motivo ? <small> · {regola.motivo}</small> : null}
        </p>
      ))}
      {passaggio.regoleStudioRifiutate.map((regola) => (
        <p className="iu-passaggio__rifiuto" key={`r${regola.id}`} role="note">
          <ShieldAlert size={14} /> <strong>{regola.etichetta} non applicata</strong> — {regola.rifiuto?.motivo}
        </p>
      ))}
    </li>
  )
}
