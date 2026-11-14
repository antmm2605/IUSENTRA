import type { ComponentType } from 'react'
import * as V from './BlocchiVetrina'
import * as C from './BlocchiContenuto'
import type { BloccoSito, PayloadSito, PercorsiSito } from './tipi'

/**
 * Tutti i tipi di blocco del costruttore del sito (prima `_public_blocks.html`, macro render_blocks):
 * 39 nomi raggruppati come nei rami del template.
 * Un tipo sconosciuto non produce nulla, come nel template.
 */
export const COMPONENTI_BLOCCO: Record<string, ComponentType<V.ContestoBlocco>> = {
  hero: V.Hero,
  hero_split: V.Hero,
  hero_centered: V.Hero,
  hero_slider: V.HeroSlider,
  image_text_slider: V.ImmagineTestoSlider,
  gallery_grid: V.Galleria,
  image_text_split: V.ImmagineTesto,
  logo_strip: V.StrisciaLoghi,
  text_ticker: V.Ticker,
  featured_services_carousel: V.CaroselloServizi,
  article_carousel: V.CaroselloArticoli,
  quote_banner: V.Citazione,
  contact_cta_split: V.ContattoDiviso,
  trust_bar: V.BarraFiducia,
  rich_text: C.TestoLibero,
  services: C.Servizi,
  practice_areas: C.Servizi,
  feature_grid: C.Griglia,
  process_steps: C.Griglia,
  stats: C.Griglia,
  document_checklist: C.Griglia,
  legal_tools: C.Griglia,
  applications: C.Griglia,
  team: C.Team,
  latest_articles: C.UltimiArticoli,
  legal_news: C.UltimiArticoli,
  faq: C.Faq,
  contact_form: C.BloccoContatto,
  office_map: C.MappaSedi,
  offices: C.Sedi,
  booking_cta: C.InvitoPrenotazione,
  cta: C.InvitoContatto,
  newsletter: C.SchedaGenerica,
  privacy_notice: C.SchedaGenerica,
  testimonials_safe: C.SchedaGenerica,
  footer_rich: C.SchedaGenerica,
  service_detail: C.SchedaGenerica,
  professional_profile: C.SchedaGenerica,
  timeline: C.SchedaGenerica,
}

export function BlocchiSito({ blocchi, payload, percorsi }: { blocchi: BloccoSito[]; payload: PayloadSito; percorsi: PercorsiSito }) {
  return (
    <>
      {blocchi.map((blocco, numero) => {
        const Componente = COMPONENTI_BLOCCO[blocco.type]
        if (!Componente) return null
        const classe = blocco.visibility && blocco.visibility.mobile === false ? ' studio-site-hide-mobile' : ''
        return <Componente key={numero} blocco={blocco} payload={payload} percorsi={percorsi} indice={numero + 1} classe={classe}/>
      })}
    </>
  )
}
