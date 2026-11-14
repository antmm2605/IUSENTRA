import { ParagrafiRicchi, TestoRicco } from './TestoRicco'
import { ModuloContatto } from './ModuliSito'
import type { ContestoBlocco } from './BlocchiVetrina'

/** Blocchi di contenuto del sito pubblico (testi, servizi, team, articoli, FAQ, sedi, inviti): markup dei blocchi Jinja. */
function Sezione({ classe, extra = '', children }: { classe: string; extra?: string; children: React.ReactNode }) {
  return <section className={`studio-site-section${extra}${classe}`}><div className="container">{children}</div></section>
}

export function TestoLibero({ blocco, classe }: ContestoBlocco) {
  return (
    <Sezione classe={classe}>
      {blocco.title ? <h2><TestoRicco testo={blocco.title}/></h2> : null}
      <div className="studio-site-copy"><ParagrafiRicchi testo={blocco.text}/></div>
    </Sezione>
  )
}

export function Servizi({ blocco, payload, classe }: ContestoBlocco) {
  return (
    <Sezione classe={classe}>
      <div className="d-flex justify-content-between align-items-end gap-3 flex-wrap">
        <div>
          <h2><TestoRicco testo={blocco.title || 'Di cosa si occupa lo studio'}/></h2>
          <p className="text-muted mb-0"><TestoRicco testo={blocco.subtitle || 'Aree operative e servizi presentati in modo chiaro sul sito studio.'}/></p>
        </div>
      </div>
      <div className="row g-4 mt-1">
        {payload.services.map((voce, numero) => (
          <div key={numero} className="col-md-6 col-xl-4">
            <article className="studio-site-card h-100">
              <div className="studio-site-card-icon"><i className={`bi ${voce.icon || 'bi-briefcase'}`}/></div>
              <h3>{voce.title}</h3>
              <p>{voce.short_description}</p>
            </article>
          </div>
        ))}
      </div>
    </Sezione>
  )
}

function Scheda({ icona, titolo, testo }: { icona?: string; titolo: string; testo: string }) {
  return (
    <div className="col-md-6 col-xl-4">
      <article className="studio-site-card h-100">
        {icona !== undefined ? <div className="studio-site-card-icon"><i className={`bi ${icona}`}/></div> : null}
        <h3>{titolo}</h3>
        <p>{testo}</p>
      </article>
    </div>
  )
}

export function Griglia({ blocco, payload, classe }: ContestoBlocco) {
  const strumenti = blocco.type === 'legal_tools' && payload.legal_tools.length
  const applicazioni = blocco.type === 'applications' && payload.applications.length
  return (
    <Sezione classe={classe}>
      <h2><TestoRicco testo={blocco.title}/></h2>
      {blocco.subtitle ? <p className="text-muted"><TestoRicco testo={blocco.subtitle}/></p> : null}
      <div className="row g-4 mt-1">
        {strumenti
          ? payload.legal_tools.map((voce, numero) => <Scheda key={numero} icona={voce.icon} titolo={voce.title} testo={voce.subtitle}/>)
          : applicazioni
            ? payload.applications.map((voce, numero) => <Scheda key={numero} icona={voce.icon} titolo={voce.title} testo={voce.summary}/>)
            : (blocco.items || []).map((voce, numero) => (
              <div key={numero} className="col-md-6 col-xl-4">
                <article className="studio-site-card h-100">
                  <h3><TestoRicco testo={voce.title}/></h3>
                  <p><TestoRicco testo={voce.text}/></p>
                </article>
              </div>
            ))}
      </div>
    </Sezione>
  )
}

export function Team({ blocco, payload, classe }: ContestoBlocco) {
  return (
    <Sezione classe={classe} extra=" studio-site-section-muted">
      <h2><TestoRicco testo={blocco.title || 'Professionisti'}/></h2>
      <div className="row g-4">
        {payload.professionals.map((voce, numero) => (
          <div key={numero} className="col-md-6 col-xl-4">
            <article className="studio-site-card h-100">
              <h3>{voce.full_name}</h3>
              {voce.role_title ? <div className="studio-site-small-label">{voce.role_title}</div> : null}
              <p>{voce.bio}</p>
              {voce.email || voce.phone ? (
                <div className="small text-muted">
                  {voce.email ? <div>{voce.email}</div> : null}
                  {voce.phone ? <div>{voce.phone}</div> : null}
                </div>
              ) : null}
            </article>
          </div>
        ))}
      </div>
    </Sezione>
  )
}

export function UltimiArticoli({ blocco, payload, percorsi, classe }: ContestoBlocco) {
  const notizie = blocco.type === 'legal_news' && payload.legal_news.length
  return (
    <Sezione classe={classe}>
      <div className="d-flex justify-content-between align-items-end flex-wrap gap-3">
        <div>
          <h2><TestoRicco testo={blocco.title || 'Ultimi articoli'}/></h2>
          <p className="text-muted mb-0">Approfondimenti, orientamenti e contenuti editoriali dello studio.</p>
        </div>
        {payload.articles.length ? <a href={percorsi.articoli} className="btn btn-outline-dark">Tutti gli articoli</a> : null}
      </div>
      <div className="row g-4 mt-1">
        {notizie
          ? payload.legal_news.map((voce, numero) => (
            <div key={numero} className="col-md-6 col-xl-4">
              <article className="studio-site-card h-100">
                <div className="studio-site-small-label">{voce.source_name || 'Fonte'}</div>
                <h3>{voce.title}</h3>
                <p>{voce.summary}</p>
                {voce.url ? <a className="btn btn-link p-0" href={voce.url} rel="noopener" target="_blank">Fonte ufficiale</a> : null}
              </article>
            </div>
          ))
          : payload.latest_articles.map((voce, numero) => (
            <div key={numero} className="col-md-6 col-xl-4">
              <article className="studio-site-card h-100">
                {voce.cover_url ? <img src={voce.cover_url} alt={voce.title} className="studio-site-cover" loading="lazy"/> : null}
                <div className="studio-site-small-label">{voce.category || 'Approfondimento'}</div>
                <h3>{voce.title}</h3>
                <p>{voce.excerpt}</p>
                <a className="btn btn-link p-0" href={percorsi.articolo(voce.slug)}>Leggi l'articolo</a>
              </article>
            </div>
          ))}
      </div>
    </Sezione>
  )
}

