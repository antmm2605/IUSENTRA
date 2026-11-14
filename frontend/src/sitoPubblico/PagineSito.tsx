import { BlocchiSito } from './BlocchiSito'
import { ModuloContatto, ModuloPrenotazione } from './ModuliSito'
import type { ApplicazioneSito, DatiPaginaSito, PercorsiSito, StrumentoSito } from './tipi'

/** Contenuto di ciascuna pagina del sito pubblico (prima i template studio_site/public_*.html). */
type Props = { dati: DatiPaginaSito; percorsi: PercorsiSito }

function Home({ dati, percorsi }: Props) {
  const { payload } = dati
  const opzionali = [
    payload.show_legal_tools ? { titolo: 'Strumenti legali', testo: 'Calcoli, moduli e strumenti operativi pubblici selezionati dallo studio.', href: percorsi.strumenti, azione: 'Apri strumenti' } : null,
    payload.show_applications ? { titolo: 'Applicazioni', testo: 'Moduli e strumenti operativi che lo studio sceglie di rendere visibili sul sito.', href: percorsi.applicazioni, azione: 'Apri applicazioni' } : null,
    payload.show_legal_news ? { titolo: 'News giuridiche strutturate', testo: 'Aggiornamenti giuridici reali pubblicati dallo studio dal presidio interno delle fonti.', href: percorsi.news, azione: 'Apri news' } : null,
  ].filter((voce): voce is NonNullable<typeof voce> => voce !== null)
  return (
    <>
      <BlocchiSito blocchi={dati.pagina?.body_json || []} payload={payload} percorsi={percorsi}/>
      {opzionali.length ? (
        <section className="studio-site-section studio-site-section-muted">
          <div className="container">
            <div className="row g-4">
              {opzionali.map((voce) => (
                <div key={voce.titolo} className="col-lg-4">
                  <article className="studio-site-card h-100">
                    <div className="studio-site-small-label">Sezione opzionale</div>
                    <h3>{voce.titolo}</h3>
                    <p>{voce.testo}</p>
                    <a className="btn btn-outline-dark" href={voce.href}>{voce.azione}</a>
                  </article>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}
    </>
  )
}

function Pagina({ dati, percorsi }: Props) {
  const pagina = dati.pagina
  if (!pagina) return null
  return (
    <>
      <section className="studio-site-section"><div className="container"><h1>{pagina.title}</h1>{pagina.excerpt ? <p className="lead text-muted">{pagina.excerpt}</p> : null}</div></section>
      <BlocchiSito blocchi={pagina.body_json || []} payload={dati.payload} percorsi={percorsi}/>
    </>
  )
}

function Articoli({ dati, percorsi }: Props) {
  return (
    <section className="studio-site-section">
      <div className="container">
        <h1>Articoli e approfondimenti</h1>
        <p className="lead text-muted">Contenuti editoriali pubblicati dallo studio per orientare clienti e imprese.</p>
        <div className="row g-4 mt-2">
          {dati.payload.articles.length ? dati.payload.articles.map((voce) => (
            <div key={voce.slug} className="col-md-6 col-xl-4">
              <article className="studio-site-card h-100">
                {voce.cover_url ? <img src={voce.cover_url} alt={voce.title} className="studio-site-cover"/> : null}
                <div className="studio-site-small-label">{voce.category || 'Approfondimento'}</div>
                <h3>{voce.title}</h3>
                <p>{voce.excerpt}</p>
                <a className="btn btn-link p-0" href={percorsi.articolo(voce.slug)}>Leggi l'articolo</a>
              </article>
            </div>
          )) : <div className="col-12"><div className="alert alert-secondary">Nessun articolo pubblicato al momento.</div></div>}
        </div>
      </div>
    </section>
  )
}

function Articolo({ dati, percorsi }: Props) {
  const articolo = dati.articolo
  if (!articolo) return null
  return (
    <>
      <section className="studio-site-section">
        <div className="container">
          <a href={percorsi.articoli} className="btn btn-link px-0">← Torna agli articoli</a>
          <div className="studio-site-small-label">{articolo.category || 'Approfondimento'}</div>
          <h1>{articolo.title}</h1>
          {articolo.excerpt ? <p className="lead text-muted">{articolo.excerpt}</p> : null}
          {articolo.cover_url ? <img src={articolo.cover_url} alt={articolo.title} className="studio-site-cover studio-site-cover--hero"/> : null}
        </div>
      </section>
      <BlocchiSito blocchi={articolo.body_json || []} payload={dati.payload} percorsi={percorsi}/>
    </>
  )
}

function Contatti({ dati, percorsi }: Props) {
  const site = dati.payload.site
  return (
    <section className="studio-site-section">
      <div className="container">
        <div className="row g-4">
          <div className="col-lg-5">
            <h1>Contatta lo studio</h1>
            <p className="lead text-muted">Richiedi informazioni, una consulenza o un primo confronto operativo.</p>
            <div className="studio-site-card">
              {site.contact_phone ? <div><strong>Telefono:</strong> {site.contact_phone}</div> : null}
              {site.contact_email ? <div><strong>Email:</strong> {site.contact_email}</div> : null}
              {site.address ? <div><strong>Indirizzo:</strong> {site.address}</div> : null}
              {site.city ? <div><strong>Città:</strong> {site.city}{site.province ? ` (${site.province})` : ''}</div> : null}
            </div>
          </div>
          <div className="col-lg-7"><ModuloContatto percorsi={percorsi}/></div>
        </div>
      </div>
    </section>
  )
}

function Prenota({ dati, percorsi }: Props) {
  return (
    <section className="studio-site-section">
      <div className="container">
        <div className="row g-4">
          <div className="col-lg-5">
            <h1>Prenota un appuntamento</h1>
            <p className="lead text-muted">Scegli sede, data e fascia oraria. La richiesta verrà confermata dallo studio dopo la verifica interna.</p>
            <div className="row g-3">
              {dati.payload.offices.map((sede) => (
                <div key={sede.id} className="col-12">
                  <article className="studio-site-card">
                    <h3>{sede.name}</h3>
                    <p className="mb-1">{sede.address}{sede.city ? `, ${sede.city}` : ''}</p>
                    {sede.opening_hours ? <div className="small text-muted">{sede.opening_hours}</div> : null}
                  </article>
                </div>
              ))}
            </div>
          </div>
          <div className="col-lg-7"><ModuloPrenotazione payload={dati.payload} percorsi={percorsi}/></div>
        </div>
      </div>
    </section>
  )
}

/** Gruppi nell'ordine di prima apparizione; le voci senza gruppo in coda, come nei template. */
function raggruppa<T>(voci: T[], gruppo: (voce: T) => string): { nome: string; voci: T[] }[] {
  const ordine: string[] = []
  for (const voce of voci) if (gruppo(voce) && !ordine.includes(gruppo(voce))) ordine.push(gruppo(voce))
  const gruppi = ordine.map((nome) => ({ nome, voci: voci.filter((voce) => gruppo(voce) === nome) }))
  const senza = voci.filter((voce) => !gruppo(voce))
  return senza.length ? [...gruppi, { nome: '', voci: senza }] : gruppi
}

function Catalogo<T extends StrumentoSito | ApplicazioneSito>({ pill, titolo, intro, voci, gruppo, vuoto, iconaVuoto, scheda }: {
  pill: string; titolo: string; intro: string; voci: T[]; gruppo: (voce: T) => string; vuoto: string; iconaVuoto: string; scheda: (voce: T) => React.ReactNode
}) {
  return (
    <>
      <div className="mb-5">
        <div className="studio-site-pill mb-3">{pill}</div>
        <h1 className="mb-2">{titolo}</h1>
        <p className="lead text-muted mb-0 sito-pubblico-intro">{intro}</p>
      </div>
      {voci.length ? raggruppa(voci, gruppo).map((gruppoVoci) => (
        <div key={gruppoVoci.nome || 'senza-gruppo'}>
          {gruppoVoci.nome ? <h2 className="h6 text-uppercase text-muted fw-bold mt-5 mb-3 sito-pubblico-gruppo">{gruppoVoci.nome}</h2> : null}
          <div className={`row g-3${gruppoVoci.nome ? '' : ' mt-2'}`}>{gruppoVoci.voci.map((voce, numero) => <div key={numero} className="col-sm-6 col-lg-4">{scheda(voce)}</div>)}</div>
        </div>
      )) : (
        <div className="studio-site-card text-center py-5"><i className={`bi ${iconaVuoto} fs-1 text-muted d-block mb-3`}/><p className="text-muted mb-0">{vuoto}</p></div>
      )}
    </>
  )
}

function SchedaCatalogo({ icona, titolo, testo, badge, piede, href, azione }: { icona: string; titolo: string; testo: string; badge?: string; piede?: React.ReactNode; href: string; azione: React.ReactNode }) {
  return (
    <div className="studio-site-card h-100 d-flex flex-column sito-pubblico-scheda">
      <div className="d-flex gap-3 align-items-start mb-3">
        <div className="studio-site-card-icon flex-shrink-0 sito-pubblico-icona"><i className={`bi ${icona}`}/></div>
        <div className="min-width-0">
          <div className="d-flex align-items-center gap-2 flex-wrap mb-1">
            <h3 className="mb-0 sito-pubblico-titolo">{titolo}</h3>
            {badge ? <span className="sito-pubblico-badge">{badge}</span> : null}
          </div>
          <p className="mb-0 small text-muted sito-pubblico-testo">{testo}</p>
        </div>
      </div>
      <div className="mt-auto pt-3 d-flex align-items-center justify-content-between gap-2 sito-pubblico-piede">
        {piede}
        <a href={href} className="btn btn-sm sito-pubblico-azione">{azione}</a>
      </div>
    </div>
  )
}

const MODI_ACCESSO: Record<string, { icona: string; testo: string }> = {
  diretta: { icona: 'bi-lightning-charge-fill text-warning', testo: 'Accesso diretto' },
  guidata: { icona: 'bi-signpost text-info', testo: 'Guidato' },
}

function Strumenti({ dati, percorsi }: Props) {
  return (
    <section className="studio-site-section">
      <div className="container">
        <Catalogo pill="Calcolatori professionali" titolo="Strumenti legali" intro="Calcolatori e strumenti operativi che lo studio mette a disposizione. Seleziona lo strumento di interesse e contattaci per una consulenza personalizzata."
          voci={dati.payload.legal_tools} gruppo={(voce) => voce.category} vuoto="Nessuno strumento disponibile al momento." iconaVuoto="bi-tools"
          scheda={(voce) => <SchedaCatalogo icona={voce.icon} titolo={voce.title} testo={voce.subtitle} href={`${percorsi.contatti}?oggetto=${encodeURIComponent(voce.title)}`} azione={<><i className="bi bi-chat-dots me-1"/>Richiedi consulenza</>}/>}/>
        <div className="studio-site-quote-banner mt-5 d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-3">
          <div>
            <p className="mb-1 sito-pubblico-banner-titolo">Hai bisogno di assistenza professionale?</p>
            <p className="mb-0 sito-pubblico-banner-testo">Il nostro team è a disposizione per analizzare il tuo caso e fornirti una consulenza su misura.</p>
          </div>
          <a href={percorsi.contatti} className="btn btn-light flex-shrink-0"><i className="bi bi-envelope me-2"/>Contattaci</a>
        </div>
      </div>
    </section>
  )
}

function Applicazioni({ dati, percorsi }: Props) {
  const prenota = dati.payload.booking_enabled
  return (
    <section className="studio-site-section">
      <div className="container">
        <Catalogo pill="Servizi digitali" titolo="Applicazioni dello studio" intro="Moduli e strumenti operativi che lo studio offre ai propri clienti. Scopri i servizi disponibili e richiedi maggiori informazioni."
          voci={dati.payload.applications} gruppo={(voce) => voce.section_title} vuoto="Nessuna applicazione disponibile al momento." iconaVuoto="bi-grid"
          scheda={(voce) => {
            const modo = MODI_ACCESSO[voce.access_mode] || { icona: 'bi-grid opacity-50', testo: 'Catalogo' }
            return <SchedaCatalogo icona={voce.icon} titolo={voce.title} testo={voce.summary} badge={voce.badge}
              piede={<span className="small text-muted sito-pubblico-modo"><i className={`bi ${modo.icona} me-1`}/>{modo.testo}</span>}
              href={`${percorsi.contatti}?oggetto=${encodeURIComponent(voce.title)}`} azione={<>Info <i className="bi bi-arrow-right ms-1"/></>}/>
          }}/>
        <div className="row g-4 mt-4">
          <div className="col-md-6">
            <div className="studio-site-card h-100 d-flex flex-column">
              <div className="studio-site-card-icon"><i className="bi bi-info-circle"/></div>
              <h3 className="sito-pubblico-titolo">Vuoi saperne di più?</h3>
              <p className="small text-muted flex-grow-1">Contattaci per ricevere informazioni dettagliate sui servizi disponibili e su come possono supportarti.</p>
              <a href={percorsi.contatti} className="btn btn-outline-dark btn-sm align-self-start mt-2"><i className="bi bi-envelope me-1"/>Scrivici</a>
            </div>
          </div>
          <div className="col-md-6">
            <div className="studio-site-card h-100 d-flex flex-column">
              <div className="studio-site-card-icon"><i className={`bi ${prenota ? 'bi-calendar-check' : 'bi-telephone'}`}/></div>
              <h3 className="sito-pubblico-titolo">{prenota ? 'Prenota una consulenza' : 'Richiedi una consulenza'}</h3>
              <p className="small text-muted flex-grow-1">{prenota ? 'Prenota un appuntamento con i nostri professionisti per discutere le tue esigenze specifiche.' : 'Il nostro team è a disposizione per analizzare il tuo caso e fornirti una risposta professionale e puntuale.'}</p>
              <a href={prenota ? percorsi.prenota : percorsi.contatti} className="btn btn-dark btn-sm align-self-start mt-2"><i className={`bi ${prenota ? 'bi-calendar-plus' : 'bi-chat-dots'} me-1`}/>{prenota ? 'Prenota ora' : 'Contattaci'}</a>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function Notizie({ dati }: Props) {
  return (
    <section className="studio-site-section">
      <div className="container">
        <h1>News giuridiche strutturate</h1>
        <p className="lead text-muted">Aggiornamenti selezionati dal presidio normativo e giurisprudenziale dello studio.</p>
        <div className="row g-4">
          {dati.payload.legal_news.length ? dati.payload.legal_news.map((voce, numero) => (
            <div key={numero} className="col-lg-6">
              <article className="studio-site-card h-100">
                <div className="studio-site-small-label">{voce.matter_name || 'Aggiornamento giuridico'}</div>
                <h3>{voce.title}</h3>
                <p>{voce.summary}</p>
                <div className="small text-muted">
                  {voce.publication_date ? <div>{voce.publication_date}</div> : null}
                  {voce.source_name ? <div>{voce.source_name}</div> : null}
                </div>
                {voce.url ? <a className="btn btn-link p-0 mt-3" href={voce.url} target="_blank" rel="noopener">Fonte collegata</a> : null}
              </article>
            </div>
          )) : <div className="col-12"><div className="alert alert-secondary">Nessuna news giuridica pubblicata al momento.</div></div>}
        </div>
      </div>
    </section>
  )
}

export const PAGINE_SITO = {
  home: Home,
  pagina: Pagina,
  articoli: Articoli,
  articolo: Articolo,
  contatti: Contatti,
  prenota: Prenota,
  'strumenti-legali': Strumenti,
  applicazioni: Applicazioni,
  'news-giuridiche': Notizie,
} as const
