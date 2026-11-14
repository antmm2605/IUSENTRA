/**
 * Sito pubblico dello studio (`/web/<slug>/...`): dati pubblici passati dal server.
 * Lo stesso oggetto serve alla pre-generazione (Node, renderToString) e all'idratazione nel browser:
 * contiene solo i campi che le pagine mostrano, mai dati interni dello studio.
 */
export type ElementoBlocco = {
  title?: string
  text?: string
  image_url?: string
  image_alt?: string
  button_url?: string
  button_text?: string
}

export type BloccoSito = ElementoBlocco & {
  type: string
  subtitle?: string
  style_variant?: string
  visibility?: { mobile?: boolean }
  items?: ElementoBlocco[]
}

export type SitoDati = {
  site_name: string
  site_title: string
  site_description: string
  public_slug: string
  logo_url: string
  city: string
  province: string
  address: string
  contact_phone: string
  contact_email: string
  whatsapp_number: string
  facebook_url: string
  instagram_url: string
  linkedin_url: string
  privacy_url: string
  cookie_policy_url: string
  accessibility_statement_url: string
  legal_disclaimer: string
  cookie_banner_enabled: boolean
  hero_claim: string
}

export type PaginaSito = { title: string; slug: string; excerpt: string; body_json: BloccoSito[] }
export type ArticoloSito = PaginaSito & { category: string; cover_url: string }
export type ServizioSito = { title: string; icon: string; short_description: string }
export type ProfessionistaSito = { full_name: string; role_title: string; bio: string; email: string; phone: string }
export type SedeSito = {
  id: number
  name: string
  address: string
  city: string
  province: string
  phone: string
  email: string
  opening_hours: string
  map_url: string
}
export type StrumentoSito = { title: string; subtitle: string; icon: string; category: string }
export type ApplicazioneSito = { title: string; summary: string; icon: string; badge: string; section_title: string; access_mode: string }
export type NotiziaSito = { title: string; summary: string; url: string; source_name: string; matter_name: string; publication_date: string }

export type PayloadSito = {
  site: SitoDati
  menu_pages: { title: string; slug: string }[]
  articles: ArticoloSito[]
  latest_articles: ArticoloSito[]
  services: ServizioSito[]
  professionals: ProfessionistaSito[]
  offices: SedeSito[]
  booking_enabled: boolean
  show_legal_tools: boolean
  show_applications: boolean
  show_legal_news: boolean
  legal_tools: StrumentoSito[]
  applications: ApplicazioneSito[]
  legal_news: NotiziaSito[]
  template_code: string
}

export type VistaSito =
  | 'home'
  | 'pagina'
  | 'articoli'
  | 'articolo'
  | 'contatti'
  | 'prenota'
  | 'strumenti-legali'
  | 'applicazioni'
  | 'news-giuridiche'

export type DatiPaginaSito = {
  vista: VistaSito
  payload: PayloadSito
  pagina?: PaginaSito | null
  articolo?: ArticoloSito | null
}

/** Indirizzi del sito come `url_for` di `studio_site_public`. */
export function percorsiSito(slug: string) {
  const base = `/web/${encodeURIComponent(slug)}`
  return {
    home: `${base}/`,
    pagina: (pagina: string) => `${base}/pagina/${encodeURIComponent(pagina)}`,
    articoli: `${base}/articoli`,
    articolo: (articolo: string) => `${base}/articoli/${encodeURIComponent(articolo)}`,
    contatti: `${base}/contatti`,
    prenota: `${base}/prenota`,
    strumenti: `${base}/strumenti-legali`,
    applicazioni: `${base}/applicazioni`,
    news: `${base}/news-giuridiche`,
    slot: `${base}/api/slot-disponibili`,
  }
}

export type PercorsiSito = ReturnType<typeof percorsiSito>
