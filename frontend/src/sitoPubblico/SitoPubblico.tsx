import { PAGINE_SITO } from './PagineSito'
import { percorsiSito, type DatiPaginaSito } from './tipi'

/**
 * Sito pubblico dello studio: cornice (navigazione, intestazione, piè di pagina, avviso cookie) e pagina.
 * Lo stesso componente produce l'HTML pre-generato sul server (renderToString) e lo idrata nel browser
 * (hydrateRoot): nessun valore che cambi fra le due esecuzioni (date, finestra, casualità).
 * La <nav> è sorella dell'<header>, non figlia: il backdrop-filter dell'header altrimenti farebbe da
 * contenitore al position:fixed del menu laterale su mobile.
 */
export function SitoPubblico({ dati }: { dati: DatiPaginaSito }) {
  const { payload } = dati
  const site = payload.site
  const percorsi = percorsiSito(site.public_slug)
  const Pagina = PAGINE_SITO[dati.vista]
  const whatsapp = site.whatsapp_number.replace(/\+/g, '').replace(/ /g, '')
  return (
    <>
      <a className="studio-site-skip-link" href="#contenuto-principale">Salta al contenuto principale</a>
      <div className="studio-site-nav-backdrop" id="studioSiteNavBackdrop" aria-hidden="true"/>
      <nav className="studio-site-nav" id="studioSiteNav" aria-label="Navigazione principale">
        <div className="studio-site-nav-drawer-header">
          <span className="studio-site-nav-drawer-title">{site.site_name}</span>
          <button type="button" className="studio-site-nav-close" aria-label="Chiudi menu"><i className="bi bi-x-lg"/></button>
        </div>
        <a href={percorsi.home}><i className="bi bi-house"/><span>Home</span></a>
        {payload.menu_pages.map((pagina) => <a key={pagina.slug} href={percorsi.pagina(pagina.slug)}><span>{pagina.title}</span></a>)}
        {payload.articles.length ? <a href={percorsi.articoli}><i className="bi bi-newspaper"/><span>Articoli</span></a> : null}
        {payload.booking_enabled ? <a href={percorsi.prenota}><i className="bi bi-calendar-check"/><span>Prenota</span></a> : null}
        <a href={percorsi.contatti}><i className="bi bi-envelope"/><span>Contatti</span></a>
        {payload.show_legal_tools ? <a href={percorsi.strumenti}><i className="bi bi-calculator"/><span>Strumenti legali</span></a> : null}
        {payload.show_applications ? <a href={percorsi.applicazioni}><i className="bi bi-grid"/><span>Applicazioni</span></a> : null}
        {payload.show_legal_news ? <a href={percorsi.news}><i className="bi bi-globe"/><span>News giuridiche</span></a> : null}
      </nav>
      <header className="studio-site-header">
        <div className="container">
          <a href={percorsi.home} className="studio-site-brand">
            {site.logo_url
              ? <img src={site.logo_url} alt={site.site_name} className="studio-site-brand-logo"/>
              : <span className="studio-site-brand-mark">{(site.site_name || 'S').slice(0, 1)}</span>}
            <span>
              <strong>{site.site_name}</strong>
              <small>{site.city}{site.province ? ` - ${site.province}` : ''}</small>
            </span>
          </a>
          <button className="studio-site-nav-toggle" type="button" aria-controls="studioSiteNav" aria-expanded="false" aria-label="Apri menu di navigazione">
            <i className="bi bi-list"/><span>Menu</span>
          </button>
        </div>
      </header>
      <main className="studio-site-main" id="contenuto-principale">
        <Pagina dati={dati} percorsi={percorsi}/>
      </main>
      <footer className="studio-site-footer">
        <div className="container py-4 d-flex flex-column flex-lg-row justify-content-between gap-3">
          <div>
            <strong>{site.site_name}</strong>
            <div className="text-white-50 small">{site.site_description}</div>
          </div>
          <div className="small text-white-50">
            {site.address ? <div>{site.address}</div> : null}
            {site.city ? <div>{site.city}{site.province ? ` (${site.province})` : ''}</div> : null}
            {site.contact_phone ? <div>{site.contact_phone}</div> : null}
            {site.contact_email ? <div>{site.contact_email}</div> : null}
            <div className="studio-site-social-links mt-2">
              {whatsapp ? <a className="text-white-50" href={`https://wa.me/${whatsapp}`} target="_blank" rel="noopener">WhatsApp</a> : null}
              {site.facebook_url ? <a className="text-white-50" href={site.facebook_url} target="_blank" rel="noopener">Facebook</a> : null}
              {site.instagram_url ? <a className="text-white-50" href={site.instagram_url} target="_blank" rel="noopener">Instagram</a> : null}
              {site.linkedin_url ? <a className="text-white-50" href={site.linkedin_url} target="_blank" rel="noopener">LinkedIn</a> : null}
            </div>
            {site.privacy_url ? <div><a className="text-white-50" href={site.privacy_url}>Privacy policy</a></div> : null}
            {site.cookie_policy_url ? <div><a className="text-white-50" href={site.cookie_policy_url}>Cookie policy</a></div> : null}
            {site.accessibility_statement_url ? <div><a className="text-white-50" href={site.accessibility_statement_url}>Accessibilità</a></div> : null}
            {site.legal_disclaimer ? <div className="mt-2">{site.legal_disclaimer}</div> : null}
          </div>
        </div>
      </footer>
      {site.cookie_banner_enabled ? (
        <div className="studio-site-cookie-banner" data-cookie-banner hidden>
          <div>
            <strong>Preferenze cookie</strong>
            <p className="mb-0">Usiamo solo cookie tecnici. Eventuali analytics vengono caricati solo dopo il consenso.</p>
          </div>
          <div className="d-flex gap-2">
            <button className="btn btn-sm btn-outline-light" type="button" data-cookie-reject>Solo necessari</button>
            <button className="btn btn-sm btn-light" type="button" data-cookie-accept>Accetta analytics</button>
          </div>
        </div>
      ) : null}
    </>
  )
}
