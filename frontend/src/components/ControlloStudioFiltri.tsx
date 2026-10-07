import { formatDateIt } from '../formatting'
import type { Voce } from './ControlloStudioPage'
export type Filtri = { priorita: string; stato: string; fascicolo: string; da: string; a: string; dataFonte: boolean; ordine: string }
export const FILTRI_VUOTI: Filtri = { priorita: '', stato: '', fascicolo: '', da: '', a: '', dataFonte: false, ordine: 'urgenza' }
export function ControlloStudioFiltri({ voci, filtri, onChange }: { voci: Voce[]; filtri: Filtri; onChange: (f: Filtri) => void }) {
  const set = (key: keyof Filtri, value: string | boolean) => onChange({ ...filtri, [key]: value })
  const stati = [...new Set(voci.map(v => v.etichetta).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'it'))
  const fascicoli = [...new Map(voci.filter(v => v.fascicolo.id).map(v => [v.fascicolo.id, v.fascicolo])).values()]
  return <div className="iu-cs-filtri-extra" aria-label="Filtri dell’area selezionata">
    <label>Priorità<select value={filtri.priorita} onChange={e => set('priorita', e.target.value)}><option value="">Tutte le priorità</option><option value="critica">Critica</option><option value="alta">Alta</option><option value="normale">Normale</option></select></label>
    <label>Stato<select value={filtri.stato} onChange={e => set('stato', e.target.value)}><option value="">Tutti gli stati</option>{stati.map(s => <option key={s}>{s}</option>)}</select></label>
    <label>Fascicolo<select value={filtri.fascicolo} onChange={e => set('fascicolo', e.target.value)}><option value="">Tutti i fascicoli</option><option value="non_collegato">Non collegato</option>{fascicoli.map(f => <option key={f.id} value={f.id}>{f.etichetta}</option>)}</select></label>
    <label>Data da filtrare<select value={filtri.dataFonte ? 'fonte' : 'termine'} onChange={e => set('dataFonte', e.target.value === 'fonte')}><option value="termine">Scadenza / udienza / ricezione</option><option value="fonte">Fonte / creazione del presidio</option></select></label>
    <label>Dal<input type="date" value={filtri.da} onChange={e => set('da', e.target.value)}/></label>
    <label>Al<input type="date" min={filtri.da || undefined} value={filtri.a} onChange={e => set('a', e.target.value)}/></label>
    <label>Ordina<select value={filtri.ordine} onChange={e => set('ordine', e.target.value)}><option value="urgenza">Urgenza</option><option value="recenti">Più recenti</option><option value="vecchie">Meno recenti</option><option value="titolo">Titolo</option></select></label>
  </div>
}
export function filtraVoce(v: Voce, f: Filtri) {
  const dataIt = formatDateIt(f.dataFonte ? v.data_riferimento || v.data : v.data)
  const giorno = dataIt ? `${dataIt.slice(6, 10)}-${dataIt.slice(3, 5)}-${dataIt.slice(0, 2)}` : ''
  return (!f.priorita || v.gravita === f.priorita) && (!f.stato || v.etichetta === f.stato)
    && (!f.fascicolo || (f.fascicolo === 'non_collegato' ? !v.fascicolo.id : v.fascicolo.id === f.fascicolo))
    && (!f.da || Boolean(giorno && giorno >= f.da)) && (!f.a || Boolean(giorno && giorno <= f.a))
}
