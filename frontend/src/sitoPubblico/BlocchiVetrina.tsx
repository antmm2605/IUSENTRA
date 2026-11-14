import type { ReactNode } from 'react'
import { ParagrafiRicchi, TestoRicco } from './TestoRicco'
import type { BloccoSito, PayloadSito, PercorsiSito } from './tipi'

/** Blocchi «vetrina» del sito pubblico (hero, caroselli, gallerie, strisce): stesso markup dei blocchi Jinja. */
export type ContestoBlocco = { blocco: BloccoSito; payload: PayloadSito; percorsi: PercorsiSito; indice: number; classe: string }

function Controlli({ id, quanti }: { id: string; quanti: number }) {
  if (quanti <= 1) return null
  return (
    <>
      <button className="carousel-control-prev" type="button" data-bs-target={`#${id}`} data-bs-slide="prev"><span className="carousel-control-prev-icon" aria-hidden="true"/><span className="visually-hidden">Precedente</span></button>
      <button className="carousel-control-next" type="button" data-bs-target={`#${id}`} data-bs-slide="next"><span className="carousel-control-next-icon" aria-hidden="true"/><span className="visually-hidden">Successivo</span></button>
    </>
  )
}

function Segnaposto({ icona }: { icona: string }) {
  return <div className="studio-site-hero-placeholder"><i className={`bi ${icona}`}/></div>
}

