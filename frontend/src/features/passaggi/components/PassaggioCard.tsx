import { Lock, PencilLine, ShieldAlert, UserCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { IusStatusBadge } from '@/components/iusentra'
import type { Passaggio } from '../types'

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

// Un passaggio: che cosa ha fatto il software, con quale regola, norma, prove
// e dati; accanto, le regole dello studio applicate o rifiutate.
export function PassaggioCard({ passaggio, onCorreggi }: { passaggio: Passaggio; onCorreggi?: (passaggio: Passaggio) => void }) {
  const campi = Object.entries(passaggio.campi)
  return (
    <li className={`iu-passaggio is-${passaggio.stato}`}>
      <div className="iu-passaggio__testa">
        <IusStatusBadge tone={TONO_STATO[passaggio.stato] || 'neutral'}>{passaggio.statoEtichetta}</IusStatusBadge>
        <strong className="iu-passaggio__titolo">{passaggio.titolo}</strong>
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
      {passaggio.norme.length ? (
        <p className="iu-passaggio__norme">
          <span>Norma</span>{' '}
          {passaggio.norme.map((norma, indice) => (
            <span key={norma.id}>
              {indice ? '; ' : ''}
              {norma.url ? <a href={norma.reader_url || norma.url} target="_blank" rel="noreferrer" title={norma.verifica || norma.titolo}>{norma.norma}</a> : norma.norma}
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
            <div key={`d${dato.etichetta}`}><dt>{dato.etichetta}</dt><dd>{dato.valore}{dato.fonte ? <small> ({dato.fonte})</small> : null}</dd></div>
          ))}
          {campi.map(([nome, campo]) => (
            <div key={`c${nome}`}>
              <dt>{campo.vincolato ? <Lock size={12} aria-label="fissato dalla norma" /> : null} {campo.etichetta}</dt>
              <dd>
                {campo.valore}
                {campo.valoreSoftware ? <small> (il software proponeva {campo.valoreSoftware})</small> : null}
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