export function Faq({ blocco, indice, classe }: ContestoBlocco) {
  const id = `faq-${indice}`
  return (
    <Sezione classe={classe} extra=" studio-site-section-muted">
      <h2><TestoRicco testo={blocco.title || 'Domande frequenti'}/></h2>
      <div className="accordion studio-site-faq" id={id}>
        {(blocco.items || []).map((voce, numero) => (
          <div key={numero} className="accordion-item">
            <h3 className="accordion-header">
              <button className="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target={`#${id}-${numero + 1}`}>
                <TestoRicco testo={voce.title}/>
              </button>
            </h3>
            <div id={`${id}-${numero + 1}`} className="accordion-collapse collapse" data-bs-parent={`#${id}`}>
              <div className="accordion-body"><TestoRicco testo={voce.text}/></div>
            </div>
          </div>
        ))}
      </div>
    </Sezione>
  )
}

export function BloccoContatto({ blocco, percorsi, classe }: ContestoBlocco) {
  return (
    <Sezione classe={classe} extra=" studio-site-section-muted">
      <h2><TestoRicco testo={blocco.title || 'Contatta lo studio'}/></h2>
      <ModuloContatto percorsi={percorsi}/>
    </Sezione>
  )
}

export function MappaSedi({ blocco, payload, classe }: ContestoBlocco) {
  return (
    <Sezione classe={classe}>
      <h2><TestoRicco testo={blocco.title || 'Dove siamo'}/></h2>
      <div className="row g-4">
        {payload.offices.map((sede) => (
          <div key={sede.id} className="col-md-6">
            <article className="studio-site-card h-100">
              <h3>{sede.name}</h3>
              <p className="mb-2">
                {sede.address ? <>{sede.address}<br/></> : null}
                {sede.city}{sede.province ? ` (${sede.province})` : ''}
              </p>
              {sede.phone ? <div className="small text-muted">{sede.phone}</div> : null}
              {sede.email ? <div className="small text-muted">{sede.email}</div> : null}
              {sede.opening_hours ? <div className="small mt-2">{sede.opening_hours}</div> : null}
              {sede.map_url ? <a className="btn btn-outline-dark mt-3" href={sede.map_url} target="_blank" rel="noopener">Apri mappa</a> : null}
            </article>
          </div>
        ))}
      </div>
    </Sezione>
  )
}

export function Sedi({ blocco, payload, classe }: ContestoBlocco) {
  return (
    <Sezione classe={classe}>
      <h2><TestoRicco testo={blocco.title || 'Sedi dello studio'}/></h2>
      <div className="row g-4">
        {payload.offices.map((sede) => (
          <div key={sede.id} className="col-md-6 col-xl-4"><article className="studio-site-card h-100"><h3>{sede.name}</h3><p>{sede.address} {sede.city}</p><div className="small text-muted">{sede.phone} {sede.email}</div></article></div>
        ))}
      </div>
    </Sezione>
  )
}

function Invito({ titolo, testo, href, pulsante, classe }: { titolo: string; testo: string; href: string; pulsante: string; classe: string }) {
  return (
    <Sezione classe={classe}>
      <div className="studio-site-cta">
        <div>
          <h2><TestoRicco testo={titolo}/></h2>
          <p className="mb-0"><TestoRicco testo={testo}/></p>
        </div>
        <a className="btn btn-light btn-lg" href={href}>{pulsante}</a>
      </div>
    </Sezione>
  )
}

export function InvitoPrenotazione({ blocco, payload, percorsi, classe }: ContestoBlocco) {
  if (!payload.booking_enabled) return null
  return <Invito classe={classe} titolo={blocco.title || 'Prenota un appuntamento'} testo={blocco.text || 'Agenda appuntamenti clienti con fasce orarie pubbliche e conferma interna dello studio.'} href={percorsi.prenota} pulsante={blocco.button_text || 'Apri agenda'}/>
}

export function InvitoContatto({ blocco, payload, percorsi, classe }: ContestoBlocco) {
  return <Invito classe={classe} titolo={blocco.title || 'Richiedi supporto allo studio'} testo={blocco.text || payload.site.site_description} href={blocco.button_url || percorsi.contatti} pulsante={blocco.button_text || 'Contattaci'}/>
}

export function SchedaGenerica({ blocco, classe }: ContestoBlocco) {
  return (
    <Sezione classe={classe}>
      <article className="studio-site-card">
        <div className="studio-site-small-label">{blocco.type.replace(/_/g, ' ')}</div>
        <h2><TestoRicco testo={blocco.title}/></h2>
        {blocco.subtitle ? <p className="lead"><TestoRicco testo={blocco.subtitle}/></p> : null}
        {blocco.text ? <div className="studio-site-copy"><ParagrafiRicchi testo={blocco.text}/></div> : null}
      </article>
    </Sezione>
  )
}