export function Hero({ blocco, payload, percorsi, classe }: ContestoBlocco) {
  const site = payload.site
  const primario = blocco.button_url || (payload.booking_enabled ? percorsi.prenota : percorsi.contatti)
  const centrato = blocco.type === 'hero_centered'
  const immagine = blocco.image_url || site.logo_url
  return (
    <section className={`studio-site-hero studio-site-hero--${blocco.style_variant || blocco.type}${classe}`}>
      <div className="container">
        <div className={`row align-items-center g-4 ${centrato ? 'justify-content-center text-center' : ''}`}>
          <div className={centrato ? 'col-lg-9' : 'col-lg-7'}>
            <span className="studio-site-pill">Studio legale digitale</span>
            <h1><TestoRicco testo={blocco.title || site.site_name}/></h1>
            <p className="lead"><TestoRicco testo={blocco.subtitle || site.hero_claim || site.site_description}/></p>
            <div className="d-flex flex-wrap gap-2">
              <a className="btn btn-primary btn-lg" href={primario}>{blocco.button_text || 'Contatta lo studio'}</a>
              <a className="btn btn-outline-dark btn-lg" href={percorsi.contatti}>Parla con noi</a>
            </div>
          </div>
          {centrato ? null : (
            <div className="col-lg-5">
              <div className="studio-site-hero-card">
                {immagine ? <img src={immagine} alt={blocco.image_alt || site.site_name} className="img-fluid rounded-4"/> : <Segnaposto icona="bi-buildings"/>}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

export function HeroSlider({ blocco, payload, percorsi, indice, classe }: ContestoBlocco) {
  const id = `hero-slider-${indice}`
  const voci = blocco.items || []
  return (
    <section className={`studio-site-hero studio-site-hero-slider${classe}`}>
      <div className="container">
        <div id={id} className="carousel slide" data-bs-ride="carousel">
          <div className="carousel-inner">
            {voci.map((voce, numero) => (
              <div key={numero} className={`carousel-item ${numero === 0 ? 'active' : ''}`}>
                <div className="row align-items-center g-4">
                  <div className="col-lg-7">
                    <span className="studio-site-pill">Studio legale</span>
                    <h1><TestoRicco testo={voce.title || blocco.title || payload.site.site_name}/></h1>
                    <p className="lead"><TestoRicco testo={voce.text || blocco.subtitle || payload.site.site_description}/></p>
                    <a className="btn btn-primary btn-lg" href={voce.button_url || blocco.button_url || percorsi.contatti}>{voce.button_text || blocco.button_text || 'Contatta lo studio'}</a>
                  </div>
                  <div className="col-lg-5">
                    <div className="studio-site-hero-card">
                      {voce.image_url || blocco.image_url
                        ? <img src={voce.image_url || blocco.image_url} alt={voce.image_alt || blocco.image_alt || voce.title || blocco.title || ''} className="img-fluid rounded-4"/>
                        : <Segnaposto icona="bi-bank"/>}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <Controlli id={id} quanti={voci.length}/>
        </div>
      </div>
    </section>
  )
}

function Intestazione({ blocco, titolo }: { blocco: BloccoSito; titolo?: string }) {
  const testo = blocco.title || titolo
  return (
    <>
      {testo ? <h2><TestoRicco testo={testo}/></h2> : null}
      {blocco.subtitle ? <p className="text-muted"><TestoRicco testo={blocco.subtitle}/></p> : null}
    </>
  )
}

export function ImmagineTestoSlider({ blocco, indice, classe }: ContestoBlocco) {
  const id = `image-text-slider-${indice}`
  const voci = blocco.items || []
  return (
    <section className={`studio-site-section${classe}`}>
      <div className="container">
        <Intestazione blocco={blocco}/>
        <div id={id} className="carousel slide studio-site-card" data-bs-ride="carousel">
          <div className="carousel-inner">
            {voci.map((voce, numero) => (
              <div key={numero} className={`carousel-item ${numero === 0 ? 'active' : ''}`}>
                <div className="row align-items-center g-4">
                  <div className="col-md-5">
                    {voce.image_url ? <img className="studio-site-cover mb-0" src={voce.image_url} alt={voce.image_alt || voce.title || ''} loading="lazy"/> : <Segnaposto icona="bi-journal-text"/>}
                  </div>
                  <div className="col-md-7">
                    <h3><TestoRicco testo={voce.title}/></h3>
                    <p><TestoRicco testo={voce.text}/></p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <Controlli id={id} quanti={voci.length}/>
        </div>
      </div>
    </section>
  )
}

export function Galleria({ blocco, classe }: ContestoBlocco) {
  return (
    <section className={`studio-site-section${classe}`}>
      <div className="container">
        <Intestazione blocco={blocco} titolo="Galleria dello studio"/>
        <div className="row g-3">
          {(blocco.items || []).map((voce, numero) => (
            <div key={numero} className="col-md-6 col-xl-4">
              <article className="studio-site-card h-100">
                {voce.image_url ? <img className="studio-site-cover" src={voce.image_url} alt={voce.image_alt || voce.title || ''} loading="lazy"/> : null}
                <h3><TestoRicco testo={voce.title}/></h3>
                {voce.text ? <p><TestoRicco testo={voce.text}/></p> : null}
              </article>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export function ImmagineTesto({ blocco, percorsi, classe }: ContestoBlocco) {
  return (
    <section className={`studio-site-section${classe}`}>
      <div className="container">
        <div className="row align-items-center g-4">
          <div className="col-lg-6">
            {blocco.image_url ? <img className="studio-site-cover mb-0" src={blocco.image_url} alt={blocco.image_alt || blocco.title || ''} loading="lazy"/> : <Segnaposto icona="bi-folder2-open"/>}
          </div>
          <div className="col-lg-6">
            <h2><TestoRicco testo={blocco.title}/></h2>
            {blocco.subtitle ? <p className="lead"><TestoRicco testo={blocco.subtitle}/></p> : null}
            {blocco.text ? <div className="studio-site-copy"><ParagrafiRicchi testo={blocco.text}/></div> : null}
            {blocco.button_text ? <a className="btn btn-primary" href={blocco.button_url || percorsi.contatti}>{blocco.button_text}</a> : null}
          </div>
        </div>
      </div>
    </section>
  )
}

function Striscia({ blocco, classe, contenitore }: { blocco: BloccoSito; classe: string; contenitore: string }) {
  return (
    <section className={`studio-site-section studio-site-section-compact${classe}`}>
      <div className="container">
        {contenitore === 'studio-site-logo-strip' && blocco.title ? <h2 className="h4"><TestoRicco testo={blocco.title}/></h2> : null}
        <div className={contenitore}>
          {(blocco.items || []).map((voce, numero) => <div key={numero}><strong><TestoRicco testo={voce.title}/></strong><span><TestoRicco testo={voce.text}/></span></div>)}
        </div>
      </div>
    </section>
  )
}

export function StrisciaLoghi({ blocco, classe }: ContestoBlocco) {
  return <Striscia blocco={blocco} classe={classe} contenitore="studio-site-logo-strip"/>
}

export function BarraFiducia({ blocco, classe }: ContestoBlocco) {
  return <Striscia blocco={blocco} classe={classe} contenitore="studio-site-trust-bar"/>
}

export function Ticker({ blocco, classe }: ContestoBlocco) {
  return (
    <section className={`studio-site-section-compact${classe}`}>
      <div className="studio-site-ticker" aria-label={blocco.title || 'Avvisi dello studio'}>
        <div>{(blocco.items || []).map((voce, numero) => <span key={numero}><TestoRicco testo={voce.text || voce.title}/></span>)}</div>
      </div>
    </section>
  )
}

function Carosello({ id, classe, blocco, titolo, voci }: { id: string; classe: string; blocco: BloccoSito; titolo: string; voci: ReactNode[] }) {
  return (
    <section className={`studio-site-section${classe}`}>
      <div className="container">
        <Intestazione blocco={blocco} titolo={titolo}/>
        <div id={id} className="carousel slide" data-bs-ride="carousel">
          <div className="carousel-inner">
            {voci.map((voce, numero) => <div key={numero} className={`carousel-item ${numero === 0 ? 'active' : ''}`}>{voce}</div>)}
          </div>
          <Controlli id={id} quanti={voci.length}/>
        </div>
      </div>
    </section>
  )
}

export function CaroselloServizi({ blocco, payload, indice, classe }: ContestoBlocco) {
  return (
    <Carosello id={`service-carousel-${indice}`} classe={classe} blocco={blocco} titolo="Servizi in evidenza" voci={payload.services.map((voce, numero) => (
      <article key={numero} className="studio-site-card">
        <div className="studio-site-card-icon"><i className={`bi ${voce.icon || 'bi-briefcase'}`}/></div>
        <h3>{voce.title}</h3>
        <p>{voce.short_description}</p>
      </article>
    ))}/>
  )
}

export function CaroselloArticoli({ blocco, payload, percorsi, indice, classe }: ContestoBlocco) {
  return (
    <Carosello id={`article-carousel-${indice}`} classe={classe} blocco={blocco} titolo="Articoli in evidenza" voci={payload.latest_articles.map((voce, numero) => (
      <article key={numero} className="studio-site-card">
        {voce.cover_url ? <img className="studio-site-cover" src={voce.cover_url} alt={voce.title} loading="lazy"/> : null}
        <div className="studio-site-small-label">{voce.category || 'Approfondimento'}</div>
        <h3>{voce.title}</h3>
        <p>{voce.excerpt}</p>
        <a className="btn btn-link p-0" href={percorsi.articolo(voce.slug)}>Leggi l'articolo</a>
      </article>
    ))}/>
  )
}

export function Citazione({ blocco, classe }: ContestoBlocco) {
  return (
    <section className={`studio-site-section${classe}`}>
      <div className="container">
        <blockquote className="studio-site-quote-banner">
          <p><TestoRicco testo={blocco.text}/></p>
          {blocco.title ? <footer><TestoRicco testo={blocco.title}/></footer> : null}
        </blockquote>
      </div>
    </section>
  )
}

export function ContattoDiviso({ blocco, percorsi, classe }: ContestoBlocco) {
  return (
    <section className={`studio-site-section${classe}`}>
      <div className="container">
        <div className="studio-site-contact-split">
          <div>
            <h2><TestoRicco testo={blocco.title}/></h2>
            <p><TestoRicco testo={blocco.text}/></p>
            <a className="btn btn-light btn-lg" href={blocco.button_url || percorsi.contatti}>{blocco.button_text || 'Contatta lo studio'}</a>
          </div>
          {blocco.image_url ? <img src={blocco.image_url} alt={blocco.image_alt || blocco.title || ''} loading="lazy"/> : null}
        </div>
      </div>
    </section>
  )
}
