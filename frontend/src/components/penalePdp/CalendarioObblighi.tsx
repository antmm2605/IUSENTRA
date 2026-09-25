import { CalendarRange } from 'lucide-react'
import { Badge } from '../dashboard'

type Voce = { dal: string; uffici: string[]; inVigore: boolean }

/** Da quando il PDP è l'unico canale di deposito, per ufficio (art. 111-bis c.p.p.; D.M. 217/2023 e modifiche). */
export function CalendarioObblighi({ calendario, fonte }: { calendario: Voce[]; fonte: string }) {
  return (
    <section className="iu-pdp-pagina__calendario">
      <h2><CalendarRange size={17}/> Obbligo del deposito telematico penale</h2>
      <ol>
        {calendario.map((v) => (
          <li key={v.dal}>
            <Badge tone={v.inVigore ? 'success' : 'neutral'}>{v.inVigore ? 'In vigore' : 'Dal'} {new Date(`${v.dal}T00:00:00`).toLocaleDateString('it-IT')}</Badge>
            <span>{v.uffici.join(' · ')}</span>
          </li>
        ))}
      </ol>
      <small>Prima della data d’obbligo restano ammessi PEC e deposito cartaceo. Fonte: {fonte}.</small>
    </section>
  )
}
